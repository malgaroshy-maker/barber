from typing import Optional


def build_category_menu_section() -> list[dict]:
    """Build interactive list rows for the 5 catalogue categories."""
    from conversation.catalogue_matcher import CATEGORIES

    rows = []
    for cat in CATEGORIES:
        rows.append({
            "id": f"cat_{cat['id']}",
            "title": cat["title"][:24],
            "description": cat["description"][:72],
            "image_url": "",
            "name_ar": cat["title"],
        })

    rows.append({
        "id": "ai_recommend",
        "title": "🌐 اختارلي القصة (AI)",
        "description": "حلل شكل وشي واقترحلي أفضل قصة تليق عليا",
        "image_url": "",
        "name_ar": "اختارلي القصة (AI)",
    })

    return [{"title": "أقسام صالون الحلاقة ✂️", "rows": rows}]


def build_haircut_menu_section(haircuts: list[dict], ai_option: bool = True) -> list[dict]:
    rows = []
    for h in haircuts:
        if not h.get("active", True):
            continue
        title = f"{h['name_ar']} ({h['price_egp']} ج.م)"
        description = h.get("description_ar", "")[:72]
        rows.append({
            "id": h["id"],
            "title": title[:24],
            "description": description,
            "image_url": h.get("image_url", ""),
            "name_ar": h.get("name_ar", ""),
        })

    if ai_option:
        rows.append({
            "id": "ai_recommend",
            "title": "🌐 اختارلي القصة",
            "description": "سيب الطلعة دي عليا وأنا اختارلك اللي يليق عليك",
            "image_url": "",
            "name_ar": "",
        })

    return [{"title": "القصات المتاحة", "rows": rows}]



def build_decision_buttons() -> list[dict]:
    return [
        {
            "type": "reply",
            "reply": {"id": "confirm_booking", "title": "✅ اعتمد واحجز"},
        },
        {
            "type": "reply",
            "reply": {"id": "try_another", "title": "🔄 جرب قصة تانية"},
        },
    ]


def build_retry_button() -> list[dict]:
    return [
        {
            "type": "reply",
            "reply": {"id": "back_to_menu", "title": "📋 الرجوع للقائمة"},
        },
    ]
