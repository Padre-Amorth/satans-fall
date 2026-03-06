"""EnemyManager with simple object pooling and spawn helpers.

Responsibilities:
- Spawn enemies (reuse from pool when possible)
- Register externally created enemies
- Recycle dead enemies back into the pool
- Expose spawn-related attributes (enemy_spawn_rate, enemy_spawn_timer)
- Provide small helper for reinforcements
"""

from __future__ import annotations

import logging
import random
from typing import List

import pygame

from src.balance import ENEMY_BASE_SPEEDS
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
        self.big_enemy_timer: int = getattr(
            game, "big_enemy_timer", 12 * getattr(game, "fps", 60)
        )
        self.big_enemy_fast_interval: int = getattr(
            game, "big_enemy_fast_interval", 9 * getattr(game, "fps", 60)
        )
        self.big_spawned_this_wave: bool = getattr(game, "big_spawned_this_wave", False)

        # Wave boss flag
        self.wave_boss_spawned: bool = getattr(game, "wave_boss_spawned", False)

        # Prologo / final boss related state
        self.prologo_final_boss_spawned: bool = getattr(
            game, "prologo_final_boss_spawned", False
        )
        self.prologo_final_boss_defeated: bool = getattr(
            game, "prologo_final_boss_defeated", False
        )
        self.prologo_final_boss_immortal: bool = getattr(
            game, "prologo_final_boss_immortal", False
        )
        # Limbo Final boss state proxy
        self.limbo_final_boss_spawned: bool = getattr(
            game, "limbo_final_boss_spawned", False
        )
        self.limbo_final_boss_immortal: bool = getattr(
            game, "limbo_final_boss_immortal", False
        )
        self.limbo_final_lightning_strike: bool = getattr(
            game, "limbo_final_lightning_strike", False
        )
        self.limbo_final_lightning_timer: int = getattr(
            game, "limbo_final_lightning_timer", 0
        )
        self.limbo_final_lightning_duration_frames: int = getattr(
            game,
            "limbo_final_lightning_duration_frames",
            180 + 2 * getattr(game, "fps", 60),
        )

        # Lightning strike handling
        self.prologo_lightning_strike: bool = getattr(
            game, "prologo_lightning_strike", False
        )
        self.prologo_lightning_timer: int = getattr(game, "prologo_lightning_timer", 0)
        self.prologo_lightning_duration_frames: int = getattr(
            game,
            "prologo_lightning_duration_frames",
            180 + 2 * getattr(game, "fps", 60),
        )

        # Purgatory inquisitor (non-boss) spawn limiter: at most 3 spawns per 15s window
        self.inquisitor_spawn_window_frames: int = 15 * getattr(game, "fps", 60)
        self.inquisitor_spawn_window_timer: int = 0
        self.inquisitor_spawn_count: int = 0
        # Per-second chance to attempt a spawn when under cap (checked once per second)
        self.inquisitor_spawn_chance_per_second: float = getattr(
            game, "inquisitor_spawn_chance_per_second", 0.12
        )

        # Pre-create a few enemies if possible (best-effort for headless envs)
        for _ in range(initial_pool):
            try:
                self.pool.append(Enemy(0, 0))
            except (AttributeError, TypeError, ValueError, KeyError):
                break

    def spawn(
        self,
        x: int,
        y: int,
        enemy_type: str = "normal",
        health: float = 20.0,
        speed: float = 100.0,
    ) -> Enemy:
        """Spawn or reuse an enemy and add to game's enemy container."""
        # apply slow modifier to every spawn in prologue/limbo
        if getattr(self.game, "selected_stage", None) in (
            "prologo",
            "limbo",
            "limbo_2",
            "limbo_3",
        ):
            speed *= 0.8
        if self.pool:
            e = self.pool.pop()
            try:
                # Reinitialize instance (safe fallback to re-run constructor)
                e.__init__(x, y, enemy_type, health, speed)  # type: ignore[misc]
            except (AttributeError, TypeError, ValueError, KeyError):
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
        except (AttributeError, TypeError, ValueError, KeyError):
            try:
                self.game.enemies.append(e)
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

        return e

    def register(self, e: Enemy) -> None:
        """Register an externally created enemy instance."""
        if e not in self.active:
            self.active.append(e)
        try:
            e.manager = self
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def recycle(self, e: Enemy) -> None:
        """Recycle enemy instance back into pool and remove from game containers."""
        try:
            if e in self.active:
                self.active.remove(e)
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        try:
            if hasattr(self.game.enemies, "remove"):
                self.game.enemies.remove(e)
        except (AttributeError, TypeError, ValueError, KeyError):
            try:
                self.game.enemies.remove(e)
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

        # Reset or hide enemy
        try:
            e.x = -9999
            e.y = -9999
            e.health = 0
            # Clear particles/temporary state where applicable
            e.burn_particles = []
            e.ice_particles = []
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        # Add back to pool
        try:
            self.pool.append(e)
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def spawn_giant_enemy(self, side: str | None = None) -> Enemy:
        """Spawn a giant enemy at the top by default (inside walls), or at a specified side.

        side: "left", "right", or "top". If omitted, defaults to "top" so giants
        appear from above and within wall constraints like other enemies.

        Note: Respects the 12-second cooldown unless a limbo horde is active.
        """
        # Check 12-second cooldown (except during limbo horde)
        if not getattr(self.game, "limbo_horde_active", False):
            if (
                self.game.time_elapsed - self.game.spawn_system.last_giant_spawn_time
            ) < 12.0:
                return None  # Cooldown active, don't spawn

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
            x = self.game.random_x_between_walls()
            y = -30

        # Determine enemy type: hell stage uses custode instead of giant
        stage = getattr(self.game, "selected_stage", "") or ""
        if stage in HELL_STAGES:
            etype = "custode"
        else:
            etype = "giant"
        health = 200 * getattr(
            self.game, "difficulty_multiplier", 1.0
        )  # Doubled from 100
        # Base non-boss giant/custode speed (use giant value as fallback)
        speed = ENEMY_BASE_SPEEDS.get("giant", 45)
        e = self.spawn(x, y, etype, health, speed)
        # Update cooldown timer
        try:
            self.game.spawn_system.last_giant_spawn_time = self.game.time_elapsed
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        return e

    def spawn_crusader_enemy(self, side: str | None = None) -> Enemy:
        """Spawn a crusader enemy.

        Mirrors :meth:`spawn_giant_enemy` but always produces a crusader regardless
        of stage.  The health is set very high and speed comes from the new
        "crusader" base speed entry.
        """
        if side is None:
            side = "top"

        if side == "left":
            x = -30
            y = random.randint(0, max(0, self.game.height))
        elif side == "right":
            x = self.game.width + 30
            y = random.randint(0, max(0, self.game.height))
        else:  # top
            x = self.game.random_x_between_walls()
            y = -30

        health = 200 * getattr(self.game, "difficulty_multiplier", 1.0)
        speed = ENEMY_BASE_SPEEDS.get("crusader", 30)
        c = self.spawn(x, y, "crusader", health, speed)
        return c

    def update_big_enemy_timer(self) -> None:
        """Decrement big enemy timer and spawn a giant when it hits zero (once per wave)."""
        # Don't update timer during victory screen, horde completion, or active horde
        if (
            getattr(self.game, "limbo_horde_completed", False)
            or getattr(self.game, "showing_victory", False)
            or getattr(self.game, "limbo_horde_active", False)
        ):
            return

        self.big_enemy_timer -= 1
        if self.big_enemy_timer <= 0 and not self.big_spawned_this_wave:
            # Block giant spawns in Limbo stages for the first 30 seconds
            stage = str(getattr(self.game, "selected_stage", "") or "")
            if (
                stage in ("limbo", "limbo_2", "limbo_3")
                and getattr(self.game, "time_elapsed", 0.0) < 30.0
            ):
                # Reset timer so it doesn't fire immediately when 30s is reached
                self.big_enemy_timer = 12 * getattr(self.game, "fps", 60)
                return
            try:
                self.spawn_giant_enemy()
                self.big_spawned_this_wave = True
                if getattr(self.game, "wave", 0) >= 6:
                    self.big_enemy_timer = self.big_enemy_fast_interval
                else:
                    self.big_enemy_timer = 12 * getattr(self.game, "fps", 60)
            except (AttributeError, TypeError, ValueError, KeyError):
                # Don't propagate spawn errors to game loop
                pass

    def update_inquisitor_spawns(self) -> None:
        """Randomly spawn inquisitor as a *normal* enemy in Purgatory.

        Behaviour:
        - Only active when current stage startswith 'purgatory'.
        - Spawns as a non-boss `normal` enemy but uses the `inquisitor` appearance.
        - Enforced cap: at most 2 spawns per `inquisitor_spawn_window_frames` (15s by default).
        - Spawn attempts are evaluated once per second with a configurable probability.
        """
        # Only valid for Purgatory/HELL stages
        if not getattr(self.game, "selected_stage", "").startswith(
            ("purgatory", "hell")
        ):
            return

        # Manage window timer (frames)
        if self.inquisitor_spawn_window_timer > 0:
            self.inquisitor_spawn_window_timer -= 1
            if self.inquisitor_spawn_window_timer <= 0:
                self.inquisitor_spawn_window_timer = 0
                self.inquisitor_spawn_count = 0

        # If we've already hit cap, nothing to do
        if self.inquisitor_spawn_count >= 3:
            return

        # Only attempt spawn once per second (stable chance)
        if getattr(self.game, "frame_count", 0) % getattr(self.game, "fps", 60) != 0:
            return

        import random

        if random.random() < self.inquisitor_spawn_chance_per_second:
            # Spawn a normal enemy that looks like an inquisitor
            x = self.game.random_x_between_walls()
            y = -20
            # Use same stats as 'normal' enemies
            health = 50 * getattr(self.game, "difficulty_multiplier", 1.0)
            speed = ENEMY_BASE_SPEEDS.get("normal", 75)

            try:
                e = self.spawn(x, y, "normal", health, speed)
            except (AttributeError, TypeError, ValueError, KeyError):
                try:
                    e = Enemy(x, y, "normal", health, speed)
                    if hasattr(self.game.enemies, "add"):
                        self.game.enemies.add(e)
                    else:
                        self.game.enemies.append(e)
                except (AttributeError, TypeError, ValueError, KeyError):
                    return

            # Make inquisitor-normal slightly larger (+10px) and give +10 HP
            try:
                e.width = getattr(e, "width", 30) + 10
                e.height = getattr(e, "height", 30) + 10
                # Rescale image if present
                try:
                    import pygame

                    if getattr(e, "image", None) is not None:
                        e.image = pygame.transform.smoothscale(
                            e.image, (e.width, e.height)
                        )
                        try:
                            e.base_image = e.image.copy()
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                        e.rect = e.image.get_rect(center=(e.x, e.y))
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

                # Increase HP by 10 (respect max_health semantics)
                try:
                    e.max_health = getattr(e, "max_health", 0) + 10
                    e.health = min(getattr(e, "health", 0) + 10, e.max_health)
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

                # Mark as inquisitor-normal (controls shooting behavior)
                setattr(e, "is_inquisitor_normal", True)
                setattr(e, "inquisitor_fire_single_next", False)
                # Align shoot cooldown to inquisitor rhythm
                try:
                    import random

                    e.shoot_cooldown = random.randint(100, 140)
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

            # Give it inquisitor appearance but keep normal behaviour
            try:
                setattr(e, "appearance", "inquisitor")
                # If an 'enemy_inquisitor.png' asset exists, use it for this instance
                try:
                    from src.assets.manager import get_image

                    img = get_image(
                        "enemy_inquisitor.png",
                        (getattr(e, "width", 32), getattr(e, "height", 32)),
                    )
                    if img is not None:
                        e.image = img.copy()
                        try:
                            e.base_image = e.image.copy()
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

            # Start window timer if not already running
            if self.inquisitor_spawn_window_timer == 0:
                self.inquisitor_spawn_window_timer = self.inquisitor_spawn_window_frames

            self.inquisitor_spawn_count += 1

    def update_wave_boss(self, wave_time: float) -> None:
        """Handle the timed wave boss spawn (at ~38s).

        Important: in the Prologo stage, once the final boss has spawned we must
        not spawn any additional wave bosses — only non-boss enemies should
        continue to appear.
        """
        # Explicitly prevent any wave-boss spawns in Prologo after final boss spawned
        if (
            getattr(self.game, "selected_stage", None) == "prologo"
            and self.prologo_final_boss_spawned
        ):
            return
        # Likewise, once the Limbo Final boss has appeared we should no longer
        # create inquisitors or any other end-of-wave boss; the stage is about
        # to end and further waves are meaningless.
        if (
            getattr(self.game, "selected_stage", None) == "limbo_final"
            and self.limbo_final_boss_spawned
        ):
            return

        if not self.wave_boss_spawned and wave_time >= 38:
            # If we're in a Limbo stage: always spawn the inquisitor boss –
            # the "boss_big" wave boss is forbidden.  This rule applies even on
            # waves divisible by three and matches the new design requirement.
            if getattr(self.game, "is_limbo_stage", lambda: False)():
                self.spawn_boss("inquisitor")
            # Purgatory: alternate end-of-wave boss between medium and inquisitor
            elif getattr(self.game, "selected_stage", "").startswith(
                ("purgatory", "hell")
            ):
                # Use wave parity to alternate: odd waves -> medium, even waves -> inquisitor
                current_wave = getattr(self.game, "wave", 0)
                if current_wave % 2 == 1:
                    self.spawn_boss("mid")
                else:
                    self.spawn_boss("inquisitor")
            elif (
                getattr(self.game, "wave", 0) % 3 == 0
                and getattr(self.game, "wave", 0) > 0
            ):
                self.spawn_boss("big")
            else:
                self.spawn_boss("mid")
            self.wave_boss_spawned = True

    def update_prologo_events(self) -> None:
        """Handle Prologo-specific boss events (final boss spawn, lightning, regen)."""
        try:
            # Final boss spawn at 3:55 (235 seconds)
            if (
                getattr(self.game, "selected_stage", None) == "prologo"
                and not self.prologo_final_boss_spawned
                and getattr(self.game, "time_elapsed", 0) >= 235
            ):
                self.spawn_boss("final")
                self.prologo_final_boss_spawned = True

            # Limbo Final boss at 3:00 (180 seconds)
            if (
                getattr(self.game, "selected_stage", None) == "limbo_final"
                and not self.limbo_final_boss_spawned
                and getattr(self.game, "time_elapsed", 0) >= 180
            ):
                self.spawn_boss("limbo")
                self.limbo_final_boss_spawned = True

            # Lightning strike countdown
            if (
                getattr(self.game, "selected_stage", None) == "prologo"
                and self.prologo_lightning_strike
            ):
                self.prologo_lightning_timer += 1
                if (
                    self.prologo_lightning_timer
                    >= self.prologo_lightning_duration_frames
                ):
                    # Call into game to show Prologo defeat
                    try:
                        self.game.prologo_defeat()
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass
            if (
                getattr(self.game, "selected_stage", None) == "limbo_final"
                and self.limbo_final_lightning_strike
            ):
                self.limbo_final_lightning_timer += 1
                if (
                    self.limbo_final_lightning_timer
                    >= self.limbo_final_lightning_duration_frames
                ):
                    try:
                        self.game.limbo_final_defeat()
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass

            # Boss regeneration when immortal
            for boss in list(getattr(self.game, "bosses", [])):
                # prologue final boss behavior
                if (
                    getattr(boss, "enemy_type", "") == "boss_final"
                    and self.prologo_final_boss_immortal
                    and getattr(boss, "health", 0) < getattr(boss, "max_health", 0)
                ):
                    boss.health = min(getattr(boss, "max_health", 0), boss.health + 3.0)
                    if (
                        boss.health >= boss.max_health
                        and not self.prologo_lightning_strike
                    ):
                        # Trigger lightning and knock out player
                        self.prologo_lightning_strike = True
                        try:
                            if hasattr(self.game, "generate_lightning"):
                                self.game.generate_lightning()
                            else:
                                self.game.lightning_points = [
                                    (
                                        int(
                                            getattr(
                                                self.game.player,
                                                "x",
                                                self.game.width // 2,
                                            )
                                        ),
                                        0,
                                    ),
                                    (
                                        int(
                                            getattr(
                                                self.game.player,
                                                "x",
                                                self.game.width // 2,
                                            )
                                        ),
                                        self.game.height,
                                    ),
                                ]
                            try:
                                self.game.player.health = 0
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                # limbo final boss behavior (same as prologue but separate flags)
                if (
                    getattr(boss, "enemy_type", "") == "boss_limbo"
                    and self.limbo_final_boss_immortal
                    and getattr(boss, "health", 0) < getattr(boss, "max_health", 0)
                ):
                    boss.health = min(getattr(boss, "max_health", 0), boss.health + 3.0)
                    if (
                        boss.health >= boss.max_health
                        and not self.limbo_final_lightning_strike
                    ):
                        self.limbo_final_lightning_strike = True
                        try:
                            if hasattr(self.game, "generate_lightning"):
                                self.game.generate_lightning()
                            else:
                                self.game.lightning_points = [
                                    (
                                        int(
                                            getattr(
                                                self.game.player,
                                                "x",
                                                self.game.width // 2,
                                            )
                                        ),
                                        0,
                                    ),
                                    (
                                        int(
                                            getattr(
                                                self.game.player,
                                                "x",
                                                self.game.width // 2,
                                            )
                                        ),
                                        self.game.height,
                                    ),
                                ]
                            try:
                                self.game.player.health = 0
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
        except (AttributeError, TypeError, ValueError, KeyError):
            # Fail-safe: don't let manager errors break the game loop
            pass

    def spawn_boss(self, boss_type: str = "mid") -> Enemy:
        """Spawn a boss of the specified type ('final', 'big', 'mid').
        Adds the boss to `game.bosses` to preserve existing boss grouping.
        """
        x = self.game.width // 2
        # Special spawn position for prologue bosses - start higher up
        if getattr(self.game, "selected_stage", None) == "prologo" and boss_type in [
            "final",
            "big",
        ]:
            y = -150  # Start higher for walking entrance
        else:
            y = -50

        if boss_type == "final":
            enemy_type = "boss_final"
            health = 2000 * getattr(
                self.game, "difficulty_multiplier", 1.0
            )  # Doubled from 1000
            speed = ENEMY_BASE_SPEEDS.get("boss_final", 40)
        elif boss_type == "big":
            enemy_type = "boss_big"
            health = 1200 * getattr(
                self.game, "difficulty_multiplier", 1.0
            )  # Doubled from 600
            speed = ENEMY_BASE_SPEEDS.get("boss_big", 40)
        elif boss_type == "mid":
            # regular wave boss
            enemy_type = "boss_medium"
            # match spawn_system's health so tests remain consistent
            health = 300 * getattr(self.game, "difficulty_multiplier", 1.0)
            speed = ENEMY_BASE_SPEEDS.get("boss_medium", 45)
        elif boss_type == "inquisitor":
            # Special Limbo boss (HP increased by 50%, now reduced by 15%)
            enemy_type = "boss_inquisitor"
            # Base HP: 525 -> apply -15% for tuning
            health = int(
                950 * 0.9 * getattr(self.game, "difficulty_multiplier", 1.0)
            )  # Reduced from 1050 -> 855
            speed = ENEMY_BASE_SPEEDS.get(
                "boss_inquisitor", 50
            )  # inquisitor speed from balance
        elif boss_type == "limbo":
            # Final Limbo boss (timed event)
            enemy_type = "boss_limbo"
            health = 1500 * getattr(self.game, "difficulty_multiplier", 1.0)
            speed = ENEMY_BASE_SPEEDS.get("boss_limbo", 40)
        elif boss_type == "limbo_horde":
            # Boss spawned at end of the Limbo horde; distinct type so its
            # sprite can differ from the final boss and tests can distinguish.
            enemy_type = "boss_limbo_horde"
            health = 1000 * getattr(self.game, "difficulty_multiplier", 1.0)
            speed = ENEMY_BASE_SPEEDS.get("boss_limbo_horde", 40)

        boss = Enemy(x, y, enemy_type, health, speed)
        # tune limbo bosses specially
        if enemy_type in ("boss_limbo", "boss_limbo_horde"):
            boss.width *= 3
            boss.height *= 3
            boss.radius = (boss.width + boss.height) // 4
            # hitbox is 50% of sprite dimensions so only the body core is
            # collidable; the aura glow around the sprite is purely visual.
            boss._shrink_hitbox = True  # flag handled below
            boss._hitbox_scale = 0.5
        # rebuild sprite image/rect to match new dimensions
        boss.image = pygame.Surface((boss.width, boss.height), pygame.SRCALPHA)
        # always let the enemy handle its own asset/fallback drawing; previously
        # we drew a purple ellipse here for limbo boss which prevented any
        # external sprite from ever being shown.  draw_enemy already knows how
        # to fall back to a vector ellipse when the file is missing, so this
        # simple call is sufficient in all cases.
        try:
            boss.draw_enemy()
        except (AttributeError, TypeError, ValueError, KeyError):
            # defensive: never crash the spawn process
            pass
        try:
            boss.rect = boss.image.get_rect(center=(boss.x, boss.y))
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        # shrink boss_limbo collision rect if requested (after rect created)
        if getattr(boss, "_shrink_hitbox", False):
            try:
                scale = getattr(boss, "_hitbox_scale", 0.5)
                w = int(boss.width * scale)
                h = int(boss.height * scale)
                boss.rect = pygame.Rect(0, 0, w, h)
                boss.rect.center = (int(boss.x), int(boss.y))
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
        try:
            boss.base_image = boss.image.copy()
        except (AttributeError, TypeError, ValueError, KeyError):
            boss.base_image = None

        # Track active
        if boss not in self.active:
            self.active.append(boss)
        # Mark that this boss should drop health when defeated
        boss.should_drop_health = True

        # Add to boss group on game
        try:
            self.game.bosses.add(boss)
        except (AttributeError, TypeError, ValueError, KeyError):
            try:
                self.game.bosses.append(boss)
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
        return boss

    def cleanup(self) -> None:
        """Optional maintenance (shrink pool if too big), not used for now."""
        pass


__all__ = ["EnemyManager"]
