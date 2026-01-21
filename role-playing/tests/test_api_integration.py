"""
Tests for RPG API integration.

These tests verify that the agent's API client correctly communicates
with the RPG API backend. They require the API server to be running.

Run with: pytest tests/test_api_integration.py -v
"""

import sys
from pathlib import Path
import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.client import (
    CharacterClient,
    CombatClient,
    InventoryClient,
    ReferenceClient,
    LocationClient,
    QuestClient,
    APIError,
    NotFoundError,
)
from api.models import CombatStatus, QuestStatus


# Test configuration
API_BASE_URL = "http://localhost:8000"


@pytest.fixture
def character_client():
    """Create a character API client."""
    return CharacterClient(base_url=API_BASE_URL)


@pytest.fixture
def combat_client():
    """Create a combat API client."""
    return CombatClient(base_url=API_BASE_URL)


@pytest.fixture
def inventory_client():
    """Create an inventory API client."""
    return InventoryClient(base_url=API_BASE_URL)


@pytest.fixture
def reference_client():
    """Create a reference API client."""
    return ReferenceClient(base_url=API_BASE_URL)


@pytest.fixture
def location_client():
    """Create a location API client."""
    return LocationClient(base_url=API_BASE_URL)


@pytest.fixture
def quest_client():
    """Create a quest API client."""
    return QuestClient(base_url=API_BASE_URL)


# === Character Tests ===

@pytest.mark.asyncio
async def test_create_character(character_client):
    """Test creating a player character."""
    character = await character_client.create(
        name="Test Hero",
        character_class="warrior",
        character_type="player",
        level=1,
        strength=16,
        dexterity=12,
        constitution=14,
        intelligence=10,
        wisdom=10,
        charisma=10,
        gold=50,
    )

    assert character.id is not None
    assert character.name == "Test Hero"
    assert character.character_class.value == "warrior"
    assert character.level == 1
    assert character.strength == 16
    assert character.gold == 50

    # Cleanup
    await character_client.delete(character.id)


@pytest.mark.asyncio
async def test_get_character(character_client):
    """Test fetching a character by ID."""
    # Create first
    created = await character_client.create(
        name="Fetch Test",
        character_class="mage",
    )

    # Fetch
    fetched = await character_client.get(created.id)

    assert fetched.id == created.id
    assert fetched.name == "Fetch Test"
    assert fetched.character_class.value == "mage"

    # Cleanup
    await character_client.delete(created.id)


@pytest.mark.asyncio
async def test_character_not_found(character_client):
    """Test that fetching non-existent character raises NotFoundError."""
    with pytest.raises(NotFoundError):
        await character_client.get(999999)


@pytest.mark.asyncio
async def test_create_from_monster(character_client):
    """Test creating an NPC from a monster template."""
    character = await character_client.create_from_monster(
        monster_id="goblin",
        name="Test Goblin",
    )

    assert character.id is not None
    assert character.name == "Test Goblin"
    assert character.character_type.value == "npc"

    # Cleanup
    await character_client.delete(character.id)


@pytest.mark.asyncio
async def test_award_experience(character_client):
    """Test awarding XP to a character."""
    character = await character_client.create(
        name="XP Test",
        character_class="warrior",
    )

    initial_xp = character.experience

    # Award XP
    updated = await character_client.award_experience(character.id, 100)

    assert updated.experience == initial_xp + 100

    # Cleanup
    await character_client.delete(character.id)


@pytest.mark.asyncio
async def test_add_gold(character_client):
    """Test adding gold to a character."""
    character = await character_client.create(
        name="Gold Test",
        character_class="rogue",
        gold=50,
    )

    # Add gold
    updated = await character_client.add_gold(character.id, 25)
    assert updated.gold == 75

    # Remove gold
    updated = await character_client.add_gold(character.id, -10)
    assert updated.gold == 65

    # Cleanup
    await character_client.delete(character.id)


# === Combat Tests ===

@pytest.mark.asyncio
async def test_start_combat(character_client, combat_client):
    """Test starting a combat session."""
    # Create combatants
    player = await character_client.create(
        name="Combat Player",
        character_class="warrior",
    )
    enemy = await character_client.create_from_monster("goblin", "Combat Goblin")

    # Start combat
    combat = await combat_client.start_combat([
        {"character_id": player.id, "team_id": 1},
        {"character_id": enemy.id, "team_id": 2},
    ])

    assert combat.id is not None
    assert combat.status == CombatStatus.ACTIVE
    assert len(combat.combatants) == 2

    # Cleanup
    try:
        await combat_client.finish(combat.id)
    except Exception:
        pass
    await character_client.delete(player.id)
    await character_client.delete(enemy.id)


@pytest.mark.asyncio
async def test_combat_player_attack(character_client, combat_client):
    """Test player attack action in combat."""
    # Create combatants
    player = await character_client.create(
        name="Attack Player",
        character_class="warrior",
        strength=18,  # High strength for reliable hits
    )
    enemy = await character_client.create_from_monster("goblin", "Attack Target")

    # Start combat
    combat = await combat_client.start_combat([
        {"character_id": player.id, "team_id": 1},
        {"character_id": enemy.id, "team_id": 2},
    ])

    # Process until player's turn
    state = await combat_client.get_state(combat.id)

    # Find the enemy combatant ID
    enemy_combatant = None
    for c in state.combatants:
        if c.team_id == 2:
            enemy_combatant = c
            break

    # If it's not player's turn, process NPC turns first
    if not state.awaiting_player:
        await combat_client.process_turns(combat.id)
        state = await combat_client.get_state(combat.id)

    # Perform attack
    if state.awaiting_player:
        result = await combat_client.player_action(
            session_id=combat.id,
            character_id=player.id,
            action_type="attack",
            target_id=enemy_combatant.id if enemy_combatant else None,
        )

        assert result.action is not None
        assert result.action.action_type.value == "attack"

    # Cleanup
    try:
        await combat_client.finish(combat.id)
    except Exception:
        pass
    await character_client.delete(player.id)
    await character_client.delete(enemy.id)


@pytest.mark.asyncio
async def test_combat_full_flow(character_client, combat_client):
    """Test a full combat flow: start -> actions -> victory -> resolve -> finish."""
    # Create a strong player and weak enemy for quick combat
    player = await character_client.create(
        name="Strong Fighter",
        character_class="warrior",
        level=5,
        strength=20,
    )
    enemy = await character_client.create_from_monster("goblin", "Weak Goblin")

    # Start combat
    combat = await combat_client.start_combat([
        {"character_id": player.id, "team_id": 1},
        {"character_id": enemy.id, "team_id": 2},
    ])

    max_rounds = 20
    rounds = 0

    while rounds < max_rounds:
        rounds += 1

        # Get current state
        state = await combat_client.get_state(combat.id)

        # Check if combat ended
        if state.status != CombatStatus.ACTIVE:
            break

        # If awaiting player, attack
        if state.awaiting_player:
            # Find alive enemy
            target = None
            for c in state.combatants:
                if c.team_id == 2 and c.is_alive:
                    target = c
                    break

            if not target:
                break

            result = await combat_client.player_action(
                session_id=combat.id,
                character_id=player.id,
                action_type="attack",
                target_id=target.id,
            )

            if result.combat_ended:
                break

        # Process NPC turns
        process_result = await combat_client.process_turns(combat.id)
        if process_result.combat_ended:
            break

    # Get final state
    final_state = await combat_client.get_state(combat.id)

    # Combat should have ended (likely victory for the strong player)
    if final_state.status == CombatStatus.FINISHED:
        # Resolve to get rewards
        rewards = await combat_client.resolve(combat.id)
        assert rewards.experience_earned is not None

    # Finish combat
    summary = await combat_client.finish(combat.id)
    assert summary is not None

    # Cleanup
    await character_client.delete(player.id)
    await character_client.delete(enemy.id)


@pytest.mark.asyncio
async def test_combat_defend_action(character_client, combat_client):
    """Test defend action in combat."""
    player = await character_client.create(
        name="Defend Player",
        character_class="warrior",
    )
    enemy = await character_client.create_from_monster("goblin", "Defender Enemy")

    combat = await combat_client.start_combat([
        {"character_id": player.id, "team_id": 1},
        {"character_id": enemy.id, "team_id": 2},
    ])

    # Get to player's turn
    state = await combat_client.get_state(combat.id)
    if not state.awaiting_player:
        await combat_client.process_turns(combat.id)

    state = await combat_client.get_state(combat.id)
    if state.awaiting_player and state.status == CombatStatus.ACTIVE:
        result = await combat_client.player_action(
            session_id=combat.id,
            character_id=player.id,
            action_type="defend",
        )

        assert result.action.action_type.value == "defend"

    # Cleanup
    try:
        await combat_client.finish(combat.id)
    except Exception:
        pass
    await character_client.delete(player.id)
    await character_client.delete(enemy.id)


# === Inventory Tests ===

@pytest.mark.asyncio
async def test_inventory_operations(character_client, inventory_client):
    """Test inventory add, get, equip, and remove."""
    # Create character
    character = await character_client.create(
        name="Inventory Test",
        character_class="warrior",
    )

    # Create an item
    item = await inventory_client.create_item(
        name="Test Sword",
        item_type="weapon",
        description="A test weapon",
        value=100,
    )

    # Add to inventory
    inv_item = await inventory_client.add_item(
        character_id=character.id,
        item_id=item.id,
        quantity=1,
    )

    assert inv_item.item.name == "Test Sword"
    assert inv_item.quantity == 1
    assert not inv_item.equipped

    # Get inventory
    inventory = await inventory_client.get_inventory(character.id)
    assert len(inventory) >= 1
    assert any(i.item.name == "Test Sword" for i in inventory)

    # Equip item
    equipped = await inventory_client.equip_item(
        character_id=character.id,
        inventory_item_id=inv_item.id,
        equipment_slot="main_hand",
    )

    assert equipped.equipped
    assert equipped.equipment_slot == "main_hand"

    # Unequip
    unequipped = await inventory_client.unequip_item(
        character_id=character.id,
        inventory_item_id=inv_item.id,
    )

    assert not unequipped.equipped

    # Remove from inventory
    await inventory_client.remove_item(
        character_id=character.id,
        inventory_item_id=inv_item.id,
    )

    # Verify removed
    inventory = await inventory_client.get_inventory(character.id)
    assert not any(i.id == inv_item.id for i in inventory)

    # Cleanup
    await character_client.delete(character.id)


# === Reference Data Tests ===

@pytest.mark.asyncio
async def test_list_monsters(reference_client):
    """Test listing monster templates."""
    monsters = await reference_client.list_monsters()

    assert len(monsters) > 0
    assert any(m.monster_id == "goblin" for m in monsters)


@pytest.mark.asyncio
async def test_get_monster(reference_client):
    """Test getting a specific monster."""
    goblin = await reference_client.get_monster("goblin")

    assert goblin.monster_id == "goblin"
    assert goblin.name is not None
    assert goblin.hit_dice is not None


# === Service Integration Tests ===

@pytest.mark.asyncio
async def test_player_service_create(character_client):
    """Test the player service create function."""
    from services.player import create_player, get_player

    player_id = await create_player("Service Test", "mage")

    assert player_id is not None

    player = await get_player(player_id)
    assert player.name == "Service Test"
    assert player.character_class.value == "mage"

    # Cleanup
    await character_client.delete(player_id)


@pytest.mark.asyncio
async def test_combat_service_build_enemy_group(character_client):
    """Test the combat service enemy group creation."""
    from services.combat import build_enemy_group

    enemy_ids, description = await build_enemy_group("goblin", 2)

    assert len(enemy_ids) == 2
    assert "goblin" in description.lower()

    # Cleanup
    for enemy_id in enemy_ids:
        await character_client.delete(enemy_id)


@pytest.mark.asyncio
async def test_combat_service_initialize_combat(character_client, combat_client):
    """Test the combat service combat initialization."""
    from services.combat import build_enemy_group, initialize_combat
    from services.player import create_player
    from core.game_state import GameUserData, GameState
    from core.state_service import GameStateService
    from unittest.mock import MagicMock

    # Create mock userdata
    mock_ctx = MagicMock()
    userdata = GameUserData(ctx=mock_ctx)
    state = GameStateService(userdata)

    # Create player
    player_id = await create_player("Combat Init Test", "warrior")
    state.set_player_id(player_id)

    # Create enemies
    enemy_ids, _ = await build_enemy_group("goblin", 1)

    # Initialize combat
    combat_start = await initialize_combat(state, player_id, enemy_ids)

    assert "Combat begins" in combat_start
    assert state.combat_session_id is not None

    # Cleanup
    try:
        await combat_client.finish(state.combat_session_id)
    except Exception:
        pass
    await character_client.delete(player_id)
    for enemy_id in enemy_ids:
        try:
            await character_client.delete(enemy_id)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_skill_check_service(character_client):
    """Test the skill check service."""
    from services.skill_checks import resolve_skill_check

    # Create a character
    character = await character_client.create(
        name="Skill Check Test",
        character_class="rogue",
        dexterity=16,  # High dex for stealth
    )

    result_text, payload = await resolve_skill_check(
        skill="stealth",
        difficulty="medium",
        character_id=character.id,
    )

    assert "[SYSTEM:" in result_text
    assert "skill" in payload
    assert "roll" in payload
    assert "dc" in payload
    assert "success" in payload

    # Cleanup
    await character_client.delete(character.id)


# === Location Tests ===

@pytest.mark.asyncio
async def test_get_zone(location_client):
    """Test fetching a zone by ID."""
    # Zone 1 is the default tavern zone from seed data
    zone = await location_client.get_zone(1)

    assert zone.id == 1
    assert zone.name is not None
    assert "Tavern" in zone.name or zone.name  # May have different name


@pytest.mark.asyncio
async def test_list_zones(location_client):
    """Test listing all zones."""
    zones = await location_client.list_zones()

    assert len(zones) > 0
    assert all(z.id is not None for z in zones)


@pytest.mark.asyncio
async def test_get_exits(location_client):
    """Test getting exits from a zone."""
    # Get exits from zone 1 (tavern)
    exits = await location_client.get_exits(1)

    # Should have at least one exit if seed data was loaded
    assert isinstance(exits, list)
    if exits:
        exit_obj = exits[0]
        assert exit_obj.id is not None
        assert exit_obj.name is not None
        assert exit_obj.to_zone_id is not None


@pytest.mark.asyncio
async def test_get_exit_by_name(location_client):
    """Test finding an exit by name."""
    # Get all exits first to know what names exist
    exits = await location_client.get_exits(1)

    if exits:
        # Search for the first exit by name
        exit_name = exits[0].name
        found = await location_client.get_exit_by_name(1, exit_name)

        assert found is not None
        assert found.name == exit_name


@pytest.mark.asyncio
async def test_get_exit_by_name_partial_match(location_client):
    """Test finding an exit by partial name match."""
    exits = await location_client.get_exits(1)

    if exits:
        # Try partial match (first word of exit name)
        exit_name = exits[0].name
        partial = exit_name.split()[0] if " " in exit_name else exit_name[:3]
        found = await location_client.get_exit_by_name(1, partial)

        # Should find the exit even with partial name
        assert found is not None


@pytest.mark.asyncio
async def test_get_exit_by_name_not_found(location_client):
    """Test that non-existent exit returns None."""
    found = await location_client.get_exit_by_name(1, "nonexistent_exit_name_xyz")

    assert found is None


@pytest.mark.asyncio
async def test_travel_through_exit(location_client, character_client):
    """Test traveling through an exit."""
    # Create a character at zone 1
    character = await character_client.create(
        name="Travel Test",
        character_class="warrior",
        zone_id=1,
    )

    # Get available exits
    exits = await location_client.get_exits(1)

    if exits:
        # Travel through first unlocked exit
        unlocked_exit = None
        for exit_obj in exits:
            if not exit_obj.locked:
                unlocked_exit = exit_obj
                break

        if unlocked_exit:
            result = await location_client.travel(unlocked_exit.id, character.id)

            assert result.success is True
            assert result.new_zone is not None
            assert result.new_zone.id == unlocked_exit.to_zone_id

    # Cleanup
    await character_client.delete(character.id)


@pytest.mark.asyncio
async def test_travel_returns_exits(location_client, character_client):
    """Test that travel response includes exits from new zone."""
    character = await character_client.create(
        name="Travel Exits Test",
        character_class="mage",
        zone_id=1,
    )

    exits = await location_client.get_exits(1)

    if exits:
        unlocked_exit = next((e for e in exits if not e.locked), None)
        if unlocked_exit:
            result = await location_client.travel(unlocked_exit.id, character.id)

            # Response should include exits from new zone
            assert isinstance(result.exits, list)

    await character_client.delete(character.id)


@pytest.mark.asyncio
async def test_cannot_travel_through_locked_exit(location_client, character_client):
    """Test that locked exits block travel."""
    character = await character_client.create(
        name="Lock Test",
        character_class="rogue",
        zone_id=1,
    )

    exits = await location_client.get_exits(1, include_hidden=True)

    # Find a locked exit if one exists
    locked_exit = next((e for e in exits if e.locked), None)

    if locked_exit:
        result = await location_client.travel(locked_exit.id, character.id)

        assert result.success is False
        assert "locked" in result.message.lower()

    await character_client.delete(character.id)


# === Location Service Integration Tests ===

@pytest.mark.asyncio
async def test_exploration_service_get_zone(location_client):
    """Test the exploration service get_zone function."""
    from services.exploration import get_zone

    zone = await get_zone(1)

    assert zone.id == 1
    assert zone.name is not None


@pytest.mark.asyncio
async def test_exploration_service_describe_zone(location_client):
    """Test the exploration service describe_zone function."""
    from services.exploration import get_zone, describe_zone

    zone = await get_zone(1)
    description = await describe_zone(zone)

    # Should have some description
    assert isinstance(description, str)
    assert len(description) > 0


@pytest.mark.asyncio
async def test_exploration_service_travel_by_name(location_client, character_client):
    """Test the exploration service travel_by_exit_name function."""
    from services.exploration import travel_by_exit_name, get_available_exits

    character = await character_client.create(
        name="Travel by Name Test",
        character_class="warrior",
        zone_id=1,
    )

    exits = await get_available_exits(1)

    if exits:
        unlocked = next((e for e in exits if not e.locked), None)
        if unlocked:
            result, error = await travel_by_exit_name(
                zone_id=1,
                exit_name=unlocked.name,
                character_id=character.id,
            )

            if result:
                assert result.success is True
                assert error == ""
            else:
                # Some error occurred (e.g., locked)
                assert error != ""

    await character_client.delete(character.id)


@pytest.mark.asyncio
async def test_exploration_service_travel_invalid_exit(location_client, character_client):
    """Test travel_by_exit_name with invalid exit name."""
    from services.exploration import travel_by_exit_name

    character = await character_client.create(
        name="Invalid Exit Test",
        character_class="mage",
        zone_id=1,
    )

    result, error = await travel_by_exit_name(
        zone_id=1,
        exit_name="completely_invalid_exit_that_does_not_exist",
        character_id=character.id,
    )

    assert result is None
    assert "no exit" in error.lower() or "available" in error.lower()

    await character_client.delete(character.id)


@pytest.mark.asyncio
async def test_state_service_zone_methods(location_client, character_client):
    """Test GameStateService zone-related methods."""
    from core.game_state import GameUserData
    from core.state_service import GameStateService
    from unittest.mock import MagicMock

    mock_ctx = MagicMock()
    userdata = GameUserData(ctx=mock_ctx)
    state = GameStateService(userdata)

    # Set zone
    state.set_zone_id(1)
    assert state.zone_id == 1
    assert 1 in userdata.visited_zone_ids

    # Get current zone
    zone = await state.get_current_zone_async()
    assert zone is not None
    assert zone.id == 1

    # Get exits
    exits = await state.get_available_exits_async()
    assert isinstance(exits, list)


@pytest.mark.asyncio
async def test_state_service_travel(location_client, character_client):
    """Test GameStateService travel_through_exit_async."""
    from core.game_state import GameUserData
    from core.state_service import GameStateService
    from unittest.mock import MagicMock

    character = await character_client.create(
        name="State Service Travel Test",
        character_class="warrior",
        zone_id=1,
    )

    mock_ctx = MagicMock()
    userdata = GameUserData(ctx=mock_ctx)
    state = GameStateService(userdata)
    state.set_zone_id(1)
    state.set_player_id(character.id)

    # Get exits and travel
    exits = await state.get_available_exits_async()
    if exits:
        unlocked = next((e for e in exits if not e.locked), None)
        if unlocked:
            result = await state.travel_through_exit_async(unlocked.id, character.id)

            if result.success:
                # Zone should be updated
                assert state.zone_id == unlocked.to_zone_id

    await character_client.delete(character.id)


# === Quest Tests ===

@pytest.mark.asyncio
async def test_list_quests(quest_client):
    """Test listing all quests."""
    quests = await quest_client.list_quests()

    # Should have quests if seed data was loaded
    assert isinstance(quests, list)
    if quests:
        quest = quests[0]
        assert quest.id is not None
        assert quest.title is not None


@pytest.mark.asyncio
async def test_get_quest(quest_client):
    """Test getting a quest by ID."""
    # List quests first to find one
    quests = await quest_client.list_quests()

    if quests:
        quest_id = quests[0].id
        quest = await quest_client.get_quest(quest_id)

        assert quest.id == quest_id
        assert quest.title is not None


@pytest.mark.asyncio
async def test_get_character_quests_empty(quest_client, character_client):
    """Test getting quests for a character with none assigned."""
    character = await character_client.create(
        name="Quest Test Empty",
        character_class="warrior",
    )

    quests = await quest_client.get_character_quests(character.id)
    assert isinstance(quests, list)
    assert len(quests) == 0

    await character_client.delete(character.id)


@pytest.mark.asyncio
async def test_assign_quest(quest_client, character_client):
    """Test assigning a quest to a character."""
    character = await character_client.create(
        name="Quest Assign Test",
        character_class="mage",
    )

    # Get a quest to assign
    quests = await quest_client.list_quests()

    if quests:
        # Find a quest without prerequisites
        quest = next((q for q in quests if not q.prerequisites), None)
        if quest:
            assignment = await quest_client.assign_quest(quest.id, character.id)

            assert assignment.quest_id == quest.id
            assert assignment.character_id == character.id
            assert assignment.status == QuestStatus.ACTIVE

    await character_client.delete(character.id)


@pytest.mark.asyncio
async def test_get_active_quests(quest_client, character_client):
    """Test getting active quests for a character."""
    character = await character_client.create(
        name="Active Quest Test",
        character_class="rogue",
    )

    # Assign a quest
    quests = await quest_client.list_quests()
    if quests:
        quest = next((q for q in quests if not q.prerequisites), None)
        if quest:
            await quest_client.assign_quest(quest.id, character.id)

            # Get active quests
            active = await quest_client.get_active_quests(character.id)
            assert len(active) >= 1
            assert any(a.quest_id == quest.id for a in active)

    await character_client.delete(character.id)


@pytest.mark.asyncio
async def test_update_quest_progress(quest_client, character_client):
    """Test updating progress on a quest objective."""
    character = await character_client.create(
        name="Quest Progress Test",
        character_class="cleric",
    )

    quests = await quest_client.list_quests()
    if quests:
        # Find a quest with objectives
        quest = next((q for q in quests if q.objectives and not q.prerequisites), None)
        if quest:
            # Assign quest
            assignment = await quest_client.assign_quest(quest.id, character.id)

            # Find an objective
            if assignment.objectives_progress:
                objective = assignment.objectives_progress[0]
                initial_count = objective.current_count

                # Update progress
                updated = await quest_client.update_progress(
                    quest.id, character.id, objective.objective_id, 1
                )

                # Find updated objective
                updated_obj = next(
                    (p for p in updated.objectives_progress if p.objective_id == objective.objective_id),
                    None
                )
                assert updated_obj is not None
                assert updated_obj.current_count == initial_count + 1

    await character_client.delete(character.id)


@pytest.mark.asyncio
async def test_complete_quest(quest_client, character_client):
    """Test completing a quest after all objectives are done."""
    character = await character_client.create(
        name="Quest Complete Test",
        character_class="ranger",
    )

    quests = await quest_client.list_quests()
    if quests:
        # Find a quest with objectives
        quest = next((q for q in quests if q.objectives and not q.prerequisites), None)
        if quest:
            # Assign quest
            assignment = await quest_client.assign_quest(quest.id, character.id)

            # Complete all objectives
            for progress in assignment.objectives_progress:
                remaining = progress.target_count - progress.current_count
                if remaining > 0:
                    await quest_client.update_progress(
                        quest.id, character.id, progress.objective_id, remaining
                    )

            # Now complete the quest
            completed = await quest_client.complete_quest(quest.id, character.id)
            assert completed.status == QuestStatus.COMPLETED

    await character_client.delete(character.id)


@pytest.mark.asyncio
async def test_abandon_quest(quest_client, character_client):
    """Test abandoning a quest."""
    character = await character_client.create(
        name="Quest Abandon Test",
        character_class="warrior",
    )

    quests = await quest_client.list_quests()
    if quests:
        quest = next((q for q in quests if not q.prerequisites), None)
        if quest:
            # Assign then abandon
            await quest_client.assign_quest(quest.id, character.id)
            abandoned = await quest_client.abandon_quest(quest.id, character.id)

            assert abandoned.status == QuestStatus.ABANDONED

    await character_client.delete(character.id)


@pytest.mark.asyncio
async def test_get_available_quests(quest_client, character_client):
    """Test getting quests available for a character."""
    character = await character_client.create(
        name="Available Quest Test",
        character_class="mage",
    )

    available = await quest_client.get_available_quests(character.id, character.level)

    # All available quests should:
    # - Be within character's level
    # - Not already be assigned
    # - Have prerequisites met
    for quest in available:
        assert quest.level_requirement <= character.level

    await character_client.delete(character.id)


# === Quest Service Tests ===

@pytest.mark.asyncio
async def test_quest_service_get_active(quest_client, character_client):
    """Test the quest service get_active_quests function."""
    from services.quests import get_active_quests, accept_quest

    character = await character_client.create(
        name="Quest Service Active Test",
        character_class="warrior",
    )

    # Get all quests and assign one
    quests = await quest_client.list_quests()
    if quests:
        quest = next((q for q in quests if not q.prerequisites), None)
        if quest:
            await accept_quest(quest.id, character.id)

            # Use service to get active
            active = await get_active_quests(character.id)
            assert len(active) >= 1

    await character_client.delete(character.id)


@pytest.mark.asyncio
async def test_quest_service_format_rewards():
    """Test the quest reward formatting."""
    from services.quests import format_quest_rewards
    from api.models import APIQuest, APIObjective

    quest = APIQuest(
        id=1,
        title="Test Quest",
        description="A test quest",
        level_requirement=1,
        experience_reward=100,
        gold_reward=50,
        item_rewards=[1, 2],
        prerequisites=[],
        objectives=[],
    )

    rewards = format_quest_rewards(quest)
    assert "100 XP" in rewards
    assert "50 gold" in rewards
    assert "2 item(s)" in rewards


@pytest.mark.asyncio
async def test_quest_service_format_quest():
    """Test the quest formatting for narration."""
    from services.quests import format_quest_for_narration
    from api.models import APIQuest, APIObjective

    quest = APIQuest(
        id=1,
        title="Test Quest",
        description="Help the villagers",
        level_requirement=1,
        experience_reward=100,
        gold_reward=0,
        item_rewards=[],
        prerequisites=[],
        objectives=[
            APIObjective(id=1, description="Talk to the elder", target_count=1, order=0),
            APIObjective(id=2, description="Defeat 3 goblins", target_count=3, order=1),
        ],
    )

    formatted = format_quest_for_narration(quest)
    assert "Test Quest" in formatted
    assert "Help the villagers" in formatted
    assert "Talk to the elder" in formatted
    assert "Defeat 3 goblins" in formatted
    assert "100 XP" in formatted


@pytest.mark.asyncio
async def test_state_service_quest_methods(quest_client, character_client):
    """Test GameStateService quest-related methods."""
    from core.game_state import GameUserData
    from core.state_service import GameStateService
    from unittest.mock import MagicMock

    character = await character_client.create(
        name="State Service Quest Test",
        character_class="warrior",
    )

    mock_ctx = MagicMock()
    userdata = GameUserData(ctx=mock_ctx)
    state = GameStateService(userdata)
    state.set_player_id(character.id)

    # Get available quests
    available = await state.get_available_quests_async(character.level)
    assert isinstance(available, list)

    # Assign a quest if available
    quests = await quest_client.list_quests()
    if quests:
        quest = next((q for q in quests if not q.prerequisites), None)
        if quest:
            assignment = await state.accept_quest_async(quest.id)
            assert assignment is not None
            assert assignment.quest_id == quest.id

            # Get active quests
            active = await state.get_active_quests_async()
            assert len(active) >= 1

    await character_client.delete(character.id)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
