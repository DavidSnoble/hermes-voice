"""Composition root: wires domain ports to concrete infrastructure adapters."""

from functools import lru_cache

from pydantic_settings import BaseSettings

from hermes_voice.application.use_cases import PollBackgroundTask, ProcessVoiceMessage
from hermes_voice.domain.ports import (
    ContextProvider,
    ConversationRepository,
    HermesGatewayPort,
    IntentClassifierPort,
    LLMPort,
    STTPort,
    TTSPort,
)
from hermes_voice.infrastructure.cartesia_tts import CartesiaTTSAdapter
from hermes_voice.infrastructure.deepgram_stt import DeepgramSTTAdapter
from hermes_voice.infrastructure.hermes_context_provider import HermesContextProvider
from hermes_voice.infrastructure.hermes_gateway_adapter import HermesGatewayAdapter
from hermes_voice.infrastructure.keyword_intent_classifier import KeywordIntentClassifier
from hermes_voice.infrastructure.memory_repo import InMemoryConversationRepository
from hermes_voice.infrastructure.hermes_gateway_llm import HermesGatewayLLMAdapter


class Settings(BaseSettings):
    deepgram_api_key: str
    cartesia_api_key: str
    hermes_api_key: str = ""
    hermes_api_url: str = "http://127.0.0.1:8642"
    voice_port: int = 9120
    voice_host: str = "0.0.0.0"
    hermes_home: str = ""

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
    if not settings.hermes_api_key:
        raise ValueError(
            "HERMES_API_KEY not configured. "
            "Enable the Hermes API server with API_SERVER_ENABLED=true and API_SERVER_KEY=xxx"
        )
    return HermesGatewayLLMAdapter(
        api_key=settings.hermes_api_key,
        base_url=settings.hermes_api_url,
    )


def get_repository() -> ConversationRepository:
    return InMemoryConversationRepository()


def get_context_provider(settings: Settings = get_settings()) -> ContextProvider:
    home = settings.hermes_home or ""
    return HermesContextProvider(hermes_home=home if home else None)


def get_intent_classifier(settings: Settings = get_settings()) -> IntentClassifierPort:
    return KeywordIntentClassifier()


def get_hermes_gateway(settings: Settings = get_settings()) -> HermesGatewayPort:
    if not settings.hermes_api_key:
        raise ValueError(
            "HERMES_API_KEY not configured. "
            "Enable the Hermes API server with API_SERVER_ENABLED=true and API_SERVER_KEY=xxx"
        )
    return HermesGatewayAdapter(
        api_key=settings.hermes_api_key,
        base_url=settings.hermes_api_url,
    )


def get_process_voice_message(settings: Settings = get_settings()) -> ProcessVoiceMessage:
    return ProcessVoiceMessage(
        stt=get_stt(),
        llm=get_llm(),
        tts=get_tts(),
        repository=get_repository(),
        context_provider=get_context_provider(),
        classifier=get_intent_classifier(),
        gateway=get_hermes_gateway(),
    )
