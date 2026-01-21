from sqlalchemy import Column, Integer, String, Boolean, Enum, ForeignKey
from sqlalchemy.orm import relationship

from ..database import Base
from ..core.enums import TerrainType


class Zone(Base):
    __tablename__ = "zones"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    entry_description = Column(String(1000), nullable=True)  # What player sees on arrival
    width = Column(Integer, nullable=False, default=1)  # Grid width (default 1 for simple zones)
    height = Column(Integer, nullable=False, default=1)  # Grid height (default 1 for simple zones)

    # Relationships
    grid_cells = relationship("GridCell", back_populates="zone", cascade="all, delete-orphan")
    characters = relationship("Character", backref="zone")
    exits_from = relationship(
        "Exit",
        foreign_keys="Exit.from_zone_id",
        back_populates="from_zone",
        cascade="all, delete-orphan",
    )
    exits_to = relationship(
        "Exit",
        foreign_keys="Exit.to_zone_id",
        back_populates="to_zone",
    )


class GridCell(Base):
    __tablename__ = "grid_cells"

    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=False)
    x = Column(Integer, nullable=False)
    y = Column(Integer, nullable=False)
    terrain_type = Column(Enum(TerrainType), default=TerrainType.GRASS)
    passable = Column(Boolean, default=True)
    description = Column(String(200), nullable=True)

    zone = relationship("Zone", back_populates="grid_cells")


class Exit(Base):
    """
    An exit connects two zones with a descriptive name.

    Exits are one-way: to create a two-way connection, create two Exit records.
    This allows for asymmetric exits (e.g., a one-way trap door).
    """
    __tablename__ = "exits"

    id = Column(Integer, primary_key=True, index=True)
    from_zone_id = Column(Integer, ForeignKey("zones.id"), nullable=False)
    to_zone_id = Column(Integer, ForeignKey("zones.id"), nullable=False)
    name = Column(String(100), nullable=False)  # "tavern door", "dark stairwell"
    description = Column(String(500), nullable=True)  # "A wooden door leads to..."
    hidden = Column(Boolean, default=False)  # Requires perception check to discover
    locked = Column(Boolean, default=False)  # Requires key or skill to open
    key_item_id = Column(Integer, ForeignKey("items.id"), nullable=True)  # Item that unlocks this exit

    # Relationships
    from_zone = relationship("Zone", foreign_keys=[from_zone_id], back_populates="exits_from")
    to_zone = relationship("Zone", foreign_keys=[to_zone_id], back_populates="exits_to")
    key_item = relationship("Item", foreign_keys=[key_item_id])
