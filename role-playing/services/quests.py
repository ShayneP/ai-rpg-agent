"""
Quest service for managing quests through the API.

Provides async functions for quest assignment, progress tracking, and completion.
"""

from typing import List, Optional, Tuple

from api.client import QuestClient
from api.models import APIQuest, APIQuestAssignment, QuestStatus
from core.settings import settings


def _get_quest_client() -> QuestClient:
    """Get a quest client instance."""
    return QuestClient(
        base_url=settings.rpg_api_base_url,
        timeout=settings.rpg_api_timeout,
    )


# === Quest Discovery ===

async def get_available_quests(character_id: int, character_level: int = 1) -> List[APIQuest]:
    """Get quests available for a character to accept.

    Filters by level and prerequisites.
    """
    client = _get_quest_client()
    return await client.get_available_quests(character_id, character_level)


async def get_quest(quest_id: int) -> APIQuest:
    """Get a quest by ID."""
    client = _get_quest_client()
    return await client.get_quest(quest_id)


async def list_quests(
    skip: int = 0,
    limit: int = 100,
    min_level: int | None = None,
    max_level: int | None = None,
) -> List[APIQuest]:
    """List all quests with optional level filtering."""
    client = _get_quest_client()
    return await client.list_quests(skip, limit, min_level, max_level)


# === Character Quests ===

async def get_character_quests(
    character_id: int,
    status: str | None = None,
) -> List[APIQuestAssignment]:
    """Get all quests assigned to a character."""
    client = _get_quest_client()
    return await client.get_character_quests(character_id, status)


async def get_active_quests(character_id: int) -> List[APIQuestAssignment]:
    """Get character's active (in-progress) quests."""
    client = _get_quest_client()
    return await client.get_active_quests(character_id)


async def get_completed_quests(character_id: int) -> List[APIQuestAssignment]:
    """Get character's completed quests."""
    client = _get_quest_client()
    return await client.get_character_quests(character_id, status="completed")


# === Quest Management ===

async def accept_quest(quest_id: int, character_id: int) -> Tuple[APIQuestAssignment | None, str]:
    """Accept a quest for a character.

    Returns (assignment, error_message).
    If successful, error_message is empty.
    """
    client = _get_quest_client()
    try:
        assignment = await client.assign_quest(quest_id, character_id)
        return assignment, ""
    except Exception as e:
        return None, str(e)


async def update_quest_progress(
    quest_id: int,
    character_id: int,
    objective_id: int,
    amount: int = 1,
) -> Tuple[APIQuestAssignment | None, str]:
    """Update progress on a quest objective.

    Returns (assignment, error_message).
    """
    client = _get_quest_client()
    try:
        assignment = await client.update_progress(
            quest_id, character_id, objective_id, amount
        )
        return assignment, ""
    except Exception as e:
        return None, str(e)


async def complete_quest(quest_id: int, character_id: int) -> Tuple[APIQuestAssignment | None, str]:
    """Complete a quest (requires all objectives done).

    Returns (assignment, error_message).
    """
    client = _get_quest_client()
    try:
        assignment = await client.complete_quest(quest_id, character_id)
        return assignment, ""
    except Exception as e:
        return None, str(e)


async def abandon_quest(quest_id: int, character_id: int) -> Tuple[APIQuestAssignment | None, str]:
    """Abandon a quest.

    Returns (assignment, error_message).
    """
    client = _get_quest_client()
    try:
        assignment = await client.abandon_quest(quest_id, character_id)
        return assignment, ""
    except Exception as e:
        return None, str(e)


# === Formatting Helpers ===

def format_quest_rewards(quest: APIQuest) -> str:
    """Format quest rewards for narration."""
    parts = []
    if quest.experience_reward > 0:
        parts.append(f"{quest.experience_reward} XP")
    if quest.gold_reward > 0:
        parts.append(f"{quest.gold_reward} gold")
    if quest.item_rewards:
        parts.append(f"{len(quest.item_rewards)} item(s)")

    if parts:
        return "Rewards: " + ", ".join(parts)
    return ""


def format_quest_for_narration(quest: APIQuest) -> str:
    """Format a quest for narrative display."""
    lines = [f"**{quest.title}**"]
    if quest.description:
        lines.append(quest.description)
    lines.append("")
    lines.append("Objectives:")
    for obj in quest.objectives:
        lines.append(f"  - {obj.description}")

    rewards = format_quest_rewards(quest)
    if rewards:
        lines.append("")
        lines.append(rewards)

    return "\n".join(lines)


def format_quest_status(assignment: APIQuestAssignment) -> str:
    """Format a quest assignment's status for display."""
    quest = assignment.quest
    lines = [f"**{quest.title}** ({assignment.status.value})"]

    if assignment.status == QuestStatus.ACTIVE:
        for progress in assignment.objectives_progress:
            status = "[x]" if progress.completed else "[ ]"
            count = f" ({progress.current_count}/{progress.target_count})" if progress.target_count > 1 else ""
            lines.append(f"  {status} {progress.description}{count}")

    return "\n".join(lines)


def format_active_quests_summary(assignments: List[APIQuestAssignment]) -> str:
    """Format all active quests for a summary display."""
    if not assignments:
        return "No active quests."

    lines = ["Active Quests:"]
    for assignment in assignments:
        lines.append(format_quest_status(assignment))
        lines.append("")

    return "\n".join(lines)


# === Frontend Serialization ===

async def serialize_quest_state(character_id: int) -> dict:
    """Serialize quest state for the frontend.

    Returns a structure compatible with the old story_state format:
    {
        "active": [{"id": ..., "title": ..., "objectives": [...]}],
        "completed": [{"id": ..., "title": ...}],
        "flags": {}
    }
    """
    active_list = []
    completed_list = []

    try:
        # Get active quests
        active = await get_active_quests(character_id)
        for assignment in active:
            quest = assignment.quest
            objectives = []
            for progress in assignment.objectives_progress:
                obj = next((o for o in quest.objectives if o.id == progress.objective_id), None)
                objectives.append({
                    "id": str(progress.objective_id),
                    "description": progress.description,
                    "type": obj.objective_type if obj else "generic",
                    "target": obj.target_identifier if obj else None,
                    "completed": progress.completed,
                })

            active_list.append({
                "id": str(quest.id),
                "title": quest.title,
                "summary": quest.description or "",
                "objectives": objectives,
            })

        # Get completed quests
        completed = await get_completed_quests(character_id)
        for assignment in completed:
            quest = assignment.quest
            completed_list.append({
                "id": str(quest.id),
                "title": quest.title,
                "summary": quest.description or "",
            })
    except Exception:
        pass

    return {
        "active": active_list,
        "completed": completed_list,
        "flags": {},
    }
