import re
from typing import Optional
from conversation.state_machine import get_haircuts

CATEGORIES = [
    {
        "id": "fades",
        "title": "💈 قصات الفيد (Fades)",
        "description": "قصات بالتدرج الناعم والأنيق للجوانب",
        "keywords": ["فيد", "fade", "فاد", "تدريج", "تدرج", "سكين"],
    },
    {
        "id": "classic",
        "title": "✂️ القصات الكلاسيك (Classic)",
        "description": "إطلالة كلاسيكية مرتبة وفخمة للمناسبات",
        "keywords": ["كلاسيك", "classic", "بومبادور", "كويف", "سليك", "سايد بارت"],
    },
    {
        "id": "modern",
        "title": "🔥 القصات المودرن (Modern)",
        "description": "قصات عصرية وجريئة لمظهر شبابي",
        "keywords": ["مودرن", "modern", "أندركت", "undercut", "موليت", "هووك"],
    },
    {
        "id": "short",
        "title": "💇‍♂️ القصات القصيرة (Short)",
        "description": "قصات خفيفة وعملية ومريحة يومياً",
        "keywords": ["قصيرة", "قصير", "short", "باز", "buzz", "فرينش", "كروب", "كرو"],
    },
    {
        "id": "curls",
        "title": "🌀 الكيرلي والغرة (Curls & Fringes)",
        "description": "قصات كيرلي وغرة مموجة بأحدث الاستايلات",
        "keywords": ["كيرلي", "curly", "أفرو", "afro", "غرة", "fringe", "وولف", "كرتينز"],
    },
]

ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def normalize_arabic_text(text: str) -> str:
    """Normalize Arabic digits, remove diacritics/tashkeel, and map alefs/taa marbuta."""
    if not text:
        return ""
    # Convert Eastern Arabic digits to Western digits
    t = text.translate(ARABIC_INDIC_DIGITS).strip().lower()
    # Strip Tashkeel
    t = re.sub(r"[\u064B-\u0652]", "", t)
    # Normalize Alef forms
    t = re.sub(r"[أإآ]", "ا", t)
    # Normalize Taa Marbuta
    t = re.sub(r"ة\b", "ه", t)
    return t.strip()


def match_category(text: str) -> Optional[dict]:
    """Match category by numeric index (1-5), category id, or keywords."""
    clean = normalize_arabic_text(text)

    # Strip prefixes like "قسم ", "القسم ", "#", etc.
    digits_only = re.sub(r"[^\d]", "", clean)
    if digits_only and digits_only in ("1", "2", "3", "4", "5"):
        idx = int(digits_only) - 1
        if 0 <= idx < len(CATEGORIES):
            return CATEGORIES[idx]

    # Handle ordinal Arabic words
    ordinals = {
        "الاول": 0, "اول": 0,
        "الثاني": 1, "ثاني": 1,
        "الثالث": 2, "ثالث": 2,
        "الرابع": 3, "رابع": 3,
        "الخامس": 4, "خامس": 4,
    }
    for word, idx in ordinals.items():
        if word in clean:
            return CATEGORIES[idx]

    # Keyword or ID matching
    for cat in CATEGORIES:
        if clean == cat["id"] or cat["id"] in clean:
            return cat
        for kw in cat["keywords"]:
            norm_kw = normalize_arabic_text(kw)
            if norm_kw and norm_kw in clean:
                return cat

    return None


def match_haircut(text: str) -> Optional[dict]:
    """Match a haircut from haircuts.json by ID, Arabic name, or English name."""
    clean = normalize_arabic_text(text)
    if not clean:
        return None

    haircuts = get_haircuts()

    # 1. Exact ID match
    for h in haircuts:
        if clean == h["id"].lower():
            return h

    # 2. Exact Arabic or English name match
    for h in haircuts:
        name_ar = normalize_arabic_text(h.get("name_ar", ""))
        name_en = h.get("name_en", "").lower()
        if name_ar and clean == name_ar:
            return h
        if name_en and clean == name_en:
            return h

    # 3. Substring match: If user text contains the haircut name (e.g. "عايز قصة فيد كلاسيك")
    category_keywords = {"فيد", "فاد", "تدريج", "تدرج", "سكين", "كلاسيك", "مودرن", "قصيرة", "قصير", "كيرلي", "غرة"}

    for h in haircuts:
        name_ar = normalize_arabic_text(h.get("name_ar", ""))
        name_en = h.get("name_en", "").lower()

        if name_ar:
            if name_ar in clean:
                return h
            if clean not in category_keywords and len(clean.split()) > 1 and clean in name_ar:
                return h

        if name_en:
            if name_en in clean:
                return h
            if clean not in ("fade", "classic", "modern", "short", "curls") and len(clean.split()) > 1 and clean in name_en:
                return h

    return None



TRY_ON_KEYWORDS = [
    "جرب", "اجرب", "نجرب", "تجربه", "سيلفي", "صورني", "صورتي",
    "تراي", "try", "test", "تطبيق", "ركبلي", "ركب", "شوفلي",
    "ذكاء اصطناعي", "ai", "شكل شعري", "اشوفها عليا", "غيرلي", "تغيير القصه", "ركب شعري"
]


def detect_try_on_intent(text: str) -> bool:
    """Return True if the text indicates a desire to try/test a haircut on a selfie."""
    clean = normalize_arabic_text(text)
    return any(kw in clean for kw in TRY_ON_KEYWORDS)

