# Tasks: OpenWA Gateway Integration

- [x] 1. Clone OpenWA locally (engine pinned to `whatsapp-web.js` — only engine bundled in v0.1.6)
- [x] 2. Create `whatsapp/openwa_client.py` — REST API client
- [x] 3. Add `_handle_openwa_webhook()` to `app/main.py` — webhook endpoint
- [x] 4. Update `whatsapp/client.py` — swap Meta -> OpenWA when `USE_OPENWA=True`
- [x] 5. Update `app/config.py` — add OpenWA env vars
- [x] 6. Update `.env` / `.env.example` — add OpenWA config section
- [x] 7. Update `render.yaml` — add OpenWA env vars
- [x] 8. Make `setup-openwa.bat` idempotent + correct (use PowerShell `Set-Content`)
- [x] 9. Auto-detect mode in `start.bat`; add `start-openwa.bat` for one-command boot
- [x] 10. Update `stop.bat` to also kill OpenWA gateway and dashboard ports
- [x] 11. Live end-to-end test on real WhatsApp (requires user to scan QR in OpenWA dashboard)

## Round 2 — Payload fixes & live testing (2026-06-13)

- [x] 12. Fix `_handle_openwa_webhook` to detect images via `data.type` (not `data.hasMedia` which is Meta-only)
- [x] 13. Decode inline `data.media.data` (base64) in webhook payload — no separate `/api/media` download needed
- [x] 14. Fix `_to_chat_id` to pass through `@lid` chatIds (newer WhatsApp) instead of appending `@c.us`
- [x] 15. Upgrade face validator from Haar cascade to YuNet DNN (232 KB ONNX, auto-downloaded)
- [x] 16. Upgrade hair-mask face detector from Haar to YuNet (same model)
- [x] 17. Render menu as paginated 3-at-a-time numbered text with "more" / "back" navigation
- [x] 18. Add `menu_page` field to `UserSession` for page tracking
- [x] 19. Handle numeric replies in AWAITING_DECISION state (1 = confirm, 2 = try another)
- [x] 20. Handle recovery commands ("hi" / "menu" / "ابدأ") from BOOKING_CONFIRMED and PROCESSING
- [x] 21. Raise OpenWA body-parser limit from 100 KB to 15 MB (413 PayloadTooLarge on result images)
- [x] 22. Lower httpx timeout in `openwa_client._post` from 30s to 5s connect / 15s read
- [x] 23. Wrap reference-image send in try/except so slow URLs don't block the webhook handler
- [x] 24. Set webhook secret via PUT API (existing webhook had `secret: null`)
- [x] 25. Full end-to-end test: hi → menu → pick cut → send selfie → validate → swap → send result → decide → recover
