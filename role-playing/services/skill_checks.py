"""
Skill check services using the RPG API.

All skill checks fetch character stats from the API. The API is the source of truth.
"""

import random
from typing import Tuple

from core.settings import settings


# Difficulty classes
DIFFICULTY_CLASSES = {
    "very easy": 5,
    "easy": 10,
    "medium": 15,
    "hard": 20,
    "very hard": 25,
    "nearly impossible": 30,
}

# Skill to attribute mapping
SKILL_TO_ATTRIBUTE = {
    "athletics": "strength",
    "acrobatics": "dexterity",
    "stealth": "dexterity",
    "sleight_of_hand": "dexterity",
    "arcana": "intelligence",
    "history": "intelligence",
    "investigation": "intelligence",
    "nature": "intelligence",
    "religion": "intelligence",
    "animal_handling": "wisdom",
    "insight": "wisdom",
    "medicine": "wisdom",
    "perception": "wisdom",
    "survival": "wisdom",
    "deception": "charisma",
    "intimidation": "charisma",
    "performance": "charisma",
    "persuasion": "charisma",
}


async def resolve_skill_check(skill: str, difficulty: str, character_id: int) -> Tuple[str, dict]:
    """
    Execute a skill check using API character stats.

    Args:
        skill: The skill name (e.g., "perception", "athletics")
        difficulty: The difficulty level (e.g., "easy", "medium", "hard")
        character_id: The API character ID

    Returns:
        Tuple of (result_text, payload)
    """
    from api.client import CharacterClient

    client = CharacterClient(
        base_url=settings.rpg_api_base_url,
        timeout=settings.rpg_api_timeout,
    )

    character = await client.get(character_id)

    # Get the relevant attribute for this skill
    skill_lower = skill.lower().replace(" ", "_")
    attribute = SKILL_TO_ATTRIBUTE.get(skill_lower, "dexterity")

    # Get the attribute value from the character
    attr_value = getattr(character, attribute, 10)
    modifier = (attr_value - 10) // 2

    # Roll d20
    roll = random.randint(1, 20)
    roll_total = roll + modifier

    # Check for critical
    is_critical = None
    if roll == 20:
        is_critical = "nat20"
    elif roll == 1:
        is_critical = "nat1"

    # Get DC
    dc = DIFFICULTY_CLASSES.get(difficulty.lower(), 15)
    success = roll_total >= dc or is_critical == "nat20"
    if is_critical == "nat1":
        success = False

    margin = roll_total - dc

    payload = {
        "skill": skill_lower,
        "difficulty": difficulty.lower(),
        "roll": roll,
        "modifier": modifier,
        "roll_total": roll_total,
        "dc": dc,
        "success": success,
        "critical": is_critical,
        "margin": margin,
    }

    # Build result text
    if is_critical == "nat20":
        result_text = f"[SYSTEM: Critical Success! Natural 20! Total: {roll_total} vs DC {dc}. Outstanding success with bonus effects.]"
    elif is_critical == "nat1":
        result_text = f"[SYSTEM: Critical Failure! Natural 1! Total: {roll_total} vs DC {dc}. Catastrophic failure with negative consequences.]"
    elif success:
        if margin >= 10:
            result_text = f"[SYSTEM: Great Success! {roll_total} vs DC {dc}. Exceeded by {margin} points.]"
        elif margin >= 5:
            result_text = f"[SYSTEM: Success! {roll_total} vs DC {dc}. Solid performance.]"
        else:
            result_text = f"[SYSTEM: Narrow Success. {roll_total} vs DC {dc}. Just barely made it.]"
    else:
        failure_margin = dc - roll_total
        payload["margin"] = -failure_margin
        if failure_margin >= 10:
            result_text = f"[SYSTEM: Severe Failure. {roll_total} vs DC {dc}. Failed by {failure_margin} points. Major negative consequences.]"
        elif failure_margin >= 5:
            result_text = f"[SYSTEM: Failed. {roll_total} vs DC {dc}. Clear failure with consequences.]"
        else:
            result_text = f"[SYSTEM: Near Miss. {roll_total} vs DC {dc}. Failed by only {failure_margin} points.]"

    return result_text, payload
