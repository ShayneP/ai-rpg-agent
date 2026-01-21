from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from . import service
from .schemas import EventCreate, EventResponse, EventQuery

router = APIRouter(prefix="/events", tags=["events"])


@router.post("/", response_model=EventResponse, status_code=201)
def log_event(event: EventCreate, db: Session = Depends(get_db)):
    """Log a new game event."""
    return service.create_event(db, event)


@router.get("/", response_model=list[EventResponse])
def list_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """List recent game events."""
    return service.get_events(db, skip, limit)


@router.get("/{event_id}", response_model=EventResponse)
def get_event(event_id: int, db: Session = Depends(get_db)):
    """Get a specific event by ID."""
    return service.get_event(db, event_id)


@router.post("/query", response_model=list[EventResponse])
def query_events(query: EventQuery, db: Session = Depends(get_db)):
    """Query events with filters."""
    return service.query_events(db, query)
