from sqlalchemy.orm import Session

from .models import Quest, QuestObjective, QuestAssignment
from .schemas import QuestCreate, QuestUpdate, ProgressUpdate
from ..core.enums import QuestStatus
from ..core.exceptions import NotFoundError, ValidationError
from ..character.service import get_character


def get_quest(db: Session, quest_id: int) -> Quest:
    quest = db.query(Quest).filter(Quest.id == quest_id).first()
    if not quest:
        raise NotFoundError("Quest", quest_id)
    return quest


def get_quests(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    min_level: int | None = None,
    max_level: int | None = None,
) -> list[Quest]:
    query = db.query(Quest)
    if min_level is not None:
        query = query.filter(Quest.level_requirement >= min_level)
    if max_level is not None:
        query = query.filter(Quest.level_requirement <= max_level)
    return query.offset(skip).limit(limit).all()


def create_quest(db: Session, quest_data: QuestCreate) -> Quest:
    # Create quest without objectives first
    quest = Quest(
        title=quest_data.title,
        description=quest_data.description,
        level_requirement=quest_data.level_requirement,
        experience_reward=quest_data.experience_reward,
        gold_reward=quest_data.gold_reward,
        item_rewards=quest_data.item_rewards,
        prerequisites=quest_data.prerequisites,
    )
    db.add(quest)
    db.flush()  # Get the quest ID

    # Create objectives
    for obj_data in quest_data.objectives:
        objective = QuestObjective(
            quest_id=quest.id,
            description=obj_data.description,
            target_count=obj_data.target_count,
            order=obj_data.order,
            objective_type=obj_data.objective_type,
            target_identifier=obj_data.target_identifier,
        )
        db.add(objective)

    db.commit()
    db.refresh(quest)
    return quest


def update_quest(db: Session, quest_id: int, quest_data: QuestUpdate) -> Quest:
    quest = get_quest(db, quest_id)
    update_data = quest_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(quest, field, value)
    db.commit()
    db.refresh(quest)
    return quest


def delete_quest(db: Session, quest_id: int) -> None:
    quest = get_quest(db, quest_id)
    db.delete(quest)
    db.commit()


def add_objective(db: Session, quest_id: int, description: str, target_count: int = 1, order: int = 0) -> QuestObjective:
    get_quest(db, quest_id)  # Ensure quest exists
    objective = QuestObjective(
        quest_id=quest_id,
        description=description,
        target_count=target_count,
        order=order,
    )
    db.add(objective)
    db.commit()
    db.refresh(objective)
    return objective


# Quest Assignment
def get_assignment(db: Session, quest_id: int, character_id: int) -> QuestAssignment | None:
    return db.query(QuestAssignment).filter(
        QuestAssignment.quest_id == quest_id,
        QuestAssignment.character_id == character_id,
    ).first()


def assign_quest(db: Session, quest_id: int, character_id: int) -> QuestAssignment:
    quest = get_quest(db, quest_id)
    character = get_character(db, character_id)

    # Check if already assigned
    existing = get_assignment(db, quest_id, character_id)
    if existing:
        raise ValidationError("Quest is already assigned to this character")

    # Check level requirement
    if character.level < quest.level_requirement:
        raise ValidationError(f"Character level {character.level} is below quest requirement {quest.level_requirement}")

    # Check prerequisites
    for prereq_id in quest.prerequisites:
        prereq_assignment = get_assignment(db, prereq_id, character_id)
        if not prereq_assignment or prereq_assignment.status != QuestStatus.COMPLETED:
            raise ValidationError(f"Prerequisite quest {prereq_id} must be completed first")

    # Create assignment with initial progress
    objective_progress = {str(obj.id): 0 for obj in quest.objectives}

    assignment = QuestAssignment(
        quest_id=quest_id,
        character_id=character_id,
        status=QuestStatus.ACTIVE,
        objective_progress=objective_progress,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def get_character_quests(db: Session, character_id: int, status: QuestStatus | None = None) -> list[QuestAssignment]:
    get_character(db, character_id)  # Ensure character exists
    query = db.query(QuestAssignment).filter(QuestAssignment.character_id == character_id)
    if status:
        query = query.filter(QuestAssignment.status == status)
    return query.all()


def update_progress(db: Session, quest_id: int, character_id: int, update: ProgressUpdate) -> QuestAssignment:
    assignment = get_assignment(db, quest_id, character_id)
    if not assignment:
        raise NotFoundError("QuestAssignment", f"quest={quest_id}, character={character_id}")

    if assignment.status != QuestStatus.ACTIVE:
        raise ValidationError("Cannot update progress on a non-active quest")

    # Find the objective
    quest = get_quest(db, quest_id)
    objective = next((o for o in quest.objectives if o.id == update.objective_id), None)
    if not objective:
        raise NotFoundError("QuestObjective", update.objective_id)

    # Update progress
    progress = dict(assignment.objective_progress)
    obj_id_str = str(update.objective_id)
    current = progress.get(obj_id_str, 0)
    new_progress = min(current + update.amount, objective.target_count)
    progress[obj_id_str] = new_progress
    assignment.objective_progress = progress

    db.commit()
    db.refresh(assignment)
    return assignment


def complete_quest(db: Session, quest_id: int, character_id: int) -> QuestAssignment:
    assignment = get_assignment(db, quest_id, character_id)
    if not assignment:
        raise NotFoundError("QuestAssignment", f"quest={quest_id}, character={character_id}")

    if assignment.status != QuestStatus.ACTIVE:
        raise ValidationError("Quest is not active")

    # Check if all objectives are complete
    quest = get_quest(db, quest_id)
    for objective in quest.objectives:
        current = assignment.objective_progress.get(str(objective.id), 0)
        if current < objective.target_count:
            raise ValidationError(f"Objective '{objective.description}' is not complete")

    assignment.status = QuestStatus.COMPLETED
    db.commit()
    db.refresh(assignment)
    return assignment


def abandon_quest(db: Session, quest_id: int, character_id: int) -> QuestAssignment:
    assignment = get_assignment(db, quest_id, character_id)
    if not assignment:
        raise NotFoundError("QuestAssignment", f"quest={quest_id}, character={character_id}")

    if assignment.status not in [QuestStatus.ACTIVE, QuestStatus.AVAILABLE]:
        raise ValidationError("Cannot abandon a completed or failed quest")

    assignment.status = QuestStatus.ABANDONED
    db.commit()
    db.refresh(assignment)
    return assignment


def get_assignment_with_progress(db: Session, assignment: QuestAssignment) -> dict:
    """Convert assignment to response with detailed objective progress."""
    quest = assignment.quest
    objectives_progress = []

    for objective in sorted(quest.objectives, key=lambda o: o.order):
        current = assignment.objective_progress.get(str(objective.id), 0)
        objectives_progress.append({
            "objective_id": objective.id,
            "description": objective.description,
            "target_count": objective.target_count,
            "current_count": current,
            "completed": current >= objective.target_count,
        })

    return {
        "id": assignment.id,
        "quest_id": assignment.quest_id,
        "character_id": assignment.character_id,
        "status": assignment.status,
        "quest": quest,
        "objectives_progress": objectives_progress,
    }
