# Plan: OpenWA Gateway Integration

## Tasks
1. Clone OpenWA locally, configure Baileys engine
2. Create `whatsapp/openwa_client.py` — REST API client
3. Create `app/webhook.py` — webhook endpoint
4. Update `whatsapp/client.py` — swap Meta → OpenWA
5. Update `app/config.py` — add OpenWA env vars
6. Update `.env` / `.env.example` — add OpenWA config
7. Update `render.yaml` — add OpenWA env vars
8. Test end-to-end flow

## Dependencies
- OpenWA running locally on port 2785
- Session created and QR scanned
- API key generated

## Risks
- OpenWA Baileys engine may be less stable than whatsapp-web.js
- Webhook URL must be reachable from local OpenWA (use ngrok or localhost)
- Base64 image size limits (OpenWA supports <5MB base64)
