import json
from pathlib import Path
from typing import Optional

from app.models import ConversationState

DATA_DIR = Path(__file__).parent.parent / "data"


def get_haircuts() -> list[dict]:
    with open(DATA_DIR / "haircuts.json", encoding="utf-8") as f:
        return json.load(f)


def get_face_shape_map() -> dict:
    with open(DATA_DIR / "face_shape_map.json", encoding="utf-8") as f:
        return json.load(f)


def get_haircut_by_id(haircut_id: str) -> Optional[dict]:
    for h in get_haircuts():
        if h["id"] == haircut_id:
            return h
    return None


def get_recommendations(face_shape: str) -> list[dict]:
    shape_map = get_face_shape_map()
    shape_data = shape_map.get(face_shape)
    if not shape_data:
        return get_haircuts()
    ids = shape_data.get("recommended", [])
    all_haircuts = {h["id"]: h for h in get_haircuts()}
    return [all_haircuts[i] for i in ids if i in all_haircuts]


TRANSITIONS = {
    ConversationState.WELCOME: {
        "any": ConversationState.AWAITING_CHOICE,
    },
    ConversationState.AWAITING_CHOICE: {
        "haircut_pick": ConversationState.AWAITING_SELFIE,
        "ai_recommend": ConversationState.AWAITING_SELFIE,
    },
    ConversationState.AWAITING_SELFIE: {
        "valid_image": ConversationState.PROCESSING,
        "invalid_image": ConversationState.AWAITING_SELFIE,
        "max_retries": ConversationState.WELCOME,
    },
    ConversationState.PROCESSING: {
        "done": ConversationState.AWAITING_DECISION,
        "error": ConversationState.AWAITING_CHOICE,
    },
    ConversationState.AWAITING_DECISION: {
        "confirm": ConversationState.BOOKING_CONFIRMED,
        "try_another": ConversationState.AWAITING_CHOICE,
    },
    ConversationState.BOOKING_CONFIRMED: {
        "any": ConversationState.AWAITING_CHOICE,
    },
}


def next_state(current: ConversationState, event: str) -> ConversationState:
    return TRANSITIONS.get(current, {}).get(event, current)
