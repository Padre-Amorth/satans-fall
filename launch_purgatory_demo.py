#!/usr/bin/env python3
"""
Demo launcher for Purgatory horde event.
Starts the game 30 seconds before the horde spawns, skipping menus.
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.game import Game
from src.game_constants import PURGATORY_HORDE_TIME_1


def main():
    """Launch game in Purgatory stage, 30 seconds before horde."""
    g = Game()
    g.reset_game()
    g.select_stage("purgatory")

    # Skip main menu - go directly to gameplay
    g.showing_main_menu = False
    g.showing_stage_menu = False

    # Start 30 seconds before horde
    g.time_elapsed = PURGATORY_HORDE_TIME_1 - 30.0

    # Run the game loop
    g.run()


if __name__ == "__main__":
    main()
