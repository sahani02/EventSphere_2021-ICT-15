
from .message_bus import MessageBus
from .venue_agent import VenueAgent
from .booking_agent import BookingAgent
from .ticket_agent import TicketAgent
from .waitlist_agent import WaitlistAgent
from .notification_agent import NotificationAgent


def initialize_agents(db):
    """
    Initialize all EventSphere agents
    using one shared message bus.
    """

    message_bus = MessageBus(db)

    venue_agent = VenueAgent(message_bus, db)
    booking_agent = BookingAgent(message_bus, db)
    ticket_agent = TicketAgent(message_bus, db)
    waitlist_agent = WaitlistAgent(message_bus, db)
    notification_agent = NotificationAgent(message_bus, db)

    return {
        "message_bus": message_bus,
        "venue_agent": venue_agent,
        "booking_agent": booking_agent,
        "ticket_agent": ticket_agent,
        "waitlist_agent": waitlist_agent,
        "notification_agent": notification_agent,
    }
