from uuid import UUID, uuid4

from hermes_voice.domain.entities import (
    AgentContext,
    AudioInput,
    AudioOutput,
    Conversation,
    IntentType,
    Task,
    Transcript,
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


class ProcessVoiceMessage:
    """
    Core use case: turn user audio into assistant audio.

    Orchestrates STT → Intent Classification → Route → Response.

    - CONVERSATION / QUICK_TOOL: fast inline LLM response
    - DELEGATE: immediate voice ack + delegate to Hermes gateway
    """

    def __init__(
        self,
        stt: STTPort,
        llm: LLMPort,
        tts: TTSPort,
        repository: ConversationRepository,
        context_provider: ContextProvider,
        classifier: IntentClassifierPort,
        gateway: HermesGatewayPort,
        notifier: NotificationPort | None = None,
    ) -> None:
        self._stt = stt
        self._llm = llm
        self._tts = tts
        self._repository = repository
        self._context_provider = context_provider
        self._classifier = classifier
        self._gateway = gateway
        self._notifier = notifier

    async def execute(
        self, audio: AudioInput, conversation_id: UUID | None = None
    ) -> tuple[AudioOutput, Conversation, Task | None]:
        # 1. STT
        transcript: Transcript = await self._stt.transcribe(audio)

        # 2. Load context + conversation
        agent_context: AgentContext = await self._context_provider.load()
        system_prompt = agent_context.build_system_prompt()

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
            ack_text = self._pick_acknowledgement(transcript.text)
            conversation.add_message("assistant", ack_text)
            await self._repository.save(conversation)

            # Delegate to Hermes gateway (the REAL brain with ALL tools)
            task = await self._gateway.delegate(
                task_description=transcript.text,
                conversation_history=conversation.as_llm_context(),
            )
            response_text = ack_text
        else:
            response_text = await self._llm.generate(
                conversation, system_prompt=system_prompt
            )
            conversation.add_message("assistant", response_text)
            await self._repository.save(conversation)

        # 5. TTS
        audio_output: AudioOutput = await self._tts.synthesize(response_text)

        return audio_output, conversation, task

    def _pick_acknowledgement(self, user_text: str) -> str:
        lower = user_text.lower()
        if any(w in lower for w in ("research", "look up", "find out", "compare")):
            return "I'm on it. Keep talking, I'll let you know when I'm done."
        if any(w in lower for w in ("refactor", "code", "rewrite", "fix", "debug")):
            return "I'm delegating that to Hermes. Chat with me while it works."
        if any(w in lower for w in ("write", "draft", "generate", "create")):
            return "I'll start writing that up. What else is on your mind?"
        return "I'm on it. Keep talking to me while Hermes works on that."


class PollBackgroundTask:
    """
    Polls Hermes gateway tasks and proactively notifies the user when complete.
    """

    def __init__(
        self,
        gateway: HermesGatewayPort,
        notifier: NotificationPort,
        tts: TTSPort,
        repository: ConversationRepository,
    ) -> None:
        self._gateway = gateway
        self._notifier = notifier
        self._tts = tts
        self._repository = repository

    async def poll_and_notify(self, task_id: str) -> None:
        task = await self._gateway.poll(task_id)
        if task and task.status == "completed" and task.result:
            completion_msg = f"By the way, Hermes finished: {task.result[:200]}"
            if len(task.result) > 200:
                completion_msg += "... Want me to read the full details?"

            audio = await self._tts.synthesize(completion_msg)
            await self._notifier.notify(completion_msg, audio=audio)

            # Persist in conversation if linked
            if task.conversation_id:
                conv = await self._repository.get(task.conversation_id)
                if conv:
                    conv.add_message(
                        "assistant", f"[Hermes completed] {task.result}"
                    )
                    await self._repository.save(conv)
