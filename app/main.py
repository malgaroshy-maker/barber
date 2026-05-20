import logging
from pathlib import Path

from fastapi import FastAPI, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import WHATSAPP_VERIFY_TOKEN, USE_OPENWA, OPENWA_WEBHOOK_SECRET
from conversation.handlers import handle_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Barber WhatsApp Bot", version="0.1.0")

static_dir = Path(__file__).parent.parent / "data"
if static_dir.exists():
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
async def receive_message(request: Request):
    body = await request.json()
    logger.info("Incoming webhook: %s", body)

    if USE_OPENWA:
        return await _handle_openwa_webhook(body)

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


async def _handle_openwa_webhook(body: dict) -> Response:
    if OPENWA_WEBHOOK_SECRET:
        import hmac
        import hashlib
        signature = body.get("signature", "")
        expected = "sha256=" + hmac.new(
            OPENWA_WEBHOOK_SECRET.encode(),
            str(body.get("data", "")).encode(),
            hashlib.sha256,
        ).hexdigest()
        if signature and not hmac.compare_digest(signature, expected):
            logger.warning("Invalid OpenWA webhook signature")
            return Response(content="Invalid signature", status_code=401)

    try:
        event = body.get("event", "")
        data = body.get("data", {})
        session_id = body.get("sessionId", "")

        if event == "message.received":
            from_id = data.get("from", "")
            phone = from_id.replace("@c.us", "").replace("@g.us", "")
            msg_type = "text"
            message_body = data.get("body", "")
            has_media = data.get("hasMedia", False)

            payload = {"text": {"body": message_body}}

            if has_media:
                msg_type = "image"
                media_id = data.get("id", "")
                payload = {"image": {"id": media_id}}

            await handle_message(phone, msg_type, payload)

        elif event == "session.status":
            status = data.get("status", "")
            logger.info("OpenWA session %s status: %s", session_id, status)

    except Exception:
        logger.exception("Failed to parse OpenWA webhook payload")

    return Response(content="OK", status_code=200)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
