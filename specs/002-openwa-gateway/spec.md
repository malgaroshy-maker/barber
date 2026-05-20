# Spec: OpenWA Gateway Integration

## Problem
Replace Meta Cloud WhatsApp API with self-hosted OpenWA gateway for free WhatsApp messaging.

## Solution
- Deploy OpenWA locally with Baileys engine (no Chromium, ~50MB RAM)
- Create Python OpenWA client to replace Meta API calls
- Add webhook endpoint for incoming messages
- Keep existing AI hair swap logic unchanged

## Scope
- `whatsapp/openwa_client.py` — new REST API client for OpenWA
- `app/webhook.py` — webhook endpoint for incoming messages
- `whatsapp/client.py` — swap Meta API → OpenWA
- `app/config.py` — add OpenWA env vars
- `.env` / `.env.example` — add OpenWA config
- `render.yaml` — add OpenWA env vars

## Out of Scope
- OpenWA deployment (user runs locally)
- Dashboard configuration
- Multi-session support
- PostgreSQL/Redis setup

## Architecture
```
User ↔ WhatsApp ↔ OpenWA (localhost:2785) ↔ Webhook → Python Bot
                                            ↓
                                      AI Hair Swap
                                            ↓
                                      OpenWA API → Send Image
```

## API Mapping
| Current (Meta) | New (OpenWA) |
|----------------|--------------|
| `POST graph.facebook.com/.../messages` | `POST /sessions/{id}/messages/send-text` |
| Media upload + send | `POST /sessions/{id}/messages/send-image` (base64) |
| Webhook from Meta | Webhook from OpenWA (`message.received`) |

## OpenWA Setup (User)
```bash
git clone https://github.com/rmyndharis/OpenWA.git
cd OpenWA
npm install
# Set ENGINE_TYPE=baileys in .env
npm run dev
# Create session, scan QR, get API key
```
