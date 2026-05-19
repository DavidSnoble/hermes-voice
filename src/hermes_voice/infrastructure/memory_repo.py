from uuid import UUID

from hermes_voice.domain.entities import Conversation
from hermes_voice.domain.ports import ConversationRepository


class InMemoryConversationRepository(ConversationRepository):
    """Simple in-memory conversation store."""

    def __init__(self) -> None:
        self._store: dict[UUID, Conversation] = {}

    async def get(self, conversation_id: UUID) -> Conversation | None:
        return self._store.get(conversation_id)

    async def save(self, conversation: Conversation) -> None:
        self._store[conversation.id] = conversation

    async def delete(self, conversation_id: UUID) -> None:
        self._store.pop(conversation_id, None)
