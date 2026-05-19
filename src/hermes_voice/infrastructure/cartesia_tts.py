import httpx

from hermes_voice.domain.entities import AudioOutput
from hermes_voice.domain.ports import TTSPort


class CartesiaTTSAdapter(TTSPort):
    """Cartesia Sonic text-to-speech adapter."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.cartesia.ai",
        voice_id: str = "694f9389-aac1-45b6-b726-9d9369183238",  # Default: friendly
        model_id: str = "sonic-english",
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._voice_id = voice_id
        self._model_id = model_id
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Cartesia-Version": "2024-06-10",
            },
            timeout=httpx.Timeout(30.0),
        )

    async def synthesize(self, text: str) -> AudioOutput:
        payload = {
            "model_id": self._model_id,
            "transcript": text,
            "voice": {"mode": "id", "id": self._voice_id},
            "output_format": {
                "container": "mp3",
                "sample_rate": 24000,
                "encoding": "mp3",
            },
        }

        response = await self._client.post(
            f"{self._base_url}/tts/bytes",
            json=payload,
        )
        response.raise_for_status()

        return AudioOutput(data=response.content, format="mp3", sample_rate=24000)

    async def close(self) -> None:
        await self._client.aclose()
