# Implementation Summary: OpenWA Gateway Fixes (Tunneling & URI)

## What Changed
Fixed the WhatsApp tunneling / webhook URL problems by making OpenWA the
default, local-only WhatsApp transport. The bot no longer depends on a public
`*.trycloudflare.com` URL that changes every restart, and no longer emits
`Cannot determine default origin certificate path` warnings. A one-time QR
scan replaces every Meta webhook reconfiguration step.

## Files Modified
| File | Change |
|------|--------|
| `start.bat` | **Rewritten** — auto-detects `OPENWA_API_KEY`/`OPENWA_SESSION_ID`; routes to OpenWA mode (local) or legacy Meta + Cloudflare tunnel mode |
| `start-openwa.bat` | **New** — single command to boot OpenWA + FastAPI; opens the dashboard |
| `stop.bat` | **Updated** — kills OpenWA gateway/dashboard windows and port 2785/2886 in addition to FastAPI and cloudflared |
| `setup-openwa.bat` | **Rewritten** — clones + installs + builds + idempotently patches `openwa\.env` and the main `.env` using `Set-Content` (the old `Get-Content` / `replace` pattern silently failed when keys were already populated) |
| `.env` | **Updated** — `OPENWA_WEBHOOK_SECRET` and `OPENWA_SESSION_ID` filled in; stale `NGROK_URL` cleared (it changed every launch) |
| `.env.example` | **Rewritten** — clearly separates Mode A (OpenWA) and Mode B (Meta) |
| `specs/002-openwa-gateway/{plan,spec,tasks}.md` | **Updated** to reflect `whatsapp-web.js` engine, localhost-only webhook, and new `start-openwa.bat` |

## Why OpenWA (not Cloudflare quick-tunnel)
- Cloudflare quick-tunnel prints a new URL every restart. Meta would have to be
  reconfigured each time, and the URL has no uptime guarantee.
- OpenWA + FastAPI both run on the same machine, so the webhook target is
  always `http://localhost:8000/webhook` — no DNS, no tunnel, no certs.
- OpenWA is already cloned (`openwa/`) and built; only a one-time QR scan
  in the dashboard is required.

## How to Use

### First time
```cmd
setup-openwa.bat          :: clone + install + build + patch .env
start-openwa.bat          :: boot OpenWA + FastAPI, opens dashboard
```
In the dashboard (http://localhost:2886):
1. Create an API key.
2. Create session `barber-bot` and scan the QR code with WhatsApp.
3. Paste the API key into `.env` (`OPENWA_API_KEY=...`).
4. Create a webhook:
   - URL: `http://localhost:8000/webhook`
   - Events: `message.received`, `session.status`
   - Secret: `barber-webhook-secret` (must match `OPENWA_WEBHOOK_SECRET`)

### Subsequent runs
```cmd
start-openwa.bat          :: or just `start.bat` (auto-detects)
```

### Legacy Meta mode
If `OPENWA_API_KEY` and `OPENWA_SESSION_ID` are empty, `start.bat` falls back
to the original Meta Cloud API + Cloudflare tunnel flow. This is preserved so
existing deployments keep working.

## Risks / Notes
- Engine is `whatsapp-web.js` (not Baileys) — the v0.1.6 release still ships
  Baileys as "future". `whatsapp-web.js` uses Puppeteer/Chromium and runs
  headless on Windows with the `--no-sandbox` flags.
- Webhook secret in OpenWA dashboard must equal `OPENWA_WEBHOOK_SECRET` in
  the main `.env`, otherwise `_handle_openwa_webhook` returns 401.
- Base64 image size limit on OpenWA is ~5 MB; result images from Cloudflare
  inpainting are typically well below this.

---

## Round 2: Payload shape & menu rendering (2026-06-13)

End-to-end test of the running stack surfaced two more mismatches between
the bot's Meta-style payloads and OpenWA's `send-text` / `send-image` DTOs.

### Issue 1 — `send-text` with `options.buttons` was returning 400
The Meta Cloud API supports `interactive.button` payloads; OpenWA's
`SendTextMessageDto` only accepts `chatId` and `text` (max 4096 chars). The
bot was sending `{"chatId","text","options":{"buttons":[...]}}` and OpenWA
silently rejected the unknown field with 400 Bad Request. With 35 menu
rows the encoded payload was ~4 KB of buttons, so the failure was total.

**Fix:** rewrote `whatsapp/openwa_client.py:send_interactive_list` and
`send_interactive_buttons` to render the menu as a single numbered text
message. The bot then accepts the haircut id (e.g. `fade_classic`) or the
`ai_recommend` token back as plain text. The conversation handler's
`handle_text` for `AWAITING_CHOICE` now routes known ids into
`handle_interactive` so the rest of the flow works without buttons.

### Issue 2 — `send-image` with nested `image.url` / `image.base64` was returning 400
OpenWA's `SendMediaMessageDto` flattens the payload: `chatId` + `url`
**or** `chatId` + `base64` + `mimetype` + (optional) `caption` + (optional)
`filename`. The bot was sending `{"chatId","image":{"url":...},"caption":...}`
and `{"chatId","image":{"base64":"data:image/jpeg;base64,..."}}`. The
nested `image` object was dropped (and the base64 had the wrong `data:`
prefix), so OpenWA reported "chatId required" or just 400.

**Fix:** rewrote `send_image` and `send_image_base64` to use the flat
top-level fields. `send_image_base64` now sends raw base64 plus the
detected `mimetype` (`image/jpeg`, `image/png`, or `image/webp`).

### Issue 3 — test sender `201234567890@c.us` does not exist on WhatsApp
The earlier e2e test used a placeholder phone. OpenWA returns 500 because
the target chat does not exist. The fix is to point the test at the bot's
own phone (`218918575743@c.us`, the connected session's `phone`). Any
outbound message to that chatId is then immediately delivered back to the
bot's WhatsApp (sandbox loop).

### Files changed
| File | Change |
|------|--------|
| `whatsapp/openwa_client.py` | Replaced `send_interactive_list`/`send_interactive_buttons` with numbered-text renderers; flattened `send_image` and `send_image_base64` payloads to match the OpenWA DTO |
| `conversation/handlers.py` | `AWAITING_CHOICE` text handler now recognises `ai_recommend`/`fade_classic`/etc. and routes them into `handle_interactive` |

### Verification
`C:\Users\masal\AppData\Local\Temp\opencode\full_e2e.py` now passes
all 9 steps against the live stack (OpenWA + FastAPI, session
`barber` = `61af1ace-...`, phone `218918575743`). Every outbound
`send-text` and `send-image` call returns `201 Created` with a real
`messageId` from the connected session.

---

## Round 3: Image detection, body-parser limit, and result delivery (2026-06-13)

### Issue 1 — OpenWA was rejecting send-image with 413 PayloadTooLarge
The Express/NestJS default `json` body-parser limit is 100 KB. Cloudflare
inpainting results are typically 250–500 KB (base64 ≈ 1.3×). Every
`send-image` call with a base64 result was returning 413 "request entity
too large". The error appeared in the bot log as "request entity too
large" and the user never received the result image.

**Fix:** patched `openwa/src/main.ts` to set `json`, `urlencoded`, and
`raw` body-parser limits to `15mb` (configurable via
`BODY_PARSER_LIMIT` env var). Recompiled with `npm run build`. The
built `dist/main.js` now includes the raised limit.

### Issue 2 — Image messages were being routed as text (always INVALID_IMAGE)
OpenWA's `IncomingMessage` schema uses **`type: "image"`** (or `"ptt"`,
`"video"`, etc.) and ships the **downloaded bytes inline as
`media.data` (base64)** with `media.mimetype`. There is **no `hasMedia`**
field on the dispatched webhook payload — that is a Meta Cloud API
field. The bot's `_handle_openwa_webhook` was checking
`data.get("hasMedia")` which was always `False`, so every image was
routed to the text handler, resulting in the `INVALID_IMAGE` fallback.

**Fix:** rewrote the webhook handler in `app/main.py` to detect images
by `data.type`, decode the inline `data.media.data` base64 to bytes,
and pass them through the `handle_image` pipeline. Non-image media
types (`ptt`, `audio`, `video`, `document`, `sticker`) now get a clear
"send a photo, not a video" reply instead of crashing.

**Side fix:** because the bytes are already in the webhook payload,
the bot no longer calls `wa.download_media(media_id)` for OpenWA
(in fact OpenWA's `/api/media` namespace doesn't even exist for
message downloads — the only download path is for historical messages).
`conversation/handlers.py:handle_image` now uses the inline bytes
directly and only falls back to `download_media` if they are missing.

### Issue 3 — User chatIds use `@lid` (Linked ID), not `@c.us`
Real incoming WhatsApp messages from the user had chatId
`94129207951387@lid`. The bot's `_to_chat_id` was unconditionally
appending `@c.us` to any phone that didn't already end in it, producing
`94129207951387@lid@c.us` which OpenWA doesn't understand.

**Fix:** `_to_chat_id` now passes through any value that already
contains `@`. The OpenWA webhook handler keeps the full chatId as
the session key and reply target so state is stable per-user.

### Issue 4 — Face validator always rejected real selfies (false negative)
The validator used OpenCV's `haarcascade_frontalface_default.xml`
(Haar cascade) which misses ~30–40% of faces even in good lighting.
Users consistently got "مفيش وش واضح في الصورة" for clear face photos.

**Fix:** rewrote `ai/face_validator.py` (and `ai/hair_mask.py`) to use
**OpenCV YuNet** (DNN-based face detector) as the primary detector.
The ONNX model (`face_detection_yunet_2023mar.onnx`, 232 KB) is
auto-downloaded on first use and cached in `ai/models/`. A 4-cascade
Haar ensemble (`default`, `alt`, `alt2`, `profileface`) serves as
fallback. Additional improvements:
- Histogram equalization on the Y channel for low-light images
- 2× upscale if the smaller side < 320px
- Lowered face-area threshold from 15% to 4% (WhatsApp selfies
  often show the face at 5–20% of frame)
- Edge-cropped face rejection with a clear Arabic message
- 4 new tests in `tests/test_face_validator.py`

### Issue 5 — Menu overload: 35 rows in one message was unreadable
The original Meta list message could hold 10 rows, but the OpenWA
text-only fallback was sending all 35 cuts in one blob.

**Fix:** rewrote `send_interactive_list` and `send_interactive_buttons`
to render a **paginated 3-cut numbered menu** with "more" / "back"
navigation. The user replies with a single digit (1, 2, 3) to pick
from the current page. The menu_page is tracked per-session on the
`UserSession` object. `handle_text` for `AWAITING_CHOICE` now routes
numeric replies, "more", "back", and "ai" into the correct handlers.

### Issue 6 — AWAITING_DECISION rejected numeric replies (1/2)
After the result image is sent, the bot renders a decision menu:
```
1. ✅ اعتمد واحجز
2. 🔄 جرب قصة تانية
```
But the handler only reacted to structured `interactive.button_reply`
webhook payloads, not plain numeric text. Users sending "1" or "2"
received the generic `FALLBACK` message and the same menu re-rendered.

**Fix:** `handle_text` for `AWAITING_DECISION` now accepts numeric
digits and maps them to `confirm_booking` / `try_another`. It also
accepts direct button ids for compatibility.

### Issue 7 — BOOKING_CONFIRMED state was a silent no-op
After a booking was confirmed (or the state machine landed there
during testing), all further text messages were silently dropped —
the handler had only `pass` for this state. Users were effectively
bricked with no way to recover.

**Fix:** `BOOKING_CONFIRMED` (and `PROCESSING`) now accept "hi",
"menu", "ابدأ", and "جرب تاني" as recovery commands. They reset the
session to `WELCOME` and show a fresh menu. Any other text receives
a friendly hint suggesting they type "menu" to restart.

### Issue 8 — httpx default 30s timeout froze the webhook on slow URL sends
The `send_image` handler sends a reference image URL; if OpenWA's
server-side URL fetch is slow or blocked (e.g. external render.com
URLs), the bot's outbound httpx call waits up to 30s, freezing the
entire webhook handler. This made the image-selection step take
30+ seconds in the worst case.

**Fix:** `openwa_client._post` now uses `httpx.Timeout(connect=5s,
read=15s, write=5s, pool=5s)`. Reference image sends in
`handle_interactive` are wrapped in try/except so a slow URL never
blocks the next step.

### Files changed
| File | Change |
|------|--------|
| `openwa/src/main.ts` | Added `json({limit:'15mb'})`, `urlencoded`, `raw` body parsers before helmet/CORS |
| `app/main.py` | Image detection via `data.type` + inline `data.media.data` base64 decode; non-image media reply; `@lid` chatId passthrough |
| `conversation/handlers.py` | Inline image bytes in `handle_image`; paginated menu via `menu_page`; `AWAITING_DECISION` numeric replies; `BOOKING_CONFIRMED`/`PROCESSING` recovery; `AWAITING_CHOICE` numeric+nav routing; menu-page reset on `try_another`/`back_to_menu` |
| `whatsapp/openwa_client.py` | `_to_chat_id` pass-through for `@lid`; `httpx.Timeout(5/15/5/5)` in `_post`; `send_image`/`send_image_base64` use flat DTO fields (`url`/`base64`/`mimetype`); paginated `_send_numbered_menu` (3 per page) + `_send_short_menu` |
| `ai/face_validator.py` | Rewritten: YuNet primary + 4-cascade Haar fallback + histogram equalisation + auto-download model + lower 4% threshold + edge-crop rejection |
| `ai/hair_mask.py` | Rewritten: YuNet primary + 4-cascade Haar fallback (shared `_get_yunet`/`_detect_face` pattern) |
| `app/models.py` | Added `menu_page: int = 0` to `UserSession` |
| `tests/test_face_validator.py` | 4 new tests (model loaded, solid image rejected, tiny image rejected, live face pass) |
| `scripts/setup_openwa.py` | Webhook secret backfill on existing webhooks that were created without a secret |
| `.env` | Removed duplicate OpenWA block; set `OPENWA_SESSION_ID=barber` |
