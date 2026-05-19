import pytest
from hermes_voice.domain.entities import (
    AudioInput,
    AudioOutput,
    Conversation,
    HermesContext,
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
        assert "helpful" in p.identity.lower()
        assert p.voice_style == "concise"

    def test_persona_prompt_fragment(self):
        p = Persona(identity="You are Hermes.", quirks=["direct", "honest"])
        fragment = p.as_system_prompt_fragment()
        assert "Hermes" in fragment
        assert "direct" in fragment
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


class TestHermesContext:
    def test_build_system_prompt(self):
        ctx = HermesContext(
            persona=Persona(identity="You are Hermes."),
            user=UserContext(name="David"),
            environment_notes="VPS: 4GB RAM",
        )
        prompt = ctx.build_system_prompt(voice_mode=True)
        assert "Hermes" in prompt
        assert "David" in prompt
        assert "VPS" in prompt
        assert "Voice mode" in prompt

    def test_build_system_prompt_no_voice(self):
        ctx = HermesContext(persona=Persona(), user=UserContext())
        prompt = ctx.build_system_prompt(voice_mode=False)
        assert "Voice mode" not in prompt


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
