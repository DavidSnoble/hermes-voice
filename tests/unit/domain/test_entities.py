import pytest
from hermes_voice.domain.entities import (
    AgentContext,
    AudioInput,
    AudioOutput,
    Conversation,
    Intent,
    IntentType,
    Message,
    Persona,
    Role,
    Task,
    Transcript,
    UserContext,
)


class TestConversation:
    def test_add_message(self):
        conv = Conversation()
        conv.add_message(Role.USER, "Hello")
        assert len(conv.messages) == 1
        assert conv.messages[0].content == "Hello"
        assert conv.messages[0].role == Role.USER

    def test_as_llm_context_with_system_prompt(self):
        conv = Conversation()
        conv.add_message(Role.USER, "Hi")
        context = conv.as_llm_context(system_prompt="You are helpful.")
        assert context[0] == {"role": "system", "content": "You are helpful."}
        assert context[1] == {"role": "user", "content": "Hi"}

    def test_as_llm_context_without_system_prompt(self):
        conv = Conversation()
        conv.add_message(Role.ASSISTANT, "Hey")
        context = conv.as_llm_context()
        assert len(context) == 1
        assert context[0] == {"role": "assistant", "content": "Hey"}


class TestAudioInput:
    def test_audio_input_creation(self):
        audio = AudioInput(data=b"\x00\x01", format="webm/opus", sample_rate=48000, channels=1)
        assert audio.data == b"\x00\x01"
        assert audio.format == "webm/opus"


class TestTranscript:
    def test_transcript_defaults(self):
        t = Transcript(text="Hello")
        assert t.confidence == 1.0
        assert t.is_final is True


class TestPersona:
    def test_default_persona(self):
        p = Persona()
        assert "Hermes" in p.identity
        assert p.voice_style == "concise"

    def test_persona_prompt_fragment(self):
        p = Persona(identity="You are Hermes.")
        fragment = p.as_system_prompt_fragment()
        assert "Hermes" in fragment
        assert "concise" in fragment


class TestUserContext:
    def test_default_user(self):
        u = UserContext()
        assert u.name == "User"
        assert u.adhd_scaffolding is False

    def test_user_prompt_fragment_with_facts(self):
        u = UserContext(
            name="David",
            location="Calgary",
            timezone="America/Edmonton",
            facts=["Has ADHD", "Loves Zig"],
            adhd_scaffolding=True,
        )
        fragment = u.as_system_prompt_fragment()
        assert "David" in fragment
        assert "Calgary" in fragment
        assert "ADHD" in fragment
        assert "scaffolding" in fragment


class TestAgentContext:
    def test_build_system_prompt(self):
        ctx = AgentContext(
            persona=Persona(identity="You are Hermes."),
            user=UserContext(name="David"),
        )
        prompt = ctx.build_system_prompt()
        assert "Hermes" in prompt
        assert "David" in prompt
        assert "small set of fast tools" in prompt


class TestIntent:
    def test_intent_classification(self):
        i = Intent(IntentType.DELEGATE, confidence=0.95, reasoning="Multi-step task")
        assert i.intent_type == IntentType.DELEGATE
        assert i.confidence == 0.95


class TestTask:
    def test_task_defaults(self):
        t = Task(description="Refactor auth")
        assert t.status == "pending"
        assert t.result is None
