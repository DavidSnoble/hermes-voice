"""Delegates background tasks to the Hermes API server (OpenAI-compatible /v1/runs)."""

import httpx

from hermes_voice.domain.entities import Task
from hermes_voice.domain.ports import HermesGatewayPort


class HermesGatewayAdapter(HermesGatewayPort):
    """
    Calls the Hermes gateway's built-in API server.

    Hermes must be configured with:
      API_SERVER_ENABLED=true
      API_SERVER_KEY=your_key
      API_SERVER_PORT=8642

    The adapter POSTs to /v1/runs to start a background agent loop,
    then polls /v1/runs/{run_id} for completion.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "http://127.0.0.1:8642",
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0),
        )

    async def delegate(
        self, task_description: str, conversation_history: list[dict[str, str]]
    ) -> Task:
        """Start a Hermes background run."""
        payload = {
            "input": task_description,
            "conversation_history": conversation_history,
            "stream": False,
        }

        response = await self._client.post(
            f"{self._base_url}/v1/runs",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        return Task(
            id=data.get("run_id", ""),
            description=task_description,
            status="pending",
        )

    async def poll(self, task_id: str) -> Task | None:
        """Poll the Hermes gateway for run status."""
        try:
            response = await self._client.get(
                f"{self._base_url}/v1/runs/{task_id}",
            )
            response.raise_for_status()
            data = response.json()

            status = data.get("status", "pending")
            result = data.get("output", "")

            # Map Hermes statuses to our Task statuses
            if status in ("completed", "cancelled"):
                task_status = "completed"
            elif status in ("failed", "error"):
                task_status = "failed"
            else:
                task_status = "running"

            return Task(
                id=task_id,
                description="",
                status=task_status,  # type: ignore[arg-type]
                result=result if result else None,
            )
        except Exception:
            return None

    async def close(self) -> None:
        await self._client.aclose()
