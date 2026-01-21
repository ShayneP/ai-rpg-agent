import json
from pathlib import Path
from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/reference", tags=["reference"])

# Load data from JSON files
DATA_DIR = Path(__file__).parent.parent.parent / "data"


def load_weapons():
    weapons_file = DATA_DIR / "weapons.json"
    if weapons_file.exists():
        with open(weapons_file) as f:
            return json.load(f)["weapons"]
    return []


def load_armor():
    armor_file = DATA_DIR / "armor.json"
    if armor_file.exists():
        with open(armor_file) as f:
            return json.load(f)["armor"]
    return []


def load_spells():
    spells_file = DATA_DIR / "spells.json"
    if spells_file.exists():
        with open(spells_file) as f:
            return json.load(f)["spells"]
    return []


def load_consumables():
    consumables_file = DATA_DIR / "consumables.json"
    if consumables_file.exists():
        with open(consumables_file) as f:
            return json.load(f)["consumables"]
    return []


def load_status_effects():
    effects_file = DATA_DIR / "status_effects.json"
    if effects_file.exists():
        with open(effects_file) as f:
            return json.load(f)["status_effects"]
    return []


def load_class_abilities():
    abilities_file = DATA_DIR / "class_abilities.json"
    if abilities_file.exists():
        with open(abilities_file) as f:
            return json.load(f)["class_abilities"]
    return []


def load_terrain_effects():
    terrain_file = DATA_DIR / "terrain_effects.json"
    if terrain_file.exists():
        with open(terrain_file) as f:
            return json.load(f)["terrain_effects"]
    return []


def load_monsters():
    monsters_file = DATA_DIR / "monsters.json"
    if monsters_file.exists():
        with open(monsters_file) as f:
            return json.load(f)["monsters"]
    return []


def get_monster(monster_id: str) -> dict | None:
    """Get monster data for a specific monster ID."""
    monsters = load_monsters()
    for monster in monsters:
        if monster["id"] == monster_id:
            return monster
    return None


def get_terrain_effect(terrain_type: str) -> dict | None:
    """Get terrain effect data for a specific terrain type."""
    effects = load_terrain_effects()
    for effect in effects:
        if effect["terrain_type"] == terrain_type:
            return effect
    return None


class WeaponResponse(BaseModel):
    name: str
    category: str
    cost_gp: float
    cost_display: str
    damage_dice: str | None
    damage_type: str | None
    weight: float
    properties: list[str]
    range: str | None = None
    versatile_dice: str | None = None


class ArmorResponse(BaseModel):
    name: str
    category: str
    cost_gp: float
    cost_display: str
    base_ac: int
    max_dex_bonus: int | None
    weight: float
    stealth_disadvantage: bool


@router.get("/weapons", response_model=list[WeaponResponse])
def list_weapons(
    category: str | None = Query(None, description="Filter by category (simple_melee, simple_ranged, martial_melee, martial_ranged)"),
    max_cost_gp: float | None = Query(None, description="Maximum cost in gold pieces"),
    min_cost_gp: float | None = Query(None, description="Minimum cost in gold pieces"),
    damage_type: str | None = Query(None, description="Filter by damage type (bludgeoning, piercing, slashing)"),
    property: str | None = Query(None, description="Filter by property (finesse, thrown, two-handed, versatile, reach, ammunition)"),
    search: str | None = Query(None, description="Search weapon names"),
):
    """
    List all base weapons with optional filtering.

    Categories: simple_melee, simple_ranged, martial_melee, martial_ranged
    Damage types: bludgeoning, piercing, slashing
    Properties: finesse, thrown, two-handed, versatile, reach, ammunition, special
    """
    weapons = load_weapons()

    # Apply filters
    if category:
        weapons = [w for w in weapons if w["category"] == category]

    if max_cost_gp is not None:
        weapons = [w for w in weapons if w["cost_gp"] <= max_cost_gp]

    if min_cost_gp is not None:
        weapons = [w for w in weapons if w["cost_gp"] >= min_cost_gp]

    if damage_type:
        weapons = [w for w in weapons if w.get("damage_type") == damage_type]

    if property:
        weapons = [w for w in weapons if property in w.get("properties", [])]

    if search:
        search_lower = search.lower()
        weapons = [w for w in weapons if search_lower in w["name"].lower()]

    return weapons


@router.get("/weapons/{weapon_name}", response_model=WeaponResponse)
def get_weapon(weapon_name: str):
    """Get a specific weapon by name."""
    weapons = load_weapons()

    # Case-insensitive search
    weapon_lower = weapon_name.lower()
    for w in weapons:
        if w["name"].lower() == weapon_lower:
            return w

    from ..core.exceptions import NotFoundError
    raise NotFoundError("Weapon", weapon_name)


@router.get("/weapons/categories/list")
def list_weapon_categories():
    """List all weapon categories."""
    return {
        "categories": [
            {"id": "simple_melee", "name": "Simple Melee Weapons"},
            {"id": "simple_ranged", "name": "Simple Ranged Weapons"},
            {"id": "martial_melee", "name": "Martial Melee Weapons"},
            {"id": "martial_ranged", "name": "Martial Ranged Weapons"},
        ]
    }


@router.get("/weapons/properties/list")
def list_weapon_properties():
    """List all weapon properties with descriptions."""
    return {
        "properties": [
            {"id": "ammunition", "name": "Ammunition", "description": "Requires ammunition to use; range specified"},
            {"id": "finesse", "name": "Finesse", "description": "Can use DEX instead of STR for attack and damage"},
            {"id": "reach", "name": "Reach", "description": "Adds 5 feet to melee attack range"},
            {"id": "thrown", "name": "Thrown", "description": "Can be thrown for ranged attack using STR"},
            {"id": "two-handed", "name": "Two-Handed", "description": "Requires two hands to use"},
            {"id": "versatile", "name": "Versatile", "description": "Can be used one or two-handed for different damage"},
            {"id": "special", "name": "Special", "description": "Has special rules (see weapon description)"},
        ]
    }


# ==================== Armor Endpoints ====================


@router.get("/armor", response_model=list[ArmorResponse])
def list_armor(
    category: str | None = Query(None, description="Filter by category (light, medium, heavy, shield)"),
    max_cost_gp: float | None = Query(None, description="Maximum cost in gold pieces"),
    min_cost_gp: float | None = Query(None, description="Minimum cost in gold pieces"),
    min_ac: int | None = Query(None, description="Minimum base AC"),
    stealth_ok: bool | None = Query(None, description="Filter to armor without stealth disadvantage"),
    search: str | None = Query(None, description="Search armor names"),
):
    """
    List all base armor with optional filtering.

    Categories: light, medium, heavy, shield

    AC Calculation:
    - Light armor: base_ac + DEX modifier (no limit)
    - Medium armor: base_ac + DEX modifier (max 2)
    - Heavy armor: base_ac (no DEX bonus)
    - Shield: +2 bonus to AC (stacks with armor)
    """
    armor = load_armor()

    if category:
        armor = [a for a in armor if a["category"] == category]

    if max_cost_gp is not None:
        armor = [a for a in armor if a["cost_gp"] <= max_cost_gp]

    if min_cost_gp is not None:
        armor = [a for a in armor if a["cost_gp"] >= min_cost_gp]

    if min_ac is not None:
        armor = [a for a in armor if a["base_ac"] >= min_ac]

    if stealth_ok is True:
        armor = [a for a in armor if not a["stealth_disadvantage"]]

    if search:
        search_lower = search.lower()
        armor = [a for a in armor if search_lower in a["name"].lower()]

    return armor


@router.get("/armor/{armor_name}", response_model=ArmorResponse)
def get_armor(armor_name: str):
    """Get a specific armor by name."""
    armor = load_armor()

    armor_lower = armor_name.lower()
    for a in armor:
        if a["name"].lower() == armor_lower:
            return a

    from ..core.exceptions import NotFoundError
    raise NotFoundError("Armor", armor_name)


@router.get("/armor/categories/list")
def list_armor_categories():
    """List all armor categories with AC calculation rules."""
    return {
        "categories": [
            {
                "id": "light",
                "name": "Light Armor",
                "ac_calculation": "base_ac + DEX modifier",
                "description": "Flexible armor that doesn't impede movement"
            },
            {
                "id": "medium",
                "name": "Medium Armor",
                "ac_calculation": "base_ac + DEX modifier (max 2)",
                "description": "Balanced protection with some mobility"
            },
            {
                "id": "heavy",
                "name": "Heavy Armor",
                "ac_calculation": "base_ac (no DEX bonus)",
                "description": "Maximum protection but restricts movement"
            },
            {
                "id": "shield",
                "name": "Shield",
                "ac_calculation": "+2 AC bonus",
                "description": "Held in one hand, stacks with armor"
            },
        ]
    }


# ==================== Spell Endpoints ====================


class SpellResponse(BaseModel):
    name: str
    level: int
    school: str
    casting_time: str
    range: int
    description: str
    classes: list[str]
    damage_dice: str | None = None
    damage_type: str | None = None
    healing_dice: str | None = None
    auto_hit: bool = False
    area_effect: bool = False
    save: str | None = None
    duration: int | None = None
    effect: dict | None = None
    num_targets: int | None = None
    num_attacks: int | None = None


@router.get("/spells", response_model=list[SpellResponse])
def list_spells(
    level: int | None = Query(None, ge=0, le=9, description="Filter by spell level (0 = cantrip)"),
    character_class: str | None = Query(None, description="Filter by class (mage, cleric, ranger)"),
    school: str | None = Query(None, description="Filter by school (evocation, abjuration, etc.)"),
    damage_type: str | None = Query(None, description="Filter by damage type"),
    healing: bool | None = Query(None, description="Filter to healing spells only"),
    search: str | None = Query(None, description="Search spell names"),
):
    """
    List all spells with optional filtering.

    Spell levels: 0 (cantrip), 1-9
    Classes: mage, cleric, ranger
    Schools: evocation, abjuration, enchantment, necromancy
    """
    spells = load_spells()

    if level is not None:
        spells = [s for s in spells if s["level"] == level]

    if character_class:
        spells = [s for s in spells if character_class in s.get("classes", [])]

    if school:
        spells = [s for s in spells if s.get("school") == school]

    if damage_type:
        spells = [s for s in spells if s.get("damage_type") == damage_type]

    if healing is True:
        spells = [s for s in spells if "healing_dice" in s]

    if search:
        search_lower = search.lower()
        spells = [s for s in spells if search_lower in s["name"].lower()]

    return spells


@router.get("/spells/{spell_name}", response_model=SpellResponse)
def get_spell(spell_name: str):
    """Get a specific spell by name."""
    spells = load_spells()

    spell_lower = spell_name.lower().replace("-", " ").replace("_", " ")
    for s in spells:
        if s["name"].lower() == spell_lower:
            return s

    from ..core.exceptions import NotFoundError
    raise NotFoundError("Spell", spell_name)


@router.get("/spells/class/{character_class}")
def get_spells_for_class(character_class: str):
    """Get all spells available to a specific class."""
    spells = load_spells()
    class_spells = [s for s in spells if character_class in s.get("classes", [])]

    # Group by level
    by_level = {}
    for spell in class_spells:
        level = spell["level"]
        if level not in by_level:
            by_level[level] = []
        by_level[level].append(spell)

    return {
        "class": character_class,
        "spells_by_level": {k: by_level[k] for k in sorted(by_level.keys())},
        "total_spells": len(class_spells),
    }


# ==================== Consumable Endpoints ====================


class ConsumableResponse(BaseModel):
    name: str
    rarity: str
    cost_gp: float
    weight: float
    effect_type: str
    description: str
    healing_dice: str | None = None
    damage_dice: str | None = None
    damage_type: str | None = None
    target_type: str | None = None
    cures: list[str] | None = None
    stat_bonus: dict | None = None
    grants_status: str | None = None
    duration: int | None = None


@router.get("/consumables", response_model=list[ConsumableResponse])
def list_consumables(
    effect_type: str | None = Query(None, description="Filter by effect type (heal, damage, buff, cure)"),
    rarity: str | None = Query(None, description="Filter by rarity (common, uncommon, rare, epic)"),
    max_cost_gp: float | None = Query(None, description="Maximum cost in gold pieces"),
    search: str | None = Query(None, description="Search consumable names"),
):
    """
    List all consumables with optional filtering.

    Effect types: heal, damage, buff, cure
    """
    consumables = load_consumables()

    if effect_type:
        consumables = [c for c in consumables if c.get("effect_type") == effect_type]

    if rarity:
        consumables = [c for c in consumables if c.get("rarity") == rarity]

    if max_cost_gp is not None:
        consumables = [c for c in consumables if c["cost_gp"] <= max_cost_gp]

    if search:
        search_lower = search.lower()
        consumables = [c for c in consumables if search_lower in c["name"].lower()]

    return consumables


@router.get("/consumables/{consumable_name}", response_model=ConsumableResponse)
def get_consumable(consumable_name: str):
    """Get a specific consumable by name."""
    consumables = load_consumables()

    consumable_lower = consumable_name.lower().replace("-", " ").replace("_", " ")
    for c in consumables:
        if c["name"].lower() == consumable_lower:
            return c

    from ..core.exceptions import NotFoundError
    raise NotFoundError("Consumable", consumable_name)


# ==================== Status Effect Endpoints ====================


class StatusEffectResponse(BaseModel):
    id: str
    name: str
    description: str
    default_duration: int
    damage_per_turn: str | None = None
    damage_type: str | None = None
    heal_per_turn: str | None = None
    skip_turn: bool = False
    ac_modifier: int | None = None
    attack_disadvantage: bool = False
    attack_advantage: bool = False
    attackers_disadvantage: bool = False
    attackers_advantage: bool = False
    auto_crit_melee: bool = False
    extra_action: bool = False
    attack_bonus_dice: str | None = None
    attack_penalty_dice: str | None = None


@router.get("/status-effects", response_model=list[StatusEffectResponse])
def list_status_effects(
    harmful: bool | None = Query(None, description="Filter to harmful effects only"),
    beneficial: bool | None = Query(None, description="Filter to beneficial effects only"),
    search: str | None = Query(None, description="Search effect names"),
):
    """
    List all status effects with optional filtering.

    Harmful effects: poison, burning, stunned, paralyzed, blinded, frightened, slowed, cursed
    Beneficial effects: hasted, invisible, blessed, regenerating, defending, dodging
    """
    effects = load_status_effects()

    # Define harmful vs beneficial
    harmful_ids = {"poisoned", "burning", "stunned", "paralyzed", "blinded", "frightened", "slowed", "cursed", "charmed"}
    beneficial_ids = {"hasted", "invisible", "blessed", "regenerating", "defending", "dodging"}

    if harmful is True:
        effects = [e for e in effects if e["id"] in harmful_ids]

    if beneficial is True:
        effects = [e for e in effects if e["id"] in beneficial_ids]

    if search:
        search_lower = search.lower()
        effects = [e for e in effects if search_lower in e["name"].lower() or search_lower in e.get("description", "").lower()]

    return effects


@router.get("/status-effects/{effect_id}", response_model=StatusEffectResponse)
def get_status_effect(effect_id: str):
    """Get a specific status effect by ID."""
    effects = load_status_effects()

    effect_lower = effect_id.lower().replace("-", "_")
    for e in effects:
        if e["id"].lower() == effect_lower:
            return e

    from ..core.exceptions import NotFoundError
    raise NotFoundError("StatusEffect", effect_id)


# ==================== Class Ability Endpoints ====================


class ClassAbilityResponse(BaseModel):
    id: str
    name: str
    class_: str = None  # Renamed from 'class' to avoid Python keyword
    description: str
    effect_type: str
    healing_dice: str | None = None
    damage_dice: str | None = None
    bonus_damage_dice: str | None = None
    adds_level: bool = False
    scales_with_level: bool = False
    uses_per_rest: str | None = None
    uses_per_turn: int | None = None
    max_uses: int | None = None
    min_level: int = 1
    duration: int | None = None
    options: list[str] | None = None
    healing_multiplier: int | None = None
    bonus_damage: int | None = None

    class Config:
        populate_by_name = True

    def __init__(self, **data):
        # Handle 'class' -> 'class_' mapping
        if 'class' in data:
            data['class_'] = data.pop('class')
        super().__init__(**data)


@router.get("/abilities", response_model=list[ClassAbilityResponse])
def list_class_abilities(
    character_class: str | None = Query(None, description="Filter by class (warrior, mage, rogue, cleric, ranger)"),
    effect_type: str | None = Query(None, description="Filter by effect type"),
    min_level: int | None = Query(None, description="Show abilities available at this level"),
    search: str | None = Query(None, description="Search ability names"),
):
    """
    List all class abilities with optional filtering.

    Classes: warrior, mage, rogue, cleric, ranger
    Effect types: heal_self, extra_action, bonus_damage, bonus_action, passive, heal_allies, etc.
    """
    abilities = load_class_abilities()

    if character_class:
        abilities = [a for a in abilities if a.get("class") == character_class]

    if effect_type:
        abilities = [a for a in abilities if a.get("effect_type") == effect_type]

    if min_level is not None:
        abilities = [a for a in abilities if a.get("min_level", 1) <= min_level]

    if search:
        search_lower = search.lower()
        abilities = [a for a in abilities if search_lower in a["name"].lower() or search_lower in a.get("description", "").lower()]

    return abilities


@router.get("/abilities/{ability_id}", response_model=ClassAbilityResponse)
def get_class_ability(ability_id: str):
    """Get a specific class ability by ID."""
    abilities = load_class_abilities()

    ability_lower = ability_id.lower().replace("-", "_")
    for a in abilities:
        if a["id"].lower() == ability_lower:
            return a

    from ..core.exceptions import NotFoundError
    raise NotFoundError("ClassAbility", ability_id)


@router.get("/abilities/class/{character_class}")
def get_abilities_for_class(character_class: str, level: int = Query(20, ge=1, le=20)):
    """Get all abilities available to a specific class at a given level."""
    abilities = load_class_abilities()
    class_abilities = [
        a for a in abilities
        if a.get("class") == character_class and a.get("min_level", 1) <= level
    ]

    return {
        "class": character_class,
        "level": level,
        "abilities": class_abilities,
        "total_abilities": len(class_abilities),
    }


# ==================== Terrain Effect Endpoints ====================


class TerrainEffectResponse(BaseModel):
    terrain_type: str
    name: str
    description: str
    movement_cost: int
    passable: bool
    hazardous: bool
    damage_on_enter: int
    damage_per_turn: int
    damage_type: str | None
    cover_bonus: int
    effects: list[str]


@router.get("/terrain", response_model=list[TerrainEffectResponse])
def list_terrain_effects(
    passable: bool | None = Query(None, description="Filter by passability"),
    hazardous: bool | None = Query(None, description="Filter by hazardous terrain"),
    provides_cover: bool | None = Query(None, description="Filter to terrain that provides cover"),
    difficult: bool | None = Query(None, description="Filter to difficult terrain (movement cost > 1)"),
):
    """
    List all terrain types and their effects.

    Terrain properties:
    - movement_cost: How many movement points to enter (0 = impassable)
    - hazardous: Deals damage on enter/stay
    - cover_bonus: AC bonus when in this terrain
    - effects: Status effects that may be applied
    """
    terrain = load_terrain_effects()

    if passable is not None:
        terrain = [t for t in terrain if t["passable"] == passable]

    if hazardous is not None:
        terrain = [t for t in terrain if t["hazardous"] == hazardous]

    if provides_cover is True:
        terrain = [t for t in terrain if t["cover_bonus"] > 0]

    if difficult is True:
        terrain = [t for t in terrain if t["movement_cost"] > 1]

    return terrain


@router.get("/terrain/{terrain_type}", response_model=TerrainEffectResponse)
def get_terrain_effects(terrain_type: str):
    """Get effects for a specific terrain type."""
    effect = get_terrain_effect(terrain_type)
    if not effect:
        from ..core.exceptions import NotFoundError
        raise NotFoundError("TerrainEffect", terrain_type)
    return effect


# ==================== Monster Endpoints ====================


class MonsterAttack(BaseModel):
    name: str
    damage_dice: str
    damage_type: str
    hit_bonus: int
    range: str | None = None
    extra_damage: str | None = None


class MonsterResponse(BaseModel):
    id: str
    name: str
    size: str
    type: str
    challenge_rating: float
    experience_reward: int
    hit_dice: str
    base_hp: int
    armor_class: int
    speed: int
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int
    attacks: list[MonsterAttack]
    special_abilities: list[str] = []
    vulnerabilities: list[str] = []
    resistances: list[str] = []
    immunities: list[str] = []
    condition_immunities: list[str] = []
    description: str


@router.get("/monsters", response_model=list[MonsterResponse])
def list_monsters(
    monster_type: str | None = Query(None, description="Filter by type (humanoid, undead, beast, dragon, etc.)"),
    size: str | None = Query(None, description="Filter by size (tiny, small, medium, large, huge)"),
    min_cr: float | None = Query(None, description="Minimum challenge rating"),
    max_cr: float | None = Query(None, description="Maximum challenge rating"),
    search: str | None = Query(None, description="Search monster names"),
):
    """
    List all monsters with optional filtering.

    Types: humanoid, undead, beast, giant, monstrosity, fiend, dragon
    Sizes: tiny, small, medium, large, huge
    Challenge ratings: 0.125, 0.25, 0.5, 1, 2, 3, 5, 7, 14, etc.
    """
    monsters = load_monsters()

    if monster_type:
        monsters = [m for m in monsters if m["type"] == monster_type]

    if size:
        monsters = [m for m in monsters if m["size"] == size]

    if min_cr is not None:
        monsters = [m for m in monsters if m["challenge_rating"] >= min_cr]

    if max_cr is not None:
        monsters = [m for m in monsters if m["challenge_rating"] <= max_cr]

    if search:
        search_lower = search.lower()
        monsters = [m for m in monsters if search_lower in m["name"].lower()]

    return monsters


@router.get("/monsters/{monster_id}", response_model=MonsterResponse)
def get_monster_by_id(monster_id: str):
    """Get a specific monster by ID."""
    monster = get_monster(monster_id)
    if not monster:
        from ..core.exceptions import NotFoundError
        raise NotFoundError("Monster", monster_id)
    return monster


@router.get("/monsters/types/list")
def list_monster_types():
    """List all monster types."""
    return {
        "types": [
            {"id": "humanoid", "name": "Humanoid", "description": "Two-legged beings with human-like intelligence"},
            {"id": "undead", "name": "Undead", "description": "Once-living creatures animated by dark magic"},
            {"id": "beast", "name": "Beast", "description": "Natural animals and their giant variants"},
            {"id": "giant", "name": "Giant", "description": "Huge humanoid creatures of great strength"},
            {"id": "monstrosity", "name": "Monstrosity", "description": "Unnatural creatures born of magic or curses"},
            {"id": "fiend", "name": "Fiend", "description": "Evil creatures from the lower planes"},
            {"id": "dragon", "name": "Dragon", "description": "Ancient reptilian creatures of immense power"},
        ]
    }


@router.get("/monsters/by-cr/{challenge_rating}")
def get_monsters_by_cr(challenge_rating: float):
    """Get all monsters of a specific challenge rating."""
    monsters = load_monsters()
    matching = [m for m in monsters if m["challenge_rating"] == challenge_rating]

    return {
        "challenge_rating": challenge_rating,
        "monsters": matching,
        "count": len(matching),
    }


# =============================================================================
# Loot Tables
# =============================================================================

def load_loot_tables():
    loot_file = DATA_DIR / "loot_tables.json"
    if loot_file.exists():
        with open(loot_file) as f:
            return json.load(f)
    return []


# Monster ID to loot table ID mapping
MONSTER_LOOT_MAPPING = {
    "goblin": "goblin_basic",
    "skeleton": "skeleton_basic",
    "zombie": "zombie_basic",
    "wolf": "wolf_beast",
    "giant_rat": None,  # No loot
    "orc": "orc_warrior",
    "hobgoblin": "goblin_basic",
    "bugbear": "bugbear_chief",
    "gnoll": "orc_warrior",
    "giant_spider": "giant_spider",
    "ogre": "ogre_brute",
    "troll": "troll_giant",
    "owlbear": None,  # Beast, no loot
    "minotaur": None,  # Beast-like, no loot
    "wight": "ghoul_undead",
    "dire_wolf": "wolf_beast",
    "ghoul": "ghoul_undead",
    "bandit": "bandit_basic",
    "bandit_captain": "bandit_captain",
    "cultist": "bandit_basic",
    "imp": None,  # Fiend, no loot
    "young_dragon": "young_dragon",
    "adult_dragon": "adult_dragon",
}


def get_loot_table(loot_table_id: str) -> dict | None:
    """Get a specific loot table by ID."""
    tables = load_loot_tables()
    for table in tables:
        if table["id"] == loot_table_id:
            return table
    return None


def get_loot_table_for_monster(monster_id: str) -> dict | None:
    """Get the loot table associated with a monster."""
    loot_table_id = MONSTER_LOOT_MAPPING.get(monster_id)
    if not loot_table_id:
        return None
    return get_loot_table(loot_table_id)


class LootTableItemResponse(BaseModel):
    item_name: str
    weight: int
    quantity: int


class LootTableDropResponse(BaseModel):
    item_name: str
    quantity: int


class LootTableResponse(BaseModel):
    id: str
    name: str
    description: str
    gold_range: list[int]
    items: list[LootTableItemResponse]
    guaranteed_drops: list[LootTableDropResponse]
    drop_count: dict


@router.get("/loot-tables")
def list_loot_tables():
    """List all loot tables."""
    tables = load_loot_tables()
    return {"loot_tables": tables, "count": len(tables)}


@router.get("/loot-tables/{table_id}", response_model=LootTableResponse)
def get_loot_table_by_id(table_id: str):
    """Get a specific loot table by ID."""
    table = get_loot_table(table_id)
    if not table:
        from ..core.exceptions import NotFoundError
        raise NotFoundError("LootTable", table_id)
    return table


@router.get("/loot-tables/for-monster/{monster_id}")
def get_monster_loot_table(monster_id: str):
    """Get the loot table associated with a monster."""
    # First verify the monster exists
    monster = get_monster(monster_id)
    if not monster:
        from ..core.exceptions import NotFoundError
        raise NotFoundError("Monster", monster_id)

    loot_table = get_loot_table_for_monster(monster_id)
    if not loot_table:
        return {
            "monster_id": monster_id,
            "monster_name": monster["name"],
            "loot_table": None,
            "message": f"{monster['name']} does not drop loot"
        }

    return {
        "monster_id": monster_id,
        "monster_name": monster["name"],
        "loot_table": loot_table
    }
