import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from .models import Scenario, ScenarioHistory
from .schemas import ScenarioCreate, ScenarioUpdate, TriggerScenarioRequest
from ..core.exceptions import NotFoundError, ValidationError
from ..character.service import get_character
from ..inventory.service import add_to_inventory, remove_from_inventory, get_inventory
from ..inventory.schemas import AddToInventoryRequest


def get_scenario(db: Session, scenario_id: int) -> Scenario:
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise NotFoundError("Scenario", scenario_id)
    return scenario


def get_scenarios(db: Session, skip: int = 0, limit: int = 100) -> list[Scenario]:
    return db.query(Scenario).offset(skip).limit(limit).all()


def create_scenario(db: Session, scenario_data: ScenarioCreate) -> Scenario:
    scenario = Scenario(**scenario_data.model_dump())
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario


def update_scenario(db: Session, scenario_id: int, scenario_data: ScenarioUpdate) -> Scenario:
    scenario = get_scenario(db, scenario_id)
    update_data = scenario_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(scenario, field, value)
    db.commit()
    db.refresh(scenario)
    return scenario


def delete_scenario(db: Session, scenario_id: int) -> None:
    scenario = get_scenario(db, scenario_id)
    db.delete(scenario)
    db.commit()


def get_character_history(db: Session, character_id: int) -> list[ScenarioHistory]:
    get_character(db, character_id)  # Ensure character exists
    return db.query(ScenarioHistory).filter(
        ScenarioHistory.character_id == character_id
    ).order_by(ScenarioHistory.triggered_at.desc()).all()


def can_trigger_scenario(db: Session, scenario: Scenario, character_id: int) -> bool:
    """Check if a scenario can be triggered for a character."""
    if not scenario.repeatable:
        # Check if already triggered
        existing = db.query(ScenarioHistory).filter(
            ScenarioHistory.scenario_id == scenario.id,
            ScenarioHistory.character_id == character_id,
        ).first()
        if existing:
            return False
    elif scenario.cooldown_seconds:
        # Check cooldown
        cooldown_cutoff = datetime.utcnow() - timedelta(seconds=scenario.cooldown_seconds)
        recent = db.query(ScenarioHistory).filter(
            ScenarioHistory.scenario_id == scenario.id,
            ScenarioHistory.character_id == character_id,
            ScenarioHistory.triggered_at > cooldown_cutoff,
        ).first()
        if recent:
            return False
    return True


def check_triggers(db: Session, scenario: Scenario, character_id: int) -> bool:
    """Check if all trigger conditions are met for a character."""
    character = get_character(db, character_id)

    for trigger in scenario.triggers:
        trigger_type = trigger.get("type")

        if trigger_type == "location":
            zone_id = trigger.get("zone_id")
            x = trigger.get("x")
            y = trigger.get("y")
            if zone_id and character.zone_id != zone_id:
                return False
            if x is not None and character.x != x:
                return False
            if y is not None and character.y != y:
                return False

        elif trigger_type == "item":
            item_id = trigger.get("item_id")
            if item_id:
                inventory = get_inventory(db, character_id)
                if not any(inv.item_id == item_id for inv in inventory):
                    return False

        elif trigger_type == "quest":
            from ..quest.service import get_assignment
            quest_id = trigger.get("quest_id")
            quest_status = trigger.get("quest_status")
            if quest_id:
                assignment = get_assignment(db, quest_id, character_id)
                if not assignment:
                    return False
                if quest_status and assignment.status.value != quest_status:
                    return False

        elif trigger_type == "health_threshold":
            threshold = trigger.get("threshold", 0.5)
            comparison = trigger.get("comparison", "below")
            hp_ratio = character.current_hp / max(character.max_hp, 1)
            if comparison == "below" and hp_ratio >= threshold:
                return False
            elif comparison == "above" and hp_ratio <= threshold:
                return False
            elif comparison == "equal" and abs(hp_ratio - threshold) > 0.01:
                return False

    return True


def select_outcome(scenario: Scenario, outcome_index: int | None = None) -> tuple[int, dict]:
    """Select an outcome, either by index or randomly by weight."""
    if not scenario.outcomes:
        raise ValidationError("Scenario has no outcomes defined")

    if outcome_index is not None:
        if outcome_index < 0 or outcome_index >= len(scenario.outcomes):
            raise ValidationError(f"Invalid outcome index: {outcome_index}")
        return outcome_index, scenario.outcomes[outcome_index]

    # Random weighted selection
    weights = [o.get("weight", 1) for o in scenario.outcomes]
    total_weight = sum(weights)
    roll = random.uniform(0, total_weight)

    cumulative = 0
    for i, (outcome, weight) in enumerate(zip(scenario.outcomes, weights)):
        cumulative += weight
        if roll <= cumulative:
            return i, outcome

    # Fallback to last outcome
    return len(scenario.outcomes) - 1, scenario.outcomes[-1]


def apply_outcome(db: Session, character_id: int, outcome: dict) -> dict:
    """Apply outcome effects to a character and return summary of changes."""
    character = get_character(db, character_id)
    effects = {}

    # Health change
    if outcome.get("health_change"):
        change = outcome["health_change"]
        old_hp = character.current_hp
        character.current_hp = max(0, min(character.max_hp, character.current_hp + change))
        effects["health_change"] = {
            "from": old_hp,
            "to": character.current_hp,
            "change": change,
        }

    # Attribute modifiers
    if outcome.get("attribute_modifiers"):
        effects["attribute_changes"] = {}
        for attr, mod in outcome["attribute_modifiers"].items():
            if hasattr(character, attr):
                old_val = getattr(character, attr)
                new_val = max(1, min(30, old_val + mod))
                setattr(character, attr, new_val)
                effects["attribute_changes"][attr] = {"from": old_val, "to": new_val}

    # Items granted
    if outcome.get("items_granted"):
        effects["items_granted"] = []
        for item_id in outcome["items_granted"]:
            try:
                add_to_inventory(db, character_id, AddToInventoryRequest(item_id=item_id))
                effects["items_granted"].append(item_id)
            except Exception:
                pass  # Item might not exist

    # Items removed
    if outcome.get("items_removed"):
        effects["items_removed"] = []
        inventory = get_inventory(db, character_id)
        for item_id in outcome["items_removed"]:
            inv_item = next((i for i in inventory if i.item_id == item_id), None)
            if inv_item:
                try:
                    remove_from_inventory(db, character_id, inv_item.id)
                    effects["items_removed"].append(item_id)
                except Exception:
                    pass

    # Quest trigger
    if outcome.get("trigger_quest_id"):
        effects["quest_triggered"] = outcome["trigger_quest_id"]
        # The actual quest assignment should be done by the caller if needed

    db.commit()
    db.refresh(character)
    return effects


def evaluate_scenarios(
    db: Session,
    character_id: int,
    trigger_type: str | None = None,
    auto_trigger: bool = False,
) -> dict:
    """
    Evaluate all scenarios for a character to find applicable ones.

    Args:
        character_id: The character to evaluate scenarios for
        trigger_type: Optional filter for trigger type (location, item, quest, health_threshold)
        auto_trigger: If True, automatically trigger the first applicable scenario

    Returns:
        Dict with applicable scenarios and optionally triggered result
    """
    character = get_character(db, character_id)
    all_scenarios = get_scenarios(db)

    applicable = []
    for scenario in all_scenarios:
        # Skip if can't trigger (already triggered non-repeatable, or on cooldown)
        if not can_trigger_scenario(db, scenario, character_id):
            continue

        # Check if triggers match
        if not check_triggers(db, scenario, character_id):
            continue

        # Filter by trigger type if specified
        if trigger_type:
            has_trigger_type = any(t.get("type") == trigger_type for t in scenario.triggers)
            if not has_trigger_type:
                continue

        applicable.append({
            "id": scenario.id,
            "title": scenario.title,
            "narrative_text": scenario.narrative_text,
            "triggers": scenario.triggers,
        })

    result = {
        "character_id": character_id,
        "applicable_scenarios": applicable,
        "count": len(applicable),
    }

    # Auto-trigger first applicable scenario if requested
    if auto_trigger and applicable:
        from .schemas import TriggerScenarioRequest
        triggered = trigger_scenario(
            db, applicable[0]["id"], character_id, TriggerScenarioRequest()
        )
        result["triggered"] = triggered

    return result


def trigger_scenario(
    db: Session,
    scenario_id: int,
    character_id: int,
    request: TriggerScenarioRequest,
) -> dict:
    """Trigger a scenario for a character."""
    scenario = get_scenario(db, scenario_id)
    character = get_character(db, character_id)

    # Check if can trigger
    if not can_trigger_scenario(db, scenario, character_id):
        raise ValidationError("Scenario cannot be triggered (already triggered or on cooldown)")

    # Select and apply outcome
    outcome_index, outcome = select_outcome(scenario, request.outcome_index)
    effects = apply_outcome(db, character_id, outcome)

    # Record history
    history = ScenarioHistory(
        scenario_id=scenario_id,
        character_id=character_id,
        outcome_index=outcome_index,
        outcome_data=outcome,
    )
    db.add(history)
    db.commit()
    db.refresh(history)

    return {
        "scenario_id": scenario_id,
        "character_id": character_id,
        "narrative_text": scenario.narrative_text,
        "outcome_applied": outcome,
        "effects_applied": effects,
        "history_id": history.id,
    }
