from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from . import service
from .schemas import (
    CharacterCreate,
    CharacterUpdate,
    CharacterResponse,
    AttributesUpdate,
    AttributesResponse,
    SkillCreate,
    SkillUpdate,
    SkillResponse,
    HealthUpdate,
    HealthResponse,
    LocationUpdate,
    LocationResponse,
)

router = APIRouter(prefix="/character", tags=["character"])


@router.post("/", response_model=CharacterResponse, status_code=201)
def create_character(character: CharacterCreate, db: Session = Depends(get_db)):
    """Create a new character with class bonuses applied."""
    return service.create_character(db, character)


@router.get("/", response_model=list[CharacterResponse])
def list_characters(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    character_type: str | None = None,
    zone_id: int | None = None,
    db: Session = Depends(get_db),
):
    """List all characters with optional filtering."""
    return service.get_characters(db, skip, limit, character_type, zone_id)


@router.get("/{character_id}", response_model=CharacterResponse)
def get_character(character_id: int, db: Session = Depends(get_db)):
    """Get a specific character by ID."""
    return service.get_character(db, character_id)


@router.put("/{character_id}", response_model=CharacterResponse)
def update_character(character_id: int, character: CharacterUpdate, db: Session = Depends(get_db)):
    """Update a character's basic info."""
    return service.update_character(db, character_id, character)


@router.delete("/{character_id}", status_code=204)
def delete_character(character_id: int, db: Session = Depends(get_db)):
    """Delete a character."""
    service.delete_character(db, character_id)


# Attributes
@router.get("/{character_id}/attributes", response_model=AttributesResponse)
def get_attributes(character_id: int, db: Session = Depends(get_db)):
    """Get a character's attributes."""
    return service.get_attributes(db, character_id)


@router.put("/{character_id}/attributes", response_model=AttributesResponse)
def update_attributes(character_id: int, attrs: AttributesUpdate, db: Session = Depends(get_db)):
    """Update a character's attributes."""
    return service.update_attributes(db, character_id, attrs)


# Skills
@router.get("/{character_id}/skills", response_model=list[SkillResponse])
def get_skills(character_id: int, db: Session = Depends(get_db)):
    """Get all skills for a character."""
    return service.get_skills(db, character_id)


@router.post("/{character_id}/skills", response_model=SkillResponse, status_code=201)
def add_skill(character_id: int, skill: SkillCreate, db: Session = Depends(get_db)):
    """Add a new skill to a character."""
    return service.add_skill(db, character_id, skill)


@router.put("/{character_id}/skills/{skill_name}", response_model=SkillResponse)
def update_skill(character_id: int, skill_name: str, skill: SkillUpdate, db: Session = Depends(get_db)):
    """Update an existing skill."""
    return service.update_skill(db, character_id, skill_name, skill)


# Health
@router.get("/{character_id}/health", response_model=HealthResponse)
def get_health(character_id: int, db: Session = Depends(get_db)):
    """Get a character's health stats."""
    return service.get_health(db, character_id)


@router.put("/{character_id}/health", response_model=HealthResponse)
def update_health(character_id: int, health: HealthUpdate, db: Session = Depends(get_db)):
    """Update a character's health stats."""
    return service.update_health(db, character_id, health)


# Location
@router.get("/{character_id}/location", response_model=LocationResponse)
def get_location(character_id: int, db: Session = Depends(get_db)):
    """Get a character's current location."""
    return service.get_location(db, character_id)


@router.put("/{character_id}/location", response_model=LocationResponse)
def update_location(character_id: int, location: LocationUpdate, db: Session = Depends(get_db)):
    """Update a character's location (direct, no terrain effects)."""
    return service.update_location(db, character_id, location)


@router.post("/{character_id}/move")
def move_character(
    character_id: int,
    x: int = Query(..., description="Target X coordinate"),
    y: int = Query(..., description="Target Y coordinate"),
    zone_id: int | None = Query(None, description="Target zone ID (optional, defaults to current zone)"),
    db: Session = Depends(get_db),
):
    """
    Move a character with terrain effect processing.

    This endpoint applies terrain effects including:
    - Movement cost (difficult terrain costs more movement)
    - Hazardous terrain damage (lava, etc.)
    - Impassable terrain blocking
    - Terrain-applied status effects

    Returns movement result including damage taken and terrain info.
    """
    return service.move_character(db, character_id, x, y, zone_id)


# Experience and Leveling
@router.post("/{character_id}/experience")
def award_experience(character_id: int, amount: int = Query(..., ge=1), db: Session = Depends(get_db)):
    """Award experience points to a character. Auto levels up if threshold reached."""
    return service.award_experience(db, character_id, amount)


@router.post("/{character_id}/level-up")
def level_up(character_id: int, db: Session = Depends(get_db)):
    """Manually level up a character if they have enough XP."""
    return service.level_up(db, character_id)


@router.get("/{character_id}/xp-status")
def get_xp_status(character_id: int, db: Session = Depends(get_db)):
    """Get character's current XP status and progress to next level."""
    character = service.get_character(db, character_id)
    xp_to_next = service.get_xp_for_next_level(character.level)
    current_level_xp = service.XP_THRESHOLDS.get(character.level, 0)

    progress = None
    if xp_to_next:
        xp_into_level = character.experience - current_level_xp
        xp_needed = xp_to_next - current_level_xp
        progress = round(xp_into_level / xp_needed * 100, 1) if xp_needed > 0 else 100

    return {
        "character_id": character.id,
        "level": character.level,
        "experience": character.experience,
        "xp_for_current_level": current_level_xp,
        "xp_for_next_level": xp_to_next,
        "progress_percent": progress,
        "at_max_level": character.level >= 20,
    }


# Gold
@router.post("/{character_id}/gold")
def modify_gold(character_id: int, amount: int = Query(...), db: Session = Depends(get_db)):
    """Add or remove gold from a character. Use negative amount to remove."""
    character = service.add_gold(db, character_id, amount)
    return {"character_id": character.id, "gold": character.gold, "amount_changed": amount}


# Rest and Recovery
@router.post("/{character_id}/rest")
def rest(
    character_id: int,
    rest_type: str = Query("long", description="Type of rest: 'short' or 'long'"),
    db: Session = Depends(get_db),
):
    """
    Rest to recover HP, spell slots, and ability uses.

    - Short rest: Recover up to half max HP, reset short-rest abilities
    - Long rest: Recover all HP, all spell slots, and all abilities
    """
    from ..reference.router import load_class_abilities

    character = service.get_character(db, character_id)
    result = {"character_id": character.id, "rest_type": rest_type}
    abilities_reset = []

    # Load class abilities for reset
    all_abilities = load_class_abilities()
    class_abilities = [a for a in all_abilities if a.get("class") == character.character_class.value]

    if rest_type == "long":
        # Full HP recovery
        hp_recovered = character.max_hp - character.current_hp
        character.current_hp = character.max_hp

        # Full spell slot recovery
        if character.max_spell_slots:
            character.spell_slots = dict(character.max_spell_slots)

        # Reset ALL ability uses (both short and long rest abilities)
        ability_uses = {}
        for ability in class_abilities:
            if ability.get("max_uses"):
                ability_uses[ability["id"]] = ability["max_uses"]
                abilities_reset.append(ability["name"])
        character.ability_uses = ability_uses

        result["hp_recovered"] = hp_recovered
        result["spell_slots_recovered"] = True
        result["abilities_reset"] = abilities_reset
        result["current_hp"] = character.current_hp

    elif rest_type == "short":
        # Recover half of max HP
        hp_to_recover = character.max_hp // 2
        old_hp = character.current_hp
        character.current_hp = min(character.max_hp, character.current_hp + hp_to_recover)
        hp_recovered = character.current_hp - old_hp

        # Reset SHORT rest ability uses only
        ability_uses = dict(character.ability_uses) if character.ability_uses else {}
        for ability in class_abilities:
            if ability.get("uses_per_rest") == "short" and ability.get("max_uses"):
                ability_uses[ability["id"]] = ability["max_uses"]
                abilities_reset.append(ability["name"])
        character.ability_uses = ability_uses

        result["hp_recovered"] = hp_recovered
        result["abilities_reset"] = abilities_reset
        result["current_hp"] = character.current_hp
    else:
        from ..core.exceptions import ValidationError
        raise ValidationError(f"Invalid rest type: {rest_type}. Use 'short' or 'long'.")

    db.commit()
    db.refresh(character)
    return result


# Spell Slots
@router.get("/{character_id}/spell-slots")
def get_spell_slots(character_id: int, db: Session = Depends(get_db)):
    """Get character's current and max spell slots."""
    character = service.get_character(db, character_id)
    return {
        "character_id": character.id,
        "character_class": character.character_class.value,
        "spell_slots": character.spell_slots or {},
        "max_spell_slots": character.max_spell_slots or {},
    }


# Create from Monster Template
@router.post("/from-monster/{monster_id}", response_model=CharacterResponse, status_code=201)
def create_from_monster(
    monster_id: str,
    name: str | None = Query(None, description="Custom name for the monster (defaults to monster's base name)"),
    zone_id: int | None = Query(None, description="Zone ID where the monster should be placed"),
    db: Session = Depends(get_db),
):
    """
    Create a new NPC character from a monster template.

    The monster's stats, HP, and AC are applied to the character.
    Monster types are mapped to appropriate character classes for ability purposes.
    """
    from ..reference.router import get_monster
    from ..core.exceptions import NotFoundError

    monster = get_monster(monster_id)
    if not monster:
        raise NotFoundError("Monster", monster_id)

    # Map monster type to a character class (for ability purposes)
    type_to_class = {
        "humanoid": "warrior",
        "undead": "warrior",
        "beast": "ranger",
        "giant": "warrior",
        "monstrosity": "warrior",
        "fiend": "mage",
        "dragon": "mage",
    }
    char_class = type_to_class.get(monster["type"], "warrior")

    # Create the character
    char_data = CharacterCreate(
        name=name or monster["name"],
        character_class=char_class,
        character_type="npc",
    )

    character = service.create_character(db, char_data)

    # Override with monster stats
    character.strength = monster["strength"]
    character.dexterity = monster["dexterity"]
    character.constitution = monster["constitution"]
    character.intelligence = monster["intelligence"]
    character.wisdom = monster["wisdom"]
    character.charisma = monster["charisma"]
    character.max_hp = monster["base_hp"]
    character.current_hp = monster["base_hp"]
    character.armor_class = monster["armor_class"]
    character.monster_id = monster_id  # Store for loot table lookup

    # Set zone if provided (important for combat distance calculations)
    if zone_id is not None:
        character.zone_id = zone_id

    db.commit()
    db.refresh(character)

    return character
