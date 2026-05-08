from typing import Optional


def build_haircut_menu_section(haircuts: list[dict], ai_option: bool = True) -> list[dict]:
    rows = []
    for h in haircuts:
        if not h.get("active", True):
            continue
        title = f"{h['name_ar']} ({h['price_egp']} ج.م)"
        description = h.get("description_ar", "")[:72]
        rows.append({"id": h["id"], "title": title[:24], "description": description})

    if ai_option:
        rows.append({
            "id": "ai_recommend",
            "title": "🌐 اختارلي القصة",
            "description": "سيب الطلعة دي عليا وأنا اختارلك اللي يليق عليك",
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
