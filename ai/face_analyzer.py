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


def analyze_face_shape(image_bytes: bytes) -> Optional[str]:
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

            valid_shapes = {"oval", "round", "square", "heart", "oblong", "diamond"}
            if result in valid_shapes:
                logger.info("Face shape detected: %s", result)
                return result

            logger.warning("Unexpected Gemini output: %s", result)
            return None

        except Exception as exc:
            last_error = exc
            logger.warning("Face analysis attempt %d failed: %s", attempt + 1, exc)
            if attempt < 2:
                time.sleep(2 ** attempt)

    logger.error("Face analysis failed after 3 retries: %s", last_error)
    return None
