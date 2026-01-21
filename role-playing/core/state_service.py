"""
Lightweight wrapper around GameUserData to centralize common state reads/writes.

Goal: reduce direct dict/attr manipulation inside agents and make it easier to
find where state changes happen.

This service uses API IDs for all game data. The API is the source of truth.
"""

from typing import Optional, List, Union
from core.game_state import (
    AgentType,
    GameState,
    GameStateMachine,
    GameUserData,
    StateTransitionError,
)
from character import NPCCharacter
from core.settings import settings


class GameStateService:
    """
    Service layer for game state management.

    All game data is accessed via API IDs with async fetch methods.
    The API is the source of truth for all game mechanics.
    """

    def __init__(self, userdata: GameUserData):
        self.ud = userdata
        # Ensure we have a machine even if a legacy userdata slips through
        if not getattr(self.ud, "state_machine", None):
            self.ud.state_machine = GameStateMachine(initial_state=self.ud.game_state)
        # Lazy-init API clients
        self._character_client = None
        self._combat_client = None
        self._inventory_client = None

    def _get_character_client(self):
        """Get or create the character API client."""
        if self._character_client is None:
            from api.client import CharacterClient
            self._character_client = CharacterClient(
                base_url=settings.rpg_api_base_url,
                timeout=settings.rpg_api_timeout,
            )
        return self._character_client

    def _get_combat_client(self):
        """Get or create the combat API client."""
        if self._combat_client is None:
            from api.client import CombatClient
            self._combat_client = CombatClient(
                base_url=settings.rpg_api_base_url,
                timeout=settings.rpg_api_timeout,
            )
        return self._combat_client

    def _get_inventory_client(self):
        """Get or create the inventory API client."""
        if self._inventory_client is None:
            from api.client import InventoryClient
            self._inventory_client = InventoryClient(
                base_url=settings.rpg_api_base_url,
                timeout=settings.rpg_api_timeout,
            )
        return self._inventory_client

    # === Player methods ===

    def has_player(self) -> bool:
        """Check if player exists."""
        return self.ud.player_character_id is not None

    def set_player_id(self, player_id: int):
        """Set the player character ID."""
        self.ud.player_character_id = player_id
        self.ud._player_cache = None  # Clear cache to force refetch

    @property
    def player_id(self) -> Optional[int]:
        """Get the player character ID."""
        return self.ud.player_character_id

    async def get_player_async(self):
        """Fetch the player character from API (with caching)."""
        if self.ud.player_character_id is None:
            return None

        # Return cache if available
        if self.ud._player_cache is not None:
            return self.ud._player_cache

        # Fetch from API
        client = self._get_character_client()
        player = await client.get(self.ud.player_character_id)
        self.ud._player_cache = player
        return player

    async def refresh_player_cache(self):
        """Force refresh the player cache from API."""
        self.ud._player_cache = None
        return await self.get_player_async()

    # === NPC methods (combat enemies) ===

    def add_npc_id(self, npc_id: int):
        """Add an NPC character ID."""
        if npc_id not in self.ud.current_npc_ids:
            self.ud.current_npc_ids.append(npc_id)

    def remove_npc_id(self, npc_id: int):
        """Remove an NPC character ID."""
        if npc_id in self.ud.current_npc_ids:
            self.ud.current_npc_ids.remove(npc_id)

    def clear_npc_ids(self):
        """Clear all NPC IDs."""
        self.ud.current_npc_ids = []

    @property
    def npc_ids(self) -> List[int]:
        """Get current NPC IDs."""
        return self.ud.current_npc_ids

    async def get_npc_async(self, npc_id: int):
        """Fetch an NPC character from API."""
        client = self._get_character_client()
        return await client.get(npc_id)

    async def get_all_npcs_async(self):
        """Fetch all current NPCs from API."""
        client = self._get_character_client()
        npcs = []
        for npc_id in self.ud.current_npc_ids:
            try:
                npc = await client.get(npc_id)
                npcs.append(npc)
            except Exception:
                pass  # NPC may have been deleted
        return npcs

    # === Dialogue NPC (local-only, for friendly NPCs) ===

    def set_active_npc(self, npc: Optional[NPCCharacter]):
        """Set the active NPC for dialogue (local-only for friendly NPCs)."""
        self.ud.active_npc = npc

    @property
    def active_npc(self) -> Optional[NPCCharacter]:
        """Get the active dialogue NPC."""
        return self.ud.active_npc

    # === Combat methods ===

    def set_combat_session_id(self, session_id: int):
        """Set the combat session ID."""
        self.ud.combat_session_id = session_id
        self.ud._combat_cache = None  # Clear cache
        self.set_game_state(GameState.COMBAT)
        self.ud.current_agent_type = AgentType.COMBAT

    @property
    def combat_session_id(self) -> Optional[int]:
        """Get the combat session ID."""
        return self.ud.combat_session_id

    def has_combat(self) -> bool:
        """Check if there's an active combat session."""
        return self.ud.combat_session_id is not None

    async def get_combat_async(self):
        """Fetch combat session from API (with caching)."""
        if self.ud.combat_session_id is None:
            return None

        # Return cache if available
        if self.ud._combat_cache is not None:
            return self.ud._combat_cache

        # Fetch from API
        client = self._get_combat_client()
        combat = await client.get_state(self.ud.combat_session_id)
        self.ud._combat_cache = combat
        return combat

    async def refresh_combat_cache(self):
        """Force refresh the combat cache from API."""
        self.ud._combat_cache = None
        return await self.get_combat_async()

    def clear_combat_session(self, game_over: bool = False):
        """Clear the combat session."""
        self.ud.combat_session_id = None
        self.ud._combat_cache = None
        next_state = GameState.GAME_OVER if game_over else GameState.EXPLORATION
        self.set_game_state(next_state)
        self.ud.current_agent_type = AgentType.NARRATOR
        self.ud.active_npc = None

    # === Story / context ===

    def add_story_event(self, event: str):
        """Add an event to the story context."""
        self.ud.add_story_event(event)

    @property
    def story_context(self) -> List[str]:
        """Get the story context."""
        return self.ud.story_context

    # === Game state ===

    def set_game_state(self, state: Union[str, GameState]):
        """Set the current game state."""
        new_state = self._coerce_state(state)
        self.ud.state_machine.transition_to(new_state)
        self.ud.game_state = new_state

    @property
    def game_state(self) -> GameState:
        """Get the current game state."""
        return self.ud.game_state

    def _coerce_state(self, state: Union[str, GameState]) -> GameState:
        if isinstance(state, GameState):
            return state
        try:
            return GameState(state)
        except ValueError as exc:
            raise StateTransitionError(f"Unknown game state: {state}") from exc

    # === Location / Zone ===

    def set_zone_id(self, zone_id: int, zone_name: Optional[str] = None):
        """Set the current zone ID and optionally the zone name (API-based location)."""
        self.ud.current_zone_id = zone_id
        if zone_name:
            self.ud.current_zone_name = zone_name
        if zone_id not in self.ud.visited_zone_ids:
            self.ud.visited_zone_ids.append(zone_id)

    @property
    def zone_id(self) -> Optional[int]:
        """Get the current zone ID."""
        return self.ud.current_zone_id

    @property
    def zone_name(self) -> Optional[str]:
        """Get the cached zone name."""
        return self.ud.current_zone_name

    def _get_location_client(self):
        """Get or create the location API client."""
        if not hasattr(self, '_location_client') or self._location_client is None:
            from api.client import LocationClient
            self._location_client = LocationClient(
                base_url=settings.rpg_api_base_url,
                timeout=settings.rpg_api_timeout,
            )
        return self._location_client

    async def get_current_zone_async(self):
        """Fetch the current zone from API."""
        if self.ud.current_zone_id is None:
            return None
        client = self._get_location_client()
        return await client.get_zone(self.ud.current_zone_id)

    async def get_available_exits_async(self, include_hidden: bool = False):
        """Get available exits from the current zone."""
        if self.ud.current_zone_id is None:
            return []
        client = self._get_location_client()
        return await client.get_exits(self.ud.current_zone_id, include_hidden)

    async def travel_through_exit_async(self, exit_id: int, character_id: int):
        """Travel through an exit and update zone."""
        client = self._get_location_client()
        result = await client.travel(exit_id, character_id)
        if result.success and result.new_zone:
            self.set_zone_id(result.new_zone.id, result.new_zone.name)
        return result

    # DEPRECATED: Legacy location methods (use zone_id instead)
    def set_location(self, location: str):
        """DEPRECATED: Set the current location string."""
        self.ud.current_location = location
        self.ud.visited_locations.append(location)

    @property
    def location(self) -> str:
        """DEPRECATED: Get the current location string."""
        return self.ud.current_location

    # === Combat result (for narrator after combat ends) ===

    def set_combat_result(self, result: dict):
        """Store combat results for the narrator to announce."""
        self.ud.combat_result = result
        self.ud.combat_just_ended = True

    def get_combat_result(self) -> Optional[dict]:
        """Get stored combat results."""
        return self.ud.combat_result

    def clear_combat_result(self):
        """Clear stored combat results."""
        self.ud.combat_result = None
        self.ud.combat_just_ended = False

    @property
    def combat_just_ended(self) -> bool:
        """Check if combat just ended."""
        return self.ud.combat_just_ended

    # === Voice acting ===

    def set_voice_acting(self, character: Optional[str]):
        """Set the character currently being voice acted."""
        self.ud.voice_acting_character = character

    @property
    def voice_acting_character(self) -> Optional[str]:
        """Get the character currently being voice acted."""
        return self.ud.voice_acting_character

    # === Summary ===

    def summary(self) -> str:
        """Get a summary of the current game state."""
        return self.ud.summarize()

    # === Quests ===

    def _get_quest_client(self):
        """Get or create the quest API client."""
        if not hasattr(self, '_quest_client') or self._quest_client is None:
            from api.client import QuestClient
            self._quest_client = QuestClient(
                base_url=settings.rpg_api_base_url,
                timeout=settings.rpg_api_timeout,
            )
        return self._quest_client

    async def get_active_quests_async(self):
        """Get active quests for the current player."""
        if self.ud.player_character_id is None:
            return []
        client = self._get_quest_client()
        return await client.get_active_quests(self.ud.player_character_id)

    async def get_available_quests_async(self, character_level: int = 1):
        """Get quests available for the player to accept."""
        if self.ud.player_character_id is None:
            return []
        client = self._get_quest_client()
        return await client.get_available_quests(self.ud.player_character_id, character_level)

    async def accept_quest_async(self, quest_id: int):
        """Accept a quest for the player."""
        if self.ud.player_character_id is None:
            return None
        client = self._get_quest_client()
        return await client.assign_quest(quest_id, self.ud.player_character_id)

    async def update_quest_progress_async(self, quest_id: int, objective_id: int, amount: int = 1):
        """Update progress on a quest objective."""
        if self.ud.player_character_id is None:
            return None
        client = self._get_quest_client()
        return await client.update_progress(quest_id, self.ud.player_character_id, objective_id, amount)

    async def complete_quest_async(self, quest_id: int):
        """Complete a quest."""
        if self.ud.player_character_id is None:
            return None
        client = self._get_quest_client()
        return await client.complete_quest(quest_id, self.ud.player_character_id)
