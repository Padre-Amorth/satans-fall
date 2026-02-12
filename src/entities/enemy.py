import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pygame import Rect, Surface  # type: ignore
    from pygame.sprite import Sprite as SpriteType  # type: ignore
else:
    Rect = Any
    Surface = Any
    SpriteType = Any

# Ensure a runtime base class reference without assigning to the type name
try:
    PygameSprite = pygame.sprite.Sprite  # type: ignore
except Exception:
    PygameSprite = object

from types import ModuleType
try:
    pygame: ModuleType = importlib.import_module("pygame")
except Exception:
    pygame: ModuleType = importlib.import_module("pygame_ce")  # type: ignore

# Use an explicit runtime base variable so mypy does not confuse a TYPE_CHECKING
# alias with a runtime assignment.
BaseSprite: type
try:
    BaseSprite = pygame.sprite.Sprite  # type: ignore
except Exception:
    BaseSprite = object

import logging
import math
import os
import random

# Import Projectile explicitly from src.projectile for stability
from src.projectile import Projectile

logger: logging.Logger = logging.getLogger(__name__) 


class BurnParticle:
    """Simple particle for burn visual effect"""

    def __init__(self, x: float, y: float, vx: float, vy: float, life: int = 30, size: int = 3):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.size = size

    def update(self) -> None:
        self.x += self.vx / 60
        self.y += self.vy / 60
        self.vy -= 0.2  # slight upward acceleration
        self.life -= 1

    @property
    def alive(self) -> bool:
        return self.life > 0



class IceParticle:
    """Simple particle for ice explosion visual effect"""

    def __init__(self, x: float, y: float, vx: float, vy: float, life: int = 20, size: int = 2):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.size = size

    def update(self) -> None:
        self.x += self.vx / 60
        self.y += self.vy / 60
        self.vy += 0.1  # slight downward acceleration for ice shards
        self.life -= 1

    @property
    def alive(self) -> bool:
        return self.life > 0


class Enemy(BaseSprite):
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
        elif enemy_type == "boss_inquisitor":
            # Inquisitor: mid-sized Limbo boss (orange projectiles + player slow)
            self.width = 80
            self.height = 80
            self.damage = 18
        elif enemy_type == "boss_big":
            # Make boss_big significantly larger (at least 3x the normal size)
            # Base enemies end up at ~40px after default growth, so 3x yields >=120.
            self.width = 120
            self.height = 120
            # Increase damage to reflect larger boss
            self.damage = 40
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
        self.health = self.max_health

        # Calculate radius from width/height (average)
        self.radius: int = (self.width + self.height) // 4

        # Shooting cooldown for enemies that shoot (None when not applicable)
        self.shoot_cooldown: int | None = None
        if enemy_type == "normal":
            self.shoot_cooldown = random.randint(60, 120)
        elif enemy_type == "boss_medium":
            self.shoot_cooldown = random.randint(60, 120)
        elif enemy_type == "boss_inquisitor":
            # Inquisitor fires a 3-shot spread periodically (slightly reduced fire rate)
            self.shoot_cooldown = random.randint(100, 140)
        elif enemy_type == "boss_final":
            self.shoot_cooldown = random.randint(60, 110)
        elif enemy_type in ["boss_big"]:
            # Boss_big doesn't have regular shooting, only special attacks
            self.shoot_cooldown = None
        else:
            self.shoot_cooldown = None

        # Boss pattern timers
        # Boss pattern timers (None when not applicable)
        self.pattern_timer: int | None = None
        self.big_shot_cooldown: int | None = None
        if enemy_type == "boss_big":
            self.pattern_timer = random.randint(100, 180)
            self.big_shot_cooldown = random.randint(200, 320)
        elif enemy_type == "boss_final":
            self.pattern_timer = random.randint(80, 150)
        else:
            self.pattern_timer = None
            self.big_shot_cooldown = None

        # Particle effects
        self.burn_particles: List["BurnParticle"] = []
        self.ice_particles: List["IceParticle"] = []

        # Create image
        self.image = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self.draw_enemy()
        self.rect: Rect | Any = self.image.get_rect(center=(self.x, self.y))

        # Keep a copy of the base image so we can add temporary effects (glow/shine)
        try:
            self.base_image: Surface | Any = self.image.copy()
        except Exception:
            self.base_image = None
        # Shine state for final boss phase
        self.shine_phase = 0.0
        self.shining = False

        self.shake_timer = 0

        # Visual particles for burn effect
        self.burn_particles: List["BurnParticle"] = []

    def draw_enemy(self) -> None:
        """Draw enemy based on type, try to load image first"""
        # Map enemy types to asset names
        asset_name = f"enemy_{self.enemy_type}.png"
        if self.enemy_type.startswith("boss_"):
            # For bosses, remove the 'boss_' prefix
            boss_type: str = self.enemy_type.replace("boss_", "")
            asset_name = f"boss_{boss_type}.png"

        try:
            from src.assets.manager import get_image

            loaded = get_image(asset_name, (self.width, self.height))
            if loaded is None:
                raise RuntimeError(f"Asset {asset_name} not available")
            self.image = loaded.copy()
        except Exception as e:
            # Asset loading already logs warnings; avoid repeating the same warning
            # for each enemy instance to reduce console spam. Log at debug level here.
            logger.debug(
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
                        self.image: Surface | Any = pygame.transform.scale(
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
                        overlay_rect: Rect | Any = overlay.get_rect(
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
                # Normal enemy behavior - sometimes stop in middle instead of chasing player
                if self.enemy_type == "normal" and game is not None:
                    # Lazily initialize a stop point/time near the center of the battlefield
                    if not hasattr(self, "stop_point"):
                        center_x = game.width / 2
                        center_y = game.height / 2
                        jitter_x = game.width * 0.2
                        jitter_y = game.height * 0.2
                        spx = center_x + random.uniform(-jitter_x, jitter_x)
                        spy = center_y + random.uniform(-jitter_y, jitter_y)
                        # Ensure the chosen stop point is within the playable walls
                        spx = game.clamp_to_walls(spx)
                        self.stop_point = (spx, spy)
                        self.stop_timer = 0
                        self.stop_threshold = max(10, min(game.width, game.height) * 0.05)

                    # If currently stopped, count down and do not move
                    if getattr(self, "stop_timer", 0) > 0:
                        # While stopped, make sure the enemy remains within walls
                        if game:
                            self.x = game.clamp_to_walls(self.x)
                        self.stop_timer -= 1
                    else:
                        # Move towards the chosen stop point
                        spx, spy = self.stop_point
                        dx = spx - self.x
                        dy = spy - self.y
                        distance = math.hypot(dx, dy)
                        if distance > 1:
                            self.x += (dx / distance) * self.speed / 60
                            self.y += (dy / distance) * self.speed / 60
                        else:
                            # Arrived: stay stopped for a random duration then pick a new stop point
                            self.stop_timer = random.randint(60, 180)
                            center_x = game.width / 2
                            center_y = game.height / 2
                            jitter_x = game.width * 0.2
                            jitter_y = game.height * 0.2
                            spx = center_x + random.uniform(-jitter_x, jitter_x)
                            spy = center_y + random.uniform(-jitter_y, jitter_y)
                            spx = game.clamp_to_walls(spx)
                            self.stop_point = (spx, spy)

                elif self.enemy_type == "boss_inquisitor" and game is not None:
                    # Inquisitor roams randomly within the top half of the playfield
                    # Do not chase the player directly; pick random roam targets and move there
                    top_margin = 50
                    bottom_limit = int(game.height / 2) - 40  # do not cross halfway
                    left_limit = 50
                    right_limit = game.width - 50

                    if not hasattr(self, "roam_target"):
                        # Use game's clamp_to_walls so roam stays within arena walls
                        rx = random.uniform(game.clamp_to_walls(0), game.clamp_to_walls(game.width))
                        ry = random.uniform(top_margin, max(top_margin + 10, bottom_limit))
                        # Ensure x respects wall clamps explicitly
                        rx = game.clamp_to_walls(rx)
                        self.roam_target = (rx, ry)
                        self.roam_timer = random.randint(60, 180)

                    # Move toward roam target with slight speed variation
                    tx, ty = self.roam_target
                    dx = tx - self.x
                    dy = ty - self.y
                    dist = math.hypot(dx, dy)
                    if dist > 4:
                        vx = (dx / dist) * (self.speed * random.uniform(0.9, 1.1)) / 60
                        vy = (dy / dist) * (self.speed * random.uniform(0.9, 1.1)) / 60
                        self.x += vx
                        self.y += vy
                    else:
                        # Reached target -> pick a new one within top half and inside walls
                        self.roam_timer = random.randint(60, 240)
                        rx = random.uniform(game.clamp_to_walls(0), game.clamp_to_walls(game.width))
                        ry = random.uniform(top_margin, max(top_margin + 10, bottom_limit))
                        rx = game.clamp_to_walls(rx)
                        self.roam_target = (rx, ry)

                    # Slight random jitter so movement looks organic
                    if random.random() < 0.02:
                        self.x += random.uniform(-1.5, 1.5)
                        self.y += random.uniform(-1.0, 1.0)

                    # Clamp to arena walls and top-half limit (never cross halfway line)
                    try:
                        self.x = game.clamp_to_walls(self.x)
                    except Exception:
                        # Fallback to previous clamp
                        self.x = max(left_limit, min(right_limit, self.x))
                    self.y = max(top_margin, min(bottom_limit, self.y))

                else:
                    # Move towards player (default behaviour for other enemy types)
                    dx = player.x - self.x
                    dy = player.y - self.y
                    distance: float = math.sqrt(dx * dx + dy * dy)

                    if distance > 1:  # Avoid division by very small numbers
                        # Move towards player
                        self.x += (dx / distance) * self.speed / 60
                        self.y += (dy / distance) * self.speed / 60

            # Handle slow effect timer
            if hasattr(self, "slow_timer") and getattr(self, "slow_timer", 0) > 0:
                self.slow_timer -= 1
                if self.slow_timer <= 0:
                    # Restore original speed
                    if hasattr(self, "original_speed"):
                        self.speed = getattr(self, "original_speed", self.speed)
                        try:
                            del self.original_speed
                        except Exception:
                            pass

            # Handle burn (damage over time)
            if hasattr(self, "burn_timer") and getattr(self, "burn_timer", 0) > 0:
                # Per-frame decrement
                self.burn_timer -= 1
                # Initialize tick timer if missing
                if not hasattr(self, "burn_tick_timer") or getattr(self, "burn_tick_timer", 0) <= 0:
                    self.burn_tick_timer = getattr(game, "fps", 60)
                self.burn_tick_timer -= 1
                if self.burn_tick_timer <= 0:
                    # Apply damage per second as an integer per tick
                    damage = getattr(self, "burn_damage_per_second", 1.0)
                    try:
                        # Use take_damage so effects like shake are applied
                        self.take_damage(damage)
                    except Exception:
                        try:
                            self.health -= damage
                        except Exception:
                            pass
                    # Reset tick timer
                    self.burn_tick_timer = getattr(game, "fps", 60)

                # Emit particles while burning
                try:
                    # spawn 2-4 small particles per frame (increased visibility)
                    for _ in range(random.randint(2, 4)):
                        px = self.x + random.uniform(-8, 8)
                        py = self.y - 8 + random.uniform(-4, 4)
                        vx = random.uniform(-15, 15)
                        vy = random.uniform(12, 36)
                        p = BurnParticle(px, py, vx, vy, life=random.randint(20, 44), size=random.randint(3, 5))
                        self.burn_particles.append(p)
                except Exception:
                    pass

            # Update and cull burn particles (run regardless of burn state)
            if self.burn_particles:
                for p in list(self.burn_particles):
                    try:
                        p.update()
                        if not p.alive:
                            self.burn_particles.remove(p)
                    except Exception:
                        try:
                            self.burn_particles.remove(p)
                        except Exception:
                            pass

            # Update and cull ice particles
            if self.ice_particles:
                for p in list(self.ice_particles):
                    try:
                        p.update()
                        if not p.alive:
                            self.ice_particles.remove(p)
                    except Exception:
                        try:
                            self.ice_particles.remove(p)
                        except Exception:
                            pass

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
                            projectile: Projectile = Projectile(
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
                            # Use a slightly narrower spread between the three projectiles
                            # Change offsets to [-15, 0, 15] (~30° between outer shots)
                            for angle_offset in [-15, 0, 15]:
                                rad: float = base_angle + math.radians(angle_offset)
                                vel_x: float = math.cos(rad) * speed
                                vel_y: float = math.sin(rad) * speed
                                projectile: Projectile = Projectile(
                                    self.x,
                                    self.y,
                                    vel_x,
                                    vel_y,
                                    damage=22,
                                    # Slightly smaller hitbox for triple shots to make them harder to hit
                                    radius=8,
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
                            projectile: Projectile = Projectile(
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

                projectile: Projectile = Projectile(
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

            elif self.enemy_type == "boss_inquisitor":
                # Inquisitor: 3-shot orange spread that applies a slow to the player
                dx = player.x - self.x
                dy = player.y - self.y
                base_angle = math.atan2(dy, dx)
                speed = 260
                angles = [base_angle - 0.2, base_angle, base_angle + 0.2]
                for ang in angles:
                    vel_x = math.cos(ang) * speed
                    vel_y = math.sin(ang) * speed
                    proj = Projectile(
                        self.x,
                        self.y,
                        vel_x,
                        vel_y,
                        damage=12,
                        radius=6,
                        is_enemy_projectile=True,
                        appearance="inquisitor",
                    )
                            # Mark slow metadata so collision handler can apply effect to player
                    proj.effect = "slow"
                    proj.slow_duration = 180  # 3s at 60 FPS (increased)
                    proj.slow_factor = 0.4   # stronger slow (60% reduction)
                    game.enemy_projectiles.add(proj)
                self.shoot_cooldown = random.randint(110, 150)

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

    def take_damage(self, damage, *, show_floating: bool = True) -> None:
        """Apply damage to this enemy.

        show_floating: when False suppresses the floating damage text (used for contact
        damage and other silent effects).
        """
        self.health -= damage
        self.shake_timer = 10
        # Try to show floating damage number via centralized game instance (unless suppressed)
        if not show_floating:
            return
        try:
            dmg = int(damage)
        except Exception:
            try:
                dmg = int(round(float(damage)))
            except Exception:
                dmg = damage
        try:
            # Lazy import CURRENT_GAME to avoid circular imports at module load
            from src.game import CURRENT_GAME
            if CURRENT_GAME is not None:
                try:
                    x = getattr(self, 'x', None) or (self.rect.centerx if getattr(self, 'rect', None) is not None else 0)
                    y = getattr(self, 'y', None) or (self.rect.top if getattr(self, 'rect', None) is not None else 0)
                    # Position above enemy
                    pos_y = (getattr(self, 'rect', None) and self.rect.top - 8) or (getattr(self, 'y', 0) - getattr(self, 'height', 0) // 2 - 8)
                    CURRENT_GAME.spawn_floating_text(str(dmg), x, pos_y)
                except Exception:
                    pass
        except Exception:
            pass

    def draw(self, screen, shake_x=0, shake_y=0) -> None:
        try:
            # Apply shake offset
            draw_x: int | Any = self.rect.x + shake_x
            draw_y: int | Any = self.rect.y + shake_y

            if self.shake_timer > 0:
                draw_x += random.randint(-1, 1)
                draw_y += random.randint(-1, 1)

            screen.blit(self.image, (draw_x, draw_y))

            # Draw health bar with shake offset
            bar_width = 25
            bar_height = 3
            bar_x: int | Any = self.rect.centerx - bar_width // 2 + shake_x
            bar_y: int | Any = self.rect.top - 5 + shake_y

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

            # Draw burn status indicator (flame + optional text) if enemy is burning
            try:
                # Draw particles behind the flame
                if self.burn_particles:
                    for p in list(self.burn_particles):
                        try:
                            surf = pygame.Surface((p.size * 2 + 2, p.size * 2 + 2), pygame.SRCALPHA)
                            alpha = max(60, int(255 * (p.life / 44)))
                            pygame.draw.circle(surf, (255, 120, 0, alpha), (p.size + 1, p.size + 1), p.size)
                            screen.blit(surf, (int(p.x - p.size), int(p.y - p.size)))
                        except Exception:
                            pass

                # Draw ice particles
                if self.ice_particles:
                    for p in list(self.ice_particles):
                        try:
                            surf = pygame.Surface((p.size * 2 + 2, p.size * 2 + 2), pygame.SRCALPHA)
                            alpha = max(50, int(255 * (p.life / 25)))
                            pygame.draw.circle(surf, (200, 240, 255, alpha), (p.size + 1, p.size + 1), p.size)
                            screen.blit(surf, (int(p.x - p.size), int(p.y - p.size)))
                        except Exception:
                            pass

                # Burn status: particles are drawn above; legacy flame/text removed (particles retained)

            except Exception as e:
                logger.exception("Error drawing burn effect for enemy %s: %s", self.enemy_type, e)
        except Exception as e:
            logger.exception("Error drawing enemy %s: %s", self.enemy_type, e)
