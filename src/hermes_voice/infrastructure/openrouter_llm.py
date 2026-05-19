import httpx

from hermes_voice.domain.entities import Conversation
from hermes_voice.domain.ports import LLMPort


class OpenRouterLLMAdapter(LLMPort):
    """OpenRouter-compatible LLM adapter (works with OpenAI, Anthropic, etc.)."""

    def __init__(
        self,
        api_key: str,
        model: str = "openai/gpt-4o-mini",
        base_url: str = "https://openrouter.ai/api/v1",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://voice.dsnoble.com",
                "X-Title": "Hermes Voice",
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
            f"{self._base_url}/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        return str(message.get("content", "")).strip()

    async def close(self) -> None:
        await self._client.aclose()
