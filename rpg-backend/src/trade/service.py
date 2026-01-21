"""Trade business logic."""

import random
from typing import Tuple, Optional
from sqlalchemy.orm import Session

from ..character.models import Character
from ..inventory.models import InventoryItem, Item
from .schemas import TradeResult, TradeValueCheck


# Item value by type (in gold pieces)
ITEM_TYPE_VALUES = {
    "weapon": 50,
    "armor": 75,
    "consumable": 10,
    "potion": 15,
    "scroll": 25,
    "misc": 5,
    "quest_item": 0,  # Quest items have no trade value
    "key": 0,  # Keys have no trade value
}

# Trade DC brackets based on offer/request value ratio
# (minimum_ratio, dc)
TRADE_DC_BRACKETS = [
    (2.0, 5),    # Offering 2x or more -> very easy
    (1.5, 8),    # Offering 1.5x -> easy
    (1.0, 10),   # Fair trade -> medium
    (0.75, 15),  # Slightly unfair -> hard
    (0.5, 18),   # Very unfair -> very hard
    (0.25, 22),  # Extremely unfair -> nearly impossible
    (0.0, 25),   # Offering almost nothing -> almost impossible
]


def get_item_value(item: Item) -> int:
    """Get the trade value of an item."""
    base_value = ITEM_TYPE_VALUES.get(item.item_type.value, 10)

    # Add item's intrinsic value if set
    if item.value:
        base_value += item.value

    # Rarity multipliers
    rarity_multipliers = {
        "common": 1.0,
        "uncommon": 2.0,
        "rare": 5.0,
        "very_rare": 10.0,
        "legendary": 50.0,
    }
    rarity = item.rarity.value if item.rarity else "common"
    multiplier = rarity_multipliers.get(rarity, 1.0)

    return int(base_value * multiplier)


def calculate_trade_dc(offer_value: int, request_value: int) -> int:
    """Calculate the DC for a trade based on offer/request ratio."""
    if request_value == 0:
        # Requesting nothing - auto-accept
        return 0

    if offer_value == 0:
        # Offering nothing - very hard
        return 25

    ratio = offer_value / request_value

    for min_ratio, dc in TRADE_DC_BRACKETS:
        if ratio >= min_ratio:
            return dc

    return 25  # Default to very hard


def calculate_trade_values(
    db: Session,
    player_id: int,
    npc_id: int,
    offer_item_id: Optional[int],
    offer_gold: int,
    request_item_id: Optional[int],
    request_gold: int,
) -> Tuple[int, int]:
    """Calculate the total values for a trade."""
    offer_value = offer_gold
    request_value = request_gold

    # Add offer item value
    if offer_item_id:
        offer_item = db.query(InventoryItem).filter(
            InventoryItem.id == offer_item_id,
            InventoryItem.character_id == player_id,
        ).first()
        if offer_item:
            offer_value += get_item_value(offer_item.item)

    # Add request item value
    if request_item_id:
        request_item = db.query(InventoryItem).filter(
            InventoryItem.id == request_item_id,
            InventoryItem.character_id == npc_id,
        ).first()
        if request_item:
            request_value += get_item_value(request_item.item)

    return offer_value, request_value


def check_trade_values(
    db: Session,
    player_id: int,
    npc_id: int,
    offer_item_id: Optional[int],
    offer_gold: int,
    request_item_id: Optional[int],
    request_gold: int,
) -> TradeValueCheck:
    """Check trade values and DC without executing."""
    offer_value, request_value = calculate_trade_values(
        db, player_id, npc_id, offer_item_id, offer_gold, request_item_id, request_gold
    )
    dc = calculate_trade_dc(offer_value, request_value)

    return TradeValueCheck(
        offer_value=offer_value,
        request_value=request_value,
        dc=dc,
        fair_trade=(dc <= 10),
    )


def execute_trade(
    db: Session,
    player: Character,
    npc: Character,
    offer_item_id: Optional[int],
    offer_gold: int,
    request_item_id: Optional[int],
    request_gold: int,
) -> None:
    """Execute the trade - transfer items and gold."""
    # Transfer gold
    if offer_gold > 0:
        player.gold -= offer_gold
        npc.gold += offer_gold

    if request_gold > 0:
        npc.gold -= request_gold
        player.gold += request_gold

    # Transfer offer item (player -> NPC)
    if offer_item_id:
        offer_item = db.query(InventoryItem).filter(
            InventoryItem.id == offer_item_id,
            InventoryItem.character_id == player.id,
        ).first()
        if offer_item:
            # If quantity > 1, just decrease quantity
            if offer_item.quantity > 1:
                offer_item.quantity -= 1
            else:
                # Transfer ownership
                offer_item.character_id = npc.id
                offer_item.equipped = False
                offer_item.equipment_slot = None

    # Transfer request item (NPC -> player)
    if request_item_id:
        request_item = db.query(InventoryItem).filter(
            InventoryItem.id == request_item_id,
            InventoryItem.character_id == npc.id,
        ).first()
        if request_item:
            if request_item.quantity > 1:
                request_item.quantity -= 1
                # Create new item for player
                new_item = InventoryItem(
                    character_id=player.id,
                    item_id=request_item.item_id,
                    quantity=1,
                    equipped=False,
                )
                db.add(new_item)
            else:
                request_item.character_id = player.id
                request_item.equipped = False
                request_item.equipment_slot = None

    db.commit()


def propose_trade(
    db: Session,
    player_id: int,
    npc_id: int,
    offer_item_id: Optional[int],
    offer_gold: int,
    request_item_id: Optional[int],
    request_gold: int,
) -> TradeResult:
    """
    Propose a trade with an NPC.

    Uses a charisma check against the trade DC.
    """
    # Get characters
    player = db.query(Character).filter(Character.id == player_id).first()
    if not player:
        return TradeResult(
            success=False,
            message="Player character not found.",
            roll=0,
            dc=0,
            offer_value=0,
            request_value=0,
        )

    npc = db.query(Character).filter(Character.id == npc_id).first()
    if not npc:
        return TradeResult(
            success=False,
            message="NPC not found.",
            roll=0,
            dc=0,
            offer_value=0,
            request_value=0,
        )

    # Validate player has the gold to offer
    if offer_gold > player.gold:
        return TradeResult(
            success=False,
            message=f"You don't have {offer_gold} gold. You only have {player.gold} gold.",
            roll=0,
            dc=0,
            offer_value=0,
            request_value=0,
        )

    # Validate NPC has the gold to give
    if request_gold > npc.gold:
        return TradeResult(
            success=False,
            message=f"{npc.name} doesn't have {request_gold} gold. They only have {npc.gold} gold.",
            roll=0,
            dc=0,
            offer_value=0,
            request_value=0,
        )

    # Validate player has the item to offer
    if offer_item_id:
        offer_item = db.query(InventoryItem).filter(
            InventoryItem.id == offer_item_id,
            InventoryItem.character_id == player_id,
        ).first()
        if not offer_item:
            return TradeResult(
                success=False,
                message="You don't have that item to offer.",
                roll=0,
                dc=0,
                offer_value=0,
                request_value=0,
            )

    # Validate NPC has the item to give
    if request_item_id:
        request_item = db.query(InventoryItem).filter(
            InventoryItem.id == request_item_id,
            InventoryItem.character_id == npc_id,
        ).first()
        if not request_item:
            return TradeResult(
                success=False,
                message=f"{npc.name} doesn't have that item.",
                roll=0,
                dc=0,
                offer_value=0,
                request_value=0,
            )

    # Check if anything is being traded
    if not offer_item_id and offer_gold == 0 and not request_item_id and request_gold == 0:
        return TradeResult(
            success=False,
            message="You need to offer or request something to make a trade!",
            roll=0,
            dc=0,
            offer_value=0,
            request_value=0,
        )

    # Calculate values and DC
    offer_value, request_value = calculate_trade_values(
        db, player_id, npc_id, offer_item_id, offer_gold, request_item_id, request_gold
    )
    dc = calculate_trade_dc(offer_value, request_value)

    # Roll charisma check
    charisma_modifier = (player.charisma - 10) // 2
    roll = random.randint(1, 20)
    total = roll + charisma_modifier

    # Determine success
    success = total >= dc

    if success:
        # Execute the trade
        execute_trade(db, player, npc, offer_item_id, offer_gold, request_item_id, request_gold)
        db.refresh(player)
        db.refresh(npc)

        message = f"{npc.name} accepts your trade! 'A fair exchange, traveler.'"

        return TradeResult(
            success=True,
            message=message,
            roll=total,
            dc=dc,
            offer_value=offer_value,
            request_value=request_value,
            player_gold=player.gold,
            npc_gold=npc.gold,
        )
    else:
        # Trade rejected
        refusals = [
            f"{npc.name} shakes their head. 'That's not a fair trade.'",
            f"{npc.name} frowns. 'You'll need to offer more than that.'",
            f"{npc.name} laughs. 'Surely you jest! That's not nearly enough.'",
        ]
        message = refusals[roll % len(refusals)]

        return TradeResult(
            success=False,
            message=message,
            roll=total,
            dc=dc,
            offer_value=offer_value,
            request_value=request_value,
        )
