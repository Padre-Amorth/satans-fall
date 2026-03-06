"""Blasphemy 5 blink and revive system.

Handles:
- Blink teleportation (SPACEBAR): 120px dash in movement direction
- Revive: one-time per-run healing when killed (blasphemy_10)
- Pause-on-revive with 2-second auto-resume
"""

from __future__ import annotations

import logging
import math
import random
from typing import TYPE_CHECKING, Any

import pygame

if TYPE_CHECKING:
    from src.game import Game

logger: logging.Logger = logging.getLogger(__name__)


class Blasphemy5System:
    """Manages Blasphemy 5 blink and Blasphemy 10 revive mechanics."""

    def __init__(self, game: Game) -> None:
        """Initialize system with game reference."""
        self.game = game

        # ---- Revive state (blasphemy_10) ----
        self.blasphemy_5_revived: bool = False
        self.blasphemy_5_pause_timer: int = 0
        self._paused_by_blasphemy5: bool = False

        # ---- Blink state (blasphemy_5) ----
        self.blasphemy_5_blink_cooldown: int = 0
        self.blasphemy_5_blink_state: int = 0  # 0=idle, 1=pre, 2=invisible, 3=post
        self.blasphemy_5_blink_timer: int = 0
        self.blasphemy_5_blink_target_x: float = 0
        self.blasphemy_5_blink_target_y: float = 0
        self.blasphemy_5_blink_origin_x: float = 0
        self.blasphemy_5_blink_origin_y: float = 0
        self.blasphemy_5_blink_particles: list[dict[str, Any]] = []
        self.blasphemy_5_invisible: bool = False
        self.blasphemy_5_invulnerable: bool = False

    def reset(self) -> None:
        """Reset revive state at start of run. Called from reset_run()."""
        self.blasphemy_5_revived = False
        self.blasphemy_5_pause_timer = 0
        self._paused_by_blasphemy5 = False
        # Blink state resets naturally via __init__ defaults

    def update(self) -> None:
        """Per-frame update for blink animation and auto-resume.

        Called from _update_pre_guard_state() before other gameplay logic.
        Runs even while paused.
        """
        # Blink animation tick
        self.update_blasphemy5_blink_animation()

        # Blink cooldown countdown
        if self.blasphemy_5_blink_cooldown > 0:
            self.blasphemy_5_blink_cooldown -= 1

        # Auto-resume after revive pause
        if self.blasphemy_5_pause_timer > 0:
            self.blasphemy_5_pause_timer -= 1
            if self.blasphemy_5_pause_timer <= 0:
                # Auto-resume game after 2 seconds
                self.game.paused = False
                self._paused_by_blasphemy5 = False

    def execute_blasphemy5_blink(self) -> None:
        """Execute Blasphemy 5 blink ability: teleport 120px in current movement direction.

        Gets called when spacebar is pressed during gameplay and blasphemy_5 > 0.
        Teleports the player in the direction they are currently moving.
        Animation: 10 frame pre-blink + 15 frame invisible transit + 10 frame post-arrival.
        """
        blasphemy_5_level = self.game.permanent_stats.get("blasphemy_5", 0)
        if blasphemy_5_level <= 0:
            return

        # If already blinking or cooldown active, don't start another blink
        if self.blasphemy_5_blink_state > 0:
            return

        if self.blasphemy_5_blink_cooldown > 0:
            return

        # Get movement direction from currently pressed keys
        keys = pygame.key.get_pressed()
        vx = 0
        vy = 0

        # Horizontal movement
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            vx = -self.game.player.speed
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            vx = self.game.player.speed

        # Vertical movement
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            vy = -self.game.player.speed
        elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
            vy = self.game.player.speed

        # If no keys pressed, fall back to velocity
        if abs(vx) < 0.1 and abs(vy) < 0.1:
            vx = self.game.player.velocity_x
            vy = self.game.player.velocity_y

        # If still not moving, don't blink (no direction)
        if abs(vx) < 0.1 and abs(vy) < 0.1:
            return

        # Normalize direction vector
        magnitude = math.hypot(vx, vy)
        if magnitude > 0:
            vx_norm = vx / magnitude
            vy_norm = vy / magnitude
        else:
            return

        # Blink distance: 120px
        blink_distance = 120.0

        # Calculate new position
        new_x = self.game.player.x + vx_norm * blink_distance
        new_y = self.game.player.y + vy_norm * blink_distance

        # Clamp to screen bounds
        margin = 30
        new_x = max(margin, min(self.game.width - margin, new_x))
        new_y = max(margin, min(self.game.height - margin, new_y))

        # Store origin position for particle effects
        self.blasphemy_5_blink_origin_x = self.game.player.x
        self.blasphemy_5_blink_origin_y = self.game.player.y

        # Store target and start pre-blink animation
        self.blasphemy_5_blink_target_x = new_x
        self.blasphemy_5_blink_target_y = new_y
        self.blasphemy_5_blink_state = 1  # Pre-blink state
        self.blasphemy_5_blink_timer = 10  # 10 frame pre-delay
        self.blasphemy_5_invisible = False  # Visible during pre-blink
        self.blasphemy_5_invulnerable = True  # Immortal immediately

        # Create violet particles at origin point (6-8 particles)
        num_particles = random.randint(6, 8)
        self.blasphemy_5_blink_particles = []
        for _ in range(num_particles):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(0.5, 2.0)
            particle = {
                "x": self.game.player.x,
                "y": self.game.player.y,
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "life": 25,
                "max_life": 25,
                "alpha": 160,
                "size": 6,
            }
            self.blasphemy_5_blink_particles.append(particle)

        # Set cooldown: 5 seconds
        self.blasphemy_5_blink_cooldown = int(5 * self.game.fps)

    def update_blasphemy5_blink_animation(self) -> None:
        """Update blink animation state machine and execute teleport.

        States:
        - 0: No animation
        - 1: Pre-blink (10 frames, visible & invulnerable)
        - 2: Invisible transit (15 frames, invisible & invulnerable)
        - 3: Post-arrival (10 frames, visible & vulnerable)
        """
        if self.blasphemy_5_blink_state == 0:
            return

        self.blasphemy_5_blink_timer -= 1

        # Update blink particles (fade out and spread)
        for p in self.blasphemy_5_blink_particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["life"] -= 1
            # Fade alpha as life decreases
            max_life = p.get("max_life", 24)
            p["alpha"] = int(160 * (max(0, p["life"]) / max(1, max_life)))

        # Remove dead particles
        self.blasphemy_5_blink_particles = [
            p for p in self.blasphemy_5_blink_particles if p["life"] > 0
        ]

        if self.blasphemy_5_blink_state == 1:  # Pre-blink state
            self.blasphemy_5_invisible = False
            self.blasphemy_5_invulnerable = True
            if self.blasphemy_5_blink_timer <= 0:
                # Transition to invisible phase
                self.blasphemy_5_blink_state = 2
                self.blasphemy_5_blink_timer = 15
                self.blasphemy_5_invisible = True
                self.blasphemy_5_invulnerable = True

        elif self.blasphemy_5_blink_state == 2:  # Invisible phase
            self.blasphemy_5_invisible = True
            self.blasphemy_5_invulnerable = True
            if self.blasphemy_5_blink_timer <= 0:
                # Execute teleport
                self.game.player.x = self.blasphemy_5_blink_target_x
                self.game.player.y = self.blasphemy_5_blink_target_y
                # Create arrival particles
                num_particles = random.randint(6, 8)
                for _ in range(num_particles):
                    angle = random.uniform(0, 2 * math.pi)
                    speed = random.uniform(0.5, 2.0)
                    particle = {
                        "x": self.game.player.x,
                        "y": self.game.player.y,
                        "vx": math.cos(angle) * speed,
                        "vy": math.sin(angle) * speed,
                        "life": 10,
                        "max_life": 10,
                        "alpha": 160,
                        "size": 6,
                    }
                    self.blasphemy_5_blink_particles.append(particle)
                # Move to post-blink state
                self.blasphemy_5_blink_state = 3
                self.blasphemy_5_blink_timer = 10
                self.blasphemy_5_invisible = False

        elif self.blasphemy_5_blink_state == 3:  # Post-blink state
            self.blasphemy_5_invisible = False
            self.blasphemy_5_invulnerable = False
            if self.blasphemy_5_blink_timer <= 0:
                # Animation complete
                self.blasphemy_5_blink_state = 0
                self.blasphemy_5_invisible = False
                self.blasphemy_5_invulnerable = False

    def _handle_blasphemy5_revive(self) -> bool:
        """Handle blasphemy-10 one-time player revive on death.

        Returns True if revive was triggered, False otherwise.
        """
        if (
            self.game.permanent_stats.get("blasphemy_10", 0)
            and not self.blasphemy_5_revived
        ):
            try:
                self.blasphemy_5_revived = True
                # Heal to 50% max health
                self.game.player.health = max(1, int(self.game.player.max_health * 0.5))

                # Create revive explosion
                try:
                    px = int(self.game.player.x)
                    py = int(self.game.player.y)
                    explosion_radius = 100

                    # Explosion visual (matches skullboom_explosions structure)
                    explode_duration = int(2 * self.game.fps)
                    self.game.skullboom_explosions.append(
                        {
                            "x": px,
                            "y": py,
                            "radius": explosion_radius,
                            "max_radius": explosion_radius,
                            "timer": explode_duration,
                            "max_timer": explode_duration,
                            "color": (255, 80, 80),
                            "inner_color": (255, 150, 50),
                            "revive": True,
                        }
                    )

                    # Spawn red particles
                    for _ in range(36):
                        ang = random.uniform(0, 2 * math.pi)
                        spd = random.choice(
                            [
                                random.uniform(40, 120),
                                random.uniform(120, 260),
                                random.uniform(260, 420),
                            ]
                        )
                        vx = math.cos(ang) * spd
                        vy = math.sin(ang) * spd
                        from src.entities.enemy import BurnParticle as _BP

                        life = random.randint(16, 48)
                        size = random.randint(2, 8)
                        p = _BP(
                            px + random.uniform(-10, 10),
                            py + random.uniform(-10, 10),
                            vx,
                            vy,
                            life=life,
                            size=size,
                        )
                        # ~30% orange particles for variety
                        if random.random() < 0.30:
                            setattr(p, "color_override", (255, 150, 50))
                        self.game.blasphemy5_particles.append(p)

                    # Damage nearby enemies
                    dmg_amount = 45
                    all_targets: list[Any] = []
                    all_targets.extend(
                        self.game.enemies
                        if getattr(self.game, "enemies", None) is not None
                        else []
                    )
                    if hasattr(self.game, "bosses") and self.game.bosses:
                        if hasattr(self.game.bosses, "sprites"):
                            all_targets.extend(self.game.bosses.sprites())
                        else:
                            all_targets.extend(self.game.bosses)

                    for enemy in all_targets:
                        try:
                            ex, ey = self.game._enemy_pos(enemy)
                            dist = math.hypot(ex - px, ey - py)
                            if dist <= explosion_radius:
                                try:
                                    enemy.take_damage(dmg_amount, show_floating=False)
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    try:
                                        enemy.health = max(0, enemy.health - dmg_amount)
                                    except (
                                        AttributeError,
                                        TypeError,
                                        ValueError,
                                        KeyError,
                                    ):
                                        pass
                                # Show floating damage
                                try:
                                    self.game.spawn_floating_text(
                                        str(dmg_amount),
                                        ex,
                                        ey - self.game._enemy_radius(enemy) - 8,
                                        color=(255, 100, 100),
                                        font_size=20,
                                    )
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

                # Pause and schedule auto-resume
                self.game.paused = True
                self._paused_by_blasphemy5 = True
                self.blasphemy_5_pause_timer = int(2 * self.game.fps)
                # Show revive message
                try:
                    self.game.show_centered_message("REVIVED", 2000, (200, 80, 80), 64)
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
                return True
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
        return False
