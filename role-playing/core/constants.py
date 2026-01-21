"""
Centralized deterministic constants used across the game.

Keeps mechanics and config-like values in one place to reduce duplication
and make it easier to adjust defaults without hunting through agent logic.
"""

from typing import Dict, List, Tuple

# Trade valuation helpers.
TRADE_ITEM_VALUES: Dict[str, int] = {
    "weapon": 50,
    "armor": 75,
    "consumable": 20,
    "misc": 10,
}

# (offer/request ratio threshold, DC)
TRADE_DC_BRACKETS: List[Tuple[float, int]] = [
    (1.5, 5),   # Very favorable to NPC
    (1.0, 10),  # Fair trade
    (0.75, 15), # Slightly unfavorable
    (0.0, 20),  # Very unfavorable
]

# Voices available for character performance.
AVAILABLE_TTS_VOICES: List[str] = [
    "Ashley",   # Warm, natural American female
    "Diego",    # Soothing, gentle Mexican male
    "Edward",   # Fast-talking, emphatic American male
    "Olivia",   # Upbeat, friendly British female
    "Hades",    # Narrator default
    "Mark",
    "Deborah",
    "Dennis",
    "Timothy",
]
