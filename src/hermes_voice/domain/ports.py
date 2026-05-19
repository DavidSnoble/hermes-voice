from abc import ABC, abstractmethod
from uuid import UUID

from hermes_voice.domain.entities import (
    AudioInput,
    AudioOutput,
    Conversation,
    HermesContext,
    Intent,
    Task,
    Transcript,
)


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


class ContextProvider(ABC):
    """Port: Loads the full Hermes startup context (persona + user + env)."""

    @abstractmethod
    async def load(self) -> HermesContext:
        """Load all context sources and return a unified HermesContext."""
        ...


class IntentClassifierPort(ABC):
    """Port: Classifies a user message into an Intent (conversation/quick_tool/delegate)."""

    @abstractmethod
    async def classify(self, transcript: str, conversation: Conversation) -> Intent:
        """Classify the user's intent."""
        ...


class TaskDispatcherPort(ABC):
    """Port: Spawns background sub-agents for delegated tasks."""

    @abstractmethod
    async def dispatch(
        self,
        task_description: str,
        hermes_context: HermesContext,
        conversation: Conversation,
    ) -> Task:
        """Dispatch a background task and return a Task handle."""
        ...

    @abstractmethod
    async def poll(self, task_id: UUID) -> Task | None:
        """Check the status of a background task."""
        ...


class NotificationPort(ABC):
    """Port: Pushes proactive notifications to the user (e.g., task completed)."""

    @abstractmethod
    async def notify(self, message: str, audio: AudioOutput | None = None) -> None:
        """Send a notification. Audio is optional but preferred for voice UX."""
        ...
