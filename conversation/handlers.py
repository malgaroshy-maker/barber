import logging
import os
import tempfile
from typing import Optional

import httpx

from app.config import MAX_SELFIE_RETRIES
from app.models import ConversationState, UserSession
from conversation import scripts as s
from conversation.state_machine import get_haircut_by_id, get_recommendations, next_state
from whatsapp import client as wa
from whatsapp.interactive import build_decision_buttons, build_haircut_menu_section, build_retry_button

logger = logging.getLogger(__name__)

sessions: dict[str, UserSession] = {}


def get_session(phone: str) -> UserSession:
    if phone not in sessions:
        sessions[phone] = UserSession(phone=phone)
    return sessions[phone]


async def handle_message(phone: str, msg_type: str, payload: dict) -> None:
    session = get_session(phone)
    logger.info("Handling %s from %s in state %s", msg_type, phone, session.state.value)

    if msg_type == "text":
        text = payload.get("text", {}).get("body", "").strip()
        await handle_text(phone, text, session)
    elif msg_type == "interactive":
        await handle_interactive(phone, payload.get("interactive", {}), session)
    elif msg_type == "image":
        await handle_image(phone, payload, session)
    else:
        await wa.send_text(phone, s.FALLBACK)
        if session.state in (ConversationState.WELCOME, ConversationState.BOOKING_CONFIRMED):
            await show_menu(phone)


async def handle_text(phone: str, text: str, session: UserSession) -> None:
    state = session.state

    if state == ConversationState.WELCOME:
        await show_menu(phone)
        session.state = ConversationState.AWAITING_CHOICE

    elif state == ConversationState.AWAITING_CHOICE:
        await wa.send_text(phone, s.FALLBACK)
        await show_menu(phone)

    elif state == ConversationState.AWAITING_SELFIE:
        await wa.send_text(phone, s.INVALID_IMAGE)

    elif state == ConversationState.AWAITING_DECISION:
        await wa.send_text(phone, s.FALLBACK)
        buttons = build_decision_buttons() if session.result_image_url else build_retry_button()
        await wa.send_interactive_buttons(phone, s.TRY_ANOTHER_PROMPT, buttons)

    elif state in (ConversationState.PROCESSING, ConversationState.BOOKING_CONFIRMED):
        pass


async def handle_interactive(phone: str, interactive: dict, session: UserSession) -> None:
    reply = interactive.get("button_reply") or interactive.get("list_reply")
    if not reply:
        return

    item_id: str = reply.get("id", "")

    if item_id == "ai_recommend":
        session.state = ConversationState.AWAITING_SELFIE
        session.selected_haircut = None
        await wa.send_text(phone, s.AWAITING_SELFIE_AI)

    elif item_id.startswith("confirm_booking"):
        session.state = ConversationState.BOOKING_CONFIRMED
        await wa.send_text(phone, s.BOOKING_CONFIRMED)

    elif item_id == "try_another":
        session.state = ConversationState.AWAITING_CHOICE
        session.selected_haircut = None
        session.result_image_url = None
        await show_menu(phone)

    elif item_id == "back_to_menu":
        session.state = ConversationState.AWAITING_CHOICE
        await show_menu(phone)

    elif item_id.startswith("fade_") or item_id.startswith("buzz_") or item_id.startswith("pompadour") or item_id.startswith("quiff") or item_id.startswith("crew_") or item_id.startswith("french_"):
        session.selected_haircut = item_id
        session.state = ConversationState.AWAITING_SELFIE
        await wa.send_text(phone, s.AWAITING_SELFIE)

    else:
        await wa.send_text(phone, s.FALLBACK)


async def handle_image(phone: str, payload: dict, session: UserSession) -> None:
    if session.state != ConversationState.AWAITING_SELFIE:
        await wa.send_text(phone, s.FALLBACK)
        return

    media_id = (payload.get("image") or payload.get("video") or {}).get("id")
    if not media_id:
        await wa.send_text(phone, s.INVALID_IMAGE)
        return

    session.selfie_media_id = media_id
    session.attempts += 1

    await wa.send_text(phone, s.PRIVACY_NOTICE)

    image_data = await wa.download_media(media_id)
    if image_data is None:
        logger.error("Failed to download image for %s", phone)
        await wa.send_text(phone, s.INVALID_IMAGE)
        if session.attempts >= MAX_SELFIE_RETRIES:
            await wa.send_text(phone, s.MAX_RETRIES)
            session.state = ConversationState.AWAITING_CHOICE
            await show_menu(phone)
        return

    from ai.face_validator import validate_selfie
    valid, msg = validate_selfie(image_data)
    if not valid:
        logger.warning("Selfie validation failed for %s: %s", phone, msg)
        await wa.send_text(phone, msg)
        if session.attempts >= MAX_SELFIE_RETRIES:
            await wa.send_text(phone, s.MAX_RETRIES)
            session.state = ConversationState.AWAITING_CHOICE
            await show_menu(phone)
        else:
            session.state = ConversationState.AWAITING_SELFIE
        return

    session.state = ConversationState.PROCESSING
    await wa.send_text(phone, s.PROCESSING)

    haircut_id = session.selected_haircut
    if not haircut_id:
        from ai.face_analyzer import analyze_face_shape
        shape = analyze_face_shape(image_data)
        if shape:
            session.face_shape = shape
            from conversation.state_machine import get_face_shape_map
            shape_map = get_face_shape_map()
            shape_data = shape_map.get(shape, {})
            rec = get_recommendations(shape)
            if rec:
                haircut_id = rec[0]["id"]
                await wa.send_text(phone, s.FACE_SHAPE_RESULT.format(
                    face_shape_ar=shape_data.get("name_ar", shape),
                    recommendation_ar=shape_data.get("description_ar", ""),
                ))
        if not haircut_id:
            from conversation.state_machine import get_haircuts
            all_hc = get_haircuts()
            if all_hc:
                haircut_id = all_hc[0]["id"]
    session.selected_haircut = haircut_id

    haircut = get_haircut_by_id(haircut_id)
    ref_url = (haircut or {}).get("image_url", "")

    from ai.hair_swap import run_hair_swap
    result_bytes = await run_hair_swap(image_data, ref_url) if ref_url else None

    if result_bytes:
        result_url = None
        async with httpx.AsyncClient() as cl:
            upload_resp = await cl.post(
                "https://tmpfiles.org/api/v1/upload",
                files={"file": ("result.jpg", result_bytes, "image/jpeg")},
                timeout=15,
            )
            if upload_resp.status_code == 200:
                data = upload_resp.json()
                result_url = data.get("data", {}).get("url")
        if result_url:
            session.result_image_url = result_url
            await wa.send_image(phone, result_url, caption=s.AI_RESULT)
        else:
            await wa.send_text(phone, s.DIRECT_RESULT)
    else:
        await wa.send_text(phone, s.DIRECT_RESULT)

    session.state = ConversationState.AWAITING_DECISION
    buttons = build_decision_buttons()
    await wa.send_interactive_buttons(phone, "إيه رأيك في القصة؟", buttons)


async def show_menu(phone: str) -> None:
    from conversation.state_machine import get_haircuts
    haircuts = get_haircuts()
    sections = build_haircut_menu_section(haircuts, ai_option=True)
    await wa.send_interactive_list(
        to=phone,
        header="✂️ صالون الحلاقة",
        body="اختار القصة اللي تعجبك من المنيو:",
        button_text="عرض القصات",
        sections=sections,
    )
