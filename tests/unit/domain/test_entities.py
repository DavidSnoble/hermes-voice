import pytest
from hermes_voice.domain.entities import AudioInput, AudioOutput, Conversation, Message, Role, Transcript


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
