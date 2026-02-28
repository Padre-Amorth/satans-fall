"""Game package - core game logic and state management."""

from .core import Game
from .ui_helpers import FloatingText, StatConfig
from .weapons import init_weapons, init_player_weapons
from .persistence import (
    load_permanent_stats,
    save_permanent_stats,
    get_profile_info,
    load_last_profile_slot,
)

__all__ = [
    "Game",
    "FloatingText",
    "StatConfig",
    "init_weapons",
    "init_player_weapons",
    "load_permanent_stats",
    "save_permanent_stats",
    "get_profile_info",
    "load_last_profile_slot",
]
