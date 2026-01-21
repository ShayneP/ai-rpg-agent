"""
API client package for communicating with the tabletop-rpg-api.

This package provides async HTTP clients for all API endpoints:
- CharacterClient: Character CRUD, XP, gold, rest
- CombatClient: Combat sessions, actions, processing
- InventoryClient: Inventory management, equipment
- ReferenceClient: Game reference data (monsters, weapons, spells)
- TradeClient: Trading between characters
"""

from .client import (
    RPGAPIClient,
    CharacterClient,
    CombatClient,
    InventoryClient,
    ReferenceClient,
)
from .models import (
    APICharacter,
    APICombatSession,
    APICombatant,
    APIActionResult,
    APIItem,
    APIInventoryItem,
)

__all__ = [
    "RPGAPIClient",
    "CharacterClient",
    "CombatClient",
    "InventoryClient",
    "ReferenceClient",
    "APICharacter",
    "APICombatSession",
    "APICombatant",
    "APIActionResult",
    "APIItem",
    "APIInventoryItem",
]
