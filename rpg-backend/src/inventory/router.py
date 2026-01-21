from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from . import service
from .schemas import (
    ItemCreate,
    ItemUpdate,
    ItemResponse,
    InventoryItemResponse,
    AddToInventoryRequest,
    EquipItemRequest,
)

router = APIRouter(tags=["inventory"])

# Item CRUD routes
items_router = APIRouter(prefix="/items", tags=["items"])


@items_router.post("/", response_model=ItemResponse, status_code=201)
def create_item(item: ItemCreate, db: Session = Depends(get_db)):
    """Create a new item definition."""
    return service.create_item(db, item)


@items_router.get("/", response_model=list[ItemResponse])
def list_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    item_type: str | None = None,
    rarity: str | None = None,
    db: Session = Depends(get_db),
):
    """List all item definitions."""
    return service.get_items(db, skip, limit, item_type, rarity)


@items_router.get("/{item_id}", response_model=ItemResponse)
def get_item(item_id: int, db: Session = Depends(get_db)):
    """Get an item definition by ID."""
    return service.get_item(db, item_id)


@items_router.put("/{item_id}", response_model=ItemResponse)
def update_item(item_id: int, item: ItemUpdate, db: Session = Depends(get_db)):
    """Update an item definition."""
    return service.update_item(db, item_id, item)


@items_router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    """Delete an item definition."""
    service.delete_item(db, item_id)


# Character inventory routes (mounted on character router)
inventory_router = APIRouter()


@inventory_router.get("/{character_id}/inventory", response_model=list[InventoryItemResponse])
def get_inventory(character_id: int, db: Session = Depends(get_db)):
    """Get a character's inventory."""
    return service.get_inventory(db, character_id)


@inventory_router.post("/{character_id}/inventory", response_model=InventoryItemResponse, status_code=201)
def add_to_inventory(character_id: int, request: AddToInventoryRequest, db: Session = Depends(get_db)):
    """Add an item to a character's inventory."""
    return service.add_to_inventory(db, character_id, request)


@inventory_router.delete("/{character_id}/inventory/{inventory_item_id}", status_code=204)
def remove_from_inventory(
    character_id: int,
    inventory_item_id: int,
    quantity: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    """Remove an item from a character's inventory."""
    service.remove_from_inventory(db, character_id, inventory_item_id, quantity)


@inventory_router.post("/{character_id}/inventory/{inventory_item_id}/equip", response_model=InventoryItemResponse)
def equip_item(
    character_id: int,
    inventory_item_id: int,
    request: EquipItemRequest,
    db: Session = Depends(get_db),
):
    """Equip an item from inventory."""
    return service.equip_item(db, character_id, inventory_item_id, request.equipment_slot)


@inventory_router.post("/{character_id}/inventory/{inventory_item_id}/unequip", response_model=InventoryItemResponse)
def unequip_item(character_id: int, inventory_item_id: int, db: Session = Depends(get_db)):
    """Unequip an item."""
    return service.unequip_item(db, character_id, inventory_item_id)


# Combine into main router
router.include_router(items_router)
