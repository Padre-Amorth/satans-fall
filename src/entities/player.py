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
        # remember originals for later scaling
        self.original_width = self.width
        self.original_height = self.height
        self.max_health = PLAYER_BASE_HEALTH
        self.health: float = float(self.max_health)
        self.speed: float = 220.0  # user-requested base speed (px/s)
        # Store immutable baseline speed so permanent multipliers are applied
        # relative to the original stat (prevents compounding on re-apply).
        self.base_speed: float = float(self.speed)
        self.velocity_x: float = 0.0
        # Vertical velocity for limited vertical movement (new feature)
        self.velocity_y: float = 0.0

        # Slow status (can be applied by enemy projectiles)
        self.slow_timer: int = 0
        self.slow_factor: float = 1.0

        # Health regeneration (per-run upgrade system)
        self.regen_per_5s: float = 0.0  # HP to regenerate every 5 seconds
        self.regen_timer: int = 0  # Frame counter for regeneration

        # Shield absorption (per-run upgrade system)
        self.shield_charges: int = (
            0  # Number of hits this shield can absorb (0 = disabled until upgrade taken)
        )
        self.shield_cooldown_timer: int = 0  # Frames until shield is available again
        self.shield_upgrade_level: int = (
            0  # Number of cooldown reductions taken (0 = upgrade never taken)
        )

        # Kill explosion (per-run upgrade system)
        self.kill_explosion_enabled: bool = False  # Whether the feature is unlocked
        self.kill_explosion_upgrades: int = (
            0  # Number of times upgraded (affects dmg/range)
        )
        self.kill_counter: int = 0  # Counter for kills (0-9, resets at 10)

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
                # Try to load custom directional walk sprites first
                if not self.load_directional_walk_sprites():
                    # Fallback to pixel-shifting animation
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
        """Create walking animation frames by shifting pixels (2 frames per direction)"""
        if self.base_image is None:
            return

        width, height = self.base_image.get_size()

        # Create 2 walking frames (reduced from 4 for simpler animation)
        for frame in range(2):
            frame_surface: pygame.Surface = self.base_image.copy()
            pixels: ndarray = pygame.surfarray.pixels3d(frame_surface)
            alpha_pixels: ndarray = pygame.surfarray.pixels_alpha(frame_surface)

            # Calculate leg movement offsets (simplified to 2 frames)
            if frame == 0:
                offset_left = -2  # Left leg forward
                offset_right = 1
            else:  # frame == 1
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

            # Create flipped version for left movement
            flipped_frame: pygame.Surface = pygame.transform.flip(
                new_frame, True, False
            )
            self.walk_frames.append(flipped_frame)

    def load_directional_walk_sprites(self) -> bool:
        """Load custom walk sprites for right/left directions (2 frames each).

        Looks for sprites in:
        - walk_right_01.png, walk_right_02.png (frames 0-1)
        - walk_left_01.png, walk_left_02.png (frames 2-3)

        Returns True if successfully loaded, False if sprites not found (fallback to pixel-shift).
        """
        try:
            from src.assets.manager import get_image

            size = (self.width, self.height)
            self.walk_frames = []

            # Try to load right-direction walk frames (2 frames)
            for i in range(1, 3):
                sprite_name = f"walk_right_{i:02d}.png"
                sprite = get_image(sprite_name, size)
                if sprite is None:
                    # Not found, fallback to pixel-shift animation
                    return False
                self.walk_frames.append(sprite)

            # Try to load left-direction walk frames (2 frames)
            for i in range(1, 3):
                sprite_name = f"walk_left_{i:02d}.png"
                sprite = get_image(sprite_name, size)
                if sprite is None:
                    # Not found, create flipped versions from right frames
                    flipped = pygame.transform.flip(
                        self.walk_frames[i - 1], True, False
                    )
                    self.walk_frames.append(flipped)
                else:
                    self.walk_frames.append(sprite)

            logger.info(
                "Loaded custom directional walk sprites (%d frames)",
                len(self.walk_frames),
            )
            return True
        except Exception as e:
            logger.debug("Could not load custom walk sprites, using fallback: %s", e)
            return False

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
        # Apply velocities (normalize on diagonal so diagonal speed == base speed)
        vx = float(self.velocity_x)
        vy = float(self.velocity_y)
        try:
            if vx != 0 and vy != 0:
                # scale components so sqrt(vx^2+vy^2) == self.speed
                import math

                mag = math.hypot(vx, vy)
                if mag > 0:
                    factor = float(self.speed) / mag
                    vx *= factor
                    vy *= factor
            # Divide by FPS
            self.x += vx / 60
            self.y += vy / 60
        except Exception:
            # fallback to previous behaviour on any error
            try:
                self.x += self.velocity_x / 60
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
                # Keep `y` as float to preserve precise per-frame movement; clamp
                # against the configured bounds without truncating.
                self.y = max(float(vmin), min(self.y, float(vmax)))
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

        # Handle health regeneration (5 seconds = 300 frames at 60 FPS)
        try:
            regen_amount = getattr(self, "regen_per_5s", 0.0)
            if regen_amount > 0:
                self.regen_timer += 1
                frames_per_5s = 300  # 5 seconds at 60 FPS
                if self.regen_timer >= frames_per_5s:
                    self.health = min(self.max_health, self.health + regen_amount)
                    self.regen_timer = 0
        except Exception:
            pass

        # Handle shield cooldown timer
        try:
            if getattr(self, "shield_cooldown_timer", 0) > 0:
                self.shield_cooldown_timer -= 1
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

    def take_damage(self, damage, *, show_floating: bool = True) -> None:
        """Subtract health and optionally display floating damage text.

        The flag mirrors ``Enemy.take_damage`` and allows callers to suppress
        numbers for contact damage or other silent effects.  ``Game`` is
        accessed lazily via ``CURRENT_GAME`` to avoid circular imports.

        Shield charges can absorb one hit each (within cooldown window).
        """
        # Check if shield is available and active
        shield_charges = getattr(self, "shield_charges", 0)
        shield_cooldown_timer = getattr(self, "shield_cooldown_timer", 0)

        if shield_charges > 0 and shield_cooldown_timer <= 0:
            # Shield absorbs this hit
            # Base cooldown: 20 seconds = 1200 frames at 60 FPS
            # Reduced by 2 seconds (120 frames) per upgrade level taken
            shield_level = getattr(self, "shield_upgrade_level", 0)
            cooldown_frames = 1200 - (120 * shield_level)
            cooldown_frames = max(120, cooldown_frames)  # minimum 2 seconds
            self.shield_cooldown_timer = cooldown_frames

            if show_floating:
                try:
                    from src.game import CURRENT_GAME

                    if CURRENT_GAME is not None:
                        x = getattr(self, "x", None) or (
                            self.rect.centerx
                            if getattr(self, "rect", None) is not None
                            else 0
                        )
                        y = getattr(self, "y", None) or (
                            self.rect.centery
                            if getattr(self, "rect", None) is not None
                            else 0
                        )
                        CURRENT_GAME.spawn_floating_text("SHIELD!", x, y - 20)
                except Exception:
                    pass
            return

        actual_damage = damage * self.damage_reduction_multiplier
        self.health = max(0, self.health - actual_damage)

        if not show_floating:
            return

        # show floating text if a game instance is available
        try:
            from src.game import CURRENT_GAME

            if CURRENT_GAME is not None:
                try:
                    # position near player centre
                    x = getattr(self, "x", None) or (
                        self.rect.centerx
                        if getattr(self, "rect", None) is not None
                        else 0
                    )
                    y = getattr(self, "y", None) or (
                        self.rect.centery
                        if getattr(self, "rect", None) is not None
                        else 0
                    )
                    CURRENT_GAME.spawn_floating_text(str(int(actual_damage)), x, y)
                except Exception:
                    pass
        except Exception:
            # silent fail if import or attributes missing
            pass

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

    def set_scale(self, scale: float) -> None:
        """Adjust the player sprite size according to a scale factor.

        The image and walking frames are recreated from the original base
        dimensions to avoid progressive distortion.  The rectangle is updated
        to keep the player centred on the same position.
        """
        try:
            # compute new dimensions based on original sizes
            ow = getattr(self, "original_width", self.width)
            oh = getattr(self, "original_height", self.height)
            self.width = max(1, int(ow * scale))
            self.height = max(1, int(oh * scale))
            if self.base_image is not None:
                self.image = pygame.transform.scale(
                    self.base_image, (self.width, self.height)
                )
            # also scale walk frames if present
            if hasattr(self, "walk_frames") and self.walk_frames:
                self.walk_frames = [
                    pygame.transform.scale(f, (self.width, self.height))
                    for f in self.walk_frames
                ]
            # update rect to keep centre constant
            old_center = self.rect.center
            self.rect = self.image.get_rect()
            self.rect.center = old_center
        except Exception:
            pass

    def draw(
        self,
        screen,
        shake_x=0,
        shake_y=0,
        anim_frame=0,
        is_moving=False,
        facing_right=True,
    ) -> None:
        # Apply shake offset
        draw_x: float | int = self.rect.x + shake_x
        draw_y: float | int = self.rect.y + shake_y

        # Apply wobble/bobbing effect (continuous idle animation even when not moving)
        bob_offset = 0
        current_image: pygame.Surface = self.image

        # Calculate wobble effect on animation frame
        # Creates continuous up-down motion in all states
        bob_cycle: int = anim_frame % 4
        if bob_cycle == 1:
            bob_offset = -1  # Up
        elif bob_cycle == 3:
            bob_offset = 1  # Down
        else:
            bob_offset = 0  # Center

        if is_moving and self.walk_frames:
            # Use walking frames based on direction (2 frames per direction)
            # Frames 0-1 = right direction, frames 2-3 = left (flipped)
            frame_index: int = anim_frame % 2
            if not facing_right:
                frame_index += 2  # Use flipped frames for left movement

            if frame_index < len(self.walk_frames):
                current_image = self.walk_frames[frame_index]

        # Draw sprite with wobble offset
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

        # Draw blue shield indicator dot if shield is available and active
        shield_charges = getattr(self, "shield_charges", 0)
        shield_cooldown = getattr(self, "shield_cooldown_timer", 0)
        if shield_charges > 0 and shield_cooldown <= 0:
            # Shield is available, draw blue dot to the left of health bar
            shield_dot_x: float | int = bar_x - 8 + shake_x
            shield_dot_y: float | int = bar_y + bar_height // 2 + shake_y
            pygame.draw.circle(
                screen, (0, 150, 255), (int(shield_dot_x), int(shield_dot_y)), 3
            )
