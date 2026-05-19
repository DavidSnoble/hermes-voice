from abc import ABC, abstractmethod
from uuid import UUID

from hermes_voice.domain.entities import (
    AgentContext,
    AudioInput,
    AudioOutput,
    Conversation,
    Intent,
    Task,
    Transcript,
)


class STTPort(ABC):
    """Port: Speech-to-Text. Converts audio into text."""

    @abstractmethod
    async def transcribe(self, audio: AudioInput) -> Transcript:
        ...


class TTSPort(ABC):
    """Port: Text-to-Speech. Converts text into audio."""

    @abstractmethod
    async def synthesize(self, text: str) -> AudioOutput:
        ...


class LLMPort(ABC):
    """Port: Language Model. Generates a text response given a conversation."""

    @abstractmethod
    async def generate(self, conversation: Conversation, system_prompt: str | None = None) -> str:
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


class ContextProvider(ABC):
    """Port: Loads lightweight Hermes persona + user context."""

    @abstractmethod
    async def load(self) -> AgentContext:
        ...


class IntentClassifierPort(ABC):
    """Port: Classifies a user message into an Intent."""

    @abstractmethod
    async def classify(self, transcript: str, conversation: Conversation) -> Intent:
        ...


class HermesGatewayPort(ABC):
    """
    Port: Delegates complex tasks to the full Hermes gateway via its API server.

    The Hermes gateway (running on port 8642) has ALL tools, skills, memory,
    and the full agent loop. The voice app only calls into it.
    """

    @abstractmethod
    async def delegate(
        self, task_description: str, conversation_history: list[dict[str, str]]
    ) -> Task:
        """
        Start a background task on the Hermes gateway.
        Returns immediately with a task handle containing the Hermes run_id.
        """
        ...

    @abstractmethod
    async def poll(self, task_id: str) -> Task | None:
        """Check the status of a Hermes background task."""
        ...


class NotificationPort(ABC):
    """Port: Pushes proactive notifications to the user."""

    @abstractmethod
    async def notify(self, message: str, audio: AudioOutput | None = None) -> None:
        ...
