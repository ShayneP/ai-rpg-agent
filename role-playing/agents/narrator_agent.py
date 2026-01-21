"""
---
title: Narrator Agent
category: complex-agents
tags: [rpg, storytelling, npc-interaction, voice-acting, exploration]
difficulty: advanced
description: Main storytelling agent for RPG games with voice acting and world interaction
demonstrates:
  - Dynamic storytelling and narrative flow
  - Multi-voice character portrayal with TTS switching
  - NPC interaction and dialogue management
  - World exploration and location transitions
  - Character creation and progression
  - Trading and inventory management
  - Skill check resolution and dice rolling
---
"""

import asyncio
import logging
from typing import List, TYPE_CHECKING

from livekit.agents.llm import function_tool
from livekit.agents import inference
from livekit.plugins import silero, inworld

from agents.base_agent import BaseGameAgent
from character import NPCCharacter
from generators.npc_generator import create_npc_by_role
from core.constants import AVAILABLE_TTS_VOICES
from core.game_state import GameState, RunContext_T
from core.settings import settings
from core import updates
from core.state_service import GameStateService
from utils.display import Colors
from utils.prompt_loader import load_prompt
from services.skill_checks import resolve_skill_check
from services.trades import propose_trade
from services.player import create_player, get_player, describe_inventory, use_item
from services.npcs import (
    get_or_create_npc,
    talk_to_npc,
    attack_npc,
    describe_npc_inventory,
)
from services.exploration import (
    get_zone,
    get_starting_zone,
    get_available_exits,
    travel_by_exit_name,
    describe_zone,
    check_for_encounter,
    format_exits_for_narration,
)
from services.combat import build_enemy_group, initialize_combat
from services import story as story_service
from services import quests as quest_service
from services.narration import build_combat_conclusion

VOICE_ACTING_TTS_MODEL = None  # use plugin; model handled by plugin

if TYPE_CHECKING:
    from agents.combat_agent import CombatAgent

logger = logging.getLogger("dungeons-and-agents")


class NarratorAgent(BaseGameAgent):
    """Handles storytelling, exploration, and non-combat interactions.

    All game data is managed via the RPG API. The API is the source of truth.
    """

    def __init__(self, *, shared_clients: dict | None = None, stt=None, llm=None, tts=None, vad=None) -> None:
        shared = shared_clients or {}
        super().__init__(
            instructions=load_prompt('narrator_prompt.yaml'),
            stt=stt or shared.get("stt") or inference.STT(model="deepgram/nova-3-general"),
            llm=llm or shared.get("llm") or inference.LLM(model="openai/gpt-4.1-mini"),
            tts=tts or shared.get("narrator_tts") or inworld.TTS(voice=settings.narrator_voice),
            vad=vad or shared.get("vad") or silero.VAD.load()
        )
        self._shared_clients = shared

    async def _emit_story_updates(self, userdata, story_updates, speak: bool = True) -> str:
        """Record and optionally voice story updates."""
        if not story_updates:
            return ""
        fragments = []
        state = GameStateService(userdata)
        for line in story_updates:
            userdata.add_story_event(line)
            if speak:
                await self.session.say(line)
            else:
                fragments.append(line)
        # Notify frontend about quest progression
        if state.player_id:
            quest_state = await quest_service.serialize_quest_state(state.player_id)
            await self.emit_state_update("story_update", quest_state)
        return " ".join(fragments)

    async def on_enter(self) -> None:
        await super().on_enter()
        userdata = self.session.userdata
        state = GameStateService(userdata)

        # Track if we handled combat ending
        combat_was_just_ended = False

        # Check if we're returning from combat
        if state.combat_just_ended:
            combat_was_just_ended = True
            state.clear_combat_result()

            conclusion = build_combat_conclusion(state.get_combat_result(), userdata.current_location)
            self.session.say(conclusion)

            # Add a small delay before continuing
            await asyncio.sleep(1.0)

        # Continue with normal entry logic
        if state.game_state == GameState.CHARACTER_CREATION:
            self.session.say("Welcome to Dungeons and Agents! Let's create your character. What is your name, brave adventurer?")
        elif state.game_state == GameState.EXPLORATION and not combat_was_just_ended:
            # Only describe location if not returning from combat
            # Get location description from environment utilities
            from services.exploration import describe_location
            location_desc = describe_location(state.location)
            self.session.say(location_desc)

        # Deliver any queued story updates (e.g., combat-completion progress)
        if userdata.pending_story_updates:
            await self._emit_story_updates(userdata, userdata.pending_story_updates)
            userdata.pending_story_updates = []

        # Check for story beats/scenarios tied to the current location
        if state.game_state == GameState.EXPLORATION:
            story_updates = await story_service.handle_location_and_story(state)
            await self._emit_story_updates(userdata, story_updates)

            # Push initial quest state to frontend on game start
            if state.player_id:
                try:
                    quest_state = await quest_service.serialize_quest_state(state.player_id)
                    await self.emit_state_update("story_update", quest_state)
                except Exception:
                    pass

    @function_tool
    async def say_in_character_voice(self, context: RunContext_T, voice: str, dialogue: str, character_name: str):
        """Say dialogue in a specific character voice for NPCs or other characters

        Available voices: Mark, Ashley, Deborah, Olivia, Dennis
        character_name: The name of the character speaking (e.g., "barkeep", "merchant", "goblin")
        """
        # Store the current voice
        original_voice = settings.narrator_voice  # Default narrator voice

        available_voices = settings.available_voices or AVAILABLE_TTS_VOICES
        if voice not in available_voices:
            return f"Voice '{voice}' not available. Choose from: {', '.join(available_voices)}"

        # Update voice acting state and emit portrait change
        userdata = context.userdata
        state = GameStateService(userdata)
        state.set_voice_acting(character_name.lower())
        await self.emit_state_update("voice_acting_start", {
            "character_name": character_name.lower(),
            "voice": voice
        })

        try:
            # Change to the character voice on the plugin TTS
            self.tts.update_options(voice=voice)
            await self.session.say(dialogue)
        finally:
            # Return to narrator voice
            self.tts.update_options(voice=original_voice)

        # Clear voice acting state and emit portrait return
        state.set_voice_acting(None)
        await self.emit_state_update("voice_acting_end", {})

        # Log the voice acting for story context
        userdata.add_story_event(f"{character_name} spoke in {voice}'s voice: '{dialogue}'")

        return f"*{character_name} speaks*"

    @function_tool
    async def create_character(self, context: RunContext_T, name: str, character_class: str = "warrior"):
        """Create a new player character at the start of the game.

        Call this when the player tells you their name and class.
        Valid classes: warrior, mage, rogue, cleric, ranger
        """
        userdata = context.userdata
        state = GameStateService(userdata)

        # Create character via API and store ID
        player_id = await create_player(name, character_class)
        state.set_player_id(player_id)

        # Fetch the created character for display info
        player = await get_player(player_id)
        # Cache it for other methods that need immediate access
        userdata._player_cache = player

        class_name = player.character_class.value

        # Set the starting zone (character is created in zone_id=1, The Stormhaven Tavern)
        state.set_zone_id(player.zone_id, "The Stormhaven Tavern")

        state.set_game_state(GameState.EXPLORATION)
        state.add_story_event(f"{name} the {class_name} begins their adventure")

        # Activate the initial story beat/scenario for the tavern
        story_updates = await story_service.handle_location_and_story(state)
        if story_updates:
            await self._emit_story_updates(userdata, story_updates, speak=False)

        return f"Character created! {name} the {class_name} stands ready. Your journey begins in the Stormhaven Tavern."

    @function_tool
    async def perform_skill_check(self, context: RunContext_T, skill: str, difficulty: str = "medium", context_description: str = ""):
        """Perform a D20 skill check when the player attempts something risky or uncertain.

        Use for: picking locks, persuading NPCs, sneaking, climbing, searching, etc.
        Skills: strength, dexterity, constitution, intelligence, wisdom, charisma,
                athletics, stealth, perception, persuasion, intimidation, deception
        Difficulty: easy, medium, hard, very_hard
        """
        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.has_player():
            return "You need to create a character first!"

        result_text, payload = await resolve_skill_check(skill, difficulty, state.player_id)
        payload["context_description"] = context_description
        state.add_story_event(f"Skill check: {skill} ({difficulty}) - {'Success' if payload['success'] else 'Failure'}")
        await updates.emit_skill_check(self, payload)
        return result_text

    @function_tool
    async def interact_with_npc(self, context: RunContext_T, npc_name: str, action: str = "talk"):
        """Talk to or attack an NPC. ALWAYS call this when the player wants to speak to someone!

        This updates quest progress, may trigger story objectives, and can offer side quests.
        npc_name: The NPC to interact with (e.g., "barkeep", "merchant", "guard")
        action: "talk" to have a conversation, "attack" to start combat
        """
        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.has_player():
            return "You need to create a character first!"

        # Get player for NPC interaction (needed for disposition check)
        player = await state.get_player_async()

        # Find or create NPC (this is still local for friendly NPCs)
        recent_events = state.story_context[-3:] if state.story_context else []
        # Get existing NPCs from dialogue state
        existing_npcs = [state.active_npc] if state.active_npc else []
        npc, npc_created = await get_or_create_npc(npc_name, state.location, recent_events, existing_npcs)

        if action == "talk":
            # Set active NPC and update game state
            state.set_active_npc(npc)
            state.set_game_state(GameState.DIALOGUE)
            logger.info(f"Set active_npc to: {npc.name} (class: {npc.character_class.value})")

            result = f"You see {npc.name}, a {npc.character_class.value}. " if npc_created else ""
            talk_text, reaction = talk_to_npc(npc, player)
            result += talk_text

            state.add_story_event(f"Talked to {npc.name} - reaction: {reaction}")

            # Pass both the generated NPC name and the original requested name
            story_updates = await story_service.handle_npc_interaction(
                npc.name,
                state,
                requested_role=npc_name,
            )
            updates_text = await self._emit_story_updates(userdata, story_updates, speak=False)
            if updates_text:
                result += f" {updates_text}"

            return result

        elif action == "attack":
            # Build attack message
            result = attack_npc(npc, player)

            # Initiate combat with this NPC
            npc.disposition = "hostile"

            # Store the message to say before combat
            self.session.say(result)

            # Create enemy via API from NPC data and start combat
            enemy_ids, _ = await build_enemy_group(
                npc.character_class.value, 1, zone_id=state.zone_id
            )
            if enemy_ids:
                return await self._initiate_combat(context, enemy_ids)
            else:
                return "Failed to initiate combat with this NPC."

        else:
            return f"You can 'talk' to or 'attack' {npc.name}, but '{action}' isn't a valid action."

    @function_tool
    async def end_dialogue(self, context: RunContext_T):
        """End dialogue with current NPC and return to exploration"""
        state = GameStateService(context.userdata)
        if state.active_npc:
            npc_name = state.active_npc.name
            state.set_active_npc(None)
            state.set_game_state(GameState.EXPLORATION)

            return f"You bid farewell to {npc_name} and step back."
        else:
            return "You're not talking to anyone right now."

    @function_tool
    async def get_story_state(self, context: RunContext_T):
        """Summarize active/completed quests for UI or debugging"""
        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.player_id:
            return "No character created yet."

        quest_state = await quest_service.serialize_quest_state(state.player_id)
        active = quest_state.get("active", [])
        completed = quest_state.get("completed", [])

        lines = []
        if active:
            lines.append("Active Quests:")
            for q in active:
                lines.append(f"  - {q['title']}")
                for obj in q.get("objectives", []):
                    status = "[x]" if obj.get("completed") else "[ ]"
                    lines.append(f"      {status} {obj['description']}")
        else:
            lines.append("No active quests.")

        if completed:
            lines.append("")
            lines.append(f"Completed Quests: {len(completed)}")

        return "\n".join(lines)

    # === Quest Management Tools ===

    @function_tool
    async def get_available_quests(self, context: RunContext_T):
        """List quests available for the player to accept.

        Call this to see what quests the player can pick up.
        Returns quest titles, descriptions, and requirements.
        """
        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.player_id:
            return "No character created yet."

        player = await state.get_player_async()
        available = await quest_service.get_available_quests(state.player_id, player.level)

        if not available:
            return "No quests available right now."

        lines = ["Available Quests:"]
        for quest in available:
            lines.append(f"  [{quest.id}] {quest.title}")
            if quest.description:
                lines.append(f"      {quest.description}")
            rewards = quest_service.format_quest_rewards(quest)
            if rewards:
                lines.append(f"      {rewards}")

        return "\n".join(lines)

    @function_tool
    async def get_active_quests(self, context: RunContext_T):
        """Get the player's current active quests with progress.

        IMPORTANT: Call this to check what objectives the player is working on!
        Use this before progressing objectives to see current quest state.
        """
        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.player_id:
            return "No character created yet."

        active = await quest_service.get_active_quests(state.player_id)

        if not active:
            return "No active quests."

        lines = ["Active Quests:"]
        for assignment in active:
            quest = assignment.quest
            lines.append(f"  [{quest.id}] {quest.title}")
            for progress in assignment.objectives_progress:
                status = "[x]" if progress.completed else "[ ]"
                count = f" ({progress.current_count}/{progress.target_count})" if progress.target_count > 1 else ""
                lines.append(f"      {status} [obj:{progress.objective_id}] {progress.description}{count}")

        return "\n".join(lines)

    @function_tool
    async def accept_quest(self, context: RunContext_T, quest_id: int):
        """Accept a quest for the player.

        quest_id: The ID of the quest to accept (from get_available_quests)
        """
        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.player_id:
            return "No character created yet."

        assignment, error = await quest_service.accept_quest(quest_id, state.player_id)
        if error:
            return f"Failed to accept quest: {error}"

        quest = assignment.quest
        state.add_story_event(f"Accepted quest: {quest.title}")

        # Notify frontend
        quest_state = await quest_service.serialize_quest_state(state.player_id)
        await self.emit_state_update("story_update", quest_state)

        return f"Quest accepted: {quest.title}. {quest.description or ''}"

    @function_tool
    async def progress_quest_objective(self, context: RunContext_T, quest_id: int, objective_id: int, amount: int = 1):
        """Update progress on a quest objective.

        IMPORTANT: Call this when gameplay events complete quest objectives!
        - Player talks to barkeep -> progress "talk to barkeep" objective
        - Player enters market -> progress "reach market" objective
        - Player defeats goblins -> progress goblin kill count

        quest_id: The quest ID
        objective_id: The objective ID (from get_active_quests)
        amount: How much to progress (default 1)
        """
        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.player_id:
            return "No character created yet."

        assignment, error = await quest_service.update_quest_progress(
            quest_id, state.player_id, objective_id, amount
        )
        if error:
            return f"Failed to update progress: {error}"

        # Find the updated objective
        updated_obj = next(
            (p for p in assignment.objectives_progress if p.objective_id == objective_id),
            None
        )

        result = ""
        if updated_obj:
            if updated_obj.completed:
                result = f"Objective completed: {updated_obj.description}"
                state.add_story_event(f"Quest objective completed: {updated_obj.description}")
            else:
                result = f"Progress updated: {updated_obj.description} ({updated_obj.current_count}/{updated_obj.target_count})"

        # Notify frontend
        quest_state = await quest_service.serialize_quest_state(state.player_id)
        await self.emit_state_update("story_update", quest_state)

        return result

    @function_tool
    async def complete_quest(self, context: RunContext_T, quest_id: int):
        """Mark a quest as complete and claim rewards.

        Call this when all objectives are done to finish the quest.
        quest_id: The quest ID to complete
        """
        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.player_id:
            return "No character created yet."

        # Get quest info before completing
        active = await quest_service.get_active_quests(state.player_id)
        quest_assignment = next((a for a in active if a.quest.id == quest_id), None)

        if not quest_assignment:
            return f"Quest {quest_id} is not active."

        quest = quest_assignment.quest

        assignment, error = await quest_service.complete_quest(quest_id, state.player_id)
        if error:
            return f"Failed to complete quest: {error}"

        rewards = quest_service.format_quest_rewards(quest)
        state.add_story_event(f"Quest completed: {quest.title}")

        # Notify frontend
        quest_state = await quest_service.serialize_quest_state(state.player_id)
        await self.emit_state_update("story_update", quest_state)

        return f"Quest completed: {quest.title}! {rewards}"

    @function_tool
    async def abandon_quest(self, context: RunContext_T, quest_id: int):
        """Abandon a quest.

        quest_id: The quest ID to abandon
        """
        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.player_id:
            return "No character created yet."

        # Get quest info before abandoning
        active = await quest_service.get_active_quests(state.player_id)
        quest_assignment = next((a for a in active if a.quest.id == quest_id), None)

        if not quest_assignment:
            return f"Quest {quest_id} is not active."

        quest = quest_assignment.quest

        assignment, error = await quest_service.abandon_quest(quest_id, state.player_id)
        if error:
            return f"Failed to abandon quest: {error}"

        state.add_story_event(f"Quest abandoned: {quest.title}")

        # Notify frontend
        quest_state = await quest_service.serialize_quest_state(state.player_id)
        await self.emit_state_update("story_update", quest_state)

        return f"Quest abandoned: {quest.title}"

    @function_tool
    async def explore_area(self, context: RunContext_T, exit_name: str):
        """Move the player through an exit to a new location. ALWAYS call this when the player wants to travel!

        This updates their location, triggers story beats, and can complete quest objectives.
        exit_name: The name of the exit to travel through (e.g., "market gate", "tavern door", "dark stairwell")
        Use look_around first to see available exits if unsure.
        Example: player says "go to the market" -> exit_name="market gate"
        Example: player says "enter the dungeon" -> exit_name="dark stairwell"
        """
        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.has_player():
            return "You need to create a character first!"

        # Ensure we have a current zone
        if state.zone_id is None:
            starting_zone = await get_starting_zone()
            state.set_zone_id(starting_zone.id, starting_zone.name)

        # Clear active NPC when exploring
        if state.active_npc:
            state.set_active_npc(None)

        state.set_game_state(GameState.EXPLORATION)

        # Travel through the exit using API
        travel_result, error = await travel_by_exit_name(
            zone_id=state.zone_id,
            exit_name=exit_name,
            character_id=state.player_id,
        )

        if error:
            return error

        if not travel_result or not travel_result.success:
            return travel_result.message if travel_result else "Failed to travel."

        # Update state with new zone
        new_zone = travel_result.new_zone
        state.set_zone_id(new_zone.id, new_zone.name)
        state.clear_npc_ids()

        # Check for random encounters in the new zone
        enemies = await check_for_encounter(new_zone)
        if enemies:
            # Build enemy group via API
            enemy_type = enemies[0].character_class.value.lower()
            enemy_ids, _ = await build_enemy_group(
                enemy_type, len(enemies), zone_id=state.zone_id
            )
            if enemy_ids:
                return await self._initiate_combat(context, enemy_ids)

        # Get zone description
        location_desc = await describe_zone(new_zone, include_exits=False)

        # Handle story triggers via API (scenarios and quests)
        story_updates = await story_service.handle_location_and_story(state)
        updates_text = await self._emit_story_updates(userdata, story_updates, speak=False)

        # Build response
        response = travel_result.message
        if location_desc and location_desc not in response:
            response += f" {location_desc}"
        if updates_text:
            response += f" {updates_text}"

        # Format available exits
        if travel_result.exits:
            exits_text = format_exits_for_narration(travel_result.exits)
            response += f" {exits_text}"

        return response

    @function_tool
    async def look_around(self, context: RunContext_T):
        """Look around the current location to see available exits and get a description.

        Call this when the player asks "where can I go?" or "what exits are there?" or "look around".
        """
        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.has_player():
            return "You need to create a character first!"

        # Ensure we have a current zone
        if state.zone_id is None:
            starting_zone = await get_starting_zone()
            state.set_zone_id(starting_zone.id, starting_zone.name)

        # Get current zone
        zone = await get_zone(state.zone_id)
        description = await describe_zone(zone, include_exits=True)

        return description

    async def _initiate_combat(self, context: RunContext_T, enemy_ids: List[int]) -> "CombatAgent":
        """Initiate combat via API and switch to combat agent."""
        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.player_id:
            raise ValueError("No player character ID set")

        combat_start = await initialize_combat(state, state.player_id, enemy_ids)
        state.add_story_event(combat_start)
        userdata.prev_chat_ctx_items = self._snapshot_chat_ctx()
        from agents.combat_agent import CombatAgent
        return CombatAgent(shared_clients=self._shared_clients)

    @function_tool
    async def check_inventory(self, context: RunContext_T):
        """Check what items the player is carrying and has equipped.

        Call when the player asks "what do I have?" or "check my inventory"
        """
        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.has_player():
            return "You need to create a character first!"

        return await describe_inventory(state.player_id)

    @function_tool
    async def use_item(self, context: RunContext_T, item_name: str):
        """Use an item from the player's inventory.

        Call when the player wants to use a potion, equip a weapon, etc.
        """
        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.has_player():
            return "You need to create a character first!"

        return await use_item(state.player_id, item_name)

    @function_tool
    async def start_combat(self, context: RunContext_T, enemy_type: str = "goblin", enemy_count: int = 1):
        """Start a combat encounter against enemies.

        Call when the player wants to fight or an enemy attacks them.
        enemy_type: goblin, orc, bandit, skeleton, wolf, dark_mage, rat, zombie, spider, ogre, troll, dragon
        enemy_count: 1-5 enemies
        """
        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.has_player():
            return "You need to create a character first!"

        if state.game_state == GameState.COMBAT:
            return "You're already in combat!"

        # Create enemies via API (in the player's current zone)
        enemy_ids, encounter_desc = await build_enemy_group(
            enemy_type, enemy_count, zone_id=state.zone_id
        )

        if not enemy_ids:
            return "Failed to spawn enemies. Please try again."

        self.session.say(encounter_desc)
        return await self._initiate_combat(context, enemy_ids)

    @function_tool
    async def trade_with_npc(self, context: RunContext_T, npc_id: int, offer_gold: int = 0, request_gold: int = 0):
        """Propose a trade with an NPC - exchange gold.

        Call when the player wants to buy or sell with an NPC.
        npc_id: The NPC's character ID (from API)
        offer_gold: Gold amount the player offers
        request_gold: Gold amount the player wants from NPC

        Note: Item trading requires knowing inventory item IDs. Use check_npc_inventory first.
        """
        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.has_player():
            return "You need to create a character first!"

        return await propose_trade(
            state,
            npc_id=npc_id,
            offer_gold=offer_gold,
            request_gold=request_gold,
        )

    @function_tool
    async def check_npc_inventory(self, context: RunContext_T, npc_name: str):
        """Check what items and gold an NPC has available for trade.

        Call when the player asks what a merchant/NPC is selling or has.
        """
        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.has_player():
            return "You need to create a character first!"

        return await describe_npc_inventory(npc_name, state)

    @function_tool
    async def create_location(
        self,
        context: RunContext_T,
        name: str,
        description: str,
        entry_description: str,
        exit_name: str,
        return_exit_name: str,
        exit_description: str = "",
        return_exit_description: str = "",
        hidden: bool = False,
        locked: bool = False,
    ):
        """Create a new location connected to the current zone.

        IMPORTANT: Call this when the story requires a NEW location that doesn't exist yet.
        For example: NPCs mention a place, quests reference a destination, or players want to explore somewhere new.

        This creates the new zone AND bidirectional exits between it and the current location.

        Args:
            name: The location name (e.g., "The Abandoned Mine", "Healer's Hut")
            description: General description of the place
            entry_description: What the player sees when they arrive (vivid, atmospheric)
            exit_name: Name of exit FROM current zone TO new location (e.g., "mine entrance", "small path")
            return_exit_name: Name of exit FROM new location BACK (e.g., "mine exit", "path to town")
            exit_description: Description of exit to new location (optional)
            return_exit_description: Description of return exit (optional)
            hidden: If True, exit is hidden until discovered (default False)
            locked: If True, exit is locked (default False)

        Example: NPC says "There's a healer in a hut east of town"
        -> create_location(
            name="Healer's Hut",
            description="A small wooden hut with herbs drying in the windows.",
            entry_description="The smell of medicinal herbs fills the air. An elderly woman looks up from her mortar and pestle.",
            exit_name="path to healer's hut",
            return_exit_name="path back to market",
            exit_description="A narrow trail leads east through the grass."
        )
        """
        from api.client import LocationClient
        from core.settings import settings

        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.has_player():
            return "You need to create a character first!"

        # Ensure we have a current zone
        if state.zone_id is None:
            starting_zone = await get_starting_zone()
            state.set_zone_id(starting_zone.id, starting_zone.name)

        client = LocationClient(
            base_url=settings.rpg_api_base_url,
            timeout=settings.rpg_api_timeout,
        )

        try:
            result = await client.create_zone_with_exits(
                name=name,
                description=description,
                entry_description=entry_description,
                exits=[{
                    "connect_to_zone_id": state.zone_id,
                    "exit_name": exit_name,
                    "exit_description": exit_description or f"A path leads to {name}.",
                    "return_exit_name": return_exit_name,
                    "return_exit_description": return_exit_description or f"A path leads back to {state.location}.",
                    "hidden": hidden,
                    "locked": locked,
                }]
            )

            state.add_story_event(f"Discovered new location: {name}")
            logger.info(f"Created new location '{name}' (zone {result.zone.id}) connected to zone {state.zone_id}")

            return f"New location '{name}' is now accessible via '{exit_name}' from {state.location}."

        except Exception as e:
            logger.error(f"Failed to create location '{name}': {e}")
            return f"Failed to create the location: {e}"
