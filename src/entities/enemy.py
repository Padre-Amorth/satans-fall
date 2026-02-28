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
        elif enemy_type == "crusader":
            # Crusader: even bigger/tankier slow variant in the vein of a giant.
            # When using the default drawing code this will render as a grey
            # armored brute; external sprites may override via asset file.
            # Introduce invulnerability cycle state here so the update loop can
            # flip it every three seconds.
            self.width = 70
            self.height = 70
            self.damage = 25
            self.invulnerable = False
            self._vuln_timer = 180  # frames until next state change
        elif enemy_type == "giant":
            # Increase base size so final size (after +10 adjustment) is 70x70
            self.width = 60
            self.height = 60
            self.damage = 20
        elif enemy_type == "angel":
            self.width = 35
            self.height = 35
            self.damage = 12
        elif enemy_type == "winged":
            # Winged flyer: fast and nimble, moderate health
            self.width = 30
            self.height = 30
            self.damage = 10
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

        # Winged enemies also get a health boost and a shield
        if enemy_type == "winged":
            self.max_health *= 2
            self.health = self.max_health
            # give them a shield equal to their health
            self.shield_hp: int = self.max_health

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
        elif enemy_type == "boss_limbo":
            # Limbo boss doesn't fire via the normal shoot_at_player path; its
            # attacks are handled in the boss-pattern logic.  Keep cooldown
            # set to None so update() doesn't try to call shoot_at_player.
            self.shoot_cooldown = None
        elif enemy_type in ["boss_big"]:
            # Boss_big doesn't have regular shooting, only special attacks
            self.shoot_cooldown = None
        else:
            self.shoot_cooldown = None

        # Boss pattern timers
        # Boss pattern timers (None when not applicable)
        self.pattern_timer: int | None = None
        self.big_shot_cooldown: int | None = None
        # optional area-attack timer only used by the Limbo boss
        self.area_attack_cooldown: int | None = None
        if enemy_type == "boss_big":
            self.pattern_timer = random.randint(100, 180)
            self.big_shot_cooldown = random.randint(200, 320)
            self.area_attack_cooldown = None
        elif enemy_type == "boss_final" or enemy_type == "boss_limbo":
            # Final bosses get a pattern timer.  Limbo boss also receives a
            # secondary "big shot" cooldown for its inquisitor-style spread and
            # (separately) an area explosion timer.  The Limbo boss's primary
            # pattern is a single large projectile rather than a radial burst.
            # Use a timer around three seconds so the big sphere is less
            # frequent; the first tick is randomized a bit to avoid synchronicity
            # with other patterns.
            self.pattern_timer = random.randint(150, 210)
            if enemy_type == "boss_limbo":
                self.big_shot_cooldown = random.randint(200, 320)
                self.area_attack_cooldown = random.randint(180, 300)
            else:
                self.big_shot_cooldown = None
                self.area_attack_cooldown = None
        elif enemy_type == "boss_limbo_horde":
            # Horde boss doesn't need a pattern timer or area attack, but it
            # should have a big_shot_cooldown so the green triple can fire.
            self.pattern_timer = None
            self.big_shot_cooldown = random.randint(200, 320)
            self.area_attack_cooldown = None
        else:
            self.pattern_timer = None
            self.big_shot_cooldown = None
            self.area_attack_cooldown = None

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

        # Walking animation state for animated enemy types
        if enemy_type in (
            "giant",
            "custode",
            "boss_inquisitor",
            "mage",
            "normal",
            "strong",
            "shielded",
        ):
            self._anim_frame: int = 0
            self._anim_timer: int = 0
            self._facing_right: bool = True  # default: face right (toward player)
            self._facing_down: bool = True  # default: face down (toward player)

    def _apply_aura(self, pulse: int) -> None:
        """Helper to rebuild `self.image` with a glowing aura behind the boss.

        The aura surface is larger than the boss so that the glow appears around
        the silhouette rather than on top of it.  A boss copy is blitted over the
        aura center so the sprite itself is never overwritten.
        """
        # prepare the boss sprite at current dimensions
        if getattr(self, "base_image", None) is not None:
            boss_img = pygame.transform.scale(
                self.base_image, (self.width, self.height)
            )
        else:
            boss_img = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self.draw_enemy()
        # aura should be a round halo slightly larger than the boss itself.
        # We compute the radius based on the *diagonal* of the boss bounding
        # box rather than simply max(width,height).  This guarantees the glow
        # fully encloses even very elongated bosses, avoiding cases where the
        # diagonal corners poked outside the circle and appeared unlit.
        # Use a square surface so transparency around the circle remains circular
        # (avoids large rectangular alpha regions that appear square when blitted).
        base_radius = int(math.hypot(self.width, self.height) / 2)
        # small inner glow padding to make the circle slightly larger than
        # the boss silhouette – reduced to 1px so there's a clearer gap from
        # the outer fade ring.
        padding = 1
        glow_radius: int = base_radius + padding
        # larger outer fade padding so the inner glow is far from the
        # softened ring; this makes the two circles visually separated
        outer_padding = 20
        aura_radius = glow_radius + outer_padding
        aura_size = aura_radius * 2
        aura = pygame.Surface((aura_size, aura_size), pygame.SRCALPHA)
        center = (aura_radius, aura_radius)
        # soft outer ring with reduced alpha (drawn first so it does not
        # overwrite the main glow inside its radius)
        # make the outer ring much more transparent than the interior pulse
        # use a fraction of the pulse value so it scales down dramatically
        fade_alpha = max(0, int(pulse * 0.25))
        if fade_alpha > 0:
            pygame.draw.circle(aura, (255, 240, 200, fade_alpha), center, aura_radius)
        # main solid glow, slightly more transparent than raw pulse value
        inner_alpha = int(pulse * 0.8)
        pygame.draw.circle(aura, (255, 240, 200, inner_alpha), center, glow_radius)
        # place boss over aura, centered
        boss_rect = boss_img.get_rect(center=center)
        aura.blit(boss_img, boss_rect)
        self.image = aura
        # update rect to match new size and keep centered on (x,y)
        try:
            # set rect based on aura image first (needed for centering)
            self.rect = self.image.get_rect(center=(self.x, self.y))
            # shrink rect so the aura border is not part of the hitbox; boss
            # sprites should only collide on the solid interior (glow_radius)
            if outer_padding > 0:
                try:
                    self.rect.inflate_ip(-outer_padding * 2, -outer_padding * 2)
                except Exception:
                    pass
            # however, aura should *never* enlarge the collision box beyond the
            # boss's normal dimensions/shrunken hitbox.  if we have a flag set by
            # the spawning code, restore the rect based on width/height (with
            # shrink applied there too) so the aura is purely visual.
            if getattr(self, "_shrink_hitbox", False):
                try:
                    scale = getattr(self, "_hitbox_scale", 0.5)
                    w = int(self.width * scale)
                    h = int(self.height * scale)
                    self.rect = pygame.Rect(0, 0, w, h)
                    self.rect.center = (int(self.x), int(self.y))
                except Exception:
                    pass
        except Exception:
            pass

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
            # For bosses, remove the 'boss_' prefix.  The horde-specific boss has
            # a slightly different naming convention so that its asset can be
            # kept separate from the final boss sprite.
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
            # Fallback to drawing; limbo bosses need special treatment when scaled
            if self.enemy_type in ("boss_limbo", "boss_limbo_horde"):
                # use different colours so the two can be distinguished if both
                # appear in debug screens without assets
                color = (
                    (150, 0, 150) if self.enemy_type == "boss_limbo" else (200, 50, 200)
                )
                try:
                    self.image.fill((0, 0, 0, 0))
                    pygame.draw.ellipse(
                        self.image,
                        color,
                        (0, 0, self.width, self.height),
                    )
                except Exception:
                    # if anything goes wrong, fall back to generic demon art
                    self.draw_demon()
            else:
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

        elif self.enemy_type == "winged":
            # Fast flying zigzag enemy (cyan)
            pygame.draw.ellipse(self.image, (0, 200, 200), (10, 15, 10, 12))
            pygame.draw.circle(self.image, (100, 255, 255), (15, 8), 5)
            # pointy wings
            pygame.draw.polygon(self.image, (150, 225, 225), [(2, 12), (0, 8), (1, 16)])
            pygame.draw.polygon(
                self.image, (150, 225, 225), [(28, 12), (30, 8), (29, 16)]
            )
            # Eyes
            pygame.draw.circle(self.image, (0, 0, 0), (13, 6), 1)
            pygame.draw.circle(self.image, (0, 0, 0), (17, 6), 1)

        elif self.enemy_type == "crusader":
            # Huge grey crusader (default art mimics a heavily-armoured giant).
            pygame.draw.ellipse(self.image, (100, 100, 100), (5, 10, 20, 25))
            pygame.draw.circle(self.image, (80, 80, 80), (15, 5), 8)
            # Eyes (yellow to stand out)
            pygame.draw.circle(self.image, (255, 255, 0), (12, 3), 1)
            pygame.draw.circle(self.image, (255, 255, 0), (18, 3), 1)
            # Simple cross or helmet crest
            pygame.draw.line(self.image, (200, 200, 200), (15, 0), (15, 10), 2)
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
            # Advance walking animation frame for animated enemy types
            _is_inquisitor = self.enemy_type == "boss_inquisitor" or (
                self.enemy_type == "normal"
                and getattr(self, "appearance", None) == "inquisitor"
            )
            if (
                self.enemy_type
                in ("giant", "custode", "mage", "normal", "strong", "shielded")
                or _is_inquisitor
            ):
                self._anim_timer = getattr(self, "_anim_timer", 0) + 1
                if self._anim_timer >= 8:
                    self._anim_timer = 0
                    self._anim_frame = (getattr(self, "_anim_frame", 0) + 1) % 8
            # handle crusader invulnerability cycling (3s vulnerable / 3s immune)
            if self.enemy_type == "crusader":
                # _vuln_timer initialized in __init__
                self._vuln_timer -= 1
                if self._vuln_timer <= 0:
                    self.invulnerable = not self.invulnerable
                    self._vuln_timer = 180
                    # little shake whenever the state flips so player gets a cue
                    self.shake_timer = 10
            # Custom movement for the Limbo horde boss: it should never chase the
            # player, instead parking itself in the upper half of the play area and
            # oscillating.  The speed for this type is slightly higher than the
            # normal final boss; it comes from ENEMY_BASE_SPEEDS.
            if self.enemy_type == "boss_limbo_horde" and game is not None:
                # target a spot well above the centre of the screen (upper half)
                target_y = game.height * 0.25
                if not hasattr(self, "horde_entrance_complete"):
                    # initial entrance: descend from off‑screen until we reach the
                    # target altitude.  We also slowly drift toward the horizontal
                    # centre while descending.
                    if self.y < target_y:
                        self.y += self.speed / 60
                        self.x += (game.width / 2 - self.x) * 0.01
                    else:
                        self.horde_entrance_complete = True
                        # initialize float parameters for the subsequent phase
                        self.float_center_x = self.x
                        self.float_amplitude = game.width * 0.2
                        self.float_speed = 0.02
                        self.float_time = 0
                else:
                    # once entrance is complete, float/oscillate in place
                    self.float_time += self.float_speed
                    # horizontal sine-wave drift
                    self.x = (
                        self.float_center_x
                        + math.sin(self.float_time) * self.float_amplitude
                    )
                    # small vertical bobbing so it never sits perfectly still
                    self.y = target_y + math.sin(self.float_time * 1.5) * 10
                    # enforce bounds: stay in upper half and within walls
                    self.x = max(50, min(game.width - 50, self.x))
                    self.y = min(self.y, game.height / 2)
                # movement handled; fall through to the remainder of update
                # (shooting and special attack code should still run)
                pass

            # Special behavior for the *final* boss in certain stages (Prologo or Limbo Final).
            # Boss_big should not be treated here otherwise it prevents the custom
            # Limbo hover movement that lives in the normal/else branch.  Only
            # final bosses (boss_final in Prologo, boss_limbo in Limbo Final) get
            # the regeneration/entrance aura logic.
            if (
                game
                and self.enemy_type in ["boss_final", "boss_limbo"]
                and game.selected_stage in ("prologo", "limbo_final")
            ):
                # If immortal (regenerating) - only for the stage's final boss
                if (
                    game.prologo_final_boss_immortal
                    and self.enemy_type == "boss_final"
                    and game.selected_stage == "prologo"
                ) or (
                    getattr(game, "limbo_final_boss_immortal", False)
                    and self.enemy_type == "boss_limbo"
                    and game.selected_stage == "limbo_final"
                ):
                    # Once the beam fires, freeze Satan in place
                    if not getattr(game, "limbo_final_lightning_strike", False):
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
                    # slower pulsing
                    self.shine_phase += 0.06
                    pulse: int = int((math.sin(self.shine_phase) + 1) / 2 * 150) + 20

                    # Build aura behind the boss so the sprite silhouette remains
                    # visible and the glow radiates outward.
                    try:
                        self._apply_aura(pulse)
                    except Exception:
                        pass

                    # additionally, during immortal phase we want a bright
                    # additive overlay that covers the boss silhouette itself.
                    if game and (
                        (
                            getattr(game, "prologo_final_boss_immortal", False)
                            and self.enemy_type == "boss_final"
                        )
                        or (
                            getattr(game, "limbo_final_boss_immortal", False)
                            and self.enemy_type == "boss_limbo"
                        )
                    ):
                        try:
                            top_overlay = pygame.Surface(
                                (self.width, self.height), pygame.SRCALPHA
                            )
                            center_pos = (self.width // 2, self.height // 2)
                            radius = max(self.width, self.height) // 2
                            pygame.draw.circle(
                                top_overlay, (255, 255, 255, pulse), center_pos, radius
                            )
                            # self.image is the aura surface (larger than the boss
                            # sprite); blit the overlay centered on it so the white
                            # glow lands exactly on the boss silhouette.
                            img_w = self.image.get_width()
                            img_h = self.image.get_height()
                            overlay_x = (img_w - self.width) // 2
                            overlay_y = (img_h - self.height) // 2
                            self.image.blit(
                                top_overlay,
                                (overlay_x, overlay_y),
                                special_flags=pygame.BLEND_ADD,
                            )
                        except Exception:
                            pass
                else:
                    # Prologue boss entrance: walk down from top to position below cathedral
                    # This block handles both the descent and the special pulsing aura that
                    # starts once the boss has traveled at least half of the path. The aura
                    # should continue even after the boss has reached its final position.
                    target_y = (
                        140  # Position below cathedral (cathedral ends around y=120)
                    )

                    # handle vertical descent until we arrive at target_y
                    if not hasattr(self, "entrance_complete"):
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

                    # aura logic: the final boss should pulse from the very start of
                    # the descent instead of waiting until halfway.  We rebuild the
                    # image each frame so the glow doesn't stack.  This applies to
                    # both the Prologo final boss and the Limbo Final boss so they
                    # share the same dramatic entrance.
                    if self.enemy_type in ("boss_final", "boss_limbo"):
                        # always rebuild from the base image so pulses don't accumulate
                        if getattr(self, "base_image", None) is not None:
                            self.image = self.base_image.copy()
                        else:
                            self.image = pygame.Surface(
                                (self.width, self.height), pygame.SRCALPHA
                            )
                            self.draw_enemy()

                        self.shining = True
                        self.shine_phase += 0.06
                        pulse: int = (
                            int((math.sin(self.shine_phase) + 1) / 2 * 150) + 20
                        )

                        try:
                            self._apply_aura(pulse)
                        except Exception:
                            pass
                    # once entrance is complete, resume the normal floating behaviour
                    if hasattr(self, "entrance_complete") and self.entrance_complete:
                        # Normal floating behavior after entrance
                        # Stay at target height, float horizontally
                        self.y = target_y  # Keep at target position

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
                if self.enemy_type == "boss_limbo_horde":
                    # movement already handled above; do not chase the player
                    pass
                elif self.enemy_type == "winged":
                    # Winged flyers dart toward the player with a noisy zigzag added
                    if not hasattr(self, "zig_time"):
                        self.zig_time = 0.0
                        self.zig_amplitude = random.uniform(3, 7)
                        self.zig_direction = random.choice([-1, 1])
                        self.zig_change_timer = random.randint(10, 30)
                    # advance zig phase
                    self.zig_time += 0.3
                    # occasionally randomize the zig parameters
                    self.zig_change_timer -= 1
                    if self.zig_change_timer <= 0:
                        self.zig_change_timer = random.randint(10, 30)
                        self.zig_amplitude = random.uniform(3, 7)
                        self.zig_direction = random.choice([-1, 1])
                    # compute base vector toward player if available
                    if game and hasattr(game, "player"):
                        dx = game.player.x - self.x
                        dy = game.player.y - self.y
                        dist = math.hypot(dx, dy)
                        if dist > 1:
                            dx /= dist
                            dy /= dist
                        else:
                            dx = dy = 0
                    else:
                        dx = 0
                        dy = 1  # fall back to downward motion
                    # add small lateral zig offset
                    offset_x = (
                        math.sin(self.zig_time)
                        * self.zig_amplitude
                        * 0.1
                        * self.zig_direction
                    )
                    offset_y = (
                        math.cos(self.zig_time)
                        * self.zig_amplitude
                        * 0.1
                        * self.zig_direction
                    )
                    self.x += (dx + offset_x) * self.speed / 60
                    self.y += (dy + offset_y) * self.speed / 60
                    # keep within arena walls when available
                    if game:
                        try:
                            self.x = game.clamp_to_walls(self.x)
                        except Exception:
                            pass
                    # movement handled; skip other behaviour
                    pass
                elif self.enemy_type == "normal" and game is not None:
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
                            if getattr(self, "appearance", None) == "inquisitor":
                                self._facing_right = dx > 0
                                self._facing_down = dy > 0
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
                    and (
                        getattr(game, "is_limbo_stage", lambda: False)()
                        or getattr(game, "selected_stage", "") == "prologo"
                    )
                ):
                    # Boss Big behavior for Limbo *and* Prologo; during prologo we
                    # want the same horizontal-hover pattern but positioned much
                    # higher, never chasing the player.
                    stage = getattr(game, "selected_stage", "")
                    top_margin = 30
                    # In limbo we stop in the mid-screen, but in prologo we hold
                    # near the ceiling so the boss never approaches the player.
                    if stage == "prologo":
                        bottom_limit = top_margin + 120  # small vertical window
                    else:
                        bottom_limit = int(game.height / 2) - 40  # vertical stop line
                    left_limit = 50
                    right_limit = game.width - 50

                    # Initialize state on first update
                    if not hasattr(self, "limbo_phase"):
                        self.limbo_phase = "descend"
                        self.entrance_start_y = float(self.y)
                        if stage == "prologo":
                            # simply hover a bit below the top margin
                            self.limbo_target_y = float(top_margin + 20)
                        else:
                            self.limbo_target_y = float(
                                max(top_margin + 10, bottom_limit - 150)
                            )
                        self.hover_center_x = float(self.x)
                        self.hover_phase = random.uniform(0.0, math.pi * 2)
                        # amplitude/frequency tuning varies only by limbo stage
                        base_amp = 120.0
                        if stage == "limbo_2":
                            base_amp = 160.0
                        elif stage in ("limbo_3", "limbo_final"):
                            base_amp = 200.0
                        max_amp = max(10.0, (right_limit - left_limit) / 2.0 - 6.0)
                        self.hover_amplitude = min(base_amp, max_amp)
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
                        self._facing_right = dx > 0
                        self._facing_down = dy > 0
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
                        self._facing_right = dx > 0
                        self._facing_down = dy > 0
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
                        # Track facing direction for sprite flip (giant only)
                        if self.enemy_type == "giant":
                            self._facing_right = dx > 0
                            self._facing_down = dy > 0

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

            if getattr(self, "_shrink_hitbox", False):
                scale = getattr(self, "_hitbox_scale", 0.5)
                w = int(self.width * scale)
                h = int(self.height * scale)
                self.rect = pygame.Rect(0, 0, w, h)
                self.rect.center = (int(self.x), int(self.y))
            else:
                self.rect.center = (self.x, self.y)

            # Handle shooting for enemies that shoot
            if game and self.shoot_cooldown is not None:
                self.shoot_cooldown -= 1
                if self.shoot_cooldown <= 0:
                    self.shoot_at_player(player, game)

            # Handle boss special attacks
            # include the horde variant so its triple-shot code runs
            if game and self.enemy_type in [
                "boss_big",
                "boss_final",
                "boss_limbo",
                "boss_limbo_horde",
            ]:
                # Update boss timers
                if self.pattern_timer is not None:
                    self.pattern_timer -= 1
                if (
                    hasattr(self, "big_shot_cooldown")
                    and self.big_shot_cooldown is not None
                ):
                    self.big_shot_cooldown -= 1
                # decrement area timer if present
                if (
                    hasattr(self, "area_attack_cooldown")
                    and self.area_attack_cooldown is not None
                ):
                    self.area_attack_cooldown -= 1

                # handle any pending delayed area explosion before other patterns
                if getattr(self, "pending_area", None) is not None:
                    self.pending_area["timer"] -= 1
                    if self.pending_area["timer"] <= 0:
                        tx = self.pending_area["x"]
                        ty = self.pending_area["y"]
                        game.skullboom_explosions.append(
                            {
                                "x": tx,
                                "y": ty,
                                # actual explosion is larger as well
                                "radius": 50,
                                "max_radius": 50,
                                "timer": 15,
                                "max_timer": 15,
                                "color": (255, 100, 100),  # reddish explosion
                            }
                        )
                        # decide damage by checking circle-rect intersection
                        # using player's current rect (fall back to center/radius)
                        try:
                            # assume player has `width`/`height` and `x`,`y` at center
                            half_w = player.width / 2
                            half_h = player.height / 2
                            left = player.x - half_w
                            right = player.x + half_w
                            top = player.y - half_h
                            bottom = player.y + half_h
                            # nearest point from explosion center to rect using clamp
                            nearest_x = max(left, min(tx, right))
                            nearest_y = max(top, min(ty, bottom))
                            ddx = tx - nearest_x
                            ddy = ty - nearest_y
                            exp_r = 50
                            inside = ddx * ddx + ddy * ddy <= exp_r * exp_r
                        except Exception:
                            # fallback to old center-based check
                            dx = player.x - tx
                            dy = player.y - ty
                            inside = dx * dx + dy * dy <= 30 * 30
                        if inside:
                            try:
                                player.take_damage(25)
                            except Exception:
                                pass
                        logger.debug(
                            "Limbo boss area attack exploded at %.1f,%.1f",
                            tx,
                            ty,
                        )
                        self.pending_area = None

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
                elif self.enemy_type == "boss_limbo":
                    # Limbo final boss behaves much like the Prologo final boss
                    # but also periodically fires the inquisitor triple spread.
                    if self.pattern_timer <= 0:
                        # Instead of a full radial spread, Limbo boss fires a single
                        # large sphere aimed at the player.  This keeps the attack
                        # distinct from the Prologo final boss and slows its rate.
                        dx = player.x - self.x
                        dy = player.y - self.y
                        distance: float = math.sqrt(dx * dx + dy * dy)
                        if distance > 0:
                            # increase speed again for an even more threatening orb
                            speed = 340
                            vel_x = (dx / distance) * speed
                            vel_y = (dy / distance) * speed
                        else:
                            vel_x = 0
                            vel_y = 340
                        big_proj = Projectile(
                            self.x,
                            self.y,
                            vel_x,
                            vel_y,
                            damage=20,
                            # slightly smaller now (was 30)
                            radius=25,
                            is_enemy_projectile=True,
                        )
                        game.enemy_projectiles.add(big_proj)
                        # fixed 3-second cooldown between big spheres
                        try:
                            self.pattern_timer = int(3 * game.fps)
                        except Exception:
                            # fallback if game or fps missing
                            self.pattern_timer = 180
                    elif self.big_shot_cooldown <= 0:
                        # Inquisitor-style triple spread with slow effect
                        dx = player.x - self.x
                        dy = player.y - self.y
                        distance: float = math.sqrt(dx * dx + dy * dy)
                        if distance > 0:
                            # slightly boost speed versus standard inquisitor speed
                            speed = 300
                            base_angle: float = math.atan2(dy, dx)
                            offset = 0.25 + math.radians(1)
                            angles = [
                                base_angle - offset,
                                base_angle,
                                base_angle + offset,
                            ]
                            for ang in angles:
                                vel_x: float = math.cos(ang) * speed
                                vel_y: float = math.sin(ang) * speed
                                proj: Projectile = Projectile(
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
                                # 1.5 seconds of slow (was 3s / 180 frames)
                                proj.slow_duration = int(1.5 * getattr(game, "fps", 60))
                                proj.slow_factor = 0.4
                                game.enemy_projectiles.add(proj)
                        self.big_shot_cooldown: int = random.randint(220, 320)
                    elif (
                        getattr(self, "area_attack_cooldown", None) is not None
                        and self.area_attack_cooldown <= 0
                    ):
                        # schedule delayed explosion at current player location
                        tx = player.x
                        ty = player.y
                        delay = int(1.0 * game.fps)  # one second delay
                        self.pending_area = {"x": tx, "y": ty, "timer": delay}
                        # indicator ring during delay (purple color)
                        game.skullboom_explosions.append(
                            {
                                "x": tx,
                                "y": ty,
                                # increase indicator size by 10px
                                "radius": 50,
                                "max_radius": 50,
                                "timer": delay,
                                "max_timer": delay,
                                "color": (100, 0, 100),  # darker purple indicator
                                "indicator": True,  # fixed-radius marker
                            }
                        )
                        logger.debug(
                            "Limbo boss scheduled area attack at %.1f,%.1f (delay %d)",
                            tx,
                            ty,
                            delay,
                        )
                        # reset cooldown immediately so it won't retrigger
                        self.area_attack_cooldown = random.randint(180, 300)
                elif self.enemy_type == "boss_limbo_horde":
                    # Horde boss uses a green-tinted triple spread (no area attack)
                    if self.big_shot_cooldown <= 0:
                        dx = player.x - self.x
                        dy = player.y - self.y
                        distance: float = math.sqrt(dx * dx + dy * dy)
                        if distance > 0:
                            speed = 300
                            base_angle: float = math.atan2(dy, dx)
                            offset = 0.25 + math.radians(1)
                            angles = [
                                base_angle - offset,
                                base_angle,
                                base_angle + offset,
                            ]
                            for ang in angles:
                                vel_x: float = math.cos(ang) * speed
                                vel_y: float = math.sin(ang) * speed
                                proj: Projectile = Projectile(
                                    self.x,
                                    self.y,
                                    vel_x,
                                    vel_y,
                                    damage=12,
                                    radius=8,  # slightly larger than regular inquisitor shots
                                    is_enemy_projectile=True,
                                    appearance="inquisitor_horde",
                                )
                                proj.effect = "slow"
                                proj.slow_duration = int(1.5 * getattr(game, "fps", 60))
                                proj.slow_factor = 0.4
                                game.enemy_projectiles.add(proj)
                        self.big_shot_cooldown: int = random.randint(220, 320)
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
                proj.slow_duration = int(1.5 * getattr(game, "fps", 60))
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
                    proj.slow_duration = int(1.5 * getattr(game, "fps", 60))
                    proj.slow_factor = 0.4
                    game.enemy_projectiles.add(proj)
                else:
                    # 3-shot spread (widened by 2° total, previously ±0.25 rad)
                    # 0.25 rad ≈ 14.3°; add 1° (≈0.01745 rad) to each side to get ≈15.3° offsets.
                    offset = 0.25 + math.radians(1)
                    angles = [base_angle - offset, base_angle, base_angle + offset]
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
                        proj.slow_duration = int(1.5 * getattr(game, "fps", 60))
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
        # Crusader cycles between vulnerable and invulnerable.  If the current
        # state is invulnerable we quietly drop the damage.
        if getattr(self, "enemy_type", "") == "crusader" and getattr(
            self, "invulnerable", False
        ):
            try:
                logger.debug("Crusader.take_damage ignored because invulnerable")
            except Exception:
                pass
            return

        # Centralized safeguard: if this is the Prologo or Limbo Final boss and
        # it is currently in the immortal/regeneration phase, ignore incoming damage.
        try:
            from src.game import CURRENT_GAME

            if CURRENT_GAME is not None:
                if (
                    getattr(self, "enemy_type", "") == "boss_final"
                    and getattr(CURRENT_GAME, "selected_stage", None) == "prologo"
                    and getattr(CURRENT_GAME, "prologo_final_boss_immortal", False)
                ) or (
                    getattr(self, "enemy_type", "") == "boss_limbo"
                    and getattr(CURRENT_GAME, "selected_stage", None) == "limbo_final"
                    and getattr(CURRENT_GAME, "limbo_final_boss_immortal", False)
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
                CURRENT_GAME is not None
                and getattr(self, "health", 1) <= 0
                and getattr(self, "enemy_type", "").startswith("boss_")
            ):
                # schedule reinforcements for medium bosses
                if getattr(self, "enemy_type", "") == "boss_medium":
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
                # spawn health drop for any qualifying boss once
                if self.enemy_type in ("boss_medium", "boss_big", "boss_inquisitor"):
                    if not getattr(self, "health_drop_spawned", False):
                        try:
                            import random

                            heal_amt = random.randint(10, 20)
                            try:
                                CURRENT_GAME.spawn_health_drop(self.x, self.y, heal_amt)
                                self.health_drop_spawned = True
                            except Exception:
                                pass
                        except Exception:
                            pass
        except Exception:
            pass
        # If this is the Prologo final boss and the damage reduced it to <=10% of
        # max health, begin the immortal/regeneration phase and clamp HP to 10%.
        try:
            from src.game import CURRENT_GAME

            if CURRENT_GAME is not None:
                # prologo boss check
                if (
                    getattr(self, "enemy_type", "") == "boss_final"
                    and getattr(CURRENT_GAME, "selected_stage", None) == "prologo"
                ):
                    # Only trigger the phase when not already immortal
                    if not getattr(CURRENT_GAME, "prologo_final_boss_immortal", False):
                        try:
                            threshold = getattr(self, "max_health", 0) * 0.1
                            if getattr(self, "health", 0) <= threshold:
                                CURRENT_GAME.prologo_final_boss_immortal = True
                                self.health = int(threshold)
                        except Exception:
                            pass
                # limbo_final boss check
                if getattr(self, "enemy_type", "") == "boss_limbo":
                    if not getattr(CURRENT_GAME, "limbo_final_boss_immortal", False):
                        try:
                            threshold = getattr(self, "max_health", 0) * 0.1
                            if getattr(self, "health", 0) <= threshold:
                                CURRENT_GAME.limbo_final_boss_immortal = True
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
            # When the hitbox is shrunken (e.g. boss_limbo with aura), self.rect
            # no longer matches self.image size.  Center the image on (self.x, self.y)
            # directly so the visual doesn't shift relative to the logical position.
            if getattr(self, "_shrink_hitbox", False):
                iw = self.image.get_width()
                ih = self.image.get_height()
                draw_x: int | Any = int(self.x) - iw // 2 + shake_x
                draw_y: int | Any = int(self.y) - ih // 2 + shake_y
            else:
                draw_x = self.rect.x + shake_x
                draw_y = self.rect.y + shake_y

            if self.shake_timer > 0:
                draw_x += random.randint(-1, 1)
                draw_y += random.randint(-1, 1)

            # Walking animation: bob vertically + slight horizontal sway
            _is_inquisitor = self.enemy_type == "boss_inquisitor" or (
                self.enemy_type == "normal"
                and getattr(self, "appearance", None) == "inquisitor"
            )
            if (
                self.enemy_type
                in ("giant", "custode", "mage", "normal", "strong", "shielded")
                or _is_inquisitor
            ):
                anim_frame = getattr(self, "_anim_frame", 0)
                # Vertical bob: same pattern as player (frames 1 and 3 shift by ±2px)
                bob_cycle = anim_frame % 4
                if bob_cycle == 1:
                    draw_y -= 2
                elif bob_cycle == 3:
                    draw_y += 2
                # Horizontal sway: left on frames 0-3, right on frames 4-7
                if anim_frame < 4:
                    draw_x -= 1
                else:
                    draw_x += 1

            # draw aura behind image if crusader is invulnerable
            if self.enemy_type == "crusader" and getattr(self, "invulnerable", False):
                # filled translucent light-blue circle slightly larger than sprite
                cx = int(self.x if hasattr(self, "x") else self.rect.centerx)
                cy = int(self.y if hasattr(self, "y") else self.rect.centery)
                r = max(self.width, self.height) // 2 + 6
                try:
                    # create temporary surface for alpha
                    aura_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                    # light blue with some transparency
                    pygame.draw.circle(aura_surf, (100, 150, 255, 100), (r, r), r)
                    screen.blit(aura_surf, (cx - r + shake_x, cy - r + shake_y))
                except Exception:
                    pass

            # Flip giant/custode sprite based on movement direction + walking oscillation
            blit_image = self.image
            if self.enemy_type in ("giant", "custode"):
                anim_frame = getattr(self, "_anim_frame", 0)
                # Oscillate flip_x every half-cycle (4 frames) to simulate stride
                stride_flip = anim_frame >= 4
                facing_right = getattr(self, "_facing_right", True)
                flip_x = facing_right != stride_flip  # XOR: inverts on each stride
                flip_y = not getattr(self, "_facing_down", True)
                if flip_x or flip_y:
                    try:
                        blit_image = pygame.transform.flip(self.image, flip_x, flip_y)
                    except Exception:
                        blit_image = self.image

            screen.blit(blit_image, (draw_x, draw_y))

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
            # Crusaders never show a shield bar, so exclude them explicitly
            if self.enemy_type != "crusader" and getattr(self, "shield_hp", 0) > 0:
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
