from dataclasses import dataclass, field
from enum import Enum
from typing import Literal
from uuid import UUID, uuid4


@dataclass(frozen=True)
class AudioInput:
    """Raw audio captured from the user's microphone."""

    data: bytes
    format: str  # e.g. "webm/opus", "wav", "mp3"
    sample_rate: int = 48000
    channels: int = 1


@dataclass(frozen=True)
class AudioOutput:
    """Synthesized audio returned to the user."""

    data: bytes
    format: str = "mp3"
    sample_rate: int = 24000


@dataclass(frozen=True)
class Transcript:
    """Result of speech-to-text conversion."""

    text: str
    confidence: float = 1.0
    is_final: bool = True


class Role(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass(frozen=True)
class Message:
    """A single turn in a conversation."""

    role: Role | Literal["user", "assistant", "system"]
    content: str


@dataclass
class Conversation:
    """Aggregated context for an LLM interaction."""

    id: UUID = field(default_factory=uuid4)
    messages: list[Message] = field(default_factory=list)

    def add_message(self, role: Role | Literal["user", "assistant", "system"], content: str) -> None:
        self.messages.append(Message(role=role, content=content))

    def as_llm_context(self, system_prompt: str | None = None) -> list[dict[str, str]]:
        context: list[dict[str, str]] = []
        if system_prompt:
            context.append({"role": "system", "content": system_prompt})
        for msg in self.messages:
            context.append({"role": str(msg.role), "content": msg.content})
        return context
