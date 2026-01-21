"""
Player character services using the RPG API.

All character operations go through the API. The API is the source of truth.
"""

import random
import logging
from typing import Optional

from core.settings import settings

logger = logging.getLogger("dungeons-and-agents.services")


async def create_player(name: str, class_str: str) -> int:
    """
    Create a player character via the RPG API.

    Args:
        name: Character name
        class_str: Class name (warrior, mage, rogue, cleric, ranger)

    Returns:
        The character ID for storage in GameUserData.
    """
    from api.client import CharacterClient

    # Map class name to API enum value
    class_map = {
        "warrior": "warrior",
        "mage": "mage",
        "rogue": "rogue",
        "cleric": "cleric",
        "ranger": "ranger",
    }
    chosen_class = class_map.get(class_str.lower(), "warrior")

    # Generate random stats (8-18 range)
    stats = {
        "strength": random.randint(8, 18),
        "dexterity": random.randint(8, 18),
        "constitution": random.randint(8, 18),
        "intelligence": random.randint(8, 18),
        "wisdom": random.randint(8, 18),
        "charisma": random.randint(8, 18),
    }

    # Create character via API
    char_client = CharacterClient(
        base_url=settings.rpg_api_base_url,
        timeout=settings.rpg_api_timeout,
    )

    character = await char_client.create(
        name=name,
        character_class=chosen_class,
        character_type="player",
        level=1,
        gold=50,  # Starting gold
        **stats,
    )

    logger.info(f"Created player via API: {character.name} (ID: {character.id})")

    # Add starting equipment via API
    await _add_starting_equipment(character.id, chosen_class)

    # Auto-assign starting quest
    await _assign_starting_quest(character.id)

    return character.id


async def _add_starting_equipment(character_id: int, character_class: str):
    """Add starting equipment to a character via the API."""
    from api.client import InventoryClient

    inv_client = InventoryClient(
        base_url=settings.rpg_api_base_url,
        timeout=settings.rpg_api_timeout,
    )

    # Define starting items by class
    starting_items = {
        "warrior": [
            {"name": "Longsword", "type": "weapon", "slot": "main_hand", "properties": {"damage_dice": "1d8", "damage_type": "slashing"}},
            {"name": "Chain Mail", "type": "armor", "slot": "chest", "properties": {"armor_bonus": 6}},
        ],
        "mage": [
            {"name": "Quarterstaff", "type": "weapon", "slot": "main_hand", "properties": {"damage_dice": "1d6", "damage_type": "bludgeoning"}},
            {"name": "Spellbook", "type": "misc", "slot": None, "properties": {}},
        ],
        "rogue": [
            {"name": "Dagger", "type": "weapon", "slot": "main_hand", "properties": {"damage_dice": "1d4", "damage_type": "piercing", "properties": ["finesse"]}},
            {"name": "Leather Armor", "type": "armor", "slot": "chest", "properties": {"armor_bonus": 2}},
        ],
        "cleric": [
            {"name": "Mace", "type": "weapon", "slot": "main_hand", "properties": {"damage_dice": "1d6", "damage_type": "bludgeoning"}},
            {"name": "Scale Mail", "type": "armor", "slot": "chest", "properties": {"armor_bonus": 4}},
        ],
        "ranger": [
            {"name": "Longbow", "type": "weapon", "slot": "main_hand", "properties": {"damage_dice": "1d8", "damage_type": "piercing", "range": "150/600"}},
            {"name": "Leather Armor", "type": "armor", "slot": "chest", "properties": {"armor_bonus": 2}},
        ],
    }

    items_to_add = starting_items.get(character_class, starting_items["warrior"])

    for item_data in items_to_add:
        try:
            # Create the item definition
            item = await inv_client.create_item(
                name=item_data["name"],
                item_type=item_data["type"],
                description=f"Starting {item_data['type']} for {character_class}",
                properties=item_data.get("properties", {}),
            )

            # Add to inventory
            inv_item = await inv_client.add_item(
                character_id=character_id,
                item_id=item.id,
                quantity=1,
            )

            # Equip if it has a slot
            if item_data.get("slot"):
                await inv_client.equip_item(
                    character_id=character_id,
                    inventory_item_id=inv_item.id,
                    equipment_slot=item_data["slot"],
                )

            logger.info(f"Added {item_data['name']} to character {character_id}")

        except Exception as e:
            logger.warning(f"Failed to add starting item {item_data['name']}: {e}")

    # Add healing potions
    try:
        potion = await inv_client.create_item(
            name="Healing Potion",
            item_type="consumable",
            description="Restores 2d4+2 hit points",
            stackable=True,
            max_stack=10,
            properties={"healing_dice": "2d4+2", "effect_type": "heal"},
        )
        await inv_client.add_item(
            character_id=character_id,
            item_id=potion.id,
            quantity=2,
        )
        logger.info(f"Added 2x Healing Potion to character {character_id}")
    except Exception as e:
        logger.warning(f"Failed to add healing potions: {e}")


async def _assign_starting_quest(character_id: int):
    """Auto-assign the starting quest to a new character."""
    from api.client import QuestClient

    quest_client = QuestClient(
        base_url=settings.rpg_api_base_url,
        timeout=settings.rpg_api_timeout,
    )

    # Quest 1 is the starting quest "Rumors in the Stormhaven Tavern"
    STARTING_QUEST_ID = 1

    try:
        # Check if already assigned (e.g., from previous session)
        existing = await quest_client.get_character_quests(character_id)
        if any(a.quest_id == STARTING_QUEST_ID for a in existing):
            logger.info(f"Starting quest already assigned to character {character_id}")
            return

        assignment = await quest_client.assign_quest(STARTING_QUEST_ID, character_id)
        logger.info(f"Auto-assigned starting quest '{assignment.quest.title}' to character {character_id}")
    except Exception as e:
        logger.warning(f"Failed to assign starting quest: {e}")


async def get_player(character_id: int):
    """Fetch a player character from the API."""
    from api.client import CharacterClient

    client = CharacterClient(
        base_url=settings.rpg_api_base_url,
        timeout=settings.rpg_api_timeout,
    )
    return await client.get(character_id)


async def describe_inventory(character_id: int) -> str:
    """Get a description of the player's inventory from the API."""
    from api.client import CharacterClient, InventoryClient

    char_client = CharacterClient(
        base_url=settings.rpg_api_base_url,
        timeout=settings.rpg_api_timeout,
    )
    inv_client = InventoryClient(
        base_url=settings.rpg_api_base_url,
        timeout=settings.rpg_api_timeout,
    )

    character = await char_client.get(character_id)
    inventory = await inv_client.get_inventory(character_id)

    desc = f"You have {character.gold} gold pieces."

    # Find equipped items
    equipped_weapon = None
    equipped_armor = None
    pack_items = []

    for inv_item in inventory:
        if inv_item.equipped:
            if inv_item.item.item_type.value == "weapon":
                equipped_weapon = inv_item.item.name
            elif inv_item.item.item_type.value == "armor":
                equipped_armor = inv_item.item.name
        else:
            if inv_item.quantity > 1:
                pack_items.append(f"{inv_item.item.name} ({inv_item.quantity})")
            else:
                pack_items.append(inv_item.item.name)

    if equipped_weapon:
        desc += f" Wielding: {equipped_weapon}."
    if equipped_armor:
        desc += f" Wearing: {equipped_armor}."

    if pack_items:
        desc += f" In your pack: {', '.join(pack_items)}."
    else:
        desc += " Your pack is empty."

    return desc


async def use_item(character_id: int, item_name: str) -> str:
    """
    Use an item from the player's inventory.

    For consumables, the item is used and removed from inventory.
    For equipment, the item is equipped.
    """
    from api.client import CharacterClient, InventoryClient

    char_client = CharacterClient(
        base_url=settings.rpg_api_base_url,
        timeout=settings.rpg_api_timeout,
    )
    inv_client = InventoryClient(
        base_url=settings.rpg_api_base_url,
        timeout=settings.rpg_api_timeout,
    )

    inventory = await inv_client.get_inventory(character_id)

    # Find the item
    inv_item = None
    for item in inventory:
        if item.item.name.lower() == item_name.lower():
            inv_item = item
            break

    if not inv_item:
        return f"You don't have a {item_name}."

    item = inv_item.item
    item_type = item.item_type.value

    if item_type == "consumable":
        # Use consumable
        if item.properties and item.properties.get("healing_dice"):
            # Healing item - this is handled by the API when using in combat
            # For exploration, we'd need a separate endpoint
            # For now, remove the item and report the effect
            await inv_client.remove_item(character_id, inv_item.id, quantity=1)

            character = await char_client.get(character_id)
            return f"You drink the {item.name}. You feel refreshed!"
        else:
            return f"You use the {item.name}."

    elif item_type == "weapon":
        # Equip weapon
        await inv_client.equip_item(character_id, inv_item.id, "main_hand")
        return f"You equip the {item.name}."

    elif item_type == "armor":
        # Equip armor
        await inv_client.equip_item(character_id, inv_item.id, "chest")
        return f"You put on the {item.name}."

    else:
        return f"You examine the {item.name}. {item.description or 'It looks ordinary.'}"
