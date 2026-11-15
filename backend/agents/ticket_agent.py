
from datetime import datetime, timedelta, timezone

from .base_agent import BaseAgent
from ..models import Booking, Event, Ticket


def normalize_datetime(value):
    """Convert a datetime into a comparable UTC datetime."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


class TicketAgent(BaseAgent):
    """
    TicketAgent validates QR tickets and controls admission.

    Goal:
    Prevent duplicate, invalid and unauthorized check-ins.
    """

    def __init__(self, message_bus, db):
        super().__init__("TicketAgent", message_bus)
        self.db = db

    def validate_ticket(
        self,
        ticket_code: str,
        event_id: int,
    ):
        """Check whether a ticket is valid for an event."""

        ticket = (
            self.db.query(Ticket)
            .filter(Ticket.ticket_code == ticket_code)
            .first()
        )

        if ticket is None:
            return {
                "valid": False,
                "reason": "Ticket not found.",
            }

        if ticket.event_id != event_id:
            return {
                "valid": False,
                "reason": "Ticket belongs to a different event.",
            }

        if ticket.status == "cancelled":
            return {
                "valid": False,
                "reason": "This ticket has been cancelled.",
            }

        if ticket.status == "used":
            return {
                "valid": False,
                "reason": "This ticket has already been used.",
            }

        booking = (
            self.db.query(Booking)
            .filter(Booking.id == ticket.booking_id)
            .first()
        )

        if booking is None or booking.status != "confirmed":
            return {
                "valid": False,
                "reason": "The booking is not confirmed.",
            }

        return {
            "valid": True,
            "reason": "Ticket is valid.",
            "ticket_id": ticket.id,
            "ticket_code": ticket.ticket_code,
        }

    def check_in(
        self,
        ticket_code: str,
        event_id: int,
        scan_time: datetime | None = None,
    ):
        """Validate a ticket and mark it as used exactly once."""

        if scan_time is None:
            scan_time = datetime.now(timezone.utc)

        ticket = (
            self.db.query(Ticket)
            .filter(Ticket.ticket_code == ticket_code)
            .first()
        )

        if ticket is None:
            return {
                "success": False,
                "message": "Ticket not found.",
            }

        if ticket.event_id != event_id:
            return {
                "success": False,
                "message": "Ticket belongs to a different event.",
            }

        if ticket.status == "cancelled":
            return {
                "success": False,
                "message": "Ticket has been cancelled.",
            }

        if ticket.status == "used":
            return {
                "success": False,
                "message": "Ticket has already been used.",
            }

        booking = (
            self.db.query(Booking)
            .filter(Booking.id == ticket.booking_id)
            .first()
        )

        if booking is None or booking.status != "confirmed":
            return {
                "success": False,
                "message": "Booking is not confirmed.",
            }

        event = (
            self.db.query(Event)
            .filter(Event.id == event_id)
            .first()
        )

        if event is None:
            return {
                "success": False,
                "message": "Event not found.",
            }

        scan_time = normalize_datetime(scan_time)

        # Use configured check-in times if available.
        # Otherwise, open check-in 2 hours before the event.
        opens_at = (
            event.check_in_opens_at
            if event.check_in_opens_at is not None
            else event.start_time - timedelta(hours=2)
        )

        closes_at = (
            event.check_in_closes_at
            if event.check_in_closes_at is not None
            else event.end_time
        )

        if scan_time < normalize_datetime(opens_at):
            return {
                "success": False,
                "message": "Check-in has not opened yet.",
            }

        if scan_time > normalize_datetime(closes_at):
            return {
                "success": False,
                "message": "The check-in window has closed.",
            }

        # Atomic update: only one concurrent scanner can use
        # a ticket whose status is still 'valid'.
        try:
            result = (
                self.db.query(Ticket)
                .filter(
                    Ticket.id == ticket.id,
                    Ticket.status == "valid",
                )
                .update(
                    {
                        Ticket.status: "used",
                        Ticket.checked_in_at: scan_time,
                    },
                    synchronize_session=False,
                )
            )

            if result != 1:
                self.db.rollback()

                return {
                    "success": False,
                    "message": "Ticket has already been checked in.",
                }

            self.db.commit()

            return {
                "success": True,
                "message": "Check-in successful.",
                "ticket_code": ticket_code,
                "checked_in_at": scan_time.isoformat(),
            }

        except Exception:
            self.db.rollback()
            raise

    def process_message(self, message: dict):
        """Process ticket validation and check-in messages."""

        content = message.get("content", {})
        action = content.get("action")

        if action == "validate_ticket":
            return self.validate_ticket(
                ticket_code=content["ticket_code"],
                event_id=content["event_id"],
            )

        if action == "check_in":
            return self.check_in(
                ticket_code=content["ticket_code"],
                event_id=content["event_id"],
            )

        return {
            "status": "refused",
            "reason": "Unsupported ticket request.",
        }
