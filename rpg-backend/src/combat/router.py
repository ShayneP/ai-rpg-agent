from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from . import service
from .schemas import (
    CombatStartRequest,
    CombatStartResponse,
    CombatStateResponse,
    PlayerActionRequest,
    ActionResult,
    ProcessTurnResponse,
    ResolveResponse,
    CombatSummary,
    CombatHistoryResponse,
    ActionResultResponse,
    CombatantResponse,
)

router = APIRouter(prefix="/combat", tags=["combat"])


@router.post("/start", response_model=CombatStartResponse, status_code=201)
def start_combat(request: CombatStartRequest, db: Session = Depends(get_db)):
    """Initialize combat with participants and calculate initiative."""
    session = service.start_combat(db, request)
    turn_order = [c.id for c in sorted(session.combatants, key=lambda c: c.turn_order)]
    return {
        "id": session.id,
        "status": session.status,
        "round_number": session.round_number,
        "current_turn": session.current_turn,
        "combatants": session.combatants,
        "turn_order": turn_order,
    }


@router.get("/{session_id}", response_model=CombatStateResponse)
def get_combat_state(session_id: int, db: Session = Depends(get_db)):
    """Get the current state of a combat session."""
    session = service.get_combat_session(db, session_id)
    current = service.get_current_combatant(session)
    awaiting = current if session.status.value == "awaiting_player" and current and current.is_player else None

    return {
        "id": session.id,
        "status": session.status,
        "round_number": session.round_number,
        "current_turn": session.current_turn,
        "combatants": session.combatants,
        "current_combatant": current,
        "awaiting_player": awaiting,
    }


@router.post("/{session_id}/process", response_model=ProcessTurnResponse)
def process_turns(session_id: int, db: Session = Depends(get_db)):
    """Process NPC turns until a player needs to act or combat ends."""
    result = service.process_turns(db, session_id)
    return {
        "actions_taken": result["actions_taken"],
        "combatants": result["combatants"],
        "status": result["status"],
        "round_number": result["round_number"],
        "current_turn": result["current_turn"],
        "awaiting_player": result["awaiting_player"],
        "combat_ended": result["combat_ended"],
    }


@router.post("/{session_id}/act", response_model=ActionResult)
def player_action(session_id: int, request: PlayerActionRequest, db: Session = Depends(get_db)):
    """Submit a player's action."""
    result = service.player_action(db, session_id, request)
    return {
        "action": result["action"],
        "combatants": result["combatants"],
        "status": result["status"],
        "combat_ended": result.get("combat_ended", False),
    }


@router.post("/{session_id}/resolve", response_model=ResolveResponse)
def resolve_combat(session_id: int, db: Session = Depends(get_db)):
    """Calculate final outcomes (rewards, experience)."""
    return service.resolve_combat(db, session_id)


@router.post("/{session_id}/finish", response_model=CombatSummary)
def finish_combat(session_id: int, db: Session = Depends(get_db)):
    """End combat and return summary."""
    return service.finish_combat(db, session_id)


@router.get("/{session_id}/history", response_model=CombatHistoryResponse)
def get_combat_history(session_id: int, db: Session = Depends(get_db)):
    """Get the action history for a combat session."""
    actions = service.get_combat_history(db, session_id)
    return {
        "session_id": session_id,
        "actions": actions,
    }
