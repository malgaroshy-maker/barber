# Plan: OpenWA Gateway Integration

## Tasks
1. Clone OpenWA locally, configure engine (whatsapp-web.js — only engine bundled in v0.1.6)
2. Create `whatsapp/openwa_client.py` — REST API client
3. Add `_handle_openwa_webhook()` to `app/main.py` — webhook endpoint
4. Update `whatsapp/client.py` — routes to OpenWA if `USE_OPENWA=True`, else Meta API
5. Update `app/config.py` — add OpenWA env vars and `USE_OPENWA` flag
6. Update `.env` / `.env.example` — add OpenWA config section
7. Update `render.yaml` — add OpenWA env vars
8. Auto-detect mode in `start.bat`; provide `start-openwa.bat` for one-command boot
9. End-to-end test the local pipeline (both modes)

## Dependencies
- OpenWA running locally on port 2785 (Node.js 22 LTS)
- Session created and QR scanned with WhatsApp
- API key generated from dashboard
- Both bot and OpenWA on the same machine (no tunneling required)

## Architecture
```
+-------------------------+        +----------------------+        +-------------------+
|  Customer WhatsApp app  | <----> |  OpenWA Gateway      | <----> |  Python FastAPI    |
|  (phone)               |        |  localhost:2785      |        |  localhost:8000    |
+-------------------------+        |  whatsapp-web.js      |        |  /webhook          |
                                    |  SQLite + local       |        |  AI Hair Swap      |
                                    +----------------------+        +-------------------+
```

- No tunneling, no random URLs, no certificate warnings.
- OpenWA dashboard (http://localhost:2886) is used once to:
  - Create API key
  - Create + start session "barber-bot" and scan QR
  - Create webhook -> http://localhost:8000/webhook (events: message.received, session.status; secret: matches OPENWA_WEBHOOK_SECRET)

## Why this solves the earlier problems
- Cloudflare quick-tunnel (`*.trycloudflare.com`) issued a new URL every restart
  and printed `Cannot determine default origin certificate path` errors.
- With OpenWA, the bot and the WhatsApp gateway both run on localhost;
  the webhook URL never changes and there is no public tunnel involved.

## Risks
- OpenWA `whatsapp-web.js` engine still needs a Chromium binary, but it runs headless
  on Windows using the bundled Puppeteer args.
- Webhook secret must match between OpenWA dashboard and `OPENWA_WEBHOOK_SECRET`.
- Base64 image size limit on OpenWA: keep result images under ~5 MB.

## Mode auto-detection (`start.bat`)
- If `OPENWA_API_KEY` and `OPENWA_SESSION_ID` are non-empty -> OpenWA mode.
- Otherwise -> legacy Meta Cloud API + Cloudflare Tunnel mode (kept as a fallback).
