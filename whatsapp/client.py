import logging
from typing import Optional

import httpx

from app.config import WHATSAPP_API_URL, WHATSAPP_ACCESS_TOKEN

logger = logging.getLogger(__name__)


async def send_text(to: str, text: str) -> dict:
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    return await _send(payload)


async def send_image(to: str, image_url: str, caption: str = "") -> dict:
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "image",
        "image": {"link": image_url, "caption": caption},
    }
    return await _send(payload)


async def upload_media_and_send_image(to: str, image_bytes: bytes, caption: str = "") -> dict:
    from app.config import WHATSAPP_PHONE_NUMBER_ID

    async with httpx.AsyncClient() as client:
        upload_resp = await client.post(
            f"https://graph.facebook.com/v23.0/{WHATSAPP_PHONE_NUMBER_ID}/media",
            headers={"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"},
            files={"file": ("image.jpg", image_bytes, "image/jpeg")},
            data={"messaging_product": "whatsapp", "type": "image/jpeg"},
        )
        if upload_resp.status_code != 200:
            logger.error("Media upload error: %s", upload_resp.text)
            return {}

        media_id = upload_resp.json().get("id")
        if not media_id:
            return {}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "image",
            "image": {"id": media_id, "caption": caption},
        }
        return await _send(payload)


async def send_interactive_list(to: str, header: str, body: str, button_text: str, sections: list[dict]) -> dict:
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": header},
            "body": {"text": body},
            "action": {
                "button": button_text,
                "sections": sections,
            },
        },
    }
    return await _send(payload)


async def send_interactive_buttons(to: str, body: str, buttons: list[dict]) -> dict:
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {"buttons": buttons},
        },
    }
    return await _send(payload)


async def download_media(media_id: str) -> Optional[bytes]:
    async with httpx.AsyncClient() as client:
        url_resp = await client.get(
            f"https://graph.facebook.com/v23.0/{media_id}",
            headers={"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"},
        )
        if url_resp.status_code != 200:
            logger.error("Failed to get media URL: %s", url_resp.text)
            return None
        media_url = url_resp.json().get("url")
        if not media_url:
            return None
        data_resp = await client.get(
            media_url,
            headers={"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"},
        )
        if data_resp.status_code != 200:
            logger.error("Failed to download media: %s", data_resp.text)
            return None
        return data_resp.content


async def _send(payload: dict) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            WHATSAPP_API_URL,
            headers={
                "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if resp.status_code != 200:
            logger.error("WhatsApp API error: %s", resp.text)
        return resp.json()
