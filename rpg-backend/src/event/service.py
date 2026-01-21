from sqlalchemy.orm import Session

from .models import GameEvent
from .schemas import EventCreate, EventQuery
from ..core.exceptions import NotFoundError


def get_event(db: Session, event_id: int) -> GameEvent:
    event = db.query(GameEvent).filter(GameEvent.id == event_id).first()
    if not event:
        raise NotFoundError("Event", event_id)
    return event


def get_events(db: Session, skip: int = 0, limit: int = 100) -> list[GameEvent]:
    return db.query(GameEvent).order_by(GameEvent.timestamp.desc()).offset(skip).limit(limit).all()


def create_event(db: Session, event_data: EventCreate) -> GameEvent:
    event = GameEvent(**event_data.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def query_events(db: Session, query: EventQuery) -> list[GameEvent]:
    q = db.query(GameEvent)

    if query.event_type:
        q = q.filter(GameEvent.event_type == query.event_type)
    if query.character_id:
        q = q.filter(GameEvent.character_id == query.character_id)
    if query.quest_id:
        q = q.filter(GameEvent.quest_id == query.quest_id)
    if query.scenario_id:
        q = q.filter(GameEvent.scenario_id == query.scenario_id)
    if query.combat_session_id:
        q = q.filter(GameEvent.combat_session_id == query.combat_session_id)
    if query.zone_id:
        q = q.filter(GameEvent.zone_id == query.zone_id)
    if query.from_timestamp:
        q = q.filter(GameEvent.timestamp >= query.from_timestamp)
    if query.to_timestamp:
        q = q.filter(GameEvent.timestamp <= query.to_timestamp)

    return q.order_by(GameEvent.timestamp.desc()).offset(query.offset).limit(query.limit).all()


# Helper functions for common event types
def log_combat_start(db: Session, combat_session_id: int, character_ids: list[int], zone_id: int | None = None) -> GameEvent:
    return create_event(db, EventCreate(
        event_type="combat_start",
        combat_session_id=combat_session_id,
        zone_id=zone_id,
        data={"participants": character_ids},
    ))


def log_combat_end(db: Session, combat_session_id: int, winner_team: int | None, zone_id: int | None = None) -> GameEvent:
    return create_event(db, EventCreate(
        event_type="combat_end",
        combat_session_id=combat_session_id,
        zone_id=zone_id,
        data={"winner_team": winner_team},
    ))


def log_character_death(db: Session, character_id: int, killer_id: int | None = None, combat_session_id: int | None = None) -> GameEvent:
    return create_event(db, EventCreate(
        event_type="character_death",
        character_id=character_id,
        target_character_id=killer_id,
        combat_session_id=combat_session_id,
    ))


def log_item_acquired(db: Session, character_id: int, item_id: int, source: str | None = None) -> GameEvent:
    return create_event(db, EventCreate(
        event_type="item_acquired",
        character_id=character_id,
        item_id=item_id,
        data={"source": source} if source else {},
    ))


def log_quest_started(db: Session, character_id: int, quest_id: int) -> GameEvent:
    return create_event(db, EventCreate(
        event_type="quest_started",
        character_id=character_id,
        quest_id=quest_id,
    ))


def log_quest_completed(db: Session, character_id: int, quest_id: int) -> GameEvent:
    return create_event(db, EventCreate(
        event_type="quest_completed",
        character_id=character_id,
        quest_id=quest_id,
    ))


def log_level_up(db: Session, character_id: int, new_level: int) -> GameEvent:
    return create_event(db, EventCreate(
        event_type="level_up",
        character_id=character_id,
        data={"new_level": new_level},
    ))


def log_location_change(db: Session, character_id: int, zone_id: int, x: int, y: int, from_zone_id: int | None = None) -> GameEvent:
    return create_event(db, EventCreate(
        event_type="location_change",
        character_id=character_id,
        zone_id=zone_id,
        x=x,
        y=y,
        data={"from_zone_id": from_zone_id} if from_zone_id else {},
    ))


def log_scenario_triggered(db: Session, character_id: int, scenario_id: int, outcome_index: int | None = None) -> GameEvent:
    return create_event(db, EventCreate(
        event_type="scenario_triggered",
        character_id=character_id,
        scenario_id=scenario_id,
        data={"outcome_index": outcome_index} if outcome_index is not None else {},
    ))
