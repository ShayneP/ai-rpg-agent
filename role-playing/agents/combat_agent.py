"""
---
title: Combat Agent
category: complex-agents
tags: [rpg, combat-system, turn-based-combat, npc-ai, function-tools]
difficulty: advanced
description: Specialized agent for handling turn-based combat encounters in RPG games
demonstrates:
  - Turn-based combat management via API
  - NPC AI for automated combat turns
  - Real-time combat state updates via RPC
  - Experience and loot distribution
  - Dynamic combat flow with player/NPC interactions
  - Combat action validation and execution
---
"""

import asyncio
import logging
from typing import TYPE_CHECKING

from livekit.agents.llm import function_tool
from livekit.agents import inference
from livekit.plugins import silero, inworld

from agents.base_agent import BaseGameAgent
from core.game_state import GameState, RunContext_T, GameUserData
from core.settings import settings
from core.state_service import GameStateService
from services import story as story_service
from utils.prompt_loader import load_prompt

logger = logging.getLogger("dungeons-and-agents")

if TYPE_CHECKING:
    from agents.narrator_agent import NarratorAgent


class CombatAgent(BaseGameAgent):
    """Handles combat encounters with fast-paced action.

    All combat is managed via the RPG API. The API is the source of truth.
    """

    def __init__(self, *, shared_clients: dict | None = None, stt=None, llm=None, tts=None, vad=None) -> None:
        shared = shared_clients or {}
        super().__init__(
            instructions=load_prompt('combat_prompt.yaml'),
            stt=stt or shared.get("stt") or inference.STT(model="deepgram/nova-3-general"),
            llm=llm or shared.get("llm") or inference.LLM(model="openai/gpt-4.1-mini"),
            tts=tts
            or shared.get("combat_tts")
            or inworld.TTS(model=settings.tts_model, voice=settings.combat_voice),
            vad=vad or shared.get("vad") or silero.VAD.load()
        )
        self._shared_clients = shared

    async def on_enter(self) -> None:
        """Handle entry into combat agent."""
        await super().on_enter()

        from api.client import CombatClient
        from api.models import CombatStatus

        userdata: GameUserData = self.session.userdata
        state = GameStateService(userdata)

        if not state.combat_session_id:
            logger.error("Combat agent entered but no combat session ID set")
            return

        combat_client = CombatClient(
            base_url=settings.rpg_api_base_url,
            timeout=settings.rpg_api_timeout,
        )

        try:
            # Fetch current combat state
            combat = await combat_client.get_state(state.combat_session_id)
            userdata._combat_cache = combat

            # Check if combat is still active
            if combat.status == CombatStatus.FINISHED:
                logger.info("Combat already completed")
                return

            # Always call _process_npc_turns() to ensure proper state transition
            # This handles both cases:
            # - NPC's turn: processes NPC actions until player turn
            # - Player's turn: sets status to AWAITING_PLAYER and returns
            await self._process_npc_turns()
        except Exception as e:
            logger.error(f"Error entering combat: {e}")

    async def _emit_turn_started(self, combatant, userdata: GameUserData):
        """Emit turn started event for combatant."""
        await self.emit_state_update(
            "turn_started",
            {
                "current": combatant.name,
                "is_player": combatant.is_player,
            },
        )

    async def _process_npc_turns(self) -> bool:
        """Process NPC turns via the API's /combat/{id}/process endpoint.

        Returns:
            True if combat ended, False otherwise
        """
        from api.client import CombatClient
        from api.models import CombatStatus

        userdata: GameUserData = self.session.userdata
        state = GameStateService(userdata)

        combat_client = CombatClient(
            base_url=settings.rpg_api_base_url,
            timeout=settings.rpg_api_timeout,
        )

        try:
            # Call API to process all NPC turns until player's turn
            result = await combat_client.process_turns(state.combat_session_id)
            userdata._combat_cache = None  # Invalidate cache

            # Narrate each NPC action
            for action in result.actions_taken:
                await self._narrate_action(action, result.combatants, is_player=False)

            # Check if combat ended
            if result.combat_ended or result.status == CombatStatus.FINISHED:
                # Determine if player won or lost
                player_alive = any(
                    c.is_player and c.is_alive for c in result.combatants
                )
                if not player_alive:
                    await self._handle_player_defeat()
                return True

            # Emit turn started for the waiting player
            if result.awaiting_player:
                await self._emit_turn_started(result.awaiting_player, userdata)

            await self.emit_state_update("turn_progress", {})
            return False

        except Exception as e:
            logger.error(f"Error processing NPC turns via API: {e}")
            return False

    async def _narrate_action(self, action, combatants, is_player: bool = False):
        """Narrate an action result from the API."""
        # Find actor and target names
        actor_name = "You" if is_player else "Unknown"
        target_name = "Unknown"

        for c in combatants:
            if not is_player and c.id == action.actor_combatant_id:
                actor_name = c.name
            if action.target_combatant_id and c.id == action.target_combatant_id:
                target_name = c.name

        action_type = action.action_type.value

        # Build TTS description based on action type
        if action_type == "attack":
            if action.hit:
                if action.critical:
                    tts_desc = f"Critical hit! {actor_name} strikes {target_name} for {action.damage} damage!"
                elif action.damage and action.damage > 0:
                    if is_player:
                        tts_desc = f"Your attack hits {target_name} for {action.damage} damage!"
                    else:
                        tts_desc = f"{actor_name} hits {target_name} for {action.damage} damage!"
                else:
                    tts_desc = f"{actor_name}'s attack connects but deals no damage!"
            else:
                if is_player:
                    tts_desc = f"{target_name} dodges your attack!"
                else:
                    tts_desc = f"{target_name} dodges {actor_name}'s attack!"
        elif action_type == "defend":
            if is_player:
                tts_desc = "You take a defensive stance, raising your guard!"
            else:
                tts_desc = f"{actor_name} takes a defensive stance!"
        elif action_type == "spell":
            tts_desc = action.description or f"{actor_name} casts a spell!"
        elif action_type == "item":
            tts_desc = action.description or f"{actor_name} uses an item!"
        elif action_type == "flee":
            if action.hit:  # hit means success for flee
                if is_player:
                    tts_desc = "You successfully flee from combat!"
                else:
                    tts_desc = f"{actor_name} flees from combat!"
            else:
                if is_player:
                    tts_desc = "You try to flee but the enemies block your escape!"
                else:
                    tts_desc = f"{actor_name} fails to escape!"
        elif action_type == "ability":
            tts_desc = action.description or f"{actor_name} uses a special ability!"
        else:
            tts_desc = action.description or f"{actor_name} acts!"

        # Emit combat card
        await self._emit_combat_card(
            action=action_type,
            attacker=actor_name,
            target=target_name,
            hit=action.hit or False,
            damage=action.damage or 0,
            description=action.description or tts_desc,
        )

        # Say the action
        self.session.say(tts_desc)
        await asyncio.sleep(1.0)

    async def _emit_combat_card(
        self,
        action: str,
        attacker: str,
        target: str,
        hit: bool,
        damage: int,
        description: str,
    ):
        """Emit a compact combat event payload for UI cards."""
        await self.emit_state_update(
            "combat_card",
            {
                "action": action,
                "attacker": attacker,
                "target": target,
                "hit": hit,
                "damage": damage,
                "description": description,
            },
        )

    async def _handle_player_defeat(self):
        """Handle player defeat."""
        userdata: GameUserData = self.session.userdata
        state = GameStateService(userdata)

        await self.emit_state_update("character_defeated", {
            "character": "player",
            "type": "player"
        })

        state.clear_combat_session(game_over=True)

        logger.info("Player defeated - ending session")
        await self.session.say("Your adventure ends here... Thank you for playing Dungeons and Agents!")
        await self.session.drain()
        await self.session.aclose()

        # Delete the room
        try:
            from livekit import api
            await userdata.ctx.api.room.delete_room(
                api.DeleteRoomRequest(room=userdata.ctx.room.name)
            )
        except Exception as e:
            logger.error(f"Error deleting room: {e}")

    @function_tool
    async def attack(self, context: RunContext_T, target_name: str = None):
        """Attack an enemy"""
        from api.client import CombatClient
        from api.models import CombatStatus

        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.combat_session_id:
            return "You're not in combat!"

        combat_client = CombatClient(
            base_url=settings.rpg_api_base_url,
            timeout=settings.rpg_api_timeout,
        )

        try:
            # Get current combat state
            combat = await combat_client.get_state(state.combat_session_id)

            # Check if it's player's turn
            if not combat.awaiting_player:
                return "It's not your turn!"

            player_combatant = combat.awaiting_player

            # Find target
            enemies = [c for c in combat.combatants if c.team_id != player_combatant.team_id and c.is_alive]
            if not enemies:
                return "No enemies to attack!"

            target = None
            if target_name:
                # Normalize target name for flexible matching
                target_lower = target_name.lower().strip()
                # Convert spoken numbers to digits (e.g., "wolf one" -> "wolf 1")
                number_words = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5"}
                for word, digit in number_words.items():
                    target_lower = target_lower.replace(word, digit)
                # Remove extra spaces
                target_lower = " ".join(target_lower.split())

                for c in enemies:
                    enemy_lower = c.name.lower().strip()
                    # Exact match
                    if enemy_lower == target_lower:
                        target = c
                        break
                    # Partial match (e.g., "wolf" matches "Wolf 1")
                    if target_lower in enemy_lower or enemy_lower in target_lower:
                        target = c
                        break
                    # Match without spaces (e.g., "wolf1" matches "Wolf 1")
                    if enemy_lower.replace(" ", "") == target_lower.replace(" ", ""):
                        target = c
                        break

            if not target:
                target = enemies[0]  # Default to first enemy

            # Submit attack action
            result = await combat_client.player_action(
                session_id=state.combat_session_id,
                character_id=state.player_id,
                action_type="attack",
                target_id=target.id,
            )

            # Narrate the action
            await self._narrate_action(result.action, result.combatants, is_player=True)

            # Check if target was defeated
            target_after = next((c for c in result.combatants if c.id == target.id), None)
            if target_after and not target_after.is_alive:
                await self.emit_state_update("character_defeated", {
                    "character": target.name,
                    "type": "enemy"
                })

            # Check if combat ended
            if result.combat_ended or result.status == CombatStatus.FINISHED:
                return await self._end_combat(context, victory=True)

            # Process NPC turns
            await self._process_npc_turns()

            return None

        except Exception as e:
            logger.error(f"Attack error: {e}")
            return f"Attack failed: {e}"

    @function_tool
    async def defend(self, context: RunContext_T):
        """Take a defensive stance"""
        from api.client import CombatClient
        from api.models import CombatStatus

        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.combat_session_id:
            return "You're not in combat!"

        combat_client = CombatClient(
            base_url=settings.rpg_api_base_url,
            timeout=settings.rpg_api_timeout,
        )

        try:
            combat = await combat_client.get_state(state.combat_session_id)

            if not combat.awaiting_player:
                return "It's not your turn!"

            result = await combat_client.player_action(
                session_id=state.combat_session_id,
                character_id=state.player_id,
                action_type="defend",
            )

            await self._narrate_action(result.action, result.combatants, is_player=True)

            if result.combat_ended or result.status == CombatStatus.FINISHED:
                return await self._end_combat(context, victory=True)

            await self._process_npc_turns()

            return None

        except Exception as e:
            logger.error(f"Defend error: {e}")
            return f"Defend failed: {e}"

    @function_tool
    async def cast_spell(self, context: RunContext_T, spell_name: str, target_name: str = None):
        """Cast a spell"""
        from api.client import CombatClient
        from api.models import CombatStatus

        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.combat_session_id:
            return "You're not in combat!"

        combat_client = CombatClient(
            base_url=settings.rpg_api_base_url,
            timeout=settings.rpg_api_timeout,
        )

        try:
            combat = await combat_client.get_state(state.combat_session_id)

            if not combat.awaiting_player:
                return "It's not your turn!"

            player_combatant = combat.awaiting_player

            # Find target if specified
            target_id = None
            if target_name:
                if target_name.lower() == "self":
                    target_id = player_combatant.id
                else:
                    # Normalize target name for flexible matching
                    target_lower = target_name.lower().strip()
                    number_words = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5"}
                    for word, digit in number_words.items():
                        target_lower = target_lower.replace(word, digit)
                    target_lower = " ".join(target_lower.split())

                    for c in combat.combatants:
                        enemy_lower = c.name.lower().strip()
                        if enemy_lower == target_lower:
                            target_id = c.id
                            break
                        if target_lower in enemy_lower or enemy_lower in target_lower:
                            target_id = c.id
                            break
                        if enemy_lower.replace(" ", "") == target_lower.replace(" ", ""):
                            target_id = c.id
                            break

            result = await combat_client.player_action(
                session_id=state.combat_session_id,
                character_id=state.player_id,
                action_type="spell",
                target_id=target_id,
                spell_name=spell_name,
            )

            await self._narrate_action(result.action, result.combatants, is_player=True)

            # Check for defeated enemies
            for c in combat.combatants:
                if c.team_id != player_combatant.team_id:
                    c_after = next((x for x in result.combatants if x.id == c.id), None)
                    if c_after and not c_after.is_alive and c.is_alive:
                        await self.emit_state_update("character_defeated", {
                            "character": c.name,
                            "type": "enemy"
                        })

            if result.combat_ended or result.status == CombatStatus.FINISHED:
                return await self._end_combat(context, victory=True)

            await self._process_npc_turns()

            return None

        except Exception as e:
            logger.error(f"Spell error: {e}")
            return f"Spell failed: {e}"

    @function_tool
    async def use_combat_item(self, context: RunContext_T, item_name: str):
        """Use an item during combat"""
        from api.client import CombatClient, InventoryClient
        from api.models import CombatStatus

        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.combat_session_id:
            return "You're not in combat!"

        combat_client = CombatClient(
            base_url=settings.rpg_api_base_url,
            timeout=settings.rpg_api_timeout,
        )
        inv_client = InventoryClient(
            base_url=settings.rpg_api_base_url,
            timeout=settings.rpg_api_timeout,
        )

        try:
            combat = await combat_client.get_state(state.combat_session_id)

            if not combat.awaiting_player:
                return "It's not your turn!"

            # Find item in inventory
            inventory = await inv_client.get_inventory(state.player_id)
            item = None
            for inv_item in inventory:
                if inv_item.item.name.lower() == item_name.lower():
                    item = inv_item
                    break

            if not item:
                return f"You don't have a {item_name}!"

            result = await combat_client.player_action(
                session_id=state.combat_session_id,
                character_id=state.player_id,
                action_type="item",
                item_id=item.id,
            )

            await self._narrate_action(result.action, result.combatants, is_player=True)

            if result.combat_ended or result.status == CombatStatus.FINISHED:
                return await self._end_combat(context, victory=True)

            await self._process_npc_turns()

            return None

        except Exception as e:
            logger.error(f"Item use error: {e}")
            return f"Item use failed: {e}"

    @function_tool
    async def flee_combat(self, context: RunContext_T):
        """Attempt to flee from combat"""
        from api.client import CombatClient

        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.combat_session_id:
            return "You're not in combat!"

        combat_client = CombatClient(
            base_url=settings.rpg_api_base_url,
            timeout=settings.rpg_api_timeout,
        )

        try:
            combat = await combat_client.get_state(state.combat_session_id)

            if not combat.awaiting_player:
                return "It's not your turn!"

            result = await combat_client.player_action(
                session_id=state.combat_session_id,
                character_id=state.player_id,
                action_type="flee",
            )

            await self._narrate_action(result.action, result.combatants, is_player=True)

            # Check if flee succeeded (hit means success)
            if result.action.hit:
                return await self._end_combat(context, victory=False, fled=True)

            # Failed - process NPC turns
            await self._process_npc_turns()

            return None

        except Exception as e:
            logger.error(f"Flee error: {e}")
            return f"Flee failed: {e}"

    async def _end_combat(self, context: RunContext_T, victory: bool, fled: bool = False):
        """End combat via API and return to narrator."""
        from api.client import CombatClient, CharacterClient

        userdata = context.userdata
        state = GameStateService(userdata)

        combat_client = CombatClient(
            base_url=settings.rpg_api_base_url,
            timeout=settings.rpg_api_timeout,
        )
        char_client = CharacterClient(
            base_url=settings.rpg_api_base_url,
            timeout=settings.rpg_api_timeout,
        )

        try:
            if victory and not fled:
                # Get combat rewards
                rewards = await combat_client.resolve(state.combat_session_id)

                # Get XP for player
                player_xp = rewards.experience_earned.get(state.player_id, 0)

                # Award XP via API
                level_up_msg = None
                if player_xp > 0:
                    try:
                        await char_client.award_experience(state.player_id, player_xp)
                        # Refresh player cache to get updated level
                        await state.refresh_player_cache()
                    except Exception as e:
                        logger.warning(f"Failed to award XP: {e}")

                # Get loot (gold and items)
                loot = rewards.loot
                loot_items = [{"item_name": item.item_name, "quantity": item.quantity} for item in loot.items] if loot else []
                gold_gained = loot.gold if loot else 0

                # Store combat results for narrator
                state.set_combat_result({
                    "xp_gained": player_xp,
                    "level_up": level_up_msg,
                    "loot": loot_items,
                    "gold_gained": gold_gained,
                    "defeated_enemies": []
                })

                state.add_story_event(f"Won combat - gained {player_xp} XP")

                # Handle story updates for combat victory (quest progress handled by LLM)
                defeated_enemies = [item.item_name for item in loot.items] if loot and loot.items else ["enemy"]
                story_updates = await story_service.handle_combat_victory(
                    state,
                    enemies_defeated=defeated_enemies,
                )
                if story_updates:
                    userdata.pending_story_updates.extend(story_updates)

            elif fled:
                state.add_story_event("Fled from combat")
            else:
                state.set_game_state(GameState.GAME_OVER)

            # Finish combat session in API
            try:
                await combat_client.finish(state.combat_session_id)
            except Exception as e:
                logger.warning(f"Failed to finish combat session: {e}")

            # Clean up state
            state.clear_combat_session(game_over=not (victory or fled))
            state.clear_npc_ids()

            # Store context for narrator
            userdata.prev_chat_ctx_items = self._snapshot_chat_ctx()

            # Switch back to narrator
            from agents.narrator_agent import NarratorAgent
            return NarratorAgent(shared_clients=self._shared_clients)

        except Exception as e:
            logger.error(f"Error ending combat: {e}")
            # Fall back to clearing state
            state.clear_combat_session()
            from agents.narrator_agent import NarratorAgent
            return NarratorAgent(shared_clients=self._shared_clients)

    @function_tool
    async def check_combat_status(self, context: RunContext_T):
        """Check the current combat status"""
        from api.client import CombatClient

        userdata = context.userdata
        state = GameStateService(userdata)

        if not state.combat_session_id:
            return "You're not in combat!"

        combat_client = CombatClient(
            base_url=settings.rpg_api_base_url,
            timeout=settings.rpg_api_timeout,
        )

        try:
            combat = await combat_client.get_state(state.combat_session_id)

            status = f"Round {combat.round_number}\n"
            status += f"Current turn: {combat.current_combatant.name if combat.current_combatant else 'Unknown'}\n\n"

            # Combatant statuses
            for c in combat.combatants:
                health_pct = int((c.current_hp / c.max_hp) * 100) if c.max_hp > 0 else 0
                team = "Ally" if c.is_player else "Enemy"
                alive = "✓" if c.is_alive else "✗"
                status += f"{alive} {c.name} ({team}): {c.current_hp}/{c.max_hp} HP ({health_pct}%)\n"

            return status

        except Exception as e:
            logger.error(f"Error getting combat status: {e}")
            return "Unable to get combat status"
