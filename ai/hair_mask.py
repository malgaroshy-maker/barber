"""Generate a hair-region mask for inpainting-based hair swap.

The mask is meant to cover the hair (the area to replace) while keeping the
face untouched.  Uses OpenCV YuNet (DNN-based) as the primary face detector
for accuracy, with a 4-cascade Haar ensemble fallback.

White pixels = region to inpaint (hair).
Black pixels = region to preserve (face / body / background).
"""

import logging
import os
from io import BytesIO
from typing import Optional

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# YuNet primary detector (shared model with face_validator).
_YUNET_CANDIDATES = [
    os.path.join(os.path.dirname(__file__), "models", "face_detection_yunet.onnx"),
    os.path.join(os.path.expanduser("~"), ".cache", "opencv", "face_detection_yunet.onnx"),
    os.path.join(os.path.dirname(cv2.__file__), "data", "face_detection_yunet.onnx"),
]
_yunet_path: Optional[str] = next((p for p in _YUNET_CANDIDATES if os.path.exists(p)), None)
_yunet = None


def _get_yunet():
    """Lazy-init the YuNet detector. Tries a download if the model is missing."""
    global _yunet, _yunet_path
    if _yunet is not None:
        return _yunet
    if not _yunet_path:
        try:
            from ai.face_validator import _try_download_yunet
            _yunet_path = _try_download_yunet()
        except Exception:
            return None
    if not _yunet_path:
        return None
    try:
        _yunet = cv2.FaceDetectorYN.create(
            _yunet_path, "", (320, 320),
            score_threshold=0.5, nms_threshold=0.3, top_k=10,
        )
    except Exception as exc:
        logger.warning("Failed to load YuNet for hair mask: %s", exc)
        _yunet = None
    return _yunet


# Fallback: 4-cascade Haar ensemble.
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



def _detect_face(rgb: np.ndarray, gray: np.ndarray) -> Optional[tuple[int, int, int, int]]:
    """Return (x, y, w, h) of the most prominent face, or None."""
    detector = _get_yunet()
    if detector is not None:
        h, w = rgb.shape[:2]
        detector.setInputSize((w, h))
        _, faces = detector.detect(rgb)
        if faces is not None and len(faces) > 0:
            f = max(faces, key=lambda f: f[2] * f[3])
            return (int(f[0]), int(f[1]), int(f[2]), int(f[3]))
    # Fallback ensemble
    boxes: list[tuple[int, int, int, int]] = []
    seen: set[tuple[int, int]] = set()
    for cascade in _FALLBACK_CASCADES:
        if cascade.empty():
            continue
        detected = cascade.detectMultiScale(
            gray, scaleFactor=1.05, minNeighbors=4, minSize=(40, 40)
        )
        for x, y, w, h in detected:
            key = (int(x) // 40, int(y) // 40)
            if key in seen:
                continue
            seen.add(key)
            boxes.append((int(x), int(y), int(w), int(h)))
    if not boxes:
        return None
    return max(boxes, key=lambda b: b[2] * b[3])


SHORT_CUT_IDS = {
    "buzz_cut", "crew_cut", "caesar_cut", "french_crop",
    "fade_low", "fade_mid_skin", "ivy_league", "textured_crop"
}

FADE_CUT_IDS = {
    "fade_classic", "fade_drop", "fade_mid_skin", "fade_low", "fade_high",
    "burst_fade", "undercut", "tapered_curls", "high_top", "buzz_cut", "crew_cut", "french_crop"
}


def create_hair_mask(image_bytes: bytes, padding: float = 0.40, haircut_id: Optional[str] = None) -> bytes:
    """Return a PNG mask image (same size as input) covering the hair region.

    The mask covers the hair on top and sides (including temples & sideburns)
    while preserving the face, eyes, and beard. Uses a multi-region approach.

    White = region to inpaint (hair).
    Black = region to preserve (face / body / background).
    """
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    img_w, img_h = image.size
    np_image = np.array(image)
    gray = cv2.cvtColor(np_image, cv2.COLOR_RGB2GRAY)

    face = _detect_face(np_image, gray)

    if face is None:
        logger.warning("No face detected for hair mask; falling back to top 40% mask")
        # Fallback: mask the top 40% of the image.
        mask = np.zeros((img_h, img_w), dtype=np.uint8)
        cutoff = int(img_h * 0.40)
        mask[:cutoff, :] = 255
        return _encode_mask(mask)

    x, y, w, h = face

    mask = np.zeros((img_h, img_w), dtype=np.uint8)

    # Dynamic top clearance:
    # Short cuts (buzz cut, crew cut) need a tight top mask so SD doesn't draw an extended bald scalp.
    # Volume cuts (pompadour, afro) get more top headroom.
    if haircut_id and haircut_id in SHORT_CUT_IDS:
        head_top = max(0, int(y - 0.22 * h))
    else:
        head_top = max(0, int(y - 0.55 * h))
    
    # Forehead/eyebrow level (covers upper forehead bangs down to just above eyebrows)
    forehead_bottom = int(y + h * 0.28)
    
    # Dynamic side & ear level (for fades/tapers, cover down past sideburns to y + 0.70*h)
    if haircut_id and haircut_id in FADE_CUT_IDS:
        ear_level = int(y + h * 0.70)
        side_extension = int(w * 0.35)
        inner_left = x + int(w * 0.08)
        inner_right = x + int(w * 0.92)
    else:
        ear_level = int(y + h * 0.58)
        side_extension = int(w * 0.30)
        inner_left = x
        inner_right = x + w
    
    # Region 1: Top hair (dome over head bounded by face width + side extension)
    top_pts = np.array([
        [max(0, x - side_extension), head_top],
        [max(0, x - side_extension), forehead_bottom],
        [min(img_w, x + w + side_extension), forehead_bottom],
        [min(img_w, x + w + side_extension), head_top],
    ], dtype=np.int32)
    cv2.fillPoly(mask, [top_pts], 255)
    
    # Region 2: Left side hair & sideburn area (temple taper)
    left_side_pts = np.array([
        [max(0, x - side_extension), forehead_bottom],
        [max(0, x - side_extension), ear_level],
        [inner_left, ear_level],
        [inner_left, forehead_bottom],
    ], dtype=np.int32)
    cv2.fillPoly(mask, [left_side_pts], 255)
    
    # Region 3: Right side hair & sideburn area (temple taper)
    right_side_pts = np.array([
        [inner_right, forehead_bottom],
        [inner_right, ear_level],
        [min(img_w, x + w + side_extension), ear_level],
        [min(img_w, x + w + side_extension), forehead_bottom],
    ], dtype=np.int32)
    cv2.fillPoly(mask, [right_side_pts], 255)

    # Blur mask edges for smoother inpainting & skin transitions
    mask = cv2.GaussianBlur(mask, (35, 35), 0)

    return _encode_mask(mask)


def _encode_mask(mask_array: np.ndarray) -> bytes:
    """Encode a grayscale mask array as PNG bytes."""
    success, encoded = cv2.imencode(".png", mask_array)
    if not success:
        raise RuntimeError("Failed to encode hair mask as PNG")
    return encoded.tobytes()
