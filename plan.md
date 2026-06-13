# 📋 AI Barber WhatsApp Bot — Technical Plan

**Version:** 1.2  
**Created:** 2026-05-07  
**Last Updated:** 2026-05-08  
**Status:** 🧪 Test Phase (Free Tier)  
**Language:** Arabic (Egyptian dialect) — Backend in English  

---

## 1. Project Summary

A WhatsApp chatbot for barbershops that:
1. Displays an interactive haircut menu in Egyptian Arabic.
2. Accepts a customer selfie and validates image quality (single face, clear lighting).
3. Optionally analyzes face shape via AI and recommends a matching haircut.
4. Generates a **virtual try-on** image (hair swap) and shows the result.
5. Confirms a booking and notifies the barber via WhatsApp/webhook.
6. Stores **zero** customer images (privacy-first).

---

## 2. Architecture Overview

```
┌──────────────┐        ┌───────────────────┐        ┌──────────────────┐
│  Customer     │  WA    │  WhatsApp Cloud   │ Webhook │  Backend Server  │
│  (WhatsApp)   │◄─────►│  API (Free Tier)  │────────►│  (Python/FastAPI)│
└──────────────┘        └───────────────────┘        └───────┬──────────┘
                                                             │
                         ┌───────────────────────────────────┼───────────────┐
                         │                                   │               │
                    ┌────▼─────┐    ┌─────────────┐    ┌────▼─────┐   ┌────▼──────┐
                    │ Face     │    │ Hair Swap   │    │ Booking  │   │ Barber    │
                    │ Analysis │    │ Engine      │    │ State    │   │ Notifier  │
                    │ (Vision) │    │ (Replicate) │    │ Machine  │   │ (Webhook) │
                    └──────────┘    └─────────────┘    └──────────┘   └───────────┘
```

---

## 3. Tech Stack — Free / Test Phase (Updated May 2026)

> ⚠️ **Note:** Gemini 2.x is deprecated (EOL mid-2026). This plan uses **Gemini 3 Flash Preview** (`gemini-3-flash-preview`), the latest free-tier model as of 2026.
> WhatsApp Cloud API uses conversation-based pricing (24-hour window). Test numbers are free for up to 5 verified recipients.

| Layer | Technology | Why Free? |
|---|---|---|
| **Runtime** | Python 3.12 + FastAPI | Open-source |
| **WhatsApp API (Primary)** | **OpenWA Gateway** (`https://github.com/rmyndharis/OpenWA`) running locally (port 2785 API / 2886 dashboard) | Self-hosted, no Meta account, no URL rotates between restarts. Uses bundled `whatsapp-web.js` engine. |
| **WhatsApp API (Fallback)** | Meta WhatsApp Cloud API v23.0+ | Conversation-based pricing. Kept as fallback for users who already have a Meta app. |
| **Hosting** | Local development (no tunnel needed in OpenWA mode) | $0 |
| **Face Analysis** | **Google Gemini 3 Flash Preview** (`gemini-3-flash-preview`, free tier via Google AI Studio) | Free tier: 15 RPM, 1M input tokens, 64k output tokens — sufficient for single-salon testing |
| **Hair Swap / Try-On (Primary)** | **Cloudflare Workers AI inpainting** (`@cf/runwayml/stable-diffusion-v1-5-inpainting`) | Free tier: 10k neurons/day (~100-200 images/day). Face-preserving via local OpenCV hair mask. |
| **Hair Swap / Try-On (Quality Fallback)** | Replicate FLUX Kontext Pro / change-haircut app | ~$0.04/image |
| **Image Validation** | OpenCV Haar cascade (local, offline) | Fully free, runs on-device |
| **Conversation State** | In-memory dict / SQLite | No external DB cost |
| **Barber Notification** | OpenWA / WhatsApp Cloud API or Telegram Bot API (free) | $0 |
| **Scheduler/Queue** | Python `asyncio` tasks | Built-in |

---

## 4. Module Breakdown

### 4.1 `app/` — Core Application

```
barber/
├── app/
│   ├── main.py                 # FastAPI app entry-point, webhook receiver
│   ├── config.py               # Environment variables & secrets
│   ├── models.py               # Pydantic models for messages, bookings
│   └── dependencies.py         # Shared dependencies (HTTP clients, etc.)
│
├── whatsapp/
│   ├── client.py               # WhatsApp Cloud API wrapper (send/receive)
│   ├── interactive.py          # Build interactive lists, buttons, templates
│   └── media.py                # Download/upload media (images)
│
├── ai/
│   ├── face_validator.py       # MediaPipe: single-face check, quality gate
│   ├── face_analyzer.py        # Gemini Vision: detect face shape
│   └── hair_swap.py            # Replicate / HuggingFace: virtual try-on
│
├── conversation/
│   ├── state_machine.py        # FSM: tracks user state (WELCOME → MENU → SELFIE → RESULT → BOOKING)
│   ├── handlers.py             # Message handlers per state
│   └── scripts.py              # All Arabic response templates
│
├── booking/
│   ├── manager.py              # Create/confirm booking records
│   └── notifier.py             # Webhook/WA message to barber
│
├── data/
│   ├── haircuts.json           # Haircut catalog (name, image_url, tags)
│   └── face_shape_map.json     # Face-shape → recommended haircuts mapping
│
├── tests/
│   ├── test_face_validator.py
│   ├── test_state_machine.py
│   └── test_whatsapp_client.py
│
├── .env.example                # Template for secrets
├── requirements.txt
├── Dockerfile
├── barbe-prd.md
├── plan.md
└── roadmap.md
```

### 4.2 Module Responsibilities

| Module | Responsibility |
|---|---|
| `whatsapp/client.py` | Authenticate with Meta Cloud API, send text/image/interactive messages, receive webhooks |
| `whatsapp/interactive.py` | Build Interactive List (haircut menu) and Reply Button payloads |
| `whatsapp/media.py` | Download customer selfie from WA CDN, upload result image |
| `ai/face_validator.py` | Run MediaPipe face detection → reject if 0 or 2+ faces, or face too small |
| `ai/face_analyzer.py` | Send image to Gemini Vision with hidden prompt → return face shape string |
| `ai/hair_swap.py` | Call Replicate/HF API with (selfie + haircut reference) → return composited image |
| `conversation/state_machine.py` | Per-user FSM with states: `WELCOME`, `AWAITING_CHOICE`, `AWAITING_SELFIE`, `PROCESSING`, `AWAITING_DECISION`, `BOOKING_CONFIRMED` |
| `conversation/handlers.py` | Route incoming messages to correct handler based on current state |
| `conversation/scripts.py` | All Arabic text constants (Egyptian dialect), centralized for easy editing |
| `booking/manager.py` | Store booking in SQLite (customer phone, haircut, timestamp) |
| `booking/notifier.py` | Send booking details to barber's WhatsApp number |

---

## 5. Conversation State Machine

```
                    ┌─────────────┐
                    │   WELCOME   │
                    └──────┬──────┘
                           │ (show menu)
                    ┌──────▼──────┐
                    │ AWAITING    │
                    │ CHOICE      │
                    └──┬───────┬──┘
          (direct pick)│       │("سيب الطلعة دي عليا")
                       │       │
                    ┌──▼───────▼──┐
                    │  AWAITING   │
                    │  SELFIE     │◄────── (bad image → loop)
                    └──────┬──────┘
                           │ (valid image)
                    ┌──────▼──────┐
                    │ PROCESSING  │  (AI pipeline: validate → analyze → swap)
                    └──────┬──────┘
                           │ (result image sent)
                    ┌──────▼──────┐
                    │ AWAITING    │
                    │ DECISION    │
                    └──┬───────┬──┘
          ("اعتمد واحجز")│    │("جرب قصة تانية")
                         │    │
                  ┌──────▼┐  ┌▼──────────┐
                  │BOOKING│  │ AWAITING   │
                  │CONFIRM│  │ CHOICE     │ (back to menu)
                  └───────┘  └────────────┘
```

---

## 6. API Integration Details

### 6.1 WhatsApp Transport (OpenWA Gateway — Primary)

- **Setup:** Run `setup-openwa.bat` → `start-openwa.bat` → open dashboard at `http://localhost:2886` → scan QR code once.
- **Webhook:** OpenWA forwards `message.received` and `session.status` events to `http://localhost:8000/webhook` (a stable, local URL — no tunneling, no random `*.trycloudflare.com` addresses, no certificate warnings).
- **Auth:** `X-API-Key` header on every OpenWA call, HMAC-SHA256 signature on every webhook.
- **Why OpenWA:** runs entirely on localhost, no Meta account required, no URL rotates between restarts, no cost. The bundled engine in v0.1.6 is `whatsapp-web.js` (Baileys is listed as "future" in the example env). The `start.bat` script auto-detects whether OpenWA keys are present and falls back to the Meta path otherwise.

### 6.1b WhatsApp Cloud API (Legacy Fallback)

Used only when `OPENWA_API_KEY` and `OPENWA_SESSION_ID` are empty.

- **Setup:** Create Meta Developer account → Create App → Add WhatsApp product → Get test phone number.
- **Webhook:** FastAPI `POST /webhook` receives all incoming messages.
- **Verification:** `GET /webhook` with hub challenge for Meta verification.
- **Pricing (as of 2026 — conversation-based model):**
  - A conversation is a 24-hour messaging window initiated by either the business or the customer. Pricing varies by conversation type and country.
  - ✅ **Customer-initiated (Service) conversations:** Free within 24h window after customer sends first message.
  - ✅ **Free Entry Point (FEP):** If customer comes from Click-to-WhatsApp ad or Facebook CTA, 72h free window.
  - 💰 **Business-initiated conversations (Marketing/Utility/Auth):** Paid per conversation, varies by country.
  - 🧪 **Test phase:** Using test numbers with up to 5 verified recipients — effectively free for development.
- **Strategy for free testing:** Since our bot is customer-initiated (customer sends "hi" first), all replies within 24h are **free**. We avoid sending template messages during test phase.

### 6.2 Face Shape Analysis (Gemini 3 Flash Preview — Free Tier)

```python
# Hidden system prompt (never exposed to user)
FACE_ANALYSIS_PROMPT = """
Analyze this photo and determine the person's face shape.
Output ONLY one of: oval, round, square, heart, oblong, diamond.
No explanation, no extra text.
"""
```

- **Model:** `gemini-3-flash-preview` via Google AI Studio (latest 2026 free-tier model, replaces deprecated 2.x series).
- **Free Tier:** Rate limits per Google Cloud Project (RPM, TPM, RPD, IPM). Check exact quotas in AI Studio dashboard.
- **Sufficient for testing:** Single barbershop = few dozen requests/day, well within free tier.
- **⚠️ Note:** Free tier data may be used by Google to improve products. Move to paid tier for production.
- **Fallback:** If Gemini is down or rate-limited, default to showing all haircuts (graceful degradation).
- **Error handling:** Implement exponential backoff with jitter for 429 errors.

### 6.3 Virtual Try-On / Hair Swap

**Option A — Cloudflare Workers AI (Primary, Free):**
- Model: `@cf/runwayml/stable-diffusion-v1-5-inpainting` for hair-region editing.
- **Free allocation:** 10,000 Neurons/day (~100–200 images/day depending on resolution).
- A local hair mask is generated from the selfie using OpenCV, masking only the hair region so the face is preserved.
- Cost after free tier: ~$0.011 per 1,000 Neurons (effectively a fraction of a cent per image).

**Option B — Replicate SDXL Inpainting (Fallback):**
- Model: `lucataco/sdxl-inpainting`.
- Cost: ~$0.0024 per image.
- Uses the same hair mask as Cloudflare; better quality if Cloudflare is insufficient.

**Option C — Replicate FLUX Kontext (Quality Fallback):**
- Model: `black-forest-labs/flux-kontext-pro` or the dedicated `flux-kontext-apps/change-haircut`.
- Cost: ~$0.04 per image.
- Text-guided editing; may alter pose/clothing but produces high-quality hairstyles.

**Option D — HuggingFace Inference API (Fallback):**
- Free tier: rate-limited (few hundred requests/hour), designed for prototyping.
- Models: FLUX variants, Stable Diffusion XL inpainting, or community hair-swap models.
- **⚠️ Note:** Expect cold starts and queuing during high-demand periods.

### 6.4 Face Validation (MediaPipe — Fully Offline)

```python
# Runs locally, zero API cost
import mediapipe as mp
face_detection = mp.solutions.face_detection.FaceDetection(min_detection_confidence=0.7)
```

- **Checks:** Single face detected, face bounding box > 15% of image area, confidence > 0.7.

---

## 7. Data Models

### 7.1 Haircut Catalog (`data/haircuts.json`)

```json
[
  {
    "id": "fade_classic",
    "name_ar": "فيد كلاسيك",
    "name_en": "Classic Fade",
    "image_url": "https://example.com/haircuts/fade_classic.jpg",
    "tags": ["oval", "round", "square"],
    "price_egp": 80,
    "description_ar": "قصة الفيد الكلاسيكية الأنيقة"
  }
]
```

### 7.2 User Session State

```python
@dataclass
class UserSession:
    phone: str
    state: ConversationState
    selected_haircut: Optional[str] = None
    face_shape: Optional[str] = None
    selfie_media_id: Optional[str] = None
    result_image_url: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    attempts: int = 0  # Track image validation retries
```

### 7.3 Booking Record

```python
@dataclass
class Booking:
    id: str  # UUID
    customer_phone: str
    haircut_id: str
    face_shape: Optional[str]
    confirmed_at: datetime
    notified_barber: bool = False
```

---

## 8. Security & Privacy

| Concern | Solution |
|---|---|
| Customer selfies | Process in-memory only. Never write to disk or DB. Delete buffer after API response. |
| Privacy notice | Auto-send: *"متقلقش، صورتك في أمان وبتتمسح فوراً 🔒"* before processing |
| API keys | `.env` file, never committed. `.gitignore` enforced. |
| WhatsApp token | Rotate every 24h during test phase (Meta enforces this). |
| Rate limiting | Max 3 image attempts per session. Max 10 sessions/hour per number. |

---

## 9. Performance Targets

| Metric | Target | How |
|---|---|---|
| Image validation | < 1 second | Local MediaPipe (no network) |
| Face shape analysis | 2–4 seconds | Gemini 3 Flash Preview (free tier, optimized for speed) |
| Hair swap generation | 10–20 seconds | Replicate/HF cold-start varies; send "processing…" message |
| Total E2E (selfie → result) | < 25 seconds | Pipeline: validate (1s) → analyze (3s) → swap (15s) → send (1s) |
| Webhook response | < 200ms | Acknowledge webhook immediately, process async |

---

## 10. Cost Analysis — Test Phase

| Item | Cost | Notes |
|---|---|---|
| WhatsApp Cloud API | **$0** | Customer-initiated msgs free in 24h window. Test numbers for dev. |
| Gemini 3 Flash Preview | **$0** | Free tier via Google AI Studio (rate-limited, data may be used by Google) |
| Replicate hair swap | **~$0** | "Try for Free" models + initial prepaid credits. Budget ~$5-10 for extended testing. |
| HuggingFace (fallback) | **$0** | Free tier for prototyping (few hundred req/hr) |
| MediaPipe validation | **$0** | Fully offline, no API calls |
| Hosting (Render) | **$0** | Free tier deployment |
| Domain | Not needed | Test phase only |
| **Total** | **~$0–$10** | Effectively free. Only Replicate may need small prepaid credit after free runs. |

---

## 11. Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| Hair swap quality is poor | Users lose trust | Test multiple FLUX/inpainting models; allow manual "try another" loop |
| WhatsApp 24h window expires | Can't reply to customer for free | Process images immediately; send results within minutes, not hours |
| Gemini 3 Flash Preview free tier rate limit (429 errors) | Face analysis fails | Exponential backoff + fallback to showing all haircuts |
| Replicate free runs exhausted | Hair swap stops working | Switch to HuggingFace free tier or AILab Tools trial |
| Gemini 3 Flash Preview deprecated in future | Need to migrate | Monitor Google announcements; plan migration to next-gen Gemini model |
| Free tier data used by Google | Privacy concern | Acceptable for test phase; move to paid tier for production |
| Customer sends inappropriate images | Bot must not process | MediaPipe + Gemini content filter as double gate |

---

## 12. Definition of Done (Test Phase)

- [ ] Bot responds to "hi" with welcome message + interactive menu
- [ ] Customer can pick a haircut from the list
- [ ] Customer can request AI recommendation ("سيب الطلعة دي عليا")
- [ ] Bot validates selfie (single face, clear)
- [ ] Bot analyzes face shape (when AI recommendation selected)
- [ ] Bot generates and sends virtual try-on image
- [ ] Customer can approve or try another haircut
- [ ] Booking confirmation sent to customer
- [ ] Barber receives notification with booking details
- [ ] Zero images stored after processing
- [ ] All responses in Egyptian Arabic dialect
- [ ] End-to-end flow completes in < 25 seconds
