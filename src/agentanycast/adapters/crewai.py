"""CrewAI adapter — expose a CrewAI Crew as a P2P A2A agent.

Usage:
    from crewai import Crew
    from agentanycast import AgentCard, Skill
    from agentanycast.adapters.crewai import serve_crew

    crew = Crew(agents=[...], tasks=[...])
    card = AgentCard(
        name="Research Crew",
        skills=[Skill(id="research", description="Research any topic")],
    )

    await serve_crew(crew, card=card, relay="/ip4/.../p2p/12D3KooW...")
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

try:
    from crewai import Crew  # noqa: F401
except ImportError as _err:
    raise ImportError(
        "CrewAI adapter requires the 'crewai' package. "
        "Install with: pip install agentanycast[crewai]"
    ) from _err

from agentanycast.adapters._base import BaseAdapter
from agentanycast.card import AgentCard

logger = logging.getLogger(__name__)


class CrewAIAdapter(BaseAdapter):
    """Wraps a CrewAI Crew as an A2A agent."""

    def __init__(self, crew: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._crew = crew

    async def _invoke(self, input_text: str, input_data: dict[str, Any] | None) -> str:
        """Run the Crew with the given input.

        CrewAI's ``kickoff()`` is synchronous, so we run it in a thread executor.
        """
        inputs = input_data or {}
        if input_text and "input" not in inputs:
            inputs["input"] = input_text

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, lambda: self._crew.kickoff(inputs=inputs))

        # CrewAI's CrewOutput has a .raw attribute for string output.
        if hasattr(result, "raw"):
            return str(result.raw)
        return str(result)


async def serve_crew(
    crew: Any,
    *,
    card: AgentCard,
    relay: str | None = None,
    key_path: str | None = None,
    home: str | None = None,
) -> None:
    """Serve a CrewAI Crew as a P2P A2A agent.

    This is the main entry point for CrewAI integration. It starts a P2P node,
    registers the crew's capabilities, and processes incoming tasks by running
    the crew's workflow.

    Args:
        crew: A CrewAI ``Crew`` instance.
        card: AgentCard describing the agent and its skills.
        relay: Relay server multiaddr.
        key_path: Path to libp2p identity key.
        home: Data directory for daemon state.
    """
    adapter = CrewAIAdapter(crew, card=card, relay=relay, key_path=key_path, home=home)
    await adapter.serve()
