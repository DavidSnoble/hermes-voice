"""WebSocket endpoint: drives the application via real-time audio."""

import asyncio
import base64
import json
import logging
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect

from hermes_voice.api.dependencies import (
    get_process_voice_message,
    get_repository,
    get_tts,
    get_hermes_gateway,
)
from hermes_voice.application.use_cases import PollBackgroundTask
from hermes_voice.domain.entities import AudioInput
from hermes_voice.infrastructure.websocket_notifier import WebSocketNotificationBus

logger = logging.getLogger(__name__)


async def handle_voice_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    client = websocket.client.host if websocket.client else "unknown"
    logger.info(f"WebSocket connected from {client}")

    use_case = get_process_voice_message()
    repository = get_repository()
    tts = get_tts()
    gateway = get_hermes_gateway()
    notifier = WebSocketNotificationBus(websocket)

    conversation_id: UUID | None = None
    active_tasks: set[str] = set()
    poller = PollBackgroundTask(gateway, notifier, tts, repository)

    poll_cancel: asyncio.Task | None = None

    async def poll_loop() -> None:
        while True:
            await asyncio.sleep(5)
            for task_id in list(active_tasks):
                try:
                    await poller.poll_and_notify(task_id)
                except Exception as exc:
                    logger.warning("Poll error for task %s: %s", task_id, exc)
                try:
                    task = await gateway.poll(task_id)
                    if task and task.status in ("completed", "failed"):
                        active_tasks.discard(task_id)
                except Exception as exc:
                    logger.warning("Gateway poll error for task %s: %s", task_id, exc)

    poll_cancel = asyncio.create_task(poll_loop())

    try:
        while True:
            # Receive raw text first so we can log malformed messages without crashing
            try:
                raw_msg = await websocket.receive_text()
            except WebSocketDisconnect:
                raise
            except Exception as exc:
                logger.warning(f"WebSocket receive error: {exc}")
                continue

            try:
                message = json.loads(raw_msg)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from client: {raw_msg[:200]}")
                try:
                    await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                except Exception:
                    pass
                continue

            msg_type = message.get("type")
            logger.debug(f"Received message type={msg_type}")

            if msg_type == "audio":
                try:
                    audio_b64 = message.get("data", "")
                    if not audio_b64:
                        logger.warning("Empty audio data received")
                        await websocket.send_json({
                            "type": "error",
                            "message": "Empty audio received. Try holding the button a little longer.",
                        })
                        continue

                    audio_bytes = base64.b64decode(audio_b64)
                    audio_format = message.get("format", "webm")

                    logger.info(f"Audio message: {len(audio_bytes)} bytes, format={audio_format}")

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
                except Exception as exc:
                    logger.exception("Error processing audio message")
                    try:
                        error_msg = str(exc)
                        if "400 Bad Request" in error_msg:
                            error_msg = "Could not understand the audio. Please speak clearly and try again."
                        await websocket.send_json({
                            "type": "error",
                            "message": error_msg,
                        })
                    except Exception:
                        pass  # If we can't send, the connection is probably dead anyway

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.exception("Unexpected WebSocket error")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        if poll_cancel:
            poll_cancel.cancel()
            try:
                await poll_cancel
            except asyncio.CancelledError:
                pass