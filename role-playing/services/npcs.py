import random
from typing import Tuple, List, Dict, Any, Optional
import yaml
from pathlib import Path

from character import NPCCharacter, CharacterClass, create_random_npc, Item
from generators.npc_generator import create_npc_by_role
from core.state_service import GameStateService

# Load prefab NPCs from YAML once
_PREFABS_PATH = Path(__file__).parent.parent / "rules" / "prefab_npcs.yaml"
_PREFABS_CACHE: Dict[str, Dict[str, Any]] = {}


def _load_prefabs() -> None:
    global _PREFABS_CACHE
    if _PREFABS_CACHE:
        return
    if not _PREFABS_PATH.exists():
        _PREFABS_CACHE = {}
        return
    try:
        with open(_PREFABS_PATH, "r") as f:
            data = yaml.safe_load(f) or {}
        for entry in data.get("prefabs", []):
            name_key = entry.get("name", "").lower()
            role_key = entry.get("role", "").lower()
            if name_key:
                _PREFABS_CACHE[name_key] = entry
            if role_key and role_key not in _PREFABS_CACHE:
                _PREFABS_CACHE[role_key] = entry
    except Exception:
        _PREFABS_CACHE = {}


def _apply_prefab(npc: NPCCharacter, prefab: Dict[str, Any]) -> NPCCharacter:
    """Overlay prefab stats/inventory onto an NPC."""
    npc.name = prefab.get("name", npc.name)
    npc.disposition = prefab.get("disposition", npc.disposition)
    npc.merchant = bool(prefab.get("merchant", npc.merchant))
    npc.gold = prefab.get("gold", npc.gold)

    # Force class/level if provided
    if prefab.get("class"):
        try:
            npc.character_class = CharacterClass[prefab["class"].upper()]
        except Exception:
            pass
    if prefab.get("level"):
        npc.level = prefab["level"]

    # Replace inventory with prefab inventory if present
    if prefab.get("inventory"):
        npc.inventory = []
        for item_data in prefab["inventory"]:
            npc.inventory.append(
                Item(
                    name=item_data["name"],
                    description=item_data.get("description", ""),
                    item_type=item_data.get("type", "misc"),
                    properties=item_data.get("properties", {}),
                    quantity=item_data.get("quantity", 1),
                )
            )
    return npc


def get_prefab_entry(name_or_role: str) -> Optional[Dict[str, Any]]:
    _load_prefabs()
    key = name_or_role.lower()
    return _PREFABS_CACHE.get(key)


def get_prefab_npc(name_or_role: str) -> Optional[NPCCharacter]:
    """Synchronous helper for contexts that can't await generation (e.g., trading fallback)."""
    prefab = get_prefab_entry(name_or_role)
    if not prefab:
        return None
    base = create_random_npc(
        name=prefab.get("name", name_or_role.title()),
        character_class=CharacterClass[prefab.get("class", "rogue").upper()],
        level=prefab.get("level", 1),
        disposition=prefab.get("disposition", "friendly"),
    )
    return _apply_prefab(base, prefab)


def _npc_matches(npc: NPCCharacter, requested_name: str) -> bool:
    """Check if an NPC matches a requested name/role."""
    req = requested_name.lower()
    npc_name = npc.name.lower()
    
    # Exact match
    if npc_name == req:
        return True
    
    # Requested name is contained in NPC's full name (e.g., "barkeep" in "Grimbold the Barkeep")
    if req in npc_name:
        return True
    
    # NPC's first name matches (e.g., "grimbold" matches "Grimbold the Bartender")
    npc_first = npc_name.split()[0] if npc_name else ""
    if npc_first == req:
        return True
    
    # Check role stored on NPC (if we stored it)
    npc_role = getattr(npc, 'role', '').lower()
    if npc_role and (req == npc_role or req in npc_role):
        return True
    
    # Synonym matching for common roles
    role_synonyms = {
        'barkeep': ['bartender', 'innkeeper', 'tavernkeeper'],
        'bartender': ['barkeep', 'innkeeper', 'tavernkeeper'],
        'innkeeper': ['barkeep', 'bartender', 'tavernkeeper'],
        'merchant': ['trader', 'shopkeeper', 'vendor', 'seller'],
        'trader': ['merchant', 'shopkeeper', 'vendor'],
        'shopkeeper': ['merchant', 'trader', 'vendor'],
        'guard': ['soldier', 'watchman', 'sentry'],
        'soldier': ['guard', 'watchman', 'warrior'],
    }
    
    # Check if any synonym of the requested name appears in NPC name
    for synonym in role_synonyms.get(req, []):
        if synonym in npc_name:
            return True
    
    return False


async def get_or_create_npc(name: str, location: str, recent_events: List[str], existing_npcs: List[NPCCharacter]) -> Tuple[NPCCharacter, bool]:
    # Check existing NPCs with flexible matching
    for npc in existing_npcs:
        if _npc_matches(npc, name):
            return npc, False

    # Check prefabs
    prefab_entry = get_prefab_entry(name) or get_prefab_entry("merchant" if "shop" in name.lower() else name)

    if prefab_entry:
        # Generate a rich NPC, then overlay prefab stats/inventory to avoid rigid dialogue
        npc = await create_npc_by_role(name, location, recent_events)
        npc = _apply_prefab(npc, prefab_entry)
    else:
        npc = await create_npc_by_role(name, location, recent_events)
    
    # Store the original role so we can match it later
    npc.role = name.lower()
    
    existing_npcs.append(npc)
    return npc, True


def talk_to_npc(npc: NPCCharacter, player) -> Tuple[str, str]:
    # Support both APICharacter (from API) and legacy PlayerCharacter
    # APICharacter has get_modifier() method and charisma directly
    # Legacy PlayerCharacter has stats.get_modifier()
    if hasattr(player, 'get_modifier'):
        charisma_mod = player.get_modifier("charisma")
    else:
        charisma_mod = player.stats.get_modifier("charisma")
    reaction = npc.get_reaction(charisma_mod)
    dialogue = npc.get_dialogue("greeting")

    result = f"You approach {npc.name}. They seem {reaction}. {dialogue}"

    # Add quest hook for friendly NPCs
    if reaction in ["friendly", "very friendly"] and random.random() < 0.5:
        result += " 'Actually, I could use some help with something...'"

    # Add inventory hint for merchants
    if npc.merchant and reaction != "unfriendly":
        result += " You notice they have wares for trade."

    return result, reaction


def attack_npc(npc: NPCCharacter, player) -> str:
    if npc.name:
        return f"You attack {npc.name}!"
    return "You attack!"


def random_dungeon_encounter() -> List[NPCCharacter]:
    enemy_count = random.randint(1, 3)
    enemies = []
    for i in range(enemy_count):
        enemy = create_random_npc(
            name=f"Goblin {i+1}",
            character_class=CharacterClass.WARRIOR,
            level=1,
            disposition="hostile"
        )
        enemies.append(enemy)
    return enemies


async def describe_npc_inventory(npc_name: str, state: GameStateService) -> str:
    """
    Locate or create an NPC and return a textual description of their gold/items/merchant state.

    Uses the active_npc from state if it matches, otherwise creates a new NPC.
    """
    npc = None
    npc_created = False

    # Check if the active NPC matches the requested name (using flexible matching)
    if state.active_npc and _npc_matches(state.active_npc, npc_name):
        npc = state.active_npc

    if not npc:
        recent_events = state.ud.story_context[-3:] if state.ud.story_context else []
        npc = await create_npc_by_role(npc_name, state.location, recent_events)
        state.set_active_npc(npc)
        npc_created = True

    if npc.disposition == "hostile":
        return f"{npc.name} is too hostile to show you their wares!"

    result = ""
    if npc_created:
        result = f"You find {npc.name}, a {npc.character_class.value}. "

    result += f"{npc.name} has {npc.gold} gold"

    if npc.inventory:
        items = []
        for item in npc.inventory:
            if item.quantity > 1:
                items.append(f"{item.name} ({item.quantity})")
            else:
                items.append(item.name)
        result += f" and carries: {', '.join(items)}."
    else:
        result += " but carries no items."

    if npc.merchant:
        result += " They seem eager to trade."
    elif npc.disposition == "friendly":
        result += " They might be willing to trade."

    return result
