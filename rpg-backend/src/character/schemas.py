from pydantic import BaseModel, Field

from ..core.enums import CharacterClass, CharacterType, CharacterStatus


class CharacterCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    character_class: CharacterClass
    character_type: CharacterType = CharacterType.PLAYER
    level: int = Field(default=1, ge=1)
    # Optional starting attributes (class bonuses applied on top)
    strength: int = Field(default=10, ge=1, le=30)
    dexterity: int = Field(default=10, ge=1, le=30)
    constitution: int = Field(default=10, ge=1, le=30)
    intelligence: int = Field(default=10, ge=1, le=30)
    wisdom: int = Field(default=10, ge=1, le=30)
    charisma: int = Field(default=10, ge=1, le=30)
    # Starting gold
    gold: int = Field(default=0, ge=0)


class CharacterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    character_class: CharacterClass | None = None
    character_type: CharacterType | None = None
    status: CharacterStatus | None = None
    level: int | None = Field(default=None, ge=1)
    gold: int | None = Field(default=None, ge=0)
    experience: int | None = Field(default=None, ge=0)


class CharacterResponse(BaseModel):
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
    monster_id: str | None
    x: int
    y: int
    zone_id: int | None

    class Config:
        from_attributes = True


class AttributesUpdate(BaseModel):
    strength: int | None = Field(default=None, ge=1, le=30)
    dexterity: int | None = Field(default=None, ge=1, le=30)
    constitution: int | None = Field(default=None, ge=1, le=30)
    intelligence: int | None = Field(default=None, ge=1, le=30)
    wisdom: int | None = Field(default=None, ge=1, le=30)
    charisma: int | None = Field(default=None, ge=1, le=30)


class AttributesResponse(BaseModel):
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int

    class Config:
        from_attributes = True


class SkillCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    level: int = Field(default=1, ge=1)
    experience: int = Field(default=0, ge=0)


class SkillUpdate(BaseModel):
    level: int | None = Field(default=None, ge=1)
    experience: int | None = Field(default=None, ge=0)


class SkillResponse(BaseModel):
    id: int
    name: str
    level: int
    experience: int

    class Config:
        from_attributes = True


class HealthUpdate(BaseModel):
    current_hp: int | None = Field(default=None, ge=0)
    max_hp: int | None = Field(default=None, ge=1)
    temporary_hp: int | None = Field(default=None, ge=0)
    armor_class: int | None = Field(default=None, ge=0)


class HealthResponse(BaseModel):
    current_hp: int
    max_hp: int
    temporary_hp: int
    armor_class: int

    class Config:
        from_attributes = True


class LocationUpdate(BaseModel):
    x: int
    y: int
    zone_id: int | None = None


class LocationResponse(BaseModel):
    x: int
    y: int
    zone_id: int | None

    class Config:
        from_attributes = True
