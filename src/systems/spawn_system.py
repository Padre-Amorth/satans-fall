"""Spawn and wave management system."""

from __future__ import annotations

import logging
import math
import random
from typing import TYPE_CHECKING, Any, Dict, List

from src.balance import ENEMY_BASE_SPEEDS
from src.entities.enemy import Enemy
from src.projectile import Projectile

if TYPE_CHECKING:
    from src.game import Game

logger = logging.getLogger(__name__)


class SpawnSystem:
    """Handles enemy spawning, wave progression, and prologo events."""

    def __init__(self, game: "Game") -> None:
        self.game = game

    def update_enemy_spawning(self) -> None:
        """Handle enemy spawning logic (delegates timing to EnemyManager when present)."""
        # Use manager timers if manager exists
        if self.game.enemy_manager is not None:
            self.game.enemy_manager.enemy_spawn_timer -= 1
            if self.game.enemy_manager.enemy_spawn_timer <= 0:
                self.spawn_enemy()
                if self.game.selected_stage == "prologo":
                    self.game.enemy_manager.enemy_spawn_timer = int(
                        self.game.enemy_manager.enemy_spawn_rate * 1.5
                    )
                else:
                    self.game.enemy_manager.enemy_spawn_timer = (
                        self.game.enemy_manager.enemy_spawn_rate
                    )
        else:
            self.game.enemy_spawn_timer -= 1
            if self.game.enemy_spawn_timer <= 0:
                self.spawn_enemy()
                if self.game.selected_stage == "prologo":
                    self.game.enemy_spawn_timer = int(self.game.enemy_spawn_rate * 1.5)
                else:
                    self.game.enemy_spawn_timer = self.game.enemy_spawn_rate

        # Periodic big enemy spawn (delegate to EnemyManager when present)
        if self.game.enemy_manager is not None:
            try:
                self.game.enemy_manager.update_big_enemy_timer()
            except Exception:
                # Fallback to legacy behavior
                self.game.big_enemy_timer -= 1
                if (
                    self.game.big_enemy_timer <= 0
                    and not self.game.big_spawned_this_wave
                ):
                    self.spawn_big_enemy()
                    self.game.big_spawned_this_wave = True
                    if self.game.wave >= 6:
                        self.game.big_enemy_timer = self.game.big_enemy_fast_interval
                    else:
                        self.game.big_enemy_timer = 12 * self.game.fps

            # Also allow EnemyManager to occasionally spawn non-boss inquisitors in Purgatory
            try:
                self.game.enemy_manager.update_inquisitor_spawns()
            except Exception:
                pass
        else:
            self.game.big_enemy_timer -= 1
            if self.game.big_enemy_timer <= 0 and not self.game.big_spawned_this_wave:
                self.spawn_big_enemy()
                self.game.big_spawned_this_wave = True
                if self.game.wave >= 6:
                    self.game.big_enemy_timer = self.game.big_enemy_fast_interval
                else:
                    self.game.big_enemy_timer = 12 * self.game.fps

        # Spawn acceleration
        self.game.spawn_accel_timer -= 1
        if self.game.spawn_accel_timer <= 0:
            # Update both game and manager rates to keep them in sync
            new_rate = max(
                self.game.spawn_min_rate, int(self.game.enemy_spawn_rate * 0.99)
            )
            self.game.enemy_spawn_rate = new_rate
            if self.game.enemy_manager is not None:
                self.game.enemy_manager.enemy_spawn_rate = new_rate
            self.game.spawn_accel_timer = 20 * self.game.fps

    def update_wave_progression(self) -> None:
        """Handle wave progression and boss spawning"""
        # Wave progression based on elapsed seconds or on explicit frame boundary
        frames_per_wave = int(self.game.wave_duration * self.game.fps)
        frame_boundary_hit: bool = (
            frames_per_wave > 0
            and self.game.frame_count % frames_per_wave == 0
            and self.game.frame_count != 0
        )

        if self.game.wave_time >= self.game.wave_duration or frame_boundary_hit:
            self.game.wave += 1
            self.game.wave_time = 0
            # Reset wave boss flag (proxy to manager when available)
            if self.game.enemy_manager is not None:
                try:
                    self.game.enemy_manager.wave_boss_spawned = False
                except Exception:
                    self.game.wave_boss_spawned = False
            else:
                self.game.wave_boss_spawned = False

            # Reset prologo final boss flags if any (proxy to manager when available)
            # Skip reset for prologo to prevent multiple spawns
            if self.game.selected_stage != "prologo":
                if self.game.enemy_manager is not None:
                    try:
                        self.game.enemy_manager.prologo_final_boss_spawned = False
                        self.game.enemy_manager.prologo_final_boss_defeated = False
                        self.game.enemy_manager.prologo_final_boss_immortal = False
                        self.game.enemy_manager.prologo_lightning_timer = 0
                        self.game.enemy_manager.prologo_lightning_strike = False
                    except Exception:
                        self.game.prologo_final_boss_spawned = False
                        self.game.prologo_final_boss_defeated = False
                        self.game.prologo_final_boss_immortal = False
                        self.game.prologo_lightning_timer = 0
                        self.game.prologo_lightning_strike = False
                else:
                    self.game.prologo_final_boss_spawned = False
                    self.game.prologo_final_boss_defeated = False
                    self.game.prologo_final_boss_immortal = False
                    self.game.prologo_lightning_timer = 0
                    self.game.prologo_lightning_strike = False

            # Keep big spawn flag in manager if available
            if self.game.enemy_manager is not None:
                try:
                    self.game.enemy_manager.big_spawned_this_wave = False
                except Exception:
                    self.game.big_spawned_this_wave = False
            else:
                self.game.big_spawned_this_wave = False

            # Adjust spawn rate based on wave
            if self.game.wave < self.game.spawn_ramp_start_wave:
                self.game.enemy_spawn_rate = max(
                    self.game.spawn_min_rate,
                    int(
                        self.game.base_spawn_rate
                        - self.game.wave * self.game.spawn_ramp_slope_pre
                    ),
                )
                if self.game.enemy_manager is not None:
                    self.game.enemy_manager.enemy_spawn_rate = (
                        self.game.enemy_spawn_rate
                    )
            else:
                self.game.enemy_spawn_rate = max(
                    self.game.spawn_min_rate,
                    int(
                        self.game.base_spawn_rate
                        - self.game.wave * self.game.spawn_ramp_slope_post
                    ),
                )
                if self.game.enemy_manager is not None:
                    self.game.enemy_manager.enemy_spawn_rate = (
                        self.game.enemy_spawn_rate
                    )

            self.game.difficulty_multiplier = 1.0 + (self.game.wave * 0.12)

        # Spawn boss at 38 seconds (delegate to manager when available)
        if self.game.enemy_manager is not None:
            try:
                self.game.enemy_manager.update_wave_boss(self.game.wave_time)
            except Exception:
                # Fallback to legacy behavior
                if not self.game.wave_boss_spawned and self.game.wave_time >= 38:
                    if not (
                        self.game.selected_stage == "prologo"
                        and self.game.prologo_final_boss_spawned
                    ):
                        if self.game.wave % 3 == 0 and self.game.wave > 0:
                            self.spawn_boss("big")
                        else:
                            self.spawn_boss("mid")
                    self.game.wave_boss_spawned = True
        else:
            if not self.game.wave_boss_spawned and self.game.wave_time >= 38:
                if not (
                    self.game.selected_stage == "prologo"
                    and self.game.prologo_final_boss_spawned
                ):
                    if self.game.wave % 3 == 0 and self.game.wave > 0:
                        self.spawn_boss("big")
                    else:
                        self.spawn_boss("mid")
                self.game.wave_boss_spawned = True

        # Ensure giant spawns at 12 seconds if not already spawned
        if self.game.wave_time >= 12:
            if self.game.enemy_manager is not None:
                if not self.game.enemy_manager.big_spawned_this_wave:
                    self.spawn_big_enemy()
                    self.game.enemy_manager.big_spawned_this_wave = True
            else:
                if not self.game.big_spawned_this_wave:
                    self.spawn_big_enemy()
                    self.game.big_spawned_this_wave = True

        # Ensure wave boss spawning is handled by manager when available
        if self.game.enemy_manager is not None:
            # manager.update_wave_boss already called earlier; nothing else required here
            pass

    def update_prologo_events(self) -> None:
        """Handle special Prologo events (managed by EnemyManager when present)"""
        if self.game.enemy_manager is not None:
            try:
                self.game.enemy_manager.update_prologo_events()
                return
            except Exception:
                # Fallback to legacy behavior below
                pass

        # Final boss at 3:55 (235 seconds) - delegate to manager when available
        if self.game.enemy_manager is not None:
            try:
                self.game.enemy_manager.update_prologo_events()
            except Exception:
                # fallback to legacy behavior
                if (
                    self.game.selected_stage == "prologo"
                    and not self.game.prologo_final_boss_spawned
                    and self.game.time_elapsed >= 235
                ):
                    logger.info(
                        "[PROLOGO] Spawning final boss at time %s",
                        self.game.time_elapsed,
                    )
                    self.spawn_boss("final")
                    self.game.prologo_final_boss_spawned = True
        else:
            if (
                self.game.selected_stage == "prologo"
                and not self.game.prologo_final_boss_spawned
                and self.game.time_elapsed >= 235
            ):
                logger.info(
                    "[PROLOGO] Spawning final boss at time %s", self.game.time_elapsed
                )
                self.spawn_boss("final")
                self.game.prologo_final_boss_spawned = True

        # Lightning strike when immortal boss reaches full health
        if self.game.selected_stage == "prologo" and self.game.prologo_lightning_strike:
            self.game.prologo_lightning_timer += 1
            if (
                self.game.prologo_lightning_timer
                >= self.game.prologo_lightning_duration_frames
            ):
                self.game.prologo_defeat()

        # Boss regeneration when immortal
        for boss in self.game.bosses:
            if (
                boss.enemy_type == "boss_final"
                and self.game.prologo_final_boss_immortal
                and boss.health < boss.max_health
            ):
                boss.health = min(boss.health + 3.0, boss.max_health)
                if (
                    boss.health >= boss.max_health
                    and not self.game.prologo_lightning_strike
                ):
                    logger.info(
                        "[PROLOGO] Final boss reached full health — triggering lightning strike"
                    )
                    self.game.prologo_lightning_strike = True
                    self.generate_lightning()
                    logger.debug(
                        "[PROLOGO] Lightning points generated: %s",
                        (
                            len(self.game.lightning_points)
                            if hasattr(self.game, "lightning_points")
                            else None
                        ),
                    )
                    self.game.player.health = 0

    def generate_lightning(self) -> None:
        """Generate lightning bolt path"""
        try:
            # Use player's current x as bolt origin, ensure numeric
            bolt_x = int(getattr(self.game.player, "x", self.game.width // 2))
            player_y = int(getattr(self.game.player, "y", self.game.height))
            segments = 10
            pts = []
            pts.append((bolt_x, 0))
            prev_x: int = bolt_x

            for i in range(segments):
                next_y = int((i + 1) * (player_y / segments))
                # Random step but clamp to screen bounds
                next_x = int(prev_x + random.randint(-25, 25))
                next_x = max(0, min(self.game.width, next_x))
                next_y = max(0, min(self.game.height, next_y))
                pts.append((next_x, next_y))
                prev_x = next_x

            pts.append((bolt_x, player_y))
            # Final assign
            self.game.lightning_points = pts
        except Exception as e:
            logger.exception("Exception while generating lightning: %s", e)
            import traceback

            traceback.print_exc()
            self.game.lightning_points = []

    def spawn_enemy(self) -> None:
        # Spawn from top of screen (pick X uniformly between the walls)
        x = self.game.random_x_between_walls()
        y = -20

        # Choose enemy type based on wave and random chance
        rand: float = random.random()
        # Choose health and speed based on type
        health: float = 0.0
        if self.game.wave >= 5 and rand < 0.05:  # 5% chance for giant after wave 5
            enemy_type = "giant"
            health = 160 * self.game.difficulty_multiplier  # Doubled from 80
            # Base non-boss giant speed (from balance)
            speed = ENEMY_BASE_SPEEDS.get("giant", 45)
        # Allow a small chance for 'strong' already in waves 1-2 (10%), larger chance in later waves
        elif self.game.wave < 3 and rand < 0.10:  # 10% chance for strong in waves 1-2
            enemy_type = "strong"
            health = 70 * self.game.difficulty_multiplier
            speed = ENEMY_BASE_SPEEDS.get("strong", 60)
        elif self.game.wave >= 3 and rand < 0.15:  # 15% chance for strong after wave 3
            enemy_type = "strong"
            health = 70 * self.game.difficulty_multiplier  # Doubled from 35
            # Strong enemies (from balance)
            speed = ENEMY_BASE_SPEEDS.get("strong", 60)
        elif rand < 0.3:  # 30% chance for normal
            enemy_type = "normal"
            health = 50 * self.game.difficulty_multiplier  # Doubled from 25
            # Normal enemies (from balance)
            speed = ENEMY_BASE_SPEEDS.get("normal", 75)
        elif rand < 0.5:  # 20% chance for angel
            enemy_type = "angel"
            health = 40 * self.game.difficulty_multiplier  # Doubled from 20
            # Angel speed (from balance)
            speed = ENEMY_BASE_SPEEDS.get("angel", 60)
        else:  # 25% chance for weak
            enemy_type = "weak"
            health = 30 * self.game.difficulty_multiplier  # Doubled from 15
            # Weak enemies (from balance)
            speed = ENEMY_BASE_SPEEDS.get("weak", 35)

        # mage override: only after purgatory starts and once timer expires (~15s)
        if (getattr(self.game, "selected_stage", None) or "").startswith(
            ("purgatory", "hell")
        ):
            if not hasattr(self.game, "mage_last_spawn_frame"):
                # just initialize; no chance to convert on this spawn
                self.game.mage_last_spawn_frame = getattr(self.game, "frame_count", 0)
            else:
                elapsed = (
                    getattr(self.game, "frame_count", 0)
                    - self.game.mage_last_spawn_frame
                )
                if elapsed >= getattr(self.game, "fps", 60) * 15:
                    # don't allow more than two mage enemies at once
                    mage_count = 0
                    for e in getattr(self.game, "enemies", []):
                        if getattr(e, "enemy_type", None) == "mage":
                            mage_count += 1
                    if mage_count < 2:
                        try:
                            if random.random() < 0.5:
                                enemy_type = "mage"
                                health = 60 * self.game.difficulty_multiplier
                                speed = ENEMY_BASE_SPEEDS.get("mage", 50)
                                # only reset timer when a mage actually spawned
                                self.game.mage_last_spawn_frame = getattr(
                                    self.game, "frame_count", 0
                                )
                        except Exception:
                            pass
                    else:
                        # if already two mages, do nothing; wait until one is gone
                        pass

        # convert some strong enemies into shielded variants for non-prologo stages
        if enemy_type == "strong" and (
            getattr(self.game, "selected_stage", None) or ""
        ) not in ("", "prologo"):
            # only consider after determining final type, reuse rand for consistency
            # 50% of the time (increased)
            try:
                if random.random() < 0.50:
                    enemy_type = "shielded"
            except Exception:
                pass
        # Use EnemyManager when available
        if self.game.enemy_manager is not None:
            try:
                self.game.enemy_manager.spawn(x, y, enemy_type, health, speed)
            except Exception:
                enemy = Enemy(x, y, enemy_type, health, speed)
                if hasattr(self.game.enemies, "add"):
                    self.game.enemies.add(enemy)
                else:
                    self.game.enemies.append(enemy)
        else:
            enemy = Enemy(x, y, enemy_type, health, speed)
            if hasattr(self.game.enemies, "add"):
                self.game.enemies.add(enemy)
            else:
                self.game.enemies.append(enemy)

    def spawn_enemy_projectiles(self) -> None:
        """Have some enemies shoot projectiles at the player"""
        # Only some enemies shoot (angels, inquisitor-normal, and bosses)
        shooting_enemies = []
        for enemy in self.game.enemies:
            if enemy.enemy_type in ["angel"] or (
                enemy.enemy_type == "normal"
                and getattr(enemy, "appearance", None) == "inquisitor"
            ):
                shooting_enemies.append(enemy)
        for boss in self.game.bosses:
            if boss.enemy_type in [
                "boss_medium",
                "boss_big",
                "boss_final",
                "boss_inquisitor",
            ]:
                shooting_enemies.append(boss)

        # Limit to 2-3 shooters at a time
        shooting_enemies = shooting_enemies[:3]

        for enemy in shooting_enemies:
            # Calculate direction to player
            dx = self.game.player.x - enemy.x
            dy = self.game.player.y - enemy.y
            distance: float = math.sqrt(dx * dx + dy * dy)

            if distance > 0:
                # Normalize direction
                dx /= distance
                dy /= distance

                # Create projectile
                speed = 200
                projectile: Projectile = Projectile(
                    enemy.x,
                    enemy.y,
                    dx * speed,
                    dy * speed,
                    damage=8,
                    radius=4,
                    is_enemy_projectile=True,
                )
                self.game.enemy_projectiles.add(projectile)

    def spawn_giant_enemy(self) -> None:
        """Spawn a giant enemy at random edge (delegates to EnemyManager)."""
        if self.game.enemy_manager is not None:
            try:
                self.game.enemy_manager.spawn_giant_enemy()
                return
            except Exception:
                pass

        # Fallback to original behavior
        side: str = random.choice(["left", "right", "top"])

        if side == "left":
            x = -30
            y = random.randint(0, self.game.height)
        elif side == "right":
            x = self.game.width + 30
            y = random.randint(0, self.game.height)
        else:  # top
            x = self.game.random_x_between_walls()
            y = -30

        # Choose type based on current stage: Hell replaces giants with custodes
        stage = getattr(self.game, "selected_stage", "") or ""
        if stage.startswith("hell"):
            enemy_type = "custode"
        else:
            enemy_type = "giant"
        health: float = 100 * self.game.difficulty_multiplier
        # Base non-boss giant (and custode) speed (from balance)
        speed = ENEMY_BASE_SPEEDS.get("giant", 45)
        enemy: Enemy = Enemy(x, y, enemy_type, health, speed)
        if hasattr(self.game.enemies, "add"):
            self.game.enemies.add(enemy)
        else:
            self.game.enemies.append(enemy)

    def spawn_big_enemy(self) -> None:
        """Spawn a big enemy (giant). Delegates to EnemyManager if available."""
        if self.game.enemy_manager is not None:
            try:
                self.game.enemy_manager.spawn_giant_enemy()
                return
            except Exception:
                pass

        x = self.game.random_x_between_walls()
        y = -30

        # choose type based on stage like spawn_giant_enemy
        stage = getattr(self.game, "selected_stage", "") or ""
        if stage.startswith("hell"):
            enemy_type = "custode"
        else:
            enemy_type = "giant"
        health: float = 100 * self.game.difficulty_multiplier
        # Base non-boss giant/custode speed (spawn fallback)
        speed = ENEMY_BASE_SPEEDS.get("giant", 45)
        enemy: Enemy = Enemy(x, y, enemy_type, health, speed)
        if hasattr(self.game.enemies, "add"):
            self.game.enemies.add(enemy)
        else:
            self.game.enemies.append(enemy)

    def spawn_reinforcements(self, x=None, y=None, count=None):
        """Spawn a short-lived cluster of reinforcements near (x,y) or at a random building.
        If x,y are None the spawn will originate from a random building at the top.
        `count` overrides the default reinforcement_count."""
        try:
            if x is None or y is None:
                if self.game.buildings:  # If there are buildings (prologo)
                    building: Dict[str, Any] = random.choice(self.game.buildings)
                    x = building["x"] + random.randint(-20, 20)
                    # Clamp building-based spawn inside walls
                    x = self.game.clamp_to_walls(x)
                    y = building["y"]
                else:  # No buildings (limbo), spawn at random top position
                    x = self.game.random_x_between_walls(margin=100)
                    y = 50
            if count is None:
                count: int = self.game.reinforcement_count

            # If this is an "extra" reinforcement (e.g., mid-boss doubled call), reduce enemies by 1/3
            # to make the extra wave smaller and less overwhelming. This is a silent adjustment.
            if count > self.game.reinforcement_count:
                count: int = max(1, int(round(count * 2.0 / 3.0)))

            # Choose types biased to normal/angel
            # include mage with a modest weight so reinforcements can sometimes
            # bring a support caster, but only once we've unlocked purgatory+.
            if (getattr(self.game, "selected_stage", None) or "").startswith(
                ("purgatory", "hell")
            ):
                weights: List[float] = [
                    0.25,  # weak
                    0.35,  # normal
                    0.15,  # strong
                    0.25,  # angel
                    0.05,  # mage
                ]
                types = ["weak", "normal", "strong", "angel", "mage"]
            else:
                weights = [0.3, 0.4, 0.2, 0.3]  # no mage before purgatory
                types = ["weak", "normal", "strong", "angel"]
            for i in range(count):
                etype: str = random.choices(types, weights=weights)[0]

                # Scatter reinforced enemies in a broader area to avoid clustering
                angle: float = random.uniform(0, 2 * math.pi)
                r: int = random.randint(40, 160)
                rx = int(x + math.cos(angle) * r)
                ry = int(y + math.sin(angle) * r)

                # Clamp positions into the playable area
                rx: int = max(30, min(self.game.width - 30, rx))
                # Also clamp to walls so reinforcements don't appear outside bounds
                rx = self.game.clamp_to_walls(rx)
                # Keep regular enemies generally in the upper area when spawning from top
                if etype != "angel":
                    ry: int = max(40, min(self.game.height - 120, ry))
                else:
                    # Angels always spawn from the top band
                    rx: int = max(50, min(self.game.width - 50, rx))
                    ry = 50

                if etype == "weak":
                    enemy_type = "weak"
                    health = int(15 * self.game.difficulty_multiplier * 1.1)
                    speed = ENEMY_BASE_SPEEDS.get("weak", 35)
                elif etype == "normal":
                    enemy_type = "normal"
                    health = int(25 * self.game.difficulty_multiplier * 1.1)
                    speed = ENEMY_BASE_SPEEDS.get("normal", 75)
                elif etype == "strong":
                    enemy_type = "strong"
                    health = int(45 * self.game.difficulty_multiplier * 1.1)
                    speed = ENEMY_BASE_SPEEDS.get("strong", 60)
                elif etype == "mage":
                    enemy_type = "mage"
                    health = int(60 * self.game.difficulty_multiplier * 1.1)
                    speed = ENEMY_BASE_SPEEDS.get("mage", 50)
                else:  # angel
                    enemy_type = "angel"
                    health = int(30 * self.game.difficulty_multiplier * 1.1)
                    speed = ENEMY_BASE_SPEEDS.get("angel", 60)

                enemy: Enemy = Enemy(rx, ry, enemy_type, health, speed)
                self.game.enemies.add(enemy)
        except Exception as e:
            logger.exception("Error spawning reinforcements: %s", e)
            import traceback

            traceback.print_exc()

    def spawn_boss(self, boss_type) -> None:
        """Spawn a boss of the specified type (delegates to EnemyManager)."""
        if self.game.enemy_manager is not None:
            try:
                self.game.enemy_manager.spawn_boss(boss_type)
                return
            except Exception:
                pass

        # Spawn boss at top center
        x: int = self.game.width // 2
        y = -50

        # Decide health and speed per boss type
        health: float = 0.0
        if boss_type == "final":
            enemy_type = "boss_final"
            health = 1000 * self.game.difficulty_multiplier
            speed = ENEMY_BASE_SPEEDS.get("boss_final", 40)
        elif boss_type == "big":
            enemy_type = "boss_big"
            health = 600 * self.game.difficulty_multiplier
            speed = ENEMY_BASE_SPEEDS.get("boss_big", 40)
        else:  # mid
            enemy_type = "boss_medium"
            health = 300 * self.game.difficulty_multiplier
            speed = ENEMY_BASE_SPEEDS.get("boss_medium", 45)

        boss: Enemy = Enemy(x, y, enemy_type, health, speed)
        self.game.bosses.add(boss)
