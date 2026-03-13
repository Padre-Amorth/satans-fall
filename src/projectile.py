import importlib
import math
import random
from typing import TYPE_CHECKING, Any, Optional

from pygame.surface import Surface

if TYPE_CHECKING:
    from pygame import Rect, Surface  # type: ignore
    from pygame.sprite import Sprite as SpriteType  # type: ignore

    from src.systems.projectile_manager import ProjectileManager
else:
    Rect = Any
    Surface = Any
    SpriteType = Any

from types import ModuleType

try:
    pygame: ModuleType = importlib.import_module("pygame")
except (AttributeError, TypeError, ValueError, KeyError):
    pygame: ModuleType = importlib.import_module("pygame_ce")  # type: ignore

# Explicit runtime base class variable so mypy does not treat it as a type alias
# assigned multiple ways. Use `BaseSprite` both as a runtime base and avoid
# reassigning names used for TYPE_CHECKING.
BaseSprite: type
try:
    BaseSprite = pygame.sprite.Sprite  # type: ignore
except (AttributeError, TypeError, ValueError, KeyError):
    BaseSprite = object


class Projectile(BaseSprite):
    def __init__(
        self,
        x: float,
        y: float,
        vel_x: float,
        vel_y: float,
        damage: int = 15,
        radius: int = 5,
        is_enemy_projectile: bool = False,
        weapon_type: Optional[str] = None,
        source: Optional[str] = None,
        appearance: Optional[str] = None,
        weapon_level: int = 0,
    ) -> None:
        super().__init__()
        self.x: Any = x
        self.y: Any = y
        self.vel_x: Any = vel_x
        self.vel_y: Any = vel_y
        self.damage: int = damage
        # radius may be modified during flight for special weapons
        self.radius: int = radius
        # remember original spawn point for distance-based effects
        self.spawn_x: float = x
        self.spawn_y: float = y
        self.is_enemy_projectile: bool = is_enemy_projectile
        self.weapon_type = weapon_type  # 'spear', 'shotgun', or None for regular
        self.source = source  # 'orbital' for orbital projectiles
        self.weapon_level: int = weapon_level  # For Final Form (Lv7) glow effects
        # Default sentinel: if this is an enemy projectile and no appearance was
        # provided, use `"enemy_default"` so draw_projectile renders the expected
        # golden enemy projectile regardless of asset lookup.
        self.appearance = (
            appearance
            if appearance is not None
            else ("enemy_default" if is_enemy_projectile else None)
        )
        self._appearance_cached: Any | None = None
        self.pierce_all = False  # Default: projectiles don't pierce
        self.pierce_count = 0  # For limited piercing
        # Track ids of enemies already hit by this projectile to avoid multiple hits
        # when piercing through or overlapping across frames
        self._hit_ids: set[int] = set()
        # Prevent applying chain lightning effects multiple times per projectile
        self._chain_applied: bool = False
        # Rotation angle used for rolling visuals (degrees)
        self.rotation_angle: float = 0.0
        # Trail positions for rolling projectile (list of (x, y) tuples)
        self.trail: list[tuple[float, float]] = []
        self.manager: "ProjectileManager | None" = (
            None  # Optional ProjectileManager reference
        )

        # Create image
        self.image: Surface = pygame.Surface(
            (self.radius * 2, self.radius * 2), pygame.SRCALPHA
        )
        self.draw_projectile()
        self.rect: Rect | Any = self.image.get_rect(center=(self.x, self.y))

        # Invariants: transient state types and defaults
        assert isinstance(self._hit_ids, set), "Projectile._hit_ids must be a set"
        assert isinstance(
            self._chain_applied, bool
        ), "Projectile._chain_applied must be a bool"
        # By default a freshly-created projectile must not have chain applied
        assert (
            self._chain_applied is False
        ), "New projectile unexpectedly has _chain_applied=True"

    def reset(
        self,
        x: float,
        y: float,
        vel_x: float,
        vel_y: float,
        damage: int = 15,
        radius: int = 5,
        is_enemy_projectile: bool = False,
        weapon_type: Optional[str] = None,
        source: Optional[str] = None,
        appearance: Optional[str] = None,
        weapon_level: int = 0,
    ) -> None:
        """Reset an existing projectile instance for reuse from a pool."""
        self.x = x
        self.y = y
        self.vel_x = vel_x
        self.vel_y = vel_y
        self.damage = damage
        self.radius = radius
        # reset spawn point as well
        self.spawn_x = x
        self.spawn_y = y
        self.is_enemy_projectile = is_enemy_projectile
        self.weapon_type = weapon_type
        self.source = source
        self.weapon_level = weapon_level
        # Preserve enemy_default sentinel when reusing projectiles from pool
        self.appearance = (
            appearance
            if appearance is not None
            else ("enemy_default" if is_enemy_projectile else None)
        )
        self._appearance_cached = None
        self.pierce_all = False
        self.pierce_count = 0
        # Reset hit-tracking and chain flag when reusing projectile instances
        self._hit_ids = set()
        self._chain_applied = False
        # Reset rotation and trail for visual consistency when reusing projectiles
        self.rotation_angle = 0.0
        self.trail = []
        try:
            self.image = pygame.Surface(
                (self.radius * 2, self.radius * 2), pygame.SRCALPHA
            )
            self.draw_projectile()
            self.rect = self.image.get_rect(center=(self.x, self.y))
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        # Runtime invariants after reset: ensure transient state cleared and types preserved
        assert isinstance(self._hit_ids, set), "_hit_ids must be set after reset"
        assert self._hit_ids == set(), "_hit_ids must be empty after reset"
        assert isinstance(
            self._chain_applied, bool
        ), "_chain_applied must be bool after reset"
        assert self._chain_applied is False, "_chain_applied must be False after reset"

    def kill(self) -> None:
        """Override kill to inform manager for recycling."""
        try:
            super().kill()
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        mgr: Any | None = getattr(self, "manager", None)
        if mgr is not None:
            try:
                mgr.recycle(self)
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

    def _render_enemy_normal(self) -> None:
        """Render enemy_normal appearance: yellow ball."""
        self.image = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(
            self.image, (255, 200, 0), (self.radius, self.radius), self.radius
        )

    def _render_orbital(self) -> None:
        """Render orbital: light blue circles. Final Form (Lv7) has golden glow."""
        self.image = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)

        # Add Final Form glow at Lv7
        if getattr(self, "weapon_level", 0) >= 7:
            pygame.draw.circle(
                self.image,
                (255, 215, 0, 100),
                (self.radius, self.radius),
                self.radius + 2,
            )

        pygame.draw.circle(
            self.image, (102, 204, 255), (self.radius, self.radius), self.radius
        )
        pygame.draw.circle(
            self.image,
            (51, 170, 255),
            (self.radius, self.radius),
            self.radius - 1,
        )

    def _render_archer_segment(self) -> None:
        """Render archer_segment: white/azure segment."""
        w = max(2, self.radius * 2 + 2)
        h = max(2, int(self.radius * 0.4))
        self.image = pygame.Surface((w, h), pygame.SRCALPHA)
        color = (200, 255, 255)
        try:
            pygame.draw.line(self.image, color, (0, h // 2), (w, h // 2), h)
        except (AttributeError, TypeError, ValueError, KeyError):
            pygame.draw.rect(self.image, color, (0, 0, w, h))

    def _render_player_generic(self) -> None:
        """Render generic player projectile segment."""
        w = max(2, self.radius * 2)
        h = max(2, int(self.radius * 0.4))
        self.image = pygame.Surface((w, h), pygame.SRCALPHA)
        color = (255, 255, 255)
        try:
            pygame.draw.line(self.image, color, (0, h // 2), (w, h // 2), h)
        except (AttributeError, TypeError, ValueError, KeyError):
            pygame.draw.rect(self.image, color, (0, 0, w, h))

    def _render_spear(self) -> None:
        """Render spear projectile."""
        # Try external asset first
        try:
            from src.assets.manager import get_image

            asset = get_image(
                "spear.png",
                (
                    max(4, int(self.radius * 1.2)),
                    max(60, self.radius * 10),
                ),
            )
            if asset is not None:
                self.image = asset
                self.rect = self.image.get_rect(center=(self.x, self.y))
                return
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        # Fallback: procedural spear
        length: int = max(60, self.radius * 10)
        width: int = max(4, int(self.radius * 1.2))
        self.image = pygame.Surface((width, length), pygame.SRCALPHA)
        pygame.draw.rect(
            self.image,
            (217, 211, 183),
            (0, 0, width, length - self.radius * 2),
        )
        arrowhead_points: list[tuple[int, int]] = [
            (width // 2, 0),
            (0, self.radius * 2),
            (width, self.radius * 2),
        ]
        pygame.draw.polygon(self.image, (255, 220, 178), arrowhead_points)
        pygame.draw.polygon(self.image, (207, 162, 111), arrowhead_points, 1)

    def _render_shotgun(self) -> None:
        """Render shotgun pellet. Final Form (Lv7) has white-yellow glow."""
        self.image = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        cx, cy = self.radius, self.radius

        # Add Final Form glow at Lv7
        if getattr(self, "weapon_level", 0) >= 7:
            pygame.draw.circle(
                self.image, (255, 255, 150, 80), (cx, cy), self.radius + 3
            )

        w = max(1, int(self.radius * 1.25))
        h = max(1, int(self.radius * 2.0))
        rect = (cx - w // 2, cy - h // 2, w, h)
        main_col = (110, 85, 0)
        inner_col = (200, 150, 40)
        outline_col = (60, 45, 0)
        try:
            pygame.draw.ellipse(self.image, main_col, rect)
            inner_rect = (
                rect[0] + max(1, int(w * 0.12)),
                rect[1] + max(1, int(h * 0.12)),
                max(1, int(w * 0.76)),
                max(1, int(h * 0.76)),
            )
            pygame.draw.ellipse(self.image, inner_col, inner_rect)
            pygame.draw.ellipse(self.image, outline_col, rect, 1)
        except (AttributeError, TypeError, ValueError, KeyError):
            try:
                pygame.draw.circle(self.image, (255, 200, 0), (cx, cy), self.radius)
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

    def _render_skullboom(self) -> None:
        """Render SkullBoom: skull with fuse and fire particles."""
        self.image = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        center_x, center_y = self.radius, self.radius
        skull_color = (240, 240, 240)
        outline_color = (200, 200, 200)

        # Main skull oval
        pygame.draw.ellipse(
            self.image,
            skull_color,
            (
                center_x - self.radius * 0.65,
                center_y - self.radius * 0.75,
                self.radius * 1.3,
                self.radius * 1.5,
            ),
        )

        # Eye sockets
        eye_y: float = center_y - self.radius * 0.25
        eye_width: float = self.radius * 0.25
        eye_height: float = self.radius * 0.22
        pygame.draw.ellipse(
            self.image,
            (0, 0, 0),
            (center_x - self.radius * 0.35, eye_y, eye_width, eye_height),
        )
        pygame.draw.ellipse(
            self.image,
            (0, 0, 0),
            (center_x + self.radius * 0.10, eye_y, eye_width, eye_height),
        )

        # Nose hole (triangle)
        nose_points = [
            (center_x, center_y + self.radius * 0.15),
            (center_x - self.radius * 0.12, center_y + self.radius * 0.40),
            (center_x + self.radius * 0.12, center_y + self.radius * 0.40),
        ]
        pygame.draw.polygon(self.image, (0, 0, 0), nose_points)

        # Jaw/teeth
        jaw_y: float = center_y + self.radius * 0.5
        pygame.draw.rect(
            self.image,
            skull_color,
            (
                center_x - self.radius * 0.3,
                jaw_y,
                self.radius * 0.6,
                self.radius * 0.28,
            ),
        )

        # Teeth lines
        for i in range(1, 4):
            tooth_x: float = center_x - self.radius * 0.3 + (i * self.radius * 0.6 / 4)
            pygame.draw.line(
                self.image,
                (0, 0, 0),
                (tooth_x, jaw_y),
                (tooth_x, jaw_y + self.radius * 0.28),
                1,
            )

        # Outline the skull
        pygame.draw.ellipse(
            self.image,
            outline_color,
            (
                center_x - self.radius * 0.65,
                center_y - self.radius * 0.75,
                self.radius * 1.3,
                self.radius * 1.5,
            ),
            1,
        )

        # Fuse (zigzag line)
        fuse_start_y: float = center_y - self.radius * 0.85
        fuse_height: float = self.radius * 0.42
        fuse_points = []
        for i in range(8):
            x: float = center_x + (i - 3.5) * (self.radius * 0.09)
            y: float = fuse_start_y - i * (fuse_height / 7)
            if i % 2 == 0:
                x += self.radius * 0.045
            else:
                x -= self.radius * 0.045
            fuse_points.append((x, y))

        if len(fuse_points) > 1:
            pygame.draw.lines(self.image, (139, 69, 19), False, fuse_points, 2)

        # Fire particles at fuse end
        if fuse_points:
            fire_x, fire_y = fuse_points[-1]
            fire_colors: list[tuple[int, int, int]] = [
                (255, 100, 0),
                (255, 150, 0),
                (255, 200, 0),
                (255, 120, 0),
                (255, 180, 0),
            ]
            for i in range(5):
                offset_x: float = (i - 2) * self.radius * 0.06 + (
                    i % 3 - 1
                ) * self.radius * 0.02
                offset_y: float = (
                    -self.radius * 0.08
                    + (i % 2) * self.radius * 0.04
                    + (i // 2) * self.radius * 0.02
                )
                particle_size: int = max(1, int(self.radius * 0.10))
                pygame.draw.circle(
                    self.image,
                    fire_colors[i % len(fire_colors)],
                    (int(fire_x + offset_x), int(fire_y + offset_y)),
                    particle_size,
                )

    def _render_demon_strike(self) -> None:
        """Render DemonStrike: black bowling ball with scrolling holes."""
        size = max(12, self.radius * 2 + 12)
        self.image = pygame.Surface((size, size), pygame.SRCALPHA)
        cx, cy = size // 2, size // 2
        pygame.draw.circle(self.image, (0, 0, 0), (cx, cy), self.radius + 6)

        hole_r = max(1, int(self.radius * 0.15))
        base_offsets = [
            (-int(self.radius * 0.4), -int(self.radius * 0.1)),
            (0, -int(self.radius * 0.3)),
            (int(self.radius * 0.4), -int(self.radius * 0.1)),
        ]
        angle = getattr(self, "rotation_angle", 0.0)
        for i, (ox, oy) in enumerate(base_offsets):
            scroll_y = math.sin(math.radians(angle + i * 120)) * self.radius * 0.3
            pygame.draw.circle(
                self.image,
                (255, 255, 255),
                (cx + ox, cy + oy + int(scroll_y)),
                hole_r,
            )
        self.rect = self.image.get_rect(center=(self.x, self.y))

    def _render_appearance_based(self) -> None:
        """Render projectile by appearance attribute."""
        appearance = getattr(self, "appearance", None)

        if appearance == "tenebrae":
            self._render_tenebrae()
        elif appearance == "beast":
            self._render_beast()
        elif appearance == "storm_statue":
            self._render_storm_statue()
        elif appearance == "fire_statue":
            self._render_fire_statue()
        elif appearance == "ice_statue":
            self._render_ice_statue()
        elif appearance == "inquisitor":
            self._render_inquisitor()
        elif appearance == "inquisitor_horde":
            self._render_inquisitor_horde()
        elif appearance == "enemy_default" or appearance is None:
            self._render_fallback()
        else:
            self._render_fallback()

    def _render_tenebrae(self) -> None:
        """Render tenebrae arc."""
        try:
            from src.assets.manager import get_image

            asset = get_image("tenebrae.png", (self.radius * 3, self.radius * 2))
            if asset is None:
                asset = get_image(
                    "weapon_tenebrae.png",
                    (self.radius * 3, self.radius * 2),
                )
            if asset is not None:
                self.image = asset
                self.rect = self.image.get_rect(center=(self.x, self.y))
                return
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        width = max(1, int(self.radius * 4))
        height = max(1, int(self.radius * 2))
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        try:
            pygame.draw.arc(
                self.image,
                (100, 0, 100),
                (0, 0, width, height),
                0,
                math.pi,
                max(1, int(self.radius / 2)),
            )
        except (AttributeError, TypeError, ValueError, KeyError):
            pygame.draw.ellipse(self.image, (100, 0, 100), (0, 0, width, height))
        self.rect = self.image.get_rect(center=(self.x, self.y))

    def _render_beast(self) -> None:
        """Render beast projectile: red '6' text. Final Form (Lv7) adds golden glow."""
        self.image = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        weapon_level = getattr(self, "weapon_level", 0)

        # Add golden glow at Lv7 Final Form
        if weapon_level >= 7:
            pygame.draw.circle(
                self.image,
                (255, 200, 50, 100),
                (self.radius, self.radius),
                self.radius + 3,
            )

        try:
            font = pygame.font.Font(None, max(8, int(self.radius * 2)))
            txt = font.render("6", True, (255, 0, 0))
            txt_rect = txt.get_rect(center=(self.radius, self.radius))
            self.image.blit(txt, txt_rect)
        except (AttributeError, TypeError, ValueError, KeyError):
            pygame.draw.circle(
                self.image,
                (255, 0, 0),
                (self.radius, self.radius),
                self.radius,
            )

    def _render_statue(
        self, outer_color: tuple, inner_color: tuple, glow_color: tuple
    ) -> None:
        """Helper to render statue projectiles with glow."""
        self.image = pygame.Surface(
            (self.radius * 2 + 6, self.radius * 2 + 6), pygame.SRCALPHA
        )
        center = (self.radius + 3, self.radius + 3)
        try:
            glow_surf = pygame.Surface(
                (self.radius * 2 + 12, self.radius * 2 + 12), pygame.SRCALPHA
            )
            pygame.draw.circle(
                glow_surf,
                glow_color,
                (glow_surf.get_width() // 2, glow_surf.get_height() // 2),
                self.radius + 5,
            )
            self.image.blit(
                glow_surf,
                (
                    -((glow_surf.get_width() - self.image.get_width()) // 2),
                    -((glow_surf.get_height() - self.image.get_height()) // 2),
                ),
            )
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        pygame.draw.circle(self.image, outer_color, center, self.radius)
        inner_r = max(1, self.radius - 3)
        pygame.draw.circle(self.image, inner_color, center, inner_r)

    def _render_storm_statue(self) -> None:
        """Render storm statue projectile."""
        self._render_statue(
            (20, 40, 140), (100, 150, 255), (40, 70, 180, 80)  # outer  # inner  # glow
        )

    def _render_fire_statue(self) -> None:
        """Render fire statue projectile."""
        self.image = pygame.Surface(
            (self.radius * 2 + 6, self.radius * 2 + 6), pygame.SRCALPHA
        )
        center = (self.radius + 3, self.radius + 3)
        try:
            glow_surf = pygame.Surface(
                (self.radius * 2 + 10, self.radius * 2 + 10), pygame.SRCALPHA
            )
            pygame.draw.circle(
                glow_surf,
                (255, 140, 0, 100),
                (glow_surf.get_width() // 2, glow_surf.get_height() // 2),
                self.radius + 4,
            )
            self.image.blit(
                glow_surf,
                (
                    -((glow_surf.get_width() - self.image.get_width()) // 2),
                    -((glow_surf.get_height() - self.image.get_height()) // 2),
                ),
            )
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        pygame.draw.circle(self.image, (200, 30, 30), center, self.radius)
        inner_r = max(1, self.radius - 4)
        pygame.draw.circle(self.image, (255, 220, 50), center, inner_r)

    def _render_ice_statue(self) -> None:
        """Render ice statue projectile."""
        self.image = pygame.Surface(
            (self.radius * 2 + 6, self.radius * 2 + 6), pygame.SRCALPHA
        )
        center = (self.radius + 3, self.radius + 3)
        try:
            glow_surf = pygame.Surface(
                (self.radius * 2 + 10, self.radius * 2 + 10), pygame.SRCALPHA
            )
            pygame.draw.circle(
                glow_surf,
                (100, 200, 255, 100),
                (glow_surf.get_width() // 2, glow_surf.get_height() // 2),
                self.radius + 4,
            )
            self.image.blit(
                glow_surf,
                (
                    -((glow_surf.get_width() - self.image.get_width()) // 2),
                    -((glow_surf.get_height() - self.image.get_height()) // 2),
                ),
            )
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        pygame.draw.circle(self.image, (150, 220, 255), center, self.radius)
        inner_r = max(1, self.radius - 4)
        pygame.draw.circle(self.image, (255, 255, 255), center, inner_r)

    def _render_inquisitor(self) -> None:
        """Render inquisitor projectile: orange glow."""
        self.image = pygame.Surface(
            (self.radius * 2 + 8, self.radius * 2 + 8), pygame.SRCALPHA
        )
        center = (self.radius + 4, self.radius + 4)
        try:
            glow_surf = pygame.Surface(
                (self.radius * 2 + 14, self.radius * 2 + 14), pygame.SRCALPHA
            )
            pygame.draw.circle(
                glow_surf,
                (255, 165, 60, 110),
                (glow_surf.get_width() // 2, glow_surf.get_height() // 2),
                self.radius + 6,
            )
            self.image.blit(
                glow_surf,
                (
                    -((glow_surf.get_width() - self.image.get_width()) // 2),
                    -((glow_surf.get_height() - self.image.get_height()) // 2),
                ),
            )
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        pygame.draw.circle(self.image, (220, 100, 20), center, self.radius)
        inner_r = max(1, self.radius - 3)
        pygame.draw.circle(self.image, (255, 170, 60), center, inner_r)

    def _render_inquisitor_horde(self) -> None:
        """Render inquisitor_horde projectile: green glow."""
        self.image = pygame.Surface(
            (self.radius * 2 + 8, self.radius * 2 + 8), pygame.SRCALPHA
        )
        center = (self.radius + 4, self.radius + 4)
        try:
            glow_surf = pygame.Surface(
                (self.radius * 2 + 14, self.radius * 2 + 14), pygame.SRCALPHA
            )
            pygame.draw.circle(
                glow_surf,
                (100, 255, 100, 110),
                (glow_surf.get_width() // 2, glow_surf.get_height() // 2),
                self.radius + 6,
            )
            self.image.blit(
                glow_surf,
                (
                    -((glow_surf.get_width() - self.image.get_width()) // 2),
                    -((glow_surf.get_height() - self.image.get_height()) // 2),
                ),
            )
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        pygame.draw.circle(self.image, (20, 100, 20), center, self.radius)
        inner_r = max(1, self.radius - 3)
        pygame.draw.circle(self.image, (60, 255, 60), center, inner_r)

    def _render_fallback(self) -> None:
        """Fallback rendering for generic/loaded projectiles."""
        image_name: str = (
            "enemy_projectile.png" if self.is_enemy_projectile else "projectile.png"
        )
        try:
            from src.assets.manager import get_image

            loaded_image: Surface | None = get_image(
                image_name, (self.radius * 2, self.radius * 2)
            )
            if loaded_image is not None:
                self.image = loaded_image.copy()
                return
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        # Fallback: draw programmatically
        if self.is_enemy_projectile:
            pygame.draw.circle(
                self.image,
                (255, 215, 0),
                (self.radius, self.radius),
                self.radius,
            )
            pygame.draw.circle(
                self.image,
                (255, 255, 0),
                (self.radius, self.radius),
                self.radius - 1,
            )
            pygame.draw.circle(
                self.image,
                (255, 255, 255),
                (self.radius - 1, self.radius - 1),
                max(1, self.radius // 3),
            )

    def draw_projectile(self) -> None:
        """Dispatch to appropriate projectile render method."""
        # Priority 1: Check appearance first
        appearance = getattr(self, "appearance", None)
        if appearance == "enemy_normal":
            self._render_enemy_normal()
            return
        if appearance == "archer_segment":
            self._render_archer_segment()
            return
        if appearance == "spear":
            self._render_spear()
            return

        # Priority 2: Check source
        if getattr(self, "source", None) == "orbital":
            self._render_orbital()
            return

        # Priority 3: Check weapon_type
        if self.weapon_type == "spear":
            self._render_spear()
            return
        if self.weapon_type == "shotgun":
            self._render_shotgun()
            return
        if self.weapon_type == "skullboom":
            self._render_skullboom()
            return
        if self.weapon_type == "DemonStrike":
            self._render_demon_strike()
            return

        # Priority 4: Generic player projectile (no appearance, no enemy, no weapon)
        if (
            self.weapon_type is None
            and not self.is_enemy_projectile
            and appearance is None
        ):
            self._render_player_generic()
            return

        # Priority 5: Appearance-based custom renderers
        self._render_appearance_based()

    def update(self) -> None:
        self.x += self.vel_x / 60  # Divide by FPS
        self.y += self.vel_y / 60

        # Tenebrae enlargement effect: grow from 12→20 over screen travel
        if (
            getattr(self, "weapon_type", None) == "tenebrae"
            or getattr(self, "appearance", None) == "tenebrae"
        ):
            # compute fraction of travelled distance relative to screen diagonal
            dist = math.hypot(self.x - self.spawn_x, self.y - self.spawn_y)
            maxd = None
            if getattr(self, "manager", None) is not None:
                g = getattr(self.manager, "game", None)
                if g is not None and hasattr(g, "width") and hasattr(g, "height"):
                    maxd = math.hypot(g.width, g.height)
            if maxd is None or maxd <= 0:
                maxd = 1000.0
            t = min(1.0, dist / maxd)
            # enlarged end size changed from 20 to 35 per further request
            target_radius = 12 + t * (35 - 12)  # float target for smoothing
            # initialize float radius tracker if missing
            if not hasattr(self, "radius_f"):
                self.radius_f = float(self.radius)
            # move a fraction toward the target for smooth animation
            # larger fraction per frame still feels smooth but nears target quicker
            self.radius_f += (target_radius - self.radius_f) * 0.2
            new_radius = int(self.radius_f)
            if new_radius != self.radius:
                self.radius = new_radius
                try:
                    self.image = pygame.Surface(
                        (self.radius * 2, self.radius * 2), pygame.SRCALPHA
                    )
                    self.draw_projectile()
                    # update rect to new size, maintain center
                    try:
                        self.rect = self.image.get_rect(center=(self.x, self.y))
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

        # Update rotation for DemonStrike to simulate rolling
        if getattr(self, "weapon_type", None) == "DemonStrike":
            speed = math.hypot(self.vel_x, self.vel_y)
            # Rotate based on speed; direction based on vertical movement
            if getattr(self, "vel_y", 0) < 0:
                self.rotation_angle = (self.rotation_angle + (speed * 0.1)) % 360
            else:
                self.rotation_angle = (self.rotation_angle - (speed * 0.1)) % 360
            # Update trail for particles
            self.trail.append((self.x, self.y))
            if len(self.trail) > 25:  # Keep last 25 positions
                self.trail.pop(0)
            # Redraw image to animate holes
            self.draw_projectile()
        self.rect.center = (self.x, self.y)

    def draw(self, screen, shake_x=0, shake_y=0) -> None:
        # If appearance changed after construction, regenerate image
        try:
            current_app: Any | None = getattr(self, "appearance", None)
            if getattr(self, "_appearance_cached", None) != current_app:
                self.draw_projectile()
                # Update rect in case size changed
                try:
                    self.rect = self.image.get_rect(center=(self.x, self.y))
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
                self._appearance_cached = current_app
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        draw_x: int | Any = self.rect.x + shake_x
        draw_y: int | Any = self.rect.y + shake_y

        # Special per-frame pulsing for fire_statue appearance
        if getattr(self, "appearance", None) == "fire_statue":
            try:
                t = pygame.time.get_ticks() / 1000.0
                pulse: float = 0.7 + 0.3 * math.sin(t * 4.0)  # smoother, stronger pulse
                size_w = int(self.radius * 2 + 14)
                surf = pygame.Surface((size_w, size_w), pygame.SRCALPHA)
                cx: int = size_w // 2
                cy: int = size_w // 2
                # Glow: slightly reduced size and brightness (tuned)
                glow_alpha: int = max(50, int(180 * pulse))
                try:
                    pygame.draw.circle(
                        surf,
                        (255, 140, 0, glow_alpha),
                        (cx, cy),
                        int(self.radius + 6 * pulse),
                    )
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
                # Outer red ring (bold)
                pygame.draw.circle(surf, (200, 30, 30), (cx, cy), self.radius)
                pygame.draw.circle(
                    surf, (160, 20, 20), (cx, cy), max(1, self.radius - 1), 1
                )
                # Inner yellow core pulses more visibly
                inner_r = max(1, int((self.radius - 4) * pulse))
                pygame.draw.circle(surf, (255, 220, 50), (cx, cy), inner_r)
                # Blit to screen centered on projectile
                screen.blit(
                    surf,
                    (int(draw_x + self.radius - cx), int(draw_y + self.radius - cy)),
                )
            except (AttributeError, TypeError, ValueError, KeyError):
                # Fallback to static image
                screen.blit(self.image, (draw_x, draw_y))
            return

        if self.weapon_type == "spear":
            # Rotate spear based on velocity direction to align tip with movement
            # Since spear is drawn vertically (pointing up), add 90° to align with velocity
            angle: float = math.degrees(math.atan2(self.vel_y, self.vel_x))
            rotated_image: Surface | Any = pygame.transform.rotate(
                self.image, -(angle + 90)
            )
            rotated_rect: Rect | Any = rotated_image.get_rect(
                center=(draw_x + self.radius, draw_y + self.radius)
            )
            screen.blit(rotated_image, rotated_rect)
        elif self.weapon_type is None and (not self.is_enemy_projectile):
            # rotate player segment
            angle = math.degrees(math.atan2(self.vel_y, self.vel_x))
            rotated = pygame.transform.rotate(self.image, -angle)
            rect = rotated.get_rect(center=(draw_x + self.radius, draw_y + self.radius))
            screen.blit(rotated, rect)
        elif getattr(self, "appearance", None) == "archer_segment":
            # rotate archer segment
            angle = math.degrees(math.atan2(self.vel_y, self.vel_x))
            rotated = pygame.transform.rotate(self.image, -angle)
            rect = rotated.get_rect(center=(draw_x + self.radius, draw_y + self.radius))
            screen.blit(rotated, rect)
        elif (
            self.weapon_type == "tenebrae"
            or getattr(self, "appearance", None) == "tenebrae"
        ):
            # Orient Tenebrae arc toward its velocity so it points at the cursor
            angle = math.degrees(math.atan2(self.vel_y, self.vel_x))
            # Use same adjustment as spear to keep the convex side forward
            rotated_image: Surface | Any = pygame.transform.rotate(
                self.image, -(angle + 90)
            )
            rotated_rect: Rect | Any = rotated_image.get_rect(
                center=(draw_x + self.radius, draw_y + self.radius)
            )
            screen.blit(rotated_image, rotated_rect)
        elif getattr(self, "weapon_type", None) == "DemonStrike":
            # Draw particle trail: wide at ball contact, narrowing and fading upward
            try:
                trail_len = len(getattr(self, "trail", []))
                for i, (px, py) in enumerate(getattr(self, "trail", [])):
                    # i=0 (start, above): small and transparent; i=trail_len-1 (end, below, at ball): large and opaque
                    alpha = int(
                        50 + (i / max(1, trail_len - 1)) * 205
                    )  # Increase opacity toward end
                    tr = max(
                        2,
                        int(
                            self.radius * 0.5
                            + (i / max(1, trail_len - 1)) * self.radius * 0.8
                        ),
                    )  # Grow toward end
                    # Yellow/orange particles at the end for variety
                    if i >= trail_len - 8:
                        color = (
                            (255, 165, 0, alpha)
                            if i >= trail_len - 5
                            else (255, 255, 0, alpha)
                        )  # Orange for last 5, yellow for next 3
                    else:
                        color = (255, 255, 255, alpha)
                    try:
                        tsurf = pygame.Surface((tr * 2, tr * 2), pygame.SRCALPHA)
                        pygame.draw.circle(tsurf, color, (tr, tr), tr)
                        screen.blit(
                            tsurf, (int(px - tr) + shake_x, int(py - tr) + shake_y)
                        )
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
            # Draw the ball
            screen.blit(self.image, (draw_x, draw_y))
        elif getattr(self, "weapon_type", None) == "skullboom":
            # Draw skull image and render an emphasized animated flame + glow
            screen.blit(self.image, (draw_x, draw_y))
            try:
                # Center of the sprite
                cx = draw_x + self.radius
                cy = draw_y + self.radius
                # Approximate fuse tip location (slightly above skull centre)
                fuse_tip_x = cx + self.radius * 0.05
                fuse_tip_y = cy - self.radius * 0.9

                # Time-based phase for flicker
                t = pygame.time.get_ticks() / 1000.0

                # Soft pulsing glow behind the fuse (makes effect more visible)
                glow_r = max(4, int(self.radius * 0.9))
                glow_alpha = int(90 + 70 * (0.5 + 0.5 * math.sin(t * 3.5)))
                glow_surf = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
                try:
                    pygame.draw.circle(
                        glow_surf,
                        (255, 170, 50, glow_alpha),
                        (glow_r, glow_r),
                        glow_r,
                    )
                    screen.blit(
                        glow_surf, (int(fuse_tip_x - glow_r), int(fuse_tip_y - glow_r))
                    )
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

                # Larger, denser particle cluster (counts scale with radius, capped)
                pcount = max(8, int(self.radius))
                pcount = min(pcount, 14)
                for i in range(pcount):
                    phase = t * (5.5 + i * 0.9) + i * 0.4
                    ox = (
                        math.sin(phase * 2.0) * self.radius * 0.10
                        + (i - pcount / 2 + 0.5) * self.radius * 0.03
                    )
                    oy = -(
                        (i % 5) * self.radius * 0.03
                        + abs(math.cos(phase)) * self.radius * 0.18
                        + random.uniform(0, self.radius * 0.08)
                    )
                    size = max(1, int(self.radius * (0.12 + (i % 3) * 0.04)))

                    # Alternate orange / yellow hues for variety
                    base_col = (255, 140 + (i % 2) * 80, 30 + (i % 3) * 20)

                    # Stronger alpha for visibility
                    alpha = int(180 + 75 * math.sin(phase + i))
                    alpha = max(50, min(255, alpha))

                    psurf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
                    try:
                        pygame.draw.circle(
                            psurf,
                            (base_col[0], base_col[1], base_col[2], alpha),
                            (size, size),
                            size,
                        )
                        screen.blit(
                            psurf,
                            (int(fuse_tip_x + ox - size), int(fuse_tip_y + oy - size)),
                        )
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass

                # Two bright upward sparks for extra emphasis
                for s in range(2):
                    sphase = t * (8.0 + s * 3.0) + s * 0.3
                    sox = math.sin(sphase * 2.5) * self.radius * 0.16 + random.uniform(
                        -self.radius * 0.04, self.radius * 0.04
                    )
                    soy = -(
                        random.uniform(self.radius * 0.12, self.radius * 0.30)
                        + abs(math.cos(sphase)) * self.radius * 0.28
                    )
                    ssize = max(1, int(self.radius * (0.22 + s * 0.05)))
                    salpha = int(220 + 35 * math.sin(sphase))
                    salpha = max(80, min(255, salpha))
                    ssurf = pygame.Surface((ssize * 2, ssize * 2), pygame.SRCALPHA)
                    try:
                        pygame.draw.circle(
                            ssurf,
                            (255, 210, 80, salpha),
                            (ssize, ssize),
                            ssize,
                        )
                        screen.blit(
                            ssurf,
                            (
                                int(fuse_tip_x + sox - ssize),
                                int(fuse_tip_y + soy - ssize),
                            ),
                        )
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
        else:
            screen.blit(self.image, (draw_x, draw_y))


class FliesProjectile(Projectile):
    def __init__(self, x, y, vel_x, vel_y, damage=10, heal_amount=2, level=1) -> None:
        # Slightly larger projectiles at max weapon level (level 6)
        base_radius = 6
        if level >= 6:
            base_radius += 2  # +2 pixels when fully upgraded
        super().__init__(
            x, y, vel_x, vel_y, damage=damage, radius=base_radius, weapon_type="Flies"
        )
        self.heal_amount: int = heal_amount
        self.level: int = level
        self.homing_range = 200
        # Reduced speed to make Flies projectiles significantly slower
        self.speed = 75
        # bounce mechanic removed; projectiles always vanish on hit
        self.target = None
        self.lifetime = 5 * 60  # 5 seconds at 60 FPS
        self.timer = 0

    def update(self, *args, **kwargs):
        self.timer += 1
        if self.timer > self.lifetime:
            self.kill()
            return

        # Update image for pulsing effect
        pulse_scale: float = 1 + 0.3 * math.sin(self.timer * 0.1)
        current_radius = int(self.radius * pulse_scale)
        self.image = pygame.Surface(
            (current_radius * 2, current_radius * 2), pygame.SRCALPHA
        )
        pygame.draw.circle(
            self.image, (75, 0, 130), (current_radius, current_radius), current_radius
        )
        pygame.draw.circle(
            self.image, (0, 0, 0), (current_radius, current_radius), current_radius // 2
        )
        self.rect = self.image.get_rect(center=(self.x, self.y))

        # If enemies and player are provided, do homing
        if args and len(args) >= 2:
            enemies = args[0]
            # Homing logic
            if not self.target or not self.target.alive():
                # Find nearest enemy (include bosses). Prefer health-based checks and support
                # both Sprite-like enemy objects and dict-like enemies used in tests.
                # Prefer bosses when possible: find nearest boss within range, otherwise nearest non-boss
                nearest_boss = None
                nearest_boss_dist = float("inf")
                nearest_other = None
                nearest_other_dist = float("inf")

                for enemy in enemies:
                    # Determine if enemy is alive/valid target
                    alive_flag = False
                    try:
                        if hasattr(enemy, "health"):
                            alive_flag: Any | bool = getattr(enemy, "health", 0) > 0
                        elif hasattr(enemy, "get"):
                            alive_flag = enemy.get("health", 0) > 0
                    except (AttributeError, TypeError, ValueError, KeyError):
                        alive_flag = False

                    # Fall back to sprite alive() if health check didn't apply
                    if not alive_flag and hasattr(enemy, "alive"):
                        try:
                            alive_flag = bool(enemy.alive())
                        except (AttributeError, TypeError, ValueError, KeyError):
                            try:
                                alive_flag = bool(getattr(enemy, "alive"))
                            except (AttributeError, TypeError, ValueError, KeyError):
                                alive_flag = False
                    if not alive_flag:
                        continue

                    # Get position safely (support attributes or dicts)
                    if hasattr(enemy, "x") and hasattr(enemy, "y"):
                        ex, ey = enemy.x, enemy.y
                    else:
                        ex, ey = getattr(enemy, "x", None), getattr(enemy, "y", None)
                        if (ex is None or ey is None) and hasattr(enemy, "get"):
                            ex, ey = enemy.get("x", None), enemy.get("y", None)
                    if ex is None or ey is None:
                        continue

                    dist: float = math.hypot(ex - self.x, ey - self.y)
                    if dist >= self.homing_range:
                        continue

                    # Detect boss enemy_type (support attr or dict)
                    try:
                        etype = getattr(enemy, "enemy_type", None)
                        if etype is None and hasattr(enemy, "get"):
                            etype = enemy.get("enemy_type")
                    except (AttributeError, TypeError, ValueError, KeyError):
                        etype = None

                    is_boss = isinstance(etype, str) and etype.startswith("boss")

                    if is_boss and dist < nearest_boss_dist:
                        nearest_boss_dist = dist
                        nearest_boss = enemy
                    elif (not is_boss) and dist < nearest_other_dist:
                        nearest_other_dist = dist
                        nearest_other = enemy

                # Prefer boss if available, otherwise fall back to nearest other
                if nearest_boss is not None:
                    self.target = nearest_boss
                else:
                    self.target = nearest_other

            if self.target:
                # Home towards target
                if hasattr(self.target, "x"):
                    tx, ty = self.target.x, self.target.y
                else:
                    tx, ty = self.target.get("x", 0), self.target.get("y", 0)
                dx = tx - self.x
                dy = ty - self.y
                dist: float = math.hypot(dx, dy)
                if dist > 0:
                    self.vel_x = (dx / dist) * self.speed
                    self.vel_y = (dy / dist) * self.speed

        # Move
        self.x += self.vel_x / 60  # Assuming 60 FPS
        self.y += self.vel_y / 60
        self.rect.center = (self.x, self.y)

    def draw_projectile(self) -> None:
        """Initial draw for flies projectile - will be updated in update()"""
        pass
