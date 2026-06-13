# Spec: OpenWA Gateway Integration

## Problem
Replace Meta Cloud WhatsApp API with self-hosted OpenWA gateway so the bot works locally without public tunnels, random trycloudflare.com URLs, or Meta webhook configuration that breaks on every restart.

## Solution
- Run OpenWA locally (`localhost:2785` API + `localhost:2886` dashboard) using the bundled `whatsapp-web.js` engine (only engine available in OpenWA v0.1.6).
- Create a thin Python OpenWA REST client (`whatsapp/openwa_client.py`) that mirrors the existing Meta API surface (`send_text`, `send_image`, `send_image_base64`, `send_interactive_buttons`, `download_media`).
- Add a webhook handler in `app/main.py` for the OpenWA `message.received` and `session.status` event formats.
- Route all `whatsapp/client.py` calls through OpenWA when `USE_OPENWA=True`, otherwise fall back to the Meta Cloud API.
- Make `start.bat` auto-detect the mode; ship a dedicated `start-openwa.bat` for one-command boot of the whole stack.

## Scope
- `whatsapp/openwa_client.py` — new REST API client for OpenWA
- `app/main.py` — new `_handle_openwa_webhook()`
- `whatsapp/client.py` — route through OpenWA when configured
- `app/config.py` — new env vars + `USE_OPENWA` flag
- `app/dependencies.py` — unchanged
- `.env` / `.env.example` — OpenWA config section
- `render.yaml` — OpenWA env vars
- `start.bat` / `start-openwa.bat` / `stop.bat` — auto-detect and clean shutdown
- `setup-openwa.bat` — clone, install, build, patch env

## Out of Scope
- OpenWA production deployment (VPS / Oracle Cloud free tier is a follow-up)
- PostgreSQL / Redis / S3 storage (SQLite + local storage is enough for test phase)
- Multi-session support
- OpenWA dashboard UI changes (user configures via web UI)

## OpenWA Setup (one time, done by the user)
1. Run `setup-openwa.bat` — clones the repo, installs deps, builds, patches `.env`.
2. Start everything with `start-openwa.bat` (or `start.bat` after the keys are filled in).
3. Open `http://localhost:2886`, then:
   - Create an API key (Settings -> API Keys)
   - Create a session named `barber-bot`, start it, scan the QR with WhatsApp
   - Copy the API key into the main `.env`:
     - `OPENWA_API_KEY=...`
     - `OPENWA_SESSION_ID=barber-bot`
   - Create a webhook (Webhooks tab):
     - URL: `http://localhost:8000/webhook`
     - Events: `message.received`, `session.status`
     - Secret: `barber-webhook-secret` (must match `OPENWA_WEBHOOK_SECRET`)
4. Restart with `start-openwa.bat`. Send "hi" to the linked WhatsApp number.

## API Mapping
| Meta Cloud API | OpenWA |
|----------------|--------|
| `POST graph.facebook.com/.../messages` | `POST /sessions/{id}/messages/send-text` |
| Media upload + send | `POST /sessions/{id}/messages/send-image` (base64) |
| Webhook from Meta | Webhook from OpenWA (`message.received`) |
| Phone number -> chatId | Auto-converted: `1234567890` -> `1234567890@c.us` |
