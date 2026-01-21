from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, JSON, ForeignKey

from ..database import Base
from ..core.enums import EventType


class GameEvent(Base):
    __tablename__ = "game_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(Enum(EventType), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Related entities (optional)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=True, index=True)
    target_character_id = Column(Integer, nullable=True)
    item_id = Column(Integer, nullable=True)
    quest_id = Column(Integer, nullable=True)
    scenario_id = Column(Integer, nullable=True)
    combat_session_id = Column(Integer, nullable=True)
    zone_id = Column(Integer, nullable=True)

    # Location when event occurred
    x = Column(Integer, nullable=True)
    y = Column(Integer, nullable=True)

    # Description and additional data
    description = Column(String(500), nullable=True)
    data = Column(JSON, default=dict)  # Flexible storage for event-specific data
