from uuid import UUID, uuid4

from hermes_voice.domain.entities import AudioInput, AudioOutput, Conversation, Transcript
from hermes_voice.domain.ports import ConversationRepository, LLMPort, STTPort, TTSPort


class ProcessVoiceMessage:
    """
    Core use case: turn user audio into assistant audio.

    Orchestrates STT → LLM → TTS while managing conversation state.
    """

    def __init__(
        self,
        stt: STTPort,
        llm: LLMPort,
        tts: TTSPort,
        repository: ConversationRepository,
        system_prompt: str | None = None,
    ) -> None:
        self._stt = stt
        self._llm = llm
        self._tts = tts
        self._repository = repository
        self._system_prompt = system_prompt

    async def execute(
        self, audio: AudioInput, conversation_id: UUID | None = None
    ) -> tuple[AudioOutput, Conversation]:
        """
        1. Transcribe audio to text.
        2. Append user message to conversation.
        3. Generate LLM response.
        4. Append assistant message to conversation.
        5. Synthesize response audio.
        6. Persist conversation.
        """
        # 1. STT
        transcript: Transcript = await self._stt.transcribe(audio)

        # 2. Load or create conversation
        conversation: Conversation
        if conversation_id:
            existing = await self._repository.get(conversation_id)
            conversation = existing if existing else Conversation(id=conversation_id)
        else:
            conversation = Conversation(id=uuid4())

        conversation.add_message("user", transcript.text)

        # 3. LLM
        response_text: str = await self._llm.generate(
            conversation, system_prompt=self._system_prompt
        )

        # 4. Update conversation
        conversation.add_message("assistant", response_text)
        await self._repository.save(conversation)

        # 5. TTS
        audio_output: AudioOutput = await self._tts.synthesize(response_text)

        return audio_output, conversation
