"""
Scenario service for managing narrative events through the API.

Provides async functions for evaluating and triggering scenarios based on
character state (location, inventory, quests, health).
"""

import logging
from typing import List, Optional, Tuple

from api.client import ScenarioClient
from api.models import (
    APIScenario,
    APIScenarioHistory,
    APITriggerScenarioResponse,
    APIEvaluateScenariosResponse,
)
from core.settings import settings
from services import quests as quest_service

logger = logging.getLogger(__name__)


def _get_scenario_client() -> ScenarioClient:
    """Get a scenario client instance."""
    return ScenarioClient(
        base_url=settings.rpg_api_base_url,
        timeout=settings.rpg_api_timeout,
    )


# === Scenario Discovery ===

async def get_scenario(scenario_id: int) -> APIScenario:
    """Get a scenario by ID."""
    client = _get_scenario_client()
    return await client.get_scenario(scenario_id)


async def list_scenarios(skip: int = 0, limit: int = 100) -> List[APIScenario]:
    """List all scenarios."""
    client = _get_scenario_client()
    return await client.list_scenarios(skip, limit)


# === Scenario Evaluation ===

async def evaluate_scenarios(
    character_id: int,
    trigger_type: str | None = None,
    auto_trigger: bool = False,
) -> APIEvaluateScenariosResponse:
    """Evaluate all scenarios for a character.

    Args:
        character_id: Character to evaluate for
        trigger_type: Optional filter (location, item, quest, health_threshold)
        auto_trigger: If True, automatically trigger first applicable scenario

    Returns:
        Evaluation result with applicable scenarios
    """
    client = _get_scenario_client()
    return await client.evaluate_scenarios(character_id, trigger_type, auto_trigger)


async def _process_triggered_effects(
    triggered: APITriggerScenarioResponse,
    character_id: int,
) -> List[str]:
    """Process effects from a triggered scenario and return narration updates.

    Handles health changes, item grants, and quest assignment.
    """
    updates: List[str] = []

    if triggered.narrative_text:
        updates.append(triggered.narrative_text)

    effects = triggered.effects_applied
    if effects.get("health_change"):
        change = effects["health_change"]
        if change["change"] > 0:
            updates.append(f"You feel better (+{change['change']} HP)")
        elif change["change"] < 0:
            updates.append(f"You take {abs(change['change'])} damage!")

    if effects.get("items_granted"):
        updates.append(f"You received {len(effects['items_granted'])} item(s)")

    if effects.get("quest_triggered"):
        # Actually assign the quest to the character
        quest_id = effects["quest_triggered"]
        logger.info(f"Scenario triggered quest {quest_id} for character {character_id}")
        try:
            assignment, error = await quest_service.accept_quest(quest_id, character_id)
            if assignment:
                quest = assignment.quest
                logger.info(f"Quest assigned successfully: {quest.title}")
                updates.append(f"New quest: {quest.title}")
            elif error:
                # Quest might already be assigned or prerequisites not met
                logger.warning(f"Failed to assign quest {quest_id}: {error}")
                updates.append("A new quest is available!")
        except Exception as e:
            logger.exception(f"Exception assigning quest {quest_id}: {e}")
            updates.append("A new quest is available!")

    return updates


async def check_location_scenarios(
    character_id: int,
    auto_trigger: bool = True,
) -> Tuple[List[str], APITriggerScenarioResponse | None]:
    """Check for location-triggered scenarios when character moves.

    Args:
        character_id: Character that moved
        auto_trigger: If True, trigger the first applicable scenario

    Returns:
        (narration_updates, triggered_response)
    """
    client = _get_scenario_client()
    result = await client.check_location_scenarios(character_id, auto_trigger)

    updates: List[str] = []
    triggered: APITriggerScenarioResponse | None = None

    if result.triggered:
        triggered = result.triggered
        updates = await _process_triggered_effects(triggered, character_id)

    return updates, triggered


async def check_item_scenarios(
    character_id: int,
    auto_trigger: bool = True,
) -> Tuple[List[str], APITriggerScenarioResponse | None]:
    """Check for item-triggered scenarios when inventory changes.

    Args:
        character_id: Character whose inventory changed
        auto_trigger: If True, trigger the first applicable scenario

    Returns:
        (narration_updates, triggered_response)
    """
    client = _get_scenario_client()
    result = await client.check_item_scenarios(character_id, auto_trigger)

    updates: List[str] = []
    triggered: APITriggerScenarioResponse | None = None

    if result.triggered:
        triggered = result.triggered
        updates = await _process_triggered_effects(triggered, character_id)

    return updates, triggered


async def check_health_scenarios(
    character_id: int,
    auto_trigger: bool = True,
) -> Tuple[List[str], APITriggerScenarioResponse | None]:
    """Check for health threshold-triggered scenarios.

    Args:
        character_id: Character to check
        auto_trigger: If True, trigger the first applicable scenario

    Returns:
        (narration_updates, triggered_response)
    """
    client = _get_scenario_client()
    result = await client.evaluate_scenarios(character_id, "health_threshold", auto_trigger)

    updates: List[str] = []
    triggered: APITriggerScenarioResponse | None = None

    if result.triggered:
        triggered = result.triggered
        updates = await _process_triggered_effects(triggered, character_id)

    return updates, triggered


# === Scenario Triggering ===

async def trigger_scenario(
    scenario_id: int,
    character_id: int,
    outcome_index: int | None = None,
) -> Tuple[APITriggerScenarioResponse | None, str]:
    """Trigger a scenario for a character.

    Args:
        scenario_id: Scenario to trigger
        character_id: Character to apply effects to
        outcome_index: Specific outcome (or None for random)

    Returns:
        (trigger_response, error_message)
    """
    client = _get_scenario_client()
    try:
        result = await client.trigger_scenario(scenario_id, character_id, outcome_index)
        return result, ""
    except Exception as e:
        return None, str(e)


# === History ===

async def get_scenario_history(character_id: int) -> List[APIScenarioHistory]:
    """Get a character's scenario history."""
    client = _get_scenario_client()
    return await client.get_character_history(character_id)


# === Combined Event Handlers ===

async def handle_zone_transition(
    character_id: int,
    zone_id: int,
    zone_name: str,
) -> List[str]:
    """Handle all scenario-related events when entering a zone.

    This combines location scenarios, quest triggers, etc.

    Returns:
        List of narration updates
    """
    updates: List[str] = []

    # Check location-triggered scenarios
    location_updates, _ = await check_location_scenarios(character_id)
    updates.extend(location_updates)

    return updates


async def handle_combat_end(
    character_id: int,
    victory: bool,
    enemies_defeated: List[str],
) -> List[str]:
    """Handle scenario events after combat ends.

    Returns:
        List of narration updates
    """
    updates: List[str] = []

    # Check health-threshold scenarios (might trigger on low HP after combat)
    health_updates, _ = await check_health_scenarios(character_id)
    updates.extend(health_updates)

    return updates


async def handle_item_pickup(
    character_id: int,
    item_name: str,
) -> List[str]:
    """Handle scenario events when picking up an item.

    Returns:
        List of narration updates
    """
    updates: List[str] = []

    # Check item-triggered scenarios
    item_updates, _ = await check_item_scenarios(character_id)
    updates.extend(item_updates)

    return updates


# === Formatting Helpers ===

def format_scenario_for_narration(scenario: APIScenario) -> str:
    """Format a scenario's narrative text for display."""
    if scenario.narrative_text:
        return scenario.narrative_text

    # Fallback to title and description
    text = f"**{scenario.title}**"
    if scenario.description:
        text += f"\n{scenario.description}"
    return text


def format_trigger_result(result: APITriggerScenarioResponse) -> str:
    """Format a trigger result for display to the player."""
    lines: List[str] = []

    if result.narrative_text:
        lines.append(result.narrative_text)

    outcome = result.outcome_applied
    if outcome.get("description"):
        lines.append(outcome["description"])

    effects = result.effects_applied
    if effects.get("health_change"):
        change = effects["health_change"]["change"]
        if change > 0:
            lines.append(f"[+{change} HP]")
        elif change < 0:
            lines.append(f"[{change} HP]")

    if effects.get("attribute_changes"):
        for attr, vals in effects["attribute_changes"].items():
            diff = vals["to"] - vals["from"]
            if diff > 0:
                lines.append(f"[+{diff} {attr.capitalize()}]")
            elif diff < 0:
                lines.append(f"[{diff} {attr.capitalize()}]")

    if effects.get("items_granted"):
        lines.append(f"[Received {len(effects['items_granted'])} item(s)]")

    if effects.get("items_removed"):
        lines.append(f"[Lost {len(effects['items_removed'])} item(s)]")

    if effects.get("quest_triggered"):
        lines.append("[New quest available!]")

    return "\n".join(lines)
