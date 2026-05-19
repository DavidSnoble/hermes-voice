from abc import ABC, abstractmethod
from uuid import UUID

from hermes_voice.domain.entities import AudioInput, AudioOutput, Conversation, Transcript


class STTPort(ABC):
    """Port: Speech-to-Text. Converts audio into text."""

    @abstractmethod
    async def transcribe(self, audio: AudioInput) -> Transcript:
        """Convert audio to transcript."""
        ...


class TTSPort(ABC):
    """Port: Text-to-Speech. Converts text into audio."""

    @abstractmethod
    async def synthesize(self, text: str) -> AudioOutput:
        """Convert text to spoken audio."""
        ...


class LLMPort(ABC):
    """Port: Language Model. Generates a text response given a conversation."""

    @abstractmethod
    async def generate(self, conversation: Conversation, system_prompt: str | None = None) -> str:
        """Generate assistant response text."""
        ...


class ConversationRepository(ABC):
    """Port: Persistence for conversation state."""

    @abstractmethod
    async def get(self, conversation_id: UUID) -> Conversation | None:
        ...

    @abstractmethod
    async def save(self, conversation: Conversation) -> None:
        ...

    @abstractmethod
    async def delete(self, conversation_id: UUID) -> None:
        ...
