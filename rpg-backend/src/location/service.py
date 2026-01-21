from sqlalchemy.orm import Session
from sqlalchemy import and_

from .models import Zone, GridCell, Exit
from .schemas import (
    ZoneCreate,
    ZoneUpdate,
    GridCellCreate,
    GridCellUpdate,
    SurroundingsRequest,
    ExitCreate,
    ExitUpdate,
    ExitWithDestinationResponse,
    TravelResponse,
    UnlockResponse,
    ZoneCreateWithExits,
    ZoneCreateWithExitsResponse,
    ZoneResponse,
    ExitResponse,
)
from ..core.exceptions import NotFoundError, ValidationError
from ..character.models import Character
from ..inventory.models import Item, InventoryItem


def get_zone(db: Session, zone_id: int) -> Zone:
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise NotFoundError("Zone", zone_id)
    return zone


def get_zones(db: Session, skip: int = 0, limit: int = 100) -> list[Zone]:
    return db.query(Zone).offset(skip).limit(limit).all()


def create_zone(db: Session, zone_data: ZoneCreate) -> Zone:
    zone = Zone(**zone_data.model_dump())
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


def update_zone(db: Session, zone_id: int, zone_data: ZoneUpdate) -> Zone:
    zone = get_zone(db, zone_id)
    update_data = zone_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(zone, field, value)
    db.commit()
    db.refresh(zone)
    return zone


def delete_zone(db: Session, zone_id: int) -> None:
    zone = get_zone(db, zone_id)
    db.delete(zone)
    db.commit()


# Grid Cell operations
def get_grid_cell(db: Session, zone_id: int, x: int, y: int) -> GridCell | None:
    return db.query(GridCell).filter(
        GridCell.zone_id == zone_id,
        GridCell.x == x,
        GridCell.y == y,
    ).first()


def create_grid_cell(db: Session, zone_id: int, cell_data: GridCellCreate) -> GridCell:
    zone = get_zone(db, zone_id)

    if cell_data.x >= zone.width or cell_data.y >= zone.height:
        raise ValidationError(f"Cell position ({cell_data.x}, {cell_data.y}) is outside zone bounds")

    existing = get_grid_cell(db, zone_id, cell_data.x, cell_data.y)
    if existing:
        raise ValidationError(f"Grid cell at ({cell_data.x}, {cell_data.y}) already exists")

    cell = GridCell(zone_id=zone_id, **cell_data.model_dump())
    db.add(cell)
    db.commit()
    db.refresh(cell)
    return cell


def update_grid_cell(db: Session, zone_id: int, x: int, y: int, cell_data: GridCellUpdate) -> GridCell:
    cell = get_grid_cell(db, zone_id, x, y)
    if not cell:
        raise NotFoundError("GridCell", f"({x}, {y})")

    update_data = cell_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cell, field, value)
    db.commit()
    db.refresh(cell)
    return cell


def get_zone_cells(db: Session, zone_id: int) -> list[GridCell]:
    get_zone(db, zone_id)  # Ensure zone exists
    return db.query(GridCell).filter(GridCell.zone_id == zone_id).all()


# Spatial queries
def get_characters_at_location(
    db: Session,
    zone_id: int,
    x: int | None = None,
    y: int | None = None,
    radius: int | None = None,
) -> list[Character]:
    query = db.query(Character).filter(Character.zone_id == zone_id)

    if x is not None and y is not None:
        if radius is not None and radius > 0:
            # Get characters within radius (manhattan distance for simplicity)
            query = query.filter(
                and_(
                    Character.x >= x - radius,
                    Character.x <= x + radius,
                    Character.y >= y - radius,
                    Character.y <= y + radius,
                )
            )
        else:
            query = query.filter(Character.x == x, Character.y == y)

    return query.all()


def get_items_at_location(
    db: Session,
    zone_id: int,
    x: int | None = None,
    y: int | None = None,
    radius: int | None = None,
) -> list[Item]:
    query = db.query(Item).filter(Item.ground_zone_id == zone_id)

    if x is not None and y is not None:
        if radius is not None and radius > 0:
            query = query.filter(
                and_(
                    Item.ground_x >= x - radius,
                    Item.ground_x <= x + radius,
                    Item.ground_y >= y - radius,
                    Item.ground_y <= y + radius,
                )
            )
        else:
            query = query.filter(Item.ground_x == x, Item.ground_y == y)

    return query.all()


def get_surroundings(db: Session, request: SurroundingsRequest) -> dict:
    zone = get_zone(db, request.zone_id)

    # Get cells in radius
    cells = db.query(GridCell).filter(
        GridCell.zone_id == request.zone_id,
        GridCell.x >= request.x - request.radius,
        GridCell.x <= request.x + request.radius,
        GridCell.y >= request.y - request.radius,
        GridCell.y <= request.y + request.radius,
    ).all()

    # Get characters in radius
    characters = get_characters_at_location(db, request.zone_id, request.x, request.y, request.radius)

    # Get items in radius
    items = get_items_at_location(db, request.zone_id, request.x, request.y, request.radius)

    return {
        "center_x": request.x,
        "center_y": request.y,
        "zone_id": request.zone_id,
        "cells": cells,
        "characters": characters,
        "items": items,
    }


# Exit operations
def get_exit(db: Session, exit_id: int) -> Exit:
    exit_obj = db.query(Exit).filter(Exit.id == exit_id).first()
    if not exit_obj:
        raise NotFoundError("Exit", exit_id)
    return exit_obj


def get_exits_from_zone(db: Session, zone_id: int, include_hidden: bool = False) -> list[Exit]:
    """Get all exits from a zone."""
    get_zone(db, zone_id)  # Ensure zone exists
    query = db.query(Exit).filter(Exit.from_zone_id == zone_id)
    if not include_hidden:
        query = query.filter(Exit.hidden == False)
    return query.all()


def get_exits_with_destinations(db: Session, zone_id: int, include_hidden: bool = False) -> list[ExitWithDestinationResponse]:
    """Get exits with destination zone info for navigation display."""
    exits = get_exits_from_zone(db, zone_id, include_hidden)
    result = []
    for exit_obj in exits:
        dest_zone = get_zone(db, exit_obj.to_zone_id)
        result.append(ExitWithDestinationResponse(
            id=exit_obj.id,
            from_zone_id=exit_obj.from_zone_id,
            to_zone_id=exit_obj.to_zone_id,
            name=exit_obj.name,
            description=exit_obj.description,
            hidden=exit_obj.hidden,
            locked=exit_obj.locked,
            key_item_id=exit_obj.key_item_id,
            to_zone_name=dest_zone.name,
            to_zone_entry_description=dest_zone.entry_description,
        ))
    return result


def create_exit(db: Session, exit_data: ExitCreate) -> Exit:
    """Create a new exit between zones."""
    # Validate both zones exist
    get_zone(db, exit_data.from_zone_id)
    get_zone(db, exit_data.to_zone_id)

    exit_obj = Exit(**exit_data.model_dump())
    db.add(exit_obj)
    db.commit()
    db.refresh(exit_obj)
    return exit_obj


def update_exit(db: Session, exit_id: int, exit_data: ExitUpdate) -> Exit:
    """Update an exit."""
    exit_obj = get_exit(db, exit_id)
    update_data = exit_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(exit_obj, field, value)
    db.commit()
    db.refresh(exit_obj)
    return exit_obj


def delete_exit(db: Session, exit_id: int) -> None:
    """Delete an exit."""
    exit_obj = get_exit(db, exit_id)
    db.delete(exit_obj)
    db.commit()


def travel_through_exit(db: Session, exit_id: int, character_id: int) -> TravelResponse:
    """
    Move a character through an exit to the destination zone.

    Returns success status, the new zone, and available exits from there.
    """
    exit_obj = get_exit(db, exit_id)

    # Get the character
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        raise NotFoundError("Character", character_id)

    # Check if character is in the right zone
    if character.zone_id != exit_obj.from_zone_id:
        return TravelResponse(
            success=False,
            message=f"You are not at the {exit_obj.name}.",
            new_zone=None,
            exits=[],
        )

    # Check if exit is locked
    if exit_obj.locked:
        return TravelResponse(
            success=False,
            message=f"The {exit_obj.name} is locked.",
            new_zone=None,
            exits=[],
        )

    # Move the character
    dest_zone = get_zone(db, exit_obj.to_zone_id)
    character.zone_id = dest_zone.id
    character.x = 0  # Reset position in new zone
    character.y = 0
    db.commit()
    db.refresh(character)

    # Get exits from new zone
    new_exits = get_exits_with_destinations(db, dest_zone.id)

    return TravelResponse(
        success=True,
        message=dest_zone.entry_description or f"You arrive at {dest_zone.name}.",
        new_zone=dest_zone,
        exits=new_exits,
    )


def unlock_exit(db: Session, exit_id: int, character_id: int, item_id: int | None = None) -> UnlockResponse:
    """
    Attempt to unlock an exit.

    If the exit requires a key, the character must have the key item in inventory.
    """
    exit_obj = get_exit(db, exit_id)

    if not exit_obj.locked:
        return UnlockResponse(success=True, message=f"The {exit_obj.name} is already unlocked.")

    # Get the character
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        raise NotFoundError("Character", character_id)

    # Check if exit requires a specific key
    if exit_obj.key_item_id:
        # Check if character has the key
        has_key = db.query(InventoryItem).filter(
            InventoryItem.character_id == character_id,
            InventoryItem.item_id == exit_obj.key_item_id,
            InventoryItem.quantity > 0,
        ).first()

        if not has_key:
            key_item = db.query(Item).filter(Item.id == exit_obj.key_item_id).first()
            key_name = key_item.name if key_item else "a key"
            return UnlockResponse(
                success=False,
                message=f"The {exit_obj.name} requires {key_name} to unlock.",
            )

    # Unlock the exit
    exit_obj.locked = False
    db.commit()

    return UnlockResponse(success=True, message=f"You unlock the {exit_obj.name}.")


def create_zone_with_exits(db: Session, data: ZoneCreateWithExits) -> ZoneCreateWithExitsResponse:
    """
    Create a new zone with bidirectional exits to existing zones.

    This creates the zone and automatically creates both:
    - An exit FROM the connected zone TO the new zone
    - An exit FROM the new zone BACK TO the connected zone

    This is the recommended way for the agent to create new locations dynamically.
    """
    # Validate all connected zones exist first
    for exit_conn in data.exits:
        get_zone(db, exit_conn.connect_to_zone_id)

    # Create the new zone
    zone = Zone(
        name=data.name,
        description=data.description,
        entry_description=data.entry_description,
        width=1,
        height=1,
    )
    db.add(zone)
    db.flush()  # Get the zone ID

    exits_created = []

    # Create bidirectional exits
    for exit_conn in data.exits:
        # Exit FROM connected zone TO new zone
        exit_to_new = Exit(
            from_zone_id=exit_conn.connect_to_zone_id,
            to_zone_id=zone.id,
            name=exit_conn.exit_name,
            description=exit_conn.exit_description,
            hidden=exit_conn.hidden,
            locked=exit_conn.locked,
        )
        db.add(exit_to_new)

        # Exit FROM new zone BACK TO connected zone
        exit_back = Exit(
            from_zone_id=zone.id,
            to_zone_id=exit_conn.connect_to_zone_id,
            name=exit_conn.return_exit_name,
            description=exit_conn.return_exit_description,
            hidden=False,  # Return exits are never hidden
            locked=False,  # Return exits are never locked
        )
        db.add(exit_back)
        db.flush()

        exits_created.append(ExitResponse(
            id=exit_to_new.id,
            from_zone_id=exit_to_new.from_zone_id,
            to_zone_id=exit_to_new.to_zone_id,
            name=exit_to_new.name,
            description=exit_to_new.description,
            hidden=exit_to_new.hidden,
            locked=exit_to_new.locked,
            key_item_id=exit_to_new.key_item_id,
        ))
        exits_created.append(ExitResponse(
            id=exit_back.id,
            from_zone_id=exit_back.from_zone_id,
            to_zone_id=exit_back.to_zone_id,
            name=exit_back.name,
            description=exit_back.description,
            hidden=exit_back.hidden,
            locked=exit_back.locked,
            key_item_id=exit_back.key_item_id,
        ))

    db.commit()
    db.refresh(zone)

    return ZoneCreateWithExitsResponse(
        zone=ZoneResponse(
            id=zone.id,
            name=zone.name,
            description=zone.description,
            entry_description=zone.entry_description,
            width=zone.width,
            height=zone.height,
        ),
        exits_created=exits_created,
    )
