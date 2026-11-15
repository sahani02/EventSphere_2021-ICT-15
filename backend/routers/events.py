
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Event, Venue, TicketCategory, Booking, Ticket
from ..schemas import EventCreate, EventUpdate, EventResponse
from ..security import get_current_admin
from ..agents.agent_setup import initialize_agents

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("/", response_model=list[EventResponse])
def get_events(
    category: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Event).filter(Event.status == "published")

    if category:
        query = query.filter(Event.category == category)

    return query.order_by(Event.start_time.asc()).all()


@router.get("/{event_id}", response_model=EventResponse)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
):
    event = (
        db.query(Event)
        .filter(
            Event.id == event_id,
            Event.status == "published",
        )
        .first()
    )

    if not event:
        raise HTTPException(404, "Published event not found.")

    return event


@router.post(
    "/",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_event(
    event_data: EventCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    venue = (
        db.query(Venue)
        .filter(Venue.id == event_data.venue_id)
        .first()
    )

    if not venue:
        raise HTTPException(404, "Venue not found.")

    total_tickets = sum(
        category.total_quantity
        for category in event_data.ticket_categories
    )

    if total_tickets > venue.capacity:
        raise HTTPException(
            400,
            "Total ticket quantity exceeds venue capacity.",
        )

    agents = initialize_agents(db)
    venue_agent = agents["venue_agent"]

    decision = venue_agent.check_availability(
        venue_id=event_data.venue_id,
        start_time=event_data.start_time,
        end_time=event_data.end_time,
        guest_count=total_tickets,
    )

    if not decision["available"]:
        raise HTTPException(
            409,
            decision["reason"],
        )

    event = Event(
        title=event_data.title,
        description=event_data.description,
        category=event_data.category,
        venue_id=event_data.venue_id,
        start_time=event_data.start_time,
        end_time=event_data.end_time,
        check_in_opens_at=event_data.check_in_opens_at,
        check_in_closes_at=event_data.check_in_closes_at,
        status="draft",
    )

    try:
        db.add(event)
        db.flush()

        for category in event_data.ticket_categories:
            db.add(
                TicketCategory(
                    event_id=event.id,
                    name=category.name,
                    price=category.price,
                    total_quantity=category.total_quantity,
                    sold_quantity=0,
                )
            )

        db.commit()
        db.refresh(event)
        return event

    except Exception:
        db.rollback()
        raise


@router.put("/{event_id}", response_model=EventResponse)
def update_event(
    event_id: int,
    event_data: EventUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    event = db.query(Event).filter(Event.id == event_id).first()

    if not event:
        raise HTTPException(404, "Event not found.")

    if event.status in ["cancelled", "completed"]:
        raise HTTPException(
            400,
            "Cancelled or completed events cannot be updated.",
        )

    updates = event_data.model_dump(exclude_unset=True)

    new_venue_id = updates.get("venue_id", event.venue_id)
    new_start = updates.get("start_time", event.start_time)
    new_end = updates.get("end_time", event.end_time)

    if new_end <= new_start:
        raise HTTPException(400, "End time must be after start time.")

    venue = db.query(Venue).filter(Venue.id == new_venue_id).first()

    if not venue:
        raise HTTPException(404, "Venue not found.")

    total_tickets = sum(
        category.total_quantity
        for category in event.ticket_categories
    )

    if total_tickets > venue.capacity:
        raise HTTPException(
            400,
            "Event ticket quantity exceeds venue capacity.",
        )

    agents = initialize_agents(db)

    decision = agents["venue_agent"].check_availability(
        venue_id=new_venue_id,
        start_time=new_start,
        end_time=new_end,
        guest_count=total_tickets,
        exclude_event_id=event.id,
    )

    if not decision["available"]:
        raise HTTPException(409, decision["reason"])

    for field, value in updates.items():
        setattr(event, field, value)

    try:
        db.commit()
        db.refresh(event)
        return event
    except Exception:
        db.rollback()
        raise


@router.patch("/{event_id}/publish", response_model=EventResponse)
def publish_event(
    event_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    event = db.query(Event).filter(Event.id == event_id).first()

    if not event:
        raise HTTPException(404, "Event not found.")

    if event.status != "draft":
        raise HTTPException(
            400,
            "Only draft events can be published.",
        )

    if not event.ticket_categories:
        raise HTTPException(
            400,
            "Create at least one ticket category before publishing.",
        )

    total_tickets = sum(
        category.total_quantity
        for category in event.ticket_categories
    )

    agents = initialize_agents(db)

    decision = agents["venue_agent"].check_availability(
        venue_id=event.venue_id,
        start_time=event.start_time,
        end_time=event.end_time,
        guest_count=total_tickets,
        exclude_event_id=event.id,
    )

    if not decision["available"]:
        raise HTTPException(409, decision["reason"])

    try:
        event.status = "published"
        db.commit()
        db.refresh(event)
        return event
    except Exception:
        db.rollback()
        raise


@router.patch("/{event_id}/cancel")
def cancel_event(
    event_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    event = db.query(Event).filter(Event.id == event_id).first()

    if not event:
        raise HTTPException(404, "Event not found.")

    if event.status == "cancelled":
        raise HTTPException(400, "Event is already cancelled.")

    if event.status == "completed":
        raise HTTPException(400, "Completed events cannot be cancelled.")

    try:
        event.status = "cancelled"

        # Cancel confirmed bookings and invalidate their tickets.
        bookings = (
            db.query(Booking)
            .filter(
                Booking.event_id == event_id,
                Booking.status == "confirmed",
            )
            .all()
        )

        for booking in bookings:
            booking.status = "cancelled"
            booking.refund_amount = booking.total_amount

            for ticket in booking.tickets:
                ticket.status = "cancelled"

        db.commit()

        # Notify attendees after the transaction is committed.
        agents = initialize_agents(db)
        for booking in bookings:
            agents["notification_agent"].send_message(
                receiver="NotificationAgent",
                performative="INFORM",
                content={
                    "action": "event_cancelled",
                    "user_id": booking.user_id,
                    "event_title": event.title,
                },
            )

        return {
            "message": "Event cancelled.",
            "cancelled_bookings": len(bookings),
        }

    except Exception:
        db.rollback()
        raise
