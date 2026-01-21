import random
from datetime import datetime
from sqlalchemy.orm import Session

from .models import CombatSession, Combatant, CombatAction
from .schemas import CombatStartRequest, PlayerActionRequest
from ..core.enums import CombatStatus, ActionType, CharacterClass, CharacterType, CharacterStatus, InitiativeType
from ..core.exceptions import NotFoundError, CombatError
from ..character.service import get_character, award_experience
from ..character.models import Character, CLASS_BONUSES
from ..reference.router import load_spells, load_consumables, load_status_effects, load_class_abilities, get_terrain_effect, get_loot_table_for_monster, get_loot_table
from ..inventory.models import InventoryItem, Item
from ..core.enums import ItemType


def get_combat_session(db: Session, session_id: int) -> CombatSession:
    session = db.query(CombatSession).filter(CombatSession.id == session_id).first()
    if not session:
        raise NotFoundError("CombatSession", session_id)
    return session


def get_combatant(db: Session, combatant_id: int) -> Combatant:
    combatant = db.query(Combatant).filter(Combatant.id == combatant_id).first()
    if not combatant:
        raise NotFoundError("Combatant", combatant_id)
    return combatant


def roll_d20() -> int:
    return random.randint(1, 20)


def get_terrain_cover_bonus(db: Session, session: CombatSession, combatant: Combatant) -> int:
    """Get terrain cover bonus for a combatant based on their character's position."""
    if not session.zone_id:
        return 0

    # Get the character to find their position
    character = db.query(Character).filter(Character.id == combatant.character_id).first()
    if not character or not character.zone_id:
        return 0

    # Get the grid cell at character's position
    from ..location.service import get_grid_cell
    grid_cell = get_grid_cell(db, character.zone_id, character.x, character.y)
    if not grid_cell:
        return 0

    # Get terrain effect
    terrain_effect = get_terrain_effect(grid_cell.terrain_type.value)
    if not terrain_effect:
        return 0

    return terrain_effect.get("cover_bonus", 0)


def get_combatant_distance(db: Session, attacker: Combatant, target: Combatant) -> int:
    """Calculate distance between two combatants based on character positions."""
    attacker_char = db.query(Character).filter(Character.id == attacker.character_id).first()
    target_char = db.query(Character).filter(Character.id == target.character_id).first()

    if not attacker_char or not target_char:
        return 0  # Can't determine distance

    # If in different zones, consider them far apart
    if attacker_char.zone_id != target_char.zone_id:
        return 999

    # Calculate euclidean distance (each grid square is 5 feet)
    dx = abs(attacker_char.x - target_char.x)
    dy = abs(attacker_char.y - target_char.y)

    # Use Chebyshev distance (diagonal = 1) for D&D-style grid
    grid_distance = max(dx, dy)

    # Convert to feet (5 feet per square), adjacent = 5 feet
    return max(5, grid_distance * 5)


def parse_weapon_range(range_str: str | None) -> tuple[int, int]:
    """Parse weapon range string (e.g., '20/60') into (normal, long) ranges in feet."""
    if not range_str:
        return (5, 5)  # Melee default (5 feet)

    try:
        parts = range_str.split("/")
        normal_range = int(parts[0])
        long_range = int(parts[1]) if len(parts) > 1 else normal_range
        return (normal_range, long_range)
    except (ValueError, IndexError):
        return (5, 5)


def check_weapon_range(weapon: Item | None, distance: int) -> dict:
    """
    Check if target is within weapon range.

    Returns:
        dict with keys:
        - in_range: bool, whether attack is possible
        - at_disadvantage: bool, whether attack is at long range (disadvantage)
        - range_info: str, description of range situation
        - is_ranged: bool, whether this is a ranged attack
    """
    result = {
        "in_range": True,
        "at_disadvantage": False,
        "range_info": "melee range",
        "is_ranged": False,
    }

    if not weapon or not weapon.properties:
        # Unarmed - melee only, 5 feet range
        if distance > 5:
            result["in_range"] = False
            result["range_info"] = f"target is {distance} feet away, unarmed reach is 5 feet"
        return result

    weapon_props = weapon.properties
    weapon_range = weapon_props.get("range")
    has_reach = "reach" in weapon_props.get("properties", [])
    is_thrown = "thrown" in weapon_props.get("properties", [])
    is_ammunition = "ammunition" in weapon_props.get("properties", [])

    # Determine if this is a ranged weapon
    is_ranged_weapon = is_ammunition or weapon_props.get("category", "").endswith("_ranged")

    # Calculate effective melee range
    melee_range = 10 if has_reach else 5

    if is_ranged_weapon:
        # Ranged weapon (bows, crossbows)
        result["is_ranged"] = True
        normal_range, long_range = parse_weapon_range(weapon_range)

        if distance > long_range:
            result["in_range"] = False
            result["range_info"] = f"target is {distance} feet away, max range is {long_range} feet"
        elif distance > normal_range:
            result["at_disadvantage"] = True
            result["range_info"] = f"long range ({distance} feet, normal is {normal_range})"
        else:
            result["range_info"] = f"normal range ({distance} feet)"
    elif is_thrown:
        # Thrown melee weapon (dagger, javelin)
        if distance <= melee_range:
            # Melee attack
            result["range_info"] = "melee range"
        else:
            # Thrown attack
            result["is_ranged"] = True
            normal_range, long_range = parse_weapon_range(weapon_range)

            if distance > long_range:
                result["in_range"] = False
                result["range_info"] = f"target is {distance} feet away, max throw range is {long_range} feet"
            elif distance > normal_range:
                result["at_disadvantage"] = True
                result["range_info"] = f"long throw range ({distance} feet, normal is {normal_range})"
            else:
                result["range_info"] = f"thrown ({distance} feet)"
    else:
        # Pure melee weapon
        if distance > melee_range:
            result["in_range"] = False
            result["range_info"] = f"target is {distance} feet away, melee reach is {melee_range} feet"

    return result


def roll_damage(dice_str: str = "1d6") -> int:
    """Roll damage dice. Format: NdM (e.g., 2d6, 1d8)"""
    try:
        num, sides = dice_str.lower().split("d")
        num = int(num) if num else 1
        sides = int(sides)
        return sum(random.randint(1, sides) for _ in range(num))
    except (ValueError, AttributeError):
        return random.randint(1, 6)  # Default to 1d6


def calculate_initiative(character) -> int:
    """Calculate initiative: d20 + DEX modifier + class bonus."""
    base_roll = roll_d20()
    dex_mod = (character.dexterity - 10) // 2

    # Rogues get +2 initiative bonus
    class_bonus = 0
    if character.character_class == CharacterClass.ROGUE:
        class_bonus = 2

    return base_roll + dex_mod + class_bonus


def calculate_threat_weight(combatant: Combatant) -> float:
    """Calculate targeting weight based on threat and HP."""
    base_weight = 10 + (combatant.threat * 2)

    # Low HP bonus: 1.5x weight if HP < 25% of max
    if combatant.current_hp < combatant.max_hp * 0.25:
        base_weight *= 1.5

    return base_weight


def sync_combatant_hp_to_character(db: Session, combatant: Combatant):
    """Sync combatant's current HP back to their character."""
    character = db.query(Character).filter(Character.id == combatant.character_id).first()
    if character:
        character.current_hp = combatant.current_hp


def process_dropping_to_zero_hp(db: Session, combatant: Combatant) -> dict:
    """
    Handle a combatant dropping to 0 HP.
    - Players: go unconscious (death saves)
    - NPCs/monsters: die immediately
    Returns dict with status info.
    """
    character = db.query(Character).filter(Character.id == combatant.character_id).first()
    if not character:
        return {"died": True, "dead": True}

    combatant.current_hp = 0
    character.current_hp = 0

    # NPCs/monsters die immediately at 0 HP (standard D&D 5e rules)
    if not combatant.is_player:
        character.status = CharacterStatus.DEAD
        combatant.is_alive = False
        combatant.can_act = False
        return {
            "died": True,
            "dead": True,
            "unconscious": False,
            "message": f"{combatant.name} is slain!"
        }

    # Players go unconscious and make death saves
    character.status = CharacterStatus.UNCONSCIOUS

    # Reset death saves
    character.death_save_successes = 0
    character.death_save_failures = 0
    character.is_stable = 0

    # Mark as not able to act (but still technically "alive" for combat tracking)
    combatant.can_act = False

    return {
        "died": False,
        "dead": False,
        "unconscious": True,
        "message": f"{combatant.name} falls unconscious!"
    }


def process_death_saving_throw(db: Session, combatant: Combatant) -> dict:
    """
    Process a death saving throw for an unconscious combatant.
    Returns dict with result info.
    """
    character = db.query(Character).filter(Character.id == combatant.character_id).first()
    if not character:
        return {"error": "Character not found"}

    # Already stable or dead
    if character.is_stable:
        return {"stable": True, "message": f"{combatant.name} is stable."}

    if character.status == CharacterStatus.DEAD:
        return {"dead": True, "message": f"{combatant.name} is dead."}

    # Roll death save
    roll = roll_d20()
    result = {
        "roll": roll,
        "successes": character.death_save_successes,
        "failures": character.death_save_failures,
    }

    if roll == 20:
        # Natural 20: regain 1 HP and wake up
        character.current_hp = 1
        combatant.current_hp = 1
        character.status = CharacterStatus.ALIVE
        character.death_save_successes = 0
        character.death_save_failures = 0
        combatant.can_act = True
        combatant.is_alive = True
        result["message"] = f"{combatant.name} rolls a natural 20! They regain 1 HP and wake up!"
        result["woke_up"] = True
    elif roll == 1:
        # Natural 1: counts as 2 failures
        character.death_save_failures += 2
        result["failures"] = character.death_save_failures
        result["message"] = f"{combatant.name} rolls a natural 1! Two death save failures ({character.death_save_failures}/3)."
    elif roll >= 10:
        # Success
        character.death_save_successes += 1
        result["successes"] = character.death_save_successes
        if character.death_save_successes >= 3:
            character.is_stable = 1
            result["message"] = f"{combatant.name} rolls {roll} - success! They stabilize ({character.death_save_successes}/3 successes)."
            result["stable"] = True
        else:
            result["message"] = f"{combatant.name} rolls {roll} - success! ({character.death_save_successes}/3 successes)."
    else:
        # Failure
        character.death_save_failures += 1
        result["failures"] = character.death_save_failures
        result["message"] = f"{combatant.name} rolls {roll} - failure! ({character.death_save_failures}/3 failures)."

    # Check for death
    if character.death_save_failures >= 3:
        character.status = CharacterStatus.DEAD
        combatant.is_alive = False
        result["message"] = f"{combatant.name} rolls {roll} - failure! They have died ({character.death_save_failures}/3 failures)."
        result["dead"] = True

    return result


def process_damage_while_unconscious(db: Session, combatant: Combatant, damage: int, is_melee_crit: bool = False) -> dict:
    """
    Process taking damage while at 0 HP.
    Returns dict with result info.
    """
    character = db.query(Character).filter(Character.id == combatant.character_id).first()
    if not character:
        return {"error": "Character not found"}

    # Damage while unconscious = automatic death save failure
    # Melee crit = 2 failures
    failures_to_add = 2 if is_melee_crit else 1
    character.death_save_failures += failures_to_add

    result = {
        "failures_added": failures_to_add,
        "total_failures": character.death_save_failures,
    }

    if character.death_save_failures >= 3:
        character.status = CharacterStatus.DEAD
        combatant.is_alive = False
        result["dead"] = True
        result["message"] = f"{combatant.name} takes damage while unconscious and dies!"
    else:
        result["message"] = f"{combatant.name} takes damage while unconscious! ({character.death_save_failures}/3 failures)."

    return result


def heal_unconscious_character(db: Session, combatant: Combatant, healing: int) -> dict:
    """
    Heal an unconscious character - any healing wakes them up.
    Returns dict with result info.
    """
    character = db.query(Character).filter(Character.id == combatant.character_id).first()
    if not character:
        return {"error": "Character not found"}

    # Any healing while at 0 HP wakes them up
    character.current_hp = min(character.max_hp, healing)
    combatant.current_hp = character.current_hp
    character.status = CharacterStatus.ALIVE
    character.death_save_successes = 0
    character.death_save_failures = 0
    character.is_stable = 0
    combatant.can_act = True
    combatant.is_alive = True

    return {
        "woke_up": True,
        "new_hp": character.current_hp,
        "message": f"{combatant.name} receives healing and wakes up with {character.current_hp} HP!"
    }


def get_equipped_weapon(db: Session, character_id: int) -> Item | None:
    """Get the character's equipped weapon (main_hand or off_hand)."""
    inv_item = db.query(InventoryItem).join(Item).filter(
        InventoryItem.character_id == character_id,
        InventoryItem.equipped == True,
        InventoryItem.equipment_slot.in_(["main_hand", "off_hand"]),
        Item.item_type == ItemType.WEAPON,
    ).first()
    return inv_item.item if inv_item else None


def get_equipped_item(db: Session, character_id: int, slot: str) -> Item | None:
    """Get the item equipped in a specific slot."""
    inv_item = db.query(InventoryItem).join(Item).filter(
        InventoryItem.character_id == character_id,
        InventoryItem.equipped == True,
        InventoryItem.equipment_slot == slot,
    ).first()
    return inv_item.item if inv_item else None


def select_target(db: Session, attacker: Combatant, session: CombatSession) -> Combatant | None:
    """Select a target using threat-based weighted random selection."""
    # Get alive enemies
    enemies = [
        c for c in session.combatants
        if c.is_alive and c.team_id != attacker.team_id
    ]

    if not enemies:
        return None

    # Calculate weights
    weights = [calculate_threat_weight(e) for e in enemies]
    total_weight = sum(weights)

    # Weighted random selection
    roll = random.uniform(0, total_weight)
    cumulative = 0
    for enemy, weight in zip(enemies, weights):
        cumulative += weight
        if roll <= cumulative:
            return enemy

    return enemies[-1]  # Fallback


def roll_group_initiative(combatants: list[Combatant], characters: dict[int, Character]):
    """Roll one initiative per team, all team members share it."""
    teams = set(c.team_id for c in combatants)
    team_initiatives = {}

    for team_id in teams:
        # Use the first character from the team for the roll
        team_members = [c for c in combatants if c.team_id == team_id]
        if team_members:
            char = characters.get(team_members[0].character_id)
            team_initiatives[team_id] = calculate_initiative(char) if char else random.randint(1, 20)

    for combatant in combatants:
        combatant.initiative = team_initiatives[combatant.team_id]


def roll_side_initiative(combatants: list[Combatant]):
    """Alternate turns between teams (Team 1 all go, then Team 2 all go)."""
    teams = sorted(set(c.team_id for c in combatants))
    team_order = {}

    # Roll to determine which team goes first
    rolls = {team: random.randint(1, 20) for team in teams}
    sorted_teams = sorted(teams, key=lambda t: rolls[t], reverse=True)

    for i, team_id in enumerate(sorted_teams):
        team_order[team_id] = i * 100  # Base initiative by team order

    for combatant in combatants:
        # Within a team, order doesn't matter much but we'll randomize
        combatant.initiative = team_order[combatant.team_id] + random.randint(1, 99)


def reroll_initiative_for_round(db: Session, session: CombatSession):
    """Re-roll initiative for all combatants (used with REROLL initiative type)."""
    characters = {}
    for combatant in session.combatants:
        if combatant.is_alive:
            char = get_character(db, combatant.character_id)
            characters[combatant.character_id] = char
            combatant.initiative = calculate_initiative(char)

    # Re-sort by initiative
    alive_combatants = [c for c in session.combatants if c.is_alive and c.can_act]
    random.shuffle(alive_combatants)  # Randomize to break ties
    alive_combatants.sort(key=lambda c: c.initiative, reverse=True)

    # Reassign turn order
    for i, combatant in enumerate(alive_combatants):
        combatant.turn_order = i


def start_combat(db: Session, request: CombatStartRequest) -> CombatSession:
    """Initialize combat with participants."""
    # Create session
    session = CombatSession(
        status=CombatStatus.INITIALIZING,
        zone_id=request.zone_id,
        initiative_type=request.initiative_type,
    )
    db.add(session)
    db.flush()

    # Create combatants
    combatants = []
    characters = {}  # Cache characters for initiative calculations
    for participant in request.participants:
        character = get_character(db, participant.character_id)
        characters[character.id] = character

        combatant = Combatant(
            session_id=session.id,
            character_id=character.id,
            team_id=participant.team_id,
            is_player=character.character_type == CharacterType.PLAYER,
            name=character.name,
            initiative=0,  # Set below based on initiative type
            current_hp=character.current_hp,
            max_hp=character.max_hp,
            armor_class=character.armor_class,
            threat=0,
        )
        db.add(combatant)
        combatants.append(combatant)

    db.flush()

    # Roll initiative based on type
    initiative_type = request.initiative_type

    if initiative_type == InitiativeType.INDIVIDUAL or initiative_type == InitiativeType.REROLL:
        # Standard individual initiative
        for combatant in combatants:
            char = characters.get(combatant.character_id)
            combatant.initiative = calculate_initiative(char) if char else random.randint(1, 20)

    elif initiative_type == InitiativeType.GROUP:
        # One roll per team
        roll_group_initiative(combatants, characters)

    elif initiative_type == InitiativeType.SIDE:
        # Alternating team turns
        roll_side_initiative(combatants)

    # Sort by initiative (highest first), ties broken randomly
    random.shuffle(combatants)  # Randomize first to break ties
    combatants.sort(key=lambda c: c.initiative, reverse=True)

    # Assign turn order
    for i, combatant in enumerate(combatants):
        combatant.turn_order = i

    session.status = CombatStatus.IN_PROGRESS
    db.commit()
    db.refresh(session)
    return session


def get_current_combatant(session: CombatSession) -> Combatant | None:
    """Get the combatant whose turn it is."""
    alive_combatants = [c for c in session.combatants if c.is_alive and c.can_act]
    if not alive_combatants:
        return None

    sorted_combatants = sorted(alive_combatants, key=lambda c: c.turn_order)
    turn_index = session.current_turn % len(sorted_combatants)
    return sorted_combatants[turn_index]


def check_combat_end(session: CombatSession) -> int | None:
    """Check if combat should end. Returns winning team_id or None."""
    teams_alive = set()
    for combatant in session.combatants:
        if combatant.is_alive:
            teams_alive.add(combatant.team_id)

    if len(teams_alive) <= 1:
        return teams_alive.pop() if teams_alive else None
    return None


def get_npc_healing_potion(db: Session, character_id: int) -> InventoryItem | None:
    """Get a healing potion from NPC's inventory."""
    inv_item = db.query(InventoryItem).join(Item).filter(
        InventoryItem.character_id == character_id,
        Item.item_type == ItemType.CONSUMABLE,
        Item.name.ilike("%healing potion%"),
    ).first()
    return inv_item


def npc_can_cast_spell(character: Character, spell_name: str) -> bool:
    """Check if an NPC can cast a specific spell."""
    spells = load_spells()
    spell = next((s for s in spells if s["name"].lower() == spell_name.lower()), None)
    if not spell:
        return False

    # Check class
    if character.character_class.value not in spell.get("classes", []):
        return False

    # Check spell slots (cantrips are always available)
    spell_level = spell["level"]
    if spell_level > 0:
        slots = character.spell_slots or {}
        if slots.get(str(spell_level), 0) <= 0:
            return False

    return True


def npc_select_offensive_spell(character: Character) -> str | None:
    """Select the best offensive spell an NPC can cast."""
    spells = load_spells()
    char_class = character.character_class.value

    # Priority: highest level damage spells first
    damage_spells = [s for s in spells if "damage_dice" in s and char_class in s.get("classes", [])]
    damage_spells.sort(key=lambda s: s["level"], reverse=True)

    for spell in damage_spells:
        if npc_can_cast_spell(character, spell["name"]):
            return spell["name"]

    return None


def npc_select_healing_spell(character: Character) -> str | None:
    """Select a healing spell an NPC can cast."""
    spells = load_spells()
    char_class = character.character_class.value

    # Priority: highest level healing spells first
    healing_spells = [s for s in spells if "healing_dice" in s and char_class in s.get("classes", [])]
    healing_spells.sort(key=lambda s: s["level"], reverse=True)

    for spell in healing_spells:
        if npc_can_cast_spell(character, spell["name"]):
            return spell["name"]

    return None


def npc_get_available_ability(db: Session, character: Character) -> str | None:
    """Get an available combat ability for the NPC."""
    abilities = load_class_abilities()
    char_class = character.character_class.value

    # Filter to this class's abilities that don't require targets
    class_abilities = [a for a in abilities
                       if a.get("class") == char_class
                       and a.get("min_level", 1) <= character.level
                       and a.get("effect_type") in ["heal_self", "extra_action", "recover_slots"]]

    ability_uses = character.ability_uses or {}

    for ability in class_abilities:
        ability_id = ability["id"]
        max_uses = ability.get("max_uses")
        if max_uses:
            remaining = ability_uses.get(ability_id, max_uses)
            if remaining > 0:
                return ability_id

    return None


def process_npc_action(db: Session, session: CombatSession, combatant: Combatant) -> CombatAction:
    """Process an NPC's turn with improved AI."""
    # Clear defending/dodging status at the start of this combatant's turn
    clear_defending_status(combatant)
    if has_status_effect(combatant, "dodging"):
        remove_status_effect(combatant, "dodging")

    # Process status effects (damage over time, etc.)
    effect_messages = process_status_effects_start_of_turn(db, session, combatant)

    # Check if combatant died from status effect damage
    if not combatant.is_alive:
        description = " ".join(effect_messages) if effect_messages else f"{combatant.name} is incapacitated."
        action = CombatAction(
            session_id=session.id,
            round_number=session.round_number,
            turn_number=session.current_turn,
            actor_combatant_id=combatant.id,
            action_type=ActionType.PASS,
            description=description,
        )
        db.add(action)
        return action

    # Check if stunned/paralyzed - skip turn
    if has_status_effect(combatant, "stunned") or has_status_effect(combatant, "paralyzed"):
        effect_name = "Stunned" if has_status_effect(combatant, "stunned") else "Paralyzed"
        description = f"{combatant.name} is {effect_name.lower()} and cannot act!"
        if effect_messages:
            description = " ".join(effect_messages) + " " + description
        action = CombatAction(
            session_id=session.id,
            round_number=session.round_number,
            turn_number=session.current_turn,
            actor_combatant_id=combatant.id,
            action_type=ActionType.PASS,
            description=description,
        )
        db.add(action)
        return action

    # Get character for AI decisions
    character = get_character(db, combatant.character_id)
    hp_percent = combatant.current_hp / combatant.max_hp if combatant.max_hp > 0 else 1.0

    # AI Decision Tree:

    # 1. If very low HP (< 20%), try to flee
    if hp_percent < 0.20:
        # 50% chance to attempt flee when very low
        if random.random() < 0.5:
            return execute_flee(db, session, combatant)

    # 2. If low HP (< 40%), try to heal
    if hp_percent < 0.40:
        # Try healing potion first
        healing_potion = get_npc_healing_potion(db, character.id)
        if healing_potion:
            try:
                return execute_item(db, session, combatant, combatant, healing_potion.id)
            except:
                pass  # If item use fails, continue to other options

        # Try healing spell (for clerics)
        healing_spell = npc_select_healing_spell(character)
        if healing_spell:
            try:
                return execute_spell(db, session, combatant, combatant, healing_spell)
            except:
                pass  # If spell fails, continue

        # Try self-healing ability (Second Wind for warriors)
        ability = npc_get_available_ability(db, character)
        if ability:
            try:
                return execute_ability(db, session, combatant, None, ability)
            except:
                pass

    # 3. Find a target for offensive actions
    target = select_target(db, combatant, session)

    if not target:
        # No valid target, pass
        description = f"{combatant.name} has no valid target and passes."
        if effect_messages:
            description = " ".join(effect_messages) + " " + description
        action = CombatAction(
            session_id=session.id,
            round_number=session.round_number,
            turn_number=session.current_turn,
            actor_combatant_id=combatant.id,
            action_type=ActionType.PASS,
            description=description,
        )
        db.add(action)
        return action

    # 4. Try offensive spell (for mages/clerics)
    if character.character_class.value in ["mage", "cleric"]:
        offensive_spell = npc_select_offensive_spell(character)
        if offensive_spell and random.random() < 0.7:  # 70% chance to cast spell if available
            try:
                return execute_spell(db, session, combatant, target, offensive_spell)
            except:
                pass  # If spell fails, fall back to attack

    # 5. Default: attack
    return execute_attack(db, session, combatant, target)


def execute_attack(db: Session, session: CombatSession, attacker: Combatant, target: Combatant) -> CombatAction:
    """Execute a basic attack."""
    # Get attacker's character for attribute modifiers
    character = get_character(db, attacker.character_id)
    str_mod = (character.strength - 10) // 2
    dex_mod = (character.dexterity - 10) // 2

    # Get equipped weapon (if any)
    weapon = get_equipped_weapon(db, character.id)
    weapon_hit_bonus = 0
    damage_dice = "1d4"  # Unarmed default
    weapon_properties = []

    if weapon and weapon.properties:
        damage_dice = weapon.properties.get("damage_dice", "1d6")
        weapon_hit_bonus = weapon.properties.get("hit_bonus", 0)
        weapon_properties = weapon.properties.get("properties", [])

        # Handle versatile weapons - use larger dice if no off-hand item
        if "versatile" in weapon_properties:
            offhand = get_equipped_item(db, character.id, "off_hand")
            if not offhand:
                versatile_dice = weapon.properties.get("versatile_dice")
                if versatile_dice:
                    damage_dice = versatile_dice

    # Determine attack modifier (finesse uses better of STR or DEX)
    if "finesse" in weapon_properties:
        attack_mod = max(str_mod, dex_mod)
    else:
        attack_mod = str_mod

    # Check distance and weapon range
    distance = get_combatant_distance(db, attacker, target)
    range_check = check_weapon_range(weapon, distance)

    if not range_check["in_range"]:
        # Target out of range
        action = CombatAction(
            session_id=session.id,
            round_number=session.round_number,
            turn_number=session.current_turn,
            actor_combatant_id=attacker.id,
            target_combatant_id=target.id,
            action_type=ActionType.ATTACK,
            hit=False,
            description=f"{attacker.name} cannot attack {target.name}: {range_check['range_info']}",
        )
        db.add(action)
        return action

    # Check for advantage/disadvantage from status effects
    has_advantage = False
    has_disadvantage = False

    # Long range gives disadvantage
    if range_check["at_disadvantage"]:
        has_disadvantage = True

    # Target conditions that give attacker advantage
    if has_status_effect(target, "stunned"):
        has_advantage = True
    if has_status_effect(target, "paralyzed"):
        has_advantage = True
    if has_status_effect(target, "blinded"):
        has_advantage = True

    # Target conditions that give attacker disadvantage
    if has_status_effect(target, "dodging"):
        has_disadvantage = True
    if has_status_effect(target, "invisible"):
        has_disadvantage = True

    # Attacker conditions
    if has_status_effect(attacker, "blinded"):
        has_disadvantage = True
    if has_status_effect(attacker, "poisoned"):
        has_disadvantage = True
    if has_status_effect(attacker, "frightened"):
        has_disadvantage = True
    if has_status_effect(attacker, "invisible"):
        has_advantage = True

    # Roll to hit (d20 + attack mod + weapon hit bonus)
    roll1 = roll_d20()
    roll2 = roll_d20()

    # Advantage and disadvantage cancel out
    if has_advantage and has_disadvantage:
        roll = roll1  # Normal roll
    elif has_advantage:
        roll = max(roll1, roll2)
    elif has_disadvantage:
        roll = min(roll1, roll2)
    else:
        roll = roll1

    total = roll + attack_mod + weapon_hit_bonus

    # Get terrain cover bonus for defender
    cover_bonus = get_terrain_cover_bonus(db, session, target)
    effective_ac = target.armor_class + cover_bonus

    # Paralyzed targets auto-crit on melee hits
    auto_crit = has_status_effect(target, "paralyzed")
    hit = total >= effective_ac or roll == 20
    critical = roll == 20 or (hit and auto_crit)

    damage = 0
    death_info = None
    if hit:
        # Roll damage (weapon dice + attack mod)
        damage = roll_damage(damage_dice) + attack_mod
        if critical:
            damage += roll_damage(damage_dice)  # Double dice on crit
        damage = max(1, damage)  # Minimum 1 damage

        # Check if target is already unconscious
        target_char = db.query(Character).filter(Character.id == target.character_id).first()
        if target_char and target_char.status == CharacterStatus.UNCONSCIOUS:
            # Damage while unconscious = auto death save failure(s)
            is_melee = not range_check["is_ranged"] and distance <= 5
            is_melee_crit = is_melee and critical
            death_info = process_damage_while_unconscious(db, target, damage, is_melee_crit)
        else:
            target.current_hp -= damage
            if target.current_hp <= 0:
                # Drop to unconscious (death saves), not immediate death
                death_info = process_dropping_to_zero_hp(db, target)
            else:
                # Sync HP back to character
                sync_combatant_hp_to_character(db, target)

        # Increase attacker's threat
        attacker.threat += damage // 2

    description = f"{attacker.name} {'critically hits' if critical else 'hits' if hit else 'misses'} {target.name}"
    if hit:
        description += f" for {damage} damage!"
        if death_info:
            if death_info.get("dead"):
                description += f" {target.name} dies!"
            elif death_info.get("unconscious"):
                description += f" {target.name} falls unconscious!"
            elif death_info.get("message"):
                description += f" {death_info['message']}"
    else:
        description += "."

    action = CombatAction(
        session_id=session.id,
        round_number=session.round_number,
        turn_number=session.current_turn,
        actor_combatant_id=attacker.id,
        target_combatant_id=target.id,
        action_type=ActionType.ATTACK,
        roll=roll,
        total=total,
        damage=damage if hit else 0,
        hit=hit,
        critical=critical,
        description=description,
    )
    db.add(action)
    return action


def apply_status_effect(combatant: Combatant, effect_id: str, duration: int | None = None):
    """Apply a status effect to a combatant with duration tracking."""
    effects = load_status_effects()
    effect_data = next((e for e in effects if e["id"] == effect_id), None)

    if not effect_data:
        return

    # Use provided duration or default
    actual_duration = duration if duration is not None else effect_data.get("default_duration", 1)

    # Get current effects as dict
    current_effects = dict(combatant.status_effects) if combatant.status_effects else {}

    # Only apply if not already present (or extend duration if longer)
    if effect_id not in current_effects or current_effects[effect_id] < actual_duration:
        current_effects[effect_id] = actual_duration

        # Apply immediate AC modifier
        if "ac_modifier" in effect_data and effect_id not in combatant.status_effects:
            combatant.armor_class += effect_data["ac_modifier"]

    combatant.status_effects = current_effects


def remove_status_effect(combatant: Combatant, effect_id: str):
    """Remove a status effect from a combatant."""
    effects = load_status_effects()
    effect_data = next((e for e in effects if e["id"] == effect_id), None)

    current_effects = dict(combatant.status_effects) if combatant.status_effects else {}

    if effect_id in current_effects:
        # Remove AC modifier
        if effect_data and "ac_modifier" in effect_data:
            combatant.armor_class -= effect_data["ac_modifier"]

        del current_effects[effect_id]
        combatant.status_effects = current_effects


def process_status_effects_start_of_turn(db: Session, session: CombatSession, combatant: Combatant) -> list[str]:
    """Process status effects at the start of a combatant's turn. Returns list of effect messages."""
    messages = []
    effects = load_status_effects()
    current_effects = dict(combatant.status_effects) if combatant.status_effects else {}

    # Check if combatant is unconscious - process death save instead
    character = db.query(Character).filter(Character.id == combatant.character_id).first()
    if character and character.status == CharacterStatus.UNCONSCIOUS:
        death_result = process_death_saving_throw(db, combatant)
        if death_result.get("message"):
            messages.append(death_result["message"])
        return messages

    for effect_id, duration in list(current_effects.items()):
        effect_data = next((e for e in effects if e["id"] == effect_id), None)
        if not effect_data:
            continue

        # Damage over time
        if "damage_per_turn" in effect_data:
            damage = roll_damage(effect_data["damage_per_turn"])
            combatant.current_hp -= damage
            damage_type = effect_data.get("damage_type", "")

            if combatant.current_hp <= 0:
                # Use death save system instead of immediate death
                death_info = process_dropping_to_zero_hp(db, combatant)
                messages.append(f"{combatant.name} takes {damage} {damage_type} damage from {effect_data['name']}!")
                if death_info.get("message"):
                    messages.append(death_info["message"])
            else:
                sync_combatant_hp_to_character(db, combatant)
                messages.append(f"{combatant.name} takes {damage} {damage_type} damage from {effect_data['name']}!")

        # Heal over time
        if "heal_per_turn" in effect_data:
            healing = roll_damage(effect_data["heal_per_turn"])

            # If unconscious, healing wakes them up
            if character and character.status == CharacterStatus.UNCONSCIOUS:
                heal_result = heal_unconscious_character(db, combatant, healing)
                if heal_result.get("message"):
                    messages.append(heal_result["message"])
            else:
                combatant.current_hp = min(combatant.max_hp, combatant.current_hp + healing)
                sync_combatant_hp_to_character(db, combatant)
                messages.append(f"{combatant.name} heals {healing} HP from {effect_data['name']}.")

        # Skip turn check (handled by caller)

    return messages


def tick_down_status_effects(combatant: Combatant) -> list[str]:
    """Tick down status effect durations at end of turn. Returns expired effect messages."""
    messages = []
    effects = load_status_effects()
    current_effects = dict(combatant.status_effects) if combatant.status_effects else {}
    expired = []

    # Effects that are cleared at start of next turn, not ticked down
    start_of_turn_effects = {"defending", "dodging"}

    for effect_id in list(current_effects.keys()):
        # Skip effects that are handled at start of turn
        if effect_id in start_of_turn_effects:
            continue

        current_effects[effect_id] -= 1
        if current_effects[effect_id] <= 0:
            expired.append(effect_id)

    # Remove expired effects
    for effect_id in expired:
        effect_data = next((e for e in effects if e["id"] == effect_id), None)
        if effect_data:
            # Remove AC modifier
            if "ac_modifier" in effect_data:
                combatant.armor_class -= effect_data["ac_modifier"]
            messages.append(f"{combatant.name}'s {effect_data['name']} effect wears off.")
        del current_effects[effect_id]

    combatant.status_effects = current_effects
    return messages


def has_status_effect(combatant: Combatant, effect_id: str) -> bool:
    """Check if combatant has a specific status effect."""
    effects = combatant.status_effects if combatant.status_effects else {}
    return effect_id in effects


def execute_defend(db: Session, session: CombatSession, combatant: Combatant) -> CombatAction:
    """Execute defend action (+2 AC until next turn)."""
    apply_status_effect(combatant, "defending", duration=1)

    action = CombatAction(
        session_id=session.id,
        round_number=session.round_number,
        turn_number=session.current_turn,
        actor_combatant_id=combatant.id,
        action_type=ActionType.DEFEND,
        description=f"{combatant.name} takes a defensive stance (+2 AC).",
    )
    db.add(action)
    return action


def execute_dodge(db: Session, session: CombatSession, combatant: Combatant) -> CombatAction:
    """Execute dodge action (attacks against have disadvantage until next turn)."""
    apply_status_effect(combatant, "dodging", duration=1)

    action = CombatAction(
        session_id=session.id,
        round_number=session.round_number,
        turn_number=session.current_turn,
        actor_combatant_id=combatant.id,
        action_type=ActionType.DODGE,
        description=f"{combatant.name} focuses on dodging (attackers have disadvantage).",
    )
    db.add(action)
    return action


def execute_flee(db: Session, session: CombatSession, combatant: Combatant) -> CombatAction:
    """Execute flee action (50% chance to escape)."""
    success = random.random() < 0.5

    if success:
        combatant.is_alive = False  # Remove from combat (not dead, just fled)
        combatant.can_act = False
        description = f"{combatant.name} successfully flees from combat!"
    else:
        description = f"{combatant.name} fails to flee!"

    action = CombatAction(
        session_id=session.id,
        round_number=session.round_number,
        turn_number=session.current_turn,
        actor_combatant_id=combatant.id,
        action_type=ActionType.FLEE,
        hit=success,
        description=description,
    )
    db.add(action)
    return action


def execute_spell(db: Session, session: CombatSession, caster: Combatant, target: Combatant | None, spell_name: str) -> CombatAction:
    """Execute a spell action."""
    # Get the character for spell slot tracking
    character = get_character(db, caster.character_id)

    # Find the spell
    spells = load_spells()
    spell = next((s for s in spells if s["name"].lower() == spell_name.lower()), None)
    if not spell:
        raise CombatError(f"Unknown spell: {spell_name}")

    # Check if character can cast this spell (class restriction)
    char_class = character.character_class.value
    if char_class not in spell.get("classes", []):
        raise CombatError(f"{char_class} cannot cast {spell_name}")

    spell_level = spell["level"]
    spell_range = spell.get("range", 0)  # Range in feet (0 = self/touch)

    # Check spell range if targeting another combatant
    if target and target.id != caster.id and spell_range > 0:
        distance = get_combatant_distance(db, caster, target)
        if distance > spell_range:
            raise CombatError(f"Target is {distance} feet away, but {spell_name} has a range of {spell_range} feet")

    # Check and consume spell slot (cantrips don't need slots)
    if spell_level > 0:
        slots = character.spell_slots or {}
        current_slots = slots.get(str(spell_level), 0)
        if current_slots <= 0:
            raise CombatError(f"No spell slots remaining for level {spell_level}")
        slots[str(spell_level)] = current_slots - 1
        character.spell_slots = slots

    # Get caster's spellcasting modifier (INT for mage, WIS for cleric)
    if character.character_class.value == "mage":
        spell_mod = character.get_modifier("intelligence")
    else:
        spell_mod = character.get_modifier("wisdom")

    damage = 0
    healing = 0
    hit = True
    description = ""

    # Handle damage spells
    if "damage_dice" in spell:
        if target is None:
            raise CombatError("Damage spell requires a target")

        # Auto-hit spells (like Magic Missile)
        if spell.get("auto_hit"):
            damage = roll_damage(spell["damage_dice"])
            hit = True
        else:
            # Spell attack roll
            roll = roll_d20()
            total = roll + spell_mod + 2  # +2 proficiency bonus
            hit = total >= target.armor_class or roll == 20

            if hit:
                damage = roll_damage(spell["damage_dice"]) + spell_mod

        death_info = None
        if hit and damage > 0:
            # Check if target is already unconscious
            target_char = db.query(Character).filter(Character.id == target.character_id).first()
            if target_char and target_char.status == CharacterStatus.UNCONSCIOUS:
                # Damage while unconscious = auto death save failure(s)
                death_info = process_damage_while_unconscious(db, target, damage, is_melee_crit=False)
            else:
                target.current_hp -= damage
                if target.current_hp <= 0:
                    # Drop to unconscious (death saves), not immediate death
                    death_info = process_dropping_to_zero_hp(db, target)
                else:
                    sync_combatant_hp_to_character(db, target)
            caster.threat += damage // 2

        description = f"{caster.name} casts {spell['name']} at {target.name}"
        if hit:
            description += f" for {damage} {spell.get('damage_type', '')} damage!"
            if death_info:
                if death_info.get("dead"):
                    description += f" {target.name} dies!"
                elif death_info.get("unconscious"):
                    description += f" {target.name} falls unconscious!"
                elif death_info.get("message"):
                    description += f" {death_info['message']}"
        else:
            description += " but misses."

    # Handle healing spells
    elif "healing_dice" in spell:
        if target is None:
            target = caster  # Self-heal if no target

        healing = roll_damage(spell["healing_dice"]) + spell_mod

        # Check if target is unconscious - healing wakes them up
        target_char = db.query(Character).filter(Character.id == target.character_id).first()
        if target_char and target_char.status == CharacterStatus.UNCONSCIOUS:
            heal_result = heal_unconscious_character(db, target, healing)
            description = f"{caster.name} casts {spell['name']} on {target.name}! {heal_result.get('message', '')}"
        else:
            target.current_hp = min(target.max_hp, target.current_hp + healing)
            sync_combatant_hp_to_character(db, target)
            description = f"{caster.name} casts {spell['name']} on {target.name}, healing {healing} HP!"

    # Handle buff/effect spells
    elif "effect" in spell:
        if target is None:
            target = caster

        effect = spell["effect"]
        duration = spell.get("duration", 10)
        if "ac_bonus" in effect:
            # Apply custom AC bonus as a temporary "blessed" status
            apply_status_effect(target, "blessed", duration=duration)
            description = f"{caster.name} casts {spell['name']} on {target.name}, granting +{effect['ac_bonus']} AC!"
        elif "status" in effect:
            status = effect["status"]
            apply_status_effect(target, status, duration=duration)
            description = f"{caster.name} casts {spell['name']} on {target.name}, inflicting {status}!"
        else:
            description = f"{caster.name} casts {spell['name']}!"
    else:
        description = f"{caster.name} casts {spell['name']}!"

    action = CombatAction(
        session_id=session.id,
        round_number=session.round_number,
        turn_number=session.current_turn,
        actor_combatant_id=caster.id,
        target_combatant_id=target.id if target else None,
        action_type=ActionType.SPELL,
        damage=damage,
        hit=hit,
        description=description,
    )
    db.add(action)
    db.commit()
    return action


def execute_item(db: Session, session: CombatSession, user: Combatant, target: Combatant | None, item_id: int) -> CombatAction:
    """Execute an item use action (consumables)."""
    # Get the inventory item
    inv_item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not inv_item:
        raise CombatError(f"Item {item_id} not found in inventory")

    if inv_item.character_id != user.character_id:
        raise CombatError("Item does not belong to this character")

    item = inv_item.item
    if item.item_type != ItemType.CONSUMABLE:
        raise CombatError(f"{item.name} is not a consumable item")

    # Get the consumable data from reference
    consumables = load_consumables()
    consumable_data = next((c for c in consumables if c["name"].lower() == item.name.lower()), None)

    # If not in reference data, use item properties
    if not consumable_data and item.properties:
        consumable_data = item.properties
        consumable_data["name"] = item.name

    if not consumable_data:
        raise CombatError(f"Unknown consumable: {item.name}")

    damage = 0
    healing = 0
    description = ""
    effect_type = consumable_data.get("effect_type", "")

    # Handle healing consumables
    if effect_type == "heal":
        if target is None:
            target = user  # Self-heal if no target

        healing_dice = consumable_data.get("healing_dice", "1d4")
        healing = roll_damage(healing_dice)

        # Check if target is unconscious - healing wakes them up
        target_char = db.query(Character).filter(Character.id == target.character_id).first()
        if target_char and target_char.status == CharacterStatus.UNCONSCIOUS:
            heal_result = heal_unconscious_character(db, target, healing)
            description = f"{user.name} uses {item.name} on {target.name}! {heal_result.get('message', '')}"
        else:
            target.current_hp = min(target.max_hp, target.current_hp + healing)
            sync_combatant_hp_to_character(db, target)
            description = f"{user.name} uses {item.name} on {target.name}, healing {healing} HP!"

    # Handle damage consumables (throwables like Alchemist's Fire)
    elif effect_type == "damage":
        if target is None:
            raise CombatError("Damage consumables require a target")

        # Check target type restriction (e.g., Holy Water only affects undead)
        target_type = consumable_data.get("target_type")
        if target_type:
            # Could add creature type check here if we had creature types
            pass

        damage_dice = consumable_data.get("damage_dice", "1d4")
        damage_type = consumable_data.get("damage_type", "fire")
        damage = roll_damage(damage_dice)

        death_info = None
        # Check if target is already unconscious
        target_char = db.query(Character).filter(Character.id == target.character_id).first()
        if target_char and target_char.status == CharacterStatus.UNCONSCIOUS:
            # Damage while unconscious = auto death save failure(s)
            death_info = process_damage_while_unconscious(db, target, damage, is_melee_crit=False)
        else:
            target.current_hp -= damage
            if target.current_hp <= 0:
                # Drop to unconscious (death saves), not immediate death
                death_info = process_dropping_to_zero_hp(db, target)
            else:
                sync_combatant_hp_to_character(db, target)

        user.threat += damage // 2
        description = f"{user.name} throws {item.name} at {target.name} for {damage} {damage_type} damage!"
        if death_info:
            if death_info.get("dead"):
                description += f" {target.name} dies!"
            elif death_info.get("unconscious"):
                description += f" {target.name} falls unconscious!"
            elif death_info.get("message"):
                description += f" {death_info['message']}"

    # Handle buff consumables
    elif effect_type == "buff":
        if target is None:
            target = user

        duration = consumable_data.get("duration", 10)

        # Apply stat bonus if present
        stat_bonus = consumable_data.get("stat_bonus")
        if stat_bonus:
            # For now, just note it in the description (would need character stat tracking)
            bonus_str = ", ".join(f"+{v} {k}" for k, v in stat_bonus.items())
            description = f"{user.name} uses {item.name} on {target.name}, gaining {bonus_str}!"

        # Apply status effect
        grants_status = consumable_data.get("grants_status")
        if grants_status:
            apply_status_effect(target, grants_status, duration=duration)
            description = f"{user.name} uses {item.name} on {target.name}, becoming {grants_status}!"

        if not description:
            description = f"{user.name} uses {item.name}!"

    # Handle cure consumables (removes conditions)
    elif effect_type == "cure":
        if target is None:
            target = user

        cures = consumable_data.get("cures", [])
        removed = []
        for condition in cures:
            if has_status_effect(target, condition):
                remove_status_effect(target, condition)
                removed.append(condition)

        if removed:
            description = f"{user.name} uses {item.name} on {target.name}, curing {', '.join(removed)}!"
        else:
            description = f"{user.name} uses {item.name} on {target.name}, but there was nothing to cure."

    else:
        description = f"{user.name} uses {item.name}."

    # Consume the item (reduce quantity or remove)
    if inv_item.quantity > 1:
        inv_item.quantity -= 1
    else:
        db.delete(inv_item)

    action = CombatAction(
        session_id=session.id,
        round_number=session.round_number,
        turn_number=session.current_turn,
        actor_combatant_id=user.id,
        target_combatant_id=target.id if target else None,
        action_type=ActionType.ITEM,
        damage=damage,
        healing=healing,
        hit=True,
        description=description,
    )
    db.add(action)
    db.commit()
    return action


def execute_ability(db: Session, session: CombatSession, user: Combatant, target: Combatant | None, ability_id: str) -> CombatAction:
    """Execute a class ability action."""
    # Get the character for ability tracking
    character = get_character(db, user.character_id)

    # Find the ability
    abilities = load_class_abilities()
    ability = next((a for a in abilities if a["id"] == ability_id), None)
    if not ability:
        raise CombatError(f"Unknown ability: {ability_id}")

    # Check class restriction
    if ability.get("class") != character.character_class.value:
        raise CombatError(f"{character.character_class.value} cannot use {ability['name']}")

    # Check level requirement
    min_level = ability.get("min_level", 1)
    if character.level < min_level:
        raise CombatError(f"{ability['name']} requires level {min_level}")

    # Check ability uses
    if ability.get("max_uses"):
        ability_uses = character.ability_uses or {}
        remaining = ability_uses.get(ability_id, ability["max_uses"])
        if remaining <= 0:
            raise CombatError(f"No uses remaining for {ability['name']}")
        ability_uses[ability_id] = remaining - 1
        character.ability_uses = ability_uses

    damage = 0
    healing = 0
    description = ""
    effect_type = ability.get("effect_type", "")

    # Handle self-healing abilities (Second Wind)
    if effect_type == "heal_self":
        healing_dice = ability.get("healing_dice", "1d10")
        healing = roll_damage(healing_dice)
        if ability.get("adds_level"):
            healing += character.level
        user.current_hp = min(user.max_hp, user.current_hp + healing)
        sync_combatant_hp_to_character(db, user)
        description = f"{user.name} uses {ability['name']}, healing {healing} HP!"

    # Handle bonus damage abilities (Sneak Attack)
    elif effect_type == "bonus_damage":
        if target is None:
            raise CombatError(f"{ability['name']} requires a target")

        damage_dice = ability.get("damage_dice", "1d6")
        # Scale with level (1d6 per 2 levels for sneak attack)
        if ability.get("scales_with_level"):
            num_dice = (character.level + 1) // 2
            damage_dice = f"{num_dice}d6"

        damage = roll_damage(damage_dice)
        death_info = None
        # Check if target is already unconscious
        target_char = db.query(Character).filter(Character.id == target.character_id).first()
        if target_char and target_char.status == CharacterStatus.UNCONSCIOUS:
            # Damage while unconscious = auto death save failure(s)
            death_info = process_damage_while_unconscious(db, target, damage, is_melee_crit=False)
        else:
            target.current_hp -= damage
            if target.current_hp <= 0:
                # Drop to unconscious (death saves), not immediate death
                death_info = process_dropping_to_zero_hp(db, target)
            else:
                sync_combatant_hp_to_character(db, target)
        user.threat += damage // 2
        description = f"{user.name} uses {ability['name']} on {target.name} for {damage} extra damage!"
        if death_info:
            if death_info.get("dead"):
                description += f" {target.name} dies!"
            elif death_info.get("unconscious"):
                description += f" {target.name} falls unconscious!"
            elif death_info.get("message"):
                description += f" {death_info['message']}"

    # Handle ally healing abilities (Channel Divinity: Preserve Life)
    elif effect_type == "heal_allies":
        multiplier = ability.get("healing_multiplier", 5)
        total_healing = multiplier * character.level

        # Heal allies (team members) - include unconscious allies!
        allies = [c for c in session.combatants if c.team_id == user.team_id and (c.is_alive or c.current_hp == 0)]
        # Filter to those who need healing
        allies_needing_healing = []
        for ally in allies:
            ally_char = db.query(Character).filter(Character.id == ally.character_id).first()
            if ally_char and (ally_char.status == CharacterStatus.UNCONSCIOUS or ally.current_hp < ally.max_hp):
                allies_needing_healing.append((ally, ally_char))

        if allies_needing_healing:
            heal_per_ally = total_healing // len(allies_needing_healing)
            healed = []
            for ally, ally_char in allies_needing_healing:
                if ally_char.status == CharacterStatus.UNCONSCIOUS:
                    # Healing wakes them up
                    heal_result = heal_unconscious_character(db, ally, heal_per_ally)
                    healed.append(f"{ally.name} (woke up with {heal_result.get('new_hp', heal_per_ally)} HP)")
                else:
                    ally_healing = min(heal_per_ally, ally.max_hp - ally.current_hp)
                    ally.current_hp += ally_healing
                    sync_combatant_hp_to_character(db, ally)
                    healed.append(f"{ally.name} ({ally_healing})")
            description = f"{user.name} uses {ability['name']}, healing: {', '.join(healed)}!"
        else:
            description = f"{user.name} uses {ability['name']}, but no allies need healing."

    # Handle extra action (Action Surge)
    elif effect_type == "extra_action":
        # Grant an extra action by not advancing turn after this
        # For now, just note it - would need more complex turn handling
        description = f"{user.name} uses {ability['name']} and gains an additional action!"

    # Handle marking abilities (Hunter's Mark)
    elif effect_type == "mark_target":
        if target is None:
            raise CombatError(f"{ability['name']} requires a target")
        duration = ability.get("duration", 10)
        apply_status_effect(target, "marked", duration=duration)
        description = f"{user.name} marks {target.name} with {ability['name']}!"

    # Handle slot recovery (Arcane Recovery)
    elif effect_type == "recover_slots":
        max_recovery = (character.level + 1) // 2
        recovered = []
        slots = dict(character.spell_slots) if character.spell_slots else {}
        max_slots = character.max_spell_slots or {}

        for level in ["1", "2"]:  # Only recover 1st and 2nd level slots
            if level in max_slots:
                can_recover = max_slots[level] - slots.get(level, 0)
                to_recover = min(can_recover, max_recovery)
                if to_recover > 0:
                    slots[level] = slots.get(level, 0) + to_recover
                    max_recovery -= to_recover
                    recovered.append(f"level {level}: {to_recover}")
                if max_recovery <= 0:
                    break

        character.spell_slots = slots
        if recovered:
            description = f"{user.name} uses {ability['name']}, recovering spell slots: {', '.join(recovered)}!"
        else:
            description = f"{user.name} uses {ability['name']}, but has no slots to recover."

    # Handle area effects (Turn Undead)
    elif effect_type == "area_effect":
        status = ability.get("status_applied", "frightened")
        duration = ability.get("duration", 10)
        target_type = ability.get("target_type")

        enemies = [c for c in session.combatants if c.team_id != user.team_id and c.is_alive]
        # For now, apply to all enemies (could add creature type filtering)
        affected = []
        for enemy in enemies:
            apply_status_effect(enemy, status, duration=duration)
            affected.append(enemy.name)

        if affected:
            description = f"{user.name} uses {ability['name']}, affecting: {', '.join(affected)}!"
        else:
            description = f"{user.name} uses {ability['name']}, but no valid targets!"

    else:
        description = f"{user.name} uses {ability['name']}!"

    action = CombatAction(
        session_id=session.id,
        round_number=session.round_number,
        turn_number=session.current_turn,
        actor_combatant_id=user.id,
        target_combatant_id=target.id if target else None,
        action_type=ActionType.ABILITY,
        ability_id=ability.get("id"),
        damage=damage,
        healing=healing,
        hit=True,
        description=description,
    )
    db.add(action)
    db.commit()
    return action


def clear_defending_status(combatant: Combatant):
    """Clear defending status from a combatant at the start of their turn."""
    if combatant and has_status_effect(combatant, "defending"):
        remove_status_effect(combatant, "defending")


def advance_turn(db: Session, session: CombatSession):
    """Advance to the next turn."""
    current = get_current_combatant(session)
    if current:
        current.turn_count += 1
        # Tick down status effect durations at end of turn
        tick_down_status_effects(current)

    # Move to next turn
    alive_combatants = [c for c in session.combatants if c.is_alive and c.can_act]
    session.current_turn += 1

    # Check for new round
    if session.current_turn >= len(alive_combatants):
        session.current_turn = 0
        session.round_number += 1

        # Re-roll initiative if using REROLL initiative type
        if session.initiative_type == InitiativeType.REROLL:
            reroll_initiative_for_round(db, session)


def process_turns(db: Session, session_id: int) -> dict:
    """Process NPC turns until a player needs to act."""
    session = get_combat_session(db, session_id)

    if session.status == CombatStatus.FINISHED:
        raise CombatError("Combat has already ended")

    actions_taken = []

    while True:
        # Check if combat should end
        winner = check_combat_end(session)
        if winner is not None:
            session.status = CombatStatus.FINISHED
            session.winner_team_id = winner
            session.ended_at = datetime.utcnow()
            db.commit()
            return {
                "actions_taken": actions_taken,
                "combatants": session.combatants,
                "status": session.status,
                "round_number": session.round_number,
                "current_turn": session.current_turn,
                "awaiting_player": None,
                "combat_ended": True,
            }

        current = get_current_combatant(session)
        if not current:
            break

        if current.is_player:
            # Clear defending/dodging status at the start of this combatant's turn
            clear_defending_status(current)
            if has_status_effect(current, "dodging"):
                remove_status_effect(current, "dodging")

            # Process status effects (damage over time, etc.)
            effect_messages = process_status_effects_start_of_turn(db, session, current)

            # Check if player died from status effect damage
            if not current.is_alive:
                description = " ".join(effect_messages) if effect_messages else f"{current.name} is incapacitated."
                action = CombatAction(
                    session_id=session.id,
                    round_number=session.round_number,
                    turn_number=session.current_turn,
                    actor_combatant_id=current.id,
                    action_type=ActionType.PASS,
                    description=description,
                )
                db.add(action)
                actions_taken.append(action)
                advance_turn(db, session)
                db.commit()
                continue

            # Check if stunned/paralyzed - auto-skip turn
            if has_status_effect(current, "stunned") or has_status_effect(current, "paralyzed"):
                effect_name = "Stunned" if has_status_effect(current, "stunned") else "Paralyzed"
                description = f"{current.name} is {effect_name.lower()} and cannot act!"
                if effect_messages:
                    description = " ".join(effect_messages) + " " + description
                action = CombatAction(
                    session_id=session.id,
                    round_number=session.round_number,
                    turn_number=session.current_turn,
                    actor_combatant_id=current.id,
                    action_type=ActionType.PASS,
                    description=description,
                )
                db.add(action)
                actions_taken.append(action)
                advance_turn(db, session)
                db.commit()
                continue

            # Pause for player input
            session.status = CombatStatus.AWAITING_PLAYER
            db.commit()
            return {
                "actions_taken": actions_taken,
                "combatants": session.combatants,
                "status": session.status,
                "round_number": session.round_number,
                "current_turn": session.current_turn,
                "awaiting_player": current,
                "combat_ended": False,
                "status_effect_messages": effect_messages,
            }

        # Process NPC turn
        action = process_npc_action(db, session, current)
        actions_taken.append(action)
        advance_turn(db, session)
        db.commit()

    db.commit()
    return {
        "actions_taken": actions_taken,
        "combatants": session.combatants,
        "status": session.status,
        "round_number": session.round_number,
        "current_turn": session.current_turn,
        "awaiting_player": None,
        "combat_ended": False,
    }


def player_action(db: Session, session_id: int, request: PlayerActionRequest) -> dict:
    """Process a player's action."""
    session = get_combat_session(db, session_id)

    if session.status != CombatStatus.AWAITING_PLAYER:
        raise CombatError("Not waiting for player input")

    # Find the player's combatant
    combatant = None
    for c in session.combatants:
        if c.character_id == request.character_id and c.is_player:
            combatant = c
            break

    if not combatant:
        raise CombatError(f"Player character {request.character_id} not found in combat")

    current = get_current_combatant(session)
    if not current or current.id != combatant.id:
        raise CombatError("It's not this player's turn")

    # Status effects already processed in process_turns when we paused for player input

    # Execute the action
    action = None
    if request.action_type == ActionType.ATTACK:
        if not request.target_id:
            raise CombatError("Attack requires a target")
        target = get_combatant(db, request.target_id)
        if target.team_id == combatant.team_id:
            raise CombatError("Cannot attack teammates")
        if not target.is_alive:
            raise CombatError("Target is not alive")
        action = execute_attack(db, session, combatant, target)

    elif request.action_type == ActionType.DEFEND:
        action = execute_defend(db, session, combatant)

    elif request.action_type == ActionType.DODGE:
        action = execute_dodge(db, session, combatant)

    elif request.action_type == ActionType.FLEE:
        action = execute_flee(db, session, combatant)

    elif request.action_type == ActionType.SPELL:
        if not request.spell_name:
            raise CombatError("Spell action requires a spell_name")
        target = None
        if request.target_id:
            target = get_combatant(db, request.target_id)
        action = execute_spell(db, session, combatant, target, request.spell_name)

    elif request.action_type == ActionType.ITEM:
        if not request.item_id:
            raise CombatError("Item action requires an item_id")
        target = None
        if request.target_id:
            target = get_combatant(db, request.target_id)
        action = execute_item(db, session, combatant, target, request.item_id)

    elif request.action_type == ActionType.ABILITY:
        if not request.ability_id:
            raise CombatError("Ability action requires an ability_id")
        target = None
        if request.target_id:
            target = get_combatant(db, request.target_id)
        action = execute_ability(db, session, combatant, target, request.ability_id)

    elif request.action_type == ActionType.PASS:
        action = CombatAction(
            session_id=session.id,
            round_number=session.round_number,
            turn_number=session.current_turn,
            actor_combatant_id=combatant.id,
            action_type=ActionType.PASS,
            description=f"{combatant.name} passes their turn.",
        )
        db.add(action)

    else:
        raise CombatError(f"Action type {request.action_type} not implemented")

    advance_turn(db, session)

    # Check if combat ended after this action
    winner = check_combat_end(session)
    combat_ended = winner is not None
    if combat_ended:
        session.status = CombatStatus.FINISHED
        session.winner_team_id = winner
        session.ended_at = datetime.utcnow()
    else:
        session.status = CombatStatus.IN_PROGRESS

    db.commit()

    return {
        "action": action,
        "combatants": session.combatants,
        "status": session.status,
        "combat_ended": combat_ended,
    }


def roll_loot_from_table(loot_table: dict) -> dict:
    """
    Roll loot from a loot table.
    Returns dict with 'gold' and 'items' (list of {item_name, quantity}).
    """
    result = {"gold": 0, "items": []}

    if not loot_table:
        return result

    # Roll gold
    gold_min, gold_max = loot_table.get("gold_range", [0, 0])
    if gold_max > 0:
        result["gold"] = random.randint(gold_min, gold_max)

    # Add guaranteed drops
    for drop in loot_table.get("guaranteed_drops", []):
        result["items"].append({
            "item_name": drop["item_name"],
            "quantity": drop["quantity"]
        })

    # Roll random items based on drop_count
    drop_count = loot_table.get("drop_count", {"min": 0, "max": 1})
    num_drops = random.randint(drop_count["min"], drop_count["max"])

    items = loot_table.get("items", [])
    if items and num_drops > 0:
        # Calculate total weight for weighted selection
        total_weight = sum(item.get("weight", 1) for item in items)

        for _ in range(num_drops):
            # Weighted random selection
            roll = random.uniform(0, total_weight)
            cumulative = 0
            for item in items:
                cumulative += item.get("weight", 1)
                if roll <= cumulative:
                    # Check if this item is already in result, add quantity
                    existing = next((i for i in result["items"] if i["item_name"] == item["item_name"]), None)
                    if existing:
                        existing["quantity"] += item.get("quantity", 1)
                    else:
                        result["items"].append({
                            "item_name": item["item_name"],
                            "quantity": item.get("quantity", 1)
                        })
                    break

    return result


def roll_loot_for_combatant(combatant: Combatant, monster_id: str | None = None) -> dict:
    """
    Roll loot for a defeated combatant.
    If monster_id is provided, use that monster's loot table.
    Otherwise, return empty loot.
    """
    if not monster_id:
        return {"gold": 0, "items": []}

    loot_table = get_loot_table_for_monster(monster_id)
    return roll_loot_from_table(loot_table)


def resolve_combat(db: Session, session_id: int) -> dict:
    """Calculate rewards and experience for combat."""
    session = get_combat_session(db, session_id)

    if session.status != CombatStatus.FINISHED:
        raise CombatError("Combat is not finished")

    # Calculate experience based on defeated enemies
    experience_earned = {}
    winning_team = session.winner_team_id

    # Sum up HP of defeated enemies
    total_enemy_hp = sum(
        c.max_hp for c in session.combatants
        if c.team_id != winning_team
    )

    # Roll loot from defeated enemies
    total_loot = {"gold": 0, "items": []}
    defeated_enemies = [c for c in session.combatants if c.team_id != winning_team]

    for enemy in defeated_enemies:
        # Get the character to find their monster_id
        enemy_char = db.query(Character).filter(Character.id == enemy.character_id).first()
        if enemy_char and enemy_char.monster_id:
            enemy_loot = roll_loot_for_combatant(enemy, enemy_char.monster_id)
            total_loot["gold"] += enemy_loot["gold"]

            # Merge items
            for loot_item in enemy_loot["items"]:
                existing = next((i for i in total_loot["items"] if i["item_name"] == loot_item["item_name"]), None)
                if existing:
                    existing["quantity"] += loot_item["quantity"]
                else:
                    total_loot["items"].append(loot_item.copy())

    # Distribute exp among winners
    winners = [c for c in session.combatants if c.team_id == winning_team and c.is_alive]
    level_ups = []
    if winners:
        exp_per_winner = max(10, total_enemy_hp // len(winners))
        for winner in winners:
            experience_earned[winner.character_id] = exp_per_winner
            # Actually award the XP to the character
            result = award_experience(db, winner.character_id, exp_per_winner)
            if result["leveled_up"]:
                level_ups.append({
                    "character_id": winner.character_id,
                    "old_level": result["old_level"],
                    "new_level": result["new_level"],
                })

        # Award gold from loot to first winner (could distribute evenly)
        if total_loot["gold"] > 0 and winners:
            first_winner_char = db.query(Character).filter(Character.id == winners[0].character_id).first()
            if first_winner_char:
                first_winner_char.gold += total_loot["gold"]

    session.status = CombatStatus.RESOLVING
    db.commit()

    return {
        "winner_team_id": winning_team,
        "experience_earned": experience_earned,
        "level_ups": level_ups,
        "loot": total_loot,
    }


def finish_combat(db: Session, session_id: int) -> dict:
    """Finalize combat and return summary."""
    session = get_combat_session(db, session_id)

    if session.status not in [CombatStatus.FINISHED, CombatStatus.RESOLVING]:
        raise CombatError("Combat is not ready to be finished")

    # Get resolve data if not already resolved
    resolve_data = resolve_combat(db, session_id) if session.status == CombatStatus.FINISHED else {
        "winner_team_id": session.winner_team_id,
        "experience_earned": {},
        "loot": {"gold": 0, "items": []},
    }

    session.status = CombatStatus.FINISHED
    if not session.ended_at:
        session.ended_at = datetime.utcnow()
    db.commit()

    return {
        "id": session.id,
        "winner_team_id": session.winner_team_id,
        "total_rounds": session.round_number,
        "total_actions": len(session.actions),
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "participants": session.combatants,
        "experience_by_character": resolve_data["experience_earned"],
        "loot": resolve_data.get("loot", {"gold": 0, "items": []}),
    }


def get_combat_history(db: Session, session_id: int) -> list[CombatAction]:
    """Get all actions from a combat session."""
    session = get_combat_session(db, session_id)
    return db.query(CombatAction).filter(
        CombatAction.session_id == session_id
    ).order_by(CombatAction.id).all()
