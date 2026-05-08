import json
from pathlib import Path
from typing import Any

import httpx

DATA_DIR = Path(__file__).parent.parent / "data"


def load_haircuts() -> list[dict[str, Any]]:
    with open(DATA_DIR / "haircuts.json", encoding="utf-8") as f:
        return json.load(f)


def load_face_shape_map() -> dict[str, Any]:
    with open(DATA_DIR / "face_shape_map.json", encoding="utf-8") as f:
        return json.load(f)


def get_whatsapp_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url="https://graph.facebook.com",
        headers={"Authorization": f"Bearer {__import__('app.config').WHATSAPP_ACCESS_TOKEN}"},
        timeout=30.0,
    )
