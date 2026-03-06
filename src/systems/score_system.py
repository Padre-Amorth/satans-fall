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
        except (AttributeError, TypeError, ValueError, KeyError):
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
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        self.game.save_permanent_stats()
        return True

    def record_enemy_kill(self, enemy_x: float = None, enemy_y: float = None) -> None:
        """Record a single enemy kill for the current run.

        Awards meta-xp. For limbo horde, victory is triggered ONLY by boss death,
        not by enemy kill count (which is unreliable and can be gamed).

        Also handles kill explosion counter for the per-run upgrade.

        Args:
            enemy_x: X coordinate where enemy died (for explosion positioning)
            enemy_y: Y coordinate where enemy died (for explosion positioning)
        """
        # Award meta_xp for enemy kills
        try:
            self.award_meta_xp(5)
        except Exception as e:
            logger.exception(f"Failed to award meta_xp: {e}")

        # Handle kill explosion upgrade - increment counter each kill
        try:
            if getattr(self.game.player, "kill_explosion_enabled", False):
                kill_counter = getattr(self.game.player, "kill_counter", 0)
                kill_counter += 1
                self.game.player.kill_counter = kill_counter
        except Exception as e:
            logger.exception(f"Failed to increment kill counter: {e}")

    def _trigger_kill_explosion(self, exp_x: float, exp_y: float) -> None:
        """Trigger explosion at specified position when 10 kills are reached.

        Damage and range scale with upgrade level:
        - Base damage: 30
        - Base range: 70px
        - Per upgrade: +20 damage, +20px range

        Args:
            exp_x: X coordinate for explosion center
            exp_y: Y coordinate for explosion center
        """
        try:
            player = self.game.player
            upgrades = getattr(player, "kill_explosion_upgrades", 0)

            # Calculate damage and range
            base_damage = 30
            base_range = 70
            damage = base_damage + (upgrades * 20)
            explosion_range = base_range + (upgrades * 20)

            # Damage all enemies in range
            px, py = exp_x, exp_y
            if hasattr(self.game.enemies, "sprites"):
                enemies_list = list(self.game.enemies.sprites())
            else:
                enemies_list = list(self.game.enemies)

            import math

            for enemy in enemies_list:
                ex, ey = getattr(enemy, "x", 0), getattr(enemy, "y", 0)
                dist = math.hypot(ex - px, ey - py)
                if dist <= explosion_range:
                    try:
                        enemy.take_damage(damage)
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass

            # Visual feedback: add explosion effect (similar to skullboom but purple)
            try:
                explosion_timer = 15  # Duration of explosion animation
                # Purple color for kill explosion
                purple_color = (180, 100, 220)
                self.game.skullboom_explosions.append(
                    {
                        "x": px,
                        "y": py,
                        "max_radius": explosion_range,
                        "timer": explosion_timer,
                        "max_timer": explosion_timer,
                        "color": purple_color,
                    }
                )
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

            # Visual feedback: spawn floating text
            try:
                self.game.spawn_floating_text(f"BOOM! +{damage}", int(px), int(py) - 30)
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

        except Exception as e:
            logger.exception(f"Failed to trigger kill explosion: {e}")
