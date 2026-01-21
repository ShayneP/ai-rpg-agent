"""
Combat services using the RPG API.

All combat operations go through the API. The API is the source of truth.
"""

import logging
from typing import List, Tuple

from core.state_service import GameStateService
from core.settings import settings

logger = logging.getLogger("dungeons-and-agents.services")


# Enemy type to monster ID mapping for API
ENEMY_TYPE_TO_MONSTER_ID = {
    "goblin": "goblin",
    "orc": "orc",
    "bandit": "bandit",
    "skeleton": "skeleton",
    "wolf": "wolf",
    "dark_mage": "cultist",
    "rat": "giant_rat",
    "zombie": "zombie",
    "hobgoblin": "hobgoblin",
    "bugbear": "bugbear",
    "gnoll": "gnoll",
    "spider": "giant_spider",
    "ogre": "ogre",
    "troll": "troll",
    "owlbear": "owlbear",
    "minotaur": "minotaur",
    "wight": "wight",
    "dire_wolf": "dire_wolf",
    "ghoul": "ghoul",
    "imp": "imp",
    "dragon": "young_dragon",
}

# Description for each enemy type (for narrator)
ENEMY_DESCRIPTIONS = {
    "goblin": "Don't underestimate them!",
    "orc": "Large and brutal",
    "bandit": "Quick and cunning",
    "skeleton": "Undead warrior",
    "dark_mage": "Wielder of dark magic",
    "wolf": "Savage beast",
    "rat": "Disease-carrying vermin",
    "zombie": "Shambling undead",
    "hobgoblin": "Disciplined warrior",
    "bugbear": "Stealthy brute",
    "gnoll": "Hyena-headed savage",
    "spider": "Venomous arachnid",
    "ogre": "Hulking brute",
    "troll": "Regenerating monster",
    "owlbear": "Ferocious beast",
    "minotaur": "Maze-dwelling monster",
    "wight": "Life-draining undead",
    "dire_wolf": "Massive predator",
    "ghoul": "Corpse-eating horror",
    "imp": "Devilish trickster",
    "dragon": "Ancient terror",
}


async def build_enemy_group(
    enemy_type: str,
    enemy_count: int,
    zone_id: int | None = None,
) -> Tuple[List[int], str]:
    """
    Create enemies via the API and return their character IDs.

    Args:
        enemy_type: Type of enemy (e.g., "goblin", "orc")
        enemy_count: Number of enemies to create (capped at 5)
        zone_id: Zone ID where enemies should be placed (for combat distance)

    Returns:
        Tuple of (list of character IDs, encounter description)
    """
    from api.client import CharacterClient

    enemy_type = enemy_type.lower()
    monster_id = ENEMY_TYPE_TO_MONSTER_ID.get(enemy_type, "goblin")
    description = ENEMY_DESCRIPTIONS.get(enemy_type, "A dangerous foe!")

    client = CharacterClient(
        base_url=settings.rpg_api_base_url,
        timeout=settings.rpg_api_timeout,
    )

    enemy_ids: List[int] = []
    enemy_count = min(enemy_count, 5)  # Cap at 5

    for i in range(enemy_count):
        enemy_name = (
            f"{enemy_type.capitalize()}"
            if enemy_count == 1
            else f"{enemy_type.capitalize()} {i+1}"
        )
        try:
            character = await client.create_from_monster(
                monster_id,
                name=enemy_name,
                zone_id=zone_id,
            )
            enemy_ids.append(character.id)
            logger.info(f"Created enemy via API: {character.name} (ID: {character.id}) from monster {monster_id} in zone {zone_id}")
        except Exception as e:
            logger.warning(f"Failed to create enemy {enemy_name} via API: {e}")

    if enemy_count == 1:
        encounter_desc = f"A {enemy_type} appears before you! {description}."
    else:
        encounter_desc = f"{enemy_count} {enemy_type}s appear before you! {description}."

    return enemy_ids, encounter_desc


async def initialize_combat(state: GameStateService, player_id: int, enemy_ids: List[int]) -> str:
    """
    Initialize combat via the API.

    Args:
        state: GameStateService for storing combat session ID
        player_id: The player character's API ID
        enemy_ids: List of enemy character API IDs

    Returns:
        Narrator intro line for the combat
    """
    from api.client import CombatClient

    combat_client = CombatClient(
        base_url=settings.rpg_api_base_url,
        timeout=settings.rpg_api_timeout,
    )

    # Build participants: player on team 1, enemies on team 2
    participants = [{"character_id": player_id, "team_id": 1}]
    for enemy_id in enemy_ids:
        participants.append({"character_id": enemy_id, "team_id": 2})

    # Start combat via API
    combat_session = await combat_client.start_combat(participants)
    state.set_combat_session_id(combat_session.id)

    # Store enemy IDs in state
    for enemy_id in enemy_ids:
        state.add_npc_id(enemy_id)

    # Get enemy names for the intro message
    enemy_names = []
    for combatant in combat_session.combatants:
        if combatant.team_id == 2:  # Enemy team
            enemy_names.append(combatant.name)

    if len(enemy_names) == 1:
        combat_start = f"Combat begins! You face {enemy_names[0]}!"
    elif len(enemy_names) > 1:
        combat_start = f"Combat begins! You face {', '.join(enemy_names[:-1])} and {enemy_names[-1]}!"
    else:
        combat_start = "Combat begins!"

    logger.info(f"Started combat session {combat_session.id} with {len(enemy_names)} enemies")

    return combat_start
