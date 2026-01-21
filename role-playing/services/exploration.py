"""
Exploration service for location navigation using the API.

Provides async functions for traveling between zones and describing locations.
"""

import random
from typing import List, Optional, Tuple

from api.client import LocationClient
from api.models import APIZone, APIExitWithDestination, APITravelResponse
from character import NPCCharacter
from services.npcs import random_dungeon_encounter
from core.settings import settings


# Default starting zone (The Stormhaven Tavern)
DEFAULT_STARTING_ZONE_ID = 1


def _get_location_client() -> LocationClient:
    """Get a location client instance."""
    return LocationClient(
        base_url=settings.rpg_api_base_url,
        timeout=settings.rpg_api_timeout,
    )


async def get_zone(zone_id: int) -> APIZone:
    """Get a zone by ID."""
    client = _get_location_client()
    return await client.get_zone(zone_id)


async def get_starting_zone() -> APIZone:
    """Get the default starting zone (tavern)."""
    return await get_zone(DEFAULT_STARTING_ZONE_ID)


async def get_available_exits(zone_id: int, include_hidden: bool = False) -> List[APIExitWithDestination]:
    """Get available exits from a zone."""
    client = _get_location_client()
    return await client.get_exits(zone_id, include_hidden)


async def find_exit_by_name(zone_id: int, exit_name: str, include_hidden: bool = False) -> Optional[APIExitWithDestination]:
    """Find an exit by name (case-insensitive partial match).

    Useful for natural language commands like "go through the tavern door".
    """
    client = _get_location_client()
    return await client.get_exit_by_name(zone_id, exit_name, include_hidden)


async def travel(exit_id: int, character_id: int) -> APITravelResponse:
    """Travel through an exit.

    Returns the travel result with new zone and available exits.
    """
    client = _get_location_client()
    return await client.travel(exit_id, character_id)


async def travel_by_exit_name(
    zone_id: int,
    exit_name: str,
    character_id: int,
    include_hidden: bool = False,
) -> Tuple[APITravelResponse | None, str]:
    """Travel through an exit by name.

    Returns (travel_response, error_message).
    If successful, error_message is empty.
    If failed, travel_response is None.
    """
    exit_obj = await find_exit_by_name(zone_id, exit_name, include_hidden)
    if exit_obj is None:
        # Get available exits to help the player
        exits = await get_available_exits(zone_id, include_hidden)
        if exits:
            exit_names = [f"'{e.name}'" for e in exits]
            return None, f"There is no exit called '{exit_name}' here. Available exits: {', '.join(exit_names)}"
        else:
            return None, f"There are no exits from this location."

    if exit_obj.locked:
        return None, f"The {exit_obj.name} is locked."

    result = await travel(exit_obj.id, character_id)
    return result, "" if result.success else result.message


async def describe_zone(zone: APIZone, include_exits: bool = True) -> str:
    """Get a description of a zone.

    If include_exits is True, also describes available exits.
    """
    description = zone.entry_description or zone.description or f"You are in {zone.name}."

    if include_exits:
        exits = await get_available_exits(zone.id)
        if exits:
            exit_descriptions = []
            for exit_obj in exits:
                if exit_obj.description:
                    exit_descriptions.append(f"{exit_obj.description}")
                else:
                    exit_descriptions.append(f"You can go through the {exit_obj.name}.")
            description += " " + " ".join(exit_descriptions)

    return description


async def describe_location_by_id(zone_id: int) -> str:
    """Get a description of a location by zone ID."""
    zone = await get_zone(zone_id)
    return await describe_zone(zone)


def format_exits_for_narration(exits: List[APIExitWithDestination]) -> str:
    """Format exits for natural language narration."""
    if not exits:
        return "There are no obvious exits."

    if len(exits) == 1:
        return f"You can leave through the {exits[0].name}."

    exit_names = [e.name for e in exits]
    if len(exit_names) == 2:
        return f"You can leave through the {exit_names[0]} or the {exit_names[1]}."

    last = exit_names[-1]
    others = ", ".join(exit_names[:-1])
    return f"You can leave through the {others}, or the {last}."


async def check_for_encounter(zone: APIZone) -> List[NPCCharacter]:
    """Check if entering a zone triggers a random encounter.

    Returns a list of enemy NPCs if an encounter occurs.
    """
    # Only trigger encounters in dungeon-like zones
    zone_name_lower = zone.name.lower()
    if "dungeon" in zone_name_lower and random.random() < 0.4:
        return random_dungeon_encounter()
    return []
