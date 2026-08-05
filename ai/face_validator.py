import logging
import os
from io import BytesIO
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)


# Primary detector: OpenCV YuNet (DNN-based, far more accurate than Haar).
# We try several candidate paths so it works in dev and in bundled apps.
_YUNET_CANDIDATES = [
    os.path.join(os.path.dirname(__file__), "models", "face_detection_yunet.onnx"),
    os.path.join(os.path.expanduser("~"), ".cache", "opencv", "face_detection_yunet.onnx"),
    os.path.join(os.path.dirname(cv2.__file__), "data", "face_detection_yunet.onnx"),
]
_yunet_path: Optional[str] = next((p for p in _YUNET_CANDIDATES if os.path.exists(p)), None)
_yunet = None


def _get_yunet():
    """Lazy-init the YuNet detector with sensible defaults.

    If the ONNX model is not present locally, tries to fetch it from the
    OpenCV zoo once, then caches it under ``ai/models/``.
    """
    global _yunet, _yunet_path
    if _yunet is not None:
        return _yunet
    if not _yunet_path:
        _yunet_path = _try_download_yunet()
    if not _yunet_path:
        return None
    try:
        _yunet = cv2.FaceDetectorYN.create(
            _yunet_path, "", (320, 320),
            score_threshold=0.6,   # accept only confident detections
            nms_threshold=0.3,
            top_k=50,
        )
        logger.info("Loaded YuNet face detector from %s", _yunet_path)
    except Exception as exc:
        logger.warning("Failed to load YuNet: %s", exc)
        _yunet = None
    return _yunet


def _try_download_yunet() -> Optional[str]:
    """Download the YuNet ONNX model to ai/models/. Returns the local path."""
    import urllib.request
    models_dir = os.path.join(os.path.dirname(__file__), "models")
    os.makedirs(models_dir, exist_ok=True)
    out = os.path.join(models_dir, "face_detection_yunet.onnx")
    if os.path.exists(out):
        return out
    url = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
        with open(out, "wb") as f:
            f.write(data)
        logger.info("Downloaded YuNet model to %s (%d bytes)", out, len(data))
        return out
    except Exception as exc:
        logger.warning("Failed to download YuNet model: %s", exc)
        return None


# Fallback ensemble: multiple Haar cascades OR'd together.  Each cascade
# catches faces the others miss.  Profile face helps with side-angle shots.
_FALLBACK_CASCADES = []
if hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades"):
    try:
        _FALLBACK_CASCADES = [
            cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml"),
            cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml"),
            cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_alt.xml"),
            cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml"),
        ]
    except Exception:
        _FALLBACK_CASCADES = []



def _detect_faces_hair_ensemble(gray: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Run the Haar-cascade ensemble and return deduped (x,y,w,h) boxes."""
    boxes: list[tuple[int, int, int, int]] = []
    seen: set[tuple[int, int]] = set()
    for cascade in _FALLBACK_CASCADES:
        if cascade.empty():
            continue
        detected = cascade.detectMultiScale(
            gray, scaleFactor=1.05, minNeighbors=4, minSize=(40, 40), maxSize=(gray.shape[1], gray.shape[0])
        )
        for x, y, w, h in detected:
            # Coarse dedup: snap to a 40-pixel grid and skip near-duplicates.
            key = (int(x) // 40, int(y) // 40)
            if key in seen:
                continue
            seen.add(key)
            boxes.append((int(x), int(y), int(w), int(h)))
    return boxes


def _detect_faces_yunet(rgb: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Run the YuNet detector and return (x, y, w, h) boxes."""
    detector = _get_yunet()
    if detector is None:
        return []
    h, w = rgb.shape[:2]
    detector.setInputSize((w, h))
    _, faces = detector.detect(rgb)
    if faces is None:
        return []
    return [(int(f[0]), int(f[1]), int(f[2]), int(f[3])) for f in faces]


def _merge_boxes(boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    """Cluster near-duplicate boxes (one cluster = one real face).

    ``cv2.groupRectangles`` requires more than one input box to cluster;
    with a single box it returns ``[]``.  For 0 or 1 box we short-circuit.
    """
    if not boxes:
        return []
    if len(boxes) == 1:
        return [boxes[0]]

    arr = np.array(boxes, dtype=np.int32)
    # ``groupRectangles`` returns (rectangles, weights) - weights are votes.
    grouped, _ = cv2.groupRectangles(arr, groupThreshold=1, eps=0.5)
    if len(grouped) == 0:
        # No clustering happened (all boxes are far apart) - keep the originals.
        return boxes
    return [(int(r[0]), int(r[1]), int(r[2]), int(r[3])) for r in grouped]


def validate_selfie(image_bytes: bytes) -> tuple[bool, str]:
    """Check that the image contains exactly one clear face.

    Returns (ok, message).  ``message`` is an Egyptian-Arabic user-facing
    string when ``ok`` is False, or the literal ``"done"`` when True.
    """
    try:
        image = Image.open(BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image)
    except Exception:
        return False, "تعذر قراءة الصورة"


    if image.mode != "RGB":
        image = image.convert("RGB")

    img_w, img_h = image.size
    total_area = img_w * img_h
    if total_area < 10_000:
        return False, "الصورة صغيرة أوي، ابعتلي صورة أكبر"

    np_image = np.array(image)
    # Slight upscaling helps YuNet on very small faces.
    if min(img_w, img_h) < 320:
        scale = 320.0 / min(img_w, img_h)
        np_image = cv2.resize(np_image, (int(img_w * scale), int(img_h * scale)),
                              interpolation=cv2.INTER_CUBIC)
        img_w, img_h = np_image.shape[1], np_image.shape[0]
        total_area = img_w * img_h

    # Histogram equalization on Y channel - helps in low light.
    ycrcb = cv2.cvtColor(np_image, cv2.COLOR_RGB2YCrCb)
    ycrcb[:, :, 0] = cv2.equalizeHist(ycrcb[:, :, 0])
    preprocessed = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2RGB)
    gray = cv2.cvtColor(preprocessed, cv2.COLOR_RGB2GRAY)

    # Primary: YuNet.  Fallback: ensemble of Haar cascades.
    boxes = _detect_faces_yunet(preprocessed)
    if not boxes:
        boxes = _detect_faces_hair_ensemble(gray)
    boxes = _merge_boxes(boxes)

    if len(boxes) == 0:
        return False, "مفيش وش واضح في الصورة، صوِّر سيلفي وبوشك للكاميرا 📸"

    if len(boxes) > 1:
        return False, "لأزم تكون لوحدك في الصورة من غير ناس تانية 🙏"

    x, y, w, h = boxes[0]
    face_area = w * h
    face_ratio = face_area / total_area

    # WhatsApp selfies often put the face at 5-20% of frame.  Drop the
    # old 15% threshold to 4% so legitimate close-ups aren't rejected.
    if face_ratio < 0.04:
        return False, "وشك بعيد أوي في الصورة، خليك أقرب شوية 📏"

    # Reject faces at the very edge (cropped heads).
    if x < 10 or y < 10 or (x + w) > img_w - 10 or (y + h) > img_h - 10:
        return False, "وشك متقطع من الصورة، صوِّر راسك كامل من غير قصّ 🖼️"

    return True, "done"
