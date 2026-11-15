
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    model_validator,
)


# =========================================================
# COMMON
# =========================================================

class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# =========================================================
# AUTHENTICATION / USER
# =========================================================

class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(ORMBase):
    id: int
    full_name: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# =========================================================
# VENUE
# =========================================================

class VenueCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    location: str = Field(min_length=2, max_length=255)
    description: Optional[str] = None

    capacity: int = Field(gt=0)
    hourly_hire_rate: Decimal = Field(default=0, ge=0)

    is_open_for_private_hire: bool = True
    turnaround_minutes: int = Field(default=30, ge=0)

    image_url: Optional[str] = None


class VenueUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    location: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None

    capacity: Optional[int] = Field(default=None, gt=0)
    hourly_hire_rate: Optional[Decimal] = Field(default=None, ge=0)

    is_open_for_private_hire: Optional[bool] = None
    turnaround_minutes: Optional[int] = Field(default=None, ge=0)

    image_url: Optional[str] = None


class VenueResponse(ORMBase):
    id: int
    name: str
    location: str
    description: Optional[str]
    capacity: int
    hourly_hire_rate: Decimal
    is_open_for_private_hire: bool
    turnaround_minutes: int
    image_url: Optional[str]
    created_at: Optional[datetime]


# =========================================================
# EVENT / TICKET CATEGORY
# =========================================================

class TicketCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    price: Decimal = Field(ge=0)
    total_quantity: int = Field(gt=0)


class TicketCategoryResponse(ORMBase):
    id: int
    event_id: int
    name: str
    price: Decimal
    total_quantity: int
    sold_quantity: int


class EventCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: Optional[str] = None
    category: str = Field(min_length=2, max_length=100)

    venue_id: int = Field(gt=0)

    start_time: datetime
    end_time: datetime

    check_in_opens_at: Optional[datetime] = None
    check_in_closes_at: Optional[datetime] = None

    ticket_categories: list[TicketCategoryCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_event_times(self):
        if self.end_time <= self.start_time:
            raise ValueError("Event end time must be after start time.")

        if (
            self.check_in_opens_at is not None
            and self.check_in_closes_at is not None
            and self.check_in_closes_at <= self.check_in_opens_at
        ):
            raise ValueError("Check-in closing time must be after opening time.")

        return self


class EventUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    venue_id: Optional[int] = Field(default=None, gt=0)

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    check_in_opens_at: Optional[datetime] = None
    check_in_closes_at: Optional[datetime] = None


class EventResponse(ORMBase):
    id: int
    title: str
    description: Optional[str]
    category: str
    venue_id: int

    start_time: datetime
    end_time: datetime
    status: str

    check_in_opens_at: Optional[datetime]
    check_in_closes_at: Optional[datetime]

    created_at: Optional[datetime]
    ticket_categories: list[TicketCategoryResponse] = []


# =========================================================
# BOOKING
# =========================================================

class BookingCreate(BaseModel):
    event_id: int = Field(gt=0)
    ticket_category_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=6)


class BookingResponse(ORMBase):
    id: int
    booking_reference: str
    user_id: int
    event_id: int
    ticket_category_id: int

    quantity: int
    total_amount: Decimal
    payment_reference: Optional[str]

    status: str
    refund_amount: Decimal

    created_at: Optional[datetime]
    cancelled_at: Optional[datetime]


class BookingCancellationResponse(BaseModel):
    message: str
    booking_reference: str
    refund_amount: Decimal
    status: str


# =========================================================
# TICKET / CHECK-IN
# =========================================================

class TicketResponse(ORMBase):
    id: int
    ticket_code: str
    booking_id: int
    event_id: int
    ticket_category_id: int
    status: str
    checked_in_at: Optional[datetime]
    created_at: Optional[datetime]


class TicketScanRequest(BaseModel):
    ticket_code: str = Field(min_length=1, max_length=100)
    event_id: int = Field(gt=0)


class TicketScanResponse(BaseModel):
    success: bool
    message: str
    ticket_code: Optional[str] = None
    checked_in_at: Optional[datetime] = None


# =========================================================
# PRIVATE VENUE HIRE
# =========================================================

class VenueHireCreate(BaseModel):
    venue_id: int = Field(gt=0)
    purpose: str = Field(min_length=3, max_length=255)
    guest_count: int = Field(gt=0)

    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def validate_hire_times(self):
        if self.end_time <= self.start_time:
            raise ValueError("Hire end time must be after start time.")
        return self


class VenueHireResponse(ORMBase):
    id: int
    user_id: int
    venue_id: int
    purpose: str
    guest_count: int

    start_time: datetime
    end_time: datetime

    quoted_price: Optional[Decimal]
    status: str
    decision_reason: Optional[str]
    conversation_id: Optional[str]
    created_at: Optional[datetime]


# =========================================================
# WAITLIST
# =========================================================

class WaitlistCreate(BaseModel):
    event_id: int = Field(gt=0)
    ticket_category_id: int = Field(gt=0)
    quantity: int = Field(default=1, gt=0, le=6)


class WaitlistResponse(ORMBase):
    id: int
    user_id: int
    event_id: int
    ticket_category_id: int
    quantity: int

    status: str
    offered_at: Optional[datetime]
    offer_expires_at: Optional[datetime]
    created_at: Optional[datetime]


# =========================================================
# AGENT COMMUNICATION
# =========================================================

class AgentMessageCreate(BaseModel):
    sender: str
    receiver: str

    performative: str = Field(
        pattern="^(REQUEST|AGREE|REFUSE|PROPOSE|INFORM|FAILURE)$"
    )

    conversation_id: str
    content: dict[str, Any]


class AgentMessageResponse(ORMBase):
    id: int
    message_id: str
    sender: str
    receiver: str
    performative: str
    conversation_id: str
    content: dict[str, Any]
    created_at: Optional[datetime]


# =========================================================
# NOTIFICATION
# =========================================================

class NotificationResponse(ORMBase):
    id: int
    user_id: int
    title: str
    message: str
    is_read: bool
    created_at: Optional[datetime]
