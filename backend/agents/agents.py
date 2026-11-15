from datetime import datetime, timedelta
from decimal import Decimal
from backend import models

class BaseAgent:
    def __init__(self, db):
        self.db = db

class VenueAgent(BaseAgent):
    name = "VenueAgent"
    def receive(self, message, bus):
        c = message["content"]
        venue_id = c.get("venue_id")
        start, end = c.get("start_time"), c.get("end_time")
        if not start or not end or end <= start:
            result = {"performative":"REFUSE","reason":"End time must be after start time"}
        else:
            clash = self.db.query(models.Event).filter(
                models.Event.venue_id == venue_id,
                models.Event.status == "published",
                models.Event.start_time < end + timedelta(minutes=30),
                models.Event.end_time > start - timedelta(minutes=30)
            ).first()
            result = ({"performative":"REFUSE","reason":"Venue is unavailable; existing activity or turnaround buffer conflict"}
                      if clash else {"performative":"AGREE","reason":"Venue slot is available"})
        bus.send(self.name, message["sender"], result["performative"], result, message["conversation_id"])
        return result

class BookingAgent(BaseAgent):
    name = "BookingAgent"
    def receive(self, message, bus):
        c = message["content"]
        result = {"performative":"AGREE","reason":"Booking request accepted for processing"}
        bus.send(self.name, message["sender"], result["performative"], result, message["conversation_id"])
        return result

class TicketAgent(BaseAgent):
    name = "TicketAgent"
    def receive(self, message, bus):
        result = {"performative":"AGREE","reason":"Ticket request received"}
        bus.send(self.name, message["sender"], result["performative"], result, message["conversation_id"])
        return result

class WaitlistAgent(BaseAgent):
    name = "WaitlistAgent"
    def receive(self, message, bus):
        result = {"performative":"INFORM","reason":"Waitlist event recorded"}
        bus.send(self.name, message["sender"], result["performative"], result, message["conversation_id"])
        return result
    def expiry_sweep(self):
        now = datetime.utcnow()
        expired = self.db.query(models.WaitlistEntry).filter(
            models.WaitlistEntry.status == "offered",
            models.WaitlistEntry.offer_expires_at < now
        ).all()
        for entry in expired:
            entry.status = "expired"
        self.db.commit()
        return len(expired)

class NotificationAgent(BaseAgent):
    name = "NotificationAgent"
    def receive(self, message, bus):
        c = message["content"]
        user_id = c.get("user_id")
        if user_id:
            self.db.add(models.Notification(user_id=user_id,
                title=c.get("title","EventSphere update"),
                message=c.get("message", str(c))))
            self.db.commit()
        return {"performative":"AGREE","reason":"Notification processed"}
