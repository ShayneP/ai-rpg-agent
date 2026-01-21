from enum import Enum


class CharacterClass(str, Enum):
    WARRIOR = "warrior"
    MAGE = "mage"
    ROGUE = "rogue"
    CLERIC = "cleric"
    RANGER = "ranger"


class CharacterType(str, Enum):
    PLAYER = "player"
    NPC = "npc"


class CharacterStatus(str, Enum):
    ALIVE = "alive"
    UNCONSCIOUS = "unconscious"
    DEAD = "dead"


class ItemType(str, Enum):
    WEAPON = "weapon"
    ARMOR = "armor"
    CONSUMABLE = "consumable"
    QUEST = "quest"
    MISC = "misc"


class ItemRarity(str, Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"


class TerrainType(str, Enum):
    GRASS = "grass"
    STONE = "stone"
    WATER = "water"
    FOREST = "forest"
    MOUNTAIN = "mountain"
    SAND = "sand"
    SWAMP = "swamp"
    LAVA = "lava"
    ICE = "ice"
    VOID = "void"


class QuestStatus(str, Enum):
    AVAILABLE = "available"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


class EventType(str, Enum):
    COMBAT_START = "combat_start"
    COMBAT_END = "combat_end"
    CHARACTER_DEATH = "character_death"
    ITEM_ACQUIRED = "item_acquired"
    ITEM_USED = "item_used"
    QUEST_STARTED = "quest_started"
    QUEST_COMPLETED = "quest_completed"
    LEVEL_UP = "level_up"
    LOCATION_CHANGE = "location_change"
    SCENARIO_TRIGGERED = "scenario_triggered"
    CUSTOM = "custom"


class EffectType(str, Enum):
    HELP = "help"
    HURT = "hurt"
    NEUTRAL = "neutral"


class CombatStatus(str, Enum):
    INITIALIZING = "initializing"
    IN_PROGRESS = "in_progress"
    AWAITING_PLAYER = "awaiting_player"
    RESOLVING = "resolving"
    FINISHED = "finished"


class ActionType(str, Enum):
    ATTACK = "attack"
    SPELL = "spell"
    ABILITY = "ability"
    ITEM = "item"
    DEFEND = "defend"
    DODGE = "dodge"
    FLEE = "flee"
    PASS = "pass"


class InitiativeType(str, Enum):
    INDIVIDUAL = "individual"  # Each combatant rolls individually (default)
    GROUP = "group"  # One roll per team, all team members share initiative
    SIDE = "side"  # Alternating turns between teams (Team 1, Team 2, Team 1...)
    REROLL = "reroll"  # Re-roll initiative each round
