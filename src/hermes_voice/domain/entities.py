from dataclasses import dataclass, field
from enum import Enum
from typing import Literal
from uuid import UUID, uuid4


@dataclass(frozen=True)
class AudioInput:
    """Raw audio captured from the user's microphone."""

    data: bytes
    format: str
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


@dataclass
class Persona:
    """The agent's personality. Loaded from Hermes SOUL.md."""

    identity: str = "You are Hermes, a helpful AI assistant."
    voice_style: str = "concise"
    display_personality: str = "default"

    def as_system_prompt_fragment(self) -> str:
        lines = [self.identity]
        if self.voice_style == "concise":
            lines.append(
                "Keep responses VERY short (1-3 sentences). Speak in a natural, "
                "conversational way suitable for text-to-speech while the user drives."
            )
        return "\n".join(lines)


@dataclass
class UserContext:
    """Everything known about the user — loaded from Hermes memories/USER.md."""

    name: str = "User"
    location: str = ""
    timezone: str = "UTC"
    job: str = ""
    preferences: dict[str, str] = field(default_factory=dict)
    facts: list[str] = field(default_factory=list)
    adhd_scaffolding: bool = False

    def as_system_prompt_fragment(self) -> str:
        lines = [f"You are assisting {self.name}."]
        if self.location:
            lines.append(f"Location: {self.location} (timezone: {self.timezone}).")
        if self.job:
            lines.append(f"Occupation: {self.job}.")
        if self.facts:
            lines.append("Known facts:")
            for fact in self.facts:
                lines.append(f"  • {fact}")
        if self.adhd_scaffolding:
            lines.append(
                "This user has ADHD and benefits from direct answers, external scaffolding, "
                "and proactive check-ins. Be concise and action-oriented."
            )
        return "\n".join(lines)


@dataclass
class AgentContext:
    """Lightweight context for the voice agent — personality + user, NOT all tools."""

    persona: Persona = field(default_factory=Persona)
    user: UserContext = field(default_factory=UserContext)

    def build_system_prompt(self) -> str:
        return (
            self.persona.as_system_prompt_fragment()
            + "\n\n"
            + self.user.as_system_prompt_fragment()
            + "\n\n"
            + "You have access to a small set of fast tools: web_search, file_read. "
            "For anything complex (coding, multi-step research, system changes), "
            "say you're delegating to Hermes and a background task will handle it."
        )


class IntentType(Enum):
    CONVERSATION = "conversation"
    QUICK_TOOL = "quick_tool"
    DELEGATE = "delegate"


@dataclass
class Intent:
    intent_type: IntentType
    confidence: float = 1.0
    reasoning: str = ""


@dataclass
class Task:
    """A background task delegated to the Hermes gateway."""

    id: str = ""  # Hermes run_id
    description: str = ""
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    result: str | None = None
    conversation_id: UUID | None = None
