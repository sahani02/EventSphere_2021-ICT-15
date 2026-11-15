
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from .database import Base


# =========================================================
# USER
# =========================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

    # admin, staff, attendee
    role = Column(String(20), nullable=False, default="attendee")

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    bookings = relationship("Booking", back_populates="user")
    waitlist_entries = relationship("WaitlistEntry", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    hire_requests = relationship("VenueHireRequest", back_populates="user")

    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'staff', 'attendee')",
            name="check_user_role"
        ),
    )


# =========================================================
# VENUE
# =========================================================

class Venue(Base):
    __tablename__ = "venues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    location = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    capacity = Column(Integer, nullable=False)
    hourly_hire_rate = Column(Numeric(10, 2), default=0, nullable=False)

    is_open_for_private_hire = Column(Boolean, default=True)
    turnaround_minutes = Column(Integer, default=30, nullable=False)

    image_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    events = relationship("Event", back_populates="venue")
    hire_requests = relationship("VenueHireRequest", back_populates="venue")

    __table_args__ = (
        CheckConstraint("capacity > 0", name="check_venue_capacity"),
        CheckConstraint(
            "hourly_hire_rate >= 0",
            name="check_venue_hire_rate"
        ),
        CheckConstraint(
            "turnaround_minutes >= 0",
            name="check_turnaround_minutes"
        ),
    )


# =========================================================
# EVENT
# =========================================================

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=False)

    venue_id = Column(
        Integer,
        ForeignKey("venues.id", ondelete="RESTRICT"),
        nullable=False
    )

    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)

    # draft, published, cancelled, completed
    status = Column(String(20), default="draft", nullable=False)

    check_in_opens_at = Column(DateTime(timezone=True), nullable=True)
    check_in_closes_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True
    )

    venue = relationship("Venue", back_populates="events")
    ticket_categories = relationship(
        "TicketCategory",
        back_populates="event",
        cascade="all, delete-orphan"
    )
    bookings = relationship("Booking", back_populates="event")
    tickets = relationship("Ticket", back_populates="event")
    waitlist_entries = relationship("WaitlistEntry", back_populates="event")

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'cancelled', 'completed')",
            name="check_event_status"
        ),
        CheckConstraint(
            "end_time > start_time",
            name="check_event_time"
        ),
        Index("ix_event_venue_time", "venue_id", "start_time", "end_time"),
    )


# =========================================================
# TICKET CATEGORY
# =========================================================

class TicketCategory(Base):
    __tablename__ = "ticket_categories"

    id = Column(Integer, primary_key=True, index=True)

    event_id = Column(
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False
    )

    name = Column(String(100), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)

    total_quantity = Column(Integer, nullable=False)
    sold_quantity = Column(Integer, default=0, nullable=False)

    event = relationship("Event", back_populates="ticket_categories")
    bookings = relationship("Booking", back_populates="ticket_category")
    tickets = relationship("Ticket", back_populates="ticket_category")
    waitlist_entries = relationship(
        "WaitlistEntry",
        back_populates="ticket_category"
    )

    __table_args__ = (
        CheckConstraint("price >= 0", name="check_ticket_price"),
        CheckConstraint(
            "total_quantity > 0",
            name="check_ticket_total"
        ),
        CheckConstraint(
            "sold_quantity >= 0",
            name="check_ticket_sold_nonnegative"
        ),
        CheckConstraint(
            "sold_quantity <= total_quantity",
            name="check_ticket_sold_limit"
        ),
        UniqueConstraint(
            "event_id",
            "name",
            name="uq_event_ticket_category"
        ),
    )


# =========================================================
# BOOKING
# =========================================================

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)

    booking_reference = Column(
        String(50),
        unique=True,
        index=True,
        nullable=False
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )

    event_id = Column(
        Integer,
        ForeignKey("events.id", ondelete="RESTRICT"),
        nullable=False
    )

    ticket_category_id = Column(
        Integer,
        ForeignKey("ticket_categories.id", ondelete="RESTRICT"),
        nullable=False
    )

    quantity = Column(Integer, nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)

    payment_reference = Column(
        String(100),
        unique=True,
        nullable=True
    )

    # confirmed, cancelled
    status = Column(String(20), default="confirmed", nullable=False)

    refund_amount = Column(Numeric(10, 2), default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="bookings")
    event = relationship("Event", back_populates="bookings")
    ticket_category = relationship(
        "TicketCategory",
        back_populates="bookings"
    )
    tickets = relationship("Ticket", back_populates="booking")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_booking_quantity"),
        CheckConstraint(
            "total_amount >= 0",
            name="check_booking_amount"
        ),
        CheckConstraint(
            "refund_amount >= 0",
            name="check_booking_refund"
        ),
        CheckConstraint(
            "status IN ('confirmed', 'cancelled')",
            name="check_booking_status"
        ),
    )


# =========================================================
# TICKET
# =========================================================

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)

    ticket_code = Column(
        String(100),
        unique=True,
        index=True,
        nullable=False
    )

    booking_id = Column(
        Integer,
        ForeignKey("bookings.id", ondelete="RESTRICT"),
        nullable=False
    )

    event_id = Column(
        Integer,
        ForeignKey("events.id", ondelete="RESTRICT"),
        nullable=False
    )

    ticket_category_id = Column(
        Integer,
        ForeignKey("ticket_categories.id", ondelete="RESTRICT"),
        nullable=False
    )

    # valid, used, cancelled
    status = Column(String(20), default="valid", nullable=False)

    checked_in_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    booking = relationship("Booking", back_populates="tickets")
    event = relationship("Event", back_populates="tickets")
    ticket_category = relationship(
        "TicketCategory",
        back_populates="tickets"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('valid', 'used', 'cancelled')",
            name="check_ticket_status"
        ),
    )


# =========================================================
# PRIVATE VENUE HIRE REQUEST
# =========================================================

class VenueHireRequest(Base):
    __tablename__ = "venue_hire_requests"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )

    venue_id = Column(
        Integer,
        ForeignKey("venues.id", ondelete="RESTRICT"),
        nullable=False
    )

    purpose = Column(String(255), nullable=False)
    guest_count = Column(Integer, nullable=False)

    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)

    quoted_price = Column(Numeric(10, 2), nullable=True)

    # pending, confirmed, rejected, escalated
    status = Column(String(20), default="pending", nullable=False)

    decision_reason = Column(Text, nullable=True)
    conversation_id = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="hire_requests")
    venue = relationship("Venue", back_populates="hire_requests")

    __table_args__ = (
        CheckConstraint(
            "guest_count > 0",
            name="check_hire_guest_count"
        ),
        CheckConstraint(
            "end_time > start_time",
            name="check_hire_time"
        ),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'rejected', 'escalated')",
            name="check_hire_status"
        ),
        Index(
            "ix_hire_venue_time",
            "venue_id",
            "start_time",
            "end_time"
        ),
    )


# =========================================================
# WAITLIST
# =========================================================

class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )

    event_id = Column(
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False
    )

    ticket_category_id = Column(
        Integer,
        ForeignKey("ticket_categories.id", ondelete="CASCADE"),
        nullable=False
    )

    quantity = Column(Integer, default=1, nullable=False)

    # waiting, offered, claimed, expired, cancelled
    status = Column(String(20), default="waiting", nullable=False)

    offered_at = Column(DateTime(timezone=True), nullable=True)
    offer_expires_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="waitlist_entries")
    event = relationship("Event", back_populates="waitlist_entries")
    ticket_category = relationship(
        "TicketCategory",
        back_populates="waitlist_entries"
    )

    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_waitlist_quantity"),
        CheckConstraint(
            "status IN ('waiting', 'offered', 'claimed', 'expired', 'cancelled')",
            name="check_waitlist_status"
        ),
        Index(
            "ix_waitlist_category_status",
            "ticket_category_id",
            "status"
        ),
    )


# =========================================================
# AGENT MESSAGE LOG
# =========================================================

class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id = Column(Integer, primary_key=True, index=True)

    message_id = Column(
        String(100),
        unique=True,
        index=True,
        nullable=False
    )

    sender = Column(String(100), nullable=False)
    receiver = Column(String(100), nullable=False)

    # REQUEST, AGREE, REFUSE, PROPOSE, INFORM, FAILURE
    performative = Column(String(20), nullable=False)

    conversation_id = Column(String(100), index=True, nullable=False)

    content = Column(JSON, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "performative IN ('REQUEST', 'AGREE', 'REFUSE', 'PROPOSE', 'INFORM', 'FAILURE')",
            name="check_agent_performative"
        ),
    )


# =========================================================
# NOTIFICATION
# =========================================================

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)

    is_read = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="notifications")
