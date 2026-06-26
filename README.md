# AI Barber WhatsApp Bot

**Arabic-first WhatsApp bot for haircut virtual try-on — bring your own hair catalogue.**

---

## 🇬🇧 English

### What is it?

A WhatsApp bot that lets customers browse a haircut catalogue, send a selfie, and receive a photorealistic virtual try-on — all within WhatsApp. No app download, no Meta Cloud API.

### Quick Start

```bash
# 1. Clone
git clone https://github.com/malgaroshy-maker/barber.git
cd barber

# 2. Python env
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 3. Install OpenWA Gateway
setup-openwa.bat

# 4. Configure
copy .env.example .env
# Edit .env with your Cloudflare account ID + API token

# 5. Generate your catalogue (or add your own images to static/)
python scripts\generate_reference_images.py

# 6. Start
start-openwa.bat
```

Open http://localhost:2886 to scan the WhatsApp QR code.

### Customize

- **Catalogue**: Edit `data/haircuts.json` — add/remove cuts, change names, swap images
- **Prompts**: Edit `HAIRCUT_PROMPTS` in `ai/hair_swap.py` — controls the inpainting style
- **Hair mask**: Tweak `ai/hair_mask.py` — adjust mask region and blur for different head shapes
- **Face validator**: `ai/face_validator.py` — change confidence thresholds or swap detector model
- **WhatsApp transport**: `whatsapp/openwa_client.py` — customize message formatting, pagination, delays
- **Conversation flow**: `conversation/handlers.py` — modify the state machine, add new steps

### Project Structure

```
barber/
├── ai/                  # Face detection, hair mask, swap, color match
├── app/                 # FastAPI webhook server
├── conversation/        # State machine + message handlers
├── data/                # Haircut catalogue JSON
├── scripts/             # Setup & image generation
├── static/              # Reference images (generate or add your own)
├── whatsapp/            # OpenWA + Meta client
├── .env.example         # Environment template
├── requirements.txt     # Python deps
└── start-openwa.bat     # One-command startup
```

---

## 🇸🇦 العربية

### ما هو؟

بوت واتساب يتيح للعملاء تصفح كتالوج قصات شعر، إرسال سيلفي، والحصول على تجربة افتراضية للقصة — كل ذلك داخل واتساب. بدون تحميل تطبيق، بدون Meta API.

### البدء السريع

```bash
# 1. انسخ المشروع
git clone https://github.com/malgaroshy-maker/barber.git
cd barber

# 2. بيئة بايثون
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 3. ثبّت OpenWA Gateway
setup-openwa.bat

# 4. الإعدادات
copy .env.example .env
# عدّل .env بمعرف حساب Cloudflare ومفتاح API

# 5. ولّد صور الكتالوج (أو أضف صورك الخاصة إلى static/)
python scripts\generate_reference_images.py

# 6. شغّل
start-openwa.bat
```

افتح http://localhost:2886 لمسح كود QR الخاص بواتساب.

### التخصيص

- **الكتالوج**: عدّل `data/haircuts.json` — أضف/احذف قصات، غيّر الأسماء والصور
- **التوليد بالذكاء الاصطناعي**: عدّل `ai/hair_swap.py` — تحكم في أسلوب معالجة الشعر
- **قناع الشعر**: `ai/hair_mask.py` — اضبط مساحة القناع لأنواع الوجوه المختلفة
- **بوت المحادثة**: `conversation/handlers.py` — غيّر تدفق المحادثة والخطوات
- **النقل**: `whatsapp/openwa_client.py` — خصص تنسيق الرسائل والترقيم

### هيكل المشروع

```
barber/
├── ai/                  # كشف الوجوه، قناع الشعر، المعالجة
├── app/                 # خادم FastAPI
├── conversation/        # حالات المحادثة ومعالجة الرسائل
├── data/                # ملف الكتالوج JSON
├── scripts/             # أدوات التنصيب والتوليد
├── static/              # صور القصات المرجعية
├── whatsapp/            # عميل واتساب
├── .env.example         # قالب الإعدادات
├── requirements.txt     # متطلبات بايثون
└── start-openwa.bat     # تشغيل بنقرة واحدة
```
