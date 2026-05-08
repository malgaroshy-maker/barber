import base64
import logging
from typing import Optional

import httpx
import replicate

from app.config import REPLICATE_API_TOKEN, HUGGINGFACE_API_TOKEN

logger = logging.getLogger(__name__)

FLUX_SCHNELL = "black-forest-labs/flux-schnell"

HAIRCUT_PROMPTS = {
    "fade_classic": "classic fade haircut, short sides, longer top, clean taper",
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
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(image_url)
                if resp.status_code == 200:
                    return resp.content

        logger.error("Replicate output unexpected: %s", output)
        return None

    except Exception as exc:
        logger.warning("Replicate failed: %s", exc)
        return None


async def swap_hair_huggingface(haircut_id: str) -> Optional[bytes]:
    if not HUGGINGFACE_API_TOKEN or HUGGINGFACE_API_TOKEN == "your_hf_token":
        return None

    prompt = HAIRCUT_PROMPTS.get(haircut_id, f"{haircut_id} hairstyle")
    full_prompt = f"portrait photo of a man with {prompt}, realistic, high quality, professional photography"

    models_to_try = [
        "stabilityai/stable-diffusion-2-1",
        "runwayml/stable-diffusion-v1-5",
    ]

    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}"}

    for model in models_to_try:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"https://api-inference.huggingface.co/models/{model}",
                    headers=headers,
                    json={"inputs": full_prompt},
                )
                if resp.status_code == 200 and resp.content:
                    logger.info("HuggingFace model %s succeeded", model)
                    return resp.content
                logger.warning("HuggingFace model %s returned %s", model, resp.status_code)
        except Exception as exc:
            logger.warning("HuggingFace model %s failed: %s", model, exc)

    logger.error("All HuggingFace models failed")
    return None


async def run_hair_swap(selfie_bytes: bytes, haircut_id: str) -> Optional[bytes]:
    result = await swap_hair_replicate(selfie_bytes, haircut_id)
    if result:
        return result
    logger.info("Replicate failed, trying HuggingFace fallback")
    return await swap_hair_huggingface(haircut_id)
