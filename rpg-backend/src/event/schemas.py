from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any

from ..core.enums import EventType


class EventCreate(BaseModel):
    event_type: EventType
    character_id: int | None = None
    target_character_id: int | None = None
    item_id: int | None = None
    quest_id: int | None = None
    scenario_id: int | None = None
    combat_session_id: int | None = None
    zone_id: int | None = None
    x: int | None = None
    y: int | None = None
    description: str | None = Field(default=None, max_length=500)
    data: dict[str, Any] = Field(default_factory=dict)


class EventResponse(BaseModel):
    id: int
    event_type: EventType
    timestamp: datetime
    character_id: int | None
    target_character_id: int | None
    item_id: int | None
    quest_id: int | None
    scenario_id: int | None
    combat_session_id: int | None
    zone_id: int | None
    x: int | None
    y: int | None
    description: str | None
    data: dict[str, Any]

    class Config:
        from_attributes = True


class EventQuery(BaseModel):
    event_type: EventType | None = None
    character_id: int | None = None
    quest_id: int | None = None
    scenario_id: int | None = None
    combat_session_id: int | None = None
    zone_id: int | None = None
    from_timestamp: datetime | None = None
    to_timestamp: datetime | None = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
