"""Hermes Voice Agent."""
import httpx

from hermes_voice.domain.entities import Conversation
from hermes_voice.domain.ports import LLMPort


class HermesGatewayLLMAdapter(LLMPort):
    """LLM adapter that calls the Hermes gateway's /v1/chat/completions endpoint.

    This lets the voice app use the gateway's configured provider (e.g. opencode-go)
    without needing its own API key to that provider.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8642",
        model: str = "google/gemini-2.0-flash-001",
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(60.0),
        )

    async def generate(self, conversation: Conversation, system_prompt: str | None = None) -> str:
        messages = conversation.as_llm_context(system_prompt=system_prompt)

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.8,
            "max_tokens": 1024,
        }

        response = await self._client.post(
            f"{self._base_url}/v1/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        return str(message.get("content", "")).strip()

    async def close(self) -> None:
        await self._client.aclose()
