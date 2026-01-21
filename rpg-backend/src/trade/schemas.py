"""Trade request/response schemas."""

from pydantic import BaseModel, Field
from typing import Optional


class TradeProposalRequest(BaseModel):
    """Request to propose a trade with an NPC."""

    player_id: int = Field(..., description="The player character ID")
    npc_id: int = Field(..., description="The NPC character ID to trade with")

    # What the player offers
    offer_item_id: Optional[int] = Field(None, description="Inventory item ID to offer")
    offer_gold: int = Field(0, ge=0, description="Gold amount to offer")

    # What the player requests
    request_item_id: Optional[int] = Field(None, description="NPC inventory item ID to request")
    request_gold: int = Field(0, ge=0, description="Gold amount to request")


class TradeResult(BaseModel):
    """Result of a trade proposal."""

    success: bool = Field(..., description="Whether the trade was accepted")
    message: str = Field(..., description="Description of the trade outcome")
    roll: int = Field(..., description="The charisma roll result")
    dc: int = Field(..., description="The difficulty class for the trade")
    offer_value: int = Field(..., description="Total value of what was offered")
    request_value: int = Field(..., description="Total value of what was requested")

    # Updated gold values after trade (if successful)
    player_gold: Optional[int] = Field(None, description="Player's gold after trade")
    npc_gold: Optional[int] = Field(None, description="NPC's gold after trade")


class TradeValueCheck(BaseModel):
    """Check the values and DC of a potential trade without executing it."""

    offer_value: int = Field(..., description="Total value of what would be offered")
    request_value: int = Field(..., description="Total value of what would be requested")
    dc: int = Field(..., description="The difficulty class for this trade")
    fair_trade: bool = Field(..., description="Whether this is considered a fair trade (DC <= 10)")
