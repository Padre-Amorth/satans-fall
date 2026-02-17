import logging
from typing import TYPE_CHECKING, Any

import pygame
from numpy import ndarray

from src.balance import (
    DEFAULT_DAMAGE_REDUCTION_MULTIPLIER,
    DEFAULT_FIRE_RATE_MULTIPLIER,
    DEFAULT_PROJECTILE_SIZE_MULTIPLIER,
    PLAYER_BASE_HEALTH,
    XP_BASE,
    XP_GROWTH,
)

if TYPE_CHECKING:
    from pygame.sprite import Sprite as SpriteType  # type: ignore
else:
    SpriteType = Any

# Use an explicit runtime base variable to avoid reassigning a TYPE_CHECKING
# name and to give mypy a concrete variable type.
BaseSprite: type
try:
    BaseSprite = pygame.sprite.Sprite  # type: ignore
except Exception:
    BaseSprite = object

logger: logging.Logger = logging.getLogger(__name__)


class Player(BaseSprite):
    def __init__(self, x, y) -> None:
        super().__init__()
        self.x: Any = x
        self.y: Any = y
        self.width = 61  # Increased by another 10%
        self.height = 73  # Increased by another 10%
        self.max_health = PLAYER_BASE_HEALTH
        self.health: float = float(self.max_health)
        self.speed: float = 250.0  # reduced from 300 to 250 px/s per user request
        self.velocity_x: float = 0.0
        # Vertical velocity for limited vertical movement (new feature)
        self.velocity_y: float = 0.0

        # Slow status (can be applied by enemy projectiles)
        self.slow_timer: int = 0
        self.slow_factor: float = 1.0

        self.base_image: pygame.Surface | None = None

        # XP and Level system
        self.xp = 0
        self.level = 1
        self.xp_to_next_level = XP_BASE
        self.damage_multiplier = 1.0
        self.fire_rate_multiplier = DEFAULT_FIRE_RATE_MULTIPLIER
        self.projectile_size_multiplier = DEFAULT_PROJECTILE_SIZE_MULTIPLIER
        self.damage_reduction_multiplier = DEFAULT_DAMAGE_REDUCTION_MULTIPLIER

        # Load image (use shared AssetManager cache when possible)
        try:
            from src.assets.manager import get_image

            loaded = get_image("satan.png", (self.width, self.height))
            if loaded is None:
                raise RuntimeError("satan.png not available")

            # Work on a copy so the cached surface isn't modified in-place
            self.base_image = loaded.copy()
            self.image = self.base_image.copy()

            # Create walking animation frames
            self.walk_frames: list[pygame.Surface] = []
            try:
                self.create_walk_frames()
            except Exception as e:
                logger.warning("Could not create walk animation: %s", e)
                self.walk_frames = []
        except Exception as e:
            logger.warning("Could not load satan.png, using fallback drawing: %s", e)
            # Fallback to drawing
            self.base_image = None
            self.image = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self.draw_satan()
            self.walk_frames = []
        self.rect: pygame.Rect = self.image.get_rect(center=(self.x, self.y))
        # Visual particles for burn effect on player
        self.burn_particles: list = []

    def create_walk_frames(self) -> None:
        """Create walking animation frames by shifting pixels"""
        if self.base_image is None:
            return

        width, height = self.base_image.get_size()

        # Create 4 walking frames
        for frame in range(4):
            frame_surface: pygame.Surface = self.base_image.copy()
            pixels: ndarray = pygame.surfarray.pixels3d(frame_surface)
            alpha_pixels: ndarray = pygame.surfarray.pixels_alpha(frame_surface)

            # Calculate leg movement offsets
            if frame == 0:
                offset_left = 0
                offset_right = 0
            elif frame == 1:
                offset_left = -2  # Left leg forward
                offset_right = 1
            elif frame == 2:
                offset_left = 0
                offset_right = 0
            elif frame == 3:
                offset_left = 1  # Right leg forward
                offset_right = -2

            # Apply pixel shifting to simulate leg movement
            new_pixels: ndarray = pixels.copy()
            new_alpha: ndarray = alpha_pixels.copy()

            for y in range(height):
                for x in range(width):
                    src_x: int
                    if x < width // 2:
                        # Left side (left leg)
                        src_x = x - offset_left
                    else:
                        # Right side (right leg)
                        src_x = x - offset_right

                    if 0 <= src_x < width:
                        new_pixels[x, y] = pixels[src_x, y]
                        new_alpha[x, y] = alpha_pixels[src_x, y]
                    else:
                        new_pixels[x, y] = [0, 0, 0]
                        new_alpha[x, y] = 0

            # Unlock surface arrays
            del pixels
            del alpha_pixels

            # Create new surface with modified pixels
            new_frame = pygame.Surface((width, height), pygame.SRCALPHA)
            pygame.surfarray.blit_array(new_frame, new_pixels)
            pygame.surfarray.pixels_alpha(new_frame)[:] = new_alpha

            self.walk_frames.append(new_frame)

            # Create flipped version
            flipped_frame: pygame.Surface = pygame.transform.flip(
                new_frame, True, False
            )
            self.walk_frames.append(flipped_frame)

    def draw_satan(self) -> None:
        """Draw Satan character - bright red demon with horns"""
        self.image.fill((0, 0, 0, 0))  # Transparent background

        # Body (bright red)
        pygame.draw.ellipse(self.image, (255, 0, 0), (10, 20, 30, 25))

        # Head (bright red)
        pygame.draw.circle(self.image, (255, 50, 50), (25, 12), 8)

        # Horns (bright red)
        pygame.draw.polygon(self.image, (255, 100, 100), [(15, 5), (18, 0), (20, 6)])
        pygame.draw.polygon(self.image, (255, 100, 100), [(30, 5), (32, 0), (35, 6)])

        # Eyes (white and black)
        pygame.draw.circle(self.image, (255, 255, 255), (21, 10), 2)
        pygame.draw.circle(self.image, (255, 255, 255), (29, 10), 2)
        pygame.draw.circle(self.image, (0, 0, 0), (21, 10), 1)
        pygame.draw.circle(self.image, (0, 0, 0), (29, 10), 1)

        # Evil grin (white)
        pygame.draw.line(self.image, (255, 200, 200), (20, 14), (30, 14), 2)

        # Arms
        pygame.draw.line(self.image, (255, 0, 0), (12, 30), (5, 35), 3)
        pygame.draw.line(self.image, (255, 0, 0), (38, 30), (45, 35), 3)

        # Legs
        pygame.draw.line(self.image, (150, 0, 0), (18, 45), (18, 55), 3)
        pygame.draw.line(self.image, (150, 0, 0), (32, 45), (32, 55), 3)

    def move_left(self) -> None:
        self.velocity_x = -self.speed

    def move_right(self) -> None:
        self.velocity_x = self.speed

    def move_up(self) -> None:
        """Request upward movement (caller should call this each frame while key held)."""
        self.velocity_y = -self.speed

    def move_down(self) -> None:
        """Request downward movement (caller should call this each frame while key held)."""
        self.velocity_y = self.speed

    def update(self, screen_width) -> None:
        # Apply horizontal velocity
        self.x += self.velocity_x / 60  # Divide by FPS
        # Apply vertical velocity (new behavior)
        try:
            self.y += self.velocity_y / 60
        except Exception:
            pass

        # Clamp vertical movement if a vertical range has been configured by the
        # `Game` instance. We attach `vertical_min_y`/`vertical_max_y` to the
        # player to avoid changing `Player.update` signature.
        vmin = getattr(self, "vertical_min_y", None)
        vmax = getattr(self, "vertical_max_y", None)
        if vmin is not None and vmax is not None:
            try:
                # Ensure consistent numeric types
                self.y = max(int(vmin), min(int(self.y), int(vmax)))
            except Exception:
                pass

        # Clamp to screen horizontally
        self.x = max(self.width // 2, min(self.x, screen_width - self.width // 2))

        # Reset velocities (per-frame input)
        self.velocity_x = 0
        self.velocity_y = 0

        # Handle slow status timer
        if getattr(self, "slow_timer", 0) > 0:
            try:
                self.slow_timer -= 1
                if self.slow_timer <= 0 and hasattr(self, "original_speed"):
                    # restore original speed when slow expires
                    self.speed = getattr(self, "original_speed", self.speed)
            except Exception:
                pass

        # Update rect
        self.rect.center = (self.x, self.y)

        # Update and cull burn particles (visual only)
        if getattr(self, "burn_particles", None):
            for p in list(self.burn_particles):
                try:
                    p.update()
                    if not getattr(p, "alive", True):
                        try:
                            self.burn_particles.remove(p)
                        except Exception:
                            pass
                except Exception:
                    try:
                        self.burn_particles.remove(p)
                    except Exception:
                        pass

    def take_damage(self, damage) -> None:
        actual_damage = damage * self.damage_reduction_multiplier
        self.health = max(0, self.health - actual_damage)

    def gain_xp(self, amount) -> None:
        self.xp += amount
        if self.xp >= self.xp_to_next_level:
            self.level_up()

    def level_up(self) -> None:
        self.level += 1
        self.xp -= self.xp_to_next_level
        # Recalculate XP requirement using centralized curve
        self.xp_to_next_level = int(
            XP_BASE * (XP_GROWTH ** (self.level - 1))
        )  # Increase XP requirement
        # Note: Upgrade selection will be handled in the game class

    def draw(self, screen, shake_x=0, shake_y=0, anim_frame=0, is_moving=False) -> None:
        # Apply shake offset
        draw_x: float | int = self.rect.x + shake_x
        draw_y: float | int = self.rect.y + shake_y

        # Apply bobbing effect if moving
        bob_offset = 0
        current_image: pygame.Surface = self.image

        if is_moving and self.walk_frames:
            # Create bobbing effect (up and down movement)
            bob_cycle: int = anim_frame % 4
            if bob_cycle == 1:
                bob_offset = -1
            elif bob_cycle == 3:
                bob_offset = 1
            else:
                bob_offset = 0

            # Use walking frames
            frame_index: int = anim_frame % 8  # 8 frames total (4 normal + 4 flipped)
            if frame_index < len(self.walk_frames):
                current_image = self.walk_frames[frame_index]

        screen.blit(current_image, (draw_x, draw_y + bob_offset))

        # Draw health bar with shake offset
        bar_width = 40
        bar_height = 5
        bar_x: float | int = self.rect.centerx - bar_width // 2 + shake_x
        bar_y: float | int = self.rect.bottom + 5 + shake_y

        # Health bar background
        pygame.draw.rect(screen, (100, 0, 0), (bar_x, bar_y, bar_width, bar_height))

        # Health bar fill
        health_ratio: float = max(0, self.health / self.max_health)
        pygame.draw.rect(
            screen, (0, 200, 0), (bar_x, bar_y, bar_width * health_ratio, bar_height)
        )
