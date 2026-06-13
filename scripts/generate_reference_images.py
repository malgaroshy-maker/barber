"""Generate reference images for the haircut catalogue using Cloudflare FLUX.1.

Usage:  python scripts\generate_reference_images.py

Generates 34 JPEG images in static/ (one per haircut) using the free
Cloudflare Workers AI REST API.  Existing images are skipped unless
``--force`` is passed.
"""

import argparse
import asyncio
import base64
import json
import logging
import os
import sys
from pathlib import Path

import httpx

# ── Config (read from .env-style via app.config) ─────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.hair_swap import HAIRCUT_PROMPTS
from app.config import CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN

FLUX_SCHNELL = "@cf/black-forest-labs/flux-1-schnell"
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("gen_ref")


def _build_prompt(haircut_id: str, haircut_name: str) -> str:
    base = HAIRCUT_PROMPTS.get(haircut_id, f"{haircut_id} hairstyle")
    return (
        f"Professional barber photo of a man with {base}. "
        f"Studio lighting, clean neutral background, sharp focus, "
        f"high quality, photorealistic, 8k."
    )


async def generate_one(client: httpx.AsyncClient, haircut_id: str, name_ar: str) -> bool:
    out_path = STATIC_DIR / f"{haircut_id}.jpg"
    if out_path.exists():
        logger.info("SKIP %s — already exists", haircut_id)
        return True

    prompt = _build_prompt(haircut_id, name_ar)
    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/{FLUX_SCHNELL}"

    for attempt in range(3):
        try:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={"prompt": prompt},
                timeout=60,
            )

            if resp.status_code == 200:
                data = resp.json()
                b64 = data.get("result", {}).get("image") or data.get("image")
                if b64:
                    out_path.write_bytes(base64.b64decode(b64))
                    logger.info("OK  %s (%d bytes)", haircut_id, out_path.stat().st_size)
                    return True
                logger.warning("No image in response for %s: %s", haircut_id, json.dumps(data)[:200])
            else:
                logger.warning("Attempt %d for %s: %s %s", attempt + 1, haircut_id, resp.status_code, resp.text[:120])
        except Exception as exc:
            logger.warning("Attempt %d for %s error: %s", attempt + 1, haircut_id, exc)

        await asyncio.sleep(3)

    return False


async def main(force: bool = False) -> None:
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        logger.error("Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN in .env")
        return

    haircuts_path = Path(__file__).resolve().parent.parent / "data" / "haircuts.json"
    haircuts = json.loads(haircuts_path.read_text(encoding="utf-8"))

    if force:
        for h in haircuts:
            p = STATIC_DIR / f"{h['id']}.jpg"
            if p.exists():
                p.unlink()
                logger.info("Removed %s", p.name)

    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    ok = 0
    sem = asyncio.Semaphore(2)  # max 2 concurrent

    async def do_one(h):
        async with sem:
            success = await generate_one(client, h["id"], h["name_ar"])
            nonlocal ok
            if success:
                ok += 1

    async with httpx.AsyncClient(timeout=60) as client:
        tasks = [do_one(h) for h in haircuts if h.get("active", True)]
        await asyncio.gather(*tasks)

    logger.info("Done — %d/%d generated successfully", ok, len(haircuts))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(force=args.force))
