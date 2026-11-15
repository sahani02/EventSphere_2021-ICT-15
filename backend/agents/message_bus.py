
import uuid
from datetime import datetime, timezone

from ..models import AgentMessage


class MessageBus:
    """
    Central communication system for EventSphere agents.

    Messages are:
    1. Created as structured JSON data.
    2. Saved in the database.
    3. Delivered to the receiving agent.
    """

    ALLOWED_PERFORMATIVES = {
        "REQUEST",
        "AGREE",
        "REFUSE",
        "PROPOSE",
        "INFORM",
        "FAILURE",
    }

    def __init__(self, db):
        self.db = db
        self.agents = {}

    def register(self, agent):
        """Register an agent with the message bus."""

        self.agents[agent.name] = agent

    def send(
        self,
        sender: str,
        receiver: str,
        performative: str,
        content: dict,
        conversation_id: str | None = None,
    ):
        """Create, persist and deliver an agent message."""

        performative = performative.upper()

        if performative not in self.ALLOWED_PERFORMATIVES:
            raise ValueError(
                f"Unsupported performative: {performative}"
            )

        if not isinstance(content, dict):
            raise ValueError("Message content must be a JSON object.")

        if conversation_id is None:
            conversation_id = str(uuid.uuid4())

        message_id = str(uuid.uuid4())

        message_data = {
            "message_id": message_id,
            "sender": sender,
            "receiver": receiver,
            "performative": performative,
            "conversation_id": conversation_id,
            "content": content,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Save every message for traceability.
        database_message = AgentMessage(
            message_id=message_id,
            sender=sender,
            receiver=receiver,
            performative=performative,
            conversation_id=conversation_id,
            content=content,
        )

        try:
            self.db.add(database_message)
            self.db.commit()
            self.db.refresh(database_message)

        except Exception:
            self.db.rollback()
            raise

        # Deliver to the receiver if it is registered.
        receiver_agent = self.agents.get(receiver)

        if receiver_agent is not None:
            try:
                response = receiver_agent.receive_message(message_data)

                return {
                    "message": message_data,
                    "delivered": True,
                    "response": response,
                }

            except Exception as exc:
                # Record delivery failure as another agent message.
                self._record_failure(
                    sender=receiver,
                    receiver=sender,
                    conversation_id=conversation_id,
                    error=str(exc),
                )

                return {
                    "message": message_data,
                    "delivered": False,
                    "error": str(exc),
                }

        return {
            "message": message_data,
            "delivered": False,
            "error": f"Agent '{receiver}' is not registered.",
        }

    def _record_failure(
        self,
        sender: str,
        receiver: str,
        conversation_id: str,
        error: str,
    ):
        """Persist a message-delivery failure."""

        failure = AgentMessage(
            message_id=str(uuid.uuid4()),
            sender=sender,
            receiver=receiver,
            performative="FAILURE",
            conversation_id=conversation_id,
            content={
                "error": error,
                "reason": "Agent message processing failed.",
            },
        )

        try:
            self.db.add(failure)
            self.db.commit()
        except Exception:
            self.db.rollback()

    def get_conversation(self, conversation_id: str):
        """Retrieve all messages belonging to a conversation."""

        return (
            self.db.query(AgentMessage)
            .filter(
                AgentMessage.conversation_id == conversation_id
            )
            .order_by(AgentMessage.created_at.asc())
            .all()
        )

    def get_message_history(self, limit: int = 100):
        """Retrieve the latest agent messages."""

        return (
            self.db.query(AgentMessage)
            .order_by(AgentMessage.created_at.desc())
            .limit(limit)
            .all()
        )
