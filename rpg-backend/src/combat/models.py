from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey, JSON
from sqlalchemy.orm import relationship

from ..database import Base
from ..core.enums import CombatStatus, ActionType, InitiativeType


class CombatSession(Base):
    __tablename__ = "combat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(Enum(CombatStatus), default=CombatStatus.INITIALIZING)
    current_turn = Column(Integer, default=0)
    round_number = Column(Integer, default=1)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

    # Winner info (set when combat ends)
    winner_team_id = Column(Integer, nullable=True)

    # Zone where combat takes place
    zone_id = Column(Integer, nullable=True)

    # Initiative type for this combat
    initiative_type = Column(Enum(InitiativeType), default=InitiativeType.INDIVIDUAL)

    # Relationships
    combatants = relationship("Combatant", back_populates="session", cascade="all, delete-orphan")
    actions = relationship("CombatAction", back_populates="session", cascade="all, delete-orphan")


class Combatant(Base):
    __tablename__ = "combatants"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("combat_sessions.id"), nullable=False)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    team_id = Column(Integer, nullable=False)
    is_player = Column(Boolean, default=False)

    # Combat stats (snapshot from character at combat start)
    name = Column(String(100), nullable=False)
    initiative = Column(Integer, default=0)
    current_hp = Column(Integer, nullable=False)
    max_hp = Column(Integer, nullable=False)
    armor_class = Column(Integer, default=10)

    # Threat and targeting
    threat = Column(Integer, default=0)

    # Turn tracking
    turn_order = Column(Integer, default=0)
    turn_count = Column(Integer, default=0)

    # Status
    is_alive = Column(Boolean, default=True)
    can_act = Column(Boolean, default=True)
    status_effects = Column(JSON, default=dict)  # {"defending": 1, "poisoned": 3} - effect_id: remaining_duration

    session = relationship("CombatSession", back_populates="combatants")


class CombatAction(Base):
    __tablename__ = "combat_actions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("combat_sessions.id"), nullable=False)
    round_number = Column(Integer, nullable=False)
    turn_number = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Actor and target
    actor_combatant_id = Column(Integer, ForeignKey("combatants.id"), nullable=False)
    target_combatant_id = Column(Integer, ForeignKey("combatants.id"), nullable=True)

    # Action details
    action_type = Column(Enum(ActionType), nullable=False)
    ability_id = Column(Integer, nullable=True)
    item_id = Column(Integer, nullable=True)

    # Results
    roll = Column(Integer, nullable=True)  # d20 roll
    total = Column(Integer, nullable=True)  # Roll + modifiers
    damage = Column(Integer, nullable=True)
    healing = Column(Integer, nullable=True)
    hit = Column(Boolean, nullable=True)
    critical = Column(Boolean, default=False)
    description = Column(String(500), nullable=True)

    session = relationship("CombatSession", back_populates="actions")
