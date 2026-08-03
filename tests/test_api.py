"""Integration tests for FastAPI endpoints."""
import hashlib
import hmac
import json
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import OPENWA_WEBHOOK_SECRET


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "ai-barber-whatsapp-bot"


@pytest.mark.asyncio
async def test_webhook_get_verification_failure():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/webhook?hub.mode=subscribe&hub.verify_token=wrong")
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_webhook_openwa_text_payload():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "event": "message.received",
            "sessionId": "barber-bot",
            "data": {
                "from": "201001234567@c.us",
                "chatId": "201001234567@c.us",
                "type": "chat",
                "body": "مرحبا",
            },
        }
        raw_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if OPENWA_WEBHOOK_SECRET:
            sig = hmac.new(OPENWA_WEBHOOK_SECRET.encode(), raw_bytes, hashlib.sha256).hexdigest()
            headers["X-OpenWA-Signature"] = sig

        response = await client.post("/webhook", content=raw_bytes, headers=headers)
        assert response.status_code == 200
        assert response.text == "OK"
