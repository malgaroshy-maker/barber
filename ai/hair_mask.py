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
from PIL import Image, ImageOps

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



def _detect_face_and_landmarks(rgb: np.ndarray, gray: np.ndarray) -> Optional[dict]:
    """Return dict with face bounding box (x,y,w,h) and 5 landmarks (eyes, nose, mouth) or None."""
    detector = _get_yunet()
    if detector is not None:
        h, w = rgb.shape[:2]
        detector.setInputSize((w, h))
        _, faces = detector.detect(rgb)
        if faces is not None and len(faces) > 0:
            f = max(faces, key=lambda f: f[2] * f[3])
            return {
                "bbox": (int(f[0]), int(f[1]), int(f[2]), int(f[3])),
                "right_eye": (float(f[4]), float(f[5])),
                "left_eye": (float(f[6]), float(f[7])),
                "nose": (float(f[8]), float(f[9])),
                "right_mouth": (float(f[10]), float(f[11])),
                "left_mouth": (float(f[12]), float(f[13])),
            }
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
    bx, by, bw, bh = max(boxes, key=lambda b: b[2] * b[3])
    # Synthesize estimated landmarks from Haar bounding box
    return {
        "bbox": (bx, by, bw, bh),
        "right_eye": (bx + bw * 0.30, by + bh * 0.35),
        "left_eye": (bx + bw * 0.70, by + bh * 0.35),
        "nose": (bx + bw * 0.50, by + bh * 0.55),
        "right_mouth": (bx + bw * 0.35, by + bh * 0.75),
        "left_mouth": (bx + bw * 0.65, by + bh * 0.75),
    }


def _detect_face(rgb: np.ndarray, gray: np.ndarray) -> Optional[tuple[int, int, int, int]]:
    """Return (x, y, w, h) of the most prominent face, or None."""
    res = _detect_face_and_landmarks(rgb, gray)
    if res is None:
        return None
    return res["bbox"]


VERY_SHORT_CUT_IDS = {
    "buzz_cut", "crew_cut", "caesar_cut", "ivy_league"
}

HIGH_VOLUME_CUT_IDS = {
    "pompadour", "afro", "high_top", "man_bun"
}

FADE_CUT_IDS = {
    "fade_classic", "fade_drop", "fade_mid_skin", "fade_low", "fade_high",
    "burst_fade", "undercut", "tapered_curls", "high_top", "buzz_cut", "crew_cut", "french_crop"
}


def create_hair_mask(image_bytes: bytes, padding: float = 0.40, haircut_id: Optional[str] = None) -> bytes:
    """Return a PNG mask image (same size as input) covering the hair region.

    The mask covers the hair on top and sides while preserving the face,
    eyes, ears, earlobes, and beard. Uses a multi-region approach.

    White = region to inpaint (hair).
    Black = region to preserve (face / body / background / ears).
    """
    raw_img = Image.open(BytesIO(image_bytes))
    image = ImageOps.exif_transpose(raw_img).convert("RGB")

    img_w, img_h = image.size
    np_image = np.array(image)
    gray = cv2.cvtColor(np_image, cv2.COLOR_RGB2GRAY)

    face = _detect_face(np_image, gray)

    if face is None:
        logger.warning("No face detected for hair mask; falling back to top 40% mask")
        mask = np.zeros((img_h, img_w), dtype=np.uint8)
        cutoff = int(img_h * 0.40)
        mask[:cutoff, :] = 255
        return _encode_mask(mask)

    x, y, w, h = face

    mask = np.zeros((img_h, img_w), dtype=np.uint8)

    # Balanced top clearance to prevent both 'big head' (too tall) and 'smashed head' (too flat):
    if haircut_id and haircut_id in VERY_SHORT_CUT_IDS:
        head_top = max(0, int(y - 0.22 * h))
    elif haircut_id and haircut_id in HIGH_VOLUME_CUT_IDS:
        head_top = max(0, int(y - 0.42 * h))
    else:
        # Standard cuts (french_crop, fade_classic, quiff, etc.) get natural 0.32*h height
        head_top = max(0, int(y - 0.32 * h))

    # Forehead level (strictly above eyebrows to preserve 100% of eyebrows and upper face)
    forehead_bottom = int(y + h * 0.18)
    ear_level = int(y + h * 0.50)
    side_extension = int(w * 0.25)

    # Calculate smooth head dome ellipse parameters
    center_x = int(x + w * 0.50)
    center_y = forehead_bottom
    radius_x = int(w * 0.70)
    radius_y = max(10, int(forehead_bottom - head_top))

    # Draw smooth upper dome ellipse covering head crown (180 to 360 degrees)
    cv2.ellipse(mask, (center_x, center_y), (radius_x, radius_y), 0, 180, 360, 255, -1)

    # Fill base rect between forehead level and dome height
    top_rect = np.array([
        [max(0, center_x - radius_x), head_top + int(radius_y * 0.4)],
        [max(0, center_x - radius_x), forehead_bottom],
        [min(img_w, center_x + radius_x), forehead_bottom],
        [min(img_w, center_x + radius_x), head_top + int(radius_y * 0.4)],
    ], dtype=np.int32)
    cv2.fillPoly(mask, [top_rect], 255)

    # Region 2: Left side hair (temple area down to ear level)
    left_side_pts = np.array([
        [max(0, x - side_extension), forehead_bottom],
        [max(0, x - side_extension), ear_level],
        [x, ear_level],
        [x, forehead_bottom],
    ], dtype=np.int32)
    cv2.fillPoly(mask, [left_side_pts], 255)

    # Region 3: Right side hair (temple area down to ear level)
    right_side_pts = np.array([
        [x + w, forehead_bottom],
        [x + w, ear_level],
        [min(img_w, x + w + side_extension), ear_level],
        [min(img_w, x + w + side_extension), forehead_bottom],
    ], dtype=np.int32)
    cv2.fillPoly(mask, [right_side_pts], 255)

    # Gaussian blur (35x35) for smooth edge feathering & realistic skin blending
    mask = cv2.GaussianBlur(mask, (35, 35), 0)


    return _encode_mask(mask)


def _encode_mask(mask_array: np.ndarray) -> bytes:
    """Encode a grayscale mask array as PNG bytes."""
    success, encoded = cv2.imencode(".png", mask_array)
    if not success:
        raise RuntimeError("Failed to encode hair mask as PNG")
    return encoded.tobytes()
