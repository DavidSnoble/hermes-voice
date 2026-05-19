"""WebSocket endpoint: drives the application via real-time audio."""

import asyncio
import base64
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect

from hermes_voice.api.dependencies import (
    get_process_voice_message,
    get_repository,
    get_task_dispatcher,
    get_tts,
)
from hermes_voice.application.use_cases import PollBackgroundTask
from hermes_voice.domain.entities import AudioInput
from hermes_voice.infrastructure.websocket_notifier import WebSocketNotificationBus


async def handle_voice_websocket(websocket: WebSocket) -> None:
    await websocket.accept()

    use_case = get_process_voice_message()
    repository = get_repository()
    tts = get_tts()
    dispatcher = get_task_dispatcher()
    notifier = WebSocketNotificationBus(websocket)

    conversation_id: UUID | None = None
    active_tasks: set[UUID] = set()
    poller = PollBackgroundTask(dispatcher, notifier, tts, repository)

    # Start a background poller loop
    poll_cancel: asyncio.Task | None = None

    async def poll_loop() -> None:
        while True:
            await asyncio.sleep(5)
            for task_id in list(active_tasks):
                await poller.poll_and_notify(task_id)
                # Remove completed/failed tasks from tracking
                task = await dispatcher.poll(task_id)
                if task and task.status in ("completed", "failed"):
                    active_tasks.discard(task_id)

    poll_cancel = asyncio.create_task(poll_loop())

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

                audio_output, conversation, task = await use_case.execute(
                    audio_input, conversation_id=conversation_id
                )
                conversation_id = conversation.id

                if task:
                    active_tasks.add(task.id)

                await websocket.send_json({
                    "type": "response_audio",
                    "data": base64.b64encode(audio_output.data).decode("utf-8"),
                    "format": audio_output.format,
                    "conversation_id": str(conversation_id),
                    "has_background_task": bool(task),
                })

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
            await websocket.close()
        except Exception:
            pass
    finally:
        if poll_cancel:
            poll_cancel.cancel()
            try:
                await poll_cancel
            except asyncio.CancelledError:
                pass
