import logging
from typing import Optional

import httpx
import replicate
from google import genai

from app.config import GEMINI_API_KEY, REPLICATE_API_TOKEN, HUGGINGFACE_API_TOKEN

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

GEMINI_IMAGE_MODELS = [
    "gemini-2.5-flash-image",
    "gemini-3.1-flash-image-preview",
]


def _image_to_data_uri(img_bytes: bytes, fmt: str = "jpeg") -> str:
    import base64
    return f"data:image/{fmt};base64,{base64.b64encode(img_bytes).decode()}"


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


async def generate_image_gemini(haircut_id: str) -> Optional[bytes]:
    if not GEMINI_API_KEY:
        return None

    prompt = HAIRCUT_PROMPTS.get(haircut_id, f"{haircut_id} hairstyle, barber haircut")
    full_prompt = f"Professional portrait photo of a man with {prompt}, realistic, high quality, studio lighting, detailed facial features"

    for model_name in GEMINI_IMAGE_MODELS:
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            response = client.models.generate_content(
                model=model_name,
                contents=full_prompt,
                config={"response_modalities": ["IMAGE"]},
            )
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    logger.info("Gemini %s generated image successfully", model_name)
                    return part.inline_data.data
        except Exception as exc:
            logger.warning("Gemini %s failed: %s", model_name, exc)

    return None


async def swap_hair_huggingface(haircut_id: str) -> Optional[bytes]:
    if not HUGGINGFACE_API_TOKEN or HUGGINGFACE_API_TOKEN == "your_hf_token":
        return None

    prompt = HAIRCUT_PROMPTS.get(haircut_id, f"{haircut_id} hairstyle")
    full_prompt = f"portrait photo of a man with {prompt}, realistic, high quality"
    models_to_try = ["stabilityai/stable-diffusion-2-1", "runwayml/stable-diffusion-v1-5"]

    for model in models_to_try:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"https://api-inference.huggingface.co/models/{model}",
                    headers={"Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}"},
                    json={"inputs": full_prompt},
                )
                if resp.status_code == 200 and resp.content:
                    return resp.content
        except Exception:
            pass

    return None


async def run_hair_swap(selfie_bytes: bytes, haircut_id: str) -> Optional[bytes]:
    result = await swap_hair_replicate(selfie_bytes, haircut_id)
    if result:
        return result
    logger.info("Replicate failed, trying Gemini image generation")
    result = await generate_image_gemini(haircut_id)
    if result:
        return result
    logger.info("Gemini failed, trying HuggingFace")
    return await swap_hair_huggingface(haircut_id)
