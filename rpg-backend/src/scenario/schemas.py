from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any

from ..core.enums import EffectType


class TriggerCondition(BaseModel):
    type: str  # "location", "item", "quest", "health_threshold", etc.
    # Additional fields depend on type
    zone_id: int | None = None
    x: int | None = None
    y: int | None = None
    item_id: int | None = None
    quest_id: int | None = None
    quest_status: str | None = None
    threshold: float | None = None
    comparison: str | None = None  # "above", "below", "equal"


class OutcomeDefinition(BaseModel):
    description: str = Field(..., max_length=500)
    effect_type: EffectType = EffectType.NEUTRAL
    health_change: int | None = None
    attribute_modifiers: dict[str, int] | None = None
    items_granted: list[int] | None = None
    items_removed: list[int] | None = None
    trigger_quest_id: int | None = None
    weight: int = Field(default=1, ge=1)


class ScenarioCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    narrative_text: str | None = Field(default=None, max_length=5000)
    triggers: list[dict[str, Any]] = Field(default_factory=list)
    outcomes: list[dict[str, Any]] = Field(default_factory=list)
    repeatable: bool = False
    cooldown_seconds: int | None = Field(default=None, ge=0)


class ScenarioUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    narrative_text: str | None = Field(default=None, max_length=5000)
    triggers: list[dict[str, Any]] | None = None
    outcomes: list[dict[str, Any]] | None = None
    repeatable: bool | None = None
    cooldown_seconds: int | None = Field(default=None, ge=0)


class ScenarioResponse(BaseModel):
    id: int
    title: str
    description: str | None
    narrative_text: str | None
    triggers: list[dict[str, Any]]
    outcomes: list[dict[str, Any]]
    repeatable: bool
    cooldown_seconds: int | None

    class Config:
        from_attributes = True


class TriggerScenarioRequest(BaseModel):
    outcome_index: int | None = None  # If None, randomly select based on weights


class TriggerScenarioResponse(BaseModel):
    scenario_id: int
    character_id: int
    narrative_text: str | None
    outcome_applied: dict[str, Any]
    effects_applied: dict[str, Any]
    history_id: int


class ScenarioHistoryResponse(BaseModel):
    id: int
    scenario_id: int
    character_id: int
    triggered_at: datetime
    outcome_index: int | None
    outcome_data: dict[str, Any]
    scenario: ScenarioResponse

    class Config:
        from_attributes = True
