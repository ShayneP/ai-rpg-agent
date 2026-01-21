"""
Typed wrappers for state updates emitted to the frontend.

These functions keep event types consistent and reduce stringly-typed calls.
"""

from typing import Any, Dict

from agents.base_agent import BaseGameAgent


async def emit_skill_check(agent: BaseGameAgent, payload: Dict[str, Any]) -> None:
    await agent.emit_state_update("skill_check", payload)
