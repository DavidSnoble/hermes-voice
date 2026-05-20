import logging

import httpx

from hermes_voice.domain.entities import AudioInput, Transcript
from hermes_voice.domain.ports import STTPort

logger = logging.getLogger(__name__)

class DeepgramSTTAdapter(STTPort):
    """Deepgram Nova-2 speech-to-text adapter."""

    def __init__(self, api_key: str, base_url: str = "https://api.deepgram.com/v1") -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Token {api_key}"},
            timeout=httpx.Timeout(30.0),
        )

    async def transcribe(self, audio: AudioInput) -> Transcript:
        if not audio.data or len(audio.data) < 100:
            logger.warning(f"Audio too small: {len(audio.data) if audio.data else 0} bytes")
            return Transcript(text="", confidence=0.0, is_final=True)

        params = {"model": "nova-2", "smart_format": "true", "language": "en"}

        # Map format to Deepgram content-type
        fmt = audio.format.lower()
        if fmt in ("mp4", "m4a", "mp3"):
            content_type = f"audio/{fmt}"
        elif "opus" in fmt:
            content_type = "audio/webm"
        else:
            content_type = f"audio/{fmt}"

        logger.info(f"Deepgram STT: sending {len(audio.data)} bytes, content-type={content_type}")

        response = await self._client.post(
            f"{self._base_url}/listen",
            params=params,
            content=audio.data,
            headers={"Content-Type": content_type},
        )

        if response.status_code >= 400:
            body = response.text[:500]
            logger.error(f"Deepgram error {response.status_code}: {body}")
            response.raise_for_status()

        payload = response.json()

        result = payload.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0]
        text = result.get("transcript", "").strip()
        confidence = result.get("confidence", 0.0)

        logger.info(f"Deepgram STT: transcript='{text[:100]}...' confidence={confidence}")

        return Transcript(text=text, confidence=confidence, is_final=True)

    async def close(self) -> None:
        await self._client.aclose()
