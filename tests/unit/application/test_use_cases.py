import pytest
from uuid import uuid4

from hermes_voice.application.use_cases import PollBackgroundTask, ProcessVoiceMessage
from hermes_voice.domain.entities import (
    AgentContext,
    AudioInput,
    AudioOutput,
    Conversation,
    Intent,
    IntentType,
    Task,
    Transcript,
    UserContext,
)
from hermes_voice.domain.ports import (
    ContextProvider,
    ConversationRepository,
    HermesGatewayPort,
    IntentClassifierPort,
    LLMPort,
    NotificationPort,
    STTPort,
    TTSPort,
)


class FakeSTT(STTPort):
    def __init__(self, transcript_text: str = "Hello"):
        self._text = transcript_text

    async def transcribe(self, audio: AudioInput) -> Transcript:
        return Transcript(text=self._text, confidence=0.99)


class FakeTTS(TTSPort):
    def __init__(self, audio_data: bytes = b"fake_audio"):
        self._data = audio_data

    async def synthesize(self, text: str) -> AudioOutput:
        return AudioOutput(data=self._data, format="mp3")


class FakeLLM(LLMPort):
    def __init__(self, response: str = "Hi there!"):
        self._response = response

    async def generate(self, conversation: Conversation, system_prompt: str | None = None) -> str:
        return self._response


class FakeRepository(ConversationRepository):
    def __init__(self):
        self.saved: dict = {}

    async def get(self, conversation_id):
        return self.saved.get(conversation_id)

    async def save(self, conversation: Conversation) -> None:
        self.saved[conversation.id] = conversation

    async def delete(self, conversation_id) -> None:
        self.saved.pop(conversation_id, None)


class FakeContextProvider(ContextProvider):
    def __init__(self, context: AgentContext | None = None):
        self._context = context or AgentContext(user=UserContext(name="Test"))

    async def load(self) -> AgentContext:
        return self._context


class FakeClassifier(IntentClassifierPort):
    def __init__(self, intent: Intent):
        self._intent = intent

    async def classify(self, transcript: str, conversation: Conversation) -> Intent:
        return self._intent


class FakeGateway(HermesGatewayPort):
    def __init__(self):
        self.dispatched: list = []
        self._tasks: dict = {}

    async def delegate(self, task_description: str, conversation_history: list[dict[str, str]]) -> Task:
        task = Task(id="run_test_123", description=task_description)
        self.dispatched.append(task)
        self._tasks[task.id] = task
        return task

    async def poll(self, task_id: str):
        return self._tasks.get(task_id)


class FakeNotifier(NotificationPort):
    def __init__(self):
        self.notifications: list = []

    async def notify(self, message: str, audio: AudioOutput | None = None) -> None:
        self.notifications.append((message, audio))


@pytest.mark.unit
class TestProcessVoiceMessage:
    async def test_fast_conversation_response(self):
        stt = FakeSTT("How are you?")
        tts = FakeTTS(b"hello_audio")
        llm = FakeLLM("I'm doing great!")
        repo = FakeRepository()
        ctx = FakeContextProvider()
        classifier = FakeClassifier(Intent(IntentType.CONVERSATION))
        gateway = FakeGateway()

        use_case = ProcessVoiceMessage(
            stt=stt, llm=llm, tts=tts, repository=repo,
            context_provider=ctx, classifier=classifier, gateway=gateway,
        )

        audio = AudioInput(data=b"\x00", format="webm")
        output, conversation, task = await use_case.execute(audio)

        assert output.data == b"hello_audio"
        assert len(conversation.messages) == 2
        assert conversation.messages[1].content == "I'm doing great!"
        assert task is None
        assert conversation.id in repo.saved

    async def test_delegates_complex_task_to_hermes(self):
        stt = FakeSTT("Refactor the auth module to use JWT")
        tts = FakeTTS(b"ack_audio")
        llm = FakeLLM("should not be called")
        repo = FakeRepository()
        ctx = FakeContextProvider()
        classifier = FakeClassifier(Intent(IntentType.DELEGATE))
        gateway = FakeGateway()

        use_case = ProcessVoiceMessage(
            stt=stt, llm=llm, tts=tts, repository=repo,
            context_provider=ctx, classifier=classifier, gateway=gateway,
        )

        audio = AudioInput(data=b"\x00", format="webm")
        output, conversation, task = await use_case.execute(audio)

        # Should get immediate ack, not LLM response
        assert task is not None
        assert task.id == "run_test_123"
        assert len(gateway.dispatched) == 1
        assert "refactor" in gateway.dispatched[0].description.lower()
        assert len(conversation.messages) == 2  # user + assistant ack
        assert conversation.id in repo.saved

    async def test_continues_existing_conversation(self):
        stt = FakeSTT("And another thing")
        tts = FakeTTS()
        llm = FakeLLM("Sure.")
        repo = FakeRepository()
        ctx = FakeContextProvider()
        classifier = FakeClassifier(Intent(IntentType.CONVERSATION))
        gateway = FakeGateway()

        existing = Conversation()
        existing.add_message("user", "Hello")
        existing.add_message("assistant", "Hi!")
        await repo.save(existing)

        use_case = ProcessVoiceMessage(
            stt=stt, llm=llm, tts=tts, repository=repo,
            context_provider=ctx, classifier=classifier, gateway=gateway,
        )
        audio = AudioInput(data=b"\x00", format="webm")
        _, conversation, _ = await use_case.execute(audio, conversation_id=existing.id)

        assert len(conversation.messages) == 4


@pytest.mark.unit
class TestPollBackgroundTask:
    async def test_notifies_on_completion(self):
        gateway = FakeGateway()
        notifier = FakeNotifier()
        tts = FakeTTS(b"done_audio")
        repo = FakeRepository()

        poller = PollBackgroundTask(gateway, notifier, tts, repo)

        # Simulate a completed task
        task = Task(id="run_abc", description="Test", status="completed", result="Found 3 options.")
        gateway._tasks["run_abc"] = task

        await poller.poll_and_notify("run_abc")

        assert len(notifier.notifications) == 1
        msg, audio = notifier.notifications[0]
        assert "Found 3 options" in msg
        assert audio is not None
