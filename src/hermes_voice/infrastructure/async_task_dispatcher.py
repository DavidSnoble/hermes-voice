"""Dispatches background sub-agents that inherit Hermes context."""

import asyncio
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from hermes_voice.domain.entities import Conversation, HermesContext, Task
from hermes_voice.domain.ports import TaskDispatcherPort


@dataclass
class _RunningTask:
    task: Task
    future: asyncio.Task


class AsyncSubAgentDispatcher(TaskDispatcherPort):
    """
    In-memory async task dispatcher.

    Background workers are Python asyncio tasks that:
      1. Inherit the full HermesContext (persona + user + env)
      2. Run their own LLM loop with tool access
      3. Return a formatted result

    In production, swap this for a Redis/RabbitMQ dispatcher.
    """

    def __init__(self, llm_client_factory) -> None:
        self._llm_client_factory = llm_client_factory
        self._registry: dict[UUID, _RunningTask] = {}

    async def dispatch(
        self,
        task_description: str,
        hermes_context: HermesContext,
        conversation: Conversation,
    ) -> Task:
        task_id = uuid4()
        task = Task(
            id=task_id,
            description=task_description,
            status="pending",
            conversation_id=conversation.id,
        )

        # Spawn the background coroutine
        future = asyncio.create_task(
            self._run_worker(task, hermes_context, conversation),
            name=f"worker-{task_id}",
        )
        self._registry[task_id] = _RunningTask(task=task, future=future)
        return task

    async def poll(self, task_id: UUID) -> Task | None:
        entry = self._registry.get(task_id)
        if not entry:
            return None
        # If future is done, reflect status in the Task object
        if entry.future.done():
            try:
                result = entry.future.result()
                entry.task.status = "completed"
                entry.task.result = result
            except Exception as e:
                entry.task.status = "failed"
                entry.task.result = str(e)
        return entry.task

    async def _run_worker(
        self, task: Task, hermes_context: HermesContext, conversation: Conversation
    ) -> str:
        """The actual background worker."""
        task.status = "running"

        # Build a fresh system prompt from inherited context
        system_prompt = hermes_context.build_system_prompt(voice_mode=False)

        # Create an LLM client for this worker
        llm = self._llm_client_factory()

        # Build a focused conversation for the sub-agent
        worker_conv = Conversation()
        for msg in conversation.messages:
            worker_conv.messages.append(msg)
        worker_conv.add_message(
            "system",
            f"You are working on a background task: {task.description}. "
            "Complete this task thoroughly. Summarize your findings clearly.",
        )

        # Run the LLM (in a real implementation this could include tool loops)
        result = await llm.generate(worker_conv, system_prompt=system_prompt)
        return result
