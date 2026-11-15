
from ..agents.agent_setup import initialize_agents


def test_reserve_available_tickets(
    db_session,
    sample_category,
):
    agents = initialize_agents(db_session)

    result = agents["booking_agent"].reserve_tickets(
        ticket_category_id=sample_category.id,
        quantity=5,
    )

    assert result["success"] is True
    assert result["quantity"] == 5

    db_session.commit()
    db_session.refresh(sample_category)

    assert sample_category.sold_quantity == 5


def test_reject_more_tickets_than_available(
    db_session,
    sample_category,
):
    sample_category.sold_quantity = 98
    db_session.commit()

    agents = initialize_agents(db_session)

    result = agents["booking_agent"].reserve_tickets(
        ticket_category_id=sample_category.id,
        quantity=5,
    )

    assert result["success"] is False
    assert "available" in result["reason"].lower()


def test_prevent_overbooking(
    db_session,
    sample_category,
):
    sample_category.sold_quantity = 95
    db_session.commit()

    agents = initialize_agents(db_session)
    booking_agent = agents["booking_agent"]

    first_result = booking_agent.reserve_tickets(
        ticket_category_id=sample_category.id,
        quantity=5,
    )

    assert first_result["success"] is True

    db_session.commit()

    second_result = booking_agent.reserve_tickets(
        ticket_category_id=sample_category.id,
        quantity=1,
    )

    assert second_result["success"] is False

    db_session.refresh(sample_category)

    assert sample_category.sold_quantity == 100


def test_release_tickets(
    db_session,
    sample_category,
):
    sample_category.sold_quantity = 10
    db_session.commit()

    agents = initialize_agents(db_session)

    result = agents["booking_agent"].release_tickets(
        ticket_category_id=sample_category.id,
        quantity=3,
    )

    assert result["success"] is True

    db_session.commit()
    db_session.refresh(sample_category)

    assert sample_category.sold_quantity == 7


def test_reject_invalid_booking_quantity(
    db_session,
    sample_category,
):
    agents = initialize_agents(db_session)

    result = agents["booking_agent"].reserve_tickets(
        ticket_category_id=sample_category.id,
        quantity=0,
    )

    assert result["success"] is False
