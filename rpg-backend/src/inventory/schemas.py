from pydantic import BaseModel, Field
from typing import Any

from ..core.enums import ItemType, ItemRarity


class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    item_type: ItemType
    rarity: ItemRarity = ItemRarity.COMMON
    weight: float = Field(default=0.0, ge=0)
    value: int = Field(default=0, ge=0)
    stackable: bool = False
    max_stack: int = Field(default=1, ge=1)
    properties: dict[str, Any] = Field(default_factory=dict)


class ItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    item_type: ItemType | None = None
    rarity: ItemRarity | None = None
    weight: float | None = Field(default=None, ge=0)
    value: int | None = Field(default=None, ge=0)
    stackable: bool | None = None
    max_stack: int | None = Field(default=None, ge=1)
    properties: dict[str, Any] | None = None


class ItemResponse(BaseModel):
    id: int
    name: str
    description: str | None
    item_type: ItemType
    rarity: ItemRarity
    weight: float
    value: int
    stackable: bool
    max_stack: int
    properties: dict[str, Any]
    ground_x: int | None
    ground_y: int | None
    ground_zone_id: int | None

    class Config:
        from_attributes = True


class InventoryItemResponse(BaseModel):
    id: int
    item_id: int
    quantity: int
    equipped: bool
    equipment_slot: str | None
    item: ItemResponse

    class Config:
        from_attributes = True


class AddToInventoryRequest(BaseModel):
    item_id: int
    quantity: int = Field(default=1, ge=1)
    equipped: bool = False
    equipment_slot: str | None = None


class EquipItemRequest(BaseModel):
    equipment_slot: str = Field(..., min_length=1, max_length=50)
