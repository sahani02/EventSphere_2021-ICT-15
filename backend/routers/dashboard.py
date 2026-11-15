
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import (
    User,
    Venue,
    Event,
    Booking,
    Ticket,
    TicketCategory,
    AgentMessage,
    VenueHireRequest,
)
from ..security import get_current_staff

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
def get_dashboard_summary(
    db: Session = Depends(get_db),
    staff=Depends(get_current_staff),
):
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_venues = db.query(func.count(Venue.id)).scalar() or 0
    total_events = db.query(func.count(Event.id)).scalar() or 0
    total_bookings = db.query(func.count(Booking.id)).scalar() or 0

    confirmed_bookings = (
        db.query(func.count(Booking.id))
        .filter(Booking.status == "confirmed")
        .scalar()
        or 0
    )

    total_revenue = (
        db.query(func.sum(Booking.total_amount))
        .filter(Booking.status == "confirmed")
        .scalar()
        or 0
    )

    tickets_sold = (
        db.query(func.sum(TicketCategory.sold_quantity))
        .scalar()
        or 0
    )

    tickets_checked_in = (
        db.query(func.count(Ticket.id))
        .filter(Ticket.status == "used")
        .scalar()
        or 0
    )

    total_capacity = (
        db.query(func.sum(TicketCategory.total_quantity))
        .scalar()
        or 0
    )

    pending_hire_requests = (
        db.query(func.count(VenueHireRequest.id))
        .filter(
            VenueHireRequest.status.in_(
                ["pending", "escalated"]
            )
        )
        .scalar()
        or 0
    )

    return {
        "users": {
            "total": total_users,
        },
        "venues": {
            "total": total_venues,
        },
        "events": {
            "total": total_events,
        },
        "bookings": {
            "total": total_bookings,
            "confirmed": confirmed_bookings,
        },
        "sales": {
            "tickets_sold": tickets_sold,
            "revenue": float(total_revenue),
            "currency": "LKR",
        },
        "check_ins": {
            "total": tickets_checked_in,
        },
        "capacity": {
            "total": total_capacity,
            "sold": tickets_sold,
            "remaining": max(0, total_capacity - tickets_sold),
        },
        "venue_hire": {
            "pending_or_escalated": pending_hire_requests,
        },
    }


@router.get("/events")
def get_event_statistics(
    db: Session = Depends(get_db),
    staff=Depends(get_current_staff),
):
    events = db.query(Event).order_by(Event.start_time.desc()).all()

    results = []

    for event in events:
        sold = (
            db.query(func.sum(TicketCategory.sold_quantity))
            .filter(TicketCategory.event_id == event.id)
            .scalar()
            or 0
        )

        capacity = (
            db.query(func.sum(TicketCategory.total_quantity))
            .filter(TicketCategory.event_id == event.id)
            .scalar()
            or 0
        )

        checked_in = (
            db.query(func.count(Ticket.id))
            .filter(
                Ticket.event_id == event.id,
                Ticket.status == "used",
            )
            .scalar()
            or 0
        )

        results.append({
            "event_id": event.id,
            "title": event.title,
            "status": event.status,
            "venue_id": event.venue_id,
            "start_time": event.start_time,
            "end_time": event.end_time,
            "ticket_capacity": capacity,
            "tickets_sold": sold,
            "tickets_remaining": max(0, capacity - sold),
            "check_ins": checked_in,
        })

    return results


@router.get("/agent-messages")
def get_agent_messages(
    limit: int = 100,
    db: Session = Depends(get_db),
    staff=Depends(get_current_staff),
):
    limit = max(1, min(limit, 500))

    messages = (
        db.query(AgentMessage)
        .order_by(AgentMessage.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "message_id": message.message_id,
            "sender": message.sender,
            "receiver": message.receiver,
            "performative": message.performative,
            "conversation_id": message.conversation_id,
            "content": message.content,
            "created_at": message.created_at,
        }
        for message in messages
    ]
