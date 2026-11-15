
from .base_agent import BaseAgent
from ..models import Notification


class NotificationAgent(BaseAgent):
    """
    NotificationAgent manages user notifications.

    Goal:
    Keep users informed about booking and event activities.
    """

    def __init__(self, message_bus, db):
        super().__init__("NotificationAgent", message_bus)
        self.db = db

    def create_notification(
        self,
        user_id: int,
        title: str,
        message: str,
    ):
        """Create and save a notification for a user."""

        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            is_read=False,
        )

        try:
            self.db.add(notification)
            self.db.commit()
            self.db.refresh(notification)

            return {
                "success": True,
                "notification_id": notification.id,
                "user_id": user_id,
                "title": title,
                "message": message,
            }

        except Exception:
            self.db.rollback()
            raise

    def notify_booking_confirmed(
        self,
        user_id: int,
        booking_reference: str,
    ):
        """Notify a user that their booking is confirmed."""

        return self.create_notification(
            user_id=user_id,
            title="Booking Confirmed",
            message=(
                f"Your booking {booking_reference} "
                "has been confirmed successfully."
            ),
        )

    def notify_booking_cancelled(
        self,
        user_id: int,
        booking_reference: str,
        refund_amount: float,
    ):
        """Notify a user about a cancelled booking."""

        return self.create_notification(
            user_id=user_id,
            title="Booking Cancelled",
            message=(
                f"Your booking {booking_reference} has been cancelled. "
                f"Your calculated refund is {refund_amount:.2f}."
            ),
        )

    def notify_event_cancelled(
        self,
        user_id: int,
        event_title: str,
    ):
        """Notify a user that an event has been cancelled."""

        return self.create_notification(
            user_id=user_id,
            title="Event Cancelled",
            message=(
                f"The event '{event_title}' has been cancelled. "
                "Please check your booking for further information."
            ),
        )

    def get_user_notifications(self, user_id: int):
        """Retrieve all notifications belonging to a user."""

        return (
            self.db.query(Notification)
            .filter(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .all()
        )

    def mark_as_read(
        self,
        notification_id: int,
        user_id: int,
    ):
        """Mark a notification as read."""

        notification = (
            self.db.query(Notification)
            .filter(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
            .first()
        )

        if notification is None:
            return {
                "success": False,
                "reason": "Notification not found.",
            }

        try:
            notification.is_read = True
            self.db.commit()

            return {
                "success": True,
                "message": "Notification marked as read.",
            }

        except Exception:
            self.db.rollback()
            raise

    def process_message(self, message: dict):
        """
        Process messages received from other agents.

        The NotificationAgent reacts to INFORM messages
        containing notification requests.
        """

        content = message.get("content", {})
        action = content.get("action")

        if (
            message.get("performative") == "INFORM"
            and action == "create_notification"
        ):
            return self.create_notification(
                user_id=content["user_id"],
                title=content["title"],
                message=content["message"],
            )

        if action == "booking_confirmed":
            return self.notify_booking_confirmed(
                user_id=content["user_id"],
                booking_reference=content["booking_reference"],
            )

        if action == "booking_cancelled":
            return self.notify_booking_cancelled(
                user_id=content["user_id"],
                booking_reference=content["booking_reference"],
                refund_amount=float(content["refund_amount"]),
            )

        if action == "event_cancelled":
            return self.notify_event_cancelled(
                user_id=content["user_id"],
                event_title=content["event_title"],
            )

        return {
            "status": "refused",
            "reason": "Unsupported notification request.",
        }
