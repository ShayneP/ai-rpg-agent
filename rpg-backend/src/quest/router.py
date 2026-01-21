from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..core.enums import QuestStatus
from . import service
from .schemas import (
    QuestCreate,
    QuestUpdate,
    QuestResponse,
    QuestAssignRequest,
    QuestAssignmentResponse,
    ProgressUpdate,
)

router = APIRouter(prefix="/quests", tags=["quests"])


@router.post("/", response_model=QuestResponse, status_code=201)
def create_quest(quest: QuestCreate, db: Session = Depends(get_db)):
    """Create a new quest with objectives."""
    return service.create_quest(db, quest)


@router.get("/", response_model=list[QuestResponse])
def list_quests(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    min_level: int | None = None,
    max_level: int | None = None,
    db: Session = Depends(get_db),
):
    """List all quests with optional level filtering."""
    return service.get_quests(db, skip, limit, min_level, max_level)


@router.get("/{quest_id}", response_model=QuestResponse)
def get_quest(quest_id: int, db: Session = Depends(get_db)):
    """Get a quest by ID."""
    return service.get_quest(db, quest_id)


@router.put("/{quest_id}", response_model=QuestResponse)
def update_quest(quest_id: int, quest: QuestUpdate, db: Session = Depends(get_db)):
    """Update a quest."""
    return service.update_quest(db, quest_id, quest)


@router.delete("/{quest_id}", status_code=204)
def delete_quest(quest_id: int, db: Session = Depends(get_db)):
    """Delete a quest."""
    service.delete_quest(db, quest_id)


@router.post("/{quest_id}/assign", response_model=QuestAssignmentResponse)
def assign_quest(quest_id: int, request: QuestAssignRequest, db: Session = Depends(get_db)):
    """Assign a quest to a character."""
    assignment = service.assign_quest(db, quest_id, request.character_id)
    return service.get_assignment_with_progress(db, assignment)


@router.post("/{quest_id}/progress", response_model=QuestAssignmentResponse)
def update_progress(
    quest_id: int,
    update: ProgressUpdate,
    character_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Update progress on a quest objective."""
    assignment = service.update_progress(db, quest_id, character_id, update)
    return service.get_assignment_with_progress(db, assignment)


@router.post("/{quest_id}/complete", response_model=QuestAssignmentResponse)
def complete_quest(quest_id: int, character_id: int = Query(...), db: Session = Depends(get_db)):
    """Mark a quest as complete (requires all objectives to be done)."""
    assignment = service.complete_quest(db, quest_id, character_id)
    return service.get_assignment_with_progress(db, assignment)


@router.post("/{quest_id}/abandon", response_model=QuestAssignmentResponse)
def abandon_quest(quest_id: int, character_id: int = Query(...), db: Session = Depends(get_db)):
    """Abandon a quest."""
    assignment = service.abandon_quest(db, quest_id, character_id)
    return service.get_assignment_with_progress(db, assignment)


# Character quest routes
@router.get("/character/{character_id}", response_model=list[QuestAssignmentResponse])
def get_character_quests(
    character_id: int,
    status: QuestStatus | None = None,
    db: Session = Depends(get_db),
):
    """Get all quests assigned to a character."""
    assignments = service.get_character_quests(db, character_id, status)
    return [service.get_assignment_with_progress(db, a) for a in assignments]
