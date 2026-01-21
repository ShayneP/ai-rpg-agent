from pydantic import BaseModel, Field

from ..core.enums import TerrainType
from ..character.schemas import CharacterResponse
from ..inventory.schemas import ItemResponse


class ZoneCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    entry_description: str | None = Field(default=None, max_length=1000)
    width: int = Field(default=1, ge=1, le=1000)
    height: int = Field(default=1, ge=1, le=1000)


class ZoneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    entry_description: str | None = Field(default=None, max_length=1000)


class GridCellResponse(BaseModel):
    id: int
    x: int
    y: int
    terrain_type: TerrainType
    passable: bool
    description: str | None

    class Config:
        from_attributes = True


class ZoneResponse(BaseModel):
    id: int
    name: str
    description: str | None
    entry_description: str | None
    width: int
    height: int

    class Config:
        from_attributes = True


class ZoneDetailResponse(ZoneResponse):
    grid_cells: list[GridCellResponse] = []


# Exit schemas
class ExitCreate(BaseModel):
    from_zone_id: int
    to_zone_id: int
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    hidden: bool = False
    locked: bool = False
    key_item_id: int | None = None


class ExitUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    hidden: bool | None = None
    locked: bool | None = None
    key_item_id: int | None = None


class ExitResponse(BaseModel):
    id: int
    from_zone_id: int
    to_zone_id: int
    name: str
    description: str | None
    hidden: bool
    locked: bool
    key_item_id: int | None

    class Config:
        from_attributes = True


class ExitWithDestinationResponse(ExitResponse):
    """Exit response that includes destination zone info for navigation."""
    to_zone_name: str
    to_zone_entry_description: str | None


class ZoneWithExitsResponse(ZoneResponse):
    """Zone response that includes all available exits."""
    exits: list[ExitWithDestinationResponse] = []


class TravelRequest(BaseModel):
    character_id: int


class TravelResponse(BaseModel):
    success: bool
    message: str
    new_zone: ZoneResponse | None = None
    exits: list[ExitWithDestinationResponse] = []


class UnlockRequest(BaseModel):
    character_id: int
    item_id: int | None = None  # Optional: item to use as key


class UnlockResponse(BaseModel):
    success: bool
    message: str


class GridCellCreate(BaseModel):
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    terrain_type: TerrainType = TerrainType.GRASS
    passable: bool = True
    description: str | None = Field(default=None, max_length=200)


class GridCellUpdate(BaseModel):
    terrain_type: TerrainType | None = None
    passable: bool | None = None
    description: str | None = Field(default=None, max_length=200)


class LocationQueryParams(BaseModel):
    zone_id: int
    x: int | None = None
    y: int | None = None
    radius: int | None = Field(default=None, ge=0)


class SurroundingsRequest(BaseModel):
    zone_id: int
    x: int
    y: int
    radius: int = Field(default=1, ge=1, le=10)


class SurroundingsResponse(BaseModel):
    center_x: int
    center_y: int
    zone_id: int
    cells: list[GridCellResponse]
    characters: list[CharacterResponse]
    items: list[ItemResponse]


# Dynamic zone creation schemas
class ExitConnectionCreate(BaseModel):
    """Define an exit connection when creating a new zone."""
    connect_to_zone_id: int  # Existing zone to connect to
    exit_name: str = Field(..., min_length=1, max_length=100)  # e.g., "dark cave entrance"
    exit_description: str | None = Field(default=None, max_length=500)
    return_exit_name: str = Field(..., min_length=1, max_length=100)  # e.g., "path back to town"
    return_exit_description: str | None = Field(default=None, max_length=500)
    hidden: bool = False
    locked: bool = False


class ZoneCreateWithExits(BaseModel):
    """Create a zone with bidirectional exits to existing zones."""
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    entry_description: str | None = Field(default=None, max_length=1000)
    exits: list[ExitConnectionCreate] = Field(default_factory=list)


class ZoneCreateWithExitsResponse(BaseModel):
    """Response when creating a zone with exits."""
    zone: ZoneResponse
    exits_created: list[ExitResponse]
