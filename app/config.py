import os
from dotenv import load_dotenv

load_dotenv()


WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
BUSINESS_PHONE_NUMBER = os.getenv("BUSINESS_PHONE_NUMBER")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-2-9b-it:free")


REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
HUGGINGFACE_API_TOKEN = os.getenv("HUGGINGFACE_API_TOKEN")
FREETHEAI_API_KEY = os.getenv("FREETHEAI_API_KEY")

# Cloudflare Workers AI (free hair swap / image generation)
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")

# Google Antigravity CLI (agy) settings
AGY_MODEL = os.getenv("AGY_MODEL", "gemini-3.6-flash")
AGY_EFFORT = os.getenv("AGY_EFFORT", "low")

BARBER_PHONE_NUMBER = os.getenv("BARBER_PHONE_NUMBER")
NGROK_URL = os.getenv("NGROK_URL", "")

# OpenWA Gateway (self-hosted WhatsApp API)
OPENWA_API_URL = os.getenv("OPENWA_API_URL", "http://localhost:2785")
OPENWA_API_KEY = os.getenv("OPENWA_API_KEY", "")
OPENWA_SESSION_ID = os.getenv("OPENWA_SESSION_ID", "")
OPENWA_WEBHOOK_SECRET = os.getenv("OPENWA_WEBHOOK_SECRET", "")

# Use OpenWA if configured, otherwise fall back to Meta Cloud API
USE_OPENWA = bool(OPENWA_API_URL and OPENWA_API_KEY and OPENWA_SESSION_ID)

WHATSAPP_API_VERSION = "v23.0"
WHATSAPP_API_URL = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"

MAX_SELFIE_RETRIES = 3
MAX_SESSIONS_PER_HOUR = 10
PROCESSING_TIMEOUT_SECONDS = 25
