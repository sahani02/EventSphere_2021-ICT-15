
from datetime import datetime, timedelta, timezone

from ..agents.agent_setup import initialize_agents
from ..models import (
    Event,
    WaitlistEntry,
    Notification,
)


def test_venue_agent_accepts_available_venue(
    db_session,
    sample_venue,
):
    agents = initialize_agents(db_session)

    now = datetime.now(timezone.utc)

    result = agents["venue_agent"].check_availability(
        venue_id=sample_venue.id,
        start_time=now + timedelta(days=20),
        end_time=now + timedelta(days=20, hours=2),
        guest_count=100,
    )

    assert result["available"] is True


def test_venue_agent_rejects_time_conflict(
    db_session,
    sample_venue,
    sample_event,
):
    agents = initialize_agents(db_session)

    result = agents["venue_agent"].check_availability(
        venue_id=sample_venue.id,
        start_time=sample_event.start_time + timedelta(minutes=15),
        end_time=sample_event.end_time + timedelta(hours=1),
        guest_count=100,
    )

    assert result["available"] is False
    assert "conflict" in result["reason"].lower()


def test_booking_agent_prevents_overbooking(
    db_session,
    sample_category,
):
    sample_category.sold_quantity = 99
    db_session.commit()

    agents = initialize_agents(db_session)

    result = agents["booking_agent"].reserve_tickets(
        ticket_category_id=sample_category.id,
        quantity=2,
    )

    assert result["success"] is False


def test_ticket_agent_prevents_double_checkin(
    db_session,
    sample_ticket,
    sample_event,
):
    agents = initialize_agents(db_session)

    now = datetime.now(timezone.utc)

    first = agents["ticket_agent"].check_in(
        ticket_code=sample_ticket.ticket_code,
        event_id=sample_event.id,
        scan_time=now,
    )

    second = agents["ticket_agent"].check_in(
        ticket_code=sample_ticket.ticket_code,
        event_id=sample_event.id,
        scan_time=now,
    )

    assert first["success"] is True
    assert second["success"] is False


def test_waitlist_agent_adds_user(
    db_session,
    attendee,
    sample_event,
    sample_category,
):
    agents = initialize_agents(db_session)

    result = agents["waitlist_agent"].add_to_waitlist(
        user_id=attendee.id,
        event_id=sample_event.id,
        ticket_category_id=sample_category.id,
        quantity=2,
    )

    assert result["success"] is True

    entry = (
        db_session.query(WaitlistEntry)
        .filter(WaitlistEntry.id == result["waitlist_id"])
        .first()
    )

    assert entry is not None
    assert entry.user_id == attendee.id
    assert entry.status == "waiting"


def test_notification_agent_saves_notification(
    db_session,
    attendee,
):
    agents = initialize_agents(db_session)

    result = agents["notification_agent"].create_notification(
        user_id=attendee.id,
        title="Test Notification",
        message="Your booking has been confirmed.",
    )

    assert result["success"] is True

    notification = (
        db_session.query(Notification)
        .filter(Notification.id == result["notification_id"])
        .first()
    )

    assert notification is not None
    assert notification.title == "Test Notification"
    assert notification.is_read is False
