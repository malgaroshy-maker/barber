import base64
import logging
from typing import Optional

import httpx

from app.config import OPENWA_API_URL, OPENWA_API_KEY, OPENWA_SESSION_ID

logger = logging.getLogger(__name__)

_resolved_session_id: Optional[str] = None


async def resolve_session_id() -> str:
    """Return the OpenWA session UUID for the configured OPENWA_SESSION_ID.

    The user can set OPENWA_SESSION_ID in .env to either:
      * a UUID (used as-is, no API call), or
      * a friendly name like "barber-bot" (resolved via GET /api/sessions).
    The resolved UUID is cached for the lifetime of the process.
    """
    global _resolved_session_id
    if _resolved_session_id:
        return _resolved_session_id

    candidate = (OPENWA_SESSION_ID or "").strip()
    if not candidate:
        return ""

    # If it already looks like a UUID, use it directly.
    looks_like_uuid = (
        len(candidate) == 36
        and candidate[8] == "-"
        and candidate[13] == "-"
        and candidate[18] == "-"
        and candidate[23] == "-"
    )
    if looks_like_uuid:
        _resolved_session_id = candidate
        return _resolved_session_id

    # Otherwise treat it as a name and look it up.
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{OPENWA_API_URL}/api/sessions",
                headers={"X-API-Key": OPENWA_API_KEY},
            )
            if resp.status_code == 200:
                sessions = resp.json()
                for s in sessions:
                    if s.get("name") == candidate:
                        _resolved_session_id = s["id"]
                        logger.info(
                            "Resolved OpenWA session name %r -> id %s",
                            candidate,
                            _resolved_session_id,
                        )
                        return _resolved_session_id
                logger.warning("No OpenWA session with name %r", candidate)
            else:
                logger.warning(
                    "OpenWA session list returned %s: %s", resp.status_code, resp.text[:200]
                )
    except Exception as exc:
        logger.error("Failed to resolve OpenWA session id for %r: %s", candidate, exc)

    # Fall back to the raw value so the request still goes out (and 404s clearly).
    return candidate


def _session_path(suffix: str) -> str:
    return f"/sessions/{OPENWA_SESSION_ID}{suffix}"


async def send_text(to: str, text: str) -> dict:
    chat_id = _to_chat_id(to)
    payload = {
        "chatId": chat_id,
        "text": text,
    }
    return await _post(f"/sessions/{await resolve_session_id()}/messages/send-text", payload)


async def send_image(to: str, image_url: str, caption: str = "") -> dict:
    if "localhost" in image_url or "127.0.0.1" in image_url or "/static/" in image_url:
        from pathlib import Path
        filename = image_url.split("/static/")[-1].split("?")[0]
        local_path = Path("static") / filename
        if local_path.exists():
            return await send_image_base64(to, local_path.read_bytes(), caption=caption)

    chat_id = _to_chat_id(to)
    payload = {
        "chatId": chat_id,
        "url": image_url,
        "caption": caption,
    }
    return await _post(f"/sessions/{await resolve_session_id()}/messages/send-image", payload)


async def send_image_base64(to: str, image_bytes: bytes, caption: str = "") -> dict:
    chat_id = _to_chat_id(to)
    b64 = base64.b64encode(image_bytes).decode()
    mimetype = _detect_mimetype(image_bytes)
    payload = {
        "chatId": chat_id,
        "base64": b64,
        "mimetype": mimetype,
        "caption": caption,
    }
    return await _post(f"/sessions/{await resolve_session_id()}/messages/send-image", payload)


async def upload_media_and_send_image(to: str, image_bytes: bytes, caption: str = "") -> dict:
    return await send_image_base64(to, image_bytes, caption)


async def send_interactive_list(to: str, header: str, body: str, button_text: str, sections: list[dict], *, page: int = 0) -> dict:
    """Paginated numbered menu — text or image carousel depending on data.

    If the rows on the current page all carry an ``image_url`` the menu is
    rendered as an image carousel (one WhatsApp image per cut with a
    numbered caption).  Otherwise it falls back to a plain text menu.
    """
    rows: list[dict] = []
    for section in sections:
        for row in section.get("rows", []):
            rows.append({
                "id": row.get("id", ""),
                "title": row.get("title", ""),
                "description": row.get("description", ""),
                "name_ar": row.get("name_ar", ""),
                "image_url": row.get("image_url", ""),
            })
    return await _send_numbered_menu(to, header, body, rows, page=page)


async def send_interactive_buttons(to: str, body: str, buttons: list[dict]) -> dict:
    """Render a short (max 3) list of decision buttons as a numbered text menu."""
    rows: list[dict] = []
    for btn in buttons:
        btn_id = btn.get("id", "")
        btn_text = (
            btn.get("text")
            or btn.get("title")
            or (btn.get("reply") or {}).get("title", "")
        )
        rows.append({"id": btn_id, "title": btn_text, "description": ""})
    return await _send_short_menu(to, body, rows)


# How many menu rows fit per message.  Each row is "N. title  (price)".
# Keep small so the user only has to read a few options at a glance.
PAGE_SIZE = 3


async def _send_numbered_menu(
    to: str, header: str, body: str, rows: list[dict], page: int
) -> dict:
    """Send one page of a numbered menu as a clean formatted WhatsApp text message."""
    if not rows:
        return await send_text(to, "\n".join([header, body]).strip() or "(empty)")

    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_rows = rows[start:end]
    has_next = end < len(rows)
    has_back = page > 0

    return await _send_text_menu(to, header, body, page_rows, page, has_next, has_back)



async def _send_text_menu(
    to: str, header: str, body: str, page_rows: list[dict], page: int,
    has_next: bool, has_back: bool,
) -> dict:
    """Render a plain-text numbered menu (fallback when no images available)."""
    lines: list[str] = []
    if page == 0:
        if header:
            lines.append(header)
        if body:
            lines.append(body)
        lines.append("")

    for i, r in enumerate(page_rows, start=1):
        title = r.get("title", "")
        if title:
            lines.append(f"{i}. {title}")
        else:
            lines.append(f"{i}. {r['id']}")
        desc = (r.get("description") or "").strip()
        if desc:
            lines.append(f"   {desc}")

    lines.append("")
    if has_next:
        lines.append("رد بالرقم (1، 2، 3) أو 'more' للقصَات اللي بعدها.")
    elif has_back:
        lines.append("رد بالرقم (1، 2، 3) أو 'back' للرجوع.")
    elif page > 0:
        lines.append("رد بالرقم (1، 2، 3) لاختيار القصة، أو 'back'.")
    else:
        lines.append("رد بالرقم (1، 2، 3) لاختيار القصة.")
        lines.append("أو اكتب 'ai' عشان أقترحلك قِصة تناسب وشك.")

    return await send_text(to, "\n".join(lines))


async def _send_image_carousel(
    to: str, page_rows: list[dict], page: int, has_next: bool, has_back: bool,
) -> dict:
    """Send one page of the haircut catalogue as WhatsApp images."""
    from pathlib import Path
    static_dir = Path(__file__).parent.parent / "static"

    chat_id = _to_chat_id(to)
    session_id = await resolve_session_id()

    logger.info("Image carousel: sending page %d with %d images", page, len(page_rows))

    # Header
    await send_text(to, f"✂️ صالون الحلاقة (صفحة {page + 1}):")

    # Send each reference image with a numbered caption
    for i, row in enumerate(page_rows, start=1):
        url = row.get("image_url", "")
        name = row.get("name_ar", "") or row.get("title", "")
        if url:
            # Extract filename from URL and read from disk
            filename = url.split("/")[-1]
            image_path = static_dir / filename
            
            if image_path.exists():
                try:
                    logger.info("Image carousel: sending %s (%d bytes)", filename, image_path.stat().st_size)
                    image_bytes = image_path.read_bytes()
                    await send_image_base64(to, image_bytes, caption=f"{i}. {name}")
                    logger.info("Image carousel: sent %s successfully", filename)
                    # Small delay to avoid overwhelming OpenWA
                    import asyncio
                    await asyncio.sleep(1)
                except Exception as exc:
                    logger.warning("Image carousel: failed to send %s: %s", filename, exc)
            else:
                logger.warning("Image carousel: image not found %s", image_path)

    # Footer
    if has_next:
        await send_text(to, "رد بالرقم (1، 2، 3) للاختيار، أو 'more' للقصات اللي بعدها ✨")
    elif has_back:
        await send_text(to, "رد بالرقم (1، 2، 3) للاختيار، أو 'back' للرجوع ⬅️")
    elif page > 0:
        await send_text(to, "رد بالرقم (1، 2، 3) للاختيار، أو 'back' ⬅️")
    else:
        await send_text(to, "رد بالرقم (1، 2، 3) للاختيار، أو اكتب 'ai' عشان أقترحلك قصة تناسب وشك 🤖")

    return {}


async def _send_short_menu(to: str, body: str, rows: list[dict]) -> dict:
    """Send a 1-3 button decision menu as a short numbered list."""
    lines = [body, ""]
    for i, r in enumerate(rows, start=1):
        title = r.get("title", "").strip() or r.get("id", "")
        lines.append(f"{i}. {title}")
    lines.append("")
    lines.append("رد بالرقم لاختيارك.")
    return await send_text(to, "\n".join(lines))


async def download_media(media_id: str) -> Optional[bytes]:
    if not OPENWA_API_URL:
        return None
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{OPENWA_API_URL}/api/media/{media_id}",
            headers={"X-API-Key": OPENWA_API_KEY},
        )
        if resp.status_code == 200:
            return resp.content
        logger.warning("Failed to download media from OpenWA: %s", resp.text)
        return None


async def _post(path: str, payload: dict) -> dict:
    if not OPENWA_API_URL:
        logger.error("OPENWA_API_URL not configured")
        return {}
    # Use longer timeouts for image uploads (base64 can be large)
    timeout = httpx.Timeout(connect=10.0, read=60.0, write=60.0, pool=10.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{OPENWA_API_URL}/api{path}",
                headers={
                    "X-API-Key": OPENWA_API_KEY,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if resp.status_code not in (200, 201, 202, 204):
                logger.error("OpenWA API error (%s): %s", resp.status_code, resp.text)
                return {}
            if resp.status_code == 204:
                return {}
            return resp.json()
    except httpx.TimeoutException as exc:
        logger.error("OpenWA API timeout on %s: %s", path, exc)
        return {}
    except httpx.HTTPError as exc:
        logger.error("OpenWA API transport error on %s: %s", path, exc)
        return {}


def _to_chat_id(phone: str) -> str:
    """Normalise a phone/chatId to the format OpenWA expects.

    - ``+201234567890`` -> ``201234567890@c.us``
    - ``201234567890@c.us`` -> unchanged
    - ``201234567890@lid`` -> unchanged (newer WhatsApp uses linked IDs)
    - ``120363@g.us`` -> unchanged (groups)
    """
    phone = phone.strip().replace("+", "")
    if "@" in phone:
        return phone
    return f"{phone}@c.us"


def _detect_mimetype(data: bytes) -> str:
    if data[:4] == b"\x89PNG":
        return "image/png"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"
