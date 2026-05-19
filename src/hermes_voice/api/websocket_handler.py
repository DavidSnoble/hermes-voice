"""WebSocket endpoint: drives the application via real-time audio."""

import base64
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect

from hermes_voice.api.dependencies import get_process_voice_message
from hermes_voice.domain.entities import AudioInput
from hermes_voice.domain.ports import ConversationRepository


async def handle_voice_websocket(websocket: WebSocket) -> None:
    await websocket.accept()

    use_case = get_process_voice_message()
    # Re-use the same repository instance for the session
    # In production, inject this properly or use a singleton
    conversation_id: UUID | None = None

    try:
        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type")

            if msg_type == "audio":
                audio_b64 = message.get("data", "")
                audio_bytes = base64.b64decode(audio_b64)
                audio_format = message.get("format", "webm")

                audio_input = AudioInput(
                    data=audio_bytes,
                    format=audio_format,
                )

                audio_output, conversation = await use_case.execute(
                    audio_input, conversation_id=conversation_id
                )
                conversation_id = conversation.id

                await websocket.send_json({
                    "type": "response_audio",
                    "data": base64.b64encode(audio_output.data).decode("utf-8"),
                    "format": audio_output.format,
                    "conversation_id": str(conversation_id),
                })

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
        await websocket.close()
