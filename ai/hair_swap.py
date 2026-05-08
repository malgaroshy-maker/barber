import asyncio
import logging
import urllib.parse
from typing import Optional

import httpx
import replicate

from app.config import FREETHEAI_API_KEY, HUGGINGFACE_API_TOKEN, REPLICATE_API_TOKEN

logger = logging.getLogger(__name__)

FLUX_SCHNELL = "black-forest-labs/flux-schnell"

HAIRCUT_PROMPTS = {
    "fade_classic": "Classic fade haircut with short faded sides and slightly longer top, clean and elegant",
    "fade_drop": "Drop fade haircut with a low fade curving behind the ears, short textured top",
    "pompadour": "Pompadour hairstyle with voluminous hair swept up and back, short faded sides",
    "buzz_cut": "Buzz cut, very short uniform length all over, clean military style haircut",
    "quiff": "Quiff hairstyle with medium length hair swept up and back, faded sides and modern look",
    "crew_cut": "Crew cut, short tapered haircut with slightly longer hair on top front",
    "french_crop": "French crop with short fringe forward, textured top, faded back and sides",
}

FREETHEAI_API_URL = "https://api.freetheai.xyz/v1/images"
FREETHEAI_EDIT_RETRIES = 3


def _image_to_data_uri(img_bytes: bytes, fmt: str = "jpeg") -> str:
    import base64
    return f"data:image/{fmt};base64,{base64.b64encode(img_bytes).decode()}"


async def swap_hair_freetheai(selfie_bytes: bytes, haircut_id: str) -> Optional[bytes]:
    if not FREETHEAI_API_KEY:
        logger.warning("FreeTheAI API key not configured")
        return None

    prompt = HAIRCUT_PROMPTS.get(haircut_id, f"{haircut_id} hairstyle, barber haircut")
    full_prompt = f"Change the hairstyle of this person to: {prompt}. Keep the face, expression, and clothing exactly the same. Realistic portrait."

    for attempt in range(FREETHEAI_EDIT_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{FREETHEAI_API_URL}/edits",
                    headers={
                        "Authorization": f"Bearer {FREETHEAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "img/gpt-image-2",
                        "prompt": full_prompt,
                        "image": _image_to_data_uri(selfie_bytes),
                    },
                )
                if resp.status_code == 503:
                    logger.warning("FreeTheAI attempt %d: provider unavailable, retrying...", attempt + 1)
                    await asyncio.sleep(3)
                    continue

                if resp.status_code != 200:
                    logger.warning("FreeTheAI attempt %d returned %s: %s", attempt + 1, resp.status_code, resp.text[:200])
                    return None

                data = resp.json()
                image_url = data.get("data", [{}])[0].get("url")
                if not image_url:
                    b64_json = data.get("data", [{}])[0].get("b64_json")
                    if b64_json:
                        import base64
                        return base64.b64decode(b64_json)
                    return None

                img_resp = await client.get(image_url)
                if img_resp.status_code == 200 and len(img_resp.content) > 1000:
                    logger.info("FreeTheAI edited image (%d bytes)", len(img_resp.content))
                    return img_resp.content
                return None
        except Exception as exc:
            logger.warning("FreeTheAI attempt %d failed: %s", attempt + 1, exc)
            if attempt < FREETHEAI_EDIT_RETRIES - 1:
                await asyncio.sleep(3)

    return None


async def swap_hair_replicate(selfie_bytes: bytes, haircut_id: str) -> Optional[bytes]:
    try:
        prompt = HAIRCUT_PROMPTS.get(haircut_id, f"{haircut_id} hairstyle")
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
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(str(output[0]))
                if resp.status_code == 200:
                    return resp.content
        return None
    except Exception as exc:
        logger.warning("Replicate failed: %s", exc)
        return None


async def generate_image_pollinations(haircut_id: str) -> Optional[bytes]:
    prompt = HAIRCUT_PROMPTS.get(haircut_id, f"{haircut_id} hairstyle, barber haircut")
    full_prompt = f"Professional portrait photo of a man with {prompt}, realistic, high quality, studio lighting, detailed facial features, photorealistic"

    url = (
        f"https://image.pollinations.ai/prompt/{urllib.parse.quote(full_prompt)}"
        f"?model=flux&width=1024&height=1024"
    )

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, follow_redirects=True)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    logger.info("Pollinations AI generated image (%d bytes)", len(resp.content))
                    return resp.content
                logger.warning("Pollinations AI attempt %d: %s (%d bytes)", attempt + 1, resp.status_code, len(resp.content))
        except Exception as exc:
            logger.warning("Pollinations AI attempt %d failed: %s", attempt + 1, exc)

        if attempt < 2:
            await asyncio.sleep(2)

    return None


async def swap_hair_huggingface(haircut_id: str) -> Optional[bytes]:
    if not HUGGINGFACE_API_TOKEN or HUGGINGFACE_API_TOKEN == "your_hf_token":
        return None

    prompt = HAIRCUT_PROMPTS.get(haircut_id, f"{haircut_id} hairstyle")
    full_prompt = f"portrait photo of a man with {prompt}, realistic, high quality"
    models_to_try = ["black-forest-labs/FLUX.1-dev", "stabilityai/stable-diffusion-3.5-medium"]

    for model in models_to_try:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"https://api-inference.huggingface.co/models/{model}",
                    headers={"Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}"},
                    json={"inputs": full_prompt},
                )
                if resp.status_code == 200 and resp.content:
                    logger.info("HuggingFace %s generated image (%d bytes)", model, len(resp.content))
                    return resp.content
        except Exception:
            pass

    return None


async def run_hair_swap(selfie_bytes: bytes, haircut_id: str) -> Optional[bytes]:
    result = await swap_hair_replicate(selfie_bytes, haircut_id)
    if result:
        return result

    logger.info("Trying FreeTheAI img2img (free, no credit card)")
    result = await swap_hair_freetheai(selfie_bytes, haircut_id)
    if result:
        return result

    logger.info("FreeTheAI failed, trying Pollinations AI")
    result = await generate_image_pollinations(haircut_id)
    if result:
        return result

    logger.info("Pollinations failed, trying HuggingFace")
    return await swap_hair_huggingface(haircut_id)
