import base64
import logging
from io import BytesIO
from typing import Optional

import replicate
import httpx

from app.config import REPLICATE_API_TOKEN, HUGGINGFACE_API_TOKEN

logger = logging.getLogger(__name__)

FLUX_SCHNELL = "black-forest-labs/flux-schnell"


async def swap_hair_replicate(selfie_bytes: bytes, ref_image_url: str) -> Optional[bytes]:
    try:
        selfie_b64 = base64.b64encode(selfie_bytes).decode()
        data_uri = f"data:image/jpeg;base64,{selfie_b64}"

        output = replicate.run(
            FLUX_SCHNELL,
            input={
                "prompt": f"hairstyle try-on: apply the hairstyle from the reference to this person, realistic portrait",
                "image": data_uri,
                "num_outputs": 1,
                "guidance_scale": 3.5,
                "output_quality": 80,
            },
        )

        if output and isinstance(output, list) and len(output) > 0:
            image_url = output[0]
            async with httpx.AsyncClient() as client:
                resp = await client.get(image_url, timeout=30)
                if resp.status_code == 200:
                    return resp.content

        logger.error("Replicate returned unexpected output: %s", output)
        return None

    except Exception as exc:
        logger.exception("Replicate hair swap failed: %s", exc)
        return None


async def swap_hair_huggingface(selfie_bytes: bytes, ref_image_url: str) -> Optional[bytes]:
    if not HUGGINGFACE_API_TOKEN or HUGGINGFACE_API_TOKEN == "your_hf_token":
        logger.warning("HuggingFace token not configured")
        return None

    try:
        selfie_b64 = base64.b64encode(selfie_bytes).decode()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell",
                headers={"Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}"},
                json={"inputs": selfie_b64, "parameters": {"guidance_scale": 3.5}},
                timeout=60,
            )
            if resp.status_code == 200:
                return resp.content

            logger.error("HuggingFace error: %s", resp.text)
            return None

    except Exception as exc:
        logger.exception("HuggingFace hair swap failed: %s", exc)
        return None


async def run_hair_swap(selfie_bytes: bytes, ref_image_url: str) -> Optional[bytes]:
    result = await swap_hair_replicate(selfie_bytes, ref_image_url)
    if result:
        return result
    logger.info("Replicate failed, trying HuggingFace fallback")
    return await swap_hair_huggingface(selfie_bytes, ref_image_url)
