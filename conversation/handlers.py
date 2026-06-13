import logging

from app.config import MAX_SELFIE_RETRIES
from app.models import ConversationState, UserSession
from conversation import scripts as s
from conversation.state_machine import get_haircut_by_id, get_haircuts, get_recommendations, next_state
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
            await show_menu(phone, session)


async def handle_text(phone: str, text: str, session: UserSession) -> None:
    state = session.state

    if state == ConversationState.WELCOME:
        # WELCOME is the very first state for a brand-new session.  But
        # also treat it as the recovery landing: if the user sends "hi"
        # again, reset menu state and re-show the menu.
        session.menu_page = 0
        session.selected_haircut = None
        session.result_image_url = None
        await show_menu(phone, session)
        session.state = ConversationState.AWAITING_CHOICE

    elif state == ConversationState.AWAITING_CHOICE:
        # The user is replying to the menu.  We use plain-text paginated
        # menus under OpenWA, so the reply is a single digit ("3"), a
        # haircut id ("fade_classic"), a control token ("more", "ai"), or
        # an Arabic/English word.
        token = text.strip().lower()

        if token in ("more", "more.", "more!", "التالي", "المزيد", "next", "n", ">"):
            session.menu_page += 1
            await show_menu(phone, session)
            return

        if token in ("back", "back.", "رجوع", "السابق", "prev", "p", "<"):
            session.menu_page = max(0, session.menu_page - 1)
            await show_menu(phone, session)
            return

        if token in ("menu", "menu.", "القائمة", "القصَات", "القصات", "ابدأ", "start"):
            session.menu_page = 0
            await show_menu(phone, session)
            return

        if token in ("ai_recommend", "ai", "اقترحلي", "اختارلي", "اقتراح"):
            await handle_interactive(phone, {"button_reply": {"id": "ai_recommend", "title": "AI"}}, session)
            return

        # Numeric reply?  Map to the haircut id on the current page.
        if token.isdigit():
            idx = int(token)
            haircuts = get_haircuts()
            visible = haircuts[session.menu_page * 3 : session.menu_page * 3 + 3]
            if 1 <= idx <= len(visible):
                picked = visible[idx - 1]
                await handle_interactive(
                    phone,
                    {"button_reply": {"id": picked["id"], "title": picked.get("name_ar", picked["id"])}},
                    session,
                )
                return
            # Index out of range for current page - render the current page
            # again and gently remind.
            await show_menu(phone, session)
            return

        # Direct haircut id (e.g. "fade_classic")
        if token and any(h["id"] == token for h in get_haircuts()):
            await handle_interactive(phone, {"button_reply": {"id": token, "title": token}}, session)
            return

        # Fallback
        await wa.send_text(phone, s.FALLBACK)
        await show_menu(phone, session)

    elif state == ConversationState.AWAITING_SELFIE:
        await wa.send_text(phone, s.INVALID_IMAGE)

    elif state == ConversationState.AWAITING_DECISION:
        # The decision menu is rendered as a numbered list because OpenWA
        # does not ship native buttons; accept numeric replies here so the
        # user can answer 1 / 2 instead of typing the button id.
        token = text.strip().lower()
        if session.result_image_url:
            decision_ids = ["confirm_booking", "try_another"]
        else:
            decision_ids = ["back_to_menu"]

        if token.isdigit():
            idx = int(token) - 1
            if 0 <= idx < len(decision_ids):
                await handle_interactive(phone, {"button_reply": {"id": decision_ids[idx], "title": token}}, session)
                return

        if token in ("1", "2"):
            idx = int(token) - 1
            if 0 <= idx < len(decision_ids):
                await handle_interactive(phone, {"button_reply": {"id": decision_ids[idx], "title": token}}, session)
                return

        if token in decision_ids:
            await handle_interactive(phone, {"button_reply": {"id": token, "title": token}}, session)
            return

        # Anything else: re-render the decision menu and let the user try again.
        buttons = build_decision_buttons() if session.result_image_url else build_retry_button()
        await wa.send_interactive_buttons(phone, s.TRY_ANOTHER_PROMPT, buttons)

    elif state in (ConversationState.PROCESSING, ConversationState.BOOKING_CONFIRMED):
        # After a booking is confirmed (or the bot is mid-processing) accept
        # an explicit "hi" / "menu" / "ابدأ" to start a fresh flow.  This
        # makes the bot recoverable if the user ever gets stuck.
        token = text.strip().lower()
        if token in ("hi", "hello", "hey", "menu", "ابدأ", "ابدأ من جديد",
                     "القائمة", "القصَات", "القصات", "start", "restart"):
            session.state = ConversationState.WELCOME
            session.selected_haircut = None
            session.result_image_url = None
            session.menu_page = 0
            session.attempts = 0
            await show_menu(phone, session)
            session.state = ConversationState.AWAITING_CHOICE
            return
        # For BOOKING_CONFIRMED, also let the user restart with "جرب تاني"
        if state == ConversationState.BOOKING_CONFIRMED:
            session.state = ConversationState.WELCOME
            session.result_image_url = None
            await wa.send_text(phone, "تمام يا باشا، لو عايز تجرب قصة تانية قولي 'جرب تاني' أو 'menu' ✂️")
            return
        # Otherwise stay quiet - the bot is processing or busy.
        return


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
        session.menu_page = 0
        await show_menu(phone, session)

    elif item_id == "back_to_menu":
        session.state = ConversationState.AWAITING_CHOICE
        session.menu_page = 0
        await show_menu(phone, session)

    elif item_id.startswith("fade_") or item_id.startswith("buzz_") or item_id.startswith("pompadour") or item_id.startswith("quiff") or item_id.startswith("crew_") or item_id.startswith("french_"):
        session.selected_haircut = item_id
        session.state = ConversationState.AWAITING_SELFIE
        # Reset menu paging so the next "back" returns to the top.
        session.menu_page = 0
        haircut = get_haircut_by_id(item_id)
        ref_url = (haircut or {}).get("image_url", "")
        if ref_url:
            # Reference image is decorative; don't let a slow external URL
            # block the rest of the flow.
            try:
                await wa.send_image(phone, ref_url, caption=haircut.get("name_ar", ""))
            except Exception as exc:
                logger.warning("Reference image send failed for %s: %s", item_id, exc)
        await wa.send_text(phone, s.AWAITING_SELFIE)

    else:
        await wa.send_text(phone, s.FALLBACK)


async def handle_image(phone: str, payload: dict, session: UserSession) -> None:
    if session.state != ConversationState.AWAITING_SELFIE:
        await wa.send_text(phone, s.FALLBACK)
        return

    image_obj = payload.get("image") or payload.get("video") or {}
    media_id = image_obj.get("id")
    image_bytes = image_obj.get("bytes")

    # OpenWA ships the downloaded bytes inline in the webhook payload as
    # base64, so we can skip the separate /api/media download call.
    if not image_bytes and media_id:
        image_bytes = await wa.download_media(media_id)

    if not image_bytes:
        logger.error("No image bytes for %s (id=%s)", phone, media_id)
        await wa.send_text(phone, s.INVALID_IMAGE)
        return

    session.selfie_media_id = media_id
    session.attempts += 1

    await wa.send_text(phone, s.PRIVACY_NOTICE)

    from ai.face_validator import validate_selfie
    valid, msg = validate_selfie(image_bytes)
    if not valid:
        logger.warning("Selfie validation failed for %s: %s", phone, msg)
        await wa.send_text(phone, msg)
        if session.attempts >= MAX_SELFIE_RETRIES:
            await wa.send_text(phone, s.MAX_RETRIES)
            session.state = ConversationState.AWAITING_CHOICE
            await show_menu(phone, session)
        else:
            session.state = ConversationState.AWAITING_SELFIE
        return

    session.state = ConversationState.PROCESSING
    await wa.send_text(phone, s.PROCESSING)

    haircut_id = session.selected_haircut
    if not haircut_id:
        from ai.face_analyzer import analyze_face_shape
        shape = analyze_face_shape(image_bytes)
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
            all_hc = get_haircuts()
            if all_hc:
                haircut_id = all_hc[0]["id"]
    session.selected_haircut = haircut_id

    haircut = get_haircut_by_id(haircut_id)
    ref_url = (haircut or {}).get("image_url", "")

    from ai.hair_swap import run_hair_swap
    result_bytes = await run_hair_swap(image_bytes, haircut_id)

    if result_bytes:
        upload_result = await wa.upload_media_and_send_image(phone, result_bytes, caption=s.AI_RESULT)
        if upload_result:
            session.result_image_url = "uploaded_via_api"

    if not result_bytes and ref_url:
        session.result_image_url = ref_url
        await wa.send_image(phone, ref_url, caption=s.AI_RESULT)

    if not result_bytes and not ref_url:
        await wa.send_text(phone, s.DIRECT_RESULT)

    session.state = ConversationState.AWAITING_DECISION
    buttons = build_decision_buttons()
    await wa.send_interactive_buttons(phone, "إيه رأيك في القصة؟", buttons)


async def show_menu(phone: str, session: UserSession | None = None) -> None:
    """Show the paginated haircut menu — image carousel or text fallback.

    When reference images are available the menu is rendered as a WhatsApp
    image carousel (3 images per page with numbered captions).  Otherwise
    it falls back to a plain-text numbered list.
    """
    haircuts = get_haircuts()

    sections = build_haircut_menu_section(haircuts, ai_option=True)
    page = session.menu_page if session else 0
    total_pages = len(haircuts) // 3 + (1 if len(haircuts) % 3 else 0)
    await wa.send_interactive_list(
        to=phone,
        header="✂️ صالون الحلاقة",
        body=(
            f"اختار قصة (صفحة {page + 1} من {total_pages}):"
            if page > 0
            else "اختار القصة اللي تعجبك من المنيو:"
        ),
        button_text="عرض القصات",
        sections=sections,
        page=page,
    )
