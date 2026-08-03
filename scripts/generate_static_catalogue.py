import asyncio
import base64
import io
import logging
from pathlib import Path
from PIL import Image
import httpx

from ai.hair_swap import HAIRCUT_PROMPTS
from app.config import CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STATIC_DIR = Path("static")
STATIC_DIR.mkdir(exist_ok=True)

PROMPT_TEMPLATE = (
    "Raw photorealistic 35mm studio headshot portrait photograph of a real handsome 28-year-old male model with {prompt}, "
    "clean barbershop studio lighting, sharp focus, authentic skin pores, real human facial features, neutral studio background, "
    "zero 3d render, zero digital painting, zero illustration, professional headshot photo"
)

async def generate_reference_image(haircut_id: str, prompt_text: str) -> bool:
    target_path = STATIC_DIR / f"{haircut_id}.jpg"
    full_prompt = PROMPT_TEMPLATE.format(prompt=prompt_text)
    
    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    body = {
        "prompt": full_prompt,
        "num_steps": 8
    }
    
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, headers=headers, json=body)
            if resp.status_code == 200:
                res_json = resp.json()
                b64 = res_json.get("result", {}).get("image")
                if b64:
                    img_bytes = base64.b64decode(b64)
                    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                    img = img.resize((512, 512), Image.Resampling.LANCZOS)
                    img.save(target_path, "JPEG", quality=95)
                    logger.info("Generated Flux reference: %s (%d bytes)", target_path.name, target_path.stat().st_size)
                    return True
            logger.warning("Flux gen failed for %s: %s %s", haircut_id, resp.status_code, resp.text[:150])
    except Exception as exc:
        logger.warning("Generation error for %s: %s", haircut_id, exc)
    return False

async def main():
    print(f"Generating hyper-realistic Flux reference images for all {len(HAIRCUT_PROMPTS)} haircuts...")
    success_count = 0
    for haircut_id, prompt_desc in HAIRCUT_PROMPTS.items():
        print(f"Generating {haircut_id}...", end="", flush=True)
        ok = await generate_reference_image(haircut_id, prompt_desc)
        if ok:
            success_count += 1
            print(" OK")
        else:
            print(" FAILED")
    print(f"\nDone! Generated {success_count}/{len(HAIRCUT_PROMPTS)} static reference images.")

if __name__ == "__main__":
    asyncio.run(main())
