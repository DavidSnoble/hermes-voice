"""End-to-end integration test: real audio through full pipeline."""

import asyncio
import base64
import json
import os
import subprocess
from pathlib import Path

import pytest
import websockets


def _load_env():
    env_path = Path("/opt/hermes-voice/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v)


_load_env()


@pytest.fixture(scope="session")
def test_audio_webm():
    path = "/tmp/test_speech.webm"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "sine=frequency=1000:duration=2",
            "-c:a", "libopus", "-b:a", "24k",
            path,
        ],
        capture_output=True,
        check=True,
    )
    assert Path(path).exists()
    print(f"Generated test webm: {Path(path).stat().st_size} bytes")
    return path


@pytest.fixture(scope="session")
def test_audio_mp3():
    path = "/tmp/test_speech.mp3"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "sine=frequency=1000:duration=2",
            "-ar", "24000", "-ac", "1",
            "-c:a", "libmp3lame", "-b:a", "64k",
            path,
        ],
        capture_output=True,
        check=True,
    )
    assert Path(path).exists()
    print(f"Generated test MP3: {Path(path).stat().st_size} bytes")
    return path


@pytest.mark.asyncio
async def test_deepgram_stt_real_audio(test_audio_webm):
    from hermes_voice.infrastructure.deepgram_stt import DeepgramSTTAdapter
    from hermes_voice.domain.entities import AudioInput

    with open(test_audio_webm, "rb") as f:
        data = f.read()

    stt = DeepgramSTTAdapter(api_key=os.environ["DEEPGRAM_API_KEY"])
    audio = AudioInput(data=data, format="webm")
    transcript = await stt.transcribe(audio)
    print(f"STT result: '{transcript.text}' confidence={transcript.confidence}")
    await stt.close()

    assert transcript is not None
    assert transcript.confidence >= 0.0


@pytest.mark.asyncio
async def test_cartesia_tts_real():
    from hermes_voice.infrastructure.cartesia_tts import CartesiaTTSAdapter

    tts = CartesiaTTSAdapter(api_key=os.environ["CARTESIA_API_KEY"])
    audio = await tts.synthesize("Hey, how's it going?")
    print(f"TTS audio: {len(audio.data)} bytes, format={audio.format}")
    await tts.close()

    assert len(audio.data) > 1000
    is_mp3 = audio.data[:3] == b"ID3" or audio.data[:2] == b"\xff\xfb"
    assert is_mp3, f"Not valid MP3. First bytes: {audio.data[:10]}"


@pytest.mark.asyncio
async def test_hermes_gateway_conversation():
    from hermes_voice.infrastructure.hermes_gateway_llm import HermesGatewayLLMAdapter
    from hermes_voice.domain.entities import Conversation

    llm = HermesGatewayLLMAdapter(
        api_key=os.environ["HERMES_API_KEY"],
        base_url="http://127.0.0.1:8642",
    )
    conv = Conversation(id="test-conv")
    conv.add_message("user", "Hey how's it going?")

    response = await llm.generate(conv)
    print(f"LLM response: '{response[:120]}...'")

    assert response
    assert len(response) > 5


@pytest.mark.asyncio
async def test_full_websocket_mp3_response(test_audio_webm):
    with open(test_audio_webm, "rb") as f:
        audio_bytes = f.read()

    uri = "ws://127.0.0.1:9120/ws"
    async with websockets.connect(uri) as ws:
        msg = json.dumps({
            "type": "audio",
            "data": base64.b64encode(audio_bytes).decode(),
            "format": "webm",
        })
        await ws.send(msg)

        response = await asyncio.wait_for(ws.recv(), timeout=20)
        payload = json.loads(response)

        print(f"Response type: {payload.get('type')}")

        if payload.get("type") == "error":
            pytest.fail(f"Server returned error: {payload.get('message')}")

        assert payload["type"] == "response_audio"

        response_audio = base64.b64decode(payload["data"])
        print(f"Response audio: {len(response_audio)} bytes, format={payload.get('format')}")

        assert len(response_audio) > 1000

        is_mp3 = response_audio[:3] == b"ID3" or response_audio[:2] == b"\xff\xfb"
        print(f"MP3 magic valid: {is_mp3}")
        assert is_mp3, f"Response not valid MP3. First bytes: {response_audio[:10]}"

        Path("/tmp/e2e_response.mp3").write_bytes(response_audio)
        print("Saved to /tmp/e2e_response.mp3")
