import base64
import logging
from typing import Optional

import httpx

from app.config import OPENWA_API_URL, OPENWA_API_KEY, OPENWA_SESSION_ID

logger = logging.getLogger(__name__)


async def send_text(to: str, text: str) -> dict:
    chat_id = _to_chat_id(to)
    payload = {
        "chatId": chat_id,
        "text": text,
    }
    return await _post(f"/sessions/{OPENWA_SESSION_ID}/messages/send-text", payload)


async def send_image(to: str, image_url: str, caption: str = "") -> dict:
    chat_id = _to_chat_id(to)
    payload = {
        "chatId": chat_id,
        "image": {"url": image_url},
        "caption": caption,
    }
    return await _post(f"/sessions/{OPENWA_SESSION_ID}/messages/send-image", payload)


async def send_image_base64(to: str, image_bytes: bytes, caption: str = "") -> dict:
    chat_id = _to_chat_id(to)
    b64 = base64.b64encode(image_bytes).decode()
    mimetype = _detect_mimetype(image_bytes)
    payload = {
        "chatId": chat_id,
        "image": {"base64": f"data:{mimetype};base64,{b64}"},
        "caption": caption,
    }
    return await _post(f"/sessions/{OPENWA_SESSION_ID}/messages/send-image", payload)


async def upload_media_and_send_image(to: str, image_bytes: bytes, caption: str = "") -> dict:
    return await send_image_base64(to, image_bytes, caption)


async def send_interactive_list(to: str, header: str, body: str, button_text: str, sections: list[dict]) -> dict:
    rows = []
    for section in sections:
        for row in section.get("rows", []):
            rows.append({
                "id": row.get("id", ""),
                "title": row.get("title", ""),
                "description": row.get("description", ""),
            })
    buttons = [{"id": r["id"], "text": r["title"]} for r in rows if r.get("id")]
    return await send_interactive_buttons(to, body, buttons)


async def send_interactive_buttons(to: str, body: str, buttons: list[dict]) -> dict:
    chat_id = _to_chat_id(to)
    openwa_buttons = []
    for btn in buttons:
        btn_id = btn.get("id", "")
        btn_text = btn.get("text", btn.get("title", ""))
        openwa_buttons.append({"id": btn_id, "text": btn_text})

    if not openwa_buttons:
        return await send_text(to, body)

    payload = {
        "chatId": chat_id,
        "text": body,
        "options": {"buttons": openwa_buttons},
    }
    return await _post(f"/sessions/{OPENWA_SESSION_ID}/messages/send-text", payload)


async def download_media(media_id: str) -> Optional[bytes]:
    if not OPENWA_API_URL:
        return None
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{OPENWA_API_URL}/api/media/{media_id}",
            headers={"X-API-Key": OPENWA_API_KEY},
        )
        if resp.status_code == 200:
            return resp.content
        logger.warning("Failed to download media from OpenWA: %s", resp.text)
        return None


async def _post(path: str, payload: dict) -> dict:
    if not OPENWA_API_URL:
        logger.error("OPENWA_API_URL not configured")
        return {}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{OPENWA_API_URL}/api{path}",
            headers={
                "X-API-Key": OPENWA_API_KEY,
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if resp.status_code != 200:
            logger.error("OpenWA API error (%s): %s", resp.status_code, resp.text)
            return {}
        return resp.json()


def _to_chat_id(phone: str) -> str:
    phone = phone.strip().replace("+", "")
    if not phone.endswith("@c.us"):
        phone = f"{phone}@c.us"
    return phone


def _detect_mimetype(data: bytes) -> str:
    if data[:4] == b"\x89PNG":
        return "image/png"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"
