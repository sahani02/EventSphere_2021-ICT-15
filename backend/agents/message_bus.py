
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4


class MessageBus:
    """
    Simple in-memory message bus for communication
    between EventSphere agents.
    """

    def __init__(self):
        self.messages: List[Dict[str, Any]] = []

    def send(
        self,
        sender: str,
        receiver: str,
        performative: str,
        content: dict
    ):
        """
        Send a message from one agent to another.
        """

        message = {
            "id": str(uuid4()),
            "sender": sender,
            "receiver": receiver,
            "performative": performative,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        self.messages.append(message)

        return message

    def receive(self, receiver: str):
        """
        Retrieve messages addressed to an agent.
        """

        received_messages = [
            message
            for message in self.messages
            if message["receiver"] == receiver
        ]

        return received_messages

    def get_all_messages(self):
        """
        Return all messages in the message bus.
        """

        return self.messages

    def clear_messages(self):
        """
        Clear all messages.
        """

        self.messages.clear()
