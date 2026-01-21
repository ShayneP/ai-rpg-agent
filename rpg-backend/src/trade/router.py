"""Trade API router."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .schemas import TradeProposalRequest, TradeResult, TradeValueCheck
from . import service

router = APIRouter(prefix="/trade", tags=["trade"])


@router.post("/propose", response_model=TradeResult)
def propose_trade(request: TradeProposalRequest, db: Session = Depends(get_db)):
    """
    Propose a trade with an NPC.

    The trade uses a charisma check against a DC determined by the fairness
    of the trade (offer value vs request value ratio).

    - **player_id**: The player character making the trade
    - **npc_id**: The NPC character to trade with
    - **offer_item_id**: Optional inventory item ID the player is offering
    - **offer_gold**: Gold amount the player is offering
    - **request_item_id**: Optional inventory item ID the player wants from NPC
    - **request_gold**: Gold amount the player wants from NPC
    """
    return service.propose_trade(
        db=db,
        player_id=request.player_id,
        npc_id=request.npc_id,
        offer_item_id=request.offer_item_id,
        offer_gold=request.offer_gold,
        request_item_id=request.request_item_id,
        request_gold=request.request_gold,
    )


@router.post("/check", response_model=TradeValueCheck)
def check_trade(request: TradeProposalRequest, db: Session = Depends(get_db)):
    """
    Check the values and DC of a potential trade without executing it.

    Useful for UI to show the player what the DC would be before committing.
    """
    return service.check_trade_values(
        db=db,
        player_id=request.player_id,
        npc_id=request.npc_id,
        offer_item_id=request.offer_item_id,
        offer_gold=request.offer_gold,
        request_item_id=request.request_item_id,
        request_gold=request.request_gold,
    )
