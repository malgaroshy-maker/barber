import logging
from io import BytesIO

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


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
    gray = cv2.cvtColor(np_image, cv2.COLOR_RGB2GRAY)

    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

    if len(faces) == 0:
        return False, "مفيش وش في الصورة يا غالي"

    if len(faces) > 1:
        return False, "في ناس تانية في الصورة معاك"

    x, y, w, h = faces[0]
    face_area = w * h
    face_ratio = face_area / total_area

    if face_ratio < 0.15:
        return False, "وشك صغير أوي في الصورة، خليك أقرب شوية"

    return True, "done"
