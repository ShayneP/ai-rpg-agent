from pydantic import BaseModel, Field

from ..core.enums import QuestStatus


class ObjectiveCreate(BaseModel):
    description: str = Field(..., min_length=1, max_length=500)
    target_count: int = Field(default=1, ge=1)
    order: int = Field(default=0, ge=0)
    # Objective type for automatic completion: "talk_to", "reach_location", "win_combat", "collect_item", "generic"
    objective_type: str = Field(default="generic", max_length=50)
    # Target identifier (NPC name like "barkeep", zone_id like "2", item_id, enemy type, etc.)
    target_identifier: str | None = Field(default=None, max_length=200)


class ObjectiveResponse(BaseModel):
    id: int
    description: str
    target_count: int
    order: int
    objective_type: str
    target_identifier: str | None

    class Config:
        from_attributes = True


class QuestCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    level_requirement: int = Field(default=1, ge=1)
    experience_reward: int = Field(default=0, ge=0)
    gold_reward: int = Field(default=0, ge=0)
    item_rewards: list[int] = Field(default_factory=list)
    prerequisites: list[int] = Field(default_factory=list)
    objectives: list[ObjectiveCreate] = Field(default_factory=list)


class QuestUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    level_requirement: int | None = Field(default=None, ge=1)
    experience_reward: int | None = Field(default=None, ge=0)
    gold_reward: int | None = Field(default=None, ge=0)
    item_rewards: list[int] | None = None
    prerequisites: list[int] | None = None


class QuestResponse(BaseModel):
    id: int
    title: str
    description: str | None
    level_requirement: int
    experience_reward: int
    gold_reward: int
    item_rewards: list[int]
    prerequisites: list[int]
    objectives: list[ObjectiveResponse]

    class Config:
        from_attributes = True


class ObjectiveProgressResponse(BaseModel):
    objective_id: int
    description: str
    target_count: int
    current_count: int
    completed: bool


class QuestAssignmentResponse(BaseModel):
    id: int
    quest_id: int
    character_id: int
    status: QuestStatus
    quest: QuestResponse
    objectives_progress: list[ObjectiveProgressResponse]

    class Config:
        from_attributes = True


class QuestAssignRequest(BaseModel):
    character_id: int


class ObjectiveProgress(BaseModel):
    objective_id: int
    progress: int = Field(..., ge=0)  # Amount to add or set


class ProgressUpdate(BaseModel):
    objective_id: int
    amount: int = Field(default=1, ge=1)  # Amount to add to current progress
