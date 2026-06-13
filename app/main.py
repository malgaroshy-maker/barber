import hashlib
import hmac
import json
import logging
from pathlib import Path

from fastapi import FastAPI, Header, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import WHATSAPP_VERIFY_TOKEN, USE_OPENWA, OPENWA_WEBHOOK_SECRET
from conversation.handlers import handle_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Barber WhatsApp Bot", version="0.1.0")

static_dir = Path(__file__).parent.parent / "static"
if not static_dir.exists():
    static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "ai-barber-whatsapp-bot"}


@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
):
    if hub_mode == "subscribe" and hub_verify_token == WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return Response(content=hub_challenge, media_type="text/plain")
    logger.warning("Webhook verification failed")
    return Response(content="Verification failed", status_code=403)


@app.post("/webhook")
async def receive_message(
    request: Request,
    x_hub_signature_256: str = Header(default="", alias="X-Hub-Signature-256"),
    x_openwa_signature: str = Header(default="", alias="X-OpenWA-Signature"),
):
    raw = await request.body()
    body = json.loads(raw) if raw else {}
    logger.info("Incoming webhook: %s", body)

    if USE_OPENWA:
        return await _handle_openwa_webhook(body, raw, x_hub_signature_256, x_openwa_signature)

    try:
        entries = body.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                for message in messages:
                    phone = message.get("from", "")
                    msg_type = message.get("type", "")
                    await handle_message(phone, msg_type, message)
    except Exception:
        logger.exception("Failed to parse webhook payload")

    return Response(content="OK", status_code=200)


def _verify_openwa_signature(raw_body: bytes, signature_header: str) -> bool:
    """Return True if signature matches the HMAC-SHA256 of raw_body.

    Accepts both ``sha256=...`` (GitHub style) and bare-hex signatures.  If
    OPENWA_WEBHOOK_SECRET is empty, verification is skipped.
    """
    if not OPENWA_WEBHOOK_SECRET:
        return True
    if not signature_header:
        return False
    expected = hmac.new(
        OPENWA_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    received = signature_header.split("=", 1)[-1].strip()
    return hmac.compare_digest(expected, received)


async def _handle_openwa_webhook(
    body: dict,
    raw_body: bytes,
    hub_sig: str,
    openwa_sig: str,
) -> Response:
    # Accept either header that OpenWA may use.
    signature_header = hub_sig or openwa_sig
    if not _verify_openwa_signature(raw_body, signature_header):
        logger.warning("Invalid OpenWA webhook signature")
        return Response(content="Invalid signature", status_code=401)

    try:
        event = body.get("event", "")
        data = body.get("data", {})
        # OpenWA ships ``data`` as a JSON-stringified dict; parse if needed.
        if isinstance(data, str):
            try:
                data = json.loads(data) if data else {}
            except json.JSONDecodeError:
                data = {}
        session_id = body.get("sessionId", "")

        if event == "message.received":
            from_id = data.get("from", "") if isinstance(data, dict) else ""
            chat_id = data.get("chatId") or from_id
            # Strip ONLY phone-number suffixes to build the session key;
            # leave @lid, @c.us, @g.us, @broadcast intact so the reply
            # chatId matches exactly what OpenWA delivered.
            phone = chat_id
            for suffix in ("@c.us", "@g.us", "@broadcast", "@s.whatsapp.net"):
                if phone.endswith(suffix):
                    phone = phone[: -len(suffix)]
                    break
            # If the chatId was a @lid (linked id), keep the @lid suffix on
            # the session key so consecutive messages from the same sender
            # land in the same UserSession. The downstream wa.send_text
            # accepts the full chatId (with @lid or @c.us).
            if "@" in chat_id and not any(chat_id.endswith(s) for s in ("@lid", "@c.us", "@g.us", "@broadcast")):
                phone = chat_id
            elif chat_id.endswith("@lid"):
                phone = chat_id  # keep @lid

            # OpenWA's IncomingMessage uses ``type`` to identify the media
            # kind ("image", "ptt", "video", "document", "sticker", "audio")
            # and ships the downloaded bytes inside ``media.data`` as
            # base64.  There is no ``hasMedia`` field on the dispatched
            # payload - that was a Meta Cloud API field.  Treat any
            # image/video as a selfie candidate; ignore other media.
            msg_type_raw = (data.get("type") or "").lower() if isinstance(data, dict) else ""
            message_body = (data.get("body") or "") if isinstance(data, dict) else ""
            media_obj = (data.get("media") or {}) if isinstance(data, dict) else {}
            media_b64 = (media_obj.get("data") or "") if isinstance(media_obj, dict) else ""
            media_mimetype = (media_obj.get("mimetype") or "") if isinstance(media_obj, dict) else ""

            payload = {"text": {"body": message_body}, "chatId": chat_id}

            if msg_type_raw == "image" and media_b64:
                import base64
                try:
                    image_bytes = base64.b64decode(media_b64)
                except Exception:
                    image_bytes = b""
                payload = {
                    "image": {
                        "id": data.get("id", ""),
                        "bytes": image_bytes,
                        "mimetype": media_mimetype,
                    },
                    "chatId": chat_id,
                }
                await handle_message(phone, "image", payload)
            elif msg_type_raw in ("ptt", "audio", "video", "document", "sticker"):
                # Non-image media: reply with a friendly hint and keep the
                # user in the AWAITING_SELFIE state.
                from whatsapp import client as _wa
                await _wa.send_text(phone, "ابعتلي صورة سيلفي عادية (jpg أو png) مش فيديو ولا ملف صوتي 📸")
            else:
                await handle_message(phone, "text", payload)

        elif event == "session.status":
            status = data.get("status", "") if isinstance(data, dict) else ""
            logger.info("OpenWA session %s status: %s", session_id, status)

    except Exception:
        logger.exception("Failed to parse OpenWA webhook payload")

    return Response(content="OK", status_code=200)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
