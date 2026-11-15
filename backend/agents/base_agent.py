
from typing import Any, Optional


class BaseAgent:
    """
    Common parent class for all EventSphere agents.

    Each agent has:
    - A unique name
    - A reference to the shared message bus
    - A method for sending messages
    - A method for receiving messages
    """

    def __init__(self, name: str, message_bus):
        self.name = name
        self.message_bus = message_bus

        # Each agent maintains its own simple runtime state.
        self.state = {
            "agent_name": name,
            "messages_received": 0,
            "messages_sent": 0,
        }

        # Register this agent with the message bus.
        self.message_bus.register(self)

    def send_message(
        self,
        receiver: str,
        performative: str,
        content: dict[str, Any],
        conversation_id: Optional[str] = None,
    ):
        """Send a message through the shared message bus."""

        self.state["messages_sent"] += 1

        return self.message_bus.send(
            sender=self.name,
            receiver=receiver,
            performative=performative,
            content=content,
            conversation_id=conversation_id,
        )

    def receive_message(self, message: dict):
        """
        Receive and process a message.

        Child agents can override process_message()
        to implement their own decision-making rules.
        """

        self.state["messages_received"] += 1

        return self.process_message(message)

    def process_message(self, message: dict):
        """Default message-processing behaviour."""

        return {
            "status": "received",
            "agent": self.name,
            "message": "Message received successfully.",
        }

    def get_state(self) -> dict:
        """Return the current runtime state of this agent."""

        return self.state.copy()
