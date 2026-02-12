"""EnemyManager with simple object pooling and spawn helpers.

Responsibilities:
- Spawn enemies (reuse from pool when possible)
- Register externally created enemies
- Recycle dead enemies back into the pool
- Expose spawn-related attributes (enemy_spawn_rate, enemy_spawn_timer)
- Provide small helper for reinforcements
"""
from __future__ import annotations

from typing import Any, List, Optional
import logging
import random

from src.entities.enemy import Enemy

logger = logging.getLogger(__name__)


class EnemyManager:
    def __init__(self, game, initial_pool: int = 40) -> None:
        self.game = game
        self.pool: List[Enemy] = []
        self.active: List[Enemy] = []
        # Spawn timing fields to be used by Game or external managers
        self.enemy_spawn_rate: int = getattr(game, "enemy_spawn_rate", 72)
        self.enemy_spawn_timer: int = getattr(game, "enemy_spawn_timer", 0)

        # Big enemy (giant) timers moved to manager
        self.big_enemy_timer: int = getattr(game, "big_enemy_timer", 12 * getattr(game, "fps", 60))
        self.big_enemy_fast_interval: int = getattr(game, "big_enemy_fast_interval", 9 * getattr(game, "fps", 60))
        self.big_spawned_this_wave: bool = getattr(game, "big_spawned_this_wave", False)

        # Wave boss flag
        self.wave_boss_spawned: bool = getattr(game, "wave_boss_spawned", False)

        # Prologo / final boss related state
        self.prologo_final_boss_spawned: bool = getattr(game, "prologo_final_boss_spawned", False)
        self.prologo_final_boss_defeated: bool = getattr(game, "prologo_final_boss_defeated", False)
        self.prologo_final_boss_immortal: bool = getattr(game, "prologo_final_boss_immortal", False)

        # Lightning strike handling
        self.prologo_lightning_strike: bool = getattr(game, "prologo_lightning_strike", False)
        self.prologo_lightning_timer: int = getattr(game, "prologo_lightning_timer", 0)
        self.prologo_lightning_duration_frames: int = getattr(game, "prologo_lightning_duration_frames", 180 + 2 * getattr(game, "fps", 60))

        # Pre-create a few enemies if possible (best-effort for headless envs)
        for _ in range(initial_pool):
            try:
                self.pool.append(Enemy(0, 0))
            except Exception:
                break

    def spawn(self, x: int, y: int, enemy_type: str = "normal", health: float = 20.0, speed: float = 100.0) -> Enemy:
        """Spawn or reuse an enemy and add to game's enemy container."""
        if self.pool:
            e = self.pool.pop()
            try:
                # Reinitialize instance (safe fallback to re-run constructor)
                e.__init__(x, y, enemy_type, health, speed)
            except Exception:
                # If re-init fails, create a new instance
                e = Enemy(x, y, enemy_type, health, speed)
        else:
            e = Enemy(x, y, enemy_type, health, speed)

        # Track active
        if e not in self.active:
            self.active.append(e)

        # Add to game container (Group or list)
        try:
            self.game.enemies.add(e)
        except Exception:
            try:
                self.game.enemies.append(e)
            except Exception:
                pass

        return e

    def register(self, e: Enemy) -> None:
        """Register an externally created enemy instance."""
        if e not in self.active:
            self.active.append(e)
        try:
            e.manager = self
        except Exception:
            pass

    def recycle(self, e: Enemy) -> None:
        """Recycle enemy instance back into pool and remove from game containers."""
        try:
            if e in self.active:
                self.active.remove(e)
        except Exception:
            pass

        try:
            if hasattr(self.game.enemies, "remove"):
                self.game.enemies.remove(e)
        except Exception:
            try:
                self.game.enemies.remove(e)
            except Exception:
                pass

        # Reset or hide enemy
        try:
            e.x = -9999
            e.y = -9999
            e.health = 0
            # Clear particles/temporary state where applicable
            e.burn_particles = []
            e.ice_particles = []
        except Exception:
            pass

        # Add back to pool
        try:
            self.pool.append(e)
        except Exception:
            pass

    def spawn_giant_enemy(self, side: str | None = None) -> Enemy:
        """Spawn a giant enemy at the top by default (inside walls), or at a specified side.

        side: "left", "right", or "top". If omitted, defaults to "top" so giants
        appear from above and within wall constraints like other enemies.
        """
        # Default to spawning from the top (inside walls) unless caller specifies a side
        if side is None:
            side = "top"  # default behavior: spawn from above, inside walls

        if side == "left":
            x = -30
            # keep within vertical bounds
            y = random.randint(0, max(0, self.game.height))
        elif side == "right":
            x = self.game.width + 30
            y = random.randint(0, max(0, self.game.height))
        else:  # top
            x = random.randint(0, self.game.width)
            # Clamp X so giant appears within the stage walls like other enemies
            x = self.game.clamp_to_walls(x)
            y = -30

        health = 100 * getattr(self.game, "difficulty_multiplier", 1.0)
        # Align with non-boss target effective speed ≈60
        speed = 75
        e = self.spawn(x, y, "giant", health, speed)
        return e

    def update_big_enemy_timer(self) -> None:
        """Decrement big enemy timer and spawn a giant when it hits zero (once per wave)."""
        self.big_enemy_timer -= 1
        if self.big_enemy_timer <= 0 and not self.big_spawned_this_wave:
            try:
                self.spawn_giant_enemy()
                self.big_spawned_this_wave = True
                if getattr(self.game, "wave", 0) >= 6:
                    self.big_enemy_timer = self.big_enemy_fast_interval
                else:
                    self.big_enemy_timer = 12 * getattr(self.game, "fps", 60)
            except Exception:
                # Don't propagate spawn errors to game loop
                pass

    def update_wave_boss(self, wave_time: float) -> None:
        """Handle the timed wave boss spawn (at ~28s)."""
        if not self.wave_boss_spawned and wave_time >= 28:
            # Avoid spawning final boss twice in prologo
            if not (
                getattr(self.game, "selected_stage", None) == "prologo"
                and self.prologo_final_boss_spawned
            ):
                # If we're in a Limbo stage, spawn the special Inquisitor boss instead
                # Limbo: always Inquisitor
                if getattr(self.game, "is_limbo_stage", lambda: False)():
                    self.spawn_boss("inquisitor")
                # Purgatory: alternate end-of-wave boss between medium and inquisitor
                elif getattr(self.game, "selected_stage", "").startswith("purgatory"):
                    # Use wave parity to alternate: odd waves -> medium, even waves -> inquisitor
                    current_wave = getattr(self.game, "wave", 0)
                    if current_wave % 2 == 1:
                        self.spawn_boss("mid")
                    else:
                        self.spawn_boss("inquisitor")
                elif getattr(self.game, "wave", 0) % 3 == 0 and getattr(self.game, "wave", 0) > 0:
                    self.spawn_boss("big")
                else:
                    self.spawn_boss("mid")
            self.wave_boss_spawned = True

    def update_prologo_events(self) -> None:
        """Handle Prologo-specific boss events (final boss spawn, lightning, regen)."""
        try:
            # Final boss spawn at 175 seconds
            if (
                getattr(self.game, "selected_stage", None) == "prologo"
                and not self.prologo_final_boss_spawned
                and getattr(self.game, "time_elapsed", 0) >= 175
            ):
                self.spawn_boss("final")
                self.prologo_final_boss_spawned = True

            # Lightning strike countdown
            if getattr(self.game, "selected_stage", None) == "prologo" and self.prologo_lightning_strike:
                self.prologo_lightning_timer += 1
                if self.prologo_lightning_timer >= self.prologo_lightning_duration_frames:
                    # Call into game to show Prologo defeat
                    try:
                        self.game.prologo_defeat()
                    except Exception:
                        pass

            # Boss regeneration when immortal
            for boss in list(getattr(self.game, "bosses", [])):
                if (
                    getattr(boss, "enemy_type", "") == "boss_final"
                    and self.prologo_final_boss_immortal
                    and getattr(boss, "health", 0) < getattr(boss, "max_health", 0)
                ):
                    boss.health = min(getattr(boss, "max_health", 0), boss.health + 3.0)
                    if boss.health >= boss.max_health and not self.prologo_lightning_strike:
                        # Trigger lightning and knock out player
                        self.prologo_lightning_strike = True
                        try:
                            # Use game's generator if available
                            if hasattr(self.game, "generate_lightning"):
                                self.game.generate_lightning()
                            else:
                                # Fallback: create a minimal lightning_points list
                                self.game.lightning_points = [(int(getattr(self.game.player, "x", self.game.width//2)), 0), (int(getattr(self.game.player, "x", self.game.width//2)), self.game.height)]
                            # Knock out player
                            try:
                                self.game.player.health = 0
                            except Exception:
                                pass
                        except Exception:
                            pass
        except Exception:
            # Fail-safe: don't let manager errors break the game loop
            pass

    def spawn_boss(self, boss_type: str = "mid") -> Enemy:
        """Spawn a boss of the specified type ('final', 'big', 'mid').
        Adds the boss to `game.bosses` to preserve existing boss grouping.
        """
        x = self.game.width // 2
        y = -50

        if boss_type == "final":
            enemy_type = "boss_final"
            health = 1000 * getattr(self.game, "difficulty_multiplier", 1.0)
            speed = 18
        elif boss_type == "big":
            enemy_type = "boss_big"
            health = 600 * getattr(self.game, "difficulty_multiplier", 1.0)
            speed = 16
        elif boss_type == "inquisitor":
            # Special Limbo boss (HP increased by 50%, now reduced by 10%)
            enemy_type = "boss_inquisitor"
            # Base HP: 525 -> apply -10% for tuning
            health = int(525 * 0.9 * getattr(self.game, "difficulty_multiplier", 1.0))  # -> 472
            speed = 34  # slightly increased movement speed
        else:
            enemy_type = "boss_medium"
            health = 300 * getattr(self.game, "difficulty_multiplier", 1.0)
            speed = 60

        boss = Enemy(x, y, enemy_type, health, speed)
        # Track active
        if boss not in self.active:
            self.active.append(boss)
        # Add to boss group on game
        try:
            self.game.bosses.add(boss)
        except Exception:
            try:
                self.game.bosses.append(boss)
            except Exception:
                pass
        return boss

    def cleanup(self) -> None:
        """Optional maintenance (shrink pool if too big), not used for now."""
        pass


__all__ = ["EnemyManager"]
