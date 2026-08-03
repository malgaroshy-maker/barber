"""End-to-end bot conversation state machine tests."""
from unittest.mock import AsyncMock, patch
import pytest
from PIL import Image
import io

from app.models import ConversationState
from conversation.handlers import get_session, handle_message, sessions


def _create_synthetic_face_bytes() -> bytes:
    """Create a minimal 400x400 synthetic RGB image for testing."""
    img = Image.new("RGB", (400, 400), color=(120, 150, 180))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def clear_sessions():
    """Reset session state before each test."""
    sessions.clear()


@pytest.mark.asyncio
@patch("whatsapp.client.send_interactive_list", new_callable=AsyncMock)
@patch("whatsapp.client.send_text", new_callable=AsyncMock)
@patch("whatsapp.client.send_image", new_callable=AsyncMock)
@patch("whatsapp.client.send_interactive_buttons", new_callable=AsyncMock)
async def test_full_bot_flow(mock_buttons, mock_image, mock_text, mock_list):
    phone = "201234567890"

    # Step 1: Initial greeting message ("مرحبا")
    await handle_message(phone, "text", {"text": {"body": "مرحبا"}})

    session = get_session(phone)
    assert session.state == ConversationState.AWAITING_CHOICE
    assert mock_list.called

    # Step 2: Customer selects haircut #1
    await handle_message(phone, "text", {"text": {"body": "1"}})

    assert session.state == ConversationState.AWAITING_SELFIE
    assert session.selected_haircut is not None
    assert mock_text.called

    # Step 3: Customer sends text while bot is awaiting selfie -> warning sent
    mock_text.reset_mock()
    await handle_message(phone, "text", {"text": {"body": "إزيك"}})

    assert session.state == ConversationState.AWAITING_SELFIE
    assert mock_text.called

    # Step 4: Customer sends selfie image
    mock_text.reset_mock()
    image_bytes = _create_synthetic_face_bytes()
    payload = {
        "image": {
            "id": "media_123",
            "bytes": image_bytes,
            "mimetype": "image/png",
        }
    }

    # Mock selfie validator to return valid face detection for test
    with patch("ai.face_validator.validate_selfie", return_value=(True, "done")), \
         patch("ai.hair_swap.run_hair_swap", new_callable=AsyncMock, return_value=b"fake_output_bytes"), \
         patch("whatsapp.client.upload_media_and_send_image", new_callable=AsyncMock, return_value=True):
        await handle_message(phone, "image", payload)

    assert session.state == ConversationState.AWAITING_DECISION
    assert mock_buttons.called

    # Step 5: Customer confirms booking ("1")
    mock_text.reset_mock()
    await handle_message(phone, "text", {"text": {"body": "1"}})

    assert session.state == ConversationState.BOOKING_CONFIRMED
    assert mock_text.called


@pytest.mark.asyncio
@patch("whatsapp.client.send_interactive_list", new_callable=AsyncMock)
@patch("whatsapp.client.send_text", new_callable=AsyncMock)
async def test_bot_menu_pagination(mock_text, mock_list):
    phone = "201999999999"

    # Greeting
    await handle_message(phone, "text", {"text": {"body": "hi"}})
    session = get_session(phone)
    assert session.menu_page == 0

    # User asks for next page ("more")
    await handle_message(phone, "text", {"text": {"body": "more"}})
    assert session.menu_page == 1

    # User goes back ("back")
    await handle_message(phone, "text", {"text": {"body": "back"}})
    assert session.menu_page == 0
