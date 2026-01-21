from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from ..database import Base


class Scenario(Base):
    """
    A scenario is a story event that can be triggered under certain conditions.

    Triggers define when the scenario activates (e.g., location, item possession, quest state).
    Outcomes define what happens when the scenario is resolved.
    """
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(String(1000), nullable=True)
    narrative_text = Column(String(5000), nullable=True)  # Story text shown to players

    # Triggers - conditions for activation
    # Example: {"type": "location", "zone_id": 1, "x": 5, "y": 5}
    # Example: {"type": "item", "item_id": 10}
    # Example: {"type": "quest", "quest_id": 5, "status": "completed"}
    # Example: {"type": "health_threshold", "threshold": 0.25, "comparison": "below"}
    triggers = Column(JSON, default=list)  # List of trigger conditions

    # Outcomes - possible results with effects
    # Each outcome: {
    #   "description": str,
    #   "effect_type": "help" | "hurt" | "neutral",
    #   "health_change": int (optional),
    #   "attribute_modifiers": {"strength": 1, ...} (optional),
    #   "items_granted": [item_ids] (optional),
    #   "items_removed": [item_ids] (optional),
    #   "trigger_quest_id": int (optional),
    #   "weight": int (for random selection, default 1)
    # }
    outcomes = Column(JSON, default=list)

    # Repeatable settings
    repeatable = Column(Boolean, default=False)
    cooldown_seconds = Column(Integer, nullable=True)  # Cooldown between triggers

    # History tracking
    history = relationship("ScenarioHistory", back_populates="scenario", cascade="all, delete-orphan")


class ScenarioHistory(Base):
    """Tracks when scenarios were triggered for each character."""
    __tablename__ = "scenario_history"

    id = Column(Integer, primary_key=True, index=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=False)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    triggered_at = Column(DateTime, default=datetime.utcnow)
    outcome_index = Column(Integer, nullable=True)  # Which outcome was applied
    outcome_data = Column(JSON, default=dict)  # Snapshot of what was applied

    scenario = relationship("Scenario", back_populates="history")
    character = relationship("Character", back_populates="scenario_history")
