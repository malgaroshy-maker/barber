from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ConversationState(str, Enum):
    WELCOME = "WELCOME"
    AWAITING_CHOICE = "AWAITING_CHOICE"
    AWAITING_SELFIE = "AWAITING_SELFIE"
    PROCESSING = "PROCESSING"
    AWAITING_DECISION = "AWAITING_DECISION"
    BOOKING_CONFIRMED = "BOOKING_CONFIRMED"


@dataclass
class UserSession:
    phone: str
    state: ConversationState = ConversationState.WELCOME
    selected_haircut: Optional[str] = None
    face_shape: Optional[str] = None
    selfie_media_id: Optional[str] = None
    result_image_url: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    attempts: int = 0


@dataclass
class Booking:
    id: str
    customer_phone: str
    haircut_id: str
    face_shape: Optional[str]
    confirmed_at: datetime = field(default_factory=datetime.now)
    notified_barber: bool = False
