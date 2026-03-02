"""Score and meta-progression system.

Handles:
- Meta XP accumulation and level-ups
- Meta point currency for permanent upgrades
- Per-run stage clear tracking and rewards
- Enemy kill tracking for meta progression
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game import Game

logger: logging.Logger = logging.getLogger(__name__)


class ScoreSystem:
    """Manages meta-progression: XP, levels, points, stage clears."""

    def __init__(self, game: Game) -> None:
        """Initialize system with game reference."""
        self.game = game

    def get_meta_xp_to_next_level(self) -> int:
        """Return the amount of meta-XP required for the next meta level.

        Uses ``META_XP_BASE`` and ``META_XP_GROWTH`` from ``src.balance``.
        This is intentionally distinct from the per-run XP settings so the
        external progression ramps more slowly.
        """
        try:
            from src.balance import META_XP_BASE, META_XP_GROWTH

            lvl = self.game.global_progress.get("meta_level", 1)
            return int(META_XP_BASE * (META_XP_GROWTH ** (lvl - 1)))
        except Exception:
            # fallback reasonable constant
            return 1000

    def award_meta_xp(self, xp: int) -> None:
        """Increment meta XP and handle any level-ups.

        Each time meta XP crosses the threshold a new level is awarded and
        ``meta_points`` increments by one (currency for upgrading the four
        permanent stats). Excess XP carries over to the next level.
        """
        if xp <= 0:
            return
        cur = self.game.global_progress.get("meta_xp", 0) + xp
        self.game.global_progress["meta_xp"] = cur
        # process level-ups
        leveled_up = False
        while cur >= self.get_meta_xp_to_next_level():
            cur -= self.get_meta_xp_to_next_level()
            self.game.global_progress["meta_level"] = (
                self.game.global_progress.get("meta_level", 1) + 1
            )
            self.game.global_progress["meta_points"] = (
                self.game.global_progress.get("meta_points", 0) + 1
            )
            leveled_up = True
        self.game.global_progress["meta_xp"] = cur
        if leveled_up:
            self.game.save_permanent_stats()

    def award_stage_clear(self, stage: str) -> bool:
        """Award the one-time completion reward for a stage.

        Returns ``True`` if the reward was granted (first clear); ``False`` if
        the stage had already been recorded.

        Currently only ``prologo`` is ever cleared by game logic, but the
        method is generic so future stages can call it.
        """
        cleared = self.game.global_progress.setdefault("stages_cleared", {})
        if cleared.get(stage):
            return False
        # mark and give reward
        cleared[stage] = True
        self.game.global_progress["meta_points"] = (
            self.game.global_progress.get("meta_points", 0) + 1
        )
        # also grant a bit of meta-XP so the bar reflects progress; use 10%
        # of the current threshold to give visible increments without
        # immediately leveling.
        try:
            xp_reward = int(self.get_meta_xp_to_next_level() * 0.1)
            if xp_reward > 0:
                self.award_meta_xp(xp_reward)
        except Exception:
            pass
        self.game.save_permanent_stats()
        return True

    def record_enemy_kill(self) -> None:
        """Record a single enemy kill for the current run.

        Awards meta-xp. For limbo horde, victory is triggered ONLY by boss death,
        not by enemy kill count (which is unreliable and can be gamed).
        """
        # Award meta_xp for enemy kills
        try:
            self.award_meta_xp(5)
        except Exception as e:
            logger.exception(f"Failed to award meta_xp: {e}")
