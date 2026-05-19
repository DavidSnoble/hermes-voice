import httpx

from hermes_voice.domain.entities import AudioInput, Transcript
from hermes_voice.domain.ports import STTPort


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
        params = {"model": "nova-2", "smart_format": "true", "language": "en"}
        content_type = f"audio/{audio.format.replace('webm/opus', 'webm')}"

        response = await self._client.post(
            f"{self._base_url}/listen",
            params=params,
            content=audio.data,
            headers={"Content-Type": content_type},
        )
        response.raise_for_status()
        payload = response.json()

        result = payload.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0]
        text = result.get("transcript", "").strip()
        confidence = result.get("confidence", 0.0)

        return Transcript(text=text, confidence=confidence, is_final=True)

    async def close(self) -> None:
        await self._client.aclose()
