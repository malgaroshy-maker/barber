import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from app.models import ConversationState, UserSession
from conversation import scripts as s
from conversation.handlers import SESSION_EXPIRY, get_session, handle_message, sessions


@pytest.fixture(autouse=True)
def clear_sessions():
    sessions.clear()
    yield
    sessions.clear()


@pytest.mark.asyncio
async def test_session_expiry():
    phone = "201234567890"
    session = get_session(phone)
    session.state = ConversationState.AWAITING_SELFIE
    session.selected_haircut = "buzz_cut"

    # Set last_active back into the past beyond SESSION_EXPIRY
    session.last_active = datetime.now() - (SESSION_EXPIRY + timedelta(minutes=5))

    # Retrieve session again; should be expired and reset to WELCOME
    new_session = get_session(phone)
    assert new_session.state == ConversationState.WELCOME
    assert new_session.selected_haircut is None


@pytest.mark.asyncio
async def test_processing_state_guard():
    phone = "201234567891"
    session = get_session(phone)
    session.state = ConversationState.PROCESSING

    with patch("whatsapp.client.send_text", new_callable=AsyncMock) as mock_send_text:
        payload = {"text": {"body": "hello"}}
        await handle_message(phone, "text", payload)

        mock_send_text.assert_called_once_with(phone, s.STILL_PROCESSING)
