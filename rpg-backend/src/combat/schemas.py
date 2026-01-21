from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any

from ..core.enums import CombatStatus, ActionType, InitiativeType


class ParticipantRequest(BaseModel):
    character_id: int
    team_id: int


class CombatStartRequest(BaseModel):
    participants: list[ParticipantRequest] = Field(..., min_length=2)
    zone_id: int | None = None
    initiative_type: InitiativeType = InitiativeType.INDIVIDUAL


class CombatantResponse(BaseModel):
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
    status_effects: dict[str, int]  # effect_id -> remaining duration

    class Config:
        from_attributes = True


class CombatStartResponse(BaseModel):
    id: int
    status: CombatStatus
    round_number: int
    current_turn: int
    combatants: list[CombatantResponse]
    turn_order: list[int]  # List of combatant IDs in initiative order

    class Config:
        from_attributes = True


class CombatStateResponse(BaseModel):
    id: int
    status: CombatStatus
    round_number: int
    current_turn: int
    combatants: list[CombatantResponse]
    current_combatant: CombatantResponse | None
    awaiting_player: CombatantResponse | None  # Set when status is awaiting_player

    class Config:
        from_attributes = True


class PlayerActionRequest(BaseModel):
    character_id: int
    action_type: ActionType
    target_id: int | None = None  # Combatant ID to target
    ability_id: str | None = None  # Class ability ID (e.g., "second_wind")
    item_id: int | None = None
    spell_name: str | None = None  # Spell name for spell action


class ActionResultResponse(BaseModel):
    id: int
    round_number: int
    turn_number: int
    actor_combatant_id: int
    target_combatant_id: int | None
    action_type: ActionType
    roll: int | None
    total: int | None
    damage: int | None
    healing: int | None
    hit: bool | None
    critical: bool
    description: str | None

    class Config:
        from_attributes = True


class ProcessTurnResponse(BaseModel):
    actions_taken: list[ActionResultResponse]
    combatants: list[CombatantResponse]
    status: CombatStatus
    round_number: int
    current_turn: int
    awaiting_player: CombatantResponse | None
    combat_ended: bool


class ActionResult(BaseModel):
    action: ActionResultResponse
    combatants: list[CombatantResponse]
    status: CombatStatus
    combat_ended: bool = False


class LootItemResponse(BaseModel):
    item_name: str
    quantity: int


class LootResponse(BaseModel):
    gold: int
    items: list[LootItemResponse]


class LevelUpResponse(BaseModel):
    character_id: int
    old_level: int
    new_level: int


class ResolveResponse(BaseModel):
    winner_team_id: int | None
    experience_earned: dict[int, int]  # character_id -> exp
    loot: LootResponse
    level_ups: list[LevelUpResponse] = []


class CombatSummary(BaseModel):
    id: int
    winner_team_id: int | None
    total_rounds: int
    total_actions: int
    started_at: datetime
    ended_at: datetime | None
    participants: list[CombatantResponse]
    experience_by_character: dict[int, int]

    class Config:
        from_attributes = True


class CombatHistoryResponse(BaseModel):
    session_id: int
    actions: list[ActionResultResponse]
