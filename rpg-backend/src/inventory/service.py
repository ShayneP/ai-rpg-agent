from sqlalchemy.orm import Session

from .models import Item, InventoryItem
from .schemas import ItemCreate, ItemUpdate, AddToInventoryRequest
from ..core.enums import ItemType
from ..core.exceptions import NotFoundError, InventoryError
from ..character.service import get_character


def get_item(db: Session, item_id: int) -> Item:
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise NotFoundError("Item", item_id)
    return item


def get_items(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    item_type: str | None = None,
    rarity: str | None = None,
) -> list[Item]:
    query = db.query(Item)
    if item_type:
        query = query.filter(Item.item_type == item_type)
    if rarity:
        query = query.filter(Item.rarity == rarity)
    return query.offset(skip).limit(limit).all()


def create_item(db: Session, item_data: ItemCreate) -> Item:
    item = Item(**item_data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_item(db: Session, item_id: int, item_data: ItemUpdate) -> Item:
    item = get_item(db, item_id)
    update_data = item_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, item_id: int) -> None:
    item = get_item(db, item_id)
    db.delete(item)
    db.commit()


# Inventory Management
def get_inventory(db: Session, character_id: int) -> list[InventoryItem]:
    character = get_character(db, character_id)
    return character.inventory_items


def add_to_inventory(db: Session, character_id: int, request: AddToInventoryRequest) -> InventoryItem:
    get_character(db, character_id)  # Ensure character exists
    item = get_item(db, request.item_id)

    # Check if stackable item already exists in inventory
    if item.stackable:
        existing = db.query(InventoryItem).filter(
            InventoryItem.character_id == character_id,
            InventoryItem.item_id == request.item_id,
            InventoryItem.equipped == False,
        ).first()

        if existing:
            new_quantity = existing.quantity + request.quantity
            if new_quantity > item.max_stack:
                raise InventoryError(f"Cannot stack more than {item.max_stack} of this item")
            existing.quantity = new_quantity
            db.commit()
            db.refresh(existing)
            return existing

    # Create new inventory entry
    inventory_item = InventoryItem(
        character_id=character_id,
        item_id=request.item_id,
        quantity=request.quantity,
        equipped=request.equipped,
        equipment_slot=request.equipment_slot,
    )
    db.add(inventory_item)
    db.commit()
    db.refresh(inventory_item)
    return inventory_item


def remove_from_inventory(db: Session, character_id: int, inventory_item_id: int, quantity: int = 1) -> None:
    get_character(db, character_id)  # Ensure character exists

    inventory_item = db.query(InventoryItem).filter(
        InventoryItem.id == inventory_item_id,
        InventoryItem.character_id == character_id,
    ).first()

    if not inventory_item:
        raise NotFoundError("InventoryItem", inventory_item_id)

    if quantity >= inventory_item.quantity:
        db.delete(inventory_item)
    else:
        inventory_item.quantity -= quantity

    db.commit()


def equip_item(db: Session, character_id: int, inventory_item_id: int, slot: str) -> InventoryItem:
    character = get_character(db, character_id)

    inventory_item = db.query(InventoryItem).filter(
        InventoryItem.id == inventory_item_id,
        InventoryItem.character_id == character_id,
    ).first()

    if not inventory_item:
        raise NotFoundError("InventoryItem", inventory_item_id)

    # Find and unequip any item currently in this slot
    currently_equipped = db.query(InventoryItem).filter(
        InventoryItem.character_id == character_id,
        InventoryItem.equipment_slot == slot,
        InventoryItem.equipped == True,
    ).first()

    if currently_equipped:
        # Remove armor bonus from old item if it's armor
        old_item = currently_equipped.item
        if old_item.item_type == ItemType.ARMOR and old_item.properties:
            old_ac_bonus = old_item.properties.get("armor_bonus", 0)
            character.armor_class -= old_ac_bonus
        currently_equipped.equipped = False
        currently_equipped.equipment_slot = None

    # Apply armor bonus from new item if it's armor
    new_item = inventory_item.item
    if new_item.item_type == ItemType.ARMOR and new_item.properties:
        new_ac_bonus = new_item.properties.get("armor_bonus", 0)
        character.armor_class += new_ac_bonus

    inventory_item.equipped = True
    inventory_item.equipment_slot = slot
    db.commit()
    db.refresh(inventory_item)
    return inventory_item


def unequip_item(db: Session, character_id: int, inventory_item_id: int) -> InventoryItem:
    character = get_character(db, character_id)

    inventory_item = db.query(InventoryItem).filter(
        InventoryItem.id == inventory_item_id,
        InventoryItem.character_id == character_id,
    ).first()

    if not inventory_item:
        raise NotFoundError("InventoryItem", inventory_item_id)

    # Remove armor bonus if it's armor
    item = inventory_item.item
    if item.item_type == ItemType.ARMOR and item.properties:
        ac_bonus = item.properties.get("armor_bonus", 0)
        character.armor_class -= ac_bonus

    inventory_item.equipped = False
    inventory_item.equipment_slot = None
    db.commit()
    db.refresh(inventory_item)
    return inventory_item


def place_item_on_ground(db: Session, item_id: int, x: int, y: int, zone_id: int) -> Item:
    item = get_item(db, item_id)
    item.ground_x = x
    item.ground_y = y
    item.ground_zone_id = zone_id
    db.commit()
    db.refresh(item)
    return item


def pickup_item_from_ground(db: Session, item_id: int) -> Item:
    item = get_item(db, item_id)
    item.ground_x = None
    item.ground_y = None
    item.ground_zone_id = None
    db.commit()
    db.refresh(item)
    return item
