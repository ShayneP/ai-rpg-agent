"""
---
title: Game State Management
category: complex-agents
tags: [rpg, state-management, dataclass, session-data, type-safety]
difficulty: intermediate
description: Centralized game state management for RPG sessions with type-safe data structures
demonstrates:
  - Dataclass-based state management
  - Session data persistence across agent switches
  - Type-safe context handling with generics
  - Game progression tracking and history
  - Multi-agent state coordination
  - Combat state integration
---
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, TYPE_CHECKING, Any
from livekit.agents import JobContext, AgentSession
from livekit.agents.voice import RunContext

from character import NPCCharacter

if TYPE_CHECKING:
    from api.models import APICharacter, APICombatSession


class GameState(Enum):
    CHARACTER_CREATION = "character_creation"
    EXPLORATION = "exploration"
    COMBAT = "combat"
    DIALOGUE = "dialogue"
    GAME_OVER = "game_over"


class AgentType(Enum):
    NARRATOR = "narrator"
    COMBAT = "combat"


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""


class GameStateMachine:
    """Guarded state machine to prevent illegal transitions."""

    _ALLOWED = {
        GameState.CHARACTER_CREATION: {
            GameState.CHARACTER_CREATION,
            GameState.EXPLORATION,
        },
        GameState.EXPLORATION: {
            GameState.EXPLORATION,
            GameState.COMBAT,
            GameState.DIALOGUE,
            GameState.GAME_OVER,
        },
        GameState.DIALOGUE: {
            GameState.EXPLORATION,
            GameState.COMBAT,
            GameState.DIALOGUE,
            GameState.GAME_OVER,
        },
        GameState.COMBAT: {
            GameState.EXPLORATION,
            GameState.COMBAT,
            GameState.GAME_OVER,
        },
        GameState.GAME_OVER: {GameState.GAME_OVER},
    }

    def __init__(self, initial_state: GameState = GameState.CHARACTER_CREATION):
        self._state = initial_state

    @property
    def state(self) -> GameState:
        return self._state

    def can_transition_to(self, new_state: GameState) -> bool:
        return new_state in self._ALLOWED.get(self._state, set())

    def transition_to(self, new_state: GameState) -> GameState:
        if not self.can_transition_to(new_state):
            raise StateTransitionError(
                f"Invalid state transition: {self._state.value} -> {new_state.value}"
            )
        self._state = new_state
        return self._state


@dataclass
class GameUserData:
    """Store game state and data across the session.

    All game data is stored as API IDs, with cached API responses for display.
    The API is the source of truth for all game mechanics.
    """
    ctx: JobContext
    session: AgentSession = None

    # === API-based state (IDs, API is source of truth) ===
    player_character_id: Optional[int] = None  # API character ID
    current_npc_ids: List[int] = field(default_factory=list)  # API character IDs for combat NPCs
    combat_session_id: Optional[int] = None  # API combat session ID

    # Cached API responses for display (avoid repeated fetches)
    _player_cache: Optional[Any] = None  # APICharacter when fetched
    _combat_cache: Optional[Any] = None  # APICombatSession when fetched

    # === Local-only state (not in API) ===
    active_npc: Optional[NPCCharacter] = None  # NPC currently in dialogue (friendly NPCs, not combat)

    # === Shared state ===
    game_state: GameState = GameState.CHARACTER_CREATION
    story_context: List[str] = field(default_factory=list)
    pending_story_updates: List[str] = field(default_factory=list)
    story_state: Dict[str, Any] = field(default_factory=dict)  # Legacy field, not actively used
    current_agent_type: AgentType = AgentType.NARRATOR
    current_zone_id: Optional[int] = None  # API zone ID (replaces current_location)
    current_zone_name: Optional[str] = None  # Zone name cached from API for quick access
    current_location: str = "tavern"  # DEPRECATED: kept for backwards compatibility during migration
    prev_chat_ctx_items: List = field(default_factory=list)  # Context snapshot across agents
    voice_acting_character: Optional[str] = None  # Character currently being voice acted
    combat_just_ended: bool = False  # Flag to indicate combat recently ended
    combat_result: Optional[dict] = None  # Store combat results (xp, loot) for narrator
    shared_clients: dict = field(default_factory=dict)  # Shared STT/LLM/TTS/etc for agents
    state_machine: GameStateMachine = field(default_factory=GameStateMachine)

    # Track game history
    completed_quests: List[str] = field(default_factory=list)
    visited_locations: List[str] = field(default_factory=list)  # DEPRECATED
    visited_zone_ids: List[int] = field(default_factory=list)  # Zone IDs visited

    def __post_init__(self):
        # Ensure the state machine is synced with the stored state
        if isinstance(self.game_state, str):
            try:
                self.game_state = GameState(self.game_state)
            except ValueError:
                self.game_state = GameState.CHARACTER_CREATION
        if self.state_machine.state != self.game_state:
            try:
                self.state_machine.transition_to(self.game_state)
            except StateTransitionError:
                # Fallback to a safe default without crashing session startup
                self.state_machine = GameStateMachine(initial_state=GameState.CHARACTER_CREATION)

    def add_story_event(self, event: str):
        """Add an event to the story context"""
        self.story_context.append(event)
        # Keep only last 10 events to manage context size
        if len(self.story_context) > 10:
            self.story_context.pop(0)

    def summarize(self) -> str:
        """Provide a summary of current game state using cached API data."""
        summary = f"Game State: {self.game_state.value}\n"

        # Use cached API data
        if self._player_cache:
            player = self._player_cache
            summary += f"Player: {player.name} - Level {player.level} {player.character_class.value}\n"
            summary += f"Health: {player.current_hp}/{player.max_hp}\n"
        elif self.player_character_id:
            summary += f"Player ID: {self.player_character_id} (not cached)\n"

        if self.current_location:
            summary += f"Location: {self.current_location}\n"

        # Combat info from cache
        if self.combat_session_id:
            if self._combat_cache:
                enemies = self._combat_cache.get_enemies()
                if enemies:
                    summary += f"In combat with: {', '.join(e.name for e in enemies)}\n"
            else:
                summary += f"Combat Session ID: {self.combat_session_id}\n"

        return summary

    def clear_caches(self):
        """Clear API response caches."""
        self._player_cache = None
        self._combat_cache = None


# Type alias for RunContext with our GameUserData
RunContext_T = RunContext[GameUserData]
