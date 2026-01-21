from sqlalchemy import Column, Integer, String, Enum, ForeignKey, JSON
from sqlalchemy.orm import relationship

from ..database import Base
from ..core.enums import CharacterClass, CharacterType, CharacterStatus

# Spell slots per level for spellcasters (Mage/Cleric)
# Format: {character_level: {spell_level: num_slots}}
SPELL_SLOTS_BY_LEVEL = {
    1: {1: 2},
    2: {1: 3},
    3: {1: 4, 2: 2},
    4: {1: 4, 2: 3},
    5: {1: 4, 2: 3, 3: 2},
    6: {1: 4, 2: 3, 3: 3},
    7: {1: 4, 2: 3, 3: 3, 4: 1},
    8: {1: 4, 2: 3, 3: 3, 4: 2},
    9: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
    10: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
}


# Class bonuses configuration
CLASS_BONUSES = {
    CharacterClass.WARRIOR: {
        "strength": 2,
        "constitution": 1,
        "base_hp_bonus": 10,
    },
    CharacterClass.MAGE: {
        "intelligence": 2,
        "wisdom": 1,
        "spell_slots": 3,
    },
    CharacterClass.ROGUE: {
        "dexterity": 2,
        "charisma": 1,
        "initiative_bonus": 2,
    },
    CharacterClass.CLERIC: {
        "wisdom": 2,
        "constitution": 1,
        "healing_bonus": 2,
    },
    CharacterClass.RANGER: {
        "dexterity": 1,
        "wisdom": 1,
        "strength": 1,
    },
}


class Character(Base):
    __tablename__ = "characters"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    character_class = Column(Enum(CharacterClass), nullable=False)
    character_type = Column(Enum(CharacterType), default=CharacterType.PLAYER)
    status = Column(Enum(CharacterStatus), default=CharacterStatus.ALIVE)
    level = Column(Integer, default=1)

    # Attributes
    strength = Column(Integer, default=10)
    dexterity = Column(Integer, default=10)
    constitution = Column(Integer, default=10)
    intelligence = Column(Integer, default=10)
    wisdom = Column(Integer, default=10)
    charisma = Column(Integer, default=10)

    # Health
    current_hp = Column(Integer, default=10)
    max_hp = Column(Integer, default=10)
    temporary_hp = Column(Integer, default=0)
    armor_class = Column(Integer, default=10)

    # Currency and Experience
    gold = Column(Integer, default=0)
    experience = Column(Integer, default=0)

    # Spell slots (JSON: {spell_level: current_slots})
    spell_slots = Column(JSON, default=dict)
    max_spell_slots = Column(JSON, default=dict)

    # Ability uses tracking (JSON: {ability_id: uses_remaining})
    ability_uses = Column(JSON, default=dict)

    # Death saving throws
    death_save_successes = Column(Integer, default=0)
    death_save_failures = Column(Integer, default=0)
    is_stable = Column(Integer, default=0)  # 0=not stable, 1=stable (SQLite doesn't have bool)

    # Monster template reference (for loot tables)
    monster_id = Column(String(50), nullable=True)

    # Location
    x = Column(Integer, default=0)
    y = Column(Integer, default=0)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=True)

    # Relationships
    skills = relationship("CharacterSkill", back_populates="character", cascade="all, delete-orphan")
    inventory_items = relationship("InventoryItem", back_populates="character", cascade="all, delete-orphan")
    quest_assignments = relationship("QuestAssignment", back_populates="character", cascade="all, delete-orphan")
    scenario_history = relationship("ScenarioHistory", back_populates="character", cascade="all, delete-orphan")

    def apply_class_bonuses(self):
        """Apply starting bonuses based on character class."""
        bonuses = CLASS_BONUSES.get(self.character_class, {})
        for attr, value in bonuses.items():
            if attr == "base_hp_bonus":
                self.max_hp += value
                self.current_hp = self.max_hp
            elif attr == "spell_slots":
                # Initialize spell slots for spellcasters
                self._init_spell_slots()
            elif hasattr(self, attr):
                setattr(self, attr, getattr(self, attr) + value)

    def _init_spell_slots(self):
        """Initialize spell slots based on character level."""
        if self.character_class in [CharacterClass.MAGE, CharacterClass.CLERIC]:
            slots = SPELL_SLOTS_BY_LEVEL.get(min(self.level, 10), {})
            self.max_spell_slots = {str(k): v for k, v in slots.items()}
            self.spell_slots = {str(k): v for k, v in slots.items()}

    def update_spell_slots_for_level(self):
        """Update spell slots when leveling up."""
        if self.character_class in [CharacterClass.MAGE, CharacterClass.CLERIC]:
            slots = SPELL_SLOTS_BY_LEVEL.get(min(self.level, 10), {})
            old_max = self.max_spell_slots or {}
            new_max = {str(k): v for k, v in slots.items()}
            # Add any new slots gained
            for level, count in new_max.items():
                old_count = old_max.get(level, 0)
                if count > old_count:
                    current = (self.spell_slots or {}).get(level, 0)
                    self.spell_slots[level] = current + (count - old_count)
            self.max_spell_slots = new_max

    def get_modifier(self, attribute: str) -> int:
        """Calculate attribute modifier: (attribute - 10) / 2."""
        value = getattr(self, attribute, 10)
        return (value - 10) // 2


class CharacterSkill(Base):
    __tablename__ = "character_skills"

    id = Column(Integer, primary_key=True, index=True)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    name = Column(String(50), nullable=False)
    level = Column(Integer, default=1)
    experience = Column(Integer, default=0)

    character = relationship("Character", back_populates="skills")
