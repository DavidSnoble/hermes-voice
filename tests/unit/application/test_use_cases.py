import pytest
from uuid import uuid4

from hermes_voice.application.use_cases import ProcessVoiceMessage
from hermes_voice.domain.entities import AudioInput, AudioOutput, Conversation, Transcript
from hermes_voice.domain.ports import ConversationRepository, LLMPort, STTPort, TTSPort


class FakeSTT(STTPort):
    def __init__(self, transcript_text: str = "Hello") -> None:
        self._text = transcript_text

    async def transcribe(self, audio: AudioInput) -> Transcript:
        return Transcript(text=self._text, confidence=0.99)


class FakeTTS(TTSPort):
    def __init__(self, audio_data: bytes = b"fake_audio") -> None:
        self._data = audio_data

    async def synthesize(self, text: str) -> AudioOutput:
        return AudioOutput(data=self._data, format="mp3")


class FakeLLM(LLMPort):
    def __init__(self, response: str = "Hi there!") -> None:
        self._response = response

    async def generate(self, conversation: Conversation, system_prompt: str | None = None) -> str:
        return self._response


class FakeRepository(ConversationRepository):
    def __init__(self) -> None:
        self.saved: dict = {}

    async def get(self, conversation_id):
        return self.saved.get(conversation_id)

    async def save(self, conversation: Conversation) -> None:
        self.saved[conversation.id] = conversation

    async def delete(self, conversation_id) -> None:
        self.saved.pop(conversation_id, None)


@pytest.mark.unit
class TestProcessVoiceMessage:
    async def test_executes_full_pipeline(self):
        stt = FakeSTT("Hello Hermes")
        tts = FakeTTS(b"hello_audio")
        llm = FakeLLM("Hello David")
        repo = FakeRepository()

        use_case = ProcessVoiceMessage(
            stt=stt, llm=llm, tts=tts, repository=repo, system_prompt="Be friendly."
        )

        audio = AudioInput(data=b"\x00", format="webm")
        output, conversation = await use_case.execute(audio)

        assert output.data == b"hello_audio"
        assert len(conversation.messages) == 2
        assert conversation.messages[0].content == "Hello Hermes"
        assert conversation.messages[1].content == "Hello David"
        assert conversation.id in repo.saved

    async def test_continues_existing_conversation(self):
        stt = FakeSTT("How are you?")
        tts = FakeTTS()
        llm = FakeLLM("I am fine.")
        repo = FakeRepository()

        existing = Conversation()
        existing.add_message("user", "Hello")
        existing.add_message("assistant", "Hi!")
        await repo.save(existing)

        use_case = ProcessVoiceMessage(stt=stt, llm=llm, tts=tts, repository=repo)
        audio = AudioInput(data=b"\x00", format="webm")
        _, conversation = await use_case.execute(audio, conversation_id=existing.id)

        assert len(conversation.messages) == 4
        assert conversation.messages[2].content == "How are you?"
        assert conversation.messages[3].content == "I am fine."
