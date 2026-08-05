import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env", override=True)

from ai.openrouter_llm import generate_llm_response


async def main():
    print("=" * 60)
    print(" Testing OpenRouter Gemma LLM Integration")
    print("=" * 60)

    history = []
    prompts = [
        "أهلاً، إيه هي المواعيد بتاعة الصالون وعندكوا إيه قصات؟",
        "بكام قصَة الفيد كلاسيك؟",
        "عايز أحجز ميعاد بكره الساعة 5 مساءً",
    ]

    for p in prompts:
        print(f"\nUser: {p}")
        reply = await generate_llm_response(p, history)
        if reply:
            print(f"Gemma Bot: {reply}")
            history.append({"role": "user", "content": p})
            history.append({"role": "assistant", "content": reply})
        else:
            print("Gemma Bot: [Skipped / API key not set or request failed]")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
