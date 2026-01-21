"""
Async HTTP client for the tabletop-rpg-api.

Provides typed client classes for all API endpoints with error handling,
retries, and response parsing into Pydantic models.
"""

import logging
from typing import Any

import httpx

from .models import (
    APICharacter,
    APICombatSession,
    APICombatant,
    APIActionResult,
    APIProcessTurnResponse,
    APIPlayerActionResponse,
    APIResolveResponse,
    APICombatSummary,
    APIItem,
    APIInventoryItem,
    APIMonster,
    APIWeapon,
    APISpell,
    APIAbility,
    APILootTable,
    APIXPStatus,
    APIExperienceResult,
    APIHealth,
    APITradeResult,
    APITradeValueCheck,
    APIZone,
    APIExitWithDestination,
    APITravelResponse,
    APIUnlockResponse,
    APIQuest,
    APIQuestAssignment,
    QuestStatus,
    APIScenario,
    APIScenarioHistory,
    APITriggerScenarioResponse,
    APIEvaluateScenariosResponse,
    ActionType,
    InitiativeType,
)

logger = logging.getLogger("dungeons-and-agents.api")


class APIError(Exception):
    """Base exception for API errors."""
    def __init__(self, message: str, status_code: int | None = None, response: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class NotFoundError(APIError):
    """Resource not found (404)."""
    pass


class ValidationError(APIError):
    """Request validation failed (422)."""
    pass


class RPGAPIClient:
    """Base async HTTP client for the RPG API."""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json: dict | None = None,
    ) -> dict | list | None:
        """Make an HTTP request and handle errors."""
        client = await self._get_client()
        url = path if path.startswith("/") else f"/{path}"

        try:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                json=json,
            )

            if response.status_code == 204:
                return None

            if response.status_code == 404:
                raise NotFoundError(
                    f"Resource not found: {url}",
                    status_code=404,
                    response=response.json() if response.content else None,
                )

            if response.status_code == 422:
                error_data = response.json() if response.content else {}
                raise ValidationError(
                    f"Validation error: {error_data.get('detail', 'Unknown error')}",
                    status_code=422,
                    response=error_data,
                )

            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                raise APIError(
                    f"API error {response.status_code}: {error_data.get('detail', 'Unknown error')}",
                    status_code=response.status_code,
                    response=error_data,
                )

            if not response.content:
                return None

            return response.json()

        except httpx.RequestError as e:
            logger.error(f"HTTP request failed: {e}")
            raise APIError(f"Request failed: {e}") from e

    async def get(self, path: str, params: dict | None = None) -> dict | list | None:
        """Make a GET request."""
        return await self._request("GET", path, params=params)

    async def post(self, path: str, json: dict | None = None, params: dict | None = None) -> dict | list | None:
        """Make a POST request."""
        return await self._request("POST", path, json=json, params=params)

    async def put(self, path: str, json: dict | None = None) -> dict | list | None:
        """Make a PUT request."""
        return await self._request("PUT", path, json=json)

    async def delete(self, path: str, params: dict | None = None) -> dict | list | None:
        """Make a DELETE request."""
        return await self._request("DELETE", path, params=params)


class CharacterClient(RPGAPIClient):
    """Client for character-related API endpoints."""

    async def create(
        self,
        name: str,
        character_class: str,
        character_type: str = "player",
        level: int = 1,
        strength: int = 10,
        dexterity: int = 10,
        constitution: int = 10,
        intelligence: int = 10,
        wisdom: int = 10,
        charisma: int = 10,
        gold: int = 0,
    ) -> APICharacter:
        """Create a new character."""
        data = {
            "name": name,
            "character_class": character_class,
            "character_type": character_type,
            "level": level,
            "strength": strength,
            "dexterity": dexterity,
            "constitution": constitution,
            "intelligence": intelligence,
            "wisdom": wisdom,
            "charisma": charisma,
            "gold": gold,
        }
        response = await self.post("/character/", json=data)
        return APICharacter.model_validate(response)

    async def create_from_monster(
        self,
        monster_id: str,
        name: str | None = None,
        zone_id: int | None = None,
    ) -> APICharacter:
        """Create an NPC character from a monster template.

        Args:
            monster_id: The monster template ID (e.g., "goblin", "wolf")
            name: Custom name for the monster (defaults to monster's base name)
            zone_id: Zone ID where the monster should be placed (important for combat)
        """
        params = {}
        if name:
            params["name"] = name
        if zone_id is not None:
            params["zone_id"] = zone_id
        response = await self.post(f"/character/from-monster/{monster_id}", params=params)
        return APICharacter.model_validate(response)

    async def get(self, character_id: int) -> APICharacter:
        """Get a character by ID."""
        response = await super().get(f"/character/{character_id}")
        return APICharacter.model_validate(response)

    async def list(
        self,
        character_type: str | None = None,
        zone_id: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[APICharacter]:
        """List characters with optional filters."""
        params = {"skip": skip, "limit": limit}
        if character_type:
            params["character_type"] = character_type
        if zone_id is not None:
            params["zone_id"] = zone_id
        response = await super().get("/character/", params=params)
        return [APICharacter.model_validate(c) for c in response]

    async def update(self, character_id: int, **updates) -> APICharacter:
        """Update a character."""
        response = await self.put(f"/character/{character_id}", json=updates)
        return APICharacter.model_validate(response)

    async def delete(self, character_id: int) -> None:
        """Delete a character."""
        await super().delete(f"/character/{character_id}")

    async def get_health(self, character_id: int) -> APIHealth:
        """Get character's health status."""
        response = await super().get(f"/character/{character_id}/health")
        return APIHealth.model_validate(response)

    async def update_health(
        self,
        character_id: int,
        current_hp: int | None = None,
        max_hp: int | None = None,
        temporary_hp: int | None = None,
        armor_class: int | None = None,
    ) -> APIHealth:
        """Update character's health."""
        data = {}
        if current_hp is not None:
            data["current_hp"] = current_hp
        if max_hp is not None:
            data["max_hp"] = max_hp
        if temporary_hp is not None:
            data["temporary_hp"] = temporary_hp
        if armor_class is not None:
            data["armor_class"] = armor_class
        response = await self.put(f"/character/{character_id}/health", json=data)
        return APIHealth.model_validate(response)

    async def award_experience(self, character_id: int, amount: int) -> APICharacter:
        """Award experience points to a character."""
        response = await self.post(f"/character/{character_id}/experience", params={"amount": amount})
        return APICharacter.model_validate(response)

    async def add_gold(self, character_id: int, amount: int) -> APICharacter:
        """Add (or subtract with negative) gold to a character."""
        response = await self.post(f"/character/{character_id}/gold", params={"amount": amount})
        return APICharacter.model_validate(response)

    async def get_xp_status(self, character_id: int) -> APIXPStatus:
        """Get XP progress to next level."""
        response = await super().get(f"/character/{character_id}/xp-status")
        return APIXPStatus.model_validate(response)

    async def rest(self, character_id: int, rest_type: str = "short") -> APICharacter:
        """Take a short or long rest."""
        response = await self.post(f"/character/{character_id}/rest", params={"rest_type": rest_type})
        return APICharacter.model_validate(response)

    async def get_spell_slots(self, character_id: int) -> dict:
        """Get current and max spell slots."""
        response = await super().get(f"/character/{character_id}/spell-slots")
        return response


class InventoryClient(RPGAPIClient):
    """Client for inventory-related API endpoints."""

    async def get_inventory(self, character_id: int) -> list[APIInventoryItem]:
        """Get a character's inventory."""
        response = await self.get(f"/character/{character_id}/inventory")
        return [APIInventoryItem.model_validate(item) for item in response]

    async def add_item(
        self,
        character_id: int,
        item_id: int,
        quantity: int = 1,
        equipped: bool = False,
        equipment_slot: str | None = None,
    ) -> APIInventoryItem:
        """Add an item to a character's inventory."""
        data = {
            "item_id": item_id,
            "quantity": quantity,
            "equipped": equipped,
        }
        if equipment_slot:
            data["equipment_slot"] = equipment_slot
        response = await self.post(f"/character/{character_id}/inventory", json=data)
        return APIInventoryItem.model_validate(response)

    async def remove_item(
        self,
        character_id: int,
        inventory_item_id: int,
        quantity: int | None = None,
    ) -> None:
        """Remove an item from inventory."""
        params = {"quantity": quantity} if quantity else {}
        await self.delete(f"/character/{character_id}/inventory/{inventory_item_id}", params=params)

    async def equip_item(
        self,
        character_id: int,
        inventory_item_id: int,
        equipment_slot: str,
    ) -> APIInventoryItem:
        """Equip an inventory item to a slot."""
        data = {"equipment_slot": equipment_slot}
        response = await self.post(
            f"/character/{character_id}/inventory/{inventory_item_id}/equip",
            json=data,
        )
        return APIInventoryItem.model_validate(response)

    async def unequip_item(
        self,
        character_id: int,
        inventory_item_id: int,
    ) -> APIInventoryItem:
        """Unequip an item."""
        response = await self.post(f"/character/{character_id}/inventory/{inventory_item_id}/unequip")
        return APIInventoryItem.model_validate(response)

    async def get_item(self, item_id: int) -> APIItem:
        """Get an item definition by ID."""
        response = await self.get(f"/items/{item_id}")
        return APIItem.model_validate(response)

    async def list_items(
        self,
        item_type: str | None = None,
        rarity: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[APIItem]:
        """List item definitions."""
        params = {"skip": skip, "limit": limit}
        if item_type:
            params["item_type"] = item_type
        if rarity:
            params["rarity"] = rarity
        response = await self.get("/items/", params=params)
        return [APIItem.model_validate(item) for item in response]

    async def create_item(
        self,
        name: str,
        item_type: str,
        description: str | None = None,
        rarity: str = "common",
        weight: float = 0.0,
        value: int = 0,
        stackable: bool = False,
        max_stack: int = 1,
        properties: dict | None = None,
    ) -> APIItem:
        """Create a new item definition."""
        data = {
            "name": name,
            "item_type": item_type,
            "rarity": rarity,
            "weight": weight,
            "value": value,
            "stackable": stackable,
            "max_stack": max_stack,
            "properties": properties or {},
        }
        if description:
            data["description"] = description
        response = await self.post("/items/", json=data)
        return APIItem.model_validate(response)


class CombatClient(RPGAPIClient):
    """Client for combat-related API endpoints."""

    async def start_combat(
        self,
        participants: list[dict[str, int]],
        zone_id: int | None = None,
        initiative_type: str = "individual",
    ) -> APICombatSession:
        """
        Start a new combat session.

        Args:
            participants: List of {"character_id": int, "team_id": int}
            zone_id: Optional zone ID for the combat
            initiative_type: "individual", "group", "side", or "reroll"
        """
        data = {
            "participants": participants,
            "initiative_type": initiative_type,
        }
        if zone_id is not None:
            data["zone_id"] = zone_id
        response = await self.post("/combat/start", json=data)
        return APICombatSession.model_validate(response)

    async def get_state(self, session_id: int) -> APICombatSession:
        """Get current combat state."""
        response = await self.get(f"/combat/{session_id}")
        return APICombatSession.model_validate(response)

    async def process_turns(self, session_id: int) -> APIProcessTurnResponse:
        """Process NPC turns until a player needs to act."""
        response = await self.post(f"/combat/{session_id}/process")
        return APIProcessTurnResponse.model_validate(response)

    async def player_action(
        self,
        session_id: int,
        character_id: int,
        action_type: str,
        target_id: int | None = None,
        ability_id: str | None = None,
        item_id: int | None = None,
        spell_name: str | None = None,
    ) -> APIPlayerActionResponse:
        """
        Submit a player action.

        Args:
            session_id: Combat session ID
            character_id: The player's character ID
            action_type: "attack", "spell", "ability", "item", "defend", "dodge", "flee", "pass"
            target_id: Combatant ID to target (for attacks, spells, etc.)
            ability_id: Class ability ID (e.g., "second_wind")
            item_id: Inventory item ID for item actions
            spell_name: Spell name for spell actions
        """
        data = {
            "character_id": character_id,
            "action_type": action_type,
        }
        if target_id is not None:
            data["target_id"] = target_id
        if ability_id:
            data["ability_id"] = ability_id
        if item_id is not None:
            data["item_id"] = item_id
        if spell_name:
            data["spell_name"] = spell_name

        response = await self.post(f"/combat/{session_id}/act", json=data)
        return APIPlayerActionResponse.model_validate(response)

    async def resolve(self, session_id: int) -> APIResolveResponse:
        """Resolve combat and calculate rewards."""
        response = await self.post(f"/combat/{session_id}/resolve")
        return APIResolveResponse.model_validate(response)

    async def finish(self, session_id: int) -> APICombatSummary:
        """End combat and get final summary."""
        response = await self.post(f"/combat/{session_id}/finish")
        return APICombatSummary.model_validate(response)

    async def get_history(self, session_id: int) -> list[APIActionResult]:
        """Get all actions from a combat session."""
        response = await self.get(f"/combat/{session_id}/history")
        return [APIActionResult.model_validate(a) for a in response.get("actions", [])]


class ReferenceClient(RPGAPIClient):
    """Client for reference data endpoints."""

    async def get_monster(self, monster_id: str) -> APIMonster:
        """Get a monster template by ID."""
        response = await self.get(f"/reference/monsters/{monster_id}")
        return APIMonster.model_validate(response)

    async def list_monsters(
        self,
        monster_type: str | None = None,
        size: str | None = None,
        min_cr: float | None = None,
        max_cr: float | None = None,
    ) -> list[APIMonster]:
        """List monster templates with optional filters."""
        params = {}
        if monster_type:
            params["monster_type"] = monster_type
        if size:
            params["size"] = size
        if min_cr is not None:
            params["min_cr"] = min_cr
        if max_cr is not None:
            params["max_cr"] = max_cr
        response = await self.get("/reference/monsters", params=params)
        return [APIMonster.model_validate(m) for m in response]

    async def get_weapon(self, weapon_name: str) -> APIWeapon:
        """Get a weapon by name."""
        response = await self.get(f"/reference/weapons/{weapon_name}")
        return APIWeapon.model_validate(response)

    async def list_weapons(
        self,
        category: str | None = None,
        damage_type: str | None = None,
        property: str | None = None,
    ) -> list[APIWeapon]:
        """List weapons with optional filters."""
        params = {}
        if category:
            params["category"] = category
        if damage_type:
            params["damage_type"] = damage_type
        if property:
            params["property"] = property
        response = await self.get("/reference/weapons", params=params)
        return [APIWeapon.model_validate(w) for w in response]

    async def get_spell(self, spell_name: str) -> APISpell:
        """Get a spell by name."""
        response = await self.get(f"/reference/spells/{spell_name}")
        return APISpell.model_validate(response)

    async def list_spells(
        self,
        level: int | None = None,
        character_class: str | None = None,
        school: str | None = None,
    ) -> list[APISpell]:
        """List spells with optional filters."""
        params = {}
        if level is not None:
            params["level"] = level
        if character_class:
            params["character_class"] = character_class
        if school:
            params["school"] = school
        response = await self.get("/reference/spells", params=params)
        return [APISpell.model_validate(s) for s in response]

    async def get_ability(self, ability_id: str) -> APIAbility:
        """Get a class ability by ID."""
        response = await self.get(f"/reference/abilities/{ability_id}")
        return APIAbility.model_validate(response)

    async def list_abilities(
        self,
        character_class: str | None = None,
        min_level: int | None = None,
    ) -> list[APIAbility]:
        """List class abilities with optional filters."""
        params = {}
        if character_class:
            params["character_class"] = character_class
        if min_level is not None:
            params["min_level"] = min_level
        response = await self.get("/reference/abilities", params=params)
        return [APIAbility.model_validate(a) for a in response]

    async def get_loot_table(self, table_id: str) -> APILootTable:
        """Get a loot table by ID."""
        response = await self.get(f"/reference/loot-tables/{table_id}")
        return APILootTable.model_validate(response)

    async def get_loot_table_for_monster(self, monster_id: str) -> APILootTable | None:
        """Get the loot table for a specific monster."""
        try:
            response = await self.get(f"/reference/loot-tables/for-monster/{monster_id}")
            return APILootTable.model_validate(response)
        except NotFoundError:
            return None


class TradeClient(RPGAPIClient):
    """Client for trade-related API endpoints."""

    async def propose_trade(
        self,
        player_id: int,
        npc_id: int,
        offer_item_id: int | None = None,
        offer_gold: int = 0,
        request_item_id: int | None = None,
        request_gold: int = 0,
    ) -> APITradeResult:
        """
        Propose a trade with an NPC.

        Args:
            player_id: The player character ID
            npc_id: The NPC character ID
            offer_item_id: Optional inventory item ID to offer
            offer_gold: Gold amount to offer
            request_item_id: Optional NPC inventory item ID to request
            request_gold: Gold amount to request

        Returns:
            Trade result with success/failure and updated gold amounts
        """
        data = {
            "player_id": player_id,
            "npc_id": npc_id,
            "offer_gold": offer_gold,
            "request_gold": request_gold,
        }
        if offer_item_id is not None:
            data["offer_item_id"] = offer_item_id
        if request_item_id is not None:
            data["request_item_id"] = request_item_id

        response = await self.post("/trade/propose", json=data)
        return APITradeResult.model_validate(response)

    async def check_trade(
        self,
        player_id: int,
        npc_id: int,
        offer_item_id: int | None = None,
        offer_gold: int = 0,
        request_item_id: int | None = None,
        request_gold: int = 0,
    ) -> APITradeValueCheck:
        """
        Check trade values and DC without executing.

        Useful for showing the player what the DC would be.
        """
        data = {
            "player_id": player_id,
            "npc_id": npc_id,
            "offer_gold": offer_gold,
            "request_gold": request_gold,
        }
        if offer_item_id is not None:
            data["offer_item_id"] = offer_item_id
        if request_item_id is not None:
            data["request_item_id"] = request_item_id

        response = await self.post("/trade/check", json=data)
        return APITradeValueCheck.model_validate(response)


class LocationClient(RPGAPIClient):
    """Client for location/zone navigation API endpoints."""

    async def get_zone(self, zone_id: int) -> APIZone:
        """Get a zone by ID."""
        response = await self.get(f"/location/zones/{zone_id}")
        return APIZone.model_validate(response)

    async def list_zones(self, skip: int = 0, limit: int = 100) -> list[APIZone]:
        """List all zones."""
        response = await self.get("/location/zones", params={"skip": skip, "limit": limit})
        return [APIZone.model_validate(z) for z in response]

    async def get_exits(
        self,
        zone_id: int,
        include_hidden: bool = False,
    ) -> list[APIExitWithDestination]:
        """Get all exits from a zone with destination info.

        Args:
            zone_id: The zone to get exits from
            include_hidden: Whether to include hidden exits (e.g., after discovery)

        Returns:
            List of exits with their destination zone info
        """
        params = {"include_hidden": include_hidden} if include_hidden else {}
        response = await self.get(f"/location/zones/{zone_id}/exits", params=params)
        return [APIExitWithDestination.model_validate(e) for e in response]

    async def travel(self, exit_id: int, character_id: int) -> APITravelResponse:
        """Travel through an exit to a new zone.

        Args:
            exit_id: The exit to travel through
            character_id: The character traveling

        Returns:
            Travel result with new zone and available exits
        """
        data = {"character_id": character_id}
        response = await self.post(f"/location/exits/{exit_id}/travel", json=data)
        return APITravelResponse.model_validate(response)

    async def unlock(
        self,
        exit_id: int,
        character_id: int,
        item_id: int | None = None,
    ) -> APIUnlockResponse:
        """Attempt to unlock a locked exit.

        Args:
            exit_id: The exit to unlock
            character_id: The character attempting to unlock
            item_id: Optional item to use as key

        Returns:
            Unlock result with success/failure message
        """
        data = {"character_id": character_id}
        if item_id is not None:
            data["item_id"] = item_id
        response = await self.post(f"/location/exits/{exit_id}/unlock", json=data)
        return APIUnlockResponse.model_validate(response)

    async def get_exit_by_name(
        self,
        zone_id: int,
        exit_name: str,
        include_hidden: bool = False,
    ) -> APIExitWithDestination | None:
        """Find an exit by name (case-insensitive partial match).

        Useful for natural language commands like "go through the tavern door".
        """
        exits = await self.get_exits(zone_id, include_hidden)
        name_lower = exit_name.lower()
        for exit in exits:
            if name_lower in exit.name.lower():
                return exit
        return None

    async def create_zone_with_exits(
        self,
        name: str,
        description: str | None = None,
        entry_description: str | None = None,
        exits: list[dict] | None = None,
    ) -> "APIZoneCreateWithExitsResponse":
        """Create a new zone with bidirectional exits to existing zones.

        This is the recommended way to dynamically create locations during gameplay.

        Args:
            name: Zone name (e.g., "Dark Cave", "Hidden Grove")
            description: General description of the zone
            entry_description: What the player sees when entering (e.g., "Water drips from above...")
            exits: List of exit connections, each with:
                - connect_to_zone_id: ID of existing zone to connect to
                - exit_name: Name of exit FROM connected zone TO new zone
                - exit_description: Description of that exit
                - return_exit_name: Name of exit FROM new zone BACK TO connected zone
                - return_exit_description: Description of return exit
                - hidden: Whether the exit to the new zone is hidden (default False)
                - locked: Whether the exit to the new zone is locked (default False)

        Returns:
            The created zone and all exits created
        """
        from .models import APIZoneCreateWithExitsResponse

        data = {
            "name": name,
            "exits": exits or [],
        }
        if description:
            data["description"] = description
        if entry_description:
            data["entry_description"] = entry_description

        response = await self.post("/location/zones/with-exits", json=data)
        return APIZoneCreateWithExitsResponse.model_validate(response)


class QuestClient(RPGAPIClient):
    """Client for quest-related API endpoints."""

    async def get_quest(self, quest_id: int) -> APIQuest:
        """Get a quest by ID."""
        response = await self.get(f"/quests/{quest_id}")
        return APIQuest.model_validate(response)

    async def list_quests(
        self,
        skip: int = 0,
        limit: int = 100,
        min_level: int | None = None,
        max_level: int | None = None,
    ) -> list[APIQuest]:
        """List all quests with optional level filtering."""
        params = {"skip": skip, "limit": limit}
        if min_level is not None:
            params["min_level"] = min_level
        if max_level is not None:
            params["max_level"] = max_level
        response = await self.get("/quests/", params=params)
        return [APIQuest.model_validate(q) for q in response]

    async def get_available_quests(
        self,
        character_id: int,
        character_level: int = 1,
    ) -> list[APIQuest]:
        """Get quests available for a character.

        Filters out quests the character already has and those above their level.
        """
        # Get all quests within level range
        all_quests = await self.list_quests(max_level=character_level)

        # Get character's current quests
        current_quests = await self.get_character_quests(character_id)
        current_quest_ids = {q.quest_id for q in current_quests}

        # Filter to quests not already assigned
        available = []
        for quest in all_quests:
            if quest.id not in current_quest_ids:
                # Check prerequisites (need to be completed)
                prereqs_met = True
                for prereq_id in quest.prerequisites:
                    prereq_assignment = next(
                        (q for q in current_quests if q.quest_id == prereq_id and q.status == QuestStatus.COMPLETED),
                        None
                    )
                    if not prereq_assignment:
                        prereqs_met = False
                        break
                if prereqs_met:
                    available.append(quest)

        return available

    async def get_character_quests(
        self,
        character_id: int,
        status: str | None = None,
    ) -> list[APIQuestAssignment]:
        """Get all quests assigned to a character."""
        params = {}
        if status:
            params["status"] = status
        response = await self.get(f"/quests/character/{character_id}", params=params)
        return [APIQuestAssignment.model_validate(q) for q in response]

    async def get_active_quests(self, character_id: int) -> list[APIQuestAssignment]:
        """Get character's active (in-progress) quests."""
        return await self.get_character_quests(character_id, status="active")

    async def assign_quest(
        self,
        quest_id: int,
        character_id: int,
    ) -> APIQuestAssignment:
        """Assign a quest to a character."""
        data = {"character_id": character_id}
        response = await self.post(f"/quests/{quest_id}/assign", json=data)
        return APIQuestAssignment.model_validate(response)

    async def update_progress(
        self,
        quest_id: int,
        character_id: int,
        objective_id: int,
        amount: int = 1,
    ) -> APIQuestAssignment:
        """Update progress on a quest objective.

        Args:
            quest_id: The quest ID
            character_id: The character's ID
            objective_id: The objective to update
            amount: Amount to add to current progress (default 1)
        """
        data = {"objective_id": objective_id, "amount": amount}
        response = await self.post(
            f"/quests/{quest_id}/progress",
            json=data,
            params={"character_id": character_id},
        )
        return APIQuestAssignment.model_validate(response)

    async def complete_quest(
        self,
        quest_id: int,
        character_id: int,
    ) -> APIQuestAssignment:
        """Mark a quest as complete (requires all objectives to be done)."""
        response = await self.post(
            f"/quests/{quest_id}/complete",
            params={"character_id": character_id},
        )
        return APIQuestAssignment.model_validate(response)

    async def abandon_quest(
        self,
        quest_id: int,
        character_id: int,
    ) -> APIQuestAssignment:
        """Abandon a quest."""
        response = await self.post(
            f"/quests/{quest_id}/abandon",
            params={"character_id": character_id},
        )
        return APIQuestAssignment.model_validate(response)


class ScenarioClient(RPGAPIClient):
    """Client for scenario (narrative event) API endpoints."""

    async def get_scenario(self, scenario_id: int) -> APIScenario:
        """Get a scenario by ID."""
        response = await self.get(f"/scenario/{scenario_id}")
        return APIScenario.model_validate(response)

    async def list_scenarios(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> list[APIScenario]:
        """List all scenarios."""
        params = {"skip": skip, "limit": limit}
        response = await self.get("/scenario/", params=params)
        return [APIScenario.model_validate(s) for s in response]

    async def evaluate_scenarios(
        self,
        character_id: int,
        trigger_type: str | None = None,
        auto_trigger: bool = False,
    ) -> APIEvaluateScenariosResponse:
        """Evaluate all scenarios for a character.

        Args:
            character_id: Character to evaluate scenarios for
            trigger_type: Optional filter (location, item, quest, health_threshold)
            auto_trigger: If True, automatically trigger first applicable scenario

        Returns:
            List of applicable scenarios and optionally the triggered result
        """
        params = {}
        if trigger_type:
            params["trigger_type"] = trigger_type
        if auto_trigger:
            params["auto_trigger"] = True
        response = await self.get(f"/scenario/evaluate/{character_id}", params=params)
        return APIEvaluateScenariosResponse.model_validate(response)

    async def trigger_scenario(
        self,
        scenario_id: int,
        character_id: int,
        outcome_index: int | None = None,
    ) -> APITriggerScenarioResponse:
        """Trigger a scenario for a character.

        Args:
            scenario_id: Scenario to trigger
            character_id: Character to apply effects to
            outcome_index: Specific outcome to apply (or random if None)

        Returns:
            Trigger result with narrative text and effects applied
        """
        data = {}
        if outcome_index is not None:
            data["outcome_index"] = outcome_index
        response = await self.post(
            f"/scenario/{scenario_id}/trigger/{character_id}",
            json=data,
        )
        return APITriggerScenarioResponse.model_validate(response)

    async def get_character_history(
        self,
        character_id: int,
    ) -> list[APIScenarioHistory]:
        """Get a character's scenario history."""
        response = await self.get(f"/scenario/history/{character_id}")
        return [APIScenarioHistory.model_validate(h) for h in response]

    async def check_location_scenarios(
        self,
        character_id: int,
        auto_trigger: bool = True,
    ) -> APIEvaluateScenariosResponse:
        """Check for location-triggered scenarios.

        Convenience method for checking scenarios when character moves.
        """
        return await self.evaluate_scenarios(character_id, "location", auto_trigger)

    async def check_item_scenarios(
        self,
        character_id: int,
        auto_trigger: bool = True,
    ) -> APIEvaluateScenariosResponse:
        """Check for item-triggered scenarios.

        Convenience method for checking scenarios when inventory changes.
        """
        return await self.evaluate_scenarios(character_id, "item", auto_trigger)


# Convenience function for creating clients with shared settings
def create_clients(base_url: str = "http://localhost:8000") -> dict[str, RPGAPIClient]:
    """Create all API clients with shared base URL."""
    return {
        "character": CharacterClient(base_url),
        "combat": CombatClient(base_url),
        "inventory": InventoryClient(base_url),
        "reference": ReferenceClient(base_url),
        "trade": TradeClient(base_url),
        "location": LocationClient(base_url),
        "quest": QuestClient(base_url),
        "scenario": ScenarioClient(base_url),
    }
