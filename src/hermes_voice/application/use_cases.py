from uuid import UUID, uuid4

from hermes_voice.domain.entities import (
    AudioInput,
    AudioOutput,
    Conversation,
    HermesContext,
    IntentType,
    Message,
    Task,
    Transcript,
)
from hermes_voice.domain.ports import (
    ContextProvider,
    ConversationRepository,
    IntentClassifierPort,
    LLMPort,
    NotificationPort,
    STTPort,
    TaskDispatcherPort,
    TTSPort,
)


class ProcessVoiceMessage:
    """
    Core use case: turn user audio into assistant audio.

    Orchestrates STT → Intent Classification → Route → Response.
    """

    def __init__(
        self,
        stt: STTPort,
        llm: LLMPort,
        tts: TTSPort,
        repository: ConversationRepository,
        context_provider: ContextProvider,
        classifier: IntentClassifierPort,
        dispatcher: TaskDispatcherPort,
        notifier: NotificationPort | None = None,
    ) -> None:
        self._stt = stt
        self._llm = llm
        self._tts = tts
        self._repository = repository
        self._context_provider = context_provider
        self._classifier = classifier
        self._dispatcher = dispatcher
        self._notifier = notifier

    async def execute(
        self, audio: AudioInput, conversation_id: UUID | None = None
    ) -> tuple[AudioOutput, Conversation, Task | None]:
        """
        1. Transcribe audio to text.
        2. Load or create conversation + Hermes context.
        3. Classify intent.
        4. Route to fast response or background delegation.
        5. Synthesize response audio.
        6. Persist conversation.
        """
        # 1. STT
        transcript: Transcript = await self._stt.transcribe(audio)

        # 2. Load context + conversation
        hermes_context: HermesContext = await self._context_provider.load()
        system_prompt = hermes_context.build_system_prompt(voice_mode=True)

        conversation: Conversation
        if conversation_id:
            existing = await self._repository.get(conversation_id)
            conversation = existing if existing else Conversation(id=conversation_id)
        else:
            conversation = Conversation(id=uuid4())

        conversation.add_message("user", transcript.text)

        # 3. Classify intent
        intent = await self._classifier.classify(transcript.text, conversation)

        # 4. Route
        task: Task | None = None
        if intent.intent_type == IntentType.DELEGATE:
            # Immediate ack + background dispatch
            ack_text = self._pick_acknowledgement(transcript.text)
            conversation.add_message("assistant", ack_text)
            await self._repository.save(conversation)

            task = await self._dispatcher.dispatch(
                task_description=transcript.text,
                hermes_context=hermes_context,
                conversation=conversation,
            )
            response_text = ack_text
        else:
            # Fast inline response
            response_text = await self._llm.generate(
                conversation, system_prompt=system_prompt
            )
            conversation.add_message("assistant", response_text)
            await self._repository.save(conversation)

        # 5. TTS
        audio_output: AudioOutput = await self._tts.synthesize(response_text)

        return audio_output, conversation, task

    def _pick_acknowledgement(self, user_text: str) -> str:
        """Pick an immediate voice ack for delegated tasks."""
        lower = user_text.lower()
        if any(w in lower for w in ("research", "look up", "find out", "compare")):
            return "I'll research that for you. Keep talking, I'll let you know when I'm done."
        if any(w in lower for w in ("refactor", "code", "rewrite", "fix", "debug")):
            return "I'm on the code task. Chat with me while I work."
        if any(w in lower for w in ("write", "draft", "generate", "create")):
            return "I'll start writing that up. What else is on your mind?"
        return "I'm on it. Keep talking to me while I work."


class PollBackgroundTask:
    """
    Polls background tasks and notifies the user when complete.
    """

    def __init__(
        self,
        dispatcher: TaskDispatcherPort,
        notifier: NotificationPort,
        tts: TTSPort,
        repository: ConversationRepository,
    ) -> None:
        self._dispatcher = dispatcher
        self._notifier = notifier
        self._tts = tts
        self._repository = repository

    async def poll_and_notify(self, task_id: UUID) -> None:
        task = await self._dispatcher.poll(task_id)
        if task and task.status == "completed" and task.result:
            # Synthesize completion message
            completion_msg = f"By the way, I finished: {task.result[:200]}"
            if len(task.result) > 200:
                completion_msg += "... Want me to read the full details?"

            audio = await self._tts.synthesize(completion_msg)
            await self._notifier.notify(completion_msg, audio=audio)

            # Persist in conversation if linked
            if task.conversation_id:
                conv = await self._repository.get(task.conversation_id)
                if conv:
                    conv.add_message("assistant", f"[Background task completed] {task.result}")
                    await self._repository.save(conv)
