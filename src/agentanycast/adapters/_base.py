"""Base adapter class for framework integrations."""

from __future__ import annotations

import logging
from typing import Any

from agentanycast.card import AgentCard
from agentanycast.node import Node
from agentanycast.task import Artifact, IncomingTask, Part

logger = logging.getLogger(__name__)


class BaseAdapter:
    """Base class for framework adapters.

    Subclasses implement ``_invoke()`` to translate between A2A messages
    and the framework's native input/output format.
    """

    def __init__(
        self,
        *,
        card: AgentCard,
        relay: str | None = None,
        key_path: str | None = None,
        home: str | None = None,
    ) -> None:
        self._card = card
        self._node = Node(
            card=card,
            relay=relay,
            key_path=key_path,
            home=home,
        )

    async def _invoke(
        self,
        input_text: str,
        input_data: dict[str, Any] | None,
    ) -> str | dict[str, Any]:
        """Invoke the wrapped framework. Must be overridden by subclasses.

        Args:
            input_text: Text extracted from the incoming A2A message.
            input_data: Structured data extracted from the message (if any).

        Returns:
            String output or dict output from the framework.
        """
        raise NotImplementedError

    async def _handle_task(self, task: IncomingTask) -> None:
        """Default task handler that translates A2A → framework → A2A."""
        await task.update_status("working")

        try:
            # Extract text and data from the incoming message.
            input_text = ""
            input_data: dict[str, Any] | None = None
            for msg in task.messages:
                for part in msg.parts:
                    if part.text:
                        input_text += part.text
                    if part.data:
                        input_data = part.data

            # Invoke the framework.
            result = await self._invoke(input_text, input_data)

            # Translate output back to A2A artifacts.
            if isinstance(result, str):
                artifact = Artifact(
                    name="output",
                    parts=[Part(text=result)],
                )
            elif isinstance(result, dict):
                artifact = Artifact(
                    name="output",
                    parts=[Part(data=result)],
                )
            else:
                artifact = Artifact(
                    name="output",
                    parts=[Part(text=str(result))],
                )

            await task.complete(artifacts=[artifact])

        except Exception as e:
            logger.exception("Framework invocation failed")
            await task.fail(str(e))

    async def serve(self) -> None:
        """Start serving as a P2P A2A agent."""
        async with self._node as node:
            node.on_task(self._handle_task)
            await node.serve_forever()
