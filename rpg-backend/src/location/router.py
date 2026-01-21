from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from . import service
from .schemas import (
    ZoneCreate,
    ZoneUpdate,
    ZoneResponse,
    ZoneDetailResponse,
    GridCellCreate,
    GridCellUpdate,
    GridCellResponse,
    SurroundingsRequest,
    SurroundingsResponse,
    ExitCreate,
    ExitUpdate,
    ExitResponse,
    ExitWithDestinationResponse,
    TravelRequest,
    TravelResponse,
    UnlockRequest,
    UnlockResponse,
    ZoneCreateWithExits,
    ZoneCreateWithExitsResponse,
)
from ..character.schemas import CharacterResponse
from ..inventory.schemas import ItemResponse

router = APIRouter(prefix="/location", tags=["location"])


# Zone routes
@router.post("/zones", response_model=ZoneResponse, status_code=201)
def create_zone(zone: ZoneCreate, db: Session = Depends(get_db)):
    """Create a new zone."""
    return service.create_zone(db, zone)


@router.get("/zones", response_model=list[ZoneResponse])
def list_zones(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """List all zones."""
    return service.get_zones(db, skip, limit)


@router.get("/zones/{zone_id}", response_model=ZoneResponse)
def get_zone(zone_id: int, db: Session = Depends(get_db)):
    """Get a zone by ID."""
    return service.get_zone(db, zone_id)


@router.put("/zones/{zone_id}", response_model=ZoneResponse)
def update_zone(zone_id: int, zone: ZoneUpdate, db: Session = Depends(get_db)):
    """Update a zone."""
    return service.update_zone(db, zone_id, zone)


@router.delete("/zones/{zone_id}", status_code=204)
def delete_zone(zone_id: int, db: Session = Depends(get_db)):
    """Delete a zone."""
    service.delete_zone(db, zone_id)


# Grid cell routes
@router.get("/zones/{zone_id}/cells", response_model=list[GridCellResponse])
def get_zone_cells(zone_id: int, db: Session = Depends(get_db)):
    """Get all grid cells in a zone."""
    return service.get_zone_cells(db, zone_id)


@router.post("/zones/{zone_id}/cells", response_model=GridCellResponse, status_code=201)
def create_grid_cell(zone_id: int, cell: GridCellCreate, db: Session = Depends(get_db)):
    """Create a grid cell in a zone."""
    return service.create_grid_cell(db, zone_id, cell)


@router.get("/zones/{zone_id}/cells/{x}/{y}", response_model=GridCellResponse)
def get_grid_cell(zone_id: int, x: int, y: int, db: Session = Depends(get_db)):
    """Get a specific grid cell."""
    cell = service.get_grid_cell(db, zone_id, x, y)
    if not cell:
        from ..core.exceptions import NotFoundError
        raise NotFoundError("GridCell", f"({x}, {y})")
    return cell


@router.put("/zones/{zone_id}/cells/{x}/{y}", response_model=GridCellResponse)
def update_grid_cell(zone_id: int, x: int, y: int, cell: GridCellUpdate, db: Session = Depends(get_db)):
    """Update a grid cell."""
    return service.update_grid_cell(db, zone_id, x, y, cell)


# Spatial query routes
@router.get("/characters", response_model=list[CharacterResponse])
def get_characters_at_location(
    zone_id: int,
    x: int | None = None,
    y: int | None = None,
    radius: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
):
    """Query characters at a location with optional radius."""
    return service.get_characters_at_location(db, zone_id, x, y, radius)


@router.get("/items", response_model=list[ItemResponse])
def get_items_at_location(
    zone_id: int,
    x: int | None = None,
    y: int | None = None,
    radius: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
):
    """Query items on the ground at a location with optional radius."""
    return service.get_items_at_location(db, zone_id, x, y, radius)


@router.post("/surroundings", response_model=SurroundingsResponse)
def get_surroundings(request: SurroundingsRequest, db: Session = Depends(get_db)):
    """Get all surroundings (cells, characters, items) around a position."""
    return service.get_surroundings(db, request)


# Exit routes
@router.post("/exits", response_model=ExitResponse, status_code=201)
def create_exit(exit_data: ExitCreate, db: Session = Depends(get_db)):
    """Create a new exit between zones."""
    return service.create_exit(db, exit_data)


@router.get("/exits/{exit_id}", response_model=ExitResponse)
def get_exit(exit_id: int, db: Session = Depends(get_db)):
    """Get an exit by ID."""
    return service.get_exit(db, exit_id)


@router.put("/exits/{exit_id}", response_model=ExitResponse)
def update_exit(exit_id: int, exit_data: ExitUpdate, db: Session = Depends(get_db)):
    """Update an exit."""
    return service.update_exit(db, exit_id, exit_data)


@router.delete("/exits/{exit_id}", status_code=204)
def delete_exit(exit_id: int, db: Session = Depends(get_db)):
    """Delete an exit."""
    service.delete_exit(db, exit_id)


@router.get("/zones/{zone_id}/exits", response_model=list[ExitWithDestinationResponse])
def get_zone_exits(
    zone_id: int,
    include_hidden: bool = Query(False, description="Include hidden exits"),
    db: Session = Depends(get_db),
):
    """Get all exits from a zone with destination info."""
    return service.get_exits_with_destinations(db, zone_id, include_hidden)


@router.post("/exits/{exit_id}/travel", response_model=TravelResponse)
def travel_through_exit(
    exit_id: int,
    request: TravelRequest,
    db: Session = Depends(get_db),
):
    """Travel through an exit to the destination zone.

    Returns the new zone info and available exits from there.
    """
    return service.travel_through_exit(db, exit_id, request.character_id)


@router.post("/exits/{exit_id}/unlock", response_model=UnlockResponse)
def unlock_exit(
    exit_id: int,
    request: UnlockRequest,
    db: Session = Depends(get_db),
):
    """Attempt to unlock a locked exit.

    If the exit requires a key, the character must have it in inventory.
    """
    return service.unlock_exit(db, exit_id, request.character_id, request.item_id)


# Dynamic zone creation
@router.post("/zones/with-exits", response_model=ZoneCreateWithExitsResponse, status_code=201)
def create_zone_with_exits(data: ZoneCreateWithExits, db: Session = Depends(get_db)):
    """Create a new zone with bidirectional exits to existing zones.

    This is the recommended way to dynamically create locations during gameplay.
    It creates:
    - The new zone
    - An exit FROM each connected zone TO the new zone
    - An exit FROM the new zone BACK TO each connected zone

    Example: Creating a "Dark Cave" connected to zone 3 (Dungeon Entrance):
    {
        "name": "Dark Cave",
        "description": "A damp cave with strange glowing moss on the walls.",
        "entry_description": "You enter the dark cave. Water drips from stalactites above.",
        "exits": [{
            "connect_to_zone_id": 3,
            "exit_name": "cave entrance",
            "exit_description": "A dark opening in the rock face.",
            "return_exit_name": "cave exit",
            "return_exit_description": "Light filters in from outside."
        }]
    }
    """
    return service.create_zone_with_exits(db, data)
