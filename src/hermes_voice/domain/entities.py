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


@dataclass
class Persona:
    """The agent's personality and voice."""

    identity: str = "You are a helpful AI assistant."
    voice_style: str = "concise"  # concise, friendly, technical
    quirks: list[str] = field(default_factory=list)
    display_personality: str = "default"  # kawaii, pirate, etc.

    def as_system_prompt_fragment(self) -> str:
        lines = [self.identity]
        if self.voice_style == "concise":
            lines.append("Keep responses short and to the point. Use brief sentences suitable for text-to-speech.")
        elif self.voice_style == "friendly":
            lines.append("Be warm and conversational. Speak like a helpful friend.")
        if self.quirks:
            lines.append("Personality notes: " + "; ".join(self.quirks))
        return "\n".join(lines)


@dataclass
class UserContext:
    """Everything known about the user — loaded from Hermes USER.md + MEMORY.md."""

    name: str = "User"
    location: str = ""
    timezone: str = "UTC"
    job: str = ""
    salary: float = 0.0
    preferences: dict[str, str] = field(default_factory=dict)
    facts: list[str] = field(default_factory=list)
    adhd_scaffolding: bool = False
    tools_available: list[str] = field(default_factory=list)

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
                "This user has ADHD and benefits from external scaffolding, "
                "direct answers, and proactive check-ins."
            )
        if self.preferences:
            lines.append("Preferences:")
            for k, v in self.preferences.items():
                lines.append(f"  • {k}: {v}")
        return "\n".join(lines)


@dataclass
class HermesContext:
    """Complete Hermes startup context — persona + user + env."""

    persona: Persona = field(default_factory=Persona)
    user: UserContext = field(default_factory=UserContext)
    environment_notes: str = ""
    config: dict = field(default_factory=dict)

    def build_system_prompt(self, voice_mode: bool = True) -> str:
        """Build the full system prompt that makes this agent feel like Hermes."""
        parts: list[str] = []

        parts.append(self.persona.as_system_prompt_fragment())
        parts.append("")
        parts.append(self.user.as_system_prompt_fragment())

        if self.environment_notes:
            parts.append("")
            parts.append("Environment context:")
            parts.append(self.environment_notes)

        if voice_mode:
            parts.append("")
            parts.append(
                "Voice mode instructions: "
                "You are responding via text-to-speech while the user is driving. "
                "Keep responses SHORT (1-3 sentences). Confirm actions immediately. "
                "For complex tasks, say 'I'm on it' and delegate to background workers."
            )

        return "\n".join(parts)


class IntentType(Enum):
    CONVERSATION = "conversation"   # chitchat, simple Q&A, no tools
    QUICK_TOOL = "quick_tool"       # single tool call, <5s
    DELEGATE = "delegate"           # complex multi-step task


@dataclass
class Intent:
    intent_type: IntentType
    confidence: float = 1.0
    reasoning: str = ""


@dataclass
class Task:
    """A background task delegated to a sub-agent."""

    id: UUID = field(default_factory=uuid4)
    description: str = ""
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    result: str | None = None
    conversation_id: UUID | None = None
