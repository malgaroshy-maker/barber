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
    "fade_classic": "Classic fade haircut, natural medium length hair neatly parted on top, clean side fade, realistic head proportions",
    "fade_drop": "Drop fade haircut, low fade curving behind ears, short textured top",
    "fade_mid_skin": "Mid skin fade haircut, neat short textured top, smooth clean skin fade on sides",
    "fade_low": "Low fade haircut, subtle taper just above ears and neckline",
    "fade_high": "High fade haircut, fade starting high on sides with short top",
    "burst_fade": "Burst fade haircut, circular fade radiating around ears, textured top",
    # Short / military
    "buzz_cut": "Buzz cut hairstyle, short textured dark hair fade on top, clean short hair trim, neat hairline, dark short hair density, stylish barber buzz cut",
    "crew_cut": "Crew cut, short tapered haircut with slightly longer hair on top front",
    "french_crop": "French crop haircut, natural short forward textured hair fringe across upper forehead, natural head volume, clean tapered sides",
    "caesar_cut": "Modern Caesar haircut, short straight horizontal fringe, short textured top",
    "ivy_league": "Ivy league haircut, short side-parted comb-over with clean tapered sides",
    # Volume / classic
    "pompadour": "Classic pompadour haircut, moderate swept-back front hair volume, clean tapered sides, natural hairline",
    "quiff": "Quiff hairstyle, medium length hair brushed up and forward at the front, faded sides",
    "textured_quiff": "Textured quiff hairstyle, messy voluminous hair on top, short faded sides",
    "brush_up": "Brush up hairstyle, hair styled straight upward with texture, tapered sides",
    "slick_back": "Slicked back hairstyle, hair combed straight back with pomade, short sides",
    "side_part": "Classic side part haircut, distinct side hair part line, neat comb-over",
    "comb_over": "Modern comb over hairstyle with hard side part and low skin fade",
    # Fringe / medium
    "angular_fringe": "Angular fringe hairstyle, textured bangs swept diagonally to one side, faded sides",
    "messy_fringe": "Messy fringe hairstyle, casual forward bangs falling near forehead, tapered sides",
    "curtain": "Middle part 90s curtain haircut, natural hair parted down the center falling gracefully to both sides",
    "wolf_cut": "Wolf cut hairstyle, shaggy layered textured hair with volume on top and choppy layers",
    "shag": "Shaggy men's hairstyle, layered messy textured hair with natural fringe",
    # Edgy / statement
    "undercut": "Disconnected undercut hairstyle, shaved short sides with long hair styled on top",
    "faux_hawk": "Faux hawk hairstyle, short sides with central strip of hair styled upward",
    "modern_mullet": "Modern mullet haircut, short textured hair on front and sides with long hair flowing down the back of neck",
    # Texture / natural
    "curly_top": "Natural defined tight curly hair on top, voluminous bouncy curls, short faded sides",
    "tapered_curls": "Tapered curly hairstyle, tight natural curls on top with gradually faded sides",
    "afro": "Full rounded afro hairstyle, dense natural kinky hair volume around head",
    "high_top": "High top fade haircut, flat top box haircut with high skin fade on sides",
    # Long
    "man_bun": "Man bun hairstyle, hair gathered into a neat top knot bun, short tapered sides",
    "bro_flow": "Bro flow hairstyle, medium length wavy hair flowing naturally backward behind ears",
    "natural_texture": "Natural textured haircut, soft parted medium length dark hair with subtle taper",
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


def detect_hair_color(image_bytes: bytes) -> str:
    """Analyze face/eyebrow/hair region to detect natural hair color."""
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return "natural hair color matching subject's beard and eyebrows"
        
        h, w = img.shape[:2]
        # Sample upper face / eyebrow / hair region
        sample_y1 = int(h * 0.15)
        sample_y2 = int(h * 0.45)
        sample_x1 = int(w * 0.25)
        sample_x2 = int(w * 0.75)
        crop = img[sample_y1:sample_y2, sample_x1:sample_x2]
        
        if crop.size == 0:
            return "natural hair color matching subject's beard and eyebrows"
        
        # Convert BGR to HSV
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        v_channel = hsv[:, :, 2]
        dark_mask = v_channel < 140
        
        if not np.any(dark_mask):
            return "natural dark hair color matching subject's beard and eyebrows"
        
        mean_v = float(np.mean(v_channel[dark_mask]))
        s_channel = hsv[:, :, 1]
        mean_s = float(np.mean(s_channel[dark_mask]))
        h_channel = hsv[:, :, 0]
        mean_h = float(np.mean(h_channel[dark_mask]))
        
        if mean_v < 45:
            return "natural jet black hair color matching subject's eyebrows"
        elif mean_v < 90:
            return "natural rich dark brown hair color matching subject's eyebrows and beard"
        elif mean_h < 25 and mean_s > 40:
            return "natural warm chestnut brown hair color matching subject's eyebrows"
        elif mean_v > 120 and mean_s < 50:
            return "natural light brown hair color matching subject's eyebrows"
        else:
            return "natural dark brown hair color matching subject's beard and eyebrows"
    except Exception as exc:
        logger.warning("Hair color detection error: %s", exc)
        return "natural hair color matching subject's beard and eyebrows"


async def swap_hair_cloudflare(selfie_bytes: bytes, haircut_id: str) -> Optional[bytes]:
    """Inpaint haircut onto selfie using Cloudflare Workers AI SD 1.5 Inpainting."""
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        logger.warning("Cloudflare credentials missing; skipping Workers AI inpainting")
        return None

    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/"
        f"ai/run/{CLOUDFLARE_INPAINTING_MODEL}"
    )

    haircut_prompt = HAIRCUT_PROMPTS.get(haircut_id, f"{haircut_id} haircut")
    hair_color_desc = detect_hair_color(selfie_bytes)
    full_prompt = (
        f"{haircut_prompt}, {hair_color_desc}, highly detailed photorealistic barber headshot, "
        f"perfect natural lighting, seamless skin tone match"
    )

    try:
        mask_bytes = create_hair_mask(selfie_bytes, haircut_id=haircut_id)
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
                            "hands, fingers, tools, comb, scissors, barber tools, "
                            "rings, loops, circles, wire, metallic, keychains, unnatural artifacts, "
                            "floating objects, background lines, wall seams, ceiling seams, distorted hairline, accessories, "
                            "bald, shaved head, hairless scalp, smooth egg head, elongated head, shiny scalp, "
                            "hair strands over eyes, hair falling on face, loose strands over cheeks, stray hairs over eyes, "
                            "earring, earrings, ear stud, ear piercing, ear jewelry, hoop earring, silver earring, gold earring, ear metal, "
                            "headset, headphones, earphones, ear defender, head strap, ear clips, black band around ear, "
                            "big head, tall head, deformed skull, squished head, flat head, bowl cut, "
                            "dyed hair, wrong hair color, changed hair color, unnatural hair dye, mismatched eyebrow color, bleach blonde hair"
                        ),
                        "image": image_bytes_array,
                        "mask": mask_bytes_array,
                        "num_steps": 20,
                        "guidance": 7.0,
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

    logger.warning("All face-preserving inpainting providers failed; falling back to reference image")
    return None
