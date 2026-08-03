import asyncio
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

# Detailed photorealistic base prompt for static reference gallery photos
PROMPT_TEMPLATE = (
    "8k photorealistic close-up studio headshot portrait photo of a handsome man with {prompt}, "
    "clean barbershop lighting, sharp focus, neutral studio background, 35mm portrait lens, professional barber model photography"
)

async def generate_reference_image(haircut_id: str, prompt_text: str) -> bool:
    target_path = STATIC_DIR / f"{haircut_id}.jpg"
    full_prompt = PROMPT_TEMPLATE.format(prompt=prompt_text)
    
    # We use Cloudflare Workers AI text-to-image or flux model if available
    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/bytedance/stable-diffusion-xl-lightning"
    
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    body = {
        "prompt": full_prompt,
        "num_steps": 8
    }
    
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(url, headers=headers, json=body)
            if resp.status_code == 200 and resp.content:
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                img = img.resize((512, 512), Image.Resampling.LANCZOS)
                img.save(target_path, "JPEG", quality=90)
                logger.info("Successfully generated static reference: %s (%d bytes)", target_path.name, len(resp.content))
                return True
            else:
                logger.warning("Cloudflare gen failed for %s: %s %s", haircut_id, resp.status_code, resp.text[:150])
    except Exception as exc:
        logger.warning("Generation error for %s: %s", haircut_id, exc)
    return False

async def main():
    print(f"Generating realistic reference images for all {len(HAIRCUT_PROMPTS)} haircuts...")
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
