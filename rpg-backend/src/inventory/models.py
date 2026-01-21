from sqlalchemy import Column, Integer, String, Float, Boolean, Enum, ForeignKey, JSON
from sqlalchemy.orm import relationship

from ..database import Base
from ..core.enums import ItemType, ItemRarity


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    item_type = Column(Enum(ItemType), nullable=False)
    rarity = Column(Enum(ItemRarity), default=ItemRarity.COMMON)
    weight = Column(Float, default=0.0)
    value = Column(Integer, default=0)  # Gold value
    stackable = Column(Boolean, default=False)
    max_stack = Column(Integer, default=1)

    # JSON field for type-specific properties
    # e.g., {"damage_dice": "1d8", "damage_type": "slashing"} for weapons
    # e.g., {"armor_bonus": 2, "slot": "chest"} for armor
    properties = Column(JSON, default=dict)

    # Items can be on the ground at a location
    ground_x = Column(Integer, nullable=True)
    ground_y = Column(Integer, nullable=True)
    ground_zone_id = Column(Integer, ForeignKey("zones.id"), nullable=True)

    inventory_items = relationship("InventoryItem", back_populates="item")


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    quantity = Column(Integer, default=1)
    equipped = Column(Boolean, default=False)
    equipment_slot = Column(String(50), nullable=True)  # e.g., "main_hand", "chest", "head"

    character = relationship("Character", back_populates="inventory_items")
    item = relationship("Item", back_populates="inventory_items")
