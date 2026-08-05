import sys
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, patch

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from conversation.catalogue_matcher import match_category, match_haircut, detect_try_on_intent
from conversation.handlers import get_session, handle_message, sessions
from app.models import ConversationState


def test_catalogue_matcher_category():
    assert match_category("1")["id"] == "fades"
    assert match_category("كلاسيك")["id"] == "classic"
    assert match_category("قصات الكيرلي")["id"] == "curls"
    assert match_category("مودرن")["id"] == "modern"
    assert match_category("قصيرة")["id"] == "short"


def test_catalogue_matcher_haircut():
    cut1 = match_haircut("بومبادور")
    assert cut1 is not None and cut1["id"] == "pompadour"

    cut2 = match_haircut("Classic Fade")
    assert cut2 is not None and cut2["id"] == "fade_classic"

    cut3 = match_haircut("buzz_cut")
    assert cut3 is not None and cut3["id"] == "buzz_cut"


def test_try_on_intent():
    assert detect_try_on_intent("عايز أجرب قصة الفيد") is True
    assert detect_try_on_intent("ركبلي القصة دي على صورتي") is True
    assert detect_try_on_intent("بكام سعر القصة؟") is False


@pytest.mark.asyncio
@patch("whatsapp.client.send_image", new_callable=AsyncMock)
@patch("whatsapp.client.send_text", new_callable=AsyncMock)
@patch("whatsapp.client.send_interactive_list", new_callable=AsyncMock)
async def test_category_flow(mock_list, mock_text, mock_image):
    phone = "201000000000"
    sessions.clear()

    # 1. User sends "menu"
    await handle_message(phone, "text", {"text": {"body": "menu"}})
    session = get_session(phone)
    assert session.state == ConversationState.AWAITING_CHOICE
    assert mock_list.called

    # 2. User chooses category "fades"
    mock_text.reset_mock()
    await handle_message(phone, "text", {"text": {"body": "فيد"}})
    assert session.active_category == "fades"
    assert len(session.category_cuts) > 0
    assert mock_text.called

    # 3. User picks haircut #1 in category fades
    mock_image.reset_mock()
    await handle_message(phone, "text", {"text": {"body": "1"}})
    assert session.state == ConversationState.AWAITING_SELFIE
    assert session.selected_haircut == session.category_cuts[0]["id"]
    assert mock_image.called

