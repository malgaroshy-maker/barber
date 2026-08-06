import logging
from datetime import datetime, timedelta

from app.config import MAX_SELFIE_RETRIES
from app.models import ConversationState, UserSession
from conversation import scripts as s
from conversation.catalogue_matcher import (
    CATEGORIES,
    detect_try_on_intent,
    match_category,
    match_haircut,
)
from conversation.state_machine import get_haircut_by_id, get_haircuts, get_recommendations
from whatsapp import client as wa
from whatsapp.interactive import (
    build_category_menu_section,
    build_decision_buttons,
    build_haircut_menu_section,
    build_retry_button,
)

logger = logging.getLogger(__name__)

SESSION_EXPIRY = timedelta(hours=1)

sessions: dict[str, UserSession] = {}


def get_session(phone: str) -> UserSession:
    """Get or create a session, auto-expiring stale ones."""
    if phone in sessions:
        session = sessions[phone]
        if datetime.now() - session.last_active > SESSION_EXPIRY:
            logger.info("Session expired for %s (idle %s), resetting", phone, datetime.now() - session.last_active)
            sessions[phone] = UserSession(phone=phone)
        else:
            session.last_active = datetime.now()
    if phone not in sessions:
        sessions[phone] = UserSession(phone=phone)
    return sessions[phone]


async def send_category_cuts(phone: str, category_id: str, session: UserSession) -> None:
    """Send a formatted catalogue list for all cuts in the requested category."""
    cat = next((c for c in CATEGORIES if c["id"] == category_id), None)
    cat_title = cat["title"] if cat else category_id

    haircuts = [
        h for h in get_haircuts() if h.get("category") == category_id and h.get("active", True)
    ]
    if not haircuts:
        haircuts = get_haircuts()[:4]

    session.active_category = category_id
    session.category_cuts = haircuts
    session.state = ConversationState.AWAITING_CHOICE

    lines = [f"✂️ *{cat_title}*:", ""]
    for i, h in enumerate(haircuts, start=1):
        name = f"{h.get('name_ar', '')} ({h.get('name_en', '')})"
        price = f"{h.get('price_egp', '')} ج.م"
        desc = h.get('description_ar', '')
        lines.append(f"*{i}. {name}* — {price}")
        if desc:
            lines.append(f"   📝 {desc}")
        lines.append("")

    lines.append("📸 *رد برقم القصة (1، 2، 3...) لمشاهدة صورتها وتجربتها على وشك!*")
    lines.append("أو اكتب 'ai' والذكاء الاصطناعي هيختارلك القصة اللي تليق عليك.")

    await wa.send_text(phone, "\n".join(lines))



async def handle_message(phone: str, msg_type: str, payload: dict) -> None:
    session = get_session(phone)
    logger.info("Handling %s from %s in state %s", msg_type, phone, session.state.value)

    # Guard: if we're still processing a previous request, acknowledge and wait
    if session.state == ConversationState.PROCESSING and msg_type != "image":
        await wa.send_text(phone, s.STILL_PROCESSING)
        return

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

    token = text.strip().lower()

    # 1. Menu & restart commands
    if token in ("hi", "hello", "hey", "مرحبا", "menu", "menu.", "القائمة", "القصَات", "القصات", "ابدأ", "start"):
        session.menu_page = 0
        session.selected_haircut = None
        session.result_image_url = None
        session.active_category = None
        session.category_cuts = []
        await show_menu(phone, session)
        session.state = ConversationState.AWAITING_CHOICE
        return

    if token in ("more", "more.", "more!", "التالي", "المزيد", "next", "n", ">"):
        session.menu_page += 1
        await show_menu(phone, session)
        return

    if token in ("back", "back.", "رجوع", "السابق", "prev", "p", "<"):
        session.menu_page = max(0, session.menu_page - 1)
        await show_menu(phone, session)
        return

    if token in ("ai_recommend", "ai", "اقترحلي", "اختارلي", "اقتراح"):
        await handle_interactive(phone, {"button_reply": {"id": "ai_recommend", "title": "AI"}}, session)
        return

    # 2. State-specific rules for AWAITING_SELFIE & AWAITING_DECISION
    if state == ConversationState.AWAITING_SELFIE:
        await wa.send_text(phone, s.INVALID_IMAGE)
        return

    if state == ConversationState.AWAITING_DECISION:
        decision_ids = ["confirm_booking", "try_another"] if session.result_image_url else ["back_to_menu"]
        if token.isdigit():
            idx = int(token) - 1
            if 0 <= idx < len(decision_ids):
                await handle_interactive(phone, {"button_reply": {"id": decision_ids[idx], "title": token}}, session)
                return
        if token in decision_ids:
            await handle_interactive(phone, {"button_reply": {"id": token, "title": token}}, session)
            return

    # 3. Numeric selection within active category or current menu page (AWAITING_CHOICE)
    if token.isdigit() and state == ConversationState.AWAITING_CHOICE:
        idx = int(token)
        available_cuts = session.category_cuts or get_haircuts()[:3]
        if 1 <= idx <= len(available_cuts):
            picked = available_cuts[idx - 1]
            await handle_interactive(
                phone,
                {"button_reply": {"id": picked["id"], "title": picked.get("name_ar", picked["id"])}},
                session,
            )
            return

    # 4. Specific haircut mention & try-on intent
    matched_cut = match_haircut(text)
    if matched_cut:
        if detect_try_on_intent(text) or state == ConversationState.AWAITING_CHOICE:
            await handle_interactive(
                phone,
                {"button_reply": {"id": matched_cut["id"], "title": matched_cut.get("name_ar", matched_cut["id"])}},
                session,
            )
            return

    # 5. Category selection (by keyword, Arabic name, or numeric choice 1-5 when NO active category)
    cat_match = match_category(text)
    if cat_match and not session.category_cuts and state == ConversationState.AWAITING_CHOICE:
        await send_category_cuts(phone, cat_match["id"], session)
        return


    # 6. OpenRouter Gemma LLM response
    from ai.openrouter_llm import generate_llm_response
    llm_reply = await generate_llm_response(text, session.chat_history, state.value)
    if llm_reply:
        session.chat_history.append({"role": "user", "content": text})
        session.chat_history.append({"role": "assistant", "content": llm_reply})
        if len(session.chat_history) > 20:
            session.chat_history = session.chat_history[-20:]
        await wa.send_text(phone, llm_reply)

        if matched_cut and matched_cut.get("image_url"):
            try:
                caption = f"✂️ *{matched_cut.get('name_ar')}* ({matched_cut.get('price_egp')} ج.م)"
                await wa.send_image(phone, matched_cut["image_url"], caption=caption)
            except Exception as exc:
                logger.warning("Failed to auto-send matched haircut image: %s", exc)

        if state == ConversationState.WELCOME:
            session.state = ConversationState.AWAITING_CHOICE
        return

    # 7. Fallback to default state machine logic
    if state == ConversationState.WELCOME:
        await show_menu(phone, session)
        session.state = ConversationState.AWAITING_CHOICE
    elif state == ConversationState.AWAITING_CHOICE:
        await wa.send_text(phone, s.FALLBACK)
        await show_menu(phone, session)


async def handle_interactive(phone: str, interactive: dict, session: UserSession) -> None:

    reply = interactive.get("button_reply") or interactive.get("list_reply")
    if not reply:
        return

    item_id: str = reply.get("id", "")

    if item_id.startswith("cat_"):
        cat_id = item_id[4:]
        await send_category_cuts(phone, cat_id, session)
        return

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

    elif get_haircut_by_id(item_id) is not None:
        session.selected_haircut = item_id
        session.state = ConversationState.AWAITING_SELFIE
        haircut = get_haircut_by_id(item_id)
        ref_url = (haircut or {}).get("image_url", "")
        if ref_url:
            try:
                caption = (
                    f"✂️ *{haircut.get('name_ar', '')}* ({haircut.get('name_en', '')})\n"
                    f"💵 السعر: {haircut.get('price_egp', '')} ج.م\n\n"
                    f"📝 {haircut.get('description_ar', '')}"
                )
                await wa.send_image(phone, ref_url, caption=caption)
            except Exception as exc:
                logger.warning("Reference image send failed for %s: %s", item_id, exc)
        await wa.send_text(phone, s.AWAITING_SELFIE)

    else:
        await wa.send_text(phone, s.FALLBACK)



async def handle_image(phone: str, payload: dict, session: UserSession) -> None:
    if session.state not in (ConversationState.AWAITING_SELFIE, ConversationState.AWAITING_CHOICE, ConversationState.WELCOME):
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
        shape = await analyze_face_shape(image_bytes)
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
    """Show the category menu first, then paginated haircuts within a category.

    On first visit (no active category), shows 5 categories + AI option.
    Once a category is selected, shows the haircuts within it.
    """
    # If user already picked a category, show haircuts within it
    if session and session.active_category:
        haircuts = [
            h for h in get_haircuts()
            if h.get("category") == session.active_category and h.get("active", True)
        ]
        if not haircuts:
            haircuts = list(get_haircuts())[:3]

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
        return

    # First visit: show categories
    sections = build_category_menu_section()
    await wa.send_interactive_list(
        to=phone,
        header="✂️ صالون الحلاقة",
        body="اختار القسم اللي يعجبك، أو اكتب 'ai' والذكاء الاصطناعي يختارلك:",
        button_text="عرض الأقسام",
        sections=sections,
        page=0,
    )
