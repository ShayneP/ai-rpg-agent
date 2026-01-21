"""
Trade services using the RPG API.

All trade operations go through the API. The API is the source of truth.
"""

from typing import Optional

from core.state_service import GameStateService
from core.settings import settings


async def propose_trade(
    state: GameStateService,
    npc_id: int,
    offer_item_id: Optional[int] = None,
    offer_gold: int = 0,
    request_item_id: Optional[int] = None,
    request_gold: int = 0,
) -> str:
    """
    Propose a trade with an NPC via the API.

    Args:
        state: GameStateService for getting player ID
        npc_id: The NPC character ID to trade with
        offer_item_id: Optional inventory item ID to offer
        offer_gold: Gold amount to offer
        request_item_id: Optional NPC inventory item ID to request
        request_gold: Gold amount to request

    Returns:
        A narrative string describing the trade outcome.
    """
    from api.client import TradeClient

    if not state.player_id:
        return "You need to create a character first!"

    trade_client = TradeClient(
        base_url=settings.rpg_api_base_url,
        timeout=settings.rpg_api_timeout,
    )

    result = await trade_client.propose_trade(
        player_id=state.player_id,
        npc_id=npc_id,
        offer_item_id=offer_item_id,
        offer_gold=offer_gold,
        request_item_id=request_item_id,
        request_gold=request_gold,
    )

    # Refresh player cache if trade succeeded (gold changed)
    if result.success:
        await state.refresh_player_cache()

    return result.message


async def check_trade_values(
    state: GameStateService,
    npc_id: int,
    offer_item_id: Optional[int] = None,
    offer_gold: int = 0,
    request_item_id: Optional[int] = None,
    request_gold: int = 0,
) -> dict:
    """
    Check what the DC would be for a trade without executing it.

    Returns:
        Dict with offer_value, request_value, dc, and fair_trade fields.
    """
    from api.client import TradeClient

    if not state.player_id:
        return {"error": "No player character"}

    trade_client = TradeClient(
        base_url=settings.rpg_api_base_url,
        timeout=settings.rpg_api_timeout,
    )

    result = await trade_client.check_trade(
        player_id=state.player_id,
        npc_id=npc_id,
        offer_item_id=offer_item_id,
        offer_gold=offer_gold,
        request_item_id=request_item_id,
        request_gold=request_gold,
    )

    return {
        "offer_value": result.offer_value,
        "request_value": result.request_value,
        "dc": result.dc,
        "fair_trade": result.fair_trade,
    }
