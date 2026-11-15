
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Ticket, Booking
from ..schemas import TicketResponse, TicketScanRequest, TicketScanResponse
from ..security import get_current_user, get_current_staff
from ..agents.agent_setup import initialize_agents

router = APIRouter(prefix="/tickets", tags=["Tickets"])


@router.get("/my", response_model=list[TicketResponse])
def get_my_tickets(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    bookings = (
        db.query(Booking.id)
        .filter(Booking.user_id == current_user.id)
        .subquery()
    )

    return (
        db.query(Ticket)
        .filter(Ticket.booking_id.in_(bookings))
        .order_by(Ticket.created_at.desc())
        .all()
    )


@router.get("/{ticket_code}", response_model=TicketResponse)
def get_ticket(
    ticket_code: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ticket = (
        db.query(Ticket)
        .join(Booking)
        .filter(
            Ticket.ticket_code == ticket_code,
            Booking.user_id == current_user.id,
        )
        .first()
    )

    if not ticket:
        raise HTTPException(404, "Ticket not found.")

    return ticket


@router.post("/scan", response_model=TicketScanResponse)
def scan_ticket(
    scan_data: TicketScanRequest,
    db: Session = Depends(get_db),
    staff=Depends(get_current_staff),
):
    agents = initialize_agents(db)
    ticket_agent = agents["ticket_agent"]

    result = ticket_agent.check_in(
        ticket_code=scan_data.ticket_code,
        event_id=scan_data.event_id,
    )

    if not result["success"]:
        return {
            "success": False,
            "message": result["message"],
            "ticket_code": scan_data.ticket_code,
        }

    return {
        "success": True,
        "message": result["message"],
        "ticket_code": result["ticket_code"],
        "checked_in_at": result["checked_in_at"],
    }
