
from datetime import datetime, timedelta, timezone

from .base_agent import BaseAgent
from ..models import TicketCategory, WaitlistEntry


class WaitlistAgent(BaseAgent):
    """
    WaitlistAgent manages waiting lists and temporary offers.

    Goal:
    Give waiting users a fair opportunity to purchase
    tickets when availability changes.
    """

    OFFER_DURATION_MINUTES = 15

    def __init__(self, message_bus, db):
        super().__init__("WaitlistAgent", message_bus)
        self.db = db

    def add_to_waitlist(
        self,
        user_id: int,
        event_id: int,
        ticket_category_id: int,
        quantity: int = 1,
    ):
        """Add a user to the waiting list."""

        if quantity < 1 or quantity > 6:
            return {
                "success": False,
                "reason": "Quantity must be between 1 and 6.",
            }

        category = (
            self.db.query(TicketCategory)
            .filter(
                TicketCategory.id == ticket_category_id,
                TicketCategory.event_id == event_id,
            )
            .first()
        )

        if category is None:
            return {
                "success": False,
                "reason": "Ticket category not found for this event.",
            }

        entry = WaitlistEntry(
            user_id=user_id,
            event_id=event_id,
            ticket_category_id=ticket_category_id,
            quantity=quantity,
            status="waiting",
        )

        try:
            self.db.add(entry)
            self.db.commit()
            self.db.refresh(entry)

            return {
                "success": True,
                "waitlist_id": entry.id,
                "status": entry.status,
                "message": "Successfully joined the waitlist.",
            }

        except Exception:
            self.db.rollback()
            raise

    def offer_next(self, ticket_category_id: int):
        """
        Offer available tickets to the earliest eligible
        waiting user.

        This creates a timed offer, not a completed booking.
        Inventory must be checked and reserved atomically
        when the user claims the offer.
        """

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

        available = category.total_quantity - category.sold_quantity

        if available <= 0:
            return {
                "success": False,
                "reason": "No tickets are currently available.",
            }

        # Do not issue another offer while an active offer
        # exists for this category.
        active_offer = (
            self.db.query(WaitlistEntry)
            .filter(
                WaitlistEntry.ticket_category_id == ticket_category_id,
                WaitlistEntry.status == "offered",
            )
            .first()
        )

        if active_offer is not None:
            return {
                "success": False,
                "reason": "An active waitlist offer already exists.",
            }

        waiting_users = (
            self.db.query(WaitlistEntry)
            .filter(
                WaitlistEntry.ticket_category_id == ticket_category_id,
                WaitlistEntry.status == "waiting",
            )
            .order_by(
                WaitlistEntry.created_at.asc(),
                WaitlistEntry.id.asc(),
            )
            .all()
        )

        # Select the first user whose requested quantity fits.
        selected = next(
            (
                entry
                for entry in waiting_users
                if entry.quantity <= available
            ),
            None,
        )

        if selected is None:
            return {
                "success": False,
                "reason": "No waiting user can use the available quantity.",
            }

        now = datetime.now(timezone.utc)

        selected.status = "offered"
        selected.offered_at = now
        selected.offer_expires_at = (
            now + timedelta(minutes=self.OFFER_DURATION_MINUTES)
        )

        try:
            self.db.commit()
            self.db.refresh(selected)

            # Notify the user through the NotificationAgent.
            self.send_message(
                receiver="NotificationAgent",
                performative="INFORM",
                content={
                    "action": "create_notification",
                    "user_id": selected.user_id,
                    "title": "Tickets Available!",
                    "message": (
                        f"{selected.quantity} ticket(s) are available. "
                        f"Your offer expires in "
                        f"{self.OFFER_DURATION_MINUTES} minutes."
                    ),
                },
            )

            return {
                "success": True,
                "waitlist_id": selected.id,
                "user_id": selected.user_id,
                "quantity": selected.quantity,
                "status": selected.status,
                "expires_at": selected.offer_expires_at.isoformat(),
            }

        except Exception:
            self.db.rollback()
            raise

    def expire_offers(self):
        """
        Expire offers whose deadlines have passed.

        After expiring an offer, attempt to offer the tickets
        to the next eligible waiting user.
        """

        now = datetime.now(timezone.utc)

        offered_entries = (
            self.db.query(WaitlistEntry)
            .filter(
                WaitlistEntry.status == "offered",
                WaitlistEntry.offer_expires_at.isnot(None),
            )
            .all()
        )

        expired_categories = set()
        expired_count = 0

        try:
            for entry in offered_entries:
                expiry = entry.offer_expires_at

                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)

                if expiry <= now:
                    entry.status = "expired"
                    expired_categories.add(entry.ticket_category_id)
                    expired_count += 1

            self.db.commit()

        except Exception:
            self.db.rollback()
            raise

        # Try the next user for each category with an expired offer.
        new_offers = []

        for category_id in expired_categories:
            result = self.offer_next(category_id)

            if result.get("success"):
                new_offers.append(result)

        return {
            "expired_count": expired_count,
            "new_offers": new_offers,
        }

    def cancel_waitlist_entry(
        self,
        waitlist_id: int,
        user_id: int,
    ):
        """Allow a user to cancel their own waitlist entry."""

        entry = (
            self.db.query(WaitlistEntry)
            .filter(
                WaitlistEntry.id == waitlist_id,
                WaitlistEntry.user_id == user_id,
            )
            .first()
        )

        if entry is None:
            return {
                "success": False,
                "reason": "Waitlist entry not found.",
            }

        if entry.status not in ["waiting", "offered"]:
            return {
                "success": False,
                "reason": "This entry cannot be cancelled.",
            }

        category_id = entry.ticket_category_id
        was_offered = entry.status == "offered"

        try:
            entry.status = "cancelled"
            self.db.commit()

            if was_offered:
                self.offer_next(category_id)

            return {
                "success": True,
                "message": "Waitlist entry cancelled.",
            }

        except Exception:
            self.db.rollback()
            raise

    def process_message(self, message: dict):
        """React to messages from other agents."""

        content = message.get("content", {})
        action = content.get("action")

        # React to an INFORM message when tickets are released.
        if (
            message.get("performative") == "INFORM"
            and action == "tickets_released"
        ):
            return self.offer_next(
                ticket_category_id=content["ticket_category_id"]
            )

        if action == "add_to_waitlist":
            return self.add_to_waitlist(
                user_id=content["user_id"],
                event_id=content["event_id"],
                ticket_category_id=content["ticket_category_id"],
                quantity=content.get("quantity", 1),
            )

        if action == "expire_offers":
            return self.expire_offers()

        return {
            "status": "refused",
            "reason": "Unsupported waitlist request.",
        }
