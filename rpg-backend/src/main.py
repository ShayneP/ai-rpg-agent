from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import engine, Base

# Import all models to ensure they're registered with SQLAlchemy
from .character.models import Character, CharacterSkill
from .inventory.models import Item, InventoryItem
from .location.models import Zone, GridCell, Exit
from .quest.models import Quest, QuestObjective, QuestAssignment
from .event.models import GameEvent
from .scenario.models import Scenario, ScenarioHistory
from .combat.models import CombatSession, Combatant, CombatAction

# Import routers
from .character.router import router as character_router
from .inventory.router import router as inventory_router
from .inventory.router import inventory_router as character_inventory_router
from .location.router import router as location_router
from .quest.router import router as quest_router
from .event.router import router as event_router
from .scenario.router import router as scenario_router
from .combat.router import router as combat_router
from .reference.router import router as reference_router
from .trade.router import router as trade_router

# Create database tables
Base.metadata.create_all(bind=engine)

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="""
## Tabletop RPG Game Loop API

A FastAPI application for managing tabletop RPG game state including:

- **Characters**: Create and manage player characters and NPCs with attributes, skills, and health
- **Inventory**: Items and inventory management with equipment slots
- **Locations**: Zones with grid-based positioning and spatial queries
- **Quests**: Quest tracking with objectives and progress
- **Events**: Game event logging for tracking game history
- **Scenarios**: Story events with triggers and outcomes
- **Combat**: Turn-based combat engine with initiative and threat-based targeting

### Character Classes
- **Warrior**: +2 STR, +1 CON, higher base HP
- **Mage**: +2 INT, +1 WIS, access to spell slots
- **Rogue**: +2 DEX, +1 CHA, +2 initiative bonus
- **Cleric**: +2 WIS, +1 CON, healing abilities
- **Ranger**: +1 DEX, +1 WIS, +1 STR

### Combat System
1. Initialize combat with `POST /combat/start`
2. Process NPC turns with `POST /combat/{id}/process`
3. Submit player actions with `POST /combat/{id}/act`
4. Repeat until combat ends
5. Resolve with `POST /combat/{id}/resolve`
6. Finalize with `POST /combat/{id}/finish`
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware for webapp support
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(character_router)
app.include_router(character_inventory_router, prefix="/character", tags=["character"])
app.include_router(inventory_router)
app.include_router(location_router)
app.include_router(quest_router)
app.include_router(event_router)
app.include_router(scenario_router)
app.include_router(combat_router)
app.include_router(reference_router)
app.include_router(trade_router)


@app.get("/", tags=["root"])
def root():
    """API root - returns basic info."""
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["root"])
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/admin/reset", tags=["admin"])
def reset_database():
    """Reset the entire database - clears all data and resets auto-increment IDs.

    WARNING: This deletes ALL data including characters, items, quests, combat sessions, etc.
    """
    from sqlalchemy import text
    from .database import engine

    # Use raw connection to avoid session state issues
    with engine.connect() as conn:
        # Order matters due to foreign key constraints
        # Note: We keep quests, quest_objectives, zones, exits, scenarios, items
        # These are game content definitions. We only clear player-specific data.
        tables_to_clear = [
            "combat_actions",
            "combatants",
            "combat_sessions",
            "scenario_history",
            "game_events",
            "quest_assignments",
            "inventory_items",
            "character_skills",
            "characters",
        ]

        deleted_counts = {}
        for table in tables_to_clear:
            try:
                result = conn.execute(text(f"DELETE FROM {table}"))
                deleted_counts[table] = result.rowcount
            except Exception as e:
                deleted_counts[table] = f"error: {str(e)}"

        # Reset SQLite auto-increment sequences (may not exist if no inserts happened)
        try:
            conn.execute(text("DELETE FROM sqlite_sequence"))
        except Exception:
            pass  # Table doesn't exist yet, that's fine

        conn.commit()

        return {
            "status": "reset complete",
            "deleted": deleted_counts,
            "message": "All data cleared and IDs reset to 1"
        }
