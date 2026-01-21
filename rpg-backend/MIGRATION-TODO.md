# LiveKit Agent → RPG API Migration Plan

This document tracks the migration of the LiveKit RPG Agent (`role-playing/`) to use the tabletop-rpg-api (`src/`) for all game mechanics.

## Overview

**Goal**: Replace embedded game mechanics in the LiveKit agent with API calls to the RPG backend.

**Key Principle**: The agent uses the API ONLY. No dual paths. No legacy fallbacks. The API handles all game rules, dice rolling, combat resolution, and state persistence.

**Status**: ✅ MIGRATION COMPLETE

---

## Phase 1: API Client Foundation ✅ COMPLETE

### 1.1 Create API Client Module ✅
- [x] Create `role-playing/api/__init__.py`
- [x] Create `role-playing/api/client.py` with async HTTP client (httpx)
  - `CharacterClient`: create, get, update, award_xp, add_gold, create_from_monster
  - `CombatClient`: start, get_state, process, act, resolve, finish
  - `InventoryClient`: get_inventory, add_item, remove_item, equip, unequip
  - `ReferenceClient`: get_monsters, get_weapons, get_spells, get_abilities
  - `TradeClient`: propose_trade, check_trade

### 1.2 Create API Response Models ✅
- [x] Create `role-playing/api/models.py` with Pydantic models matching API schemas

### 1.3 Update Configuration ✅
- [x] Add API URL to `role-playing/core/settings.py`

---

## Phase 2: GameUserData Cleanup ✅ COMPLETE

### 2.1 Remove Legacy Fields ✅
- [x] Updated `role-playing/core/game_state.py`:
  - REMOVED: `player_character: Optional[PlayerCharacter]`
  - REMOVED: `current_npcs: List[NPCCharacter]`
  - REMOVED: `combat_state: Optional[CombatState]`
  - KEPT: `player_character_id: Optional[int]`
  - KEPT: `current_npc_ids: List[int]`
  - KEPT: `combat_session_id: Optional[int]`

### 2.2 Remove Legacy Methods from StateService ✅
- [x] Updated `role-playing/core/state_service.py`:
  - REMOVED: `set_player()`, `set_combat_state()`, etc.
  - KEPT: `set_player_id()`, `set_combat_session_id()`, `get_player_async()`, etc.

---

## Phase 3: Character Creation (API Only) ✅ COMPLETE

### 3.1 Clean Up Player Service ✅
- [x] Updated `role-playing/services/player.py`:
  - All functions now use API only
  - `create_player()` - creates character via API
  - `get_player()` - fetches character via API
  - `describe_inventory()` - fetches inventory via API

### 3.2 Clean Up NarratorAgent ✅
- [x] Updated `create_character` tool - API only, no fallbacks
- [x] Updated `check_inventory` tool - API only

---

## Phase 4: Enemy Creation (API Only) ✅ COMPLETE

### 4.1 Clean Up Combat Service ✅
- [x] Updated `role-playing/services/combat.py`:
  - `build_enemy_group()` - creates enemies via API
  - `initialize_combat()` - starts combat via API

### 4.2 Clean Up NarratorAgent start_combat ✅
- [x] Updated `start_combat` tool - API only

---

## Phase 5: Combat System (API Only) ✅ COMPLETE

### 5.1 Rewrite CombatAgent - API Only ✅
- [x] REMOVED: `_is_using_api_combat()` helper
- [x] REMOVED: All legacy branches
- [x] REWROTE: `on_enter()` - API only
- [x] REWROTE: `_process_npc_turns()` - uses API's `/combat/{id}/process`
- [x] REWROTE: `attack()` - API only
- [x] REWROTE: `defend()` - API only
- [x] REWROTE: `cast_spell()` - API only
- [x] REWROTE: `use_combat_item()` - API only
- [x] REWROTE: `flee_combat()` - API only
- [x] REWROTE: `check_combat_status()` - API only
- [x] REWROTE: `_end_combat()` - uses API's resolve + finish

---

## Phase 6: Skill Checks (API Only) ✅ COMPLETE

### 6.1 Clean Up Skill Check Service ✅
- [x] Updated `role-playing/services/skill_checks.py`:
  - `resolve_skill_check()` - now uses API to fetch character stats
  - Takes `character_id` parameter instead of player object

---

## Phase 7: Inventory (API Only) ✅ COMPLETE

### 7.1 Inventory Display ✅
- [x] `describe_inventory()` uses API

### 7.2 Item Use During Exploration ✅
- [x] `use_item()` implemented for API

---

## Phase 8: Trading System ✅ COMPLETE

### 8.1 Trade API ✅
- [x] Created `src/trade/` module in the API
- [x] Created `POST /trade/propose` endpoint
- [x] Created `POST /trade/check` endpoint
- [x] Added TradeClient to API client

### 8.2 Agent Integration ✅
- [x] Updated `role-playing/services/trades.py` to use API
- [x] Updated `trade_with_npc` function tool

---

## Phase 9: RPC Methods ✅ COMPLETE

### 9.1 Update RPC Methods ✅
- [x] Updated `get_game_state()` to fetch from API
- [x] Updated `get_combat_state()` to fetch from API
- [x] Updated `get_inventory()` to fetch from API
- [x] Updated `get_current_context()` to use API state

---

## Phase 10: Final Cleanup ✅ COMPLETE

### 10.1 Delete Legacy Code ✅
- [x] DELETED: `role-playing/game_mechanics.py`
- [x] REMOVED: `from game_mechanics import Combat` in `services/npcs.py`
- [x] REMOVED: `from game_mechanics import GameUtilities` in `services/exploration.py`
- [x] UPDATED: `character.py` - deprecated `attack()`, `defend()`, `cast_spell()`, `attempt_flee()` methods
- [x] UPDATED: `README.md` and `architecture_README.md` documentation

### 10.2 Testing ✅
- [x] Created `role-playing/tests/test_api_integration.py`
- [x] Tests for character creation
- [x] Tests for combat flow
- [x] Tests for inventory
- [x] Tests for skill checks

---

## API Endpoints Reference

### Character
- `POST /character/` - Create player
- `GET /character/{id}` - Get character
- `POST /character/{id}/experience` - Award XP
- `POST /character/from-monster/{monster_id}` - Create enemy

### Inventory
- `GET /character/{id}/inventory` - Get inventory
- `POST /character/{id}/inventory` - Add item
- `POST /character/{id}/inventory/{inv_id}/equip` - Equip

### Combat
- `POST /combat/start` - Start combat
- `GET /combat/{id}` - Get state
- `POST /combat/{id}/act` - Player action
- `POST /combat/{id}/process` - Process NPC turns
- `POST /combat/{id}/resolve` - Calculate rewards
- `POST /combat/{id}/finish` - End combat

### Trade
- `POST /trade/propose` - Propose a trade with NPC
- `POST /trade/check` - Check trade values and DC

---

## Summary of Changes

### Files Created
- `role-playing/api/__init__.py` - API package
- `role-playing/api/client.py` - Async HTTP clients (Character, Combat, Inventory, Reference, Trade)
- `role-playing/api/models.py` - Pydantic response models
- `role-playing/tests/test_api_integration.py` - Integration tests
- `src/trade/__init__.py` - Trade API module
- `src/trade/router.py` - Trade endpoints
- `src/trade/service.py` - Trade business logic
- `src/trade/schemas.py` - Trade request/response schemas

### Files Modified
- `role-playing/core/game_state.py` - Removed legacy fields, uses API IDs only
- `role-playing/core/state_service.py` - Removed legacy methods, uses async API fetches
- `role-playing/core/settings.py` - Added API URL config
- `role-playing/services/player.py` - Fully API-based
- `role-playing/services/combat.py` - Fully API-based
- `role-playing/services/skill_checks.py` - Fully API-based
- `role-playing/services/trades.py` - Fully API-based
- `role-playing/services/npcs.py` - Removed legacy `game_mechanics` import
- `role-playing/services/exploration.py` - Removed legacy `game_mechanics` import, local env descriptions
- `role-playing/agents/narrator_agent.py` - Uses API only
- `role-playing/agents/combat_agent.py` - Complete rewrite for API
- `role-playing/agent.py` - RPC methods fetch from API
- `role-playing/character.py` - Deprecated combat methods (now raise NotImplementedError)
- `role-playing/README.md` - Updated architecture docs
- `role-playing/architecture_README.md` - Updated file tree
- `src/main.py` - Added trade router

### Files Deleted
- `role-playing/game_mechanics.py` - All logic moved to API

---

## Notes

- **NO LEGACY FALLBACKS** - If API fails, show error. Don't fall back to local logic.
- **API must be running** - Agent requires API to function
- **Run tests** with `pytest role-playing/tests/test_api_integration.py -v`
- **Start API** with `uvicorn src.main:app --reload`
- **Start Agent** with `cd role-playing && python agent.py dev`
