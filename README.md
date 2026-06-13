# AI Barber WhatsApp Bot 🤖✂️

**Smart Haircut Recommendation & Virtual Try-On via WhatsApp**

---

## 🇬🇧 English

### What is it?

AI Barber is a WhatsApp bot that lets customers browse a catalogue of 34 trending men's haircuts, send a selfie, and receive a photorealistic virtual try-on of their chosen haircut — all within WhatsApp. No app download required.

### Features

- **Visual Catalogue**: Browse 34 trending haircuts with reference images, sent as a paginated carousel (3 per page)
- **AI Try-On**: Upload a selfie and see how the haircut looks on you using Cloudflare Workers AI inpainting
- **Face Detection**: YuNet DNN face validator ensures only valid selfies are processed
- **Smart Recommendations**: Optional AI face-shape analysis suggests the best haircut for your face
- **Booking Flow**: Confirm or retry after seeing the result
- **Bilingual**: Arabic-first UI with English fallback
- **Free Tier**: Runs entirely on free services (Cloudflare, OpenWA)

### Tech Stack

| Component | Technology |
|-----------|-----------|
| WhatsApp Transport | OpenWA Gateway (self-hosted, no Meta API) |
| Backend | Python 3.12 + FastAPI |
| Face Detection | OpenCV YuNet DNN + Haar cascade fallback |
| Hair Swap | Cloudflare Workers AI (SD 1.5 inpainting) |
| Catalogue Images | Cloudflare FLUX.2 (AI-generated) |
| Color Matching | OpenCV Lab histogram matching |

### Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/malgaroshy-maker/barber.git
cd barber

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 3. Set up OpenWA Gateway
setup-openwa.bat

# 4. Configure environment
copy .env.example .env
# Edit .env with your Cloudflare account ID and API token

# 5. Generate reference images (one-time)
python scripts\generate_reference_images.py

# 6. Start all services
start-openwa.bat
```

Then open http://localhost:2886 to scan the WhatsApp QR code.

### Project Structure

```
barber/
├── ai/                  # AI models (face detection, hair swap, color match)
├── app/                 # FastAPI application (webhook, config)
├── conversation/        # State machine & message handlers
├── data/                # Haircut catalogue (haircuts.json)
├── scripts/             # Setup & generation scripts
├── specs/               # Technical specifications
├── static/              # Reference haircut images
── tests/               # Unit tests
├── whatsapp/            # WhatsApp client (OpenWA + Meta)
├── .env.example         # Environment template
├── requirements.txt     # Python dependencies
└── start-openwa.bat     # One-command startup
```

### How It Works

1. User sends **"hi"** → Bot shows 3 haircut images with numbered captions
2. User replies **"1"**, **"2"**, or **"3"** → Bot asks for a selfie
3. User sends **selfie** → Face validation → AI inpainting → Result image
4. User sees the result → Replies **"1"** to confirm booking or **"2"** to try another

### Requirements

- Python 3.12+
- Node.js 18+ (for OpenWA Gateway)
- Cloudflare account (free tier)
- WhatsApp account (for QR scan)

---

## 🇸🇦 العربية

### ما هو؟

AI Barber هو بوت واتساب يتيح للعملاء تصفح كتالوج من 34 قصة شعر رجالية عصرية، إرسال صورة سيلفي، والحصول على تجربة افتراضية واقعية للقصة المختارة — كل ذلك داخل واتساب. بدون تحميل أي تطبيق.

### المميزات

- **كتالوج مرئي**: تصفح 34 قصة شعر عصرية مع صور مرجعية، تُرسل كصفحات (3 صور لكل صفحة)
- **تجربة افتراضية بالذكاء الاصطناعي**: ارفع سيلفي وشوف القصة عليك باستخدام Cloudflare Workers AI
- **كشف الوجوه**: YuNet DNN للتأكد من أن السيلفي صالح للمعالجة
- **توصيات ذكية**: تحليل شكل الوجه بالذكاء الاصطناعي يقترح أفضل قصة لك
- **تأكيد الحجز**:确认后 أو جرب قصة أخرى بعد رؤية النتيجة
- **ثنائي اللغة**: واجهة عربية أولاً مع دعم الإنجليزي
- **مجاني بالكامل**: يعمل على خدمات مجانية (Cloudflare, OpenWA)

### التقنيات المستخدمة

| المكوّن | التقنية |
|---------|---------|
| نقل واتساب | OpenWA Gateway (مستضاف محلياً، بدون Meta API) |
| الخلفية | Python 3.12 + FastAPI |
| كشف الوجوه | OpenCV YuNet DNN + Haar cascade |
| تبديل الشعر | Cloudflare Workers AI (SD 1.5 inpainting) |
| صور الكتالوج | Cloudflare FLUX.2 (مولّدة بالذكاء الاصطناعي) |
| مطابقة الألوان | OpenCV Lab histogram matching |

### البدء السريع

```bash
# 1. انسخ المشروع
git clone https://github.com/malgaroshy-maker/barber.git
cd barber

# 2. أنشئ بيئة افتراضية
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 3. ثبّت OpenWA Gateway
setup-openwa.bat

# 4. اضبط الإعدادات
copy .env.example .env
# عدّل .env بمعرف حساب Cloudflare ومفتاح API

# 5. ولّد صور الكتالوج (مرة واحدة)
python scripts\generate_reference_images.py

# 6. شغّل كل الخدمات
start-openwa.bat
```

ثم افتح http://localhost:2886 لمسح كود QR الخاص بواتساب.

### كيف يعمل؟

1. المستخدم يرسل **"hi"** → البوت يعرض 3 صور قصات مع أرقام
2. المستخدم يرد **"1"** أو **"2"** أو **"3"** → البوت يطلب سيلفي
3. المستخدم يرسل **سيلفي** → التحقق من الوجه → معالجة بالذكاء الاصطناعي → صورة النتيجة
4. المستخدم يرى النتيجة → يرد **"1"** لتأكيد الحجز أو **"2"** لتجربة قصة أخرى

### المتطلبات

- Python 3.12+
- Node.js 18+ (لـ OpenWA Gateway)
- حساب Cloudflare (النسخة المجانية)
- حساب واتساب (لمسح QR)

---

## 👨‍💻 Developed by

**Mahamed Al-Garoshy**  
**محمد الجروشي**

---

##  License

This project is proprietary. All rights reserved.
