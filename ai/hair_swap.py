import asyncio
import base64
import io
import logging
import re
import urllib.parse
from io import BytesIO
from typing import Optional

import cv2
import httpx
import numpy as np
import replicate
from google import genai
from google.genai import types as genai_types
from PIL import Image as PILImage

from ai.hair_mask import create_hair_mask
from app.config import (
    CLOUDFLARE_ACCOUNT_ID,
    CLOUDFLARE_API_TOKEN,
    FREETHEAI_API_KEY,
    GEMINI_API_KEY,
    HUGGINGFACE_API_TOKEN,
    REPLICATE_API_TOKEN,
)

logger = logging.getLogger(__name__)

FLUX_SCHNELL = "black-forest-labs/flux-schnell"
FLUX_KONTEXT_PRO = "black-forest-labs/flux-kontext-pro"
CLOUDFLARE_INPAINTING_MODEL = "@cf/runwayml/stable-diffusion-v1-5-inpainting"

HAIRCUT_PROMPTS = {
    # Fades
    "fade_classic": "Classic fade haircut with short faded sides and slightly longer top, clean and elegant",
    "fade_drop": "Drop fade haircut with a low fade curving behind the ears, short textured top",
    "fade_mid_skin": "Mid skin fade haircut with very short faded sides ending above the ears",
    "fade_low": "Low fade haircut with a subtle taper just above the ears and neckline",
    "fade_high": "High fade haircut with the fade starting high on the sides",
    "burst_fade": "Burst fade haircut with the fade radiating around the ears",
    # Short / military
    "buzz_cut": "Buzz cut, very short uniform length all over, clean military style haircut",
    "crew_cut": "Crew cut, short tapered haircut with slightly longer hair on top front",
    "french_crop": "French crop with short fringe forward, textured top, faded back and sides",
    "caesar_cut": "Modern Caesar haircut with short horizontal fringe, neat and textured",
    "ivy_league": "Ivy league haircut, short tapered sides with slightly longer top parted to the side",
    # Volume / classic
    "pompadour": "Pompadour hairstyle with voluminous hair swept up and back, short faded sides",
    "quiff": "Quiff hairstyle with medium length hair swept up and back, faded sides and modern look",
    "textured_quiff": "Textured quiff hairstyle with messy volume on top and very short sides",
    "brush_up": "Brush up hairstyle with hair styled upward, textured top and tapered sides",
    "slick_back": "Slicked back hairstyle with hair combed straight back, short sides",
    "side_part": "Classic side part hairstyle with neat comb over and tapered sides",
    "comb_over": "Modern comb over hairstyle with a side part and low fade",
    # Fringe / medium
    "angular_fringe": "Angular fringe hairstyle with textured fringe swept to one side, short sides",
    "messy_fringe": "Messy fringe hairstyle with tousled bangs forward, tapered sides",
    "curtain": "Middle part curtains hairstyle with hair parted in the middle and falling to both sides",
    "wolf_cut": "Wolf cut hairstyle with shaggy layered hair, longer top and textured ends",
    "shag": "Shaggy men's hairstyle with layered messy hair and textured fringe",
    # Edgy / statement
    "undercut": "Disconnected undercut with very short sides and long hair on top",
    "faux_hawk": "Faux hawk hairstyle with short sides and longer hair styled up in the center",
    "modern_mullet": "Modern mullet haircut with short front and sides, longer textured back",
    # Texture / natural
    "textured_crop": "Textured crop hairstyle with short choppy textured top and faded sides",
    "natural_texture": "Natural textured men's hairstyle with messy volume and tapered sides",
    "curly_top": "Curly top hairstyle with defined curls on top and faded sides",
    "tapered_curls": "Tapered curls hairstyle with tight curls on top and gradually faded sides",
    "afro": "Classic rounded afro hairstyle, full natural volume",
    "high_top": "High top fade haircut with flat top and very short faded sides",
    # Long
    "man_bun": "Man bun hairstyle with long hair tied up in a bun on top",
    "bro_flow": "Bro flow hairstyle with medium length hair pushed back and flowing naturally",
}

FREETHEAI_API_URL = "https://api.freetheai.xyz/v1/images"
FREETHEAI_EDIT_RETRIES = 3

GEMINI_IMAGE_MODELS = [
    "gemini-3.1-flash-image-preview",
    "gemini-2.5-flash-image-preview",
]


def _image_to_data_uri(img_bytes: bytes, fmt: str = "jpeg") -> str:
    import base64
    return f"data:image/{fmt};base64,{base64.b64encode(img_bytes).decode()}"


def _extract_retry_delay(exc: Exception) -> int:
    match = re.search(r"retry in (\d+(?:\.\d+)?)s", str(exc))
    if match:
        return max(1, int(float(match.group(1))))
    return 10


async def swap_hair_gemini(selfie_bytes: bytes, haircut_id: str) -> Optional[bytes]:
    if not GEMINI_API_KEY:
        logger.warning("Gemini API key not configured")
        return None

    prompt = HAIRCUT_PROMPTS.get(haircut_id, f"{haircut_id} hairstyle")
    full_prompt = (
        f"Transform this person's hairstyle to: {prompt}. "
        f"Keep the face, facial features, skin tone, expression, clothing, "
        f"body, posture, and background exactly the same. Only change the hair."
    )

    for model_name in GEMINI_IMAGE_MODELS:
        for attempt in range(3):
            try:
                client = genai.Client(api_key=GEMINI_API_KEY)
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        genai_types.Part.from_text(text=full_prompt),
                        genai_types.Part.from_bytes(data=selfie_bytes, mime_type="image/jpeg"),
                    ],
                    config=genai_types.GenerateContentConfig(
                        response_modalities=["TEXT", "IMAGE"],
                    ),
                )

                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.data:
                        logger.info("Gemini %s generated edited image (%d bytes)", model_name, len(part.inline_data.data))
                        return part.inline_data.data

                logger.warning("Gemini %s returned no image in response", model_name)

            except Exception as exc:
                exc_str = str(exc)
                if "429" in exc_str or "RESOURCE_EXHAUSTED" in exc_str:
                    delay = _extract_retry_delay(exc)
                    logger.warning("Gemini %s attempt %d rate limited, retrying in %ds: %s", model_name, attempt + 1, delay, exc)
                    await asyncio.sleep(delay)
                    continue
                logger.warning("Gemini %s attempt %d failed: %s", model_name, attempt + 1, exc)
                break

        logger.info("Gemini %s exhausted attempts, trying next model", model_name)

    return None


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
                if resp.status_code in (429, 503):
                    backoff = (attempt + 1) * 3
                    logger.warning("FreeTheAI attempt %d: %s, retrying in %ds...", attempt + 1, resp.status_code, backoff)
                    await asyncio.sleep(backoff)
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
            FLUX_KONTEXT_PRO,
            input={
                "prompt": f"Give this exact person a {prompt}. Preserve the person's exact face identity, facial structure, skin tone, eye color, expression, age, clothing, body, posture, and background exactly as they are. The ONLY change should be the hairstyle.",
                "image": selfie_uri,
                "num_outputs": 1,
                "output_format": "jpg",
                "output_quality": 90,
                "guidance_scale": 2.0,
                "steps": 50,
            },
        )

        image_url = None
        if isinstance(output, str):
            image_url = output
        elif isinstance(output, list) and len(output) > 0:
            item = output[0]
            image_url = item if isinstance(item, str) else str(item)
        elif hasattr(output, "url"):
            image_url = output.url
        elif hasattr(output, "__iter__") and not isinstance(output, (str, bytes)):
            for item in output:
                image_url = str(item)
                break

        if not image_url:
            logger.warning("Replicate returned unexpected output type: %s = %s", type(output).__name__, str(output)[:200])
            return None

        if image_url:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(image_url)
                if resp.status_code == 200:
                    return resp.content
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


async def swap_hair_cloudflare(selfie_bytes: bytes, haircut_id: str) -> Optional[bytes]:
    """Use Cloudflare Workers AI inpainting (free tier) to change the hairstyle.

    Pads non-square input to square before sending and crops the result
    back afterwards to prevent SD 1.5's 512×512 native resolution from
    stretching the image.
    """
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        logger.warning("Cloudflare credentials not configured")
        return None

    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}"
        f"/ai/run/{CLOUDFLARE_INPAINTING_MODEL}"
    )

    prompt = HAIRCUT_PROMPTS.get(haircut_id, f"{haircut_id} hairstyle")
    full_prompt = (
        f"Portrait photo of a man with {prompt}. "
        f"Only change the hair. Keep the exact same face, eyes, nose, mouth, ears, skin tone, "
        f"facial features, expression, clothing, and background. "
        f"Photorealistic, natural lighting, sharp focus."
    )

    try:
        mask_bytes = create_hair_mask(selfie_bytes)
    except Exception as exc:
        logger.warning("Failed to create hair mask: %s", exc)
        return None

    # ── Aspect-ratio preservation ─────────────────────────────────
    # SD 1.5 inpainting natively operates at 512×512.  We pad the image
    # to a square (centered, with reflective padding) so the model sees
    # a square input, then resize the result back and crop to original.
    pil_img = PILImage.open(io.BytesIO(selfie_bytes))
    orig_w, orig_h = pil_img.size
    square_size = max(orig_w, orig_h)

    if orig_w != orig_h:
        # Center the image in a square canvas with reflective padding
        padded_img = PILImage.new("RGB", (square_size, square_size), (0, 0, 0))
        # Calculate centering offsets
        x_offset = (square_size - orig_w) // 2
        y_offset = (square_size - orig_h) // 2
        padded_img.paste(pil_img, (x_offset, y_offset))
        padded_buf = io.BytesIO()
        padded_img.save(padded_buf, format="JPEG", quality=95)
        send_image_bytes = padded_buf.getvalue()

        # Pad mask correspondingly (centered, black on padded sides = preserve)
        mask_arr = cv2.imdecode(np.frombuffer(mask_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
        padded_mask = np.zeros((square_size, square_size), dtype=np.uint8)
        padded_mask[y_offset:y_offset + orig_h, x_offset:x_offset + orig_w] = mask_arr
        _, mask_encoded = cv2.imencode(".png", padded_mask)
        send_mask_bytes = mask_encoded.tobytes()
    else:
        send_image_bytes = selfie_bytes
        send_mask_bytes = mask_bytes
        x_offset, y_offset = 0, 0

    image_bytes_array = list(send_image_bytes)
    mask_bytes_array = list(send_mask_bytes)

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "prompt": full_prompt,
                        "negative_prompt": (
                            "blurry, distorted face, changed face, different person, ugly, "
                            "deformed, low quality, bad proportions, unnatural skin, bad lighting, "
                            "oversaturated, cartoon, painting, 3d render, illustration, "
                            "hands, fingers, tools, comb, scissors, barber tools"
                        ),
                        "image": image_bytes_array,
                        "mask": mask_bytes_array,
                        "num_steps": 20,
                        "guidance": 6.0,
                    },
                )

            if resp.status_code == 200:
                content_type = resp.headers.get("content-type", "").lower()
                result_bytes: Optional[bytes] = None
                if "application/json" in content_type:
                    data = resp.json()
                    result_image_b64 = data.get("image") or data.get("result", {}).get("image")
                    if result_image_b64:
                        result_bytes = base64.b64decode(result_image_b64)
                elif len(resp.content) > 1000:
                    result_bytes = resp.content

                if result_bytes:
                    if orig_w != orig_h:
                        # Cloudflare returns 512×512 — resize to square first,
                        # then crop to original dimensions
                        result_img = PILImage.open(io.BytesIO(result_bytes))
                        # Resize to the padded square size using high-quality resampling
                        result_img = result_img.resize((square_size, square_size), PILImage.LANCZOS)
                        # Crop the centered region back to original size
                        result_img = result_img.crop((x_offset, y_offset, x_offset + orig_w, y_offset + orig_h))
                        out_buf = io.BytesIO()
                        result_img.save(out_buf, format="JPEG", quality=95)
                        result_bytes = out_buf.getvalue()
                    logger.info("Cloudflare inpainting succeeded (%d bytes)", len(result_bytes))
                    return result_bytes

            logger.warning(
                "Cloudflare attempt %d failed: %s - %s",
                attempt + 1,
                resp.status_code,
                resp.text[:200],
            )
        except Exception as exc:
            logger.warning("Cloudflare attempt %d error: %s", attempt + 1, exc)

    return None


async def run_hair_swap(selfie_bytes: bytes, haircut_id: str) -> Optional[bytes]:
    logger.info("Trying Cloudflare Workers AI inpainting (free tier)")
    result = await swap_hair_cloudflare(selfie_bytes, haircut_id)
    if result:
        # Color matching disabled — histogram matching on entire image
        # was causing washed-out results. SD 1.5 already preserves colors
        # reasonably well with the improved prompt.
        return result

    logger.info("Cloudflare failed, trying Replicate img2img (flux-kontext-pro)")
    result = await swap_hair_replicate(selfie_bytes, haircut_id)
    if result:
        return result

    logger.info("Replicate failed, trying Gemini image editing")
    result = await swap_hair_gemini(selfie_bytes, haircut_id)
    if result:
        return result

    logger.info("Gemini failed, trying FreeTheAI")
    result = await swap_hair_freetheai(selfie_bytes, haircut_id)
    if result:
        return result

    logger.info("FreeTheAI failed, trying Pollinations AI (fallback)")
    result = await generate_image_pollinations(haircut_id)
    if result:
        return result

    logger.info("Pollinations failed, trying HuggingFace")
    return await swap_hair_huggingface(haircut_id)
