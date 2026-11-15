
import pytest

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ..database import Base, get_db
from ..main import app
from ..models import (
    User,
    Venue,
    Event,
    TicketCategory,
    Booking,
    Ticket,
)
from ..security import (
    get_current_user,
    get_current_admin,
    get_current_staff,
    get_password_hash,
)


# --------------------------------------------------
# TEST DATABASE
# --------------------------------------------------

TEST_DATABASE_URL = "sqlite://"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


@pytest.fixture
def db_session():
    """Create a fresh database for each test."""

    Base.metadata.create_all(bind=test_engine)

    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=test_engine)


# --------------------------------------------------
# TEST USERS
# --------------------------------------------------

@pytest.fixture
def attendee(db_session):
    user = User(
        full_name="Test Attendee",
        email="attendee@test.com",
        password_hash=get_password_hash("Test12345"),
        role="attendee",
        is_active=True,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture
def admin(db_session):
    user = User(
        full_name="Test Admin",
        email="admin@test.com",
        password_hash=get_password_hash("Admin12345"),
        role="admin",
        is_active=True,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture
def staff(db_session):
    user = User(
        full_name="Test Staff",
        email="staff@test.com",
        password_hash=get_password_hash("Staff12345"),
        role="staff",
        is_active=True,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


# --------------------------------------------------
# SAMPLE VENUE
# --------------------------------------------------

@pytest.fixture
def sample_venue(db_session):
    venue = Venue(
        name="University Main Auditorium",
        location="University Campus",
        capacity=500,
        description="Main university event venue",
        hourly_hire_rate=Decimal("5000.00"),
        is_open_for_private_hire=True,
        turnaround_minutes=30,
    )

    db_session.add(venue)
    db_session.commit()
    db_session.refresh(venue)

    return venue


# --------------------------------------------------
# SAMPLE EVENT AND TICKET CATEGORY
# --------------------------------------------------

@pytest.fixture
def sample_event(db_session, sample_venue):
    now = datetime.now(timezone.utc)

    event = Event(
        title="Technology Conference 2026",
        description="A university technology conference.",
        category="Conference",
        venue_id=sample_venue.id,
        start_time=now + timedelta(days=7),
        end_time=now + timedelta(days=7, hours=4),
        check_in_opens_at=now + timedelta(days=7) - timedelta(hours=2),
        check_in_closes_at=now + timedelta(days=7, hours=4),
        status="published",
    )

    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    return event


@pytest.fixture
def sample_category(db_session, sample_event):
    category = TicketCategory(
        event_id=sample_event.id,
        name="Standard",
        price=Decimal("1000.00"),
        total_quantity=100,
        sold_quantity=0,
    )

    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    return category


# --------------------------------------------------
# SAMPLE BOOKING AND TICKET
# --------------------------------------------------

@pytest.fixture
def sample_booking(
    db_session,
    attendee,
    sample_event,
    sample_category,
):
    booking = Booking(
        booking_reference="EVT-TEST-001",
        user_id=attendee.id,
        event_id=sample_event.id,
        ticket_category_id=sample_category.id,
        quantity=1,
        total_amount=Decimal("1000.00"),
        payment_reference="SIM-TEST-001",
        status="confirmed",
        refund_amount=Decimal("0.00"),
    )

    sample_category.sold_quantity = 1

    db_session.add(booking)
    db_session.commit()
    db_session.refresh(booking)

    return booking


@pytest.fixture
def sample_ticket(db_session, sample_booking, sample_event, sample_category):
    ticket = Ticket(
        ticket_code="TKT-TEST-001",
        booking_id=sample_booking.id,
        event_id=sample_event.id,
        ticket_category_id=sample_category.id,
        status="valid",
    )

    db_session.add(ticket)
    db_session.commit()
    db_session.refresh(ticket)

    return ticket


# --------------------------------------------------
# FASTAPI CLIENT
# --------------------------------------------------

@pytest.fixture
def client(
    db_session,
    attendee,
    admin,
    staff,
):
    """Create a TestClient with the test database."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    app.dependency_overrides[get_current_user] = lambda: attendee
    app.dependency_overrides[get_current_admin] = lambda: admin
    app.dependency_overrides[get_current_staff] = lambda: staff

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
