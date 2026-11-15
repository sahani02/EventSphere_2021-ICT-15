from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict

class UserRegister(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    full_name: str
    email: str
    role: str
    model_config = ConfigDict(from_attributes=True)

class VenueCreate(BaseModel):
    name: str
    location: str
    capacity: int = Field(gt=0)
    description: str = ""
    image_url: str = ""
    hourly_hire_rate: float = Field(ge=0)
    is_open_for_private_hire: bool = True

class EventCreate(BaseModel):
    title: str
    category: str
    venue_id: int
    start_time: datetime
    end_time: datetime
    description: str = ""
    status: str = "draft"
    ticket_name: str = "Standard"
    ticket_price: float = Field(ge=0)
    ticket_quantity: int = Field(gt=0)

class BookingCreate(BaseModel):
    event_id: int
    ticket_category_id: int
    quantity: int = Field(gt=0, le=6)

class HireCreate(BaseModel):
    venue_id: int
    purpose: str
    guest_count: int = Field(gt=0)
    start_time: datetime
    end_time: datetime
