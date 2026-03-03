"""DeathSystem — handles enemy/boss death, health drops, and post-death effects."""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Any

import pygame

if TYPE_CHECKING:
    from src.game import Game

from src.balance import ENEMY_SCORE_PER_HEALTH

logger = logging.getLogger(__name__)


class DeathSystem:
    """Manages removal of dead enemies/bosses, scoring, XP, health drops, and related side effects."""

    def __init__(self, game: Game) -> None:
        self.game = game

    def remove_dead_enemies(self) -> None:
        """Remove dead enemies and award score/XP. Handles both sprite groups and plain lists."""
        g = self.game
        # Check for dead enemies after update (e.g., from burn damage over time) and remove them
        if hasattr(g.enemies, "sprites"):
            for enemy in list(g.enemies.sprites()):
                if hasattr(enemy, "health") and enemy.health <= 0:
                    g.add_score(
                        enemy.max_health
                        * ENEMY_SCORE_PER_HEALTH
                        * g.difficulty_multiplier
                    )
                    type_xp_local = {
                        "weak": 10,
                        "normal": 16,
                        "strong": 25,
                        "giant": 50,
                        "angel": 22,
                    }
                    base_xp_local = type_xp_local.get(
                        str(getattr(enemy, "enemy_type", "")), 12
                    )
                    g.player_xp += int(
                        round(base_xp_local * getattr(g, "xp_multiplier", 1.0))
                    )
                    if g.player_xp >= g.xp_to_next_level:
                        g.trigger_level_up()
                    try:
                        if (
                            getattr(enemy, "burn_propagate_on_death", False)
                            or getattr(enemy, "burn_propagate_hops", 0) > 0
                        ):
                            try:
                                g._propagate_burn(enemy)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        enemy.kill()
                    except Exception:
                        pass
        else:
            for enemy in list(g.enemies):
                # Plain-list enemies (object instances expected)
                if getattr(enemy, "health", 0) <= 0:
                    g.add_score(
                        getattr(enemy, "max_health", 10)
                        * ENEMY_SCORE_PER_HEALTH
                        * g.difficulty_multiplier
                    )
                    try:
                        if (
                            getattr(enemy, "burn_propagate_on_death", False)
                            or getattr(enemy, "burn_propagate_hops", 0) > 0
                        ):
                            try:
                                g._propagate_burn(enemy)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    base_xp_local = 12
                    try:
                        base_xp_local = {
                            "weak": 10,
                            "normal": 16,
                            "strong": 25,
                            "giant": 50,
                            "angel": 22,
                        }.get(str(getattr(enemy, "enemy_type", "")), 12)
                    except Exception:
                        base_xp_local = 12
                    g.player_xp += int(
                        round(base_xp_local * getattr(g, "xp_multiplier", 1.0))
                    )
                    if g.player_xp >= g.xp_to_next_level:
                        g.trigger_level_up()
                    try:
                        g.record_enemy_kill()
                    except Exception:
                        pass
                    try:
                        # Call kill() if implemented, then ensure removal from plain list
                        if hasattr(enemy, "kill"):
                            try:
                                enemy.kill()
                            except Exception:
                                pass
                        try:
                            # Always attempt to remove from the plain list container
                            g.enemies.remove(enemy)
                        except Exception:
                            pass
                    except Exception:
                        pass

                # Object/sprite enemies stored in a plain list (support for tests)
                elif hasattr(enemy, "health") and enemy.health <= 0:
                    try:
                        g.add_score(
                            enemy.max_health
                            * ENEMY_SCORE_PER_HEALTH
                            * g.difficulty_multiplier
                        )
                    except Exception:
                        pass
                    type_xp_local = {
                        "weak": 10,
                        "normal": 16,
                        "strong": 25,
                        "giant": 50,
                        "angel": 22,
                    }
                    base_xp_local = type_xp_local.get(
                        str(getattr(enemy, "enemy_type", "")), 12
                    )
                    try:
                        g.player_xp += int(
                            round(base_xp_local * getattr(g, "xp_multiplier", 1.0))
                        )
                    except Exception:
                        pass
                    if g.player_xp >= g.xp_to_next_level:
                        g.trigger_level_up()
                    # Propagate burn if flagged
                    try:
                        if (
                            getattr(enemy, "burn_propagate_on_death", False)
                            or getattr(enemy, "burn_propagate_hops", 0) > 0
                        ):
                            try:
                                g._propagate_burn(enemy)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        # If enemy implements kill(), call it for symmetry with Group
                        enemy.kill()
                    except Exception:
                        pass
                    try:
                        # remove from the plain list
                        g.enemies.remove(enemy)
                        try:
                            g.record_enemy_kill()
                        except Exception:
                            pass
                    except Exception:
                        pass

    def remove_dead_bosses(self) -> None:
        """Remove dead bosses and award score/XP. Handles both sprite groups and dict lists."""
        g = self.game
        # Check for dead bosses after update (e.g., from burn damage over time) and remove them
        if hasattr(g.bosses, "sprites"):
            for boss in list(g.bosses.sprites()):
                if hasattr(boss, "health") and boss.health <= 0:
                    # Boss death handling (similar to enemy death but with different XP multiplier)
                    # For now, use enemy-like handling; adjust if bosses have special death logic
                    g.add_score(boss.max_health * 25)  # Bosses give more score
                    boss_xp_map = {"medium": 80, "big": 150, "final": 400}
                    boss_base_xp = boss_xp_map.get(
                        boss.enemy_type.replace("boss_", ""), 100
                    )
                    g.player_xp += int(
                        round(boss_base_xp * getattr(g, "xp_multiplier", 1.0))
                    )
                    if g.player_xp >= g.xp_to_next_level:
                        g.trigger_level_up()
                    # Propagate burn on boss death if applicable
                    try:
                        if (
                            getattr(boss, "burn_propagate_on_death", False)
                            or getattr(boss, "burn_propagate_hops", 0) > 0
                        ):
                            try:
                                g._propagate_burn(boss)
                            except Exception:
                                pass
                    except Exception:
                        pass

                    # spawn limbo_final countdown if appropriate
                    try:
                        if getattr(g, "debug", False):
                            print(
                                "[CORE] death flag check",
                                boss.enemy_type,
                                getattr(g, "selected_stage", None),
                                "started?",
                                getattr(g, "limbo_final_victory_started", False),
                            )
                        if (
                            getattr(boss, "enemy_type", "") == "boss_limbo"
                            and getattr(g, "selected_stage", None) == "limbo_final"
                            and not getattr(g, "limbo_final_victory_started", False)
                        ):
                            # begin 5‑second timer
                            g.limbo_final_victory_timer = int(g.fps * 5)
                            g.limbo_final_victory_started = True
                            if getattr(g, "debug", False):
                                print("[CORE] limbo_final timer started")
                            try:
                                g.show_centered_message(
                                    "BOSS DEFEATED!", 2000, (255, 255, 0)
                                )
                            except Exception:
                                pass
                    except Exception:
                        pass

                    # Spawn health drop for all bosses
                    try:
                        et = getattr(boss, "enemy_type", "")
                        if et.startswith("boss_"):
                            heal_amt = random.randint(10, 20)
                            try:
                                self.spawn_health_drop(boss.x, boss.y, heal_amt)
                            except Exception:
                                pass
                    except Exception:
                        pass

                    # If a medium (wave) boss dies by any cause, schedule reinforcements
                    try:
                        if getattr(boss, "enemy_type", "") == "boss_medium":
                            # Show the centered HUD message and schedule the reinforcement timer
                            try:
                                g.show_centered_message(
                                    "REINFORCEMENTS INCOMING!", 1800, (255, 204, 0)
                                )
                            except Exception:
                                pass
                            try:
                                # Clear any existing reinforcement timer then schedule a new one
                                pygame.time.set_timer(pygame.USEREVENT + 1, 0)
                                pygame.time.set_timer(
                                    pygame.USEREVENT + 1, g.reinforcement_delay_ms
                                )
                            except Exception:
                                pass
                    except Exception:
                        pass

                    boss.kill()  # Remove dead boss
        else:
            for boss in list(g.bosses):
                if isinstance(boss, dict) and boss.get("health", 0) <= 0:
                    g.add_score(
                        boss.get("max_health", 100) * 25 * g.difficulty_multiplier
                    )  # Assuming bosses have higher multiplier
                    if g.player_xp >= g.xp_to_next_level:
                        g.trigger_level_up()
                    # Propagate burn on boss death if applicable
                    try:
                        if (
                            boss.get("burn_propagate_on_death", False)
                            or boss.get("burn_propagate_hops", 0) > 0
                        ):
                            try:
                                g._propagate_burn(boss)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        g.bosses.remove(boss)
                    except Exception:
                        pass

    def spawn_health_drop(self, x: float, y: float, heal: int) -> None:
        """Create a healing bonus that falls from (x,y).

        ``heal`` is the hit point amount restored when the player picks it up.
        The drop is represented as a simple dict and is processed by
        ``update_health_drops``.

        Drops are always spawned within the visible battlefield: if the boss
        died while still above the top edge we clamp ``y`` to zero so the item
        is immediately visible.

        A soft click sound is played when the drop is created, provided sounds
        are enabled.  The call is performed lazily to avoid importing the
        sound module at the top-level (which would in turn import pygame in
        environments where it may not be available).
        """
        g = self.game
        # ensure drop starts on-screen
        if y < 0:
            y = 0
        # faster fall and now even smaller
        drop = {"x": x, "y": y, "vy": 1.5, "heal": heal, "radius": 8}
        try:
            g.health_drops.append(drop)
        except Exception:
            g.health_drops = [drop]

        # play accompanying sound if enabled
        if getattr(g, "sounds_enabled", False):
            try:
                from src.utils import sound as sound_utils

                sound_utils.suono_click_soft().play()
            except Exception:
                # if anything goes wrong we silently ignore, since sound is
                # cosmetic and may not be available in test environments
                pass

    def update_health_drops(self) -> None:
        """Move health drops downward and handle collection by the player.

        Each frame the drop's ``y`` is incremented by its ``vy`` value.  If the
        player intersects a drop the player is healed and the drop is removed.
        Drops that fall past the bottom of the screen are also discarded.
        """
        g = self.game
        if not getattr(g, "health_drops", None):
            return
        alive: list[dict[str, Any]] = []
        # radius used for collision test; player radius is approximated as half
        # of the larger dimension of the player sprite.
        try:
            pr = max(getattr(g.player, "width", 0), getattr(g.player, "height", 0)) / 2
        except Exception:
            pr = 0
        for drop in list(g.health_drops):
            # move
            drop["y"] = drop.get("y", 0) + drop.get("vy", 0.5)

            # check for collision with player
            try:
                dx = drop.get("x", 0) - getattr(g.player, "x", 0)
                dy = drop.get("y", 0) - getattr(g.player, "y", 0)
                dr = drop.get("radius", 12)
                if dx * dx + dy * dy <= (pr + dr) * (pr + dr):
                    heal_amt = drop.get("heal", 0)
                    g.player.health = min(
                        g.player.max_health, g.player.health + heal_amt
                    )
                    try:
                        # let the player see the heal amount
                        g.spawn_floating_text(
                            f"+{int(heal_amt)}",
                            drop.get("x", 0),
                            drop.get("y", 0),
                            color=(0, 255, 0),
                        )
                    except Exception:
                        pass
                    continue
            except Exception:
                pass

            # keep if still on screen
            if drop.get("y", 0) <= g.height + 50:
                alive.append(drop)
        g.health_drops = alive
