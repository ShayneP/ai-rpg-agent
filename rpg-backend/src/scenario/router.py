from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from . import service
from .schemas import (
    ScenarioCreate,
    ScenarioUpdate,
    ScenarioResponse,
    TriggerScenarioRequest,
    TriggerScenarioResponse,
    ScenarioHistoryResponse,
)

router = APIRouter(prefix="/scenario", tags=["scenario"])


@router.post("/", response_model=ScenarioResponse, status_code=201)
def create_scenario(scenario: ScenarioCreate, db: Session = Depends(get_db)):
    """Create a new scenario."""
    return service.create_scenario(db, scenario)


@router.get("/", response_model=list[ScenarioResponse])
def list_scenarios(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """List all scenarios."""
    return service.get_scenarios(db, skip, limit)


@router.get("/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(scenario_id: int, db: Session = Depends(get_db)):
    """Get a scenario by ID."""
    return service.get_scenario(db, scenario_id)


@router.put("/{scenario_id}", response_model=ScenarioResponse)
def update_scenario(scenario_id: int, scenario: ScenarioUpdate, db: Session = Depends(get_db)):
    """Update a scenario."""
    return service.update_scenario(db, scenario_id, scenario)


@router.delete("/{scenario_id}", status_code=204)
def delete_scenario(scenario_id: int, db: Session = Depends(get_db)):
    """Delete a scenario."""
    service.delete_scenario(db, scenario_id)


@router.post("/{scenario_id}/trigger/{character_id}", response_model=TriggerScenarioResponse)
def trigger_scenario(
    scenario_id: int,
    character_id: int,
    request: TriggerScenarioRequest = TriggerScenarioRequest(),
    db: Session = Depends(get_db),
):
    """Trigger a scenario for a character, applying an outcome."""
    return service.trigger_scenario(db, scenario_id, character_id, request)


@router.get("/history/{character_id}", response_model=list[ScenarioHistoryResponse])
def get_character_history(character_id: int, db: Session = Depends(get_db)):
    """Get a character's scenario history."""
    return service.get_character_history(db, character_id)


@router.get("/evaluate/{character_id}")
def evaluate_scenarios(
    character_id: int,
    trigger_type: str | None = Query(None, description="Filter by trigger type (location, item, quest, health_threshold)"),
    auto_trigger: bool = Query(False, description="Automatically trigger the first applicable scenario"),
    db: Session = Depends(get_db),
):
    """
    Evaluate all scenarios for a character to find applicable ones.

    Returns a list of scenarios whose triggers match the character's current state.
    Optionally auto-trigger the first applicable scenario.

    Trigger types:
    - location: Triggered by character's position (zone, x, y)
    - item: Triggered by having an item in inventory
    - quest: Triggered by quest status
    - health_threshold: Triggered by HP percentage (below/above/equal)
    """
    return service.evaluate_scenarios(db, character_id, trigger_type, auto_trigger)
