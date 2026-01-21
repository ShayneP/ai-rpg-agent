from sqlalchemy.orm import Session

from .models import Character, CharacterSkill
from .schemas import (
    CharacterCreate,
    CharacterUpdate,
    AttributesUpdate,
    SkillCreate,
    SkillUpdate,
    HealthUpdate,
    LocationUpdate,
)
from ..core.exceptions import NotFoundError, ValidationError

# XP required to reach each level (cumulative)
XP_THRESHOLDS = {
    1: 0,
    2: 300,
    3: 900,
    4: 2700,
    5: 6500,
    6: 14000,
    7: 23000,
    8: 34000,
    9: 48000,
    10: 64000,
    11: 85000,
    12: 100000,
    13: 120000,
    14: 140000,
    15: 165000,
    16: 195000,
    17: 225000,
    18: 265000,
    19: 305000,
    20: 355000,
}


def get_character(db: Session, character_id: int) -> Character:
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        raise NotFoundError("Character", character_id)
    return character


def get_characters(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    character_type: str | None = None,
    zone_id: int | None = None,
) -> list[Character]:
    query = db.query(Character)
    if character_type:
        query = query.filter(Character.character_type == character_type)
    if zone_id is not None:
        query = query.filter(Character.zone_id == zone_id)
    return query.offset(skip).limit(limit).all()


def create_character(db: Session, character_data: CharacterCreate) -> Character:
    # Base HP calculation
    base_hp = 10

    character = Character(
        name=character_data.name,
        character_class=character_data.character_class,
        character_type=character_data.character_type,
        level=character_data.level,
        strength=character_data.strength,
        dexterity=character_data.dexterity,
        constitution=character_data.constitution,
        intelligence=character_data.intelligence,
        wisdom=character_data.wisdom,
        charisma=character_data.charisma,
        max_hp=base_hp,
        current_hp=base_hp,
        temporary_hp=0,
        armor_class=10,
        gold=character_data.gold,
        experience=0,
        x=0,
        y=0,
        zone_id=1,  # Start in The Stormhaven Tavern
    )
    # Apply class bonuses
    character.apply_class_bonuses()

    db.add(character)
    db.commit()
    db.refresh(character)
    return character


def update_character(db: Session, character_id: int, character_data: CharacterUpdate) -> Character:
    character = get_character(db, character_id)
    update_data = character_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(character, field, value)
    db.commit()
    db.refresh(character)
    return character


def delete_character(db: Session, character_id: int) -> None:
    character = get_character(db, character_id)
    db.delete(character)
    db.commit()


# Attributes
def get_attributes(db: Session, character_id: int) -> Character:
    return get_character(db, character_id)


def update_attributes(db: Session, character_id: int, attrs: AttributesUpdate) -> Character:
    character = get_character(db, character_id)
    update_data = attrs.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(character, field, value)
    db.commit()
    db.refresh(character)
    return character


# Skills
def get_skills(db: Session, character_id: int) -> list[CharacterSkill]:
    character = get_character(db, character_id)
    return character.skills


def add_skill(db: Session, character_id: int, skill_data: SkillCreate) -> CharacterSkill:
    get_character(db, character_id)  # Ensure character exists
    skill = CharacterSkill(
        character_id=character_id,
        name=skill_data.name,
        level=skill_data.level,
        experience=skill_data.experience,
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


def update_skill(db: Session, character_id: int, skill_name: str, skill_data: SkillUpdate) -> CharacterSkill:
    character = get_character(db, character_id)
    skill = next((s for s in character.skills if s.name == skill_name), None)
    if not skill:
        raise NotFoundError("Skill", skill_name)
    update_data = skill_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(skill, field, value)
    db.commit()
    db.refresh(skill)
    return skill


# Health
def get_health(db: Session, character_id: int) -> Character:
    return get_character(db, character_id)


def update_health(db: Session, character_id: int, health_data: HealthUpdate) -> Character:
    character = get_character(db, character_id)
    update_data = health_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(character, field, value)

    # Update status based on HP
    if character.current_hp <= 0:
        character.status = "unconscious"
        if character.current_hp <= -character.max_hp:
            character.status = "dead"

    db.commit()
    db.refresh(character)
    return character


# Location
def get_location(db: Session, character_id: int) -> Character:
    return get_character(db, character_id)


def update_location(db: Session, character_id: int, location_data: LocationUpdate) -> Character:
    character = get_character(db, character_id)
    character.x = location_data.x
    character.y = location_data.y
    if location_data.zone_id is not None:
        character.zone_id = location_data.zone_id
    db.commit()
    db.refresh(character)
    return character


def move_character(db: Session, character_id: int, x: int, y: int, zone_id: int | None = None) -> dict:
    """
    Move a character with terrain effect processing.

    Returns a dict with:
    - character: Updated character
    - terrain_effect: Applied terrain effect (if any)
    - damage_taken: Damage from hazardous terrain
    - movement_cost: Cost to enter this terrain
    - blocked: True if movement was blocked
    """
    from ..location.service import get_grid_cell, get_zone
    from ..reference.router import get_terrain_effect

    character = get_character(db, character_id)
    target_zone_id = zone_id if zone_id is not None else character.zone_id

    result = {
        "character_id": character.id,
        "from_x": character.x,
        "from_y": character.y,
        "from_zone_id": character.zone_id,
        "to_x": x,
        "to_y": y,
        "to_zone_id": target_zone_id,
        "terrain_effect": None,
        "damage_taken": 0,
        "movement_cost": 1,
        "blocked": False,
        "status_effects_applied": [],
    }

    # Check if target zone exists
    if target_zone_id:
        try:
            get_zone(db, target_zone_id)
        except Exception:
            raise ValidationError(f"Zone {target_zone_id} does not exist")

    # Get terrain at destination
    grid_cell = get_grid_cell(db, target_zone_id, x, y) if target_zone_id else None

    if grid_cell:
        terrain_type = grid_cell.terrain_type.value
        terrain_effect = get_terrain_effect(terrain_type)

        if terrain_effect:
            result["terrain_effect"] = terrain_effect

            # Check if terrain is passable
            if not terrain_effect.get("passable", True) or not grid_cell.passable:
                result["blocked"] = True
                result["block_reason"] = f"Terrain is impassable ({terrain_effect['name']})"
                return result

            # Set movement cost
            result["movement_cost"] = terrain_effect.get("movement_cost", 1)

            # Apply hazardous terrain damage
            if terrain_effect.get("hazardous", False):
                damage = terrain_effect.get("damage_on_enter", 0)
                if damage > 0:
                    old_hp = character.current_hp
                    character.current_hp = max(0, character.current_hp - damage)
                    result["damage_taken"] = damage
                    result["damage_type"] = terrain_effect.get("damage_type", "environmental")

                    # Check if character is now unconscious
                    if character.current_hp <= 0:
                        character.status = "unconscious"
                        if character.current_hp <= -character.max_hp:
                            character.status = "dead"

            # Apply terrain status effects (like poisoned from swamp)
            terrain_effects = terrain_effect.get("effects", [])
            if terrain_effects:
                result["status_effects_applied"] = terrain_effects

    # Update character position
    character.x = x
    character.y = y
    if zone_id is not None:
        character.zone_id = zone_id

    db.commit()
    db.refresh(character)

    result["current_hp"] = character.current_hp
    result["status"] = character.status.value if hasattr(character.status, 'value') else character.status

    return result


# Experience and Leveling
def get_level_for_xp(xp: int) -> int:
    """Calculate what level a character should be based on XP."""
    level = 1
    for lvl, threshold in sorted(XP_THRESHOLDS.items()):
        if xp >= threshold:
            level = lvl
        else:
            break
    return min(level, 20)  # Cap at level 20


def get_xp_for_next_level(current_level: int) -> int | None:
    """Get XP required for the next level, or None if at max level."""
    if current_level >= 20:
        return None
    return XP_THRESHOLDS.get(current_level + 1)


def award_experience(db: Session, character_id: int, xp_amount: int) -> dict:
    """Award XP to a character and check for level up."""
    character = get_character(db, character_id)
    old_level = character.level
    old_xp = character.experience

    character.experience += xp_amount
    new_level = get_level_for_xp(character.experience)

    leveled_up = new_level > old_level
    levels_gained = new_level - old_level if leveled_up else 0

    # Auto level-up if XP threshold reached
    if leveled_up:
        character.level = new_level
        # Grant HP per level gained (CON modifier + base)
        con_mod = character.get_modifier("constitution")
        hp_per_level = max(1, 5 + con_mod)  # Base 5 + CON mod, minimum 1
        hp_gained = hp_per_level * levels_gained
        character.max_hp += hp_gained
        character.current_hp += hp_gained

    db.commit()
    db.refresh(character)

    return {
        "character_id": character.id,
        "xp_gained": xp_amount,
        "total_xp": character.experience,
        "old_level": old_level,
        "new_level": character.level,
        "leveled_up": leveled_up,
        "levels_gained": levels_gained,
        "xp_to_next_level": get_xp_for_next_level(character.level),
    }


def level_up(db: Session, character_id: int) -> dict:
    """Manually level up a character if they have enough XP."""
    character = get_character(db, character_id)

    if character.level >= 20:
        raise ValidationError("Character is already at maximum level (20)")

    required_xp = XP_THRESHOLDS.get(character.level + 1, float('inf'))
    if character.experience < required_xp:
        raise ValidationError(
            f"Not enough XP to level up. Have {character.experience}, need {required_xp}"
        )

    old_level = character.level
    character.level += 1

    # Grant HP for the level
    con_mod = character.get_modifier("constitution")
    hp_gained = max(1, 5 + con_mod)
    character.max_hp += hp_gained
    character.current_hp += hp_gained

    db.commit()
    db.refresh(character)

    return {
        "character_id": character.id,
        "old_level": old_level,
        "new_level": character.level,
        "hp_gained": hp_gained,
        "new_max_hp": character.max_hp,
        "xp_to_next_level": get_xp_for_next_level(character.level),
    }


def add_gold(db: Session, character_id: int, amount: int) -> Character:
    """Add gold to a character (can be negative to remove)."""
    character = get_character(db, character_id)
    character.gold = max(0, character.gold + amount)
    db.commit()
    db.refresh(character)
    return character
