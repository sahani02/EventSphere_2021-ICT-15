
from datetime import datetime, timedelta, timezone

from .base_agent import BaseAgent
from ..models import Event, Venue, VenueHireRequest


def make_comparable(value):
    """Normalize datetimes so SQLite and timezone-aware values can be compared."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


class VenueAgent(BaseAgent):
    """
    VenueAgent makes venue scheduling decisions.

    Goal:
    Prevent double-booking and ensure venue suitability.
    """

    def __init__(self, message_bus, db):
        super().__init__("VenueAgent", message_bus)
        self.db = db

    def check_availability(
        self,
        venue_id: int,
        start_time: datetime,
        end_time: datetime,
        guest_count: int = 1,
        exclude_event_id: int | None = None,
        exclude_hire_id: int | None = None,
    ):
        """Check whether a venue can accommodate a requested booking."""

        venue = self.db.query(Venue).filter(
            Venue.id == venue_id
        ).first()

        if venue is None:
            return {
                "available": False,
                "reason": "Venue not found.",
            }

        if guest_count > venue.capacity:
            return {
                "available": False,
                "reason": (
                    f"Guest count exceeds venue capacity "
                    f"({venue.capacity})."
                ),
            }

        if end_time <= start_time:
            return {
                "available": False,
                "reason": "End time must be after start time.",
            }

        requested_start = make_comparable(start_time)
        requested_end = make_comparable(end_time)

        buffer = timedelta(
            minutes=venue.turnaround_minutes
        )

        # Check existing events.
        events = (
            self.db.query(Event)
            .filter(
                Event.venue_id == venue_id,
                Event.status != "cancelled",
                Event.status != "completed",
            )
            .all()
        )

        for event in events:
            if event.id == exclude_event_id:
                continue

            existing_start = make_comparable(event.start_time)
            existing_end = make_comparable(event.end_time)

            if (
                requested_start < existing_end + buffer
                and requested_end + buffer > existing_start
            ):
                return {
                    "available": False,
                    "reason": (
                        f"Venue conflicts with event "
                        f"'{event.title}'."
                    ),
                    "conflicting_event_id": event.id,
                }

        # Check existing venue hire requests.
        hire_requests = (
            self.db.query(VenueHireRequest)
            .filter(
                VenueHireRequest.venue_id == venue_id,
                VenueHireRequest.status.in_(
                    ["pending", "confirmed", "escalated"]
                ),
            )
            .all()
        )

        for hire in hire_requests:
            if hire.id == exclude_hire_id:
                continue

            existing_start = make_comparable(hire.start_time)
            existing_end = make_comparable(hire.end_time)

            if (
                requested_start < existing_end + buffer
                and requested_end + buffer > existing_start
            ):
                return {
                    "available": False,
                    "reason": (
                        "Venue conflicts with another "
                        "private hire request."
                    ),
                    "conflicting_hire_id": hire.id,
                }

        return {
            "available": True,
            "reason": "Venue is available.",
            "venue_id": venue.id,
            "venue_name": venue.name,
            "capacity": venue.capacity,
        }

    def find_alternatives(
        self,
        start_time: datetime,
        end_time: datetime,
        guest_count: int,
        exclude_venue_id: int | None = None,
    ):
        """Find other venues available for the requested time."""

        venues = self.db.query(Venue).all()
        alternatives = []

        for venue in venues:
            if venue.id == exclude_venue_id:
                continue

            result = self.check_availability(
                venue_id=venue.id,
                start_time=start_time,
                end_time=end_time,
                guest_count=guest_count,
            )

            if result["available"]:
                alternatives.append({
                    "venue_id": venue.id,
                    "venue_name": venue.name,
                    "capacity": venue.capacity,
                    "hourly_hire_rate": float(
                        venue.hourly_hire_rate
                    ),
                })

        return alternatives

    def process_message(self, message: dict):
        """Process requests from other agents."""

        content = message.get("content", {})
        action = content.get("action")

        if action == "check_availability":
            result = self.check_availability(
                venue_id=content["venue_id"],
                start_time=datetime.fromisoformat(
                    content["start_time"]
                ),
                end_time=datetime.fromisoformat(
                    content["end_time"]
                ),
                guest_count=content.get("guest_count", 1),
                exclude_event_id=content.get("exclude_event_id"),
                exclude_hire_id=content.get("exclude_hire_id"),
            )

            return result

        if action == "find_alternatives":
            alternatives = self.find_alternatives(
                start_time=datetime.fromisoformat(
                    content["start_time"]
                ),
                end_time=datetime.fromisoformat(
                    content["end_time"]
                ),
                guest_count=content["guest_count"],
                exclude_venue_id=content.get("venue_id"),
            )

            return {
                "alternatives": alternatives,
                "count": len(alternatives),
            }

        return {
            "status": "refused",
            "reason": "Unsupported venue request.",
        }
