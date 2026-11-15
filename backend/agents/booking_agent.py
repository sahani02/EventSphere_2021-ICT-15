
import uuid

from sqlalchemy import update

from .base_agent import BaseAgent
from ..models import Event, TicketCategory


class BookingAgent(BaseAgent):
    """
    BookingAgent controls ticket inventory allocation.

    Goal:
    Prevent overbooking and protect ticket availability.
    """

    def __init__(self, message_bus, db):
        super().__init__("BookingAgent", message_bus)
        self.db = db

    def check_availability(
        self,
        ticket_category_id: int,
        quantity: int,
    ):
        """Check ticket availability without reserving tickets."""

        if quantity <= 0 or quantity > 6:
            return {
                "available": False,
                "reason": "Quantity must be between 1 and 6.",
            }

        category = (
            self.db.query(TicketCategory)
            .filter(TicketCategory.id == ticket_category_id)
            .first()
        )

        if category is None:
            return {
                "available": False,
                "reason": "Ticket category not found.",
            }

        available_quantity = (
            category.total_quantity - category.sold_quantity
        )

        return {
            "available": available_quantity >= quantity,
            "available_quantity": available_quantity,
            "requested_quantity": quantity,
        }

    def reserve_tickets(
        self,
        ticket_category_id: int,
        quantity: int,
    ):
        """
        Atomically allocate ticket inventory.

        Returns success only if the database update
        successfully reserves the requested quantity.

        The caller must commit the transaction after it
        has also created the booking and tickets.
        """

        if quantity <= 0 or quantity > 6:
            return {
                "success": False,
                "reason": "Quantity must be between 1 and 6.",
            }

        category = (
            self.db.query(TicketCategory)
            .filter(TicketCategory.id == ticket_category_id)
            .first()
        )

        if category is None:
            return {
                "success": False,
                "reason": "Ticket category not found.",
            }

        event = (
            self.db.query(Event)
            .filter(Event.id == category.event_id)
            .first()
        )

        if event is None or event.status != "published":
            return {
                "success": False,
                "reason": "This event is not available for booking.",
            }

        # Conditional UPDATE prevents concurrent overbooking.
        statement = (
            update(TicketCategory)
            .where(
                TicketCategory.id == ticket_category_id,
                TicketCategory.sold_quantity + quantity
                <= TicketCategory.total_quantity,
            )
            .values(
                sold_quantity=TicketCategory.sold_quantity + quantity
            )
        )

        try:
            result = self.db.execute(statement)

            if result.rowcount != 1:
                self.db.rollback()

                return {
                    "success": False,
                    "reason": "Not enough tickets are available.",
                }

            # Do not commit here. The booking router should
            # create the booking and tickets in this transaction.
            return {
                "success": True,
                "ticket_category_id": ticket_category_id,
                "quantity": quantity,
                "reservation_reference": str(uuid.uuid4()),
                "message": "Ticket inventory allocated successfully.",
            }

        except Exception:
            self.db.rollback()
            raise

    def release_tickets(
        self,
        ticket_category_id: int,
        quantity: int,
    ):
        """Restore ticket inventory after a cancellation."""

        if quantity <= 0:
            return {
                "success": False,
                "reason": "Invalid quantity.",
            }

        statement = (
            update(TicketCategory)
            .where(
                TicketCategory.id == ticket_category_id,
                TicketCategory.sold_quantity >= quantity,
            )
            .values(
                sold_quantity=TicketCategory.sold_quantity - quantity
            )
        )

        try:
            result = self.db.execute(statement)

            if result.rowcount != 1:
                self.db.rollback()

                return {
                    "success": False,
                    "reason": "Unable to release ticket inventory.",
                }

            return {
                "success": True,
                "released_quantity": quantity,
                "message": "Ticket inventory released successfully.",
            }

        except Exception:
            self.db.rollback()
            raise

    def process_message(self, message: dict):
        """Respond to ticket inventory requests."""

        content = message.get("content", {})
        action = content.get("action")

        if action == "check_availability":
            return self.check_availability(
                ticket_category_id=content["ticket_category_id"],
                quantity=content["quantity"],
            )

        if action == "reserve_tickets":
            return self.reserve_tickets(
                ticket_category_id=content["ticket_category_id"],
                quantity=content["quantity"],
            )

        if action == "release_tickets":
            return self.release_tickets(
                ticket_category_id=content["ticket_category_id"],
                quantity=content["quantity"],
            )

        return {
            "status": "refused",
            "reason": "Unsupported booking request.",
        }
