import logging
from typing import Optional
import httpx

from app.config import OPENROUTER_API_KEY, OPENROUTER_MODEL

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

def build_system_prompt() -> str:
    """Build the system prompt dynamically with all 30 haircuts from haircuts.json."""
    from conversation.state_machine import get_haircuts
    haircuts = get_haircuts()

    cuts_summary_lines = []
    for i, h in enumerate(haircuts, start=1):
        name_ar = h.get("name_ar", h["id"])
        name_en = h.get("name_en", "")
        price = h.get("price_egp", 100)
        desc = h.get("description_ar", "")
        cat = h.get("category", "")
        cuts_summary_lines.append(f"  {i}. {name_ar} ({name_en}) [{cat}] - {price} EGP: {desc}")

    cuts_text = "\n".join(cuts_summary_lines)

    return f"""أنت "أسطى حلاق" خبير في صالون الحلاقة والتجميل الرجالي، ودمك خفيف ومتحدث باللهجة المصرية العامية الطبيعية الودودة.

معلومات الصالون والخدمات:
- مواعيد العمل: كل يوم من 12:00 ظهراً حتى 12:00 منتصف الليل.
- الأقسام الرئيسية للقصَات (5 أقسام):
  1. 💈 قصات الفيد (Fades): تدرج ناعم وأنيق.
  2. ✂️ القصات الكلاسيك (Classic): بومبادور، كويف، سايد بارت، سليك باك.
  3. 🔥 القصات المودرن (Modern): أندركت، موليت مودرن، فو هوك.
  4. 💇‍♂️ القصات القصيرة (Short): باز كت، فرينش كروب، كرو كت، تكستشرد كروب.
  5. 🌀 الكيرلي والغرة (Curls & Fringes): كيرلي توب، أفرو، كرتينز، وولف كت.

قائمة الكتالوج الكاملة (30 قصة):
{cuts_text}

خدمات الذكاء الاصطناعي والتجربة:
- الزبون يقدر يختار قصة من الكتالوج أو يبعد صورة سيلفي في أي وقت عشان الذكاء الاصطناعي يحلل شكل وشه ويجربله القصة اللي يختارها على صورته فوراً!
- لو الزبون محتار، قوله يبعد سيلفي أو يكتب "ai" والسيستم هيختارله القصة المناسبة لشكله.

تعليمات الرد:
1. اتكلم باللهجة المصرية العامية الودودة (مثال: "يا باشا", "منور الصالون", "تحت أمرك", "يا غالي").
2. خلي إجابتك مختصرة ومباشرة (2-4 جمل على الأكثر) عشان رسائل الواتساب تكون سهلة في القراءة.
3. لو الزبون يسأل عن أي قصة من الـ 30 قصة أو أسعارها أو المواعيد جاوبه بدقة وبطريقة جذابة.
4. لو الزبون حابب يجرب قصة، شجعه يبعث صورة سيلفي.
5. لا تستخدم الفصحى المعقدة ولا تكرر نفسك.
"""


async def generate_llm_response(
    user_text: str,
    history: list[dict],
    current_state: str = "",
) -> Optional[str]:
    """Call OpenRouter API to generate a response from Gemma LLM in Egyptian Arabic.

    Returns the generated response string, or None if OPENROUTER_API_KEY is not configured or on error.
    """
    api_key = (OPENROUTER_API_KEY or "").strip()
    if not api_key:
        logger.debug("OPENROUTER_API_KEY is empty; skipping LLM call")
        return None

    # Construct chat messages
    system_prompt = build_system_prompt()
    messages = [{"role": "system", "content": system_prompt}]


    # Include recent history (last 10 messages)
    for msg in history[-10:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    # Append current user prompt
    messages.append({"role": "user", "content": user_text})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/malgaroshy-maker/barber",
        "X-Title": "AI Barber Bot",
        "Content-Type": "application/json",
    }

    models_to_try = [
        OPENROUTER_MODEL or "google/gemma-4-26b-a4b-it:free",
        "openrouter/free",
        "openai/gpt-oss-20b:free",
        "google/gemma-4-31b-it:free",
        "inclusionai/ling-3.0-flash:free",
    ]


    for model_name in models_to_try:
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 300,
        }

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        reply = choices[0].get("message", {}).get("content", "").strip()
                        if reply:
                            return reply
                else:
                    logger.warning(
                        "OpenRouter API error with model %s (%s): %s",
                        model_name,
                        resp.status_code,
                        resp.text[:200],
                    )
        except Exception as exc:
            logger.error("OpenRouter request exception for model %s: %s", model_name, exc)

    return None

