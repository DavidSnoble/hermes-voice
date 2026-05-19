"""Notification bus that pushes audio/text over an active WebSocket."""

import base64

from fastapi import WebSocket

from hermes_voice.domain.entities import AudioOutput
from hermes_voice.domain.ports import NotificationPort


class WebSocketNotificationBus(NotificationPort):
    """
    Sends proactive notifications to a connected WebSocket client.
    Used to announce background task completion while the user is chatting.
    """

    def __init__(self, websocket: WebSocket) -> None:
        self._ws = websocket

    async def notify(self, message: str, audio: AudioOutput | None = None) -> None:
        payload: dict = {
            "type": "proactive",
            "message": message,
        }
        if audio:
            payload["audio_data"] = base64.b64encode(audio.data).decode("utf-8")
            payload["audio_format"] = audio.format

        try:
            await self._ws.send_json(payload)
        except Exception:
            # Client disconnected; silently drop
            pass
