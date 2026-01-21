"""
Story service for handling quests and scenarios via the API.

This module provides the interface for story progression, triggering
scenarios and updating quest progress based on game events.
"""

import logging
from typing import List

from core.state_service import GameStateService
from services import scenarios as scenario_service

logger = logging.getLogger(__name__)


async def handle_location_and_story(
    state: GameStateService,
) -> List[str]:
    """
    Trigger scenarios and check quest progress on location transition.

    Returns narration updates from triggered scenarios and quest completions.
    """
    updates: List[str] = []

    if not state.player_id or not state.zone_id:
        logger.debug(f"Skipping location/story check: player_id={state.player_id}, zone_id={state.zone_id}")
        return updates

    logger.info(f"Checking location/story for player {state.player_id} in zone {state.zone_id}")

    # Check API-based scenarios (database-driven)
    try:
        scenario_updates = await scenario_service.handle_zone_transition(
            character_id=state.player_id,
            zone_id=state.zone_id,
            zone_name=state.zone_name or "",
        )
        logger.info(f"Scenario updates: {scenario_updates}")
        updates.extend(scenario_updates)
    except Exception as e:
        logger.exception(f"Error checking scenarios: {e}")

    return updates


async def handle_npc_interaction(
    npc_name: str,
    state: GameStateService,
    requested_role: str | None = None,
) -> List[str]:
    """
    Handle NPC interaction events.

    Note: Quest progress is now handled by the LLM via function tools.
    This function is kept for potential future scenario triggers.

    Args:
        npc_name: The NPC's generated name (e.g., "Grimbold the Bartender")
        state: The game state service
        requested_role: The role the player requested (e.g., "barkeep")
    """
    updates: List[str] = []

    if not state.player_id:
        return updates

    # Quest progress is now handled by the LLM via progress_quest_objective()
    # This function can be extended for NPC-specific scenario triggers if needed

    return updates


async def handle_combat_victory(
    state: GameStateService,
    enemies_defeated: List[str],
) -> List[str]:
    """
    Handle story updates after combat victory.

    Note: Quest progress is now handled by the LLM via function tools.
    """
    updates: List[str] = []

    if not state.player_id:
        return updates

    # Quest progress is now handled by the LLM via progress_quest_objective()

    # Check scenario triggers (e.g., health threshold after combat)
    try:
        scenario_updates = await scenario_service.handle_combat_end(
            character_id=state.player_id,
            victory=True,
            enemies_defeated=enemies_defeated,
        )
        updates.extend(scenario_updates)
    except Exception:
        pass

    return updates
