import importlib
from typing import TYPE_CHECKING, Any

from pygame import Rect, Surface

if TYPE_CHECKING:
    import pygame  # type: ignore

try:
    pygame: importlib.ModuleType = importlib.import_module("pygame")
except Exception:
    # Fallback to pygame-ce when running in environments where SDL is available
    pygame: importlib.ModuleType = importlib.import_module("pygame_ce")  # type: ignore

import logging
import math
import os
import random

# Import Projectile explicitly from src.projectile for stability
from src.projectile import Projectile

logger: logging.Logger = logging.getLogger(__name__) 


class Enemy(pygame.sprite.Sprite):
    def __init__(self, x, y, enemy_type="basic", health=20, speed=100) -> None:
        super().__init__()
        self.x: Any = x
        self.y: Any = y
        self.enemy_type: str = enemy_type
        self.max_health: int = health
        self.health: int = health
        self.speed: int = speed
        self.width = 30
        self.height = 30
        self.damage = 10

        # Adjust size and damage based on type
        if enemy_type == "strong":
            self.width = 40
            self.height = 40
            self.damage = 15
        elif enemy_type == "giant":
            self.width = 50
            self.height = 50
            self.damage = 20
        elif enemy_type == "angel":
            self.width = 35
            self.height = 35
            self.damage = 12
        elif enemy_type == "boss_medium":
            self.width = 60
            self.height = 60
            self.damage = 25
        elif enemy_type == "boss_final":
            # Set final boss size explicitly to 100x100
            self.width = 100
            self.height = 100
            self.damage = 30

        # Make enemies slightly larger by 10 pixels (except final boss keeps canonical size)
        if self.enemy_type != "boss_final":
            self.width += 10
            self.height += 10

        # Increase health by 20% for all enemies
        self.max_health = int(self.max_health * 1.2)
        self.health: int = self.max_health

        # Calculate radius from width/height (average)
        self.radius: int = (self.width + self.height) // 4

        # Shooting cooldown for enemies that shoot
        if enemy_type == "normal":
            self.shoot_cooldown: int = random.randint(60, 120)
        elif enemy_type == "boss_medium":
            self.shoot_cooldown: int = random.randint(60, 120)
        elif enemy_type == "boss_final":
            self.shoot_cooldown: int = random.randint(60, 110)
        elif enemy_type in ["boss_big"]:
            # Boss_big doesn't have regular shooting, only special attacks
            self.shoot_cooldown = None
        else:
            self.shoot_cooldown = None

        # Boss pattern timers
        if enemy_type == "boss_big":
            self.pattern_timer: int = random.randint(100, 180)
            self.big_shot_cooldown: int = random.randint(200, 320)
        elif enemy_type == "boss_final":
            self.pattern_timer: int = random.randint(80, 150)
        else:
            self.pattern_timer = None
            self.big_shot_cooldown = None

        # Create image
        self.image = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self.draw_enemy()
        self.rect: Rect | logging.Any = self.image.get_rect(center=(self.x, self.y))

        # Keep a copy of the base image so we can add temporary effects (glow/shine)
        try:
            self.base_image: Surface | logging.Any = self.image.copy()
        except Exception:
            self.base_image = None
        # Shine state for final boss phase
        self.shine_phase = 0.0
        self.shining = False

        self.shake_timer = 0

    def draw_enemy(self) -> None:
        """Draw enemy based on type, try to load image first"""
        # Map enemy types to asset names
        asset_name: str = f"enemy_{self.enemy_type}.png"
        if self.enemy_type.startswith("boss_"):
            # For bosses, remove the 'boss_' prefix
            boss_type: str = self.enemy_type.replace("boss_", "")
            asset_name: str = f"boss_{boss_type}.png"

        try:
            # Robust assets path: two levels up from src/entities -> project root 'assets'
            assets_dir: str = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "assets")
            )
            image_path: str = os.path.join(assets_dir, asset_name)
            loaded_image: Surface | logging.Any = pygame.image.load(image_path).convert_alpha()
            self.image: Surface | logging.Any = pygame.transform.scale(loaded_image, (self.width, self.height))
        except Exception as e:
            logger.warning(
                "Could not load %s, using fallback drawing: %s", asset_name, e
            )
            # Fallback to drawing
            self.draw_demon()

    def draw_demon(self) -> None:
        """Draw an enemy demon - fallback vector art"""
        self.image.fill((0, 0, 0, 0))  # Transparent background

        if self.enemy_type == "weak":
            # Light blue weak angel fallback art
            # Body (light blue)
            pygame.draw.ellipse(
                self.image, (135, 206, 235), (10, 15, 10, 12)
            )  # Light blue
            # Head (lighter blue)
            pygame.draw.circle(self.image, (176, 212, 241), (15, 8), 5)
            # Wings (light)
            pygame.draw.polygon(
                self.image, (224, 244, 255), [(5, 15), (1, 12), (2, 18)]
            )  # Left wing
            pygame.draw.polygon(
                self.image, (224, 244, 255), [(25, 15), (29, 12), (28, 18)]
            )  # Right wing
            # Eyes (small)
            pygame.draw.circle(self.image, (0, 0, 0), (13, 6), 1)
            pygame.draw.circle(self.image, (0, 0, 0), (17, 6), 1)

        elif self.enemy_type == "normal":
            # White normal angel
            # Body (white)
            pygame.draw.ellipse(self.image, (255, 255, 255), (10, 15, 10, 12))
            # Head (light gray)
            pygame.draw.circle(self.image, (240, 240, 240), (15, 8), 5)
            # Wings (white)
            pygame.draw.polygon(
                self.image, (248, 248, 255), [(5, 15), (1, 12), (2, 18)]
            )  # Left wing
            pygame.draw.polygon(
                self.image, (248, 248, 255), [(25, 15), (29, 12), (28, 18)]
            )  # Right wing
            # Eyes
            pygame.draw.circle(self.image, (0, 0, 0), (13, 6), 1)
            pygame.draw.circle(self.image, (0, 0, 0), (17, 6), 1)

        elif self.enemy_type == "strong":
            # Red strong enemy
            # Body (red)
            pygame.draw.ellipse(self.image, (200, 50, 50), (8, 13, 14, 16))
            # Head (darker red)
            pygame.draw.circle(self.image, (180, 30, 30), (15, 6), 6)
            # Horns (dark red)
            pygame.draw.polygon(self.image, (120, 20, 20), [(10, 1), (12, -2), (14, 2)])
            pygame.draw.polygon(self.image, (120, 20, 20), [(16, 1), (18, -2), (20, 2)])
            # Eyes (yellow evil eyes)
            pygame.draw.circle(self.image, (255, 255, 0), (12, 4), 1)
            pygame.draw.circle(self.image, (255, 255, 0), (18, 4), 1)

        elif self.enemy_type == "angel":
            # Purple angel
            # Body (purple)
            pygame.draw.ellipse(self.image, (150, 50, 150), (10, 15, 10, 12))
            # Head (light purple)
            pygame.draw.circle(self.image, (200, 100, 200), (15, 8), 5)
            # Wings (purple)
            pygame.draw.polygon(
                self.image, (220, 160, 220), [(3, 15), (0, 10), (1, 20), (5, 18)]
            )  # Left wing
            pygame.draw.polygon(
                self.image, (220, 160, 220), [(27, 15), (31, 10), (30, 20), (25, 18)]
            )  # Right wing
            # Halo (gold)
            pygame.draw.circle(self.image, (255, 215, 0), (15, 2), 3, 1)
            # Eyes
            pygame.draw.circle(self.image, (0, 0, 0), (13, 6), 1)
            pygame.draw.circle(self.image, (0, 0, 0), (17, 6), 1)

        elif self.enemy_type == "giant":
            # Large brown giant
            # Body (brown)
            pygame.draw.ellipse(self.image, (139, 69, 19), (5, 10, 20, 25))
            # Head (darker brown)
            pygame.draw.circle(self.image, (101, 67, 33), (15, 5), 8)
            # Eyes (red)
            pygame.draw.circle(self.image, (255, 0, 0), (12, 3), 1)
            pygame.draw.circle(self.image, (255, 0, 0), (18, 3), 1)
            # Fangs
            pygame.draw.polygon(
                self.image, (255, 255, 255), [(14, 8), (15, 12), (16, 8)]
            )

        else:
            # Default demon (bosses)
            # Body (dark red/purple)
            pygame.draw.ellipse(self.image, (100, 20, 50), (8, 13, 14, 16))
            # Head (dark)
            pygame.draw.circle(self.image, (80, 15, 40), (15, 6), 6)
            # Horns (black)
            pygame.draw.polygon(self.image, (0, 0, 0), [(10, 1), (12, -3), (14, 2)])
            pygame.draw.polygon(self.image, (0, 0, 0), [(16, 1), (18, -3), (20, 2)])
            # Eyes (glowing red)
            pygame.draw.circle(self.image, (255, 0, 0), (12, 4), 2)
            pygame.draw.circle(self.image, (255, 0, 0), (18, 4), 2)

    def update(self, player, game=None):
        try:
            if self.shake_timer > 0:
                self.shake_timer -= 1
            # Special behavior for bosses in prologue
            if (
                game
                and self.enemy_type in ["boss_final", "boss_big"]
                and game.selected_stage == "prologo"
            ):
                # If immortal (regenerating) - only for final boss
                if game.prologo_final_boss_immortal and self.enemy_type == "boss_final":
                    # Stop floating, move toward the center of the screen (regeneration phase)
                    target_x = game.width / 2
                    desired_y = game.height / 2 - 50  # Stop slightly above center
                    # Smoothly interpolate toward center (even slower movement)
                    self.x += (target_x - self.x) * 0.01
                    self.y += (desired_y - self.y) * 0.01 + 0.3
                    # Prevent moving below the playable area
                    self.y = min(self.y, game.height - 60)

                    # Gradually increase size by 50% while moving
                    if not hasattr(self, "size_interp"):
                        self.size_interp = 0.0
                        self.original_width: int = self.width
                        self.original_height: int = self.height
                        self.target_width = int(self.width * 1.5)
                        self.target_height = int(self.height * 1.5)
                    self.size_interp += 0.01  # Slow size increase
                    self.size_interp: float = min(self.size_interp, 1.0)
                    self.width = int(
                        self.original_width
                        + (self.target_width - self.original_width) * self.size_interp
                    )
                    self.height = int(
                        self.original_height
                        + (self.target_height - self.original_height) * self.size_interp
                    )
                    self.radius: int = (self.width + self.height) // 4

                    # Scale the base image to new size
                    if getattr(self, "base_image", None) is not None:
                        self.image: Surface | logging.Any = pygame.transform.scale(
                            self.base_image, (self.width, self.height)
                        )
                    else:
                        # Fallback: redraw at new size
                        self.image = pygame.Surface(
                            (self.width, self.height), pygame.SRCALPHA
                        )
                        self.draw_enemy()

                    # Start pulsing shine
                    self.shining = True
                    self.shine_phase += 0.15
                    pulse: int = int((math.sin(self.shine_phase) + 1) / 2 * 150) + 20

                    # Compose image: base + glow overlay using additive blending
                    try:
                        overlay = pygame.Surface(
                            (self.width * 3 // 2, self.height * 3 // 2), pygame.SRCALPHA
                        )
                        center: tuple[int | Any, int | Any] = (overlay.get_width() // 2, overlay.get_height() // 2)
                        glow_radius: int = max(self.width, self.height)
                        pygame.draw.circle(
                            overlay, (255, 220, 120, pulse), center, glow_radius
                        )
                        overlay_rect: Rect | logging.Any = overlay.get_rect(
                            center=(self.width // 2, self.height // 2)
                        )
                        # Additive blit for glow effect
                        self.image.blit(
                            overlay, overlay_rect, special_flags=pygame.BLEND_ADD
                        )
                    except Exception:
                        # If anything goes wrong (headless env), ignore and continue
                        pass
                else:
                    # Stay at top of screen, float horizontally
                    self.y = 50  # Keep at top

                    # Initialize floating movement
                    if not hasattr(self, "float_center_x"):
                        self.float_center_x = self.x  # Center point of oscillation
                        self.float_amplitude = 150  # How far left/right to float
                        self.float_speed = (
                            0.015  # Speed of oscillation (reduced for slower movement)
                        )
                        self.float_time = 0

                    # Update oscillation time
                    self.float_time += self.float_speed

                    # Calculate new x position using sine wave for smooth floating
                    self.x = (
                        self.float_center_x
                        + math.sin(self.float_time) * self.float_amplitude
                    )

                    # Keep within screen bounds
                    self.x = max(50, min(game.width - 50, self.x))
            else:
                # Normal enemy behavior - move towards player
                dx = player.x - self.x
                dy = player.y - self.y
                distance: float = math.sqrt(dx * dx + dy * dy)

                if distance > 1:  # Avoid division by very small numbers
                    # Move towards player
                    self.x += (dx / distance) * self.speed / 60
                    self.y += (dy / distance) * self.speed / 60

            # Clamp to walls if game reference is provided
            if game:
                self.x = game.clamp_to_walls(self.x)

            self.rect.center = (self.x, self.y)

            # Handle shooting for enemies that shoot
            if game and self.shoot_cooldown is not None:
                self.shoot_cooldown -= 1
                if self.shoot_cooldown <= 0:
                    self.shoot_at_player(player, game)

            # Handle boss special attacks
            if game and self.enemy_type in ["boss_big", "boss_final"]:
                # Update boss timers
                if self.pattern_timer is not None:
                    self.pattern_timer -= 1
                if (
                    hasattr(self, "big_shot_cooldown")
                    and self.big_shot_cooldown is not None
                ):
                    self.big_shot_cooldown -= 1

                # Check for special attacks
                if self.enemy_type == "boss_big":
                    if self.pattern_timer <= 0:
                        # Radial burst
                        for angle in range(0, 360, 18):
                            rad: float = math.radians(angle)
                            speed = 220
                            vel_x: float = math.cos(rad) * speed
                            vel_y: float = math.sin(rad) * speed
                            projectile: Projectile[Any | float | Any, Any | Any | int, float, float] = Projectile(
                                self.x,
                                self.y,
                                vel_x,
                                vel_y,
                                damage=10,
                                radius=6,
                                is_enemy_projectile=True,
                            )
                            game.enemy_projectiles.add(projectile)
                        self.pattern_timer: int = random.randint(140, 220)
                    elif self.big_shot_cooldown <= 0:
                        # Triple spread shot
                        dx = player.x - self.x
                        dy = player.y - self.y
                        distance: float = math.sqrt(dx * dx + dy * dy)
                        if distance > 0:
                            speed = 360
                            base_angle: float = math.atan2(dy, dx)
                            for angle_offset in [-10, 0, 10]:
                                rad: float = base_angle + math.radians(angle_offset)
                                vel_x: float = math.cos(rad) * speed
                                vel_y: float = math.sin(rad) * speed
                                projectile: Projectile[Any | float | Any, Any | Any | int, float, float] = Projectile(
                                    self.x,
                                    self.y,
                                    vel_x,
                                    vel_y,
                                    damage=22,
                                    radius=11,
                                    is_enemy_projectile=True,
                                )
                                game.enemy_projectiles.add(projectile)
                        self.big_shot_cooldown: int = random.randint(220, 320)
                elif self.enemy_type == "boss_final":
                    if self.pattern_timer <= 0:
                        # Radial burst
                        for angle in range(0, 360, 20):
                            rad: float = math.radians(angle)
                            speed = 250
                            vel_x: float = math.cos(rad) * speed
                            vel_y: float = math.sin(rad) * speed
                            projectile: Projectile[Any | float | Any, Any | Any | int, float, float] = Projectile(
                                self.x,
                                self.y,
                                vel_x,
                                vel_y,
                                damage=12,
                                radius=7,
                                is_enemy_projectile=True,
                            )
                            game.enemy_projectiles.add(projectile)
                        self.pattern_timer: int = random.randint(120, 180)
        except Exception as e:
            logger.exception("Error updating enemy %s: %s", self.enemy_type, e)

        # Flashing effect removed

    def shoot_at_player(self, player, game):
        """Handle shooting logic for different enemy types"""
        try:
            if self.enemy_type == "normal":
                # Single aimed shot
                dx = player.x - self.x
                dy = player.y - self.y
                distance: float = math.sqrt(dx * dx + dy * dy)
                if distance > 0:
                    speed = 220
                    vel_x = (dx / distance) * speed
                    vel_y = (dy / distance) * speed
                else:
                    vel_x = 0
                    vel_y = 220

                projectile: Projectile[Any | Any | float, Any | Any | int, Any | int, Any | int] = Projectile(
                    self.x,
                    self.y,
                    vel_x,
                    vel_y,
                    damage=8,
                    radius=5,
                    is_enemy_projectile=True,
                )
                game.enemy_projectiles.add(projectile)
                self.shoot_cooldown: int = random.randint(90, 180)

            elif self.enemy_type == "angel":
                # Single aimed shot (same as normal but maybe different stats)
                dx = player.x - self.x
                dy = player.y - self.y
                distance: float = math.sqrt(dx * dx + dy * dy)
                if distance > 0:
                    speed = 220
                    vel_x = (dx / distance) * speed
                    vel_y = (dy / distance) * speed
                else:
                    vel_x = 0
                    vel_y = 220

                projectile: Projectile[Any | Any | float, Any | Any | int, Any | int, Any | int] = Projectile(
                    self.x,
                    self.y,
                    vel_x,
                    vel_y,
                    damage=8,
                    radius=5,
                    is_enemy_projectile=True,
                )
                game.enemy_projectiles.add(projectile)
                self.shoot_cooldown: int = random.randint(90, 180)

            elif self.enemy_type == "boss_medium":
                # Heavy single projectile
                dx = player.x - self.x
                dy = player.y - self.y
                distance: float = math.sqrt(dx * dx + dy * dy)
                if distance > 0:
                    speed = 300
                    vel_x = (dx / distance) * speed
                    vel_y = (dy / distance) * speed
                else:
                    vel_x = 0
                    vel_y = 300

                projectile: Projectile[Any | Any | float, Any | Any | int, Any | int, Any | int] = Projectile(
                    self.x,
                    self.y,
                    vel_x,
                    vel_y,
                    damage=20,
                    radius=10,
                    is_enemy_projectile=True,
                )
                game.enemy_projectiles.add(projectile)
                self.shoot_cooldown: int = random.randint(90, 150)

            elif self.enemy_type == "boss_final":
                # Single aimed shot for final boss
                dx = player.x - self.x
                dy = player.y - self.y
                distance: float = math.sqrt(dx * dx + dy * dy)
                if distance > 0:
                    speed = 180
                    vel_x = (dx / distance) * speed
                    vel_y = (dy / distance) * speed
                else:
                    vel_x = 0
                    vel_y = 180

                projectile: Projectile[Any | Any | float, Any | Any | int, Any | int, Any | int] = Projectile(
                    self.x,
                    self.y,
                    vel_x,
                    vel_y,
                    damage=15,
                    radius=8,
                    is_enemy_projectile=True,
                )
                game.enemy_projectiles.add(projectile)
                self.shoot_cooldown: int = random.randint(60, 110)
        except Exception as e:
            logger.exception("Error in enemy shooting %s: %s", self.enemy_type, e)

    def take_damage(self, damage) -> None:
        self.health -= damage
        self.shake_timer = 10

    def draw(self, screen, shake_x=0, shake_y=0) -> None:
        try:
            # Apply shake offset
            draw_x: int | logging.Any = self.rect.x + shake_x
            draw_y: int | logging.Any = self.rect.y + shake_y

            if self.shake_timer > 0:
                draw_x += random.randint(-1, 1)
                draw_y += random.randint(-1, 1)

            screen.blit(self.image, (draw_x, draw_y))

            # Draw health bar with shake offset
            bar_width = 25
            bar_height = 3
            bar_x: int | logging.Any = self.rect.centerx - bar_width // 2 + shake_x
            bar_y: int | logging.Any = self.rect.top - 5 + shake_y

            if self.shake_timer > 0:
                bar_x += random.randint(-1, 1)
                bar_y += random.randint(-1, 1)

            pygame.draw.rect(screen, (100, 0, 0), (bar_x, bar_y, bar_width, bar_height))
            health_ratio = max(0, self.health / self.max_health)
            pygame.draw.rect(
                screen,
                (255, 100, 100),
                (bar_x, bar_y, bar_width * health_ratio, bar_height),
            )
        except Exception as e:
            logger.exception("Error drawing enemy %s: %s", self.enemy_type, e)
