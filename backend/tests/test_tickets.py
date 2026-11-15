
from datetime import datetime, timedelta, timezone

from ..agents.agent_setup import initialize_agents
from ..models import Event


def test_valid_ticket_check_in(
    db_session,
    sample_ticket,
    sample_event,
):
    agents = initialize_agents(db_session)

    now = datetime.now(timezone.utc)

    # Use a time inside the event's check-in window.
    result = agents["ticket_agent"].check_in(
        ticket_code=sample_ticket.ticket_code,
        event_id=sample_event.id,
        scan_time=now,
    )

    assert result["success"] is True
    assert result["message"] == "Check-in successful."


def test_reject_wrong_event(
    db_session,
    sample_ticket,
    sample_event,
):
    agents = initialize_agents(db_session)

    result = agents["ticket_agent"].check_in(
        ticket_code=sample_ticket.ticket_code,
        event_id=99999,
    )

    assert result["success"] is False
    assert "different event" in result["message"].lower()


def test_reject_cancelled_ticket(
    db_session,
    sample_ticket,
    sample_event,
):
    sample_ticket.status = "cancelled"
    db_session.commit()

    agents = initialize_agents(db_session)

    result = agents["ticket_agent"].check_in(
        ticket_code=sample_ticket.ticket_code,
        event_id=sample_event.id,
    )

    assert result["success"] is False
    assert "cancelled" in result["message"].lower()


def test_prevent_double_check_in(
    db_session,
    sample_ticket,
    sample_event,
):
    agents = initialize_agents(db_session)

    now = datetime.now(timezone.utc)

    first_result = agents["ticket_agent"].check_in(
        ticket_code=sample_ticket.ticket_code,
        event_id=sample_event.id,
        scan_time=now,
    )

    assert first_result["success"] is True

    second_result = agents["ticket_agent"].check_in(
        ticket_code=sample_ticket.ticket_code,
        event_id=sample_event.id,
        scan_time=now,
    )

    assert second_result["success"] is False
    assert "already" in second_result["message"].lower()


def test_reject_check_in_before_window_opens(
    db_session,
    sample_ticket,
    sample_event,
):
    agents = initialize_agents(db_session)

    early_time = (
        sample_event.start_time - timedelta(days=1)
    )

    result = agents["ticket_agent"].check_in(
        ticket_code=sample_ticket.ticket_code,
        event_id=sample_event.id,
        scan_time=early_time,
    )

    assert result["success"] is False
    assert "not opened" in result["message"].lower()
