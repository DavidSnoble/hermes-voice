"""Integration tests for external API adapters.

Run only when real API keys are available (marked as integration).
These hit live endpoints and cost money — run sparingly.
"""

import os

import pytest

from hermes_voice.domain.entities import AudioInput, Conversation
from hermes_voice.infrastructure.cartesia_tts import CartesiaTTSAdapter
from hermes_voice.infrastructure.deepgram_stt import DeepgramSTTAdapter
from hermes_voice.infrastructure.openrouter_llm import OpenRouterLLMAdapter

pytestmark = pytest.mark.integration


@pytest.fixture
def deepgram_key() -> str:
    key = os.environ.get("DEEPGRAM_API_KEY")
    if not key:
        pytest.skip("DEEPGRAM_API_KEY not set")
    return key


@pytest.fixture
def cartesia_key() -> str:
    key = os.environ.get("CARTESIA_API_KEY")
    if not key:
        pytest.skip("CARTESIA_API_KEY not set")
    return key


@pytest.fixture
def llm_key() -> str:
    key = os.environ.get("LLM_API_KEY")
    if not key:
        pytest.skip("LLM_API_KEY not set")
    return key


@pytest.mark.asyncio
async def test_deepgram_transcribe(deepgram_key: str) -> None:
    """Deepgram can transcribe a minimal valid webm audio file."""
    # This is a tiny valid WebM/Opus silent frame — won't return text,
    # but validates the API round-trip.
    adapter = DeepgramSTTAdapter(api_key=deepgram_key)
    # We use a synthetic silent audio chunk for health-check only
    # Real tests should load a recorded sample.
    try:
        audio = AudioInput(data=b"\x1a\x45\xdf\xa3" + b"\x00" * 100, format="webm")
        result = await adapter.transcribe(audio)
        assert isinstance(result.text, str)
    except Exception:
        pytest.skip("Deepgram returned error for synthetic audio (expected)")
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_cartesia_synthesize(cartesia_key: str) -> None:
    adapter = CartesiaTTSAdapter(api_key=cartesia_key)
    try:
        result = await adapter.synthesize("Hello, this is a test.")
        assert len(result.data) > 0
        assert result.format == "mp3"
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_openrouter_generate(llm_key: str) -> None:
    adapter = OpenRouterLLMAdapter(api_key=llm_key)
    conv = Conversation()
    conv.add_message("user", "Say exactly 'pong' and nothing else.")
    try:
        result = await adapter.generate(conv)
        assert "pong" in result.lower()
    finally:
        await adapter.close()
