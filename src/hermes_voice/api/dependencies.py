"""Composition root: wires domain ports to concrete infrastructure adapters."""

from functools import lru_cache

from pydantic_settings import BaseSettings

from hermes_voice.application.use_cases import ProcessVoiceMessage
from hermes_voice.domain.ports import ConversationRepository, LLMPort, STTPort, TTSPort
from hermes_voice.infrastructure.cartesia_tts import CartesiaTTSAdapter
from hermes_voice.infrastructure.deepgram_stt import DeepgramSTTAdapter
from hermes_voice.infrastructure.memory_repo import InMemoryConversationRepository
from hermes_voice.infrastructure.openrouter_llm import OpenRouterLLMAdapter


class Settings(BaseSettings):
    deepgram_api_key: str
    cartesia_api_key: str
    llm_api_key: str
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "openai/gpt-4o-mini"
    voice_port: int = 9120
    voice_host: str = "0.0.0.0"
    system_prompt: str | None = None

    class Config:
        env_prefix = ""
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_stt(settings: Settings = get_settings()) -> STTPort:
    return DeepgramSTTAdapter(api_key=settings.deepgram_api_key)


def get_tts(settings: Settings = get_settings()) -> TTSPort:
    return CartesiaTTSAdapter(api_key=settings.cartesia_api_key)


def get_llm(settings: Settings = get_settings()) -> LLMPort:
    return OpenRouterLLMAdapter(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
    )


def get_repository() -> ConversationRepository:
    return InMemoryConversationRepository()


def get_process_voice_message(settings: Settings = get_settings()) -> ProcessVoiceMessage:
    return ProcessVoiceMessage(
        stt=get_stt(),
        llm=get_llm(),
        tts=get_tts(),
        repository=get_repository(),
        system_prompt=settings.system_prompt,
    )
