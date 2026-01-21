"""
---
title: D&D Role-Playing Game
category: complex-agents
tags: [rpg, game_state, rpc_methods, item_generation, combat_system, npc_interaction]
difficulty: advanced
description: Dungeons & Dragons role-playing game with narrator and combat agents
demonstrates:
  - Complex game state management
  - Multiple RPC methods for game queries
  - Dynamic NPC and item generation
  - Combat system with initiative tracking
  - Character creation and stats management
  - Inventory and equipment system
  - Voice acting for different NPCs
---
"""

import json
import logging
from dotenv import load_dotenv

from livekit.agents import AgentServer, AgentSession, JobContext, cli, inference
from livekit.rtc import RpcInvocationData

from agents.narrator_agent import NarratorAgent
from agents.combat_agent import CombatAgent
from core.game_state import GameUserData
from core.settings import settings
from core.state_service import GameStateService
from services import quests as quest_service
from livekit.plugins import silero, inworld


logger = logging.getLogger("dungeons-and-agents")
logger.setLevel(logging.INFO)

load_dotenv()

server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    """Main entry point for the game (LiveKit Agents 1.3+ style)."""
    ctx.log_context_fields = {"room": ctx.room.name}

    # Connect early so RPC registration can access the local participant safely
    await ctx.connect()

    userdata = GameUserData(ctx=ctx)
    shared_clients = {
        "stt": inference.STT(model="deepgram/nova-3-general"),
        "llm": inference.LLM(model="openai/gpt-4.1"),
        "vad": silero.VAD.load(),
        "narrator_tts": inworld.TTS(model=settings.tts_model, voice=settings.narrator_voice),
        "combat_tts": inworld.TTS(model=settings.tts_model, voice=settings.combat_voice),
    }
    userdata.shared_clients = shared_clients

    async def get_game_state(data: RpcInvocationData) -> str:
        """Get current game state, player stats, and inventory via API."""
        try:
            state = GameStateService(userdata)

            # Get quest state from API
            quest_state = {}
            if state.player_id:
                try:
                    quest_state = await quest_service.serialize_quest_state(state.player_id)
                except Exception:
                    pass

            response = {
                "success": True,
                "data": {
                    "game_state": userdata.game_state.value,
                    "player": None,
                    "inventory": [],
                    "equipped": {"weapon": None, "armor": None},
                    "story_state": quest_state,
                },
            }

            if state.player_id:
                # Fetch player from API
                player = await state.get_player_async()
                if player:
                    response["data"]["player"] = {
                        "name": player.name,
                        "class": player.character_class.value,
                        "level": player.level,
                        "current_health": player.current_hp,
                        "max_health": player.max_hp,
                        "ac": player.armor_class,
                        "gold": player.gold,
                        "experience": player.experience,
                        "stats": {
                            "strength": player.strength,
                            "dexterity": player.dexterity,
                            "constitution": player.constitution,
                            "intelligence": player.intelligence,
                            "wisdom": player.wisdom,
                            "charisma": player.charisma,
                        },
                    }

                    # Fetch inventory from API
                    from api.client import InventoryClient
                    inv_client = InventoryClient(
                        base_url=settings.rpg_api_base_url,
                        timeout=settings.rpg_api_timeout,
                    )
                    inventory = await inv_client.get_inventory(state.player_id)

                    for inv_item in inventory:
                        item_data = {
                            "name": inv_item.item.name,
                            "type": inv_item.item.item_type.value,
                            "quantity": inv_item.quantity,
                            "description": inv_item.item.description or "",
                            "properties": inv_item.item.properties,
                            "equipped": inv_item.equipped,
                            "equipment_slot": inv_item.equipment_slot,
                        }
                        response["data"]["inventory"].append(item_data)

                        # Track equipped items
                        if inv_item.equipped:
                            if inv_item.item.item_type.value == "weapon":
                                response["data"]["equipped"]["weapon"] = inv_item.item.name
                            elif inv_item.item.item_type.value == "armor":
                                response["data"]["equipped"]["armor"] = inv_item.item.name

            return json.dumps(response)
        except Exception as e:
            logger.error(f"Error in get_game_state RPC: {e}")
            return json.dumps({"success": False, "error": str(e)})

    async def get_combat_state(data: RpcInvocationData) -> str:
        """Get current combat state via API."""
        try:
            state = GameStateService(userdata)

            response = {
                "success": True,
                "data": {
                    "in_combat": state.has_combat(),
                    "combat": None,
                },
            }

            if state.combat_session_id:
                # Fetch combat state from API
                combat = await state.get_combat_async()
                if combat:
                    response["data"]["combat"] = {
                        "round": combat.round_number,
                        "current_turn": combat.current_turn,
                        "status": combat.status.value,
                        "turn_order": [c.name for c in combat.combatants],
                        "participants": [],
                    }

                    for combatant in combat.combatants:
                        participant_data = {
                            "id": combatant.id,
                            "name": combatant.name,
                            "type": "player" if combatant.is_player else "enemy",
                            "current_health": combatant.current_hp,
                            "max_health": combatant.max_hp,
                            "ac": combatant.armor_class,
                            "initiative": combatant.initiative,
                            "is_alive": combatant.is_alive,
                            "is_current_turn": (
                                combat.current_combatant and
                                combatant.id == combat.current_combatant.id
                            ),
                        }
                        response["data"]["combat"]["participants"].append(participant_data)

            return json.dumps(response)
        except Exception as e:
            logger.error(f"Error in get_combat_state RPC: {e}")
            return json.dumps({"success": False, "error": str(e)})

    async def get_inventory(data: RpcInvocationData) -> str:
        """Get detailed inventory information via API."""
        try:
            state = GameStateService(userdata)

            response = {
                "success": True,
                "data": {
                    "inventory": [],
                    "equipped": {"weapon": None, "armor": None},
                    "gold": 0,
                },
            }

            if state.player_id:
                player = await state.get_player_async()
                if player:
                    response["data"]["gold"] = player.gold

                # Fetch inventory from API
                from api.client import InventoryClient
                inv_client = InventoryClient(
                    base_url=settings.rpg_api_base_url,
                    timeout=settings.rpg_api_timeout,
                )
                inventory = await inv_client.get_inventory(state.player_id)

                for inv_item in inventory:
                    item_data = {
                        "id": inv_item.id,
                        "name": inv_item.item.name,
                        "type": inv_item.item.item_type.value,
                        "quantity": inv_item.quantity,
                        "description": inv_item.item.description or "",
                        "properties": inv_item.item.properties,
                        "is_equipped": inv_item.equipped,
                        "equipment_slot": inv_item.equipment_slot,
                    }
                    response["data"]["inventory"].append(item_data)

                    # Track equipped items
                    if inv_item.equipped:
                        item_type = inv_item.item.item_type.value
                        if item_type == "weapon":
                            response["data"]["equipped"]["weapon"] = {
                                "name": inv_item.item.name,
                                "damage": inv_item.item.properties.get("damage_dice", "1d4"),
                            }
                        elif item_type == "armor":
                            response["data"]["equipped"]["armor"] = {
                                "name": inv_item.item.name,
                                "ac": inv_item.item.properties.get("armor_bonus", 10),
                            }

            return json.dumps(response)
        except Exception as e:
            logger.error(f"Error in get_inventory RPC: {e}")
            return json.dumps({"success": False, "error": str(e)})

    async def get_current_context(data: RpcInvocationData) -> str:
        """Get current conversation context (agent type, voice acting character, etc)."""
        try:
            state = GameStateService(userdata)

            logger.info(
                f"get_current_context called - voice_acting_character: {userdata.voice_acting_character if userdata.voice_acting_character else 'None'}"
            )

            response = {
                "success": True,
                "data": {
                    "agent_type": userdata.current_agent_type.value,
                    "game_state": userdata.game_state.value,
                    "voice_acting_character": userdata.voice_acting_character,
                    "in_combat": state.has_combat(),
                    "player_id": state.player_id,
                    "combat_session_id": state.combat_session_id,
                },
            }

            logger.info(
                f"Returning context with voice_acting_character: {response['data']['voice_acting_character']}"
            )

            return json.dumps(response)
        except Exception as e:
            logger.error(f"Error in get_current_context RPC: {e}")
            return json.dumps({"success": False, "error": str(e)})

    session = AgentSession[GameUserData](userdata=userdata)
    userdata.session = session

    ctx.room.local_participant.register_rpc_method("get_game_state", get_game_state)
    ctx.room.local_participant.register_rpc_method("get_combat_state", get_combat_state)
    ctx.room.local_participant.register_rpc_method("get_inventory", get_inventory)
    ctx.room.local_participant.register_rpc_method(
        "get_current_context", get_current_context
    )

    logger.info(
        "RPC methods registered: get_game_state, get_combat_state, get_inventory, get_current_context"
    )

    await session.start(agent=NarratorAgent(shared_clients=shared_clients), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)
