import base64
import logging
import time
from typing import Optional

import httpx
from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

FACE_ANALYSIS_PROMPT = """
Analyze this photo and determine the person's face shape.
Output ONLY one of: oval, round, square, heart, oblong, diamond.
No explanation, no extra text.
"""


def _detect_face_shape_geometric(image_bytes: bytes) -> str:
    """Fallback face shape analyzer using OpenCV face bounding box and aspect ratio."""
    try:
        from io import BytesIO
        import cv2
        import numpy as np
        from PIL import Image, ImageOps
        from ai.hair_mask import _detect_face_and_landmarks

        pil_img = Image.open(BytesIO(image_bytes))
        pil_img = ImageOps.exif_transpose(pil_img).convert("RGB")
        np_img = np.array(pil_img)
        gray = cv2.cvtColor(np_img, cv2.COLOR_RGB2GRAY)

        res = _detect_face_and_landmarks(np_img, gray)
        if res and "bbox" in res:
            _, _, w, h = res["bbox"]
            if w > 0:
                aspect_ratio = float(h) / float(w)
                if aspect_ratio >= 1.42:
                    return "oblong"
                elif aspect_ratio <= 1.12:
                    return "round"
                elif aspect_ratio >= 1.30:
                    return "oval"
                else:
                    return "square"
    except Exception as exc:
        logger.warning("Geometric face shape detection failed: %s", exc)

    return "oval"


def _analyze_face_shape_sync(image_bytes: bytes) -> Optional[str]:
    """Synchronous face shape analysis — runs Gemini API + geometric fallback."""
    valid_shapes = {"oval", "round", "square", "heart", "oblong", "diamond"}

    if GEMINI_API_KEY:
        last_error = None
        for attempt in range(3):
            try:
                client = genai.Client(api_key=GEMINI_API_KEY)
                response = client.models.generate_content(
                    model="gemini-3-flash-preview",
                    contents=[
                        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                        FACE_ANALYSIS_PROMPT.strip(),
                    ],
                )
                result = response.text.strip().lower().replace(".", "").replace(" ", "")

                if result in valid_shapes:
                    logger.info("Face shape detected via Gemini: %s", result)
                    return result

                logger.warning("Unexpected Gemini output: %s", result)
                break

            except Exception as exc:
                last_error = exc
                logger.warning("Face analysis attempt %d failed: %s", attempt + 1, exc)
                if attempt < 2:
                    time.sleep(2 ** attempt)

        logger.warning("Gemini face analysis unavailable or failed: %s. Using geometric fallback.", last_error)

    # Fallback to local geometric face shape detector
    geom_shape = _detect_face_shape_geometric(image_bytes)
    logger.info("Face shape detected via geometric fallback: %s", geom_shape)
    return geom_shape


async def analyze_face_shape(image_bytes: bytes) -> Optional[str]:
    """Async wrapper — runs blocking Gemini/CV analysis in a thread."""
    import asyncio
    return await asyncio.to_thread(_analyze_face_shape_sync, image_bytes)

