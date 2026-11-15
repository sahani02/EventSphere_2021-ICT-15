
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Booking, Event, Ticket, TicketCategory
from ..schemas import BookingCreate, BookingResponse
from ..security import get_current_user
from ..agents.agent_setup import initialize_agents

router = APIRouter(prefix="/bookings", tags=["Bookings"])


def comparable_datetime(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@router.post(
    "/",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_booking(
    booking_data: BookingCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    event = (
        db.query(Event)
        .filter(
            Event.id == booking_data.event_id,
            Event.status == "published",
        )
        .first()
    )

    if not event:
        raise HTTPException(
            404,
            "Published event not found.",
        )

    category = (
        db.query(TicketCategory)
        .filter(
            TicketCategory.id == booking_data.ticket_category_id,
            TicketCategory.event_id == event.id,
        )
        .first()
    )

    if not category:
        raise HTTPException(
            404,
            "Ticket category not found for this event.",
        )

    if comparable_datetime(event.start_time) <= datetime.now(timezone.utc):
        raise HTTPException(
            400,
            "Booking is closed because the event has started.",
        )

    agents = initialize_agents(db)
    booking_agent = agents["booking_agent"]

    allocation = booking_agent.reserve_tickets(
        ticket_category_id=category.id,
        quantity=booking_data.quantity,
    )

    if not allocation["success"]:
        raise HTTPException(409, allocation["reason"])

    total_amount = category.price * booking_data.quantity

    booking = Booking(
        booking_reference=f"EVT-{uuid.uuid4().hex[:12].upper()}",
        user_id=current_user.id,
        event_id=event.id,
        ticket_category_id=category.id,
        quantity=booking_data.quantity,
        total_amount=total_amount,
        payment_reference=f"SIM-{uuid.uuid4().hex[:12].upper()}",
        status="confirmed",
        refund_amount=0,
    )

    try:
        db.add(booking)
        db.flush()

        for _ in range(booking_data.quantity):
            ticket = Ticket(
                ticket_code=f"TKT-{uuid.uuid4().hex.upper()}",
                booking_id=booking.id,
                event_id=event.id,
                ticket_category_id=category.id,
                status="valid",
            )
            db.add(ticket)

        db.commit()
        db.refresh(booking)

    except Exception:
        db.rollback()
        raise

    # Notify after the booking transaction succeeds.
    agents["booking_agent"].send_message(
        receiver="NotificationAgent",
        performative="INFORM",
        content={
            "action": "booking_confirmed",
            "user_id": current_user.id,
            "booking_reference": booking.booking_reference,
        },
    )

    return booking


@router.get("/my", response_model=list[BookingResponse])
def get_my_bookings(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return (
        db.query(Booking)
        .filter(Booking.user_id == current_user.id)
        .order_by(Booking.created_at.desc())
        .all()
    )


@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    booking = (
        db.query(Booking)
        .filter(
            Booking.id == booking_id,
            Booking.user_id == current_user.id,
        )
        .first()
    )

    if not booking:
        raise HTTPException(404, "Booking not found.")

    return booking


@router.patch("/{booking_id}/cancel")
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    booking = (
        db.query(Booking)
        .filter(
            Booking.id == booking_id,
            Booking.user_id == current_user.id,
        )
        .first()
    )

    if not booking:
        raise HTTPException(404, "Booking not found.")

    if booking.status != "confirmed":
        raise HTTPException(
            400,
            "Only confirmed bookings can be cancelled.",
        )

    event = db.query(Event).filter(Event.id == booking.event_id).first()

    if not event or event.status == "cancelled":
        raise HTTPException(
            400,
            "This booking cannot be cancelled through this endpoint.",
        )

    now = datetime.now(timezone.utc)
    event_start = comparable_datetime(event.start_time)

    hours_before_event = (
        event_start - now
    ).total_seconds() / 3600

    if hours_before_event > 48:
        refund_percentage = 1.0
    elif hours_before_event >= 24:
        refund_percentage = 0.5
    else:
        refund_percentage = 0.0

    refund_amount = booking.total_amount * refund_percentage

    agents = initialize_agents(db)

    release = agents["booking_agent"].release_tickets(
        ticket_category_id=booking.ticket_category_id,
        quantity=booking.quantity,
    )

    if not release["success"]:
        raise HTTPException(
            409,
            release["reason"],
        )

    try:
        booking.status = "cancelled"
        booking.refund_amount = refund_amount
        booking.cancelled_at = now

        for ticket in booking.tickets:
            ticket.status = "cancelled"

        db.commit()
        db.refresh(booking)

    except Exception:
        db.rollback()
        raise

    # Inform the waitlist that inventory has been released.
    agents["booking_agent"].send_message(
        receiver="WaitlistAgent",
        performative="INFORM",
        content={
            "action": "tickets_released",
            "ticket_category_id": booking.ticket_category_id,
            "quantity": booking.quantity,
        },
    )

    agents["booking_agent"].send_message(
        receiver="NotificationAgent",
        performative="INFORM",
        content={
            "action": "booking_cancelled",
            "user_id": current_user.id,
            "booking_reference": booking.booking_reference,
            "refund_amount": float(refund_amount),
        },
    )

    return {
        "message": "Booking cancelled successfully.",
        "booking_reference": booking.booking_reference,
        "refund_amount": refund_amount,
        "refund_percentage": refund_percentage * 100,
        "status": booking.status,
    }
