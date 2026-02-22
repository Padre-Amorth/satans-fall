import importlib
import inspect
import logging
import math
import random
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pygame import Rect, Surface  # type: ignore
    from pygame.sprite import Sprite as SpriteType  # type: ignore
else:
    Rect = Any
    Surface = Any
    SpriteType = Any

from types import ModuleType

try:
    pygame: ModuleType = importlib.import_module("pygame")
except Exception:
    pygame: ModuleType = importlib.import_module("pygame_ce")  # type: ignore

# Ensure a runtime base class reference without assigning to the type name
try:
    PygameSprite = pygame.sprite.Sprite  # type: ignore
except Exception:
    PygameSprite = object

# Use an explicit runtime base variable so mypy does not confuse a TYPE_CHECKING
# alias with a runtime assignment.
BaseSprite: type
try:
    BaseSprite = pygame.sprite.Sprite  # type: ignore
except Exception:
    BaseSprite = object

# Import Projectile explicitly from src.projectile for stability
from src.projectile import Projectile  # noqa: E402

logger: logging.Logger = logging.getLogger(__name__)


class BurnParticle:
    """Simple particle for burn visual effect"""

    def __init__(
        self, x: float, y: float, vx: float, vy: float, life: int = 30, size: int = 3
    ):
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

    def __init__(
        self, x: float, y: float, vx: float, vy: float, life: int = 20, size: int = 2
    ):
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
    def __init__(
        self,
        x: float,
        y: float,
        enemy_type: str = "basic",
        health: float = 20.0,
        speed: float = 60.0,
    ) -> None:
        super().__init__()
        self.x: Any = x
        self.y: Any = y
        self.enemy_type: str = enemy_type
        self.max_health: int = int(health)
        self.health: int = int(health)
        # Use the provided `speed` directly — no global reduction applied
        self.speed: float = float(speed)
        self.width = 30
        self.height = 30
        self.damage = 10

        # Adjust size and damage based on type
        if enemy_type == "strong":
            # Increase base size so final size (after +10 adjustment) is 70x70
            self.width = 60
            self.height = 60
            self.damage = 15
        elif enemy_type == "shielded":
            self.width = 60
            self.height = 60
            self.damage = 15
        elif enemy_type == "mage":
            # Mage: 50x50 before +10 growth → 60x60 final; support caster, not melee
            self.width = 50
            self.height = 50
            self.damage = 8
        elif enemy_type == "custode":
            # Custode: large enemy that splits at half health
            self.width = 80
            self.height = 80
            self.damage = 20
        elif enemy_type == "giant":
            # Increase base size so final size (after +10 adjustment) is 70x70
            self.width = 60
            self.height = 60
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
            # Toggle used to alternate firing pattern (3-shot, then single)
            self.inquisitor_fire_single_next: bool = False
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

        # Custode are especially tough: double their health after global modifier
        if enemy_type == "custode":
            self.max_health *= 2
            self.health = self.max_health

        # Shield HP: shielded and mage enemies absorb damage through shield first
        if enemy_type in ("shielded", "mage"):
            self.shield_hp: int = self.max_health
        # Mage support-caster state
        if enemy_type == "mage":
            self.shield_timer: int = 60 * 5  # frames until first shield cast
        # Custode split flag: True means this custode is already a split half
        if enemy_type == "custode":
            self._custode_split: bool = False

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
        self.burn_particles: list["BurnParticle"] = []
        self.ice_particles: list["IceParticle"] = []

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

        # Ensure we only record a kill once if kill() called multiple times
        self._kill_recorded: bool = False

    def kill(self) -> None:
        """Override kill to notify the running Game once (idempotent)."""
        try:
            # Import CURRENT_GAME from whichever module path is available in the
            # current test/runtime environment ('game' or 'src.game'). Tests
            # sometimes import Game as `game` (top-level) while runtime uses
            # `src.game` — handle both to ensure the kill counter is recorded.
            try:
                # Prefer the packaged module import path used by the test-suite/runtime
                from src.game import CURRENT_GAME

                # If that module's CURRENT_GAME is not set but a top-level `game`
                # module exists (some tests import `game`), prefer that instead.
                if CURRENT_GAME is None:
                    try:
                        from game import CURRENT_GAME as _ALT_CURRENT_GAME

                        CURRENT_GAME = _ALT_CURRENT_GAME
                    except Exception:
                        pass
            except Exception:
                try:
                    from game import CURRENT_GAME as _ALT_CURRENT_GAME

                    CURRENT_GAME = _ALT_CURRENT_GAME
                except Exception:
                    CURRENT_GAME = None

            # If multiple Game instances/modules are present in the test-runner
            # prefer the Game instance that actually contains this enemy in its
            # `enemies` container. This avoids recording kills on a different
            # running Game when tests import both `game` and `src.game`.
            try:
                if CURRENT_GAME is not None:
                    enemies_container = getattr(CURRENT_GAME, "enemies", None)
                    found_here = False
                    try:
                        if enemies_container is not None:
                            if hasattr(enemies_container, "sprites"):
                                # pygame Group
                                try:
                                    if self in enemies_container.sprites():
                                        found_here = True
                                except Exception:
                                    found_here = False
                            else:
                                if self in enemies_container:
                                    found_here = True
                    except Exception:
                        found_here = False

                    # If the current module's CURRENT_GAME doesn't own this enemy,
                    # try the alternate top-level `game` module (if available).
                    if not found_here:
                        try:
                            from game import CURRENT_GAME as _ALT_CURRENT_GAME

                            alt_enemies = getattr(_ALT_CURRENT_GAME, "enemies", None)
                            if alt_enemies is not None:
                                if hasattr(alt_enemies, "sprites"):
                                    try:
                                        if self in alt_enemies.sprites():
                                            CURRENT_GAME = _ALT_CURRENT_GAME
                                    except Exception:
                                        pass
                                else:
                                    try:
                                        if self in alt_enemies:
                                            CURRENT_GAME = _ALT_CURRENT_GAME
                                    except Exception:
                                        pass
                        except Exception:
                            pass
            except Exception:
                pass
            if not getattr(self, "_kill_recorded", False):
                try:
                    if CURRENT_GAME is not None:
                        CURRENT_GAME.record_enemy_kill()
                except Exception:
                    pass
                try:
                    self._kill_recorded = True
                except Exception:
                    pass
        except Exception:
            # If import failed, still attempt to set the flag to avoid double-records
            try:
                self._kill_recorded = True
            except Exception:
                pass
        except Exception:
            pass
        # Call base kill
        try:
            super().kill()
        except Exception:
            try:
                # defensive: attempt to remove from any groups
                if hasattr(self, "groups"):
                    for g in list(self.groups()):
                        try:
                            g.remove(self)
                        except Exception:
                            pass
            except Exception:
                pass

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
            logger.debug("Could not load %s, using fallback drawing: %s", asset_name, e)
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
                    # Stop 100px higher than the previous 'slightly above center' position
                    desired_y = game.height / 2 - 150
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
                        center: tuple[int | Any, int | Any] = (
                            overlay.get_width() // 2,
                            overlay.get_height() // 2,
                        )
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
                    # Prologue boss entrance: walk down from top to position below cathedral
                    if not hasattr(self, "entrance_complete"):
                        # Find target position below cathedral
                        target_y = 140  # Position below cathedral (cathedral ends around y=120)

                        # Move down towards target
                        if self.y < target_y:
                            self.y += self.speed * 0.5 / 60  # Walk down at half speed
                            # Keep centered horizontally
                            self.x = game.width // 2
                        else:
                            # Reached target position
                            self.entrance_complete = True
                            self.y = target_y

                            # Initialize floating movement for normal behavior
                            self.float_center_x = self.x
                            self.float_amplitude = 150
                            self.float_speed = 0.015
                            self.float_time = 0

                    if hasattr(self, "entrance_complete") and self.entrance_complete:
                        # Normal floating behavior after entrance
                        # Stay at target height, float horizontally
                        self.y = 140  # Keep at target position

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
                        self.stop_threshold = max(
                            10, min(game.width, game.height) * 0.05
                        )

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

                elif (
                    self.enemy_type == "boss_big"
                    and game is not None
                    and getattr(game, "selected_stage", None)
                    in ("limbo", "limbo_2", "limbo_3")
                ):
                    # Boss Big (Limbo stages): descend vertically to a mid-screen Y,
                    # then perform a smooth sinusoidal horizontal oscillation (no chase).
                    top_margin = 30
                    bottom_limit = int(game.height / 2) - 40  # vertical stop line
                    left_limit = 50
                    right_limit = game.width - 50

                    # Initialize Limbo-specific state on first update
                    if not hasattr(self, "limbo_phase"):
                        # Phase: 'descend' -> move vertically toward bottom_limit
                        #        'hover'  -> sinusoidal horizontal oscillation around a center X
                        self.limbo_phase = "descend"
                        # Record where the entrance starts so we can ease acceleration
                        # from the spawn Y -> entrance_threshold smoothly.
                        self.entrance_start_y = float(self.y)
                        # Stop 150px higher than the prior bottom_limit (raised 50px from before),
                        # but never above the top margin region.
                        self.limbo_target_y = float(
                            max(top_margin + 10, bottom_limit - 150)
                        )
                        # Centre of horizontal oscillation (set when hover starts)
                        self.hover_center_x = float(self.x)
                        # Phase and parameters for the sine wave
                        self.hover_phase = random.uniform(0.0, math.pi * 2)
                        # Tune amplitude/frequency slightly by limbo stage for variety
                        stage = getattr(game, "selected_stage", "limbo")
                        # Increase base amplitude to make oscillation noticeably wider
                        base_amp = 120.0
                        if stage == "limbo_2":
                            base_amp = 160.0
                        elif stage == "limbo_3":
                            base_amp = 200.0
                        # Ensure amplitude fits inside arena (respect walls)
                        max_amp = max(10.0, (right_limit - left_limit) / 2.0 - 6.0)
                        self.hover_amplitude = min(base_amp, max_amp)
                        # Angular speed (radians/frame) -> period ~ (2*pi / ang_speed)
                        # Further reduced angular speed => noticeably slower oscillation
                        # (still within testable limits so we observe at least one cycle).
                        self.hover_angular_speed = random.uniform(0.010, 0.022)

                    if self.limbo_phase == "descend":
                        # Move vertically toward the mid-screen stop line; keep X steady
                        dy = self.limbo_target_y - self.y
                        if abs(dy) > 2:
                            vy = math.copysign(max(1.0, abs(dy) * 0.12), dy)

                            # Entrance easing: progressively accelerate from a slow
                            # entrance speed up to normal descent as the boss moves
                            # into the visible area. Progress is based on Y position
                            # from entrance_start_y -> entrance_threshold.
                            entrance_threshold = top_margin + 60
                            entrance_slow_factor = 0.25  # slow at the very start
                            base_speed_factor = self.speed * 0.02

                            start_y = getattr(self, "entrance_start_y", self.y)
                            if (
                                self.y < entrance_threshold
                                and entrance_threshold > start_y
                            ):
                                # progress in [0,1] as boss moves from start_y -> threshold
                                progress = (self.y - start_y) / (
                                    entrance_threshold - start_y
                                )
                                progress = max(0.0, min(1.0, progress))
                                # ease-in (quadratic) so acceleration ramps up gradually
                                ease = progress * progress
                                lerped = (
                                    entrance_slow_factor
                                    + (1.0 - entrance_slow_factor) * ease
                                )
                                speed_factor = base_speed_factor * lerped
                            else:
                                speed_factor = base_speed_factor

                            # apply vertical movement with progressive acceleration
                            self.y += vy * speed_factor
                        else:
                            # Arrived: switch to hover phase; capture current center X
                            self.limbo_phase = "hover"
                            self.hover_center_x = float(self.x)

                        # Small x-clamp while descending to avoid wall overlap
                        try:
                            self.x = game.clamp_to_walls(self.x)
                        except Exception:
                            self.x = max(left_limit, min(right_limit, self.x))
                        # Clamp vertically so it never crosses halfway line.
                        # Allow boss_big in the 'descend' entrance phase to remain
                        # above the visible top (y < top_margin) so it can enter
                        # gradually from off-screen instead of snapping to top.
                        if not (
                            self.enemy_type == "boss_big"
                            and getattr(self, "limbo_phase", None) == "descend"
                        ):
                            self.y = max(top_margin, min(self.y, bottom_limit))
                        else:
                            # Only cap the lower bound — allow values above top_margin
                            self.y = min(self.y, bottom_limit)

                    elif self.limbo_phase == "hover":
                        # Maintain Y near the mid-screen line with light vertical jitter
                        self.y += random.uniform(-0.25, 0.25)
                        self.y = max(top_margin, min(self.y, bottom_limit))

                        # Sinusoidal horizontal oscillation around hover_center_x
                        self.hover_phase += self.hover_angular_speed
                        self.x = self.hover_center_x + (
                            self.hover_amplitude * math.sin(self.hover_phase)
                        )

                        # Keep inside arena walls (clamp final X)
                        try:
                            self.x = game.clamp_to_walls(self.x)
                        except Exception:
                            self.x = max(left_limit, min(right_limit, self.x))

                    # Ensure boss never chases the player in Limbo
                    # (no code path that sets velocity towards player here)

                elif self.enemy_type == "boss_inquisitor" and game is not None:
                    # Inquisitor roams randomly within the top half of the playfield
                    # Do not chase the player directly; pick random roam targets and move there
                    top_margin = 50
                    bottom_limit = int(game.height / 2) - 40  # do not cross halfway
                    left_limit = 50
                    right_limit = game.width - 50

                    if not hasattr(self, "roam_target"):
                        # Use game's clamp_to_walls so roam stays within arena walls
                        rx = random.uniform(
                            game.clamp_to_walls(0), game.clamp_to_walls(game.width)
                        )
                        ry = random.uniform(
                            top_margin, max(top_margin + 10, bottom_limit)
                        )
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
                        rx = random.uniform(
                            game.clamp_to_walls(0), game.clamp_to_walls(game.width)
                        )
                        ry = random.uniform(
                            top_margin, max(top_margin + 10, bottom_limit)
                        )
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

                elif self.enemy_type == "mage" and game is not None:
                    # Mage behaviour: a support caster that stays in the back
                    # quarter of the arena and periodically grants shields.
                    # --- movement toward rear zone ------------------------------------------------
                    rear_y = max(30, game.height // 4)
                    # vertical movement: if outside a small band around rear_y, move
                    # at full speed until entering the rear area. once inside, keep a
                    # gentle oscillation so the mage doesn't freeze.
                    if self.y > rear_y + 10:
                        # still below ideal zone, move upward at normal speed
                        self.y -= self.speed / 60
                    elif self.y < rear_y - 10:
                        # above ideal zone, descend
                        self.y += self.speed / 60
                    else:
                        # inside target band: small sinusoidal bobbing
                        self.y += math.sin(getattr(self, "_mage_vert_phase", 0.0)) * 0.5
                        self._mage_vert_phase = (
                            getattr(self, "_mage_vert_phase", 0.0) + 0.05
                        )
                    # continuous horizontal motion (sinusoidal) for visibility
                    self.x += math.sin(getattr(self, "_mage_drift_phase", 0.0)) * 0.5
                    self._mage_drift_phase = (
                        getattr(self, "_mage_drift_phase", 0.0) + 0.04
                    )
                    # clamp to walls/arena bounds
                    try:
                        self.x = game.clamp_to_walls(self.x)
                    except Exception:
                        self.x = max(30, min(game.width - 30, self.x))
                    # keep within vertical margins too
                    self.y = max(10, min(game.height - 30, self.y))

                    # --- shield‑cast timer -----------------------------------------------------
                    if not hasattr(self, "shield_timer"):
                        # first timer initialised to a random 5‑10 second interval
                        fps = getattr(game, "fps", 60)
                        self.shield_timer = fps * random.randint(5, 10)
                    self.shield_timer -= 1
                    if self.shield_timer <= 0:
                        # choose a random alive ally (not self) and give it a shield
                        try:
                            allies = [
                                e
                                for e in game.enemies
                                if e is not self and getattr(e, "health", 0) > 0
                            ]
                            if allies:
                                target = random.choice(allies)
                                target.shield_hp = self.max_health
                                target.shield_beam = {"remaining": 30, "source": self}
                                if not hasattr(target, "shield_particles"):
                                    target.shield_particles = []
                                for _ in range(8):
                                    target.shield_particles.append(
                                        {
                                            "x": target.x + random.uniform(-10, 10),
                                            "y": target.y + random.uniform(-10, 10),
                                            "vx": random.uniform(-1, 1),
                                            "vy": random.uniform(-2, 0),
                                            "life": random.randint(15, 30),
                                        }
                                    )
                        except Exception:
                            pass
                        # reset timer for another random 5‑10 second interval
                        fps = getattr(game, "fps", 60)
                        self.shield_timer = fps * random.randint(5, 10)

                    # update any shield particles on the mage itself
                    if hasattr(self, "shield_particles"):
                        self.shield_particles = [
                            p for p in self.shield_particles if p.get("life", 0) > 0
                        ]
                        for p in self.shield_particles:
                            p["x"] += p.get("vx", 0)
                            p["y"] += p.get("vy", 0)
                            p["life"] -= 1

                elif self.enemy_type == "custode" and game is not None:
                    # Custode: first, apply any initial outward push
                    if getattr(self, "_custode_push_timer", 0) > 0:
                        push_speed = self.speed * 0.5  # push magnitude ~half regular
                        self.x += self._custode_push_dir * push_speed / 60
                        self._custode_push_timer -= 1

                    # then move toward player like a normal enemy
                    dx = player.x - self.x
                    dy = player.y - self.y
                    distance: float = math.sqrt(dx * dx + dy * dy)
                    if distance > 1:
                        self.x += (dx / distance) * self.speed / 60
                        self.y += (dy / distance) * self.speed / 60
                    # Check for half-health split (only if not already a half)
                    if (
                        not getattr(self, "_custode_split", False)
                        and self.health <= self.max_health / 2
                    ):
                        self._custode_split = True
                        self.health = 0
                        # Spawn two smaller custodes
                        try:
                            half_health = max(1, self.max_health // 2)
                            half_w = max(10, self.width // 2 - 10)
                            half_h = max(10, self.height // 2 - 10)
                            # record the parent’s base speed (accounting for
                            # any active slowdown). we’ll double that for the
                            # children and also mark it as their `original_speed`
                            orig_speed = getattr(self, "original_speed", self.speed)
                            doubled = orig_speed * 2.0
                            # choose separation distance based on current size so
                            # halves start noticeably farther apart than before
                            sep_dist = max(30, self.width // 2)
                            for offset_x in (-sep_dist, sep_dist):
                                # halves travel at a fixed 2× speed boost; they
                                # should chomp after the player noticeably faster
                                # than the parent
                                child = Enemy(
                                    self.x + offset_x,
                                    self.y,
                                    "custode",
                                    half_health,
                                    doubled,
                                )
                                # give the new halves a short outward push so they
                                # visibly peel away from each other when spawned
                                child._custode_push_dir = -1 if offset_x < 0 else 1
                                child._custode_push_timer = 15
                                child.width = half_w
                                child.height = half_h
                                child.max_health = int(half_health * 1.2)
                                child.health = child.max_health
                                # make sure collision/slow systems treat the new
                                # halves as having the doubled speed, otherwise
                                # they’ll reset back to the parent’s value
                                child.original_speed = doubled
                                child._custode_split = True  # halves do not split again
                                child.image = pygame.Surface(
                                    (child.width, child.height), pygame.SRCALPHA
                                )
                                child.draw_enemy()
                                child.rect = child.image.get_rect(
                                    center=(child.x, child.y)
                                )
                                if hasattr(game.enemies, "add"):
                                    game.enemies.add(child)
                                else:
                                    game.enemies.append(child)
                            # Explosion effect
                            try:
                                # explosion area effect with full metadata so drawing works
                                game.skullboom_explosions.append(
                                    {
                                        "x": self.x,
                                        "y": self.y,
                                        "radius": 40,
                                        "max_radius": 40,
                                        "timer": 15,
                                        "max_timer": 15,
                                        # default glow colour
                                        "color": (255, 150, 50),
                                    }
                                )
                            except Exception:
                                pass
                            try:
                                # spawn several burn particles using the same helper class
                                for _ in range(6):
                                    try:
                                        p_burn = BurnParticle(
                                            self.x,
                                            self.y,
                                            random.uniform(-3, 3),
                                            random.uniform(-3, 3),
                                            life=random.randint(10, 20),
                                        )
                                        game.skullboom_particles.append(p_burn)
                                    except Exception:
                                        # fall back to dict if BurnParticle fails for some reason
                                        try:
                                            game.skullboom_particles.append(
                                                {
                                                    "x": self.x,
                                                    "y": self.y,
                                                    "vx": random.uniform(-3, 3),
                                                    "vy": random.uniform(-3, 3),
                                                    "life": random.randint(10, 20),
                                                }
                                            )
                                        except Exception:
                                            pass
                            except Exception:
                                pass
                        except Exception:
                            pass
                        self.kill()

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
                        delattr(self, "original_speed")
            if hasattr(self, "burn_timer") and getattr(self, "burn_timer", 0) > 0:
                # Per-frame decrement
                self.burn_timer -= 1
                # Initialize tick timer if missing
                if (
                    not hasattr(self, "burn_tick_timer")
                    or getattr(self, "burn_tick_timer", 0) <= 0
                ):
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
                        p = BurnParticle(
                            px,
                            py,
                            vx,
                            vy,
                            life=random.randint(20, 44),
                            size=random.randint(3, 5),
                        )
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

            # Update shield_particles (dict-based, used by mage shield-cast targets)
            if hasattr(self, "shield_particles") and self.shield_particles:
                alive = []
                for p in self.shield_particles:
                    try:
                        p["x"] += p.get("vx", 0)
                        p["y"] += p.get("vy", 0)
                        p["life"] -= 1
                        if p["life"] > 0:
                            alive.append(p)
                    except Exception:
                        pass
                self.shield_particles = alive

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
            # Mini‑Inquisitor (normal enemy with inquisitor appearance) fires only the single aimed slow projectile
            if (
                self.enemy_type == "normal"
                and getattr(self, "appearance", None) == "inquisitor"
            ):
                dx = player.x - self.x
                dy = player.y - self.y
                distance: float = math.sqrt(dx * dx + dy * dy)
                if distance > 0:
                    speed = 260
                    vel_x = (dx / distance) * speed
                    vel_y = (dy / distance) * speed
                else:
                    vel_x = 0
                    vel_y = 260

                proj = Projectile(
                    self.x,
                    self.y,
                    vel_x,
                    vel_y,
                    damage=14,
                    radius=7,
                    is_enemy_projectile=True,
                    appearance="inquisitor",
                )
                proj.effect = "slow"
                proj.slow_duration = 180
                proj.slow_factor = 0.4
                game.enemy_projectiles.add(proj)

                # Keep same fire-rate as boss inquisitor
                try:
                    self.shoot_cooldown = random.randint(100, 140)
                except Exception:
                    self.shoot_cooldown = 120
            elif self.enemy_type == "normal":
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

                projectile: Projectile[
                    Any | Any | float, Any | Any | int, Any | int, Any | int
                ] = Projectile(
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

                projectile: Projectile[
                    Any | Any | float, Any | Any | int, Any | int, Any | int
                ] = Projectile(
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
                # Inquisitor: alternate between a 3-shot spread and a single aimed shot
                dx = player.x - self.x
                dy = player.y - self.y
                base_angle = math.atan2(dy, dx)
                speed = 260

                # Alternate pattern: if flag is True -> single shot, else -> 3-shot spread
                if getattr(self, "inquisitor_fire_single_next", False):
                    # Single aimed shot (center)
                    vel_x = math.cos(base_angle) * speed
                    vel_y = math.sin(base_angle) * speed
                    proj = Projectile(
                        self.x,
                        self.y,
                        vel_x,
                        vel_y,
                        damage=14,
                        radius=7,
                        is_enemy_projectile=True,
                        appearance="inquisitor",
                    )
                    proj.effect = "slow"
                    proj.slow_duration = 180
                    proj.slow_factor = 0.4
                    game.enemy_projectiles.add(proj)
                else:
                    # 3-shot spread (slightly narrower than before)
                    angles = [base_angle - 0.25, base_angle, base_angle + 0.25]
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
                        proj.effect = "slow"
                        proj.slow_duration = 180
                        proj.slow_factor = 0.4
                        game.enemy_projectiles.add(proj)

                # Toggle for next shot
                self.inquisitor_fire_single_next = not getattr(
                    self, "inquisitor_fire_single_next", False
                )
                # Slightly longer cooldown after a single shot to balance rhythm
                if getattr(self, "inquisitor_fire_single_next", False):
                    # next will be single -> use normal cooldown
                    self.shoot_cooldown = random.randint(110, 150)
                else:
                    # next will be 3-shot -> keep cooldown slightly shorter for pattern
                    self.shoot_cooldown = random.randint(100, 140)

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

                projectile: Projectile[
                    Any | Any | float, Any | Any | int, Any | int, Any | int
                ] = Projectile(
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
        try:
            logger.debug(
                "Enemy.take_damage: %s taking damage %s (health_before=%s)",
                self,
                damage,
                getattr(self, "health", None),
            )
        except Exception:
            pass
        # Debug: log take_damage call (caller info included)
        try:
            caller = "unknown"
            try:
                f = inspect.stack()[1]
                caller = f"{f.filename}:{f.lineno} in {f.function}"
            except Exception:
                pass
            logger.debug(
                "Enemy.take_damage called -> self=%s dmg=%s health_before=%s caller=%s",
                self,
                damage,
                getattr(self, "health", None),
                caller,
            )
        except Exception:
            pass
        # Centralized safeguard: if this is the Prologo final boss and it is currently
        # in the immortal/regeneration phase, ignore incoming damage from any source.
        try:
            from src.game import CURRENT_GAME

            if (
                getattr(self, "enemy_type", "") == "boss_final"
                and CURRENT_GAME is not None
                and getattr(CURRENT_GAME, "selected_stage", None) == "prologo"
                and getattr(CURRENT_GAME, "prologo_final_boss_immortal", False)
            ):
                return
        except Exception:
            pass

        # Shield absorption: shield_hp takes the hit first; health only decreases when shield is gone
        if getattr(self, "shield_hp", 0) > 0:
            absorbed = min(self.shield_hp, damage)
            self.shield_hp -= absorbed
            damage -= absorbed
            if damage <= 0:
                self.shake_timer = 10
                return

        self.health -= damage
        try:
            logger.debug(
                "Enemy.take_damage: %s health_after=%s",
                self,
                getattr(self, "health", None),
            )
        except Exception:
            pass

        # If a wave boss (boss_medium) is killed by any damage source, ensure the
        # game's reinforcement sequence is scheduled (message + timer). This covers
        # cases where bosses die outside the projectile-collision path (burn, DOT, etc.).
        try:
            from src.game import CURRENT_GAME

            if (
                getattr(self, "enemy_type", "") == "boss_medium"
                and CURRENT_GAME is not None
                and getattr(self, "health", 1) <= 0
            ):
                try:
                    CURRENT_GAME.show_centered_message(
                        "REINFORCEMENTS INCOMING!", 1800, (255, 204, 0)
                    )
                except Exception:
                    pass
                try:
                    import pygame

                    pygame.time.set_timer(pygame.USEREVENT + 1, 0)
                    pygame.time.set_timer(
                        pygame.USEREVENT + 1, CURRENT_GAME.reinforcement_delay_ms
                    )
                except Exception:
                    pass
        except Exception:
            pass
        # If this is the Prologo final boss and the damage reduced it to <=10% of
        # max health, begin the immortal/regeneration phase and clamp HP to 10%.
        try:
            from src.game import CURRENT_GAME

            if (
                getattr(self, "enemy_type", "") == "boss_final"
                and CURRENT_GAME is not None
                and getattr(CURRENT_GAME, "selected_stage", None) == "prologo"
            ):
                # Only trigger the phase when not already immortal
                if not getattr(CURRENT_GAME, "prologo_final_boss_immortal", False):
                    try:
                        threshold = getattr(self, "max_health", 0) * 0.1
                        if getattr(self, "health", 0) <= threshold:
                            CURRENT_GAME.prologo_final_boss_immortal = True
                            # Clamp to exact 10% so subsequent game logic won't kill the boss
                            self.health = int(threshold)
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            caller = "unknown"
            try:
                f = inspect.stack()[1]
                caller = f"{f.filename}:{f.lineno} in {f.function}"
            except Exception:
                pass
            logger.debug(
                "Enemy.take_damage finished -> self=%s health_after=%s caller=%s",
                self,
                getattr(self, "health", None),
                caller,
            )
        except Exception:
            pass
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
                    x = getattr(self, "x", None) or (
                        self.rect.centerx
                        if getattr(self, "rect", None) is not None
                        else 0
                    )

                    # Position above enemy
                    pos_y = (getattr(self, "rect", None) and self.rect.top - 8) or (
                        getattr(self, "y", 0) - getattr(self, "height", 0) // 2 - 8
                    )
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

            # Draw shield bar (blue) below health bar when shield_hp > 0
            if getattr(self, "shield_hp", 0) > 0:
                sh_y = bar_y + 4
                shield_ratio = max(0, min(1, self.shield_hp / max(1, self.max_health)))
                pygame.draw.rect(
                    screen, (20, 60, 120), (bar_x, sh_y, bar_width, bar_height)
                )
                pygame.draw.rect(
                    screen,
                    (100, 150, 255),
                    (bar_x, sh_y, bar_width * shield_ratio, bar_height),
                )
            # draw a connecting beam if mage has recently granted shield
            if getattr(self, "shield_beam", None):
                try:
                    beam = self.shield_beam
                    if beam.get("remaining", 0) > 0 and beam.get("source"):
                        src = beam["source"]
                        # compute world-centre coordinates (ignore width/height)
                        sx = int(getattr(src, "x", 0) + shake_x)
                        sy = int(getattr(src, "y", 0) + shake_y)
                        ex = int(self.x + shake_x)
                        ey = int(self.y + shake_y)
                        # build a 3‑point polyline with noisy midpoint for irregularity
                        mx = (sx + ex) // 2 + random.randint(-6, 6)
                        my = (sy + ey) // 2 + random.randint(-6, 6)
                        pygame.draw.lines(
                            screen,
                            (200, 200, 255),
                            False,
                            [(sx, sy), (mx, my), (ex, ey)],
                            2,
                        )
                        beam["remaining"] -= 1
                    else:
                        # clear when expired
                        try:
                            delattr(self, "shield_beam")
                        except Exception:
                            pass
                except Exception:
                    pass

            # Draw burn status indicator (flame + optional text) if enemy is burning
            try:
                # Draw particles behind the flame
                if self.burn_particles:
                    for bp in list(self.burn_particles):
                        try:
                            surf = pygame.Surface(
                                (bp.size * 2 + 2, bp.size * 2 + 2), pygame.SRCALPHA
                            )
                            alpha = max(60, int(255 * (bp.life / 44)))
                            pygame.draw.circle(
                                surf,
                                (255, 120, 0, alpha),
                                (bp.size + 1, bp.size + 1),
                                bp.size,
                            )
                            screen.blit(
                                surf, (int(bp.x - bp.size), int(bp.y - bp.size))
                            )
                        except Exception:
                            pass

                # Draw ice particles
                if self.ice_particles:
                    for ip in list(self.ice_particles):
                        try:
                            surf = pygame.Surface(
                                (ip.size * 2 + 2, ip.size * 2 + 2), pygame.SRCALPHA
                            )
                            alpha = max(50, int(255 * (ip.life / 25)))
                            pygame.draw.circle(
                                surf,
                                (200, 240, 255, alpha),
                                (ip.size + 1, ip.size + 1),
                                ip.size,
                            )
                            screen.blit(
                                surf, (int(ip.x - ip.size), int(ip.y - ip.size))
                            )
                        except Exception:
                            pass

                # Burn status: particles are drawn above; legacy flame/text removed (particles retained)

            except Exception as e:
                logger.exception(
                    "Error drawing burn effect for enemy %s: %s", self.enemy_type, e
                )
        except Exception as e:
            logger.exception("Error drawing enemy %s: %s", self.enemy_type, e)
