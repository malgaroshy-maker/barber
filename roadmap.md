# 🗺️ AI Barber WhatsApp Bot — Development Roadmap

**Project:** AI Barber WhatsApp Bot  
**Start Date:** 2026-05-08  
**Current Phase:** 🧪 Test Phase (Free Tier)  

---

## Phase Overview

```
Phase 0          Phase 1           Phase 2           Phase 3           Phase 4
Foundation       Core Bot          AI Pipeline       Booking &         Polish &
& Setup          Logic             Integration       Notifications     Launch
────────►       ────────►        ────────►        ────────►        ────────►
 3 days           5 days            5 days            3 days            3 days
                                                                     ┌──────────┐
                                                                     │ Phase 5  │
                                                                     │ Scale &  │
                                                                     │ Monetize │
                                                                     │ (Future) │
                                                                     └──────────┘
```

**Total Estimated Duration:** ~19 working days (~4 weeks)

---

## 📅 Phase 0 — Foundation & Environment Setup
**Duration:** 3 days  
**Goal:** Project skeleton, all accounts created, dev environment ready.

### Tasks

| # | Task | Details | Status |
|---|---|---|---|
| 0.1 | Initialize Python project | `pyproject.toml`, virtual env, folder structure from `plan.md` | ✅ |
| 0.2 | Create Meta Developer account | Register at developers.facebook.com, create app | ✅ |
| 0.3 | Set up WhatsApp Cloud API | Add WhatsApp product to Meta app, get test phone number, generate temp token | ✅ |
| 0.4 | Get Gemini API key | Sign up at aistudio.google.com, generate **Gemini 3 Flash Preview** free API key | ✅ |
| 0.5 | Get Replicate API key | Sign up at replicate.com, explore "Try for Free" models | ✅ |
| 0.6 | Set up `.env` file | All API keys, phone numbers, webhook verify token | ✅ |
| 0.7 | Set up FastAPI skeleton | `main.py` with health check endpoint, CORS, error handling | ✅ |
| 0.8 | Set up Cloudflare tunnel | For local testing with WhatsApp webhooks (ngrok IP blocked) | ✅ |
| 0.9 | Configure webhook with Meta | Register cloudflare URL as webhook endpoint, verify challenge | ✅ |
| 0.10 | Create `.gitignore` | Exclude `.env`, `__pycache__`, venv, IDE files | ✅ |
| 0.11 | Write `requirements.txt` | FastAPI, uvicorn, httpx, mediapipe, Pillow, python-dotenv, google-genai | ✅ |

### Deliverables
- ✅ FastAPI server running locally
- ✅ Webhook verified by Meta
- ✅ Bot can receive a "hi" message and log it

---

## 📅 Phase 1 — Core Bot Logic & Conversation Flow
**Duration:** 5 days  
**Goal:** Full conversation state machine, interactive menu, Arabic scripts.

### Tasks

| # | Task | Details | Status |
|---|---|---|---|
| 1.1 | Build WhatsApp client wrapper | `whatsapp/client.py` — send text, image, interactive messages | ✅ |
| 1.2 | Build Interactive Message builder | `whatsapp/interactive.py` — construct List & Button payloads | ✅ |
| 1.3 | Create haircut catalog | `data/haircuts.json` — 6-8 haircuts with names (AR/EN), tags, prices | ✅ |
| 1.4 | Create face-shape mapping | `data/face_shape_map.json` — map each face shape to recommended haircuts | ✅ |
| 1.5 | Implement FSM | `conversation/state_machine.py` — all states from plan.md diagram | ✅ |
| 1.6 | Write all Arabic scripts | `conversation/scripts.py` — every bot response in Egyptian dialect | ✅ |
| 1.7 | Implement message handlers | `conversation/handlers.py` — route by state + message type | ✅ |
| 1.8 | Handle fallback/error messages | Unknown input → friendly redirect to menu | ✅ |
| 1.9 | Implement media download | `whatsapp/media.py` — download selfie from WA CDN using media ID | ✅ |
| 1.10 | Unit tests for FSM | Test all state transitions, edge cases | ⬜ |

### Deliverables
- ✅ Bot sends welcome message with interactive haircut menu
- ✅ User can select a haircut or request AI recommendation
- ✅ Bot asks for selfie and waits for image
- ✅ Bot handles text fallback gracefully
- ✅ All responses in Egyptian Arabic

---

## 📅 Phase 2 — AI Pipeline Integration
**Duration:** 5 days  
**Goal:** Image validation, face analysis, and hair swap working end-to-end.

### Tasks

| # | Task | Details | Status |
|---|---|---|---|
| 2.1 | Implement face validator | `ai/face_validator.py` — MediaPipe face detection, single-face check | ✅ |
| 2.2 | Test validator with edge cases | Multiple faces, no face, blurry, side profile, sunglasses | ✅ |
| 2.3 | Implement face shape analyzer | `ai/face_analyzer.py` — **Gemini 3 Flash Preview** Vision API call with hidden prompt | ✅ |
| 2.4 | Test analyzer accuracy | Test with known face shapes, verify correct classification | ✅ |
| 2.5 | Implement hair swap engine | `ai/hair_swap.py` — Replicate API (FLUX-based models) integration | ⬜ |
| 2.6 | Create reference haircut images | Prepare high-quality reference images for each haircut in catalog | ⬜ |
| 2.7 | Test hair swap quality | Run 10-15 test swaps, evaluate quality, tune parameters | ⬜ |
| 2.8 | Build AI pipeline orchestrator | Chain: validate → analyze (optional) → swap → return result | ✅ |
| 2.9 | Add "processing" feedback | Send "ثواني بحلل..." message while AI processes | ✅ |
| 2.10 | Add privacy notice | Send "صورتك في أمان 🔒" before processing | ✅ |
| 2.11 | Implement image cleanup | Ensure selfie bytes are deleted from memory after processing | ✅ |
| 2.12 | Add HuggingFace fallback | If Replicate fails/exhausted, fall back to HF Inference API (free tier) | ⬜ |
| 2.14 | Evaluate AILab Tools | Test AILab Tools Hairstyle Changer API (7-day free trial) as alternative | ⬜ |
| 2.13 | Unit tests for AI modules | Mock API responses, test error handling | ⬜ |

### Deliverables
- ✅ Bad selfies are rejected with friendly Arabic message
- ✅ Face shape is detected correctly
- ✅ Virtual try-on image is generated and sent to user
- ✅ Processing takes < 25 seconds
- ✅ Images are never persisted

---

## 📅 Phase 3 — Booking System & Barber Notifications
**Duration:** 3 days  
**Goal:** Booking confirmation flow + barber gets notified.

### Tasks

| # | Task | Details | Status |
|---|---|---|---|
| 3.1 | Implement booking manager | `booking/manager.py` — create booking in SQLite | ⬜ |
| 3.2 | Create SQLite schema | Bookings table: id, phone, haircut, face_shape, timestamp, notified | ⬜ |
| 3.3 | Implement barber notifier | `booking/notifier.py` — send WA message to barber's number | ⬜ |
| 3.4 | Design barber notification format | Include: customer name/phone, haircut name, face shape, result image | ⬜ |
| 3.5 | Wire "اعتمد واحجز" button | Trigger booking creation + barber notification | ⬜ |
| 3.6 | Wire "جرب قصة تانية" button | Reset state to AWAITING_CHOICE, show menu again | ⬜ |
| 3.7 | Add booking confirmation message | Send customer confirmation with salon details | ⬜ |
| 3.8 | Handle duplicate bookings | Prevent double-booking from rapid button taps | ⬜ |
| 3.9 | Unit tests for booking flow | Test creation, notification, edge cases | ⬜ |

### Deliverables
- ✅ Customer can confirm booking after seeing try-on result
- ✅ Barber receives WhatsApp notification with all details
- ✅ Customer gets confirmation message
- ✅ Bookings are logged in SQLite

---

## 📅 Phase 4 — Polish, Testing & Soft Launch
**Duration:** 3 days  
**Goal:** End-to-end testing, bug fixes, deploy for real barber testing.

### Tasks

| # | Task | Details | Status |
|---|---|---|---|
| 4.1 | Full E2E test | Walk through entire flow on WhatsApp with test number | ⬜ |
| 4.2 | Test "try another" loop | Verify user can try multiple haircuts in one session | ⬜ |
| 4.3 | Test error recovery | Kill server mid-conversation → restart → graceful recovery | ⬜ |
| 4.4 | Test concurrent users | Simulate 3-5 users chatting simultaneously | ⬜ |
| 4.5 | Performance benchmarking | Measure actual E2E latency for 10 flows | ⬜ |
| 4.6 | Deploy to Render | Free tier deployment with environment variables (Railway free tier deprecated) | ⬜ |
| 4.7 | Update webhook URL | Point Meta webhook to production URL | ⬜ |
| 4.8 | Create Dockerfile | For consistent deployment | ⬜ |
| 4.9 | Add logging & monitoring | Structured logs for debugging production issues | ⬜ |
| 4.10 | Prepare demo video | Screen-record a full conversation flow | ⬜ |
| 4.11 | Barber onboarding | Set up barber's WhatsApp number, test notifications | ⬜ |

### Deliverables
- ✅ Bot deployed and accessible 24/7
- ✅ Real barber testing with 5 test customers
- ✅ All critical bugs fixed
- ✅ Demo video ready

---

## 📅 Phase 5 — Scale & Monetize (Future — Post Test Phase)
**Duration:** Ongoing  
**Goal:** Graduate from free tier, onboard paying barbershops.

> [!NOTE]
> This phase is planned for later. Documented here for vision clarity.

### Tasks

| # | Task | Details | Status |
|---|---|---|---|
| 5.1 | Migrate to official WhatsApp BSP | WATI, 360dialog, or similar. Unlocks unlimited numbers. | ⬜ |
| 5.2 | Add payment integration | Fawry or Vodafone Cash for optional pre-payment | ⬜ |
| 5.3 | Multi-salon support | Each barbershop gets its own catalog, barber number, branding | ⬜ |
| 5.4 | Admin dashboard (web) | Salon owners can manage haircuts, view bookings, analytics | ⬜ |
| 5.5 | Appointment scheduling | Time-slot based booking instead of walk-in only | ⬜ |
| 5.6 | Customer history | Return customers get personalized recommendations | ⬜ |
| 5.7 | Subscription pricing model | Monthly fee per salon (EGP 200-500/month) | ⬜ |
| 5.8 | Marketing landing page | Arabic landing page for acquiring salon clients | ⬜ |
| 5.9 | WhatsApp catalog integration | Use WA native product catalog for haircuts | ⬜ |
| 5.10 | Loyalty system | Return customer discounts, referral bonuses | ⬜ |

---

## 📊 Sprint Calendar View

```
Week 1  │ Phase 0 (3d) ──►│ Phase 1 starts (2d)
Week 2  │ Phase 1 continues (3d) ──►│ Phase 2 starts (2d)
Week 3  │ Phase 2 continues (3d) ──►│ Phase 3 (2d)
Week 4  │ Phase 3 (1d) ──►│ Phase 4 (3d) ──►│ 🚀 Soft Launch
```

---

## 🎯 Key Milestones

| Milestone | Target Date | Indicator |
|---|---|---|
| 🟢 **M0: Environment Ready** | Day 3 | Bot receives & logs WhatsApp messages |
| 🟢 **M1: Conversational Bot** | Day 8 | Full Arabic conversation flow without AI |
| 🟢 **M2: AI Pipeline Live** | Day 13 | Virtual try-on working end-to-end |
| 🟢 **M3: Booking System** | Day 16 | Barber receives booking notification |
| 🚀 **M4: Soft Launch** | Day 19 | Real barber testing with customers |
| 🏁 **M5: Production Ready** | TBD | Multi-salon, paid tier (Phase 5) |

---

## 💡 Dependencies & Blockers

| Dependency | Required By | Risk Level |
|---|---|---|
| Meta Developer account approval | Phase 0 | 🟡 Medium (can take 1-2 days) |
| WhatsApp Business verification | Phase 0 | 🟢 Low (test mode works immediately) |
| Haircut reference images | Phase 2 | 🟡 Medium (need quality photos from barber) |
| Barber cooperation for testing | Phase 4 | 🟡 Medium (need their number + availability) |
| Replicate "Try for Free" models | Phase 2 | 🟢 Low (free runs available, prepaid credits ~$5-10 for extended testing) |

---

## 🔄 Decision Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-07 | Use WhatsApp Cloud API directly (not BSP) | Conversation-based pricing, free within 24h customer-initiated window. Test numbers for dev. |
| 2026-05-07 | Use **Gemini 3 Flash Preview** for face analysis (not deprecated 2.x) | Latest free-tier model via AI Studio, fast responses |
| 2026-05-08 | Updated stack via Context7 verification | Corrected WhatsApp to conversation-based pricing, Gemini to `gemini-3-flash-preview`, Replicate to FLUX Schnell, Railway deprecated |
| 2026-05-07 | Use FLUX-based models on Replicate for hair swap | State-of-the-art quality, "Try for Free" models available |
| 2026-05-07 | HuggingFace Inference API as hair swap fallback | Free tier (few hundred req/hr), good for prototyping |
| 2026-05-07 | Use MediaPipe for image validation | Fully offline, zero cost, reliable |
| 2026-05-07 | SQLite for bookings (not Supabase) | Zero cost, sufficient for single-salon test |
| 2026-05-07 | Python + FastAPI (not Node.js) | Better AI/ML ecosystem, team familiarity |
| 2026-05-07 | Cash-only payments for test phase | Simplifies MVP, matches PRD requirement |

---

> [!IMPORTANT]
> **Test Phase Ground Rules:**
> - All services must be free-tier or use signup/trial credits.
> - Maximum 5 test phone numbers (Meta limit).
> - Customer-initiated conversations only (free within 24h window).
> - Process AI results quickly — don't let the 24h reply window expire.
> - Free tier AI data may be used by providers to improve their models — acceptable for test phase.
> - Focus on proving the AI try-on concept works before investing in paid infrastructure.
> - Collect feedback from 10-15 real test users before graduating to Phase 5.
