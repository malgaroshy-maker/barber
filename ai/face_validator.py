import logging
from io import BytesIO
from pathlib import Path
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from PIL import Image

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent / "face_detector.tflite"

_detector: Optional[vision.FaceDetector] = None


def _get_detector() -> vision.FaceDetector:
    global _detector
    if _detector is None:
        options = vision.FaceDetectorOptions(
            base_options=python.BaseOptions(model_asset_path=str(MODEL_PATH)),
            running_mode=vision.RunningMode.IMAGE,
            min_detection_confidence=0.5,
        )
        _detector = vision.FaceDetector.create_from_options(options)
    return _detector


def validate_selfie(image_bytes: bytes) -> tuple[bool, str]:
    try:
        image = Image.open(BytesIO(image_bytes))
    except Exception:
        return False, "تعذر قراءة الصورة"

    if image.mode != "RGB":
        image = image.convert("RGB")

    img_w, img_h = image.size
    total_area = img_w * img_h

    np_image = np.array(image)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np_image)

    detector = _get_detector()
    result = detector.detect(mp_image)

    if not result or not result.detections:
        return False, "مفيش وش في الصورة يا غالي"

    face_count = len(result.detections)
    if face_count > 1:
        return False, "في ناس تانية في الصورة معاك"

    detection = result.detections[0]
    bbox = detection.bounding_box
    face_area = bbox.width * bbox.height
    face_ratio = face_area / total_area

    if face_ratio < 0.15:
        return False, "وشك صغير أوي في الصورة، خليك أقرب شوية"

    if detection.categories[0].score < 0.7:
        return False, "الصورة مش واضحة كفاية يا باشا"

    return True, "done"

