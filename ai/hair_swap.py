import base64
import logging
from io import BytesIO
from typing import Optional

import httpx
import replicate
from PIL import Image

from app.config import REPLICATE_API_TOKEN, HUGGINGFACE_API_TOKEN

logger = logging.getLogger(__name__)

FLUX_SCHNELL = "black-forest-labs/flux-schnell"

HAIRCUT_PROMPTS = {
    "fade_classic": "classic fade haircut, short sides, longer top, clean taper, barber style",
    "fade_drop": "drop fade haircut, low fade curving behind ears, short textured top",
    "pompadour": "pompadour hairstyle, voluminous hair swept up and back, short faded sides",
    "buzz_cut": "buzz cut, very short uniform length all over, clean military style",
    "quiff": "quiff hairstyle, medium length hair swept up and back, faded sides",
    "crew_cut": "crew cut, short tapered haircut, slightly longer hair on top front",
    "french_crop": "french crop, short fringe forward, textured top, faded back and sides",
}


def _image_to_data_uri(img_bytes: bytes, fmt: str = "jpeg") -> str:
    return f"data:image/{fmt};base64,{base64.b64encode(img_bytes).decode()}"


async def swap_hair_replicate(selfie_bytes: bytes, haircut_id: str) -> Optional[bytes]:
    try:
        prompt = HAIRCUT_PROMPTS.get(haircut_id, f"{haircut_id} hairstyle, barber haircut")
        selfie_uri = _image_to_data_uri(selfie_bytes)

        output = replicate.run(
            FLUX_SCHNELL,
            input={
                "prompt": f"portrait photo of a man with {prompt}, realistic, high quality",
                "image": selfie_uri,
                "num_outputs": 1,
                "guidance_scale": 3.5,
                "output_quality": 85,
                "prompt_strength": 0.7,
            },
        )

        if output and isinstance(output, list) and len(output) > 0:
            image_url = output[0]
            async with httpx.AsyncClient() as client:
                resp = await client.get(image_url, timeout=30)
                if resp.status_code == 200:
                    return resp.content

        logger.error("Replicate output unexpected: %s", output)
        return None

    except Exception as exc:
        logger.warning("Replicate hair swap failed: %s", exc)
        return None


async def swap_hair_huggingface(selfie_bytes: bytes, haircut_id: str) -> Optional[bytes]:
    if not HUGGINGFACE_API_TOKEN or HUGGINGFACE_API_TOKEN == "your_hf_token":
        logger.warning("HuggingFace token not configured")
        return None

    try:
        selfie_b64 = base64.b64encode(selfie_bytes).decode()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell",
                headers={"Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}"},
                json={"inputs": selfie_b64},
                timeout=60,
            )
            if resp.status_code == 200:
                return resp.content
            logger.error("HuggingFace error: %s", resp.text[:200])
            return None
    except Exception as exc:
        logger.warning("HuggingFace fallback failed: %s", exc)
        return None


async def run_hair_swap(selfie_bytes: bytes, haircut_id: str, ref_image_url: str = "") -> Optional[bytes]:
    result = await swap_hair_replicate(selfie_bytes, haircut_id)
    if result:
        return result
    logger.info("Replicate failed, trying HuggingFace fallback")
    return await swap_hair_huggingface(selfie_bytes, haircut_id)
