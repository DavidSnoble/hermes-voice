import httpx

from hermes_voice.domain.entities import Conversation, Intent, IntentType
from hermes_voice.domain.ports import IntentClassifierPort


class LLMIntentClassifier(IntentClassifierPort):
    """
    Cheap LLM-based intent classifier.
    Uses a tiny model to decide: conversation | quick_tool | delegate.
    """

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
            timeout=httpx.Timeout(10.0),
        )

    async def classify(self, transcript: str, conversation: Conversation) -> Intent:
        system = (
            "You are an intent classifier. Respond with EXACTLY one word:\n"
            "CONVERSATION — for chitchat, simple Q&A, opinions, no tools needed\n"
            "QUICK_TOOL — for a single lookup (weather, file read, quick search)\n"
            "DELEGATE — for multi-step tasks (research, coding, writing, analysis)\n"
            "Respond with only the uppercase keyword."
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f'Classify this user message: "{transcript}"'},
        ]

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 20,
        }

        response = await self._client.post(
            f"{self._base_url}/chat/completions", json=payload
        )
        response.raise_for_status()
        data = response.json()

        raw = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "CONVERSATION")
            .strip()
            .upper()
        )

        if "QUICK_TOOL" in raw:
            return Intent(IntentType.QUICK_TOOL, confidence=0.9, reasoning=raw)
        if "DELEGATE" in raw:
            return Intent(IntentType.DELEGATE, confidence=0.9, reasoning=raw)
        return Intent(IntentType.CONVERSATION, confidence=0.95, reasoning=raw)

    async def close(self) -> None:
        await self._client.aclose()
