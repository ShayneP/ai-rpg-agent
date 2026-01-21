"""
Pydantic models for API responses.

These models mirror the schemas from the tabletop-rpg-api for type-safe
deserialization of API responses in the LiveKit agent.
"""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Any


# Enums matching API
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
    INDIVIDUAL = "individual"
    GROUP = "group"
    SIDE = "side"
    REROLL = "reroll"


# Character Models
class APICharacter(BaseModel):
    """Character response from the API."""
    id: int
    name: str
    character_class: CharacterClass
    character_type: CharacterType
    status: CharacterStatus
    level: int
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int
    current_hp: int
    max_hp: int
    temporary_hp: int
    armor_class: int
    gold: int
    experience: int
    death_save_successes: int
    death_save_failures: int
    is_stable: bool
    monster_id: str | None = None
    x: int = 0
    y: int = 0
    zone_id: int | None = None

    @property
    def is_alive(self) -> bool:
        return self.status == CharacterStatus.ALIVE

    @property
    def health_percent(self) -> float:
        if self.max_hp == 0:
            return 0.0
        return (self.current_hp / self.max_hp) * 100

    def get_modifier(self, stat: str) -> int:
        """Calculate D&D-style ability modifier."""
        value = getattr(self, stat, 10)
        return (value - 10) // 2

    def get_status_description(self) -> str:
        """Get a narrative description of character's current status."""
        health_percent = self.health_percent

        if health_percent >= 100:
            health_desc = "in perfect health"
        elif health_percent >= 75:
            health_desc = "lightly wounded"
        elif health_percent >= 50:
            health_desc = "moderately wounded"
        elif health_percent >= 25:
            health_desc = "severely wounded"
        else:
            health_desc = "near death"

        return f"{self.name} is {health_desc} ({self.current_hp}/{self.max_hp} HP)"


class APIHealth(BaseModel):
    """Health status response."""
    current_hp: int
    max_hp: int
    temporary_hp: int
    armor_class: int


class APIAttributes(BaseModel):
    """Character attributes response."""
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int


class APILocation(BaseModel):
    """Character location response."""
    x: int
    y: int
    zone_id: int | None = None


# Item Models
class APIItem(BaseModel):
    """Item definition from the API."""
    id: int
    name: str
    description: str | None = None
    item_type: ItemType
    rarity: ItemRarity
    weight: float = 0.0
    value: int = 0
    stackable: bool = False
    max_stack: int = 1
    properties: dict[str, Any] = Field(default_factory=dict)
    ground_x: int | None = None
    ground_y: int | None = None
    ground_zone_id: int | None = None


class APIInventoryItem(BaseModel):
    """Inventory item response (item instance in character's inventory)."""
    id: int
    item_id: int
    quantity: int
    equipped: bool
    equipment_slot: str | None = None
    item: APIItem


# Combat Models
class APICombatant(BaseModel):
    """Combatant in a combat session."""
    id: int
    character_id: int
    team_id: int
    is_player: bool
    name: str
    initiative: int
    current_hp: int
    max_hp: int
    armor_class: int
    threat: int
    turn_order: int
    turn_count: int
    is_alive: bool
    can_act: bool
    status_effects: dict[str, int] = Field(default_factory=dict)

    @property
    def health_percent(self) -> float:
        if self.max_hp == 0:
            return 0.0
        return (self.current_hp / self.max_hp) * 100

    def get_status_description(self) -> str:
        """Get a narrative description of combatant's current status."""
        health_percent = self.health_percent

        if not self.is_alive:
            return f"{self.name} has been defeated!"
        elif health_percent >= 100:
            health_desc = "in perfect health"
        elif health_percent >= 75:
            health_desc = "lightly wounded"
        elif health_percent >= 50:
            health_desc = "moderately wounded"
        elif health_percent >= 25:
            health_desc = "severely wounded"
        else:
            health_desc = "near death"

        return f"{self.name} is {health_desc} ({self.current_hp}/{self.max_hp} HP)"


class APICombatSession(BaseModel):
    """Combat session state from the API."""
    id: int
    status: CombatStatus
    round_number: int
    current_turn: int
    combatants: list[APICombatant]
    current_combatant: APICombatant | None = None
    awaiting_player: APICombatant | None = None
    turn_order: list[int] | None = None  # Only in start response

    def get_player_combatant(self) -> APICombatant | None:
        """Get the player's combatant."""
        for c in self.combatants:
            if c.is_player:
                return c
        return None

    def get_enemies(self) -> list[APICombatant]:
        """Get all enemy combatants that are alive."""
        player = self.get_player_combatant()
        if not player:
            return []
        return [c for c in self.combatants if c.team_id != player.team_id and c.is_alive]

    def get_combatant_by_id(self, combatant_id: int) -> APICombatant | None:
        """Find a combatant by their ID."""
        for c in self.combatants:
            if c.id == combatant_id:
                return c
        return None

    def get_combatant_by_name(self, name: str) -> APICombatant | None:
        """Find a combatant by name (case-insensitive partial match)."""
        name_lower = name.lower()
        for c in self.combatants:
            if name_lower in c.name.lower():
                return c
        return None


class APIActionResult(BaseModel):
    """Result of a combat action."""
    id: int
    round_number: int
    turn_number: int
    actor_combatant_id: int
    target_combatant_id: int | None = None
    action_type: ActionType
    roll: int | None = None
    total: int | None = None
    damage: int | None = None
    healing: int | None = None
    hit: bool | None = None
    critical: bool = False
    description: str | None = None


class APIProcessTurnResponse(BaseModel):
    """Response from processing NPC turns."""
    actions_taken: list[APIActionResult]
    combatants: list[APICombatant]
    status: CombatStatus
    round_number: int
    current_turn: int
    awaiting_player: APICombatant | None = None
    combat_ended: bool


class APIPlayerActionResponse(BaseModel):
    """Response from a player action."""
    action: APIActionResult
    combatants: list[APICombatant]
    status: CombatStatus
    combat_ended: bool = False


class APILootItem(BaseModel):
    """An item in combat loot."""
    item_name: str
    quantity: int


class APILoot(BaseModel):
    """Combat loot with gold and items."""
    gold: int = 0
    items: list[APILootItem] = Field(default_factory=list)


class APILevelUp(BaseModel):
    """Level up information."""
    character_id: int
    old_level: int
    new_level: int


class APIResolveResponse(BaseModel):
    """Response from resolving combat (calculating rewards)."""
    winner_team_id: int | None = None
    experience_earned: dict[int, int] = Field(default_factory=dict)  # character_id -> xp
    loot: APILoot = Field(default_factory=APILoot)
    level_ups: list[APILevelUp] = Field(default_factory=list)


class APICombatSummary(BaseModel):
    """Final combat summary."""
    id: int
    winner_team_id: int | None = None
    total_rounds: int
    total_actions: int
    started_at: datetime
    ended_at: datetime | None = None
    participants: list[APICombatant]
    experience_by_character: dict[int, int] = Field(default_factory=dict)


# Reference Data Models
class APIMonster(BaseModel):
    """Monster template from reference data."""
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
    attacks: list[dict[str, Any]] = Field(default_factory=list)
    special_abilities: list[str] = Field(default_factory=list)
    vulnerabilities: list[str] = Field(default_factory=list)
    immunities: list[str] = Field(default_factory=list)
    condition_immunities: list[str] = Field(default_factory=list)
    description: str | None = None


class APIWeapon(BaseModel):
    """Weapon from reference data."""
    name: str
    category: str
    cost_gp: float
    cost_display: str
    damage_dice: str
    damage_type: str
    weight: float
    properties: list[str] = Field(default_factory=list)
    range: str | None = None
    versatile_dice: str | None = None


class APISpell(BaseModel):
    """Spell from reference data."""
    id: str
    name: str
    level: int
    school: str
    casting_time: str
    range: str
    components: str
    duration: str
    description: str
    damage_dice: str | None = None
    damage_type: str | None = None
    healing_dice: str | None = None
    classes: list[str] = Field(default_factory=list)
    is_ritual: bool = False
    concentration: bool = False


class APIAbility(BaseModel):
    """Class ability from reference data."""
    id: str
    name: str
    character_class: str
    min_level: int
    description: str
    effect_type: str
    damage_dice: str | None = None
    healing_dice: str | None = None
    max_uses: int | None = None
    uses_per_rest: str | None = None  # "short" or "long"


class APILootTable(BaseModel):
    """Loot table from reference data."""
    id: str
    name: str
    description: str
    gold_range: list[int]
    items: list[dict[str, Any]] = Field(default_factory=list)
    guaranteed_drops: list[str] = Field(default_factory=list)
    drop_count: dict[str, int] = Field(default_factory=dict)


# XP and Level Models
class APIXPStatus(BaseModel):
    """XP progress status."""
    level: int
    experience: int
    xp_for_next_level: int
    xp_progress: int
    xp_needed: int


class APIExperienceResult(BaseModel):
    """Result of awarding experience."""
    experience: int
    level: int
    leveled_up: bool
    new_max_hp: int | None = None


# Trade Models
class APITradeResult(BaseModel):
    """Result of a trade proposal."""
    success: bool
    message: str
    roll: int
    dc: int
    offer_value: int
    request_value: int
    player_gold: int | None = None
    npc_gold: int | None = None


class APITradeValueCheck(BaseModel):
    """Trade value check result."""
    offer_value: int
    request_value: int
    dc: int
    fair_trade: bool


# Location Models
class APIZone(BaseModel):
    """Zone/location from the API."""
    id: int
    name: str
    description: str | None = None
    entry_description: str | None = None
    width: int = 1
    height: int = 1


class APIExit(BaseModel):
    """Exit connecting two zones."""
    id: int
    from_zone_id: int
    to_zone_id: int
    name: str
    description: str | None = None
    hidden: bool = False
    locked: bool = False
    key_item_id: int | None = None


class APIExitWithDestination(APIExit):
    """Exit with destination zone info for navigation display."""
    to_zone_name: str
    to_zone_entry_description: str | None = None


class APITravelResponse(BaseModel):
    """Response from traveling through an exit."""
    success: bool
    message: str
    new_zone: APIZone | None = None
    exits: list["APIExitWithDestination"] = Field(default_factory=list)


class APIUnlockResponse(BaseModel):
    """Response from attempting to unlock an exit."""
    success: bool
    message: str


class APIExitConnection(BaseModel):
    """Exit connection for creating a zone with exits."""
    connect_to_zone_id: int
    exit_name: str
    exit_description: str | None = None
    return_exit_name: str
    return_exit_description: str | None = None
    hidden: bool = False
    locked: bool = False


class APIZoneCreateWithExitsResponse(BaseModel):
    """Response from creating a zone with exits."""
    zone: APIZone
    exits_created: list[APIExit]


# Quest Models
class QuestStatus(str, Enum):
    AVAILABLE = "available"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


class APIObjective(BaseModel):
    """Quest objective from the API."""
    id: int
    description: str
    target_count: int
    order: int
    objective_type: str = "generic"
    target_identifier: str | None = None


class APIQuest(BaseModel):
    """Quest definition from the API."""
    id: int
    title: str
    description: str | None = None
    level_requirement: int = 1
    experience_reward: int = 0
    gold_reward: int = 0
    item_rewards: list[int] = Field(default_factory=list)
    prerequisites: list[int] = Field(default_factory=list)
    objectives: list[APIObjective] = Field(default_factory=list)


class APIObjectiveProgress(BaseModel):
    """Progress on a quest objective."""
    objective_id: int
    description: str
    target_count: int
    current_count: int
    completed: bool


class APIQuestAssignment(BaseModel):
    """Quest assignment to a character."""
    id: int
    quest_id: int
    character_id: int
    status: QuestStatus
    quest: APIQuest
    objectives_progress: list[APIObjectiveProgress] = Field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        """Check if all objectives are complete."""
        return all(p.completed for p in self.objectives_progress)

    @property
    def progress_summary(self) -> str:
        """Get a summary of quest progress."""
        done = sum(1 for p in self.objectives_progress if p.completed)
        total = len(self.objectives_progress)
        return f"{done}/{total} objectives complete"


# Scenario Models
class EffectType(str, Enum):
    HELP = "help"
    HURT = "hurt"
    NEUTRAL = "neutral"


class APIScenario(BaseModel):
    """Scenario (narrative event) from the API."""
    id: int
    title: str
    description: str | None = None
    narrative_text: str | None = None
    triggers: list[dict[str, Any]] = Field(default_factory=list)
    outcomes: list[dict[str, Any]] = Field(default_factory=list)
    repeatable: bool = False
    cooldown_seconds: int | None = None


class APIScenarioHistory(BaseModel):
    """Record of a scenario being triggered."""
    id: int
    scenario_id: int
    character_id: int
    triggered_at: datetime
    outcome_index: int | None = None
    outcome_data: dict[str, Any] = Field(default_factory=dict)
    scenario: APIScenario | None = None


class APITriggerScenarioResponse(BaseModel):
    """Response from triggering a scenario."""
    scenario_id: int
    character_id: int
    narrative_text: str | None = None
    outcome_applied: dict[str, Any] = Field(default_factory=dict)
    effects_applied: dict[str, Any] = Field(default_factory=dict)
    history_id: int


class APIEvaluateScenariosResponse(BaseModel):
    """Response from evaluating scenarios for a character."""
    character_id: int
    applicable_scenarios: list[dict[str, Any]] = Field(default_factory=list)
    count: int = 0
    triggered: APITriggerScenarioResponse | None = None
