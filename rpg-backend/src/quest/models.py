from sqlalchemy import Column, Integer, String, Boolean, Enum, ForeignKey, JSON
from sqlalchemy.orm import relationship

from ..database import Base
from ..core.enums import QuestStatus


class Quest(Base):
    __tablename__ = "quests"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(String(2000), nullable=True)
    level_requirement = Column(Integer, default=1)

    # Rewards
    experience_reward = Column(Integer, default=0)
    gold_reward = Column(Integer, default=0)
    item_rewards = Column(JSON, default=list)  # List of item IDs

    # Prerequisites - list of quest IDs that must be completed first
    prerequisites = Column(JSON, default=list)

    # Relationships
    objectives = relationship("QuestObjective", back_populates="quest", cascade="all, delete-orphan")
    assignments = relationship("QuestAssignment", back_populates="quest", cascade="all, delete-orphan")


class QuestObjective(Base):
    __tablename__ = "quest_objectives"

    id = Column(Integer, primary_key=True, index=True)
    quest_id = Column(Integer, ForeignKey("quests.id"), nullable=False)
    description = Column(String(500), nullable=False)
    target_count = Column(Integer, default=1)
    order = Column(Integer, default=0)  # For ordering objectives

    # Objective type and target for automatic completion
    # Types: "talk_to", "reach_location", "win_combat", "collect_item", "generic"
    objective_type = Column(String(50), default="generic")
    # Target identifier (NPC name, zone_id, item_id, enemy type, etc.)
    target_identifier = Column(String(200), nullable=True)

    quest = relationship("Quest", back_populates="objectives")


class QuestAssignment(Base):
    __tablename__ = "quest_assignments"

    id = Column(Integer, primary_key=True, index=True)
    quest_id = Column(Integer, ForeignKey("quests.id"), nullable=False)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    status = Column(Enum(QuestStatus), default=QuestStatus.ACTIVE)

    # Track progress for each objective: {objective_id: current_count}
    objective_progress = Column(JSON, default=dict)

    quest = relationship("Quest", back_populates="assignments")
    character = relationship("Character", back_populates="quest_assignments")
