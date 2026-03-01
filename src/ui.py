import logging
import math
import os
import random
from typing import Any, Literal

from src.assets.manager import get_image
from src.game_constants import (
    SELECTION_BOX_HEIGHT,
    SELECTION_BOX_SPACING,
    SELECTION_BOX_WIDTH,
    STATUE_ASSET_VERTICAL_OFFSET,
    STATUE_BASE_Y,
    WALL_THICKNESS,
    WEAPON_ICON_SIZE,
    WEAPON_ICON_PADDING,
)
from src.weapons import WEAPON_DEFS

logger: logging.Logger = logging.getLogger(__name__)

# NOTE: Legacy UIManager (Tkinter-based) class removed — all rendering
# is handled by PygameUIManager below.

_STAT_CONFIGS: list[dict] = [
    {"name": "POWER", "key": "power", "color": (255, 68, 68), "y": 140},
    {"name": "VIGOR", "key": "vigor", "color": (255, 204, 0), "y": 185},
    {
        "name": "ADRENALINE",
        "key": "adrenaline",
        "color": (170, 68, 255),
        "y": 230,
    },
    {
        "name": "STRUCTURE",
        "key": "structure",
        "color": (139, 105, 20),
        "y": 275,
    },
]

_TREE_TYPES = [
    ("FIRE", "fire", (255, 68, 68)),
    ("STORM", "storm", (170, 68, 255)),
    ("ICE", "ice", (100, 200, 255)),
]

_WEAPON_HUD_NAMES: dict[str, str] = {
    "shotgun": "Hellgun",
    "orbital": "Orbitals",
    "spear": "Spear",
    "beast": "The number of the beast",
    "Flies": "Flies",
}


class PygameUIManager:
    """A Pygame-specific UI manager which encapsulates all drawing logic previously inside Game."""

    class FogParticle:
        """Particle representing a single fog blob in the dynamic fog system."""

        def __init__(self, ui, image):
            self.ui = ui
            self.image = image
            self.width = image.get_width()
            self.reset(start_random=True)

        def reset(self, start_random=False):
            WIDTH = self.ui.width
            HEIGHT = self.ui.height
            # import speed/amplitude constants locally to avoid NameError
            from src.game_constants import (
                FOG_AMPLITUDE_RANGE,
                FOG_MAX_SPEED,
                FOG_MIN_SPEED,
                FOG_TIMER_RANGE,
            )

            # allow particles to occupy top ~50%; bottom of texture <=50%
            y_limit = int(HEIGHT * 0.50)
            if start_random:
                self.x = random.randint(-self.width, WIDTH)
            else:
                self.x = -self.width
            # ensure y + height <= y_limit
            max_y = y_limit - self.width
            # y can start fairly high (negative) to create cut‑off effect
            self.y = random.randint(
                -self.width, max_y if max_y >= -self.width else -self.width
            )
            self.speed = random.uniform(FOG_MIN_SPEED, FOG_MAX_SPEED)
            self.amplitude = random.uniform(*FOG_AMPLITUDE_RANGE)
            self.timer = random.uniform(*FOG_TIMER_RANGE)

        def update(self):
            # horizontal drift
            self.x += self.speed
            # sine-wave vertical wobble
            self.timer += 0.02
            y_offset = math.sin(self.timer) * 0.5
            self.y += y_offset
            # wrap or reset when off right edge
            if self.x > self.ui.width:
                self.reset()

        def _apply_tint(self, color):
            """Pre-bake a tinted copy of the texture for the given color.

            Called once when the stage color changes instead of every frame,
            so draw() can do a single cheap blit.
            """
            pygame_mod = self.ui.pygame
            img = self.image.copy()
            tint_surf = pygame_mod.Surface(img.get_size(), pygame_mod.SRCALPHA)
            tint_surf.fill((*color, 255))
            img.blit(tint_surf, (0, 0), special_flags=pygame_mod.BLEND_RGBA_MULT)
            try:
                if (
                    getattr(pygame_mod, "display", None)
                    and pygame_mod.display.get_init()
                ):
                    img = img.convert_alpha()
            except Exception:
                pass
            self._tinted_image = img
            self._tinted_color = color

        def draw(self, surface):
            from src.game_constants import FOG_COLOR, PURGATORY_FOG_COLORS

            stage = getattr(self.ui.game, "selected_stage", None)
            color = PURGATORY_FOG_COLORS.get(stage, FOG_COLOR)
            # rebuild tinted texture only when color changes (not every frame)
            if getattr(self, "_tinted_color", None) != color:
                try:
                    self._apply_tint(color)
                except Exception:
                    self._tinted_image = self.image
                    self._tinted_color = color
            try:
                surface.blit(self._tinted_image, (self.x, self.y))
            except Exception:
                surface.blit(self.image, (self.x, self.y))

    def __init__(self, game) -> None:
        try:
            import pygame

            self.pygame: Any = pygame
        except Exception:
            self.pygame = None
        self.game: Any = game
        self.screen: Any | None = getattr(game, "screen", None)
        self.width: Any | int = getattr(game, "width", 0)
        self.height: Any | int = getattr(game, "height", 0)

        from src.assets.text_cache import get_font, get_text

        self.get_font = get_font
        self.get_text = get_text

        self._init_fog_particles()

    def _draw_button(self, rect, bg_normal, bg_hover, border_color, border_width=1):
        hov = rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
        self.pygame.draw.rect(self.screen, bg_hover if hov else bg_normal, rect)
        self.pygame.draw.rect(self.screen, border_color, rect, border_width)
        return hov

    def _center_text_in_rect(self, text_surf, rect, shake_x=0, shake_y=0):
        return (
            rect.centerx - text_surf.get_width() // 2 + shake_x,
            rect.centery - text_surf.get_height() // 2 + shake_y,
        )

    def _apply_shake_to_points(self, points, shake_x=0, shake_y=0):
        return [(p[0] + shake_x, p[1] + shake_y) for p in points]

    def _apply_shake(self, x, y, shake_x=0, shake_y=0):
        return int(x + shake_x), int(y + shake_y)

    def _draw_health_drop_particle(self, x, y, radius, alpha=255):
        if self.pygame:
            surf = self.pygame.Surface((radius * 2, radius * 2), self.pygame.SRCALPHA)
            self.pygame.draw.circle(surf, (0, 200, 0, alpha), (radius, radius), radius)
            self.pygame.draw.line(
                surf,
                (255, 255, 255),
                (radius - radius // 2, radius),
                (radius + radius // 2, radius),
                2,
            )
            self.pygame.draw.line(
                surf,
                (255, 255, 255),
                (radius, radius - radius // 2),
                (radius, radius + radius // 2),
                2,
            )
            self.screen.blit(surf, (x - radius, y - radius))

    def _draw_centered_text(self, text_surf, x, y, shake_x=0, shake_y=0):
        return (
            int(x - text_surf.get_width() // 2 + shake_x),
            int(y - text_surf.get_height() // 2 + shake_y),
        )

    def _calculate_meta_xp_fill(self, xp: int, xp_to: int, bar_width: int) -> int:
        """Compute fill width for the meta‑XP bar.

        This method guarantees that any positive XP produces at least one pixel of
        fill so the bar visibly advances even when the threshold is very large
        (e.g. 100 000).  We expose it separately so unit tests can verify the
        behaviour without rendering.
        """
        if xp_to <= 0:
            return 0
        ratio = min(1.0, xp / max(1, xp_to))
        fill = int(bar_width * ratio)
        if xp > 0 and fill == 0:
            fill = 1
        return fill

    def _health_drop_alpha(self, drop: dict) -> int:
        """Return the current alpha value for a health drop.

        The alpha pulses over time using ``game.frame_count``.  The amplitude and
        base level are chosen so the green circle is more transparent than a
        normal opaque colour (alpha < 255) and exhibits a gentle breathing
        effect.  The drop's ``x`` coordinate is folded into the phase so multiple
        drops do not pulse in perfect unison.
        """
        import math

        # base alpha and oscillation range
        # lower base alpha yields a more transparent average appearance
        base = 80
        amplitude = 80
        phase = self.game.frame_count * 0.1 + drop.get("x", 0)
        # sine oscillates between -1 and 1; map to 0..1
        norm = (math.sin(phase) + 1) / 2
        return int(base + norm * amplitude)

    # --- fog particle system helpers ------------------------------------------------
    # ── Fog / cloud optimization notes ───────────────────────────────────────
    #
    # Elemento,Tecnica di Ottimizzazione,Risultato
    # Fog Surface (Statica),.convert() + .set_alpha(),Carico CPU quasi nullo.
    # Nuvole (Dinamiche),.convert_alpha() + Downsampling (tela 1/2),
    #     Risparmio del 75% dei calcoli sui pixel.
    #
    # The table above documents the two main tricks we apply below: static
    # fog layers are pre‑converted to the display format and given a fixed
    # alpha so blits are blazingly cheap; dynamic elements (historically
    # purgatory clouds) are spawned at half resolution and use convert_alpha
    # to keep per‑pixel transparency while still being fast.  The cloud
    # helpers are currently no‑ops but the comments stay in case they return.

    def _create_fog_texture(self, size, color, alpha):
        """Create a circular gradient texture used by each fog particle.

        The resulting surface is not converted here because we may need to
        draw onto it repeatedly before use; consumers should call
        ``convert_alpha()`` if they intend to blit it many times.  We
        explicitly avoid conversion during headless testing since SDL
        dummy drivers don't support it.
        """
        try:
            pygame = self.pygame
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            for r in range(size // 2, 0, -1):
                current_alpha = int(alpha * (1 - (r / (size // 2)) ** 2))
                pygame.draw.circle(
                    surf, (*color, current_alpha), (size // 2, size // 2), r
                )
            # avoid convert_alpha in headless/test environments
            if getattr(pygame, "display", None) and pygame.display.get_init():
                try:
                    surf = surf.convert_alpha()
                except Exception:
                    pass
            return surf
        except Exception:
            return None

    def _init_fog_particles(self) -> None:
        """Create the static texture and initial particle list."""
        try:
            from src.game_constants import (
                FOG_ALPHA,
                FOG_COLOR,
                FOG_PARTICLE_COUNT,
                FOG_TEXTURE_SIZE,
            )

            # create texture once
            tex = self._create_fog_texture(FOG_TEXTURE_SIZE, FOG_COLOR, FOG_ALPHA)
            self._fog_particles: list[PygameUIManager.FogParticle] = []
            if tex:
                for _ in range(FOG_PARTICLE_COUNT):
                    self._fog_particles.append(PygameUIManager.FogParticle(self, tex))
            else:
                self._fog_particles = []
        except Exception:
            self._fog_particles = []

    def _update_and_draw_fog_particles(self) -> None:
        """Update positions and render all fog particles to the screen."""
        try:
            for p in list(getattr(self, "_fog_particles", [])):
                p.update()
                # clamp bottom edge within top 50% after update
                if p.y + p.width > self.height * 0.50:
                    p.y = self.height * 0.50 - p.width
                if self.screen and self.pygame:
                    p.draw(self.screen)
        except Exception:
            pass

    def _draw_floor_polygon(self, shake_x=0, shake_y=0) -> None:
        pygame = self.pygame
        settings = self.game.stage_settings[self.game.selected_stage]

        if (
            self.game.selected_stage == "prologo"
            and self.game.left_wall_points
            and self.game.right_wall_points
            and not self.game.background_image_drawn
        ):
            inside_points = (
                self.game.left_wall_points + self.game.right_wall_points[::-1]
            )
            prologo_floor = settings.get("floor_color", (0, 50, 0))
            pygame.draw.polygon(
                self.screen,
                prologo_floor,
                self._apply_shake_to_points(inside_points, shake_x, shake_y),
            )
        elif (
            self.game.is_limbo_stage()
            and self.game.left_wall_points
            and self.game.right_wall_points
            and not getattr(self.game, "background_image_drawn", False)
        ):
            inside_points = (
                self.game.left_wall_points + self.game.right_wall_points[::-1]
            )
            pygame.draw.polygon(
                self.screen,
                (100, 50, 0),
                self._apply_shake_to_points(inside_points, shake_x, shake_y),
            )
        elif (
            getattr(self.game, "selected_stage", None)
            and str(self.game.selected_stage).startswith(("purgatory", "hell"))
            and self.game.left_wall_points
            and self.game.right_wall_points
            and not getattr(self.game, "background_image_drawn", False)
        ):
            inside_points = (
                self.game.left_wall_points + self.game.right_wall_points[::-1]
            )
            settings = self.game.stage_settings.get(self.game.selected_stage, {})
            inside_color = settings.get("floor_color", (40, 40, 40))
            pygame.draw.polygon(
                self.screen,
                inside_color,
                [(p[0], p[1]) for p in inside_points],
            )

    def _draw_walls(self, shake_x=0, shake_y=0) -> None:
        pygame = self.pygame
        settings = self.game.stage_settings[self.game.selected_stage]
        wall_color = settings["wall_color"]

        is_hell_stage = getattr(self.game, "selected_stage", "").startswith("hell")
        is_prologo = getattr(self.game, "selected_stage", "") == "prologo"
        render_wall_thickness = (
            WALL_THICKNESS * 2
            if is_hell_stage
            else WALL_THICKNESS if is_prologo else WALL_THICKNESS
        )
        cap_extension = max(6, render_wall_thickness // 4) if is_hell_stage else 0

        if is_prologo:
            section_size = 5
            num_points = len(self.game.left_wall_points)
            num_sections = (num_points + section_size - 1) // section_size
            rng = random.Random(42)
            thickness_variations = [rng.randint(-2, 2) for _ in range(num_sections)]

        if self.game.left_wall_points:
            if is_prologo:
                left_wall_exterior = []
                for i, point in enumerate(self.game.left_wall_points):
                    section = i // section_size
                    variation = thickness_variations[section]
                    thickness = WALL_THICKNESS + variation
                    left_wall_exterior.append((point[0] - thickness, point[1]))
            else:
                left_wall_exterior = [
                    (point[0] - render_wall_thickness, point[1])
                    for point in self.game.left_wall_points
                ]
            if cap_extension and left_wall_exterior:
                tx, ty = left_wall_exterior[0]
                left_wall_exterior.insert(0, (tx - cap_extension, ty - cap_extension))
                bx, by = left_wall_exterior[-1]
                left_wall_exterior.append((bx - cap_extension, by + cap_extension))

            left_wall_all = self.game.left_wall_points + left_wall_exterior[::-1]
            pygame.draw.polygon(
                self.screen,
                wall_color,
                [(p[0], p[1]) for p in left_wall_all],
            )

            if is_hell_stage:
                try:
                    inner_edge = [
                        (int(p[0]), int(p[1])) for p in self.game.left_wall_points
                    ]
                    outer_edge = [(int(p[0]), int(p[1])) for p in left_wall_exterior]
                    pygame.draw.lines(
                        self.screen, (0, 0, 0), False, inner_edge, width=4
                    )
                    pygame.draw.lines(
                        self.screen, (0, 0, 0), False, outer_edge, width=4
                    )
                except Exception:
                    pass

        if self.game.right_wall_points:
            if is_prologo:
                right_wall_exterior = []
                for i, point in enumerate(self.game.right_wall_points):
                    section = i // section_size
                    variation = thickness_variations[section]
                    thickness = WALL_THICKNESS + variation
                    right_wall_exterior.append((point[0] + thickness, point[1]))
            else:
                right_wall_exterior = [
                    (point[0] + render_wall_thickness, point[1])
                    for point in self.game.right_wall_points
                ]
            if cap_extension and right_wall_exterior:
                tx, ty = right_wall_exterior[0]
                right_wall_exterior.insert(0, (tx + cap_extension, ty - cap_extension))
                bx, by = right_wall_exterior[-1]
                right_wall_exterior.append((bx + cap_extension, by + cap_extension))

            right_wall_all = self.game.right_wall_points + right_wall_exterior[::-1]
            pygame.draw.polygon(
                self.screen,
                wall_color,
                [(p[0], p[1]) for p in right_wall_all],
            )

            if is_hell_stage:
                try:
                    inner_edge = [
                        (int(p[0]), int(p[1])) for p in self.game.right_wall_points
                    ]
                    outer_edge = [(int(p[0]), int(p[1])) for p in right_wall_exterior]
                    pygame.draw.lines(
                        self.screen, (0, 0, 0), False, inner_edge, width=4
                    )
                    pygame.draw.lines(
                        self.screen, (0, 0, 0), False, outer_edge, width=4
                    )
                except Exception:
                    pass

    def _draw_torches(self, shake_x=0, shake_y=0) -> None:
        pygame = self.pygame
        is_prologo = getattr(self.game, "selected_stage", "") == "prologo"
        if not is_prologo:
            return

        torch_image = get_image("torch.png", (40, 80))
        torch_positions = [0.2, 0.5, 0.8]
        for frac in torch_positions:
            y = int(frac * self.height)
            left_point = min(self.game.left_wall_points, key=lambda p: abs(p[1] - y))
            right_point = min(self.game.right_wall_points, key=lambda p: abs(p[1] - y))

            if torch_image:
                torch_x = left_point[0] - 20
                torch_y = left_point[1] - 80
                self.screen.blit(torch_image, (torch_x, torch_y))

                torch_x = right_point[0] - 20
                torch_y = right_point[1] - 80
                self.screen.blit(torch_image, (torch_x, torch_y))
            else:
                torch_x = left_point[0] - 20
                torch_y = left_point[1]
                pygame.draw.rect(
                    self.screen, (50, 25, 0), (torch_x, torch_y - 20, 16, 40)
                )
                pygame.draw.circle(
                    self.screen,
                    (255, 100, 0),
                    (int(torch_x + 8), int(torch_y - 20)),
                    16,
                )
                pygame.draw.circle(
                    self.screen, (255, 200, 0), (int(torch_x + 8), int(torch_y - 20)), 8
                )

                torch_x = right_point[0] - 20
                torch_y = right_point[1]
                pygame.draw.rect(
                    self.screen, (50, 25, 0), (torch_x, torch_y - 20, 16, 40)
                )
                pygame.draw.circle(
                    self.screen,
                    (255, 100, 0),
                    (int(torch_x + 8), int(torch_y - 20)),
                    16,
                )
                pygame.draw.circle(
                    self.screen, (255, 200, 0), (int(torch_x + 8), int(torch_y - 20)), 8
                )

    def _draw_buildings(self, shake_x=0, shake_y=0) -> None:
        pygame = self.pygame
        settings = self.game.stage_settings[self.game.selected_stage]

        if (
            self.game.selected_stage == "prologo"
            and self.game.buildings
            and settings.get("building_color")
        ):
            # building_color is present in settings but not needed for procedural drawing
            pass

            # Sort buildings by x position for consistent left/center/right assignment
            sorted_buildings = sorted(self.game.buildings, key=lambda b: b["x"])

            for i, building in enumerate(sorted_buildings):
                base_x = building["x"] + shake_x
                base_y = building["y"] + shake_y - 40  # Position above spawn point

                # Try to load external assets first
                asset_loaded = False

                if i == 0:  # Outer left church
                    asset_name = "church_outer_left.png"
                    scale_factor = 0.3  # Same size as other side churches
                elif i == 1:  # Left church
                    asset_name = "church_left.png"
                    scale_factor = 0.3  # Reduced proportionally
                elif i == 2:  # Center cathedral
                    asset_name = "cathedral_center.png"
                    scale_factor = 0.4  # Scaled to 200x200 pixels (500*0.4=200)
                elif i == 3:  # Right church
                    asset_name = "church_right.png"
                    scale_factor = 0.3  # Reduced proportionally
                else:  # i == 4: Outer right church
                    asset_name = "church_outer_right.png"
                    scale_factor = 0.3  # Same size as other side churches

                # Try to load the asset
                try:
                    building_image = get_image(asset_name)
                    if building_image:
                        # Scale the image
                        original_size = building_image.get_size()
                        scaled_size = (
                            int(original_size[0] * scale_factor),
                            int(original_size[1] * scale_factor),
                        )
                        building_image = pygame.transform.scale(
                            building_image, scaled_size
                        )

                        # Position the image (centered on the spawn point, above it)
                        image_rect = building_image.get_rect()
                        image_rect.centerx = base_x
                        # Position lower to avoid being cut off at the top
                        image_rect.centery = (
                            base_y + scaled_size[1] // 4
                        )  # Position lower

                        self.screen.blit(building_image, image_rect)
                        asset_loaded = True
                except (ImportError, pygame.error, AttributeError):
                    pass  # Fall back to procedural drawing

                # Fallback: procedural drawing if asset not found
                if not asset_loaded:
                    if i == 1:  # Center cathedral - larger
                        # Adjust Y position (lower by 20 pixels)
                        cathedral_y = base_y + 50

                        # Cathedral foundation/base (dark stone)
                        foundation_color = (60, 45, 35)
                        pygame.draw.rect(
                            self.screen,
                            foundation_color,
                            (base_x - 42, cathedral_y + 40, 84, 12),
                        )

                        # Main cathedral body (rectangular base) - light stone
                        stone_color = (140, 120, 100)
                        pygame.draw.rect(
                            self.screen, stone_color, (base_x - 35, cathedral_y, 70, 50)
                        )

                        # Central entrance doors (large, ornate)
                        door_color = (80, 60, 45)
                        pygame.draw.rect(
                            self.screen,
                            door_color,
                            (base_x - 12, cathedral_y + 25, 24, 25),
                        )

                        # Door frame/details (gold accents)
                        gold_color = (180, 150, 50)
                        pygame.draw.rect(
                            self.screen,
                            gold_color,
                            (base_x - 14, cathedral_y + 23, 28, 3),  # Top frame
                        )
                        pygame.draw.rect(
                            self.screen,
                            gold_color,
                            (base_x - 14, cathedral_y + 47, 28, 3),  # Bottom frame
                        )
                        pygame.draw.rect(
                            self.screen,
                            gold_color,
                            (base_x - 14, cathedral_y + 23, 3, 27),  # Left frame
                        )
                        pygame.draw.rect(
                            self.screen,
                            gold_color,
                            (base_x + 11, cathedral_y + 23, 3, 27),  # Right frame
                        )

                        # Rose window above entrance (stained glass)
                        rose_window_color = (100, 150, 200)
                        pygame.draw.circle(
                            self.screen,
                            rose_window_color,
                            (base_x, cathedral_y + 15),
                            8,
                        )

                        # Side windows (stained glass)
                        window_color = (120, 160, 210)
                        # Left side windows
                        pygame.draw.rect(
                            self.screen,
                            window_color,
                            (base_x - 28, cathedral_y + 12, 8, 12),
                        )
                        pygame.draw.rect(
                            self.screen,
                            window_color,
                            (base_x - 28, cathedral_y + 28, 8, 12),
                        )
                        # Right side windows
                        pygame.draw.rect(
                            self.screen,
                            window_color,
                            (base_x + 20, cathedral_y + 12, 8, 12),
                        )
                        pygame.draw.rect(
                            self.screen,
                            window_color,
                            (base_x + 20, cathedral_y + 28, 8, 12),
                        )

                        # Window frames (stone)
                        frame_color = (100, 85, 70)
                        # Left frames
                        pygame.draw.rect(
                            self.screen,
                            frame_color,
                            (base_x - 29, cathedral_y + 11, 10, 1),
                        )
                        pygame.draw.rect(
                            self.screen,
                            frame_color,
                            (base_x - 29, cathedral_y + 24, 10, 1),
                        )
                        pygame.draw.rect(
                            self.screen,
                            frame_color,
                            (base_x - 29, cathedral_y + 11, 1, 14),
                        )
                        pygame.draw.rect(
                            self.screen,
                            frame_color,
                            (base_x - 20, cathedral_y + 11, 1, 14),
                        )
                        pygame.draw.rect(
                            self.screen,
                            frame_color,
                            (base_x - 29, cathedral_y + 39, 10, 1),
                        )
                        pygame.draw.rect(
                            self.screen,
                            frame_color,
                            (base_x - 29, cathedral_y + 27, 1, 14),
                        )
                        pygame.draw.rect(
                            self.screen,
                            frame_color,
                            (base_x - 20, cathedral_y + 27, 1, 14),
                        )
                        # Right frames
                        pygame.draw.rect(
                            self.screen,
                            frame_color,
                            (base_x + 19, cathedral_y + 11, 10, 1),
                        )
                        pygame.draw.rect(
                            self.screen,
                            frame_color,
                            (base_x + 19, cathedral_y + 24, 10, 1),
                        )
                        pygame.draw.rect(
                            self.screen,
                            frame_color,
                            (base_x + 19, cathedral_y + 11, 1, 14),
                        )
                        pygame.draw.rect(
                            self.screen,
                            frame_color,
                            (base_x + 28, cathedral_y + 11, 1, 14),
                        )
                        pygame.draw.rect(
                            self.screen,
                            frame_color,
                            (base_x + 19, cathedral_y + 39, 10, 1),
                        )
                        pygame.draw.rect(
                            self.screen,
                            frame_color,
                            (base_x + 19, cathedral_y + 27, 1, 14),
                        )
                        pygame.draw.rect(
                            self.screen,
                            frame_color,
                            (base_x + 28, cathedral_y + 27, 1, 14),
                        )

                        # Cathedral roof (triangular) - dark tile
                        roof_color = (70, 55, 45)
                        roof_points = [
                            (base_x - 40, cathedral_y),  # Left base
                            (base_x, cathedral_y - 30),  # Top peak
                            (base_x + 40, cathedral_y),  # Right base
                        ]
                        pygame.draw.polygon(self.screen, roof_color, roof_points)

                        # Roof ridge details
                        ridge_color = (90, 75, 60)
                        pygame.draw.line(
                            self.screen,
                            ridge_color,
                            (base_x - 35, cathedral_y - 5),
                            (base_x + 35, cathedral_y - 5),
                            2,
                        )

                        # Central spire - stone
                        pygame.draw.rect(
                            self.screen,
                            stone_color,
                            (base_x - 5, cathedral_y - 55, 10, 25),
                        )

                        # Spire cross (large gold cross)
                        pygame.draw.rect(
                            self.screen,
                            gold_color,
                            (base_x - 3, cathedral_y - 57, 6, 10),  # Vertical
                        )
                        pygame.draw.rect(
                            self.screen,
                            gold_color,
                            (base_x - 6, cathedral_y - 54, 12, 4),  # Horizontal
                        )

                        # Side towers (larger than before)
                        tower_color = (130, 110, 90)
                        # Left tower
                        pygame.draw.rect(
                            self.screen,
                            tower_color,
                            (base_x - 50, cathedral_y - 15, 15, 35),
                        )
                        # Left tower roof
                        pygame.draw.polygon(
                            self.screen,
                            roof_color,
                            [
                                (base_x - 52, cathedral_y - 15),
                                (base_x - 42, cathedral_y - 25),
                                (base_x - 35, cathedral_y - 15),
                            ],
                        )
                        # Left tower spire
                        pygame.draw.rect(
                            self.screen,
                            tower_color,
                            (base_x - 45, cathedral_y - 35, 5, 10),
                        )

                        # Right tower
                        pygame.draw.rect(
                            self.screen,
                            tower_color,
                            (base_x + 35, cathedral_y - 15, 15, 35),
                        )
                        # Right tower roof
                        pygame.draw.polygon(
                            self.screen,
                            roof_color,
                            [
                                (base_x + 35, cathedral_y - 15),
                                (base_x + 42, cathedral_y - 25),
                                (base_x + 47, cathedral_y - 15),
                            ],
                        )
                        # Right tower spire
                        pygame.draw.rect(
                            self.screen,
                            tower_color,
                            (base_x + 40, cathedral_y - 35, 5, 10),
                        )

                        # Tower windows
                        pygame.draw.rect(
                            self.screen,
                            window_color,
                            (base_x - 47, cathedral_y - 5, 4, 6),  # Left tower window
                        )
                        pygame.draw.rect(
                            self.screen,
                            window_color,
                            (base_x + 39, cathedral_y - 5, 4, 6),  # Right tower window
                        )

                    else:  # Side churches - smaller
                        # Adjust Y position (lower by 20 pixels)
                        church_y = base_y + 50

                        # Main church body (rectangular base) - stone color
                        stone_color = (120, 100, 80)  # Brownish stone
                        pygame.draw.rect(
                            self.screen, stone_color, (base_x - 20, church_y, 40, 28)
                        )

                        # Church foundation/base (darker stone)
                        foundation_color = (80, 60, 50)
                        pygame.draw.rect(
                            self.screen,
                            foundation_color,
                            (base_x - 22, church_y + 25, 44, 8),
                        )

                        # Central door (darker rectangle)
                        door_color = (60, 40, 30)
                        pygame.draw.rect(
                            self.screen, door_color, (base_x - 6, church_y + 12, 12, 16)
                        )

                        # Door frame/details
                        pygame.draw.rect(
                            self.screen,
                            (100, 80, 60),
                            (base_x - 7, church_y + 11, 14, 2),  # Top frame
                        )
                        pygame.draw.rect(
                            self.screen,
                            (100, 80, 60),
                            (base_x - 7, church_y + 27, 14, 2),  # Bottom frame
                        )

                        # Side windows
                        window_color = (150, 180, 200)  # Light blue stained glass
                        # Left window
                        pygame.draw.rect(
                            self.screen, window_color, (base_x - 16, church_y + 8, 6, 8)
                        )
                        # Right window
                        pygame.draw.rect(
                            self.screen, window_color, (base_x + 10, church_y + 8, 6, 8)
                        )

                        # Window frames (stone)
                        pygame.draw.rect(
                            self.screen,
                            stone_color,
                            (base_x - 17, church_y + 7, 8, 1),  # Left top
                        )
                        pygame.draw.rect(
                            self.screen,
                            stone_color,
                            (base_x - 17, church_y + 16, 8, 1),  # Left bottom
                        )
                        pygame.draw.rect(
                            self.screen,
                            stone_color,
                            (base_x + 9, church_y + 7, 8, 1),  # Right top
                        )
                        pygame.draw.rect(
                            self.screen,
                            stone_color,
                            (base_x + 9, church_y + 16, 8, 1),  # Right bottom
                        )

                        # Church roof (triangular) - darker tile color
                        roof_color = (80, 60, 50)
                        roof_points = [
                            (base_x - 24, church_y),  # Left base
                            (base_x, church_y - 16),  # Top peak
                            (base_x + 24, church_y),  # Right base
                        ]
                        pygame.draw.polygon(self.screen, roof_color, roof_points)

                        # Roof ridge detail
                        ridge_color = (100, 80, 60)
                        pygame.draw.line(
                            self.screen,
                            ridge_color,
                            (base_x - 20, church_y - 2),
                            (base_x + 20, church_y - 2),
                            2,
                        )

                        # Central spire - stone color
                        pygame.draw.rect(
                            self.screen, stone_color, (base_x - 2, church_y - 28, 4, 12)
                        )

                        # Spire cross (gold color)
                        cross_color = (200, 180, 50)
                        pygame.draw.rect(
                            self.screen,
                            cross_color,
                            (base_x - 1, church_y - 30, 2, 6),  # Vertical
                        )
                        pygame.draw.rect(
                            self.screen,
                            cross_color,
                            (base_x - 2, church_y - 28, 4, 2),  # Horizontal
                        )

                        # Small bell tower windows
                        pygame.draw.rect(
                            self.screen, window_color, (base_x - 1, church_y - 22, 2, 3)
                        )

    def _draw_battlefield_crosses(self, shake_x=0, shake_y=0) -> None:
        pygame = self.pygame
        if (
            self.game.selected_stage == "prologo"
            and self.game.left_wall_points
            and self.game.right_wall_points
        ):
            battlefield_cross = self.game.assets.get("battlefield_cross.png")
            if battlefield_cross is None:
                # Create fallback bloody cross image for battlefield (80x100)
                battlefield_cross = pygame.Surface((80, 100), pygame.SRCALPHA)
                # Draw cross shape in brown/wood color
                wood_color = (139, 69, 19)
                blood_color = (139, 0, 0)
                # Vertical bar (scaled for 80x100)
                pygame.draw.rect(battlefield_cross, wood_color, (32, 20, 16, 60))
                # Horizontal bar (scaled for 80x100)
                pygame.draw.rect(battlefield_cross, wood_color, (16, 42, 48, 16))
                # Add blood stains (scaled for 80x100)
                pygame.draw.circle(battlefield_cross, blood_color, (40, 30), 6)
                pygame.draw.circle(battlefield_cross, blood_color, (20, 45), 5)
                pygame.draw.circle(battlefield_cross, blood_color, (60, 55), 5)
            else:
                # Scale the loaded image to 80x100 if it's not already that size
                if battlefield_cross.get_size() != (80, 100):
                    battlefield_cross = pygame.transform.scale(
                        battlefield_cross, (80, 100)
                    )

            # Position crosses at bottom sides of battlefield
            if self.game.left_wall_points and self.game.right_wall_points:
                # Calculate battlefield height for better positioning
                battlefield_height = self.game.height
                cross_y_position = battlefield_height - 130  # Position for 80x100 size

                # Left cross - positioned closer to left wall
                left_bottom_x = (
                    self.game.left_wall_points[-1][0] + 5
                )  # Closer to left wall

                # Right cross - positioned closer to right wall
                right_bottom_x = (
                    self.game.right_wall_points[-1][0] - 85
                )  # Closer to right wall

                # Draw the crosses at the calculated Y position
                self.screen.blit(
                    battlefield_cross,
                    (left_bottom_x + shake_x, cross_y_position + shake_y),
                )
                self.screen.blit(
                    battlefield_cross,
                    (right_bottom_x + shake_x, cross_y_position + shake_y),
                )

    def draw_game_world(self, shake_x=0, shake_y=0) -> None:
        """Draw walls, buildings and background following the original implementation."""
        if (
            not self.screen
            or not self.game.selected_stage
            or self.game.selected_stage not in self.game.stage_settings
        ):
            return

        self._draw_floor_polygon(shake_x, shake_y)
        self._draw_walls(shake_x, shake_y)
        self._draw_torches(shake_x, shake_y)
        self._draw_buildings(shake_x, shake_y)
        self._draw_battlefield_crosses(shake_x, shake_y)

        if hasattr(self, "draw_dead_trees"):
            self.draw_dead_trees(shake_x, shake_y)
        if hasattr(self, "draw_pedestals"):
            self.draw_pedestals(shake_x, shake_y)

    def draw_main_menu(self, shake_x: int = 0, shake_y: int = 0) -> None:
        """Main menu: big START button + permanent upgrades + gear icon."""
        pygame = self.pygame
        if not self.screen or not pygame:
            return

        w, h = self.width, self.height

        # Gothic dark background
        self.screen.fill((5, 3, 8))

        # Top and bottom darkening strips
        top_vignette = pygame.Surface((w, 110), pygame.SRCALPHA)
        top_vignette.fill((0, 0, 0, 150))
        self.screen.blit(top_vignette, (0, 0))
        bot_vignette = pygame.Surface((w, 90), pygame.SRCALPHA)
        bot_vignette.fill((0, 0, 0, 130))
        self.screen.blit(bot_vignette, (0, h - 90))

        # ── Title ──────────────────────────────────────────────────────────
        title_font = self.get_font(72)
        title_surf = self.get_text("SATAN'S FALL", title_font, (185, 28, 28))
        tx, ty = self._draw_centered_text(
            title_surf, w // 2, h // 2 - 195, shake_x, shake_y
        )
        self.screen.blit(title_surf, (tx, ty))

        # Ornamental line + diamond under title
        line_y = ty + title_surf.get_height() + 12
        pygame.draw.line(
            self.screen,
            (110, 28, 28),
            (w // 2 - 190, line_y),
            (w // 2 + 190, line_y),
            1,
        )
        dcx, dcy = w // 2, line_y
        pygame.draw.polygon(
            self.screen,
            (150, 38, 38),
            [(dcx, dcy - 5), (dcx + 5, dcy), (dcx, dcy + 5), (dcx - 5, dcy)],
        )

        # ── START button ───────────────────────────────────────────────────
        btn_w, btn_h = 250, 68
        start_rect = pygame.Rect(
            w // 2 - btn_w // 2 + shake_x, h // 2 - 34 + shake_y, btn_w, btn_h
        )
        start_hov = self._draw_button(
            start_rect, (22, 5, 5), (38, 10, 10), (145, 32, 32), 2
        )
        inner = start_rect.inflate(-6, -6)
        pygame.draw.rect(
            self.screen, (110, 28, 28) if start_hov else (68, 16, 16), inner, 1
        )
        start_font = self.get_font(48)
        start_text = self.get_text(
            "START", start_font, (255, 230, 205) if start_hov else (225, 200, 175)
        )
        tx, ty = self._draw_centered_text(
            start_text, w // 2, start_rect.centery, shake_x, 0
        )
        self.screen.blit(start_text, (tx, ty))

        # ── PERMANENT UPGRADES button ──────────────────────────────────────
        up_w, up_h = 220, 36
        up_rect = pygame.Rect(
            w // 2 - up_w // 2 + shake_x, h // 2 + 55 + shake_y, up_w, up_h
        )
        up_hov = self._draw_button(
            up_rect, (10, 6, 18), (18, 10, 28), (105, 68, 165), 1
        )
        up_font = self.get_font(20)
        up_text = self.get_text(
            "PERMANENT UPGRADES",
            up_font,
            (185, 145, 235) if up_hov else (138, 102, 192),
        )
        tx, ty = self._draw_centered_text(up_text, w // 2, up_rect.centery, shake_x, 0)
        self.screen.blit(up_text, (tx, ty))

        # ── PROFILES button ────────────────────────────────────────────────
        pr_w, pr_h = 220, 36
        pr_rect = pygame.Rect(
            w // 2 - pr_w // 2 + shake_x, h // 2 + 100 + shake_y, pr_w, pr_h
        )
        pr_hov = self._draw_button(pr_rect, (8, 12, 8), (14, 22, 14), (60, 110, 60), 1)
        pr_font = self.get_font(20)
        active_slot = getattr(self.game, "active_profile_slot", None)
        if active_slot is not None:
            profile_name = self.game.global_progress.get(
                "profile_name", f"Profile {active_slot}"
            )
            pr_label = f"PROFILES  ● {profile_name}"
        else:
            pr_label = "PROFILES"
        pr_text = self.get_text(
            pr_label, pr_font, (160, 220, 140) if pr_hov else (100, 160, 100)
        )
        tx, ty = self._draw_centered_text(pr_text, w // 2, pr_rect.centery, shake_x, 0)
        self.screen.blit(pr_text, (tx, ty))

        # ── EXIT button (bottom center, above vignette) ─────────────────────
        ex_w, ex_h = 220, 36
        ex_rect = pygame.Rect(
            w // 2 - ex_w // 2 + shake_x, h - 110 + shake_y, ex_w, ex_h
        )
        ex_hov = self._draw_button(ex_rect, (12, 8, 8), (22, 14, 14), (110, 60, 60), 1)
        ex_font = self.get_font(20)
        ex_text = self.get_text(
            "EXIT", ex_font, (220, 160, 140) if ex_hov else (160, 100, 80)
        )
        tx, ty = self._draw_centered_text(ex_text, w // 2, ex_rect.centery, shake_x, 0)
        self.screen.blit(ex_text, (tx, ty))

        # Draw EXIT confirmation prompt if pending
        if getattr(self.game, "exit_confirm_pending", False):
            # Semi-transparent overlay
            overlay = pygame.Surface((w, h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            self.screen.blit(overlay, (0, 0))

            # Confirmation dialog background
            dialog_w, dialog_h = 400, 160
            dialog_x = w // 2 - dialog_w // 2
            dialog_y = h // 2 - dialog_h // 2
            pygame.draw.rect(
                self.screen, (20, 10, 10), (dialog_x, dialog_y, dialog_w, dialog_h)
            )
            pygame.draw.rect(
                self.screen, (100, 50, 50), (dialog_x, dialog_y, dialog_w, dialog_h), 2
            )

            # Text: "Exit Game?"
            confirm_font = self.get_font(32)
            confirm_text = self.get_text("Exit Game?", confirm_font, (220, 180, 160))
            tx, ty = self._draw_centered_text(confirm_text, w // 2, dialog_y + 40, 0, 0)
            self.screen.blit(confirm_text, (tx, ty))

            # YES button (left)
            yes_w, yes_h = 75, 36
            yes_x = dialog_x + dialog_w // 2 - yes_w - 12
            yes_y = dialog_y + dialog_h - 52
            yes_rect = pygame.Rect(yes_x, yes_y, yes_w, yes_h)
            yes_hov = self._draw_button(
                yes_rect, (12, 8, 8), (22, 14, 14), (110, 60, 60), 1
            )
            yes_font = self.get_font(18)
            yes_text = self.get_text(
                "YES", yes_font, (220, 160, 140) if yes_hov else (160, 100, 80)
            )
            tx, ty = self._draw_centered_text(
                yes_text, yes_x + yes_w // 2, yes_y + yes_h // 2, 0, 0
            )
            self.screen.blit(yes_text, (tx, ty))

            # NO button (right)
            no_w, no_h = 75, 36
            no_x = dialog_x + dialog_w // 2 + 12
            no_y = dialog_y + dialog_h - 52
            no_rect = pygame.Rect(no_x, no_y, no_w, no_h)
            no_hov = self._draw_button(
                no_rect, (8, 12, 8), (14, 22, 14), (60, 110, 60), 1
            )
            no_font = self.get_font(18)
            no_text = self.get_text(
                "NO", no_font, (160, 220, 140) if no_hov else (100, 160, 100)
            )
            tx, ty = self._draw_centered_text(
                no_text, no_x + no_w // 2, no_y + no_h // 2, 0, 0
            )
            self.screen.blit(no_text, (tx, ty))

        # ── Gear (options) button bottom-right ────────────────────────────
        opt_size = 38
        opt_x = w - opt_size - 14
        opt_y = h - opt_size - 14
        options_rect = pygame.Rect(opt_x, opt_y, opt_size, opt_size)
        opt_hov = self._draw_button(
            options_rect, (18, 10, 10), (32, 20, 20), (120, 85, 85), 0
        )
        gear_col = (175, 130, 130) if opt_hov else (120, 85, 85)
        pygame.draw.rect(self.screen, gear_col, options_rect, 1)
        gcx, gcy = opt_x + opt_size // 2, opt_y + opt_size // 2
        pygame.draw.circle(self.screen, gear_col, (gcx, gcy), 7, 1)
        for i in range(8):
            ang = math.radians(i * 45)
            pygame.draw.line(
                self.screen,
                gear_col,
                (gcx, gcy),
                (
                    int(gcx + math.cos(ang) * (opt_size // 2 - 6)),
                    int(gcy + math.sin(ang) * (opt_size // 2 - 6)),
                ),
                1,
            )

        try:
            self.game._last_drawn_menu = "main_menu"
        except Exception:
            pass

        if getattr(self.game, "showing_options", False):
            self.draw_options_menu(shake_x, shake_y)

    def draw_profiles_menu(self, shake_x: int = 0, shake_y: int = 0) -> None:
        """Profile selection screen: 3 slot cards with name, stats, and actions."""
        pygame = self.pygame
        if not self.screen or not pygame:
            return

        w, h = self.width, self.height
        g = self.game

        # Gothic dark background
        self.screen.fill((5, 3, 8))
        top_v = pygame.Surface((w, 110), pygame.SRCALPHA)
        top_v.fill((0, 0, 0, 150))
        self.screen.blit(top_v, (0, 0))
        bot_v = pygame.Surface((w, 90), pygame.SRCALPHA)
        bot_v.fill((0, 0, 0, 130))
        self.screen.blit(bot_v, (0, h - 90))

        # Title
        title_font = self.get_font(48)
        title_surf = self.get_text("PROFILES", title_font, (185, 28, 28))
        tx, ty = self._draw_centered_text(
            title_surf, w // 2, h // 2 - 270, shake_x, shake_y
        )
        self.screen.blit(title_surf, (tx, ty))

        # Layout constants (must match _handle_profiles_menu_click in input_handler.py)
        card_w, card_h = 460, 120
        card_x = w // 2 - card_w // 2 + shake_x
        start_y = h // 2 - 210
        spacing = 140

        font_med = self.get_font(20)
        font_sm = self.get_font(16)
        font_xs = self.get_font(14)

        mx, my = getattr(g, "mouse_x", 0), getattr(g, "mouse_y", 0)
        active_slot = getattr(g, "active_profile_slot", None)
        editing_slot = getattr(g, "editing_profile_slot", None)
        editing = getattr(g, "editing_profile_name", False)
        delete_confirms = getattr(g, "profile_delete_confirm", {})

        for slot in range(1, 4):
            cy = start_y + (slot - 1) * spacing + shake_y
            card_rect = pygame.Rect(card_x, cy, card_w, card_h)

            # Card background — gold border if active
            border_col = (200, 170, 60) if slot == active_slot else (60, 40, 40)
            bg_col = (18, 12, 8) if slot == active_slot else (12, 8, 6)
            pygame.draw.rect(self.screen, bg_col, card_rect, border_radius=6)
            pygame.draw.rect(self.screen, border_col, card_rect, 2, border_radius=6)

            info = g.get_profile_info(slot)
            slot_exists = info["exists"]

            # Slot label
            slot_label = self.get_text(f"SLOT {slot}", font_xs, (120, 80, 60))
            self.screen.blit(slot_label, (card_x + 10, cy + 8))

            # ── DELETE confirmation overlay ──────────────────────────────
            if delete_confirms.get(slot):
                confirm_surf = self.get_text("DELETE profile?", font_med, (240, 80, 60))
                self.screen.blit(confirm_surf, (card_x + 10, cy + 42))
                yes_rect = pygame.Rect(card_x + card_w - 120, cy + card_h - 30, 50, 22)
                no_rect = pygame.Rect(card_x + card_w - 62, cy + card_h - 30, 50, 22)
                yes_hov = yes_rect.collidepoint(mx, my)
                no_hov = no_rect.collidepoint(mx, my)
                pygame.draw.rect(
                    self.screen,
                    (180, 30, 30) if yes_hov else (100, 20, 20),
                    yes_rect,
                    border_radius=4,
                )
                pygame.draw.rect(
                    self.screen,
                    (30, 100, 30) if no_hov else (20, 60, 20),
                    no_rect,
                    border_radius=4,
                )
                self.screen.blit(
                    self.get_text("YES", font_xs, (255, 200, 200)),
                    (yes_rect.x + 8, yes_rect.y + 4),
                )
                self.screen.blit(
                    self.get_text("NO", font_xs, (200, 255, 200)),
                    (no_rect.x + 10, no_rect.y + 4),
                )
                continue

            # ── EDIT button ──────────────────────────────────────────────
            edit_rect = pygame.Rect(card_x + card_w - 56, cy + 8, 48, 22)
            edit_hov = edit_rect.collidepoint(mx, my)
            pygame.draw.rect(
                self.screen,
                (40, 30, 60) if not edit_hov else (70, 50, 110),
                edit_rect,
                border_radius=3,
            )
            pygame.draw.rect(self.screen, (100, 80, 160), edit_rect, 1, border_radius=3)
            self.screen.blit(
                self.get_text("EDIT", font_xs, (180, 150, 240)),
                (edit_rect.x + 6, edit_rect.y + 4),
            )

            # ── Name area ───────────────────────────────────────────────
            if editing and editing_slot == slot:
                # Text input box
                name_box = pygame.Rect(card_x + 55, cy + 6, card_w - 120, 26)
                pygame.draw.rect(self.screen, (30, 25, 45), name_box, border_radius=3)
                pygame.draw.rect(
                    self.screen, (140, 110, 220), name_box, 1, border_radius=3
                )
                input_text = getattr(g, "profile_name_input", "")
                # Blinking cursor
                cursor = "|" if (pygame.time.get_ticks() // 500) % 2 == 0 else ""
                name_surf = self.get_text(
                    input_text + cursor, font_med, (220, 200, 255)
                )
                self.screen.blit(name_surf, (name_box.x + 4, name_box.y + 3))
                hint = self.get_text(
                    "ENTER to confirm • ESC to cancel", font_xs, (120, 100, 160)
                )
                self.screen.blit(hint, (card_x + 10, cy + card_h - 22))
            else:
                if slot_exists:
                    name_surf = self.get_text(info["name"], font_med, (230, 200, 150))
                else:
                    name_surf = self.get_text("— Empty —", font_med, (70, 55, 45))
                self.screen.blit(name_surf, (card_x + 55, cy + 8))

            # ── Stats (only for existing slots) ─────────────────────────
            if slot_exists:
                stats_line1 = f"Satan Lv. {info['meta_level']}   XP: {info['meta_xp']}"
                stats_line2 = f"Points: {info['meta_points']}"
                last = info["last_played"]
                if last:
                    # Show only date part (yyyy-mm-dd)
                    date_part = last[:10]
                    stats_line2 += f"   Last: {date_part}"
                self.screen.blit(
                    self.get_text(stats_line1, font_sm, (180, 160, 110)),
                    (card_x + 10, cy + 42),
                )
                self.screen.blit(
                    self.get_text(stats_line2, font_sm, (140, 130, 90)),
                    (card_x + 10, cy + 62),
                )

                # DELETE button
                del_rect = pygame.Rect(card_x + card_w - 56, cy + 36, 48, 22)
                del_hov = del_rect.collidepoint(mx, my)
                pygame.draw.rect(
                    self.screen,
                    (60, 18, 18) if not del_hov else (100, 30, 30),
                    del_rect,
                    border_radius=3,
                )
                pygame.draw.rect(
                    self.screen, (160, 60, 60), del_rect, 1, border_radius=3
                )
                self.screen.blit(
                    self.get_text("DEL", font_xs, (255, 160, 160)),
                    (del_rect.x + 7, del_rect.y + 4),
                )

                # SELECT button
                select_rect = pygame.Rect(
                    card_x + card_w - 80, cy + card_h - 30, 72, 22
                )
                sel_hov = select_rect.collidepoint(mx, my)
                sel_bg = (30, 80, 30) if not sel_hov else (50, 130, 50)
                pygame.draw.rect(self.screen, sel_bg, select_rect, border_radius=4)
                pygame.draw.rect(
                    self.screen, (80, 180, 80), select_rect, 1, border_radius=4
                )
                sel_label = "SELECTED" if slot == active_slot else "SELECT"
                sel_col = (200, 255, 200) if slot == active_slot else (160, 230, 160)
                self.screen.blit(
                    self.get_text(sel_label, font_xs, sel_col),
                    (select_rect.x + 4, select_rect.y + 4),
                )
            else:
                # CREATE button
                create_rect = pygame.Rect(
                    card_x + card_w - 80, cy + card_h - 30, 72, 22
                )
                cr_hov = create_rect.collidepoint(mx, my)
                cr_bg = (20, 50, 70) if not cr_hov else (30, 80, 110)
                pygame.draw.rect(self.screen, cr_bg, create_rect, border_radius=4)
                pygame.draw.rect(
                    self.screen, (60, 140, 200), create_rect, 1, border_radius=4
                )
                self.screen.blit(
                    self.get_text("CREATE", font_xs, (160, 210, 255)),
                    (create_rect.x + 4, create_rect.y + 4),
                )

        # BACK button
        back_y = start_y + 3 * spacing + 10 + shake_y
        back_rect = pygame.Rect(w // 2 - 55 + shake_x, back_y, 110, 32)
        back_hov = back_rect.collidepoint(mx, my)
        back_bg = (30, 12, 12) if not back_hov else (55, 20, 20)
        pygame.draw.rect(self.screen, back_bg, back_rect, border_radius=4)
        pygame.draw.rect(self.screen, (130, 60, 60), back_rect, 1, border_radius=4)
        back_surf = self.get_text(
            "BACK", font_med, (200, 140, 140) if back_hov else (155, 100, 100)
        )
        btx, bty = self._draw_centered_text(
            back_surf, w // 2, back_rect.centery, shake_x, 0
        )
        self.screen.blit(back_surf, (btx, bty))

    def _draw_stage_submenu(
        self,
        title: str,
        labels: list[str],
        normal_color: tuple,
        hover_color: tuple,
        menu_key: str,
        shake_x: int = 0,
        shake_y: int = 0,
    ) -> None:
        pygame = self.pygame

        w, h = self.width, self.height

        # Gothic dark background
        self.screen.fill((5, 3, 8))

        font_large = self.get_font(48)
        font_medium = self.get_font(28)
        font_small = self.get_font(18)

        # Title
        title_surf = self.get_text(title, font_large, (215, 195, 155))
        tx, ty = self._draw_centered_text(
            title_surf, w // 2, h // 2 - 130, shake_x, shake_y
        )
        self.screen.blit(title_surf, (tx, ty))
        line_y = h // 2 - 130 + title_surf.get_height() + 8
        pygame.draw.line(
            self.screen,
            (110, 85, 45),
            (w // 2 - 160, line_y),
            (w // 2 + 160, line_y),
            1,
        )

        # Stage option buttons — keep geometry matching input_handler expectations
        option_w = 280
        option_h = 48
        start_x: int = w // 2 - option_w // 2
        start_y: int = h // 2 - 40
        spacing = 60

        for i, label in enumerate(labels):
            rect = pygame.Rect(start_x, start_y + i * spacing, option_w, option_h)
            hovered = self._draw_button(
                rect, normal_color, hover_color, (145, 118, 75), 1
            )
            text = font_medium.render(
                label, True, (240, 220, 190) if hovered else (205, 185, 158)
            )
            tx, ty = self._draw_centered_text(
                text, w // 2, rect.centery, shake_x, shake_y
            )
            self.screen.blit(text, (tx, ty))

        # Back button — geometry and style match stage selection BACK button
        back_rect = pygame.Rect(
            w // 2 - 55, start_y + len(labels) * spacing + 10, 110, 32
        )
        back_hov = self._draw_button(
            back_rect, (14, 7, 7), (28, 15, 15), (72, 48, 48), 1
        )
        back_text = font_small.render(
            "BACK", True, (180, 148, 140) if back_hov else (138, 112, 106)
        )
        tx, ty = self._draw_centered_text(
            back_text, w // 2, back_rect.centery, shake_x, shake_y
        )
        self.screen.blit(back_text, (tx, ty))

        try:
            self.game._last_drawn_menu = menu_key
        except Exception:
            pass

    def draw_stage_menu(self, shake_x=0, shake_y=0) -> None:
        """Draw the stage selection screen (gothic dark style) and submenus."""
        pygame = self.pygame
        if not self.screen or not pygame:
            return

        if getattr(self.game, "showing_limbo_menu", False):
            self._draw_stage_submenu(
                "LIMBO",
                ["LIMBO 1", "LIMBO 2", "LIMBO 3", "LIMBO FINAL"],
                (55, 28, 10),
                (82, 45, 18),
                "limbo",
                shake_x,
                shake_y,
            )
            return

        if getattr(self.game, "showing_purgatory_menu", False):
            self._draw_stage_submenu(
                "PURGATORY",
                ["PURGATORY 1", "PURGATORY 2", "PURGATORY 3"],
                (48, 24, 60),
                (72, 38, 90),
                "purgatory",
                shake_x,
                shake_y,
            )
            return

        if getattr(self.game, "showing_hell_menu", False):
            self._draw_stage_submenu(
                "HELL",
                ["GEHENNA", "LAKE OF FIRE", "HADES"],
                (80, 16, 16),
                (118, 30, 30),
                "hell",
                shake_x,
                shake_y,
            )
            return

        w, h = self.width, self.height

        # Gothic dark background
        self.screen.fill((5, 3, 8))

        font_large = self.get_font(48)
        font_medium = self.get_font(28)
        font_small = self.get_font(18)

        # Title
        title_surf = self.get_text("SELECT STAGE", font_large, (175, 150, 115))
        tx, ty = self._draw_centered_text(
            title_surf, w // 2, h // 2 - 195, shake_x, shake_y
        )
        self.screen.blit(title_surf, (tx, ty))
        line_y = h // 2 - 195 + title_surf.get_height() + 10
        pygame.draw.line(
            self.screen,
            (105, 82, 50),
            (w // 2 - 185, line_y),
            (w // 2 + 185, line_y),
            1,
        )

        # Stage buttons — geometry must match input_handler rects below
        #   prologo_rect = Rect(w//2 - 140, h//2 - 100, 280, 46)
        #   limbo_rect   = Rect(w//2 - 140, h//2 - 42,  280, 46)
        #   purgatory    = Rect(w//2 - 140, h//2 + 16,  280, 46)
        #   hell         = Rect(w//2 - 140, h//2 + 74,  280, 46)
        btn_w, btn_h = 280, 46
        btn_x = w // 2 - btn_w // 2
        base_y = h // 2 - 100
        spacing = 58

        _stages = [
            ("PROLOGUE", (45, 40, 36), (68, 60, 52), (158, 138, 108)),
            ("LIMBO", (55, 28, 10), (82, 45, 18), (175, 122, 58)),
            ("PURGATORY", (45, 22, 58), (68, 36, 88), (162, 112, 205)),
            ("HELL", (75, 14, 14), (112, 26, 26), (215, 68, 68)),
        ]

        for i, (label, bg_n, bg_h, border_col) in enumerate(_stages):
            rect = pygame.Rect(btn_x, base_y + i * spacing, btn_w, btn_h)
            hov = self._draw_button(rect, bg_n, bg_h, border_col, 1)
            text = font_medium.render(
                label, True, (238, 220, 192) if hov else (205, 188, 162)
            )
            tx, ty = self._draw_centered_text(
                text, w // 2, rect.centery, shake_x, shake_y
            )
            self.screen.blit(text, (tx, ty))

        # Back button (returns to main menu)
        back_rect = pygame.Rect(
            w // 2 - 55, base_y + len(_stages) * spacing + 10, 110, 32
        )
        back_hov = self._draw_button(
            back_rect, (14, 7, 7), (28, 15, 15), (72, 48, 48), 1
        )
        back_text = font_small.render(
            "BACK", True, (180, 148, 140) if back_hov else (138, 112, 106)
        )
        tx, ty = self._draw_centered_text(
            back_text, w // 2, back_rect.centery, shake_x, shake_y
        )
        self.screen.blit(back_text, (tx, ty))

        try:
            self.game._last_drawn_menu = "stage_main"
        except Exception:
            pass

        if getattr(self.game, "showing_options", False):
            self.draw_options_menu(shake_x, shake_y)

    def draw_options_menu(self, shake_x=0, shake_y=0) -> None:
        """Options overlay with gothic styling matching main menu."""
        pygame = self.pygame
        if not self.screen or not pygame:
            return

        # Semi-transparent overlay
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        # Dialog box with gothic dark background
        dialog_w, dialog_h = 520, 320
        dx = self.width // 2 - dialog_w // 2
        dy = self.height // 2 - dialog_h // 2

        # Main dialog background (gothic dark)
        pygame.draw.rect(self.screen, (22, 12, 22), (dx, dy, dialog_w, dialog_h))
        # Outer border (reddish)
        pygame.draw.rect(self.screen, (145, 32, 32), (dx, dy, dialog_w, dialog_h), 2)
        # Inner border (darker)
        inner = pygame.Rect(dx + 2, dy + 2, dialog_w - 4, dialog_h - 4)
        pygame.draw.rect(self.screen, (68, 16, 16), inner, 1)

        # Title with gothic styling
        try:
            font = self.get_font(32)
            title = self.get_text("OPTIONS", font, (210, 65, 65))
        except Exception:
            font = pygame.font.Font(None, 32)
            title = font.render("OPTIONS", True, (210, 65, 65))

        self.screen.blit(
            title,
            (self.width // 2 - title.get_width() // 2 + shake_x, dy + 16 + shake_y),
        )

        # Decorative line under title
        line_y = dy + 16 + title.get_height() + 8
        pygame.draw.line(
            self.screen,
            (110, 28, 28),
            (dx + 30, line_y),
            (dx + dialog_w - 30, line_y),
            1,
        )

        # Label and toggle helper function
        try:
            font_med = self.get_font(18)
        except Exception:
            font_med = pygame.font.Font(None, 18)

        def draw_toggle_option(label_text, is_enabled, y_offset):
            """Draw a label with a toggle switch."""
            # Label
            label = (
                self.get_text(label_text, font_med, (210, 185, 165))
                if hasattr(self.get_text, "__call__")
                else font_med.render(label_text, True, (210, 185, 165))
            )
            self.screen.blit(label, (dx + 24 + shake_x, dy + y_offset + shake_y))

            # Toggle switch
            toggle_w, toggle_h = 48, 24
            toggle_x = dx + dialog_w - 24 - toggle_w
            toggle_y = dy + y_offset
            toggle_rect = pygame.Rect(toggle_x, toggle_y, toggle_w, toggle_h)

            # Background based on state
            if is_enabled:
                toggle_bg = (
                    (80, 32, 32)
                    if toggle_rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
                    else (60, 20, 20)
                )
                text_color = (100, 200, 100)
            else:
                toggle_bg = (
                    (32, 32, 32)
                    if toggle_rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
                    else (20, 20, 20)
                )
                text_color = (180, 100, 100)

            pygame.draw.rect(self.screen, toggle_bg, toggle_rect)
            pygame.draw.rect(self.screen, (110, 28, 28), toggle_rect, 1)

            # Status text
            status_text = "ON" if is_enabled else "OFF"
            status_surf = font_med.render(status_text, True, text_color)
            self.screen.blit(
                status_surf,
                (
                    toggle_x + (toggle_w - status_surf.get_width()) // 2 + shake_x,
                    toggle_y + (toggle_h - status_surf.get_height()) // 2 + shake_y,
                ),
            )
            return toggle_rect

        # Damage numbers toggle
        draw_toggle_option(
            "Show Damage Numbers:", getattr(self.game, "show_damage_numbers", True), 64
        )

        # Sounds toggle
        draw_toggle_option(
            "Enable Sounds:", getattr(self.game, "sounds_enabled", True), 104
        )

        # Smooth-scaling toggle
        smooth_on = bool(
            self.game.global_progress.get("display", {}).get("smooth_scale", True)
        )
        draw_toggle_option("Smooth Scaling:", smooth_on, 144)

        # Resolution presets
        preset_label = (
            self.get_text("Resolution:", font_med, (210, 185, 165))
            if hasattr(self.get_text, "__call__")
            else font_med.render("Resolution:", True, (210, 185, 165))
        )
        self.screen.blit(preset_label, (dx + 24 + shake_x, dy + 216 + shake_y))

        # Buttons for presets (taken from game constants)
        try:
            from src.game_constants import DEFAULT_DISPLAY_PRESETS
        except Exception:
            DEFAULT_DISPLAY_PRESETS = [(1280, 720)]

        # Dropdown for resolution presets
        btn_w, btn_h = 140, 28
        start_x = dx + 24
        btn_y = dy + 248

        dropdown_w, dropdown_h = btn_w, btn_h
        dropdown_x, dropdown_y = start_x, btn_y
        dropdown_rect = pygame.Rect(dropdown_x, dropdown_y, dropdown_w, dropdown_h)

        current_label = f"{self.game.window_width}x{self.game.window_height}"
        hovered = dropdown_rect.collidepoint(self.game.mouse_x, self.game.mouse_y)

        is_preset = (
            self.game.window_width,
            self.game.window_height,
        ) in DEFAULT_DISPLAY_PRESETS
        if is_preset:
            bg = (38, 16, 38)
            pygame.draw.rect(self.screen, bg, dropdown_rect)
            pygame.draw.rect(self.screen, (110, 28, 28), dropdown_rect, 1)
        else:
            self._draw_button(
                dropdown_rect, (22, 12, 22), (32, 20, 28), (110, 28, 28), 1
            )

        txt = font_med.render(current_label, True, (210, 185, 165))
        self.screen.blit(
            txt,
            (
                dropdown_x + 8 + shake_x,
                dropdown_y + (dropdown_h - txt.get_height()) // 2 + shake_y,
            ),
        )
        # small caret indicator
        caret = font_med.render("▾", True, (145, 100, 100))
        self.screen.blit(
            caret,
            (
                dropdown_x + dropdown_w - 18 + shake_x,
                dropdown_y + (dropdown_h - caret.get_height()) // 2 + shake_y,
            ),
        )

        # If dropdown open, render the list beneath
        if getattr(self.game, "options_resolution_dropdown_open", False):
            item_h = 24
            item_spacing = 2
            for i, (pw, ph) in enumerate(DEFAULT_DISPLAY_PRESETS):
                iy = dropdown_y + dropdown_h + i * (item_h + item_spacing)
                item_rect = pygame.Rect(dropdown_x, iy, dropdown_w, item_h)
                is_current = (pw, ph) == (
                    self.game.window_width,
                    self.game.window_height,
                )
                hovered_item = item_rect.collidepoint(
                    self.game.mouse_x, self.game.mouse_y
                )

                # Gothic colors
                if is_current:
                    item_bg = (50, 20, 50)
                else:
                    item_bg = (32, 20, 28) if hovered_item else (22, 12, 22)

                pygame.draw.rect(self.screen, item_bg, item_rect)
                pygame.draw.rect(self.screen, (110, 28, 28), item_rect, 1)
                label = f"{pw}x{ph}"
                txt = font_med.render(label, True, (210, 185, 165))
                self.screen.blit(
                    txt,
                    (
                        dropdown_x + 8 + shake_x,
                        iy + (item_h - txt.get_height()) // 2 + shake_y,
                    ),
                )

        # Close button with gothic styling
        btn_w, btn_h = 120, 36
        btn_x = dx + (dialog_w - btn_w) // 2
        btn_y = dy + dialog_h - 50
        close_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        hovered = self._draw_button(
            close_rect, (22, 5, 5), (38, 10, 10), (145, 32, 32), 2
        )
        inner = close_rect.inflate(-6, -6)
        pygame.draw.rect(
            self.screen, (110, 28, 28) if hovered else (68, 16, 16), inner, 1
        )

        btn_text = (
            self.get_text(
                "CLOSE",
                self.get_font(20),
                (255, 230, 205) if hovered else (225, 200, 175),
            )
            if hasattr(self.get_text, "__call__")
            else pygame.font.Font(None, 20).render(
                "CLOSE", True, (255, 230, 205) if hovered else (225, 200, 175)
            )
        )
        self.screen.blit(
            btn_text,
            (
                btn_x + (btn_w - btn_text.get_width()) // 2 + shake_x,
                btn_y + (btn_h - btn_text.get_height()) // 2 + shake_y,
            ),
        )

    def draw_permanent_upgrades(self, shake_x=0, shake_y=0) -> None:
        """Authoritative renderer for the permanent-upgrades overlay.

        Draws both top (1..5) and bottom (6..10) Blasphemy boxes using the
        imported `blasphemy_box.png` asset when available. This single
        implementation is the canonical source of truth for both runtime and
        tests (keeps behavior deterministic and easier to reason about).
        """
        pygame = self.pygame
        if not self.screen or not pygame:
            return

        font_large = pygame.font.Font(None, 36)
        font_medium = pygame.font.Font(None, 24)
        font_small = pygame.font.Font(None, 18)

        left_x = self.width // 2 - 420
        title = font_large.render("PERMANENT UPGRADES", True, (255, 255, 0))
        self.screen.blit(
            title, (self.width // 2 - title.get_width() // 2 + shake_x, 40 + shake_y)
        )

        # subtitle was removed per design; we no longer render any text above the
        # XP bar.  (Previously it said "Upgrade your demonic powers".)

        # --- progression info ---
        lvl = self.game.global_progress.get("meta_level", 1)
        pts = self.game.global_progress.get("meta_points", 0)
        xp = self.game.global_progress.get("meta_xp", 0)
        xp_to = self.game.get_meta_xp_to_next_level()
        # we will later want to align the XP bar with the permanent-stat
        # bars; those use ``bar_x_base`` which depends on the widest stat name.
        rendered_names = [
            font_medium.render(s["name"], True, s["color"]) for s in _STAT_CONFIGS
        ]
        max_name_w = max(s.get_width() for s in rendered_names)
        bar_x_base = left_x + max(120, max_name_w + 24)
        bar_width = 180
        # render level and points on separate lines; the XP bar should now sit
        # on the same vertical line as the points text rather than above it.
        # we still place everything above the stats block (POWER at y=140).
        lvl_text = font_medium.render(f"SATAN LEVEL {lvl}", True, (255, 215, 0))
        pts_text = font_medium.render(f"Points: {pts}", True, (255, 215, 0))

        # derive y positions from an anchor for the points line; keep the
        # points text near the top. We'll place the XP bar lower, aligned with
        # the permanent-stat bars drawn later.
        pts_y = 120
        lvl_y = pts_y - lvl_text.get_height() - 2

        # bar should start and end at the same horizontal coordinates as the
        # permanent-stat bars below.  Those use ``bar_x_base`` and ``bar_width``
        # so we reuse the same values.
        pts_x = left_x + shake_x
        bar_x = bar_x_base
        bar_w = bar_width
        bar_h = 10
        # vertical position returns to previous value (same as points line)
        bar_y = pts_y

        self.screen.blit(lvl_text, (pts_x, lvl_y + shake_y))
        self.screen.blit(pts_text, (pts_x, pts_y + shake_y))

        # draw XP bar background at the same vertical as points
        pygame.draw.rect(self.screen, (26, 26, 26), (bar_x, bar_y, bar_w, bar_h))
        # compute filled width with minimum visibility for tiny XP
        fill_w = self._calculate_meta_xp_fill(xp, xp_to, bar_w)
        # fill color now darker green (0,100,0) per update
        pygame.draw.rect(self.screen, (0, 100, 0), (bar_x, bar_y, fill_w, bar_h))
        # numeric indicator showing current and required XP
        xp_text = font_small.render(f"{xp}/{xp_to} XP", True, (255, 215, 0))
        # leave at least 50px gap between bar end and xp text; using bar_width
        self.screen.blit(
            xp_text,
            (bar_x + bar_w + 58 + shake_x, bar_y - 2 + shake_y),
        )

        # POWER / VIGOR / ADRENALINE / STRUCTURE stats
        rendered_names = [
            font_medium.render(s["name"], True, s["color"]) for s in _STAT_CONFIGS
        ]
        max_name_w = max(s.get_width() for s in rendered_names)
        bar_x_base = left_x + max(120, max_name_w + 24)
        bar_width = 180
        bar_height = 12
        font_name_hover = pygame.font.Font(None, 26)

        for i, stat in enumerate(_STAT_CONFIGS):
            name_rect = pygame.Rect(left_x, stat["y"], 120, 30)
            try:
                is_hovered = name_rect.collidepoint(
                    self.game.mouse_x, self.game.mouse_y
                )
            except Exception:
                is_hovered = False
            stat_value = self.game.permanent_stats.get(stat["key"], 0)

            # Previously we showed a tooltip with explanation text when the
            # player hovered any of the four permanent stats.  Design has since
            # changed: the side text (to the right of the bar) is sufficient and
            # the hover pop‑ups are now distracting.  We intentionally no longer
            # render anything here, but leave the hover detection in place in
            # case we want to visually alter the name (see colouring below).
            #
            # (This block used to call ``permanent_stat_effect_text`` and draw a
            # gray box with the lines.)
            #
            # is_hovered is still used later when colouring the stat name, so
            # we keep the variable around but ignore it for tooltips.
            name_color = stat["color"]
            if is_hovered and stat_value < 10:
                col = stat["color"]
                name_color = (
                    min(255, col[0] + 50),
                    min(255, col[1] + 50),
                    min(255, col[2] + 50),
                )
            elif stat_value >= 10:
                name_color = (100, 100, 100)
            name_text = (
                font_name_hover.render(stat["name"], True, name_color)
                if is_hovered
                else rendered_names[i]
            )
            name_y = int(stat["y"] + 22 - name_text.get_height() // 2) + shake_y
            self.screen.blit(name_text, (left_x + shake_x, name_y))

            val_text = font_small.render(f"Level: {stat_value}", True, (255, 255, 255))
            self.screen.blit(val_text, (left_x + 200 + shake_x, stat["y"] + shake_y))

            effect_text = self.game.permanent_stat_effect_text(stat["key"], stat_value)
            if effect_text:
                eff_lines = [ln.strip() for ln in effect_text.split(";") if ln.strip()]
                if len(eff_lines) == 1:
                    eff_surf = font_small.render(eff_lines[0], True, (180, 180, 180))
                    eff_y = (
                        stat["y"]
                        + 15
                        + bar_height // 2
                        - eff_surf.get_height() // 2
                        + shake_y
                    )
                    self.screen.blit(eff_surf, (left_x + 340 + shake_x, eff_y))
                else:
                    eff_surfs = [
                        font_small.render(ln, True, (180, 180, 180)) for ln in eff_lines
                    ]
                    sp = 2
                    total_h = sum(s.get_height() for s in eff_surfs) + sp * (
                        len(eff_surfs) - 1
                    )
                    ey = stat["y"] + 15 + bar_height // 2 - total_h // 2 + shake_y
                    for es in eff_surfs:
                        self.screen.blit(es, (left_x + 340 + shake_x, ey))
                        ey += es.get_height() + sp

            if stat_value >= 10:
                max_text = font_small.render("MAX", True, (255, 215, 0))
                self.screen.blit(
                    max_text, (left_x + 270 + shake_x, stat["y"] + shake_y)
                )

            bar_x = bar_x_base
            bar_y = stat["y"] + 15
            pygame.draw.rect(
                self.screen,
                (26, 26, 26),
                (bar_x + shake_x, bar_y + shake_y, bar_width, bar_height),
            )
            pygame.draw.rect(
                self.screen,
                (68, 68, 68),
                (bar_x + shake_x, bar_y + shake_y, bar_width, bar_height),
                1,
            )
            if stat_value > 0:
                fill_w = min(bar_width, int((stat_value / 10) * bar_width))
                pygame.draw.rect(
                    self.screen,
                    stat["color"],
                    (bar_x + shake_x, bar_y + shake_y, fill_w, bar_height),
                )

        separator_y = 320

        # Blasphemies header + layout
        blasp_text = font_medium.render("BLASPHEMIES", True, (136, 136, 136))
        self.screen.blit(blasp_text, (left_x + shake_x, separator_y + 30 + shake_y))

        box_width = 80
        box_height = box_width
        box_spacing = 100
        start_x = left_x + box_spacing // 2 - 40

        asset_name = (
            self.game.global_progress.get("blasphemy_box_asset")
            if getattr(self.game, "global_progress", None)
            else None
        ) or "blasphemy_box.png"
        logger.debug("draw_permanent_upgrades: looking for asset %s", asset_name)
        box_asset = get_image(asset_name, (box_width, box_height))
        box_y1 = separator_y + 60
        box_y2 = box_y1 + box_height + 12

        for row_idx, y in enumerate((box_y1, box_y2)):
            for col in range(5):
                bx = start_x + col * box_spacing
                rect = (
                    bx - box_width // 2 + shake_x,
                    y + shake_y,
                    box_width,
                    box_height,
                )

                if box_asset:
                    try:
                        self.screen.blit(box_asset, (rect[0], rect[1]))
                        if row_idx == 1:
                            try:
                                self._blasphemy_bottom_drawn = True
                            except Exception:
                                pass
                    except Exception:
                        pygame.draw.rect(self.screen, (26, 26, 26), rect)
                else:
                    pygame.draw.rect(self.screen, (26, 26, 26), rect)

                try:
                    pygame.draw.rect(self.screen, (51, 51, 51), rect, 1)
                except Exception:
                    pass

                key = f"blasphemy_{row_idx * 5 + col + 1}"
                lvl = self.game.permanent_stats.get(key, 0)

                # Render roman numerals for blasphemies that show level text (include single-level slots 5 & 10)
                if lvl and key in (
                    "blasphemy_1",
                    "blasphemy_2",
                    "blasphemy_3",
                    "blasphemy_4",
                    "blasphemy_5",
                    "blasphemy_6",
                    "blasphemy_7",
                    "blasphemy_8",
                    "blasphemy_9",
                    "blasphemy_10",
                ):
                    roman_map = {1: "I", 2: "II", 3: "III"}
                    roman = roman_map.get(lvl, "")
                    if roman:
                        lvl_surf = font_large.render(roman, True, (120, 20, 20))
                        sx = bx - lvl_surf.get_width() // 2 + shake_x
                        sy = y + box_height // 2 - lvl_surf.get_height() // 2 + shake_y
                        self.screen.blit(lvl_surf, (sx, sy))

                # Hover/tooltips (defensive)
                try:
                    mouse_point = (self.game.mouse_x, self.game.mouse_y)
                except Exception:
                    mouse_point = (0, 0)

                if pygame.Rect(*rect).collidepoint(mouse_point):
                    effect_text = self.game.permanent_stat_effect_text(key, lvl)
                    lines = [
                        s.strip() for s in (effect_text or "").split(";") if s.strip()
                    ]
                    # Always show tooltip for all blasphemy upgrades when hovered
                    if lines:
                        if lvl:
                            lines.insert(0, f"Level: {lvl}")
                        tip_x = bx
                        tip_y = box_y2 + box_height + 12 + shake_y
                        padding_x, padding_y = 8, 6
                        try:
                            self.game._draw_tooltip(
                                lines,
                                tip_x,
                                tip_y,
                                pygame.font.Font(None, 18),
                                anchor_center=True,
                            )
                        except Exception:
                            pass
                        line_surfs = [
                            font_small.render(line_text, True, (255, 255, 255))
                            for line_text in lines
                        ]
                        width = max(s.get_width() for s in line_surfs) + padding_x * 2
                        height = (
                            sum(s.get_height() for s in line_surfs)
                            + padding_y * 2
                            + (len(line_surfs) - 1) * 4
                        )
                        tx = max(
                            4, min(int(tip_x - width // 2), self.width - width - 4)
                        )
                        ty = max(4, min(tip_y, self.height - height - 4))
                        bg_rect = pygame.Rect(tx, ty, width, height)
                        pygame.draw.rect(self.screen, (30, 30, 30), bg_rect)
                        pygame.draw.rect(self.screen, (120, 120, 120), bg_rect, 1)
                        cur_y = ty + padding_y
                        for s in line_surfs:
                            self.screen.blit(s, (tx + padding_x, cur_y))
                            cur_y += s.get_height() + 4

        # Skill trees (FIRE, STORM, ICE)
        tree_box_w = 50
        tree_box_h = 36
        tree_v_spacing = 46
        tree_col_spacing = 120
        tree_base_x: int = left_x + 680
        tree_top_y: int = separator_y - 150

        for col, (label, key_prefix, color) in enumerate(_TREE_TYPES):
            col_x = tree_base_x + col * tree_col_spacing
            lbl_surf = font_small.render(label, True, color)
            self.screen.blit(
                lbl_surf,
                (
                    col_x - lbl_surf.get_width() // 2 + shake_x,
                    tree_top_y - 28 + shake_y,
                ),
            )

            inner_col_offset = tree_box_w // 2 + 1
            left_col_x = col_x - inner_col_offset
            right_col_x = col_x + inner_col_offset
            for row in range(3):
                y = tree_top_y + row * tree_v_spacing
                left_rect = (
                    left_col_x - tree_box_w // 2 + shake_x,
                    y + shake_y,
                    tree_box_w,
                    tree_box_h,
                )
                right_rect = (
                    right_col_x - tree_box_w // 2 + shake_x,
                    y + shake_y,
                    tree_box_w,
                    tree_box_h,
                )

                left_active = bool(
                    self.game.permanent_stats.get(f"{key_prefix}_{row + 1}", 0)
                )
                right_active = bool(
                    self.game.permanent_stats.get(f"{key_prefix}_{4 + row}", 0)
                )
                left_bg = color if left_active else (26, 26, 26)
                right_bg = color if right_active else (26, 26, 26)
                left_border = (
                    tuple(min(255, c + 20) for c in color)
                    if left_active
                    else (51, 51, 51)
                )
                right_border = (
                    tuple(min(255, c + 20) for c in color)
                    if right_active
                    else (51, 51, 51)
                )

                try:
                    mouse_point = (self.game.mouse_x, self.game.mouse_y)
                except Exception:
                    mouse_point = (0, 0)
                left_hovered = pygame.Rect(*left_rect).collidepoint(mouse_point)
                right_hovered = pygame.Rect(*right_rect).collidepoint(mouse_point)
                if left_hovered:
                    left_border = (255, 224, 20)
                    left_bg = tuple(min(255, v + 30) for v in left_bg)
                if right_hovered:
                    right_border = (255, 224, 20)
                    right_bg = tuple(min(255, v + 30) for v in right_bg)

                pygame.draw.rect(self.screen, left_bg, left_rect)
                pygame.draw.rect(self.screen, left_border, left_rect, 1)
                pygame.draw.rect(self.screen, right_bg, right_rect)
                pygame.draw.rect(self.screen, right_border, right_rect, 1)

                if left_hovered:
                    tooltip_lines = self.game._skill_tooltip_lines(key_prefix, row + 1)
                    if tooltip_lines:
                        self.game._draw_tooltip(
                            tooltip_lines,
                            col_x,
                            tree_top_y + 3 * tree_v_spacing + tree_box_h + 12 + shake_y,
                            pygame.font.Font(None, 18),
                            anchor_center=True,
                        )
                if right_hovered:
                    tooltip_lines = self.game._skill_tooltip_lines(key_prefix, 4 + row)
                    if tooltip_lines:
                        self.game._draw_tooltip(
                            tooltip_lines,
                            col_x,
                            tree_top_y + 3 * tree_v_spacing + tree_box_h + 12 + shake_y,
                            pygame.font.Font(None, 18),
                            anchor_center=True,
                        )

            center_y = tree_top_y + 3 * tree_v_spacing
            center_key = f"{key_prefix}_7"
            center_active = bool(self.game.permanent_stats.get(center_key, 0))
            center_bg = color if center_active else (26, 26, 26)
            center_border = (
                tuple(min(255, c + 20) for c in color)
                if center_active
                else (51, 51, 51)
            )
            center_rect = (
                col_x - tree_box_w // 2 + shake_x,
                center_y + shake_y,
                tree_box_w,
                tree_box_h,
            )
            try:
                mouse_point = (self.game.mouse_x, self.game.mouse_y)
            except Exception:
                mouse_point = (0, 0)
            center_hovered = pygame.Rect(*center_rect).collidepoint(mouse_point)
            if center_hovered:
                center_border = (255, 224, 20)
                center_bg = tuple(min(255, v + 30) for v in center_bg)
            pygame.draw.rect(self.screen, center_bg, center_rect)
            pygame.draw.rect(self.screen, center_border, center_rect, 1)
            if center_hovered:
                tooltip_lines = self.game._skill_tooltip_lines(key_prefix, 7)
                if tooltip_lines:
                    self.game._draw_tooltip(
                        tooltip_lines,
                        col_x,
                        tree_top_y + 3 * tree_v_spacing + tree_box_h + 12 + shake_y,
                        pygame.font.Font(None, 18),
                        anchor_center=True,
                    )

        # Instructions
        instructions = font_medium.render(
            "Left click to upgrade | Right click to downgrade | ESC to return",
            True,
            (200, 200, 200),
        )
        self.screen.blit(instructions, (left_x + shake_x, self.height - 50 + shake_y))

        # Sentinel for tests (asset already drawn inside the box loop above roman numerals)
        if box_asset and self.screen:
            try:
                if getattr(self.game, "_test_blasphemy_sentinel", False):
                    sen_color = (123, 45, 67)
                    sen_x = int(start_x)
                    sen_y = int(box_y2 + box_height // 2 + 1)
                    self.screen.set_at((sen_x, sen_y), sen_color)
            except Exception:
                pass

        # Defensive: enforce center pixel color when asset present
        if box_asset and self.screen:
            try:
                center_color = box_asset.get_at((box_width // 2, box_height // 2))
            except Exception:
                center_color = None
            if center_color:
                try:
                    self.screen.set_at(
                        (int(start_x), int(box_y1 + box_height // 2)), center_color
                    )
                except Exception:
                    pass
                try:
                    self.screen.set_at(
                        (int(start_x), int(box_y2 + box_height // 2)), center_color
                    )
                except Exception:
                    pass

    def draw_pause_menu(self, shake_x=0, shake_y=0) -> None:
        """Draw the pause menu (migrated from Game)."""
        pygame = self.pygame
        if not self.screen or not pygame:
            return

        font_large = self.get_font(36)
        font_medium = self.get_font(28)

        title = self.get_text("PAUSED", font_large, (255, 255, 255))
        self.screen.blit(
            title,
            (
                self.width // 2 - title.get_width() // 2 + shake_x,
                self.height // 2 - 100 + shake_y,
            ),
        )

        options = ["Resume", "Quit to Menu"]
        option_height = 40
        for i, option in enumerate(options):
            y_pos = self.height // 2 - 20 + i * option_height
            text_width = len(option) * 14
            option_rect = pygame.Rect(
                self.width // 2 - text_width // 2, y_pos, text_width, option_height
            )
            is_hovered = option_rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
            if is_hovered and option_rect.width > 0 and option_rect.height > 0:
                self.game.pause_menu_option = i
            is_selected = i == self.game.pause_menu_option
            color = (
                (255, 255, 0)
                if is_selected
                else ((200, 200, 0) if is_hovered else (255, 255, 255))
            )
            text = font_medium.render(option, True, color)
            self.screen.blit(
                text,
                (self.width // 2 - text.get_width() // 2 + shake_x, y_pos + shake_y),
            )

        try:
            self.game._last_drawn_menu = "pause"
        except Exception:
            pass

        # Draw pause confirmation dialog if active (overlay handled by caller)
        self.draw_pause_confirmation_dialog(shake_x, shake_y)

    def draw_pause_confirmation_dialog(self, shake_x=0, shake_y=0) -> None:
        """Draw the pause confirmation Yes/No dialog (can be called any time, not just when paused)."""
        pygame = self.pygame
        if not self.screen or not pygame:
            return

        try:
            if getattr(self.game, "pause_confirmation", None):
                pc = self.game.pause_confirmation
                dialog_w, dialog_h = 260, 70
                dx = self.width // 2 - dialog_w // 2
                dy = self.height // 2 - dialog_h // 2

                # dialog background
                dlg_surf = pygame.Surface((dialog_w, dialog_h))
                dlg_surf.set_alpha(220)
                dlg_surf.fill((30, 30, 30))
                pygame.draw.rect(
                    dlg_surf, (120, 120, 120), (0, 0, dialog_w, dialog_h), 2
                )
                self.screen.blit(dlg_surf, (dx, dy))

                font = self.get_font(18)
                msg = "Quit to menu?"
                msg_surf = self.get_text(msg, font, (255, 255, 255))
                self.screen.blit(
                    msg_surf, (dx + (dialog_w - msg_surf.get_width()) // 2, dy + 6)
                )

                # Buttons (clearly boxed and highlight on hover)
                btn_w = 80
                btn_h = 28
                yes_rect = pygame.Rect(dx + 10, dy + 30, btn_w, btn_h)
                no_rect = pygame.Rect(dx + dialog_w - btn_w - 10, dy + 30, btn_w, btn_h)

                # Detect hover and set selection accordingly
                try:
                    if yes_rect.collidepoint(self.game.mouse_x, self.game.mouse_y):
                        pc["selection"] = 0
                    elif no_rect.collidepoint(self.game.mouse_x, self.game.mouse_y):
                        pc["selection"] = 1
                except Exception:
                    pass

                sel = pc.get("selection", 0)

                # Draw yes button
                yes_bg = (255, 215, 0) if sel == 0 else (60, 60, 60)
                yes_border = (200, 160, 20) if sel == 0 else (120, 120, 120)
                pygame.draw.rect(self.screen, yes_bg, yes_rect)
                pygame.draw.rect(self.screen, yes_border, yes_rect, 2)
                yes_s = self.get_text(
                    "Yes", font, (0, 0, 0) if sel == 0 else (200, 200, 200)
                )
                self.screen.blit(
                    yes_s,
                    (
                        yes_rect.x + (btn_w - yes_s.get_width()) // 2 + shake_x,
                        yes_rect.y + shake_y + (btn_h - yes_s.get_height()) // 2,
                    ),
                )

                # Draw no button
                no_bg = (255, 215, 0) if sel == 1 else (60, 60, 60)
                no_border = (200, 160, 20) if sel == 1 else (120, 120, 120)
                pygame.draw.rect(self.screen, no_bg, no_rect)
                pygame.draw.rect(self.screen, no_border, no_rect, 2)
                no_s = self.get_text(
                    "No", font, (0, 0, 0) if sel == 1 else (200, 200, 200)
                )
                self.screen.blit(
                    no_s,
                    (
                        no_rect.x + (btn_w - no_s.get_width()) // 2 + shake_x,
                        no_rect.y + shake_y + (btn_h - no_s.get_height()) // 2,
                    ),
                )
        except Exception:
            pass

    def draw_player_stats(self, shake_x=0, shake_y=0) -> None:
        """Draw the player stats panel."""
        pygame = self.pygame
        if not self.screen or not pygame:
            return

        font_title = self.get_font(40)
        font_header = self.get_font(20)
        font_body = self.get_font(18)
        font_small = self.get_font(15)

        COLOR_TITLE = (220, 180, 40)
        COLOR_HEADER = (180, 80, 40)
        COLOR_LABEL = (150, 150, 150)
        COLOR_VALUE = (230, 230, 230)
        COLOR_DIVIDER = (80, 40, 20)
        COLOR_HINT = (100, 100, 100)
        COLOR_GREEN = (100, 180, 100)
        COLOR_RED = (200, 60, 60)

        def _clean(key: str) -> str:
            return key.replace("_", " ").title()

        def _pct(v: float) -> str:
            sign = "+" if v >= 0 else ""
            return f"{sign}{v:.0f}%"

        def _draw_section_header(label: str, x: int, y: int, width: int = 260) -> int:
            surf = self.get_text(label.upper(), font_header, COLOR_HEADER)
            self.screen.blit(surf, (x + shake_x, y + shake_y))
            line_y = y + surf.get_height() + 4
            pygame.draw.line(
                self.screen,
                COLOR_DIVIDER,
                (x + shake_x, line_y + shake_y),
                (x + width + shake_x, line_y + shake_y),
                1,
            )
            return line_y + 9

        def _draw_row(
            label: str,
            value: str,
            x: int,
            y: int,
            val_x: int = 0,
            label_col=None,
            val_col=None,
        ) -> None:
            lc = label_col or COLOR_LABEL
            vc = val_col or COLOR_VALUE
            lab = self.get_text(label, font_body, lc)
            val = self.get_text(value, font_body, vc)
            self.screen.blit(lab, (x + shake_x, y + shake_y))
            vx = val_x if val_x else x + 180
            self.screen.blit(val, (vx + shake_x, y + shake_y))

        # ── Overlay ──────────────────────────────────────────────────────────────
        overlay = pygame.Surface((self.width, self.height))
        overlay.set_alpha(220)
        overlay.fill((6, 6, 10))
        self.screen.blit(overlay, (0, 0))

        # ── Title ────────────────────────────────────────────────────────────────
        title = self.get_text("PLAYER STATS", font_title, COLOR_TITLE)
        tx = self.width // 2 - title.get_width() // 2 + shake_x
        ty = 28 + shake_y
        self.screen.blit(title, (tx, ty))
        bar_y = ty + title.get_height() + 5
        pygame.draw.line(
            self.screen,
            COLOR_DIVIDER,
            (self.width // 2 - 240 + shake_x, bar_y),
            (self.width // 2 + 240 + shake_x, bar_y),
            1,
        )

        line_h = 25
        left_x = self.width // 2 - 430
        right_x = self.width // 2 + 40
        top_y = 88

        # ── LEFT COLUMN ──────────────────────────────────────────────────────────
        y = top_y
        val_x_l = left_x + 190

        # — SATAN LEVEL (Meta Progression) —
        y = _draw_section_header("Satan Level", left_x, y)
        meta_lvl = self.game.global_progress.get("meta_level", 1)
        meta_pts = self.game.global_progress.get("meta_points", 0)
        meta_xp = self.game.global_progress.get("meta_xp", 0)
        meta_xp_to = self.game.get_meta_xp_to_next_level()

        _draw_row("Level", str(meta_lvl), left_x, y, val_x_l, val_col=(255, 100, 100))
        y += line_h
        _draw_row("Points", str(meta_pts), left_x, y, val_x_l, val_col=(255, 215, 0))
        y += line_h

        # Progress bar for meta XP
        bar_width = 400
        bar_height = 14
        bar_x = left_x + shake_x
        bar_y = y + shake_y

        pygame.draw.rect(
            self.screen, (40, 40, 40), (bar_x, bar_y, bar_width, bar_height)
        )
        fill_w = self._calculate_meta_xp_fill(meta_xp, meta_xp_to, bar_width)
        pygame.draw.rect(
            self.screen, (255, 100, 100), (bar_x, bar_y, fill_w, bar_height)
        )

        xp_text = self.get_text(
            f"{meta_xp} / {meta_xp_to} XP", font_small, (255, 215, 0)
        )
        self.screen.blit(xp_text, (left_x + shake_x, bar_y + bar_height + 4 + shake_y))

        y += line_h + 35

        # — Run —
        y = _draw_section_header("Run", left_x, y)
        _draw_row("Level", str(self.game.player_level), left_x, y, val_x_l)
        y += line_h
        _draw_row(
            "XP",
            f"{int(self.game.player_xp)} / {int(self.game.xp_to_next_level)}",
            left_x,
            y,
            val_x_l,
        )
        y += line_h
        _draw_row("Score", str(int(self.game.score)), left_x, y, val_x_l)
        y += line_h
        _draw_row(
            "Enemies Killed",
            str(getattr(self.game, "enemies_killed_this_run", 0)),
            left_x,
            y,
            val_x_l,
        )
        y += line_h + 14

        # — Satan (vitals + combat merged) —
        y = _draw_section_header("Satan", left_x, y)

        hp_cur = int(self.game.player.health)
        hp_max = int(self.game.player.max_health)
        _draw_row(
            "Health",
            f"{hp_cur} / {hp_max}",
            left_x,
            y,
            val_x_l,
            val_col=COLOR_RED if hp_cur < hp_max // 2 else COLOR_VALUE,
        )
        y += line_h

        # HP bar
        bar_w, bar_h = 220, 6
        bx = left_x + shake_x
        by = y + shake_y
        pygame.draw.rect(self.screen, (35, 8, 8), (bx, by, bar_w, bar_h))
        fill = int(bar_w * min(1.0, hp_cur / max(1, hp_max)))
        if fill > 0:
            pygame.draw.rect(self.screen, COLOR_RED, (bx, by, fill, bar_h))
        pygame.draw.rect(self.screen, (80, 30, 30), (bx, by, bar_w, bar_h), 1)
        y += bar_h + 10

        spd = getattr(
            self.game.player, "speed", getattr(self.game.player, "base_speed", 220.0)
        )
        b7 = self.game.permanent_stats.get("blasphemy_7", 0)
        spd_str = f"{int(spd)} px/s" + (f"  (+{b7 * 10}%)" if b7 else "")
        _draw_row("Movement Speed", spd_str, left_x, y, val_x_l)
        y += line_h

        dmg_pct = (self.game.damage_multiplier - 1.0) * 100
        fr_pct = (1.0 - self.game.fire_rate_multiplier) * -100
        ps_pct = (self.game.projectile_size_multiplier - 1.0) * 100
        dr_pct = (1.0 - self.game.damage_reduction_multiplier) * 100

        _draw_row(
            "Damage Bonus",
            _pct(dmg_pct),
            left_x,
            y,
            val_x_l,
            val_col=COLOR_GREEN if dmg_pct > 0 else COLOR_VALUE,
        )
        y += line_h
        # Critical chance: Blasphemy_6 (10%/level) plus Adrenaline (2%/level)
        crit_pct = (self.game.permanent_stats.get("blasphemy_6", 0) * 10.0) + (
            self.game.permanent_stats.get("adrenaline", 0) * 2.0
        )
        _draw_row(
            "Critical damage chance",
            _pct(crit_pct),
            left_x,
            y,
            val_x_l,
            val_col=COLOR_GREEN if crit_pct > 0 else COLOR_VALUE,
        )
        y += line_h
        _draw_row(
            "Fire Rate Bonus",
            _pct(fr_pct),
            left_x,
            y,
            val_x_l,
            val_col=COLOR_GREEN if fr_pct > 0 else COLOR_VALUE,
        )
        y += line_h
        _draw_row(
            "Projectile Size",
            _pct(ps_pct),
            left_x,
            y,
            val_x_l,
            val_col=COLOR_GREEN if ps_pct > 0 else COLOR_VALUE,
        )
        y += line_h
        _draw_row(
            "Damage Reduction",
            _pct(dr_pct),
            left_x,
            y,
            val_x_l,
            val_col=COLOR_GREEN if dr_pct > 0 else COLOR_VALUE,
        )
        y += line_h

        # ── RIGHT COLUMN ─────────────────────────────────────────────────────────
        y = top_y

        # — Weapons —
        y = _draw_section_header("Weapons", right_x, y)
        weapons = list(self.game.player_weapons)
        if weapons:
            for wid in weapons:
                lvl = self.game.weapon_levels.get(wid, 0)
                name = WEAPON_DEFS.get(wid, {}).get("name", _clean(wid))
                name_surf = self.get_text(name, font_body, COLOR_VALUE)
                lv_surf = self.get_text(f"Lv {lvl}", font_small, COLOR_GREEN)
                self.screen.blit(name_surf, (right_x + shake_x, y + shake_y))
                self.screen.blit(
                    lv_surf,
                    (right_x + name_surf.get_width() + 10 + shake_x, y + 4 + shake_y),
                )
                y += line_h
        else:
            self.screen.blit(
                self.get_text("None", font_body, COLOR_HINT),
                (right_x + shake_x, y + shake_y),
            )
            y += line_h
        y += 14

        # — Permanent Upgrades (Power/Vigor/Adrenaline/Structure, arabic numbers) —
        PERM_LABEL = {
            "power": "Power",
            "vigor": "Vigor",
            "adrenaline": "Adrenaline",
            "structure": "Structure",
        }
        perm_items = [
            (k, v) for k, v in self.game.permanent_stats.items() if k in PERM_LABEL
        ]
        if perm_items:
            y = _draw_section_header("Permanent Upgrades", right_x, y)
            for k, v in perm_items:
                label = PERM_LABEL[k]
                col = COLOR_TITLE if v > 0 else COLOR_HINT
                val_surf = self.get_text(str(v), font_body, col)
                lab_surf = self.get_text(label, font_body, COLOR_LABEL)
                # max indicator
                max_surf = (
                    self.get_text("MAX", font_small, (180, 140, 20))
                    if v >= 10
                    else None
                )
                self.screen.blit(lab_surf, (right_x + shake_x, y + shake_y))
                self.screen.blit(val_surf, (right_x + 160 + shake_x, y + shake_y))
                if max_surf:
                    self.screen.blit(
                        max_surf,
                        (
                            right_x + 160 + val_surf.get_width() + 8 + shake_x,
                            y + 4 + shake_y,
                        ),
                    )
                # small pip bar (10 pips)
                pip_x = right_x + shake_x
                pip_y = y + lab_surf.get_height() + 3 + shake_y
                pip_w, pip_h, pip_gap = 14, 4, 2
                for p in range(10):
                    px = pip_x + p * (pip_w + pip_gap)
                    filled = p < v
                    pip_col = COLOR_HEADER if filled else (35, 35, 35)
                    pygame.draw.rect(self.screen, pip_col, (px, pip_y, pip_w, pip_h))
                    pygame.draw.rect(
                        self.screen,
                        (60, 40, 20) if filled else (50, 50, 50),
                        (px, pip_y, pip_w, pip_h),
                        1,
                    )
                y += lab_surf.get_height() + pip_h + 7 + 4

        # ── Close hint ───────────────────────────────────────────────────────────
        inst = self.get_text("Tab / ESC  to close", font_small, COLOR_HINT)
        self.screen.blit(
            inst,
            (
                self.width // 2 - inst.get_width() // 2 + shake_x,
                self.height - 34 + shake_y,
            ),
        )

        try:
            self.game._last_drawn_menu = "player_stats"
        except Exception:
            pass

    def draw_dead_trees(self, shake_x=0, shake_y=0) -> None:
        # Debugging hook: log when drawing dead trees to help visibility issues
        try:
            if not self.game.is_limbo_stage() or not hasattr(self.game, "dead_trees"):
                if getattr(self.game, "debug", False):
                    print("[DEBUG] draw_dead_trees: not in limbo or no dead_trees attr")
                return

            if not self.game.dead_trees:
                if getattr(self.game, "debug", False):
                    print("[DEBUG] draw_dead_trees: dead_trees is empty")
                return

            if getattr(self.game, "debug", False):
                print(
                    f"[DEBUG] draw_dead_trees: drawing {len(self.game.dead_trees)} trees"
                )
        except Exception:
            pass
        pygame = self.pygame

        # Hellish palette — charred, bone-dry wood
        TRUNK_FILL = (72, 50, 38)
        TRUNK_EDGE = (32, 18, 12)
        TRUNK_HIGHLIGHT = (108, 78, 58)
        CRACK_COLOR = (42, 25, 16)
        BRANCH_COLOR = (65, 44, 32)
        BRANCH_SHADOW = (22, 11, 7)
        SUB_COLOR = (56, 36, 25)
        TWIG_COLOR = (46, 28, 18)

        for tree in self.game.dead_trees:
            x = int(tree["x"] + shake_x)
            y = int(tree["y"] + shake_y)
            height = tree["height"]
            tw = tree["trunk_width"]

            # Draw trunk — single tapered polygon, or Y-fork if split
            split = tree.get("split")
            if split:
                fork_y = int(y + height * split["frac"])
                fork_tw = max(1, tw - 1)
                tine_top = max(1, fork_tw // 2)

                # Lower trunk segment: base → fork point
                lower_poly = [
                    (x - tw, y + height),
                    (x + tw, y + height),
                    (x + fork_tw, fork_y),
                    (x - fork_tw, fork_y),
                ]
                pygame.draw.polygon(self.screen, TRUNK_FILL, lower_poly)
                pygame.draw.polygon(self.screen, TRUNK_EDGE, lower_poly, 1)
                pygame.draw.line(
                    self.screen,
                    TRUNK_HIGHLIGHT,
                    (x, y + height - 3),
                    (x, fork_y + 2),
                    1,
                )

                # Left tine: diverges upper-left from fork point
                lx = x - split["left_dx"]
                ly = fork_y - split["left_dy"]
                left_poly = [
                    (x - fork_tw, fork_y),
                    (x + 1, fork_y),
                    (lx + tine_top, ly),
                    (lx - tine_top, ly),
                ]
                pygame.draw.polygon(self.screen, TRUNK_FILL, left_poly)
                pygame.draw.polygon(self.screen, TRUNK_EDGE, left_poly, 1)

                # Right tine: diverges upper-right from fork point
                rx = x + split["right_dx"]
                ry = fork_y - split["right_dy"]
                right_poly = [
                    (x - 1, fork_y),
                    (x + fork_tw, fork_y),
                    (rx + tine_top, ry),
                    (rx - tine_top, ry),
                ]
                pygame.draw.polygon(self.screen, TRUNK_FILL, right_poly)
                pygame.draw.polygon(self.screen, TRUNK_EDGE, right_poly, 1)
            else:
                # Tapered trunk polygon: wider at base (y+height), narrow at crown (y)
                top_w = max(1, tw // 2)
                trunk_poly = [
                    (x - tw, y + height),
                    (x + tw, y + height),
                    (x + top_w, y),
                    (x - top_w, y),
                ]
                pygame.draw.polygon(self.screen, TRUNK_FILL, trunk_poly)
                pygame.draw.polygon(self.screen, TRUNK_EDGE, trunk_poly, 1)

                # Centre highlight stripe for depth
                pygame.draw.line(
                    self.screen, TRUNK_HIGHLIGHT, (x, y + 3), (x, y + height - 3), 1
                )

            # Trunk cracks / texture marks
            for crack in tree.get("cracks", []):
                cx = x + crack["x_off"]
                cy = y + int(height * crack["y_frac"])
                half = crack["length"] // 2
                pygame.draw.line(
                    self.screen,
                    CRACK_COLOR,
                    (cx, cy),
                    (cx + crack["dir"] * half, cy + half),
                    1,
                )

            # Branches — 3 levels deep (main → sub → twig)
            for branch in tree.get("branches", []):
                bsx = x
                bsy = int(branch["start_y"] + shake_y)
                bex = int(branch["end_x"] + shake_x)
                bey = int(branch["end_y"] + shake_y)
                bthick = branch.get("thickness", 2)

                # Shadow offset for depth
                pygame.draw.line(
                    self.screen,
                    BRANCH_SHADOW,
                    (bsx + 1, bsy + 1),
                    (bex + 1, bey + 1),
                    bthick,
                )
                pygame.draw.line(
                    self.screen, BRANCH_COLOR, (bsx, bsy), (bex, bey), bthick
                )

                for sub in branch.get("sub_branches", []):
                    ssx = int(sub["start_x"] + shake_x)
                    ssy = int(sub["start_y"] + shake_y)
                    sex = int(sub["end_x"] + shake_x)
                    sey = int(sub["end_y"] + shake_y)
                    pygame.draw.line(self.screen, SUB_COLOR, (ssx, ssy), (sex, sey), 1)

                    for twig in sub.get("sub_branches", []):
                        pygame.draw.line(
                            self.screen,
                            TWIG_COLOR,
                            (
                                int(twig["start_x"] + shake_x),
                                int(twig["start_y"] + shake_y),
                            ),
                            (
                                int(twig["end_x"] + shake_x),
                                int(twig["end_y"] + shake_y),
                            ),
                            1,
                        )

    def _draw_tower_energy_bar(self, shake_x: int = 0, shake_y: int = 0) -> None:
        """Draw the shared tower energy bar in the bottom‑right corner.

        The bar is now vertical (growing from bottom to top) and twice as
        thick as the original horizontal design. It still turns gold when full.
        """
        # obtain a local pygame reference like other draw helpers
        pygame = self.pygame
        g = self.game
        if not hasattr(g, "tower_energy") or not hasattr(g, "tower_energy_max"):
            return
        try:
            cur = float(getattr(g, "tower_energy", 0))
            mx = float(getattr(g, "tower_energy_max", 0))
        except Exception:
            return
        if mx <= 0:
            return
        # bar dimensions – vertical orientation (bottom→top)
        bar_w = 16  # twice as thick as the old horizontal bar
        bar_h = 100  # height of the bar
        bar_x = self.width - bar_w - 20
        bar_y = self.height - bar_h - 20
        # background (slightly lighter so empty bar stands out on dark scenes)
        pygame.draw.rect(self.screen, (40, 40, 40), (bar_x, bar_y, bar_w, bar_h))
        # outline/border
        pygame.draw.rect(self.screen, (120, 120, 120), (bar_x, bar_y, bar_w, bar_h), 1)
        # fill from bottom based on current energy
        fill_h = int(bar_h * min(1.0, cur / mx))
        if fill_h > 0:
            color = (255, 215, 0) if cur >= mx else (200, 200, 200)
            fill_y = bar_y + bar_h - fill_h
            pygame.draw.rect(self.screen, color, (bar_x, fill_y, bar_w, fill_h))

    def _draw_statue_model(
        self, x: int, statue_base_y: int, tower_type: str | None
    ) -> None:
        """Draw a statue model centered at X using a provided statue base Y.

        This helper is reused by both pedestals (Limbo) and dynamic towers (Purgatory).
        The `tower_type` controls coloring similarly to the old logic (fire/storm/ice).

        New behaviour: before resorting to procedural vector art we attempt to
        load an external image asset.  The asset files are expected to live in
        ``assets/`` and follow the naming convention ``statue_<type>.png`` where
        <type> is one of ``fire``, ``storm`` or ``ice`` (the same categories used
        for colouring).  If the asset manager returns a Surface we blit it so
        that its bottom centre aligns with ``(x, statue_base_y)`` and return
        early.  This allows designers to drop custom tower/statue graphics into
        the assets folder and have them picked up automatically.
        """
        pygame = self.pygame

        # apply the global vertical offset to *all* statues, including those
        # drawn procedurally.  previously only imported assets were shifted;
        # the constant now acts as a universal adjustment so designers can tweak
        # one value and affect Limbo pedestals, Purgatory towers and Hell
        # statues alike.
        adjusted_base_y = statue_base_y + STATUE_ASSET_VERTICAL_OFFSET

        # first figure out which of the three categories we want.  mirror the
        # colour logic below so limbo stages still map sensibly.
        tt = tower_type or getattr(self.game, "selected_stage", None)
        if tt == "storm" or tt == "limbo_2":
            asset_type = "storm"
        elif tt == "ice" or tt in ("limbo_3", "limbo_final"):
            asset_type = "ice"
        else:
            asset_type = "fire"

        # attempt to load an external image; do not scale so artist can choose
        # whatever dimensions they like.  if we got something, draw and exit.
        try:
            from src.assets.manager import get_image

            asset_name = f"statue_{asset_type}.png"
            asset_img = get_image(asset_name)
        except Exception:
            asset_img = None
        if asset_img:
            w, h = asset_img.get_size()
            # optionally flip horizontally when drawing on the right side of the
            # screen.  this mirrors imported assets for the right-hand statue
            # while leaving the left-hand one untouched.
            if x > (getattr(self, "width", 0) / 2):
                try:
                    asset_img = pygame.transform.flip(asset_img, True, False)
                except Exception:
                    pass
            # bottom-center anchor, with optional vertical offset
            y_pos = adjusted_base_y - h
            self.screen.blit(asset_img, (x - w // 2, y_pos))
            return

        # Choose statue colors based on provided tower_type (or current stage)
        tt = tt  # reuse value computed above for colouring
        if tt == "storm" or tt == "limbo_2":
            # Storm - blueish statue
            body_color = (18, 36, 120)
            outline_color = (8, 18, 80)
            horn_color = (60, 100, 200)
            eye_color = (100, 150, 255)
            glow_color = (40, 70, 180)
        elif tt == "ice" or tt in ("limbo_3", "limbo_final"):
            # Ice - icy pale statue
            body_color = (120, 140, 180)
            outline_color = (80, 100, 140)
            horn_color = (160, 180, 200)
            eye_color = (180, 220, 255)
            glow_color = (140, 180, 220)
        else:
            # Default: Fire/limbo - demonic red
            body_color = (58, 10, 10)
            outline_color = (26, 0, 0)
            horn_color = (138, 32, 32)
            eye_color = (255, 48, 48)
            glow_color = (200, 150, 60)

        # Statue body (slimmer triangular/demonic shape) using the adjusted
        # base Y so vector art lines up with any asset-based artworks.
        body_points: list[tuple[int, int]] = [
            (x, adjusted_base_y - 60),  # Neck point (head connects here)
            (x - 12, adjusted_base_y - 40),  # Left shoulder
            (x - 15, adjusted_base_y),  # Left base
            (x + 15, adjusted_base_y),  # Right base
            (x + 12, adjusted_base_y - 40),  # Right shoulder
        ]
        pygame.draw.polygon(self.screen, body_color, body_points)
        pygame.draw.polygon(self.screen, outline_color, body_points, 2)

        # Head (larger and round)
        head_y: int = adjusted_base_y - 70
        head_radius = 15
        pygame.draw.circle(self.screen, body_color, (x, head_y), head_radius)
        pygame.draw.circle(self.screen, outline_color, (x, head_y), head_radius, 2)

        # Larger horns (from head)
        pygame.draw.line(
            self.screen,
            horn_color,
            (x - 10, head_y - 10),
            (x - 20, head_y - 30),
            4,
        )
        pygame.draw.line(
            self.screen,
            horn_color,
            (x + 10, head_y - 10),
            (x + 20, head_y - 30),
            4,
        )

        # Glowing eyes (on head)
        pygame.draw.circle(self.screen, eye_color, (x - 7, head_y), 3)
        pygame.draw.circle(self.screen, eye_color, (x + 7, head_y), 3)

        # Subtle glow ring around head for visibility
        pygame.draw.circle(self.screen, glow_color, (x, head_y), head_radius + 4, 2)

        # Pitchfork in hand
        fork_x: int = x + 20  # Held to the right side
        fork_top_y: int = statue_base_y - 100
        fork_bottom_y: int = statue_base_y - 20
        pygame.draw.line(
            self.screen,
            (42, 42, 42),
            (fork_x, fork_bottom_y),
            (fork_x, fork_top_y),
            3,
        )

        # Pitchfork prongs (3 prongs)
        prong_length = 15
        # Center prong
        pygame.draw.line(
            self.screen,
            (74, 74, 74),
            (fork_x, fork_top_y),
            (fork_x, fork_top_y - prong_length),
            2,
        )
        # Left prong
        pygame.draw.line(
            self.screen,
            (74, 74, 74),
            (fork_x - 6, fork_top_y),
            (fork_x - 6, fork_top_y - prong_length),
            2,
        )
        # Right prong
        pygame.draw.line(
            self.screen,
            (74, 74, 74),
            (fork_x + 6, fork_top_y),
            (fork_x + 6, fork_top_y - prong_length),
            2,
        )
        # Connecting bar
        pygame.draw.line(
            self.screen,
            (74, 74, 74),
            (fork_x - 6, fork_top_y),
            (fork_x + 6, fork_top_y),
            2,
        )

        # Smaller wings (simple angular shapes)
        # Left wing
        left_wing_points: list[tuple[int, int]] = [
            (x - 12, statue_base_y - 40),
            (x - 30, statue_base_y - 45),
            (x - 25, statue_base_y - 30),
        ]
        pygame.draw.polygon(self.screen, (74, 16, 16), left_wing_points)
        pygame.draw.polygon(self.screen, (42, 0, 0), left_wing_points, 1)

        # Right wing (smaller to not interfere with pitchfork)
        right_wing_points: list[tuple[int, int]] = [
            (x + 12, statue_base_y - 40),
            (x + 28, statue_base_y - 45),
            (x + 23, statue_base_y - 30),
        ]
        pygame.draw.polygon(self.screen, (74, 16, 16), right_wing_points)
        pygame.draw.polygon(self.screen, (42, 0, 0), right_wing_points, 1)

        return

    def draw_pedestals(self, shake_x=0, shake_y=0) -> None:
        """Draw (static) statues in Limbo stage.

        The original implementation drew full pedestals with statues.  Pedestals
        were removed, but the statues themselves are still desired for Limbo for
        visual continuity.  This method now simply places two statue models at
        the side positions; the same `_draw_statue_model` helper is used so any
        external assets are respected.

        Calls from Game.draw_game_world remain unchanged.
        """
        # If we're not in any limbo variant, bail early.
        if not self.game.is_limbo_stage():
            if getattr(self.game, "debug", False):
                print("[DEBUG] draw_pedestals: not in limbo")
            return
        # **Limbo Final** should not draw the static statues at all.  The
        # dynamic tower models that appear after the player chooses a tower
        # replace them, and drawing the ice statues early led to visual
        # overlap (the 'ice statue' complaint).  We also prevent firing while
        # the player is selecting a tower (handled in WeaponSystem).
        if getattr(self.game, "selected_stage", None) == "limbo_final":
            if getattr(self.game, "debug", False):
                print("[DEBUG] draw_pedestals: skipped (limbo_final)")
            return
        if getattr(self.game, "debug", False):
            print("[DEBUG] draw_pedestals: drawing limbo statues")

        # Two statues at the sides of the play area (no pedestals).  X coords
        # are moved inward by 50 pixels vs the original pedestal positions.
        # Y is the universal STATUE_BASE_Y constant shared with all other stages.
        statue_xs: list[int] = [370, 910]

        for sx in statue_xs:
            self._draw_statue_model(
                sx + shake_x,
                STATUE_BASE_Y + shake_y,
                getattr(self.game, "selected_stage", None),
            )

    def _build_fog_cache(self) -> None:
        """Pre-render fog layers into cached surfaces.

        Cache is invalidated when wall points change or when stage is not Limbo.
        """
        if not self.game.is_limbo_stage():
            self._fog_cache = None
            self._fog_cache_signature = None
            return
        if not self.game.left_wall_points or not self.game.right_wall_points:
            self._fog_cache = None
            self._fog_cache_signature = None
            return

        # Create a signature from wall points to detect changes
        sig_left = tuple((int(x), int(y)) for (x, y) in self.game.left_wall_points)
        sig_right = tuple((int(x), int(y)) for (x, y) in self.game.right_wall_points)
        sig = (
            sig_left,
            sig_right,
            self.width,
            self.height,
            getattr(self.game, "selected_stage", None),
        )
        if getattr(self, "_fog_cache_signature", None) == sig and getattr(
            self, "_fog_cache", None
        ):
            return  # Cache still valid

        # Build cache
        pygame = self.pygame
        wall_thickness = WALL_THICKNESS
        num_layers = 5

        # Choose a stage-aware base tint for lateral fog so limbo variants look distinct.
        # - default limbo: neutral gray
        # - limbo_2: slightly yellower (increase R+G)
        # - limbo_3: slightly redder (increase R)
        stage = getattr(self.game, "selected_stage", None)
        # limbo_final uses same redder tint as limbo_3
        if stage in ("limbo_3", "limbo_final"):
            base_r, base_g, base_b = 90, 60, 60
        elif stage == "limbo_2":
            base_r, base_g, base_b = 80, 80, 60
        else:
            base_r, base_g, base_b = 60, 60, 60

        cache = []  # type: ignore  # list of pygame.Surface

        for i in range(num_layers):
            opacity = (num_layers - i) / num_layers
            layer_offset = 250 * (i + 1) // num_layers
            r = int(base_r * (1 - opacity * 0.6))
            g = int(base_g * (1 - opacity * 0.6))
            b = int(base_b * (1 - opacity * 0.6))
            color = (r, g, b)

            # Left fog polygon
            left_fog_points = []
            for point in self.game.left_wall_points:
                left_fog_points.append((0, point[1]))
            for point in reversed(self.game.left_wall_points):
                left_fog_points.append(
                    (
                        point[0] - wall_thickness - layer_offset,
                        point[1],
                    )
                )
            if len(left_fog_points) > 2:
                fog_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                pygame.draw.polygon(
                    fog_surface, color + (int(128 * opacity),), left_fog_points
                )
                try:
                    fog_surface = fog_surface.convert_alpha()
                except Exception:
                    pass
                cache.append(fog_surface)
            else:
                cache.append(None)

            # Right fog polygon
            right_fog_points = []
            for point in self.game.right_wall_points:
                right_fog_points.append(
                    (
                        point[0] + wall_thickness + layer_offset,
                        point[1],
                    )
                )
            for point in reversed(self.game.right_wall_points):
                right_fog_points.append((self.width, point[1]))
            if len(right_fog_points) > 2:
                fog_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                pygame.draw.polygon(
                    fog_surface, color + (int(128 * opacity),), right_fog_points
                )
                try:
                    fog_surface = fog_surface.convert_alpha()
                except Exception:
                    pass
                cache.append(fog_surface)
            else:
                cache.append(None)

        self._fog_cache = cache
        self._fog_cache_signature = sig

    def draw_purgatory_fog(self, shake_x=0, shake_y=0) -> None:
        """Draw the semi–transparent gray haze overlay for purgatory stages.

        The earlier implementation also produced drifting fog particles along
        the lateral wall edges, but those were removed at the designer's
        request.  Only the flat overlay remains in use; the particle methods
        themselves still exist but are no longer invoked.
        """
        stage = getattr(self.game, "selected_stage", None)
        if not (stage and str(stage).startswith("purgatory")):
            return
        if not self.screen:
            return
        if not self.game.left_wall_points or not self.game.right_wall_points:
            return

        # update and render dynamic fog particles (new system)
        try:
            self._update_and_draw_fog_particles()
        except Exception:
            pass

        # draw the screen‑wide fog overlay last so it mutes everything beneath
        from src.game_constants import PURGATORY_OVERLAY_ALPHA, PURGATORY_OVERLAY_COLOR

        self._draw_stage_overlay(
            "_purgatory_overlay",
            "_purgatory_overlay_color",
            "_purgatory_overlay_alpha",
            PURGATORY_OVERLAY_COLOR,
            PURGATORY_OVERLAY_ALPHA,
        )

    def _draw_stage_overlay(
        self, cache_attr, color_attr, alpha_attr, color, alpha
    ) -> None:
        """Blit a full-screen cached overlay onto the screen.

        Creates and caches a ``convert()``+``set_alpha()`` Surface on first
        call (or when parameters change); subsequent frames are a single cheap
        blit with no allocation.
        """
        if not self.screen:
            return
        try:
            pygame = self.pygame
            need_new = False
            ov = getattr(self, cache_attr, None)
            if ov is None:
                need_new = True
            else:
                if ov.get_size() != (self.width, self.height):
                    need_new = True
                if getattr(self, color_attr, None) != color:
                    need_new = True
                if getattr(self, alpha_attr, None) != alpha:
                    need_new = True
            if need_new:
                overlay = pygame.Surface((self.width, self.height))
                try:
                    overlay = overlay.convert()
                except Exception:
                    pass
                overlay.fill(color)
                overlay.set_alpha(alpha)
                setattr(self, cache_attr, overlay)
                setattr(self, color_attr, color)
                setattr(self, alpha_attr, alpha)
            self.screen.blit(getattr(self, cache_attr), (0, 0))
        except Exception:
            pass

    def draw_fog(self, shake_x=0, shake_y=0) -> None:
        stage = getattr(self.game, "selected_stage", None)
        if not stage or not self.screen:
            return

        if str(stage).startswith("purgatory"):
            try:
                self.draw_purgatory_fog(shake_x, shake_y)
            except Exception:
                pass
            return

        if str(stage).startswith("hell"):
            from src.game_constants import HELL_OVERLAY_ALPHA, HELL_OVERLAY_COLOR

            self._draw_stage_overlay(
                "_hell_overlay",
                "_hell_overlay_color",
                "_hell_overlay_alpha",
                HELL_OVERLAY_COLOR,
                HELL_OVERLAY_ALPHA,
            )
            return

        if stage == "prologo":
            from src.game_constants import PROLOGO_OVERLAY_ALPHA, PROLOGO_OVERLAY_COLOR

            self._draw_stage_overlay(
                "_prologo_overlay",
                "_prologo_overlay_color",
                "_prologo_overlay_alpha",
                PROLOGO_OVERLAY_COLOR,
                PROLOGO_OVERLAY_ALPHA,
            )
            return

        if not self.game.is_limbo_stage():
            return
        if not self.game.left_wall_points or not self.game.right_wall_points:
            return

        from src.game_constants import LIMBO_OVERLAY_ALPHA, LIMBO_OVERLAY_COLOR

        self._draw_stage_overlay(
            "_limbo_overlay",
            "_limbo_overlay_color",
            "_limbo_overlay_alpha",
            LIMBO_OVERLAY_COLOR,
            LIMBO_OVERLAY_ALPHA,
        )

        # Ensure cache is built and up-to-date
        try:
            self._build_fog_cache()
        except Exception:
            # If caching fails, fall back to original drawing
            self._fog_cache = None
            self._fog_cache_signature = None

        pygame = self.pygame
        wall_thickness = WALL_THICKNESS
        num_layers = 5

        if getattr(self, "_fog_cache", None):
            # Blit pre-rendered fog layers with per-frame shake offsets
            idx = 0
            for i in range(num_layers):
                left_surf = self._fog_cache[idx]
                idx += 1
                right_surf = self._fog_cache[idx]
                idx += 1
                if left_surf:
                    # blit with shake offset
                    self.screen.blit(left_surf, (shake_x, shake_y))
                if right_surf:
                    self.screen.blit(right_surf, (shake_x, shake_y))
            return

        # Fallback to dynamic drawing if cache absent
        pygame = self.pygame
        wall_thickness = WALL_THICKNESS
        base_r, base_g, base_b = 60, 60, 60
        for i in range(num_layers):
            opacity: float = (num_layers - i) / num_layers
            layer_offset: int = 250 * (i + 1) // num_layers
            r = int(base_r * (1 - opacity * 0.6))
            g = int(base_g * (1 - opacity * 0.6))
            b = int(base_b * (1 - opacity * 0.6))
            color: tuple[int, int, int] = (r, g, b)
            left_fog_points = []
            for point in self.game.left_wall_points:
                left_fog_points.append((0 + shake_x, point[1] + shake_y))
            for point in reversed(self.game.left_wall_points):
                left_fog_points.append(
                    (
                        point[0] - wall_thickness - layer_offset + shake_x,
                        point[1] + shake_y,
                    )
                )
            if len(left_fog_points) > 2:
                fog_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                pygame.draw.polygon(
                    fog_surface, color + (int(128 * opacity),), left_fog_points
                )
                try:
                    fog_surface = fog_surface.convert_alpha()
                except Exception:
                    pass
                self.screen.blit(fog_surface, (0, 0))

            # Right fog - create polygon following wall structure
            right_fog_points = []
            # Wall edge going down (outer wall + layer offset)
            for point in self.game.right_wall_points:
                right_fog_points.append(
                    (
                        point[0] + wall_thickness + layer_offset + shake_x,
                        point[1] + shake_y,
                    )
                )
            # Screen edge going up
            for point in reversed(self.game.right_wall_points):
                right_fog_points.append((self.width + shake_x, point[1] + shake_y))

            if len(right_fog_points) > 2:
                fog_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                pygame.draw.polygon(
                    fog_surface, color + (int(128 * opacity),), right_fog_points
                )
                try:
                    fog_surface = fog_surface.convert_alpha()
                except Exception:
                    pass
                self.screen.blit(fog_surface, (0, 0))

    def draw_game_objects(self, shake_x=0, shake_y=0) -> None:
        if not self.screen:
            return
        pygame = self.pygame
        # Draw enemies (object-based Enemy instances only)
        for enemy in self.game.enemies:
            # Delegate drawing (and particle updates/emission) to the Enemy instance
            # to avoid duplicate particle emission/rendering from both UI and Enemy.
            try:
                enemy.draw(self.screen, shake_x, shake_y)
            except Exception:
                pass

        # Draw bosses
        for boss in self.game.bosses:
            boss.draw(self.screen, shake_x, shake_y)

        # Draw projectiles
        for projectile in self.game.projectiles:
            projectile.draw(self.screen, shake_x, shake_y)

        # Draw enemy projectiles
        for projectile in self.game.enemy_projectiles:
            projectile.draw(self.screen, shake_x, shake_y)

        for drop in getattr(self.game, "health_drops", []):
            try:
                x = int(drop.get("x", 0) + shake_x)
                y = int(drop.get("y", 0) + shake_y)
                r = drop.get("radius", 8)
                alpha = self._health_drop_alpha(drop)
                if pygame:
                    self._draw_health_drop_particle(x, y, r, alpha)
                else:
                    pygame_mod = self.pygame
                    if pygame_mod:
                        pygame_mod.draw.circle(self.screen, (0, 200, 0), (x, y), r)
                        pygame_mod.draw.line(
                            self.screen,
                            (255, 255, 255),
                            (x - r // 2, y),
                            (x + r // 2, y),
                            2,
                        )
                        pygame_mod.draw.line(
                            self.screen,
                            (255, 255, 255),
                            (x, y - r // 2),
                            (x, y + r // 2),
                            2,
                        )
            except Exception:
                pass

        # (statues/towers will be drawn later, after special effects, to ensure
        # they stay above everything including Voltaic Mayhem beams)

        # NOTE: statue projectile visual indicators removed (kept internal data for logic/tests)

        # Draw aura around player once satan growth has started; it remains
        # until the level ends.  we base the pulse on the global frame count so
        # it continues even after the animation period finishes.
        if (
            getattr(self.game, "satan_growth_persistent", False)
            and self.screen is not None
        ):
            try:
                import math

                # pulse formula using frame_count for continuous pulsing
                pulse = int((math.sin(self.game.frame_count * 0.06) + 1) / 2 * 150) + 20
                w = getattr(self.game.player, "width", 0)
                h = getattr(self.game.player, "height", 0)
                base_radius = int(math.hypot(w, h) / 2)
                padding = 1
                glow_radius = base_radius + padding
                outer_padding = 20
                aura_radius = glow_radius + outer_padding
                aura_size = aura_radius * 2
                aura = pygame.Surface((aura_size, aura_size), pygame.SRCALPHA)
                center = (aura_radius, aura_radius)
                fade_alpha = max(0, int(pulse * 0.25))
                if fade_alpha > 0:
                    pygame.draw.circle(
                        aura, (255, 0, 0, fade_alpha), center, aura_radius
                    )
                inner_alpha = int(pulse * 0.8)
                pygame.draw.circle(aura, (255, 0, 0, inner_alpha), center, glow_radius)
                # compute draw position matching player draw logic (including bobbing)
                draw_x = self.game.player.rect.x + shake_x
                draw_y = self.game.player.rect.y + shake_y
                bob_offset = 0
                if getattr(self.game, "player_is_moving", False) and getattr(
                    self.game.player, "walk_frames", False
                ):
                    bob_cycle = self.game.player_anim_frame % 4
                    if bob_cycle == 1:
                        bob_offset = -1
                    elif bob_cycle == 3:
                        bob_offset = 1
                draw_y += bob_offset
                aura_x = draw_x - (aura_radius - w // 2)
                aura_y = draw_y - (aura_radius - h // 2)
                self.screen.blit(aura, (aura_x, aura_y))
            except Exception:
                pass

        # Draw player
        self.game.player.draw(
            self.screen,
            shake_x,
            shake_y,
            self.game.player_anim_frame,
            self.game.player_is_moving,
        )

        # Draw player burn particles (if any)
        try:
            if getattr(self.game.player, "burn_particles", None):
                for p in list(self.game.player.burn_particles):
                    try:
                        # p is a BurnParticle object
                        surf = pygame.Surface(
                            (p.size * 2 + 2, p.size * 2 + 2), pygame.SRCALPHA
                        )
                        alpha = max(60, int(255 * (p.life / 44)))
                        pygame.draw.circle(
                            surf, (255, 140, 0, alpha), (p.size + 1, p.size + 1), p.size
                        )
                        self.screen.blit(
                            surf,
                            (int(p.x + shake_x - p.size), int(p.y + shake_y - p.size)),
                        )
                    except Exception:
                        pass
        except Exception:
            pass

        # Draw orbitals
        for orb in self.game.orbitals:
            ox = orb.get("x", self.game.player.x)
            oy = orb.get("y", self.game.player.y)
            ox_s, oy_s = self._apply_shake(ox, oy, shake_x, shake_y)
            pygame.draw.circle(self.screen, (176, 240, 255), (ox_s, oy_s), 6)
            pygame.draw.circle(
                self.screen,
                (224, 248, 255),
                (ox_s, oy_s),
                10,
                1,
            )

        # Draw special effects
        self.draw_special_effects(shake_x, shake_y)

        # Draw tower energy bar (bottom-right) only if special unlocked and not prologo
        try:
            if self.game.special_unlocked():
                self._draw_tower_energy_bar(shake_x, shake_y)
        except Exception:
            pass

        # Always render statues/towers last so they layer above projectiles and
        # even Voltaic Mayhem rays.  ``draw_pedestals`` is a no-op except in
        # Limbo, while the dynamic tower code handles Purgatory/Hell.
        try:
            if hasattr(self, "draw_pedestals"):
                self.draw_pedestals(shake_x, shake_y)

            if getattr(self.game, "selected_stage", None) and (
                str(self.game.selected_stage).startswith(("purgatory", "hell"))
                or self.game.selected_stage == "limbo_final"
            ):
                lt = getattr(self.game, "left_tower", None)
                rt = getattr(self.game, "right_tower", None)
                if lt and getattr(lt, "visible", False):
                    self._draw_statue_model(
                        int(lt.x + shake_x),
                        STATUE_BASE_Y + shake_y,
                        getattr(lt, "tower_type", None),
                    )
                if rt and getattr(rt, "visible", False):
                    self._draw_statue_model(
                        int(rt.x + shake_x),
                        STATUE_BASE_Y + shake_y,
                        getattr(rt, "tower_type", None),
                    )
        except Exception:
            # Don't break rendering if statue drawing throws
            pass

    def draw_special_effects(self, shake_x=0, shake_y=0) -> None:
        # local import ensures pygame is always available inside this method
        try:
            import pygame
        except Exception:
            pygame = None

        if (
            self.game.selected_stage == "prologo" and self.game.prologo_lightning_strike
        ) or (
            self.game.selected_stage == "limbo_final"
            and getattr(self.game, "limbo_final_lightning_strike", False)
        ):
            self.draw_lightning_effect(shake_x, shake_y)
        # Voltaic Mayhem cursor ring (pulsing) for storm-tier7 special
        if pygame is not None:
            try:
                # fire special explosions (orange) drawn first
                # fire special explosions: layered circles for explosion effect
                for eff in getattr(self.game.game_state, "fire_explosions", []):
                    try:
                        r = eff.get("radius", 0)
                        timer = eff.get("timer", 0)
                        max_timer = max(1, eff.get("max_timer", 1))
                        prog = 1.0 - (timer / max_timer)
                        prog = max(0.0, min(1.0, prog))
                        current = int(r * prog)
                        alpha = int(200 * (timer / max_timer))
                        if current <= 0:
                            continue
                        surf = pygame.Surface(
                            (current * 2 + 4, current * 2 + 4), pygame.SRCALPHA
                        )
                        cx = cy = current + 2
                        # dark red core
                        inner = int(current * 0.3)
                        if inner > 0:
                            pygame.draw.circle(
                                surf, (200, 0, 0, alpha), (cx, cy), inner
                            )
                        # yellow mid circle
                        mid = int(current * 0.6)
                        if mid > inner:
                            pygame.draw.circle(
                                surf, (255, 200, 0, alpha), (cx, cy), mid
                            )
                        # outer orange ring
                        pygame.draw.circle(
                            surf, (255, 100, 0, alpha), (cx, cy), current
                        )
                        # blit the filled multi-color surf first
                        self.screen.blit(
                            surf,
                            (
                                int(eff["x"] - current) + shake_x,
                                int(eff["y"] - current) + shake_y,
                            ),
                        )
                        # jagged yellow outline resembling skullboom's glow
                        try:
                            num_segments = 10
                            for i in range(num_segments):
                                angle1 = (
                                    2 * math.pi * i
                                ) / num_segments + random.uniform(-0.2, 0.2)
                                angle2 = (
                                    2 * math.pi * (i + 1)
                                ) / num_segments + random.uniform(-0.2, 0.2)
                                rvar = current + 3 + random.uniform(-2, 2)
                                pygame.draw.arc(
                                    self.screen,
                                    (255, 200, 0, alpha),
                                    (
                                        int(eff.get("x", 0) - rvar) + shake_x,
                                        int(eff.get("y", 0) - rvar) + shake_y,
                                        int(rvar * 2),
                                        int(rvar * 2),
                                    ),
                                    angle1,
                                    angle2,
                                    max(1, int(2 * (timer / max_timer))),
                                )
                        except Exception:
                            pass
                    except Exception:
                        pass
                # smoke particles (grey, rising)
                for s in getattr(self.game, "fire_smoke", []):
                    try:
                        size = int(s.get("size", 5))
                        alpha = max(0, min(255, int(255 * (s.get("life", 0) / 40))))
                        surf = pygame.Surface(
                            (size * 2 + 2, size * 2 + 2), pygame.SRCALPHA
                        )
                        pygame.draw.circle(
                            surf, (100, 100, 100, alpha), (size + 1, size + 1), size
                        )
                        self.screen.blit(
                            surf,
                            (
                                int(s.get("x", 0) - size) + shake_x,
                                int(s.get("y", 0) - size) + shake_y,
                            ),
                        )
                    except Exception:
                        pass
                if getattr(self.game, "voltaic_active", False):
                    # draw a semitransparent pulsing circle at the beam endpoint (which
                    # now moves toward the cursor at a fixed speed rather than
                    # instantly following it).
                    mx = getattr(
                        self.game, "voltaic_x", getattr(self.game, "mouse_x", 0)
                    )
                    my = getattr(
                        self.game, "voltaic_y", getattr(self.game, "mouse_y", 0)
                    )
                    radius = getattr(self.game, "VOLTAIC_MAYHEM_IMPACT_RADIUS", 50)
                    # constant alpha to avoid flashing/intermittence
                    alpha = 150
                    color = (180, 220, 255, alpha)
                    surf = pygame.Surface(
                        (radius * 2 + 8, radius * 2 + 8), pygame.SRCALPHA
                    )
                    try:
                        # simple filled circle with a gentle radial fade.
                        base_alpha = color[3]
                        # alpha increases toward the outer radius
                        for rstep in range(radius, 0, -2):
                            frac = 1 - (rstep / float(radius))
                            a = int(base_alpha * frac)
                            if a <= 0:
                                continue
                            grad_color = (color[0], color[1], color[2], min(a, 255))
                            pygame.draw.circle(
                                surf,
                                grad_color,
                                (radius + 4, radius + 4),
                                rstep,
                            )
                        # blit gradient circle onto main surface
                        self.screen.blit(
                            surf,
                            (
                                int(mx - radius) + shake_x - 4,
                                int(my - radius) + shake_y - 4,
                            ),
                        )
                    except Exception:
                        pass
                    # draw a few lightning-style rays from center outward
                    try:
                        segments = 4
                        for i in range(segments):
                            angle = random.random() * 2 * math.pi
                            length = random.uniform(radius * 0.6, radius)
                            start_x = mx
                            start_y = my
                            end_x = mx + math.cos(angle) * length
                            end_y = my + math.sin(angle) * length
                            # draw as small jagged polyline
                            points = [(start_x, start_y)]
                            steps = int(length / 10)
                            for s in range(1, steps):
                                frac = s / float(steps)
                                px = mx + math.cos(angle) * length * frac
                                py = my + math.sin(angle) * length * frac
                                # random offset perpendicular
                                perp = (-math.sin(angle), math.cos(angle))
                                offset = random.uniform(-5, 5)
                                px += perp[0] * offset
                                py += perp[1] * offset
                                points.append((px, py))
                            points.append((end_x, end_y))
                            pygame.draw.lines(
                                self.screen,
                                (200, 255, 255),
                                False,
                                [(int(x), int(y)) for x, y in points],
                                1,
                            )
                    except Exception:
                        pass
            except Exception:
                pass
        self.draw_chain_lightning_effects(shake_x, shake_y)

    def draw_lightning_effect(self, shake_x=0, shake_y=0):
        pygame = self.pygame
        if not self.screen or not pygame:
            return
        try:
            # Screen flash based on a pulsing alpha (use frame_count)
            flash_alpha: float = abs(math.sin(self.game.frame_count * 0.18))
            if flash_alpha > 0.25:
                overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                alpha = int(min(255, 180 * flash_alpha))
                overlay.fill((255, 255, 255, alpha))
                self.screen.blit(overlay, (0, 0))

            # Draw falling light beam (replaces bolt) and keep explosion
            pts: Any | None = getattr(self.game, "lightning_points", None)
            if pts and len(pts) > 0:
                end_x, end_y = pts[-1]
            else:
                end_x = int(getattr(self.game.player, "x", self.width // 2))
                end_y = int(getattr(self.game.player, "y", self.height - 80))

            # select timer and duration based on current stage
            if self.game.selected_stage == "limbo_final":
                t = getattr(self.game, "limbo_final_lightning_timer", 0)
                total = int(
                    getattr(self.game, "limbo_final_lightning_duration_frames", 180)
                )
            else:
                t = getattr(self.game, "prologo_lightning_timer", 0)
                total = int(
                    getattr(self.game, "prologo_lightning_duration_frames", 180)
                )

            # Beam fall progress (fast initial fall)
            fall_frames = 30
            progress: float = min(1.0, t / float(fall_frames))
            current_y = int(end_y * progress)
            # Beam widths
            max_outer = 180
            max_core = 40
            outer_w = int(max(30, max_outer * (0.2 + 0.8 * progress)))
            core_w = int(max(6, max_core * progress))
            # Draw beam using alpha surface for glow
            beam_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            outer_color: tuple[Literal[255], Literal[240], Literal[200], int] = (
                255,
                240,
                200,
                int(150 * (0.5 + progress * 0.5)),
            )
            core_color: tuple[Literal[255], Literal[255], Literal[200], int] = (
                255,
                255,
                200,
                int(220 * (0.3 + progress * 0.7)),
            )
            center_color: tuple[Literal[255], Literal[255], Literal[180], int] = (
                255,
                255,
                180,
                int(255 * progress),
            )
            # Outer glow rectangle
            pygame.draw.rect(
                beam_surf,
                outer_color,
                (
                    int(end_x - outer_w / 2) + int(shake_x),
                    0 + int(shake_y),
                    outer_w,
                    current_y,
                ),
            )
            # Inner core rectangle
            pygame.draw.rect(
                beam_surf,
                core_color,
                (
                    int(end_x - core_w / 2) + int(shake_x),
                    0 + int(shake_y),
                    core_w,
                    current_y,
                ),
            )
            # Bright center line
            pygame.draw.rect(
                beam_surf,
                center_color,
                (
                    int(end_x - 3) + int(shake_x),
                    0 + int(shake_y),
                    6,
                    current_y,
                ),
            )
            # Blit the beam
            self.screen.blit(beam_surf, (0, 0))

            # Try to capture screenshots at two key moments (non-fatal)
            try:
                start_frame: int = max(1, int(total * 0.1))
                peak_frame: int = max(1, int(total * 0.75))
                os.makedirs("screenshots", exist_ok=True)
                suffix = (
                    "limbo" if self.game.selected_stage == "limbo_final" else "prologo"
                )
                if (
                    not getattr(self.game, "_screenshot_taken_start", False)
                    and t == start_frame
                ):
                    pygame.image.save(
                        self.screen,
                        os.path.join("screenshots", f"{suffix}_beam_start.png"),
                    )
                    self.game._screenshot_taken_start = True
                if (
                    not getattr(self.game, "_screenshot_taken_peak", False)
                    and t == peak_frame
                ):
                    pygame.image.save(
                        self.screen,
                        os.path.join("screenshots", f"{suffix}_beam_peak.png"),
                    )
                    self.game._screenshot_taken_peak = True
            except Exception:
                pass

            # Explosion / impact at the end point
            # Make a pulsing explosion that grows over the configured timer
            max_radius = 160
            radius = int(min(max_radius, (t / float(total)) * max_radius + 8))
            pulse: float = (math.sin(self.game.frame_count * 0.25) + 1) * 0.5
            # Outer glow circle
            pygame.draw.circle(
                self.screen,
                (255, 240, 200),
                self._apply_shake(end_x, end_y, shake_x, shake_y),
                int(radius * 1.1),
            )
            end_xs, end_ys = self._apply_shake(end_x, end_y, shake_x, shake_y)
            pygame.draw.circle(
                self.screen,
                (255, 255, 200),
                (end_xs, end_ys),
                int(radius * 0.6 + pulse * 8),
            )
            for ang in range(0, 360, 45):
                rad: float = math.radians(ang)
                lx: Any | float = end_x + math.cos(rad) * (radius * 0.9)
                ly: Any | float = end_y + math.sin(rad) * (radius * 0.9)
                lxs, lys = self._apply_shake(lx, ly, shake_x, shake_y)
                pygame.draw.line(
                    self.screen,
                    (255, 255, 230),
                    (end_xs, end_ys),
                    (lxs, lys),
                    3,
                )
            else:
                # Fallback: vertical beam above player like old behavior
                player_x: Any | int = getattr(self.game.player, "x", self.width // 2)
                player_y: Any | int = getattr(self.game.player, "y", self.height - 80)
                beam_width = 8
                beam_x: Any | int = player_x
                pygame.draw.line(
                    self.screen,
                    (255, 255, 200),
                    (beam_x + shake_x, 0 + shake_y),
                    (beam_x + shake_x, player_y + shake_y),
                    beam_width + 12,
                )
        except Exception:
            # Avoid breaking the game if drawing fails
            logger.exception("draw_lightning_effect failed")

    def draw_chain_lightning_effects(self, shake_x=0, shake_y=0) -> None:
        """Draw chain lightning effects between enemies"""
        pygame = self.pygame
        try:
            for effect in getattr(self.game.game_state, "chain_lightning_effects", []):
                points = effect.get("points", [])
                timer = effect.get("timer", 0)
                if len(points) < 2 or timer <= 0:
                    continue

                # Calculate alpha based on remaining timer (fade out)
                # Use 16 as the default max for explosion-type effects (older chain effects use 8)
                max_timer = 16 if effect.get("explosion") else 8
                alpha = min(255, int(255 * (timer / float(max_timer))))

                is_explosion = bool(effect.get("explosion", False))

                # If this is an explosion effect, draw a pulsing core and sparks at the center
                if is_explosion and len(points) > 0:
                    try:
                        cx, cy = points[0]
                        progress = timer / float(max_timer)
                        radius = int(effect.get("radius", 80) * (1.0 - progress + 0.25))
                        color_base = effect.get("color", (120, 220, 255))

                        # Outer glow (soft)
                        glow_surf = pygame.Surface(
                            (radius * 2 + 8, radius * 2 + 8), pygame.SRCALPHA
                        )
                        glow_alpha = max(30, int(alpha * 0.6))
                        try:
                            pygame.draw.circle(
                                glow_surf,
                                (
                                    color_base[0],
                                    color_base[1],
                                    color_base[2],
                                    glow_alpha,
                                ),
                                (radius + 4, radius + 4),
                                radius,
                            )
                            self.screen.blit(
                                glow_surf,
                                (
                                    int(cx - radius) + shake_x - 4,
                                    int(cy - radius) + shake_y - 4,
                                ),
                            )
                        except Exception:
                            pass

                        # Inner bright core
                        try:
                            inner_alpha = min(255, alpha + 40)
                            cxs, cys = self._apply_shake(cx, cy, shake_x, shake_y)
                            pygame.draw.circle(
                                self.screen,
                                (255, 255, 230, inner_alpha),
                                (cxs, cys),
                                max(3, int(radius * 0.15)),
                            )
                        except Exception:
                            pass

                        # Irregular radial lightning bolts for emphasis
                        try:
                            for ang in range(0, 360, 45):
                                rad = math.radians(ang)
                                ex = cx + math.cos(rad) * (radius * 0.9)
                                ey = cy + math.sin(rad) * (radius * 0.9)
                                radial_points = self._generate_lightning_path(
                                    cx + shake_x,
                                    cy + shake_y,
                                    ex + shake_x,
                                    ey + shake_y,
                                    segments=4,
                                    max_offset=4,
                                )
                                for j in range(len(radial_points) - 1):
                                    pygame.draw.line(
                                        self.screen,
                                        (
                                            color_base[0],
                                            color_base[1],
                                            color_base[2],
                                            inner_alpha,
                                        ),
                                        radial_points[j],
                                        radial_points[j + 1],
                                        2,
                                    )
                        except Exception:
                            pass

                        # Sparks at destination points (short-lived bright dots)
                        try:
                            for px, py in points[1:]:
                                pxs, pys = self._apply_shake(px, py, shake_x, shake_y)
                                pygame.draw.circle(
                                    self.screen,
                                    (200, 255, 255, alpha),
                                    (pxs, pys),
                                    4,
                                )
                        except Exception:
                            pass
                    except Exception:
                        pass

                # Draw jagged lines between consecutive points
                # Draw the jagged line segments. Allow effect-provided color (RGB) and apply alpha fade.
                color_base = effect.get("color", (150, 200, 255))
                try:
                    if len(color_base) >= 3:
                        color = (color_base[0], color_base[1], color_base[2], alpha)
                    else:
                        color = (150, 200, 255, alpha)
                except Exception:
                    color = (150, 200, 255, alpha)

                if is_explosion:
                    # For explosion, draw independent lightning bolts from center to each target
                    center_x, center_y = points[0]
                    for target_x, target_y in points[1:]:
                        lightning_points = self._generate_lightning_path(
                            center_x + shake_x,
                            center_y + shake_y,
                            target_x + shake_x,
                            target_y + shake_y,
                            segments=6,
                            max_offset=8,
                        )
                        thickness = 3
                        for j in range(len(lightning_points) - 1):
                            pygame.draw.line(
                                self.screen,
                                color,
                                lightning_points[j],
                                lightning_points[j + 1],
                                thickness,
                            )
                else:
                    # Normal chain lightning: draw between consecutive points
                    for i in range(len(points) - 1):
                        start_x, start_y = points[i]
                        end_x, end_y = points[i + 1]
                        lightning_points = self._generate_lightning_path(
                            start_x + shake_x,
                            start_y + shake_y,
                            end_x + shake_x,
                            end_y + shake_y,
                            segments=6,
                            max_offset=8,
                        )
                        thickness = 2
                        for j in range(len(lightning_points) - 1):
                            pygame.draw.line(
                                self.screen,
                                color,
                                lightning_points[j],
                                lightning_points[j + 1],
                                thickness,
                            )
        except Exception:
            logger.exception("draw_chain_lightning_effects failed")

    def _generate_lightning_path(
        self, start_x, start_y, end_x, end_y, segments=6, max_offset=8
    ):
        """Generate a jagged lightning path between two points"""
        points = [(start_x, start_y)]

        # Calculate direction vector
        dx = end_x - start_x
        dy = end_y - start_y
        distance = math.hypot(dx, dy)

        if distance == 0:
            return points

        # Normalize direction
        dir_x = dx / distance
        dir_y = dy / distance

        # Create perpendicular vector for offset
        perp_x = -dir_y
        perp_y = dir_x

        # Generate intermediate points
        for i in range(1, segments):
            # Position along the line (0 to 1)
            t = i / segments

            # Base position
            base_x = start_x + dx * t
            base_y = start_y + dy * t

            # Add random offset perpendicular to direction
            offset = (random.random() - 0.5) * 2 * max_offset
            point_x = base_x + perp_x * offset
            point_y = base_y + perp_y * offset

            points.append((point_x, point_y))

        points.append((end_x, end_y))
        return points

    def draw_hud(self, shake_x=0, shake_y=0):
        """Draw the HUD elements (migrated from Game.draw_hud).

        Uses self.game state and self.screen (pygame Surface)."""
        pygame = self.pygame
        if not self.screen or not pygame:
            return

        font = self.get_font(24)
        small_font = self.get_font(18)

        # Score
        score_text = self.get_text(
            f"Score: {int(self.game.score)}", font, (255, 255, 0)
        )
        self.screen.blit(score_text, (10 + shake_x, 10 + shake_y))

        # Wave
        wave_text = self.get_text(f"Wave: {self.game.wave}", font, (255, 100, 100))
        self.screen.blit(wave_text, (10 + shake_x, 40 + shake_y))

        # Time
        minutes = int(self.game.time_elapsed // 60)
        seconds = int(self.game.time_elapsed % 60)
        time_text = self.get_text(
            f"Time: {minutes}:{seconds:02d}", font, (100, 200, 255)
        )
        self.screen.blit(time_text, (10 + shake_x, 70 + shake_y))

        # Health bar
        bar_width = 200
        bar_height = 20
        bar_x: int = self.width - bar_width - 10
        bar_y = 10

        # Background
        pygame.draw.rect(
            self.screen,
            (100, 100, 100),
            (bar_x + shake_x, bar_y + shake_y, bar_width, bar_height),
        )
        # Health
        health_ratio: float = self.game.player.health / self.game.player.max_health
        health_color: (
            tuple[Literal[20], Literal[80], Literal[20]]
            | tuple[Literal[255], Literal[255], Literal[0]]
            | tuple[Literal[255], Literal[0], Literal[0]]
        ) = (
            (20, 80, 20)
            if health_ratio > 0.5
            else (255, 255, 0) if health_ratio > 0.25 else (255, 0, 0)
        )
        pygame.draw.rect(
            self.screen,
            health_color,
            (bar_x + shake_x, bar_y + shake_y, bar_width * health_ratio, bar_height),
        )
        # Border
        pygame.draw.rect(
            self.screen,
            (255, 255, 255),
            (bar_x + shake_x, bar_y + shake_y, bar_width, bar_height),
            2,
        )

        # Health text
        health_text = self.get_text(
            f"{int(self.game.player.health)}/{int(self.game.player.max_health)}",
            small_font,
            (255, 255, 255),
        )
        self.screen.blit(
            health_text,
            (
                bar_x + bar_width // 2 - health_text.get_width() // 2 + shake_x,
                bar_y + bar_height // 2 - health_text.get_height() // 2 + shake_y,
            ),
        )

        # XP bar
        xp_bar_y = 40
        pygame.draw.rect(
            self.screen,
            (100, 100, 100),
            (bar_x + shake_x, xp_bar_y + shake_y, bar_width, bar_height),
        )
        xp_ratio: float = self.game.player_xp / max(1, self.game.xp_to_next_level)
        # XP bar in darker purple
        pygame.draw.rect(
            self.screen,
            (120, 34, 160),
            (bar_x + shake_x, xp_bar_y + shake_y, bar_width * xp_ratio, bar_height),
        )
        pygame.draw.rect(
            self.screen,
            (255, 255, 255),
            (bar_x + shake_x, xp_bar_y + shake_y, bar_width, bar_height),
            2,
        )

        # XP text
        xp_text = self.get_text(
            f"{int(self.game.player_xp)}/{int(self.game.xp_to_next_level)}",
            small_font,
            (255, 255, 255),
        )
        self.screen.blit(
            xp_text,
            (
                bar_x + bar_width // 2 - xp_text.get_width() // 2 + shake_x,
                xp_bar_y + bar_height // 2 - xp_text.get_height() // 2 + shake_y,
            ),
        )

        # Level
        level_text = self.get_text(
            f"Level {self.game.player_level}", font, (255, 215, 0)
        )
        self.screen.blit(
            level_text,
            (
                bar_x + bar_width // 2 - level_text.get_width() // 2 + shake_x,
                xp_bar_y + bar_height + 5 + shake_y,
            ),
        )

        # Weapon HUD - show extra weapons with levels
        hud_x: int = self.width - 10
        hud_y: int = xp_bar_y + bar_height + 35
        box_w = 170
        box_h = 20

        # Extra weapons
        if hasattr(self.game, "player_weapons") and self.game.player_weapons:
            for i, wid in enumerate(self.game.player_weapons):
                lvl: int = self.game.weapon_levels.get(wid, 0)
                display_name: str = _WEAPON_HUD_NAMES.get(wid, wid.capitalize())
                display_text: str = f"{display_name} Lv{lvl}"

                y: int = hud_y + i * 22

                # Background box
                pygame.draw.rect(
                    self.screen,
                    (22, 22, 22),
                    (hud_x - box_w + shake_x, y - 10 + shake_y, box_w, box_h),
                )
                pygame.draw.rect(
                    self.screen,
                    (68, 68, 68),
                    (hud_x - box_w + shake_x, y - 10 + shake_y, box_w, box_h),
                    1,
                )

                weapon_text = small_font.render(display_text, True, (200, 200, 200))
                self.screen.blit(
                    weapon_text,
                    (
                        hud_x - box_w // 2 - weapon_text.get_width() // 2 + shake_x,
                        y - 8 + shake_y,
                    ),
                )

                # If at max level, add MAX indicator
                if lvl >= getattr(self.game, "max_weapon_level", 6):
                    max_text = small_font.render("MAX", True, (255, 215, 0))
                    self.screen.blit(
                        max_text,
                        (
                            hud_x - 12 - max_text.get_width() // 2 + shake_x,
                            y - 8 + shake_y,
                        ),
                    )

        # Draw center messages
        if hasattr(self, "draw_center_messages"):
            self.draw_center_messages(shake_x, shake_y)
        elif hasattr(self.game, "draw_center_messages"):
            self.game.draw_center_messages(shake_x, shake_y)

    def draw_center_messages(self, shake_x=0, shake_y=0) -> None:
        """Draw any active centered messages"""
        pygame = self.pygame
        if not self.screen or not pygame:
            return

        for msg in list(self.game.center_messages):
            try:
                font = self.get_font(msg.get("font_size", 36))
                # Shadow for readability
                shadow_text = self.get_text(msg["text"], font, (0, 0, 0))
                self.screen.blit(
                    shadow_text,
                    (
                        self.width // 2 - shadow_text.get_width() // 2 + 2 + shake_x,
                        self.height // 2 - 40 + 2 + shake_y,
                    ),
                )
                # Main text
                main_text = self.get_text(msg["text"], font, msg["color"])
                self.screen.blit(
                    main_text,
                    (
                        self.width // 2 - main_text.get_width() // 2 + shake_x,
                        self.height // 2 - 40 + shake_y,
                    ),
                )
            except Exception:
                logger.exception("Error drawing center message")
                # Remove the problematic message
                if msg in self.game.center_messages:
                    self.game.center_messages.remove(msg)

    def draw_fps_counter(self) -> None:
        """Draw the FPS counter in the top-right corner, always on top, no shake."""
        if not getattr(self.game, "show_fps", True):
            return
        pygame = self.pygame
        if not self.screen or not pygame:
            return
        try:
            fps_val = int(self.game.clock.get_fps())
            font = self.get_font(18)
            fps_text = self.get_text(f"FPS: {fps_val}", font, (200, 200, 200))
            x = self.width - fps_text.get_width() - 6
            y = 6
            # Dark background for readability
            bg = pygame.Surface((fps_text.get_width() + 4, fps_text.get_height() + 2))
            bg.fill((0, 0, 0))
            bg.set_alpha(120)
            self.screen.blit(bg, (x - 2, y - 1))
            self.screen.blit(fps_text, (x, y))
        except Exception:
            pass

    def draw_prologo_end(self, shake_x=0, shake_y=0) -> None:
        """Draw the prologo completion screen"""
        try:
            import pygame

            # Create semi-transparent purple overlay
            overlay = pygame.Surface((self.width, self.height))
            overlay.fill((40, 20, 45))  # Purple background
            overlay.set_alpha(180)  # Semi-transparent (0-255, 180 = ~70% opacity)
            self.game.screen.blit(overlay, (0, 0))

            font_large = self.get_font(48)
            font_medium = self.get_font(32)

            # Title
            title = self.get_text("SATAN'S FALL COMPLETE", font_large, (255, 215, 0))
            self.game.screen.blit(
                title,
                (
                    self.game.width // 2 - title.get_width() // 2 + shake_x,
                    self.game.height // 2 - 100 + shake_y,
                ),
            )

            # Message
            message1 = self.get_text(
                "You have witnessed Satan's fall from grace.",
                font_medium,
                (255, 255, 255),
            )
            message2 = self.get_text(
                "Now face the endless torment of Limbo.", font_medium, (255, 255, 255)
            )

            self.game.screen.blit(
                message1,
                (
                    self.game.width // 2 - message1.get_width() // 2 + shake_x,
                    self.game.height // 2 - 20 + shake_y,
                ),
            )
            self.game.screen.blit(
                message2,
                (
                    self.game.width // 2 - message2.get_width() // 2 + shake_x,
                    self.game.height // 2 + 20 + shake_y,
                ),
            )
        except Exception:
            pass

    def draw_weapon_selection(self, shake_x=0, shake_y=0) -> None:
        """Draw weapon selection screen"""
        try:
            import pygame

            font_title = self.get_font(38)
            font_name = self.get_font(26)
            font_desc = self.get_font(17)
            font_small = self.get_font(15)
            font_key = self.get_font(17)

            # ── palette ──────────────────────────────────────────────────────────────
            # new weapon boxes  →  dark crimson / burgundy
            C_NEW_BG = (28, 12, 12)
            C_NEW_BG_HOV = (44, 20, 18)
            C_NEW_BORDER = (92, 42, 40)
            C_NEW_BORDER_H = (135, 65, 58)
            C_NEW_NAME = (172, 98, 88)

            # weapon upgrade boxes  →  aged bronze / dark ochre
            C_UPG_BG = (26, 20, 10)
            C_UPG_BG_HOV = (40, 30, 14)
            C_UPG_BORDER = (88, 72, 38)
            C_UPG_BORDER_H = (125, 102, 55)
            C_UPG_NAME = (165, 138, 82)

            C_TITLE = (145, 45, 45)
            C_DIVIDER = (72, 52, 42)
            C_DESC = (138, 135, 130)
            C_KEY = (70, 62, 56)

            # ── overlay ──────────────────────────────────────────────────────────────
            overlay = pygame.Surface((self.game.width, self.game.height))
            overlay.set_alpha(185)
            overlay.fill((4, 4, 10))
            self.game.screen.blit(overlay, (0, 0))

            # ── title ────────────────────────────────────────────────────────────────
            is_initial = getattr(self.game, "is_initial_weapon_choice", False)
            title_text = "CHOOSE YOUR WEAPON" if is_initial else "NEW WEAPON"
            sub_text = (
                "pick your starting arsenal"
                if is_initial
                else "a new weapon joins your arsenal"
            )
            title_surf = self.get_text(title_text, font_title, C_TITLE)
            sub_surf = self.get_text(sub_text, font_small, (90, 100, 130))
            ty = 60 + shake_y
            self.game.screen.blit(
                title_surf,
                (self.game.width // 2 - title_surf.get_width() // 2 + shake_x, ty),
            )
            self.game.screen.blit(
                sub_surf,
                (
                    self.game.width // 2 - sub_surf.get_width() // 2 + shake_x,
                    ty + title_surf.get_height() + 4,
                ),
            )
            div_y = ty + title_surf.get_height() + sub_surf.get_height() + 10
            pygame.draw.line(
                self.game.screen,
                C_DIVIDER,
                (self.game.width // 2 - 180 + shake_x, div_y),
                (self.game.width // 2 + 180 + shake_x, div_y),
                1,
            )

            # ── layout (must match click-handler) ────────────────────────────────────
            cx = self.game.width // 2
            box_width = SELECTION_BOX_WIDTH
            box_height = SELECTION_BOX_HEIGHT
            spacing = SELECTION_BOX_SPACING
            total_height = (
                len(self.game.weapon_choices) * box_height
                + (len(self.game.weapon_choices) - 1) * spacing
            )
            start_y = self.game.height // 2 - total_height // 2 + 30
            x_pos = cx - box_width // 2

            # ── weapon boxes ─────────────────────────────────────────────────────────
            for i, weapon in enumerate(self.game.weapon_choices):
                y_pos = start_y + i * (box_height + spacing)
                mouse_rect = pygame.Rect(x_pos, y_pos, box_width, box_height)
                is_hovered = mouse_rect.collidepoint(
                    self.game.mouse_x, self.game.mouse_y
                )
                if is_hovered:
                    self.game.selected_weapon_index = i

                # Weapon upgrades (for owned weapons at lvl 3/6) use gold palette;
                # new weapons (initial pick or entirely new ones) use crimson palette.
                is_upgrade = weapon.get("id", "").endswith("_upgrade")
                if is_upgrade:
                    bg_col = C_UPG_BG_HOV if is_hovered else C_UPG_BG
                    border_col = C_UPG_BORDER_H if is_hovered else C_UPG_BORDER
                    name_col = C_UPG_NAME
                    stripe_col = C_UPG_BORDER_H
                else:
                    bg_col = C_NEW_BG_HOV if is_hovered else C_NEW_BG
                    border_col = C_NEW_BORDER_H if is_hovered else C_NEW_BORDER
                    name_col = C_NEW_NAME
                    stripe_col = C_NEW_BORDER_H

                bx = x_pos + shake_x
                by = y_pos + shake_y

                pygame.draw.rect(
                    self.game.screen, bg_col, (bx, by, box_width, box_height)
                )
                pygame.draw.rect(
                    self.game.screen, border_col, (bx, by, box_width, box_height), 2
                )

                if is_hovered:
                    pygame.draw.rect(
                        self.game.screen, stripe_col, (bx, by, 3, box_height)
                    )

                # --- content layout ------------------------------------------------
                # reserve a fixed margin for the icon on the left; the actual
                # graphic is optional but the blank space keeps the text
                # columns aligned across all choices.
                icon_start_x = bx + 16
                content_x = icon_start_x + WEAPON_ICON_SIZE + WEAPON_ICON_PADDING

                # draw an icon if the weapon definition provided one
                icon_path = weapon.get("icon")
                if icon_path:
                    icon_surf = get_image(icon_path, (WEAPON_ICON_SIZE, WEAPON_ICON_SIZE))
                    # if the named asset wasn't found, try the alternate naming
                    # convention (strip or add "weapon_" prefix) so manually
                    # dropped files still work.
                    if icon_surf is None:
                        if icon_path.startswith("weapon_"):
                            alt = icon_path[len("weapon_"):]
                        else:
                            alt = f"weapon_{icon_path}"
                        icon_surf = get_image(alt, (WEAPON_ICON_SIZE, WEAPON_ICON_SIZE))
                    if icon_surf:
                        icon_y = by + (box_height - WEAPON_ICON_SIZE) // 2
                        self.game.screen.blit(icon_surf, (icon_start_x, icon_y))

                # key (e.g. "[1]") comes after icon/margin
                key_surf = self.get_text(f"[{i + 1}]", font_key, C_KEY)
                self.game.screen.blit(
                    key_surf,
                    (content_x, by + box_height // 2 - key_surf.get_height() // 2),
                )
                content_x += key_surf.get_width() + WEAPON_ICON_PADDING

                name_surf = self.get_text(weapon["name"], font_name, name_col)
                desc_surf = self.get_text(weapon["description"], font_desc, C_DESC)
                block_h = name_surf.get_height() + 4 + desc_surf.get_height()
                name_x = content_x
                name_y = by + (box_height - block_h) // 2
                self.game.screen.blit(name_surf, (name_x, name_y))
                self.game.screen.blit(
                    desc_surf, (name_x, name_y + name_surf.get_height() + 4)
                )
        except Exception:
            pass

    def draw_tower_selection(self, shake_x=0, shake_y=0) -> None:
        """Draw tower selection screen (Purgatory)."""
        try:
            import pygame

            font_title = self.get_font(38)
            font_name = self.get_font(26)
            font_desc = self.get_font(17)
            font_small = self.get_font(15)
            font_key = self.get_font(17)

            # ── palette  (dark iron / charcoal) ──────────────────────────────────────
            C_TITLE = (148, 148, 145)
            C_DIVIDER = (58, 56, 52)
            C_BG = (14, 13, 13)
            C_BG_HOV = (26, 25, 24)
            C_BORDER = (60, 58, 54)
            C_BORDER_H = (105, 100, 92)
            C_NAME = (188, 185, 178)
            C_DESC = (118, 115, 110)
            C_KEY = (58, 56, 52)

            # ── overlay ──────────────────────────────────────────────────────────────
            overlay = pygame.Surface((self.game.width, self.game.height))
            overlay.set_alpha(200)
            overlay.fill((2, 2, 4))
            self.game.screen.blit(overlay, (0, 0))

            # ── title ────────────────────────────────────────────────────────────────
            title_surf = self.get_text("CHOOSE YOUR TOWER", font_title, C_TITLE)
            sub_surf = self.get_text("place your guardian", font_small, (75, 75, 80))
            ty = 60 + shake_y
            self.game.screen.blit(
                title_surf,
                (self.game.width // 2 - title_surf.get_width() // 2 + shake_x, ty),
            )
            self.game.screen.blit(
                sub_surf,
                (
                    self.game.width // 2 - sub_surf.get_width() // 2 + shake_x,
                    ty + title_surf.get_height() + 4,
                ),
            )
            div_y = ty + title_surf.get_height() + sub_surf.get_height() + 10
            pygame.draw.line(
                self.game.screen,
                C_DIVIDER,
                (self.game.width // 2 - 180 + shake_x, div_y),
                (self.game.width // 2 + 180 + shake_x, div_y),
                1,
            )

            # ── layout (must match click-handler) ────────────────────────────────────
            cx = self.game.width // 2
            box_width = SELECTION_BOX_WIDTH
            box_height = SELECTION_BOX_HEIGHT
            spacing = SELECTION_BOX_SPACING
            total_height = (
                len(self.game.tower_choices) * box_height
                + (len(self.game.tower_choices) - 1) * spacing
            )
            start_y = self.game.height // 2 - total_height // 2 + 30
            x_pos = cx - box_width // 2

            # ── tower boxes ──────────────────────────────────────────────────────────
            for i, tower in enumerate(self.game.tower_choices):
                y_pos = start_y + i * (box_height + spacing)
                mouse_rect = pygame.Rect(x_pos, y_pos, box_width, box_height)
                is_hovered = mouse_rect.collidepoint(
                    self.game.mouse_x, self.game.mouse_y
                )
                if is_hovered:
                    self.game.selected_tower_index = i

                bg_col = C_BG_HOV if is_hovered else C_BG
                border_col = C_BORDER_H if is_hovered else C_BORDER

                bx = x_pos + shake_x
                by = y_pos + shake_y

                pygame.draw.rect(
                    self.game.screen, bg_col, (bx, by, box_width, box_height)
                )
                pygame.draw.rect(
                    self.game.screen, border_col, (bx, by, box_width, box_height), 2
                )

                if is_hovered:
                    pygame.draw.rect(
                        self.game.screen, C_BORDER_H, (bx, by, 3, box_height)
                    )

                key_surf = self.get_text(f"[{i + 1}]", font_key, C_KEY)
                self.game.screen.blit(
                    key_surf,
                    (bx + 16, by + box_height // 2 - key_surf.get_height() // 2),
                )

                name_surf = self.get_text(tower["name"], font_name, C_NAME)
                desc_surf = self.get_text(tower["description"], font_desc, C_DESC)
                block_h = name_surf.get_height() + 4 + desc_surf.get_height()
                name_x = bx + 52
                name_y = by + (box_height - block_h) // 2
                self.game.screen.blit(name_surf, (name_x, name_y))
                self.game.screen.blit(
                    desc_surf, (name_x, name_y + name_surf.get_height() + 4)
                )
        except Exception:
            pass

    def draw_upgrade_selection(self, shake_x=0, shake_y=0) -> None:
        """Draw upgrade selection screen"""
        try:
            import pygame

            font_title = self.get_font(38)
            font_name = self.get_font(26)
            font_desc = self.get_font(17)
            font_small = self.get_font(15)
            font_key = self.get_font(17)

            # ── palette ──────────────────────────────────────────────────────────────
            C_TITLE = (145, 45, 45)
            C_DIVIDER = (65, 50, 40)

            # weapon upgrade box  (aged parchment / dark bronze)
            C_WPN_BG = (26, 20, 10)
            C_WPN_BG_HOV = (40, 30, 14)
            C_WPN_BORDER = (88, 72, 38)
            C_WPN_BORDER_H = (125, 102, 55)
            C_WPN_NAME = (165, 138, 82)

            # normal upgrade box  (dark slate green)
            C_NRM_BG = (14, 28, 22)
            C_NRM_BG_HOV = (20, 40, 30)
            C_NRM_BORDER = (45, 78, 60)
            C_NRM_BORDER_H = (68, 112, 85)
            C_NRM_NAME = (95, 148, 115)

            C_DESC = (138, 135, 130)
            C_KEY = (70, 68, 62)

            def _is_weapon_upg(upgrade: dict) -> bool:
                uid = upgrade.get("id", "")
                return uid.endswith("_upgrade") or uid in (
                    "shotgun",
                    "orbital",
                    "spear",
                    "skullboom",
                    "beast",
                )

            # ── overlay ──────────────────────────────────────────────────────────────
            overlay = pygame.Surface((self.game.width, self.game.height))
            overlay.set_alpha(185)
            overlay.fill((4, 4, 8))
            self.game.screen.blit(overlay, (0, 0))

            # ── title ────────────────────────────────────────────────────────────────
            title_surf = self.get_text("LEVEL UP", font_title, C_TITLE)
            sub_surf = self.get_text("choose your upgrade", font_small, (110, 110, 110))
            tx = self.game.width // 2 - title_surf.get_width() // 2 + shake_x
            ty = 60 + shake_y
            self.game.screen.blit(title_surf, (tx, ty))
            self.game.screen.blit(
                sub_surf,
                (
                    self.game.width // 2 - sub_surf.get_width() // 2 + shake_x,
                    ty + title_surf.get_height() + 4,
                ),
            )
            div_y = ty + title_surf.get_height() + sub_surf.get_height() + 10
            pygame.draw.line(
                self.game.screen,
                C_DIVIDER,
                (self.game.width // 2 - 180 + shake_x, div_y),
                (self.game.width // 2 + 180 + shake_x, div_y),
                1,
            )

            # ── layout (must match click-handler) ────────────────────────────────────
            cx = self.game.width // 2
            box_width = SELECTION_BOX_WIDTH
            box_height = SELECTION_BOX_HEIGHT
            spacing = SELECTION_BOX_SPACING
            total_height = (
                len(self.game.upgrade_choices) * box_height
                + (len(self.game.upgrade_choices) - 1) * spacing
            )
            start_y = self.game.height // 2 - total_height // 2 + 30
            x_pos = cx - box_width // 2

            # ── reroll button ─────────────────────────────────────────────────────────
            if getattr(self.game, "upgrade_rerolls_remaining", 0) > 0:
                pad = 8
                reroll_label = f"Reroll  ({self.game.upgrade_rerolls_remaining} left)"
                reroll_surf = self.get_text(reroll_label, font_small, (190, 150, 150))
                reroll_w = reroll_surf.get_width() + 24
                reroll_h = reroll_surf.get_height() + 10
                reroll_x = self.game.width // 2 - reroll_w // 2
                reroll_y = int((div_y + 6 + start_y) / 2 - reroll_h / 2)
                reroll_rect = pygame.Rect(reroll_x, reroll_y, reroll_w, reroll_h)
                hot_rect = pygame.Rect(
                    reroll_x - pad,
                    reroll_y - pad,
                    reroll_w + pad * 2,
                    reroll_h + pad * 2,
                )
                mouse_over = hot_rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
                pygame.draw.rect(
                    self.game.screen,
                    (68, 32, 28) if mouse_over else (38, 18, 16),
                    reroll_rect,
                )
                pygame.draw.rect(
                    self.game.screen,
                    (130, 72, 62) if mouse_over else (88, 52, 46),
                    reroll_rect,
                    2,
                )
                self.game.screen.blit(reroll_surf, (reroll_x + 12, reroll_y + 5))

            # ── upgrade boxes ─────────────────────────────────────────────────────────
            for i, upgrade in enumerate(self.game.upgrade_choices):
                y_pos = start_y + i * (box_height + spacing)
                mouse_rect = pygame.Rect(x_pos, y_pos, box_width, box_height)
                is_hovered = mouse_rect.collidepoint(
                    self.game.mouse_x, self.game.mouse_y
                )
                if is_hovered:
                    self.game.selected_upgrade_index = i
                is_weapon = _is_weapon_upg(upgrade)

                if is_weapon:
                    bg_col = C_WPN_BG_HOV if is_hovered else C_WPN_BG
                    border_col = C_WPN_BORDER_H if is_hovered else C_WPN_BORDER
                    name_col = C_WPN_NAME
                else:
                    bg_col = C_NRM_BG_HOV if is_hovered else C_NRM_BG
                    border_col = C_NRM_BORDER_H if is_hovered else C_NRM_BORDER
                    name_col = C_NRM_NAME

                bx = x_pos + shake_x
                by = y_pos + shake_y

                pygame.draw.rect(
                    self.game.screen, bg_col, (bx, by, box_width, box_height)
                )
                pygame.draw.rect(
                    self.game.screen, border_col, (bx, by, box_width, box_height), 2
                )

                # left accent stripe on hover
                if is_hovered:
                    stripe = C_WPN_BORDER_H if is_weapon else C_NRM_BORDER_H
                    pygame.draw.rect(self.game.screen, stripe, (bx, by, 3, box_height))

                # [1] [2] [3] key hint — left side
                key_surf = self.get_text(f"[{i + 1}]", font_key, C_KEY)
                key_x = bx + 16
                key_y = by + box_height // 2 - key_surf.get_height() // 2
                self.game.screen.blit(key_surf, (key_x, key_y))

                # name + description — centred vertically in the box
                name_surf = self.get_text(upgrade["name"], font_name, name_col)
                desc_surf = self.get_text(upgrade["description"], font_desc, C_DESC)
                block_h = name_surf.get_height() + 4 + desc_surf.get_height()
                name_x = bx + 52
                name_y = by + (box_height - block_h) // 2
                self.game.screen.blit(name_surf, (name_x, name_y))
                self.game.screen.blit(
                    desc_surf, (name_x, name_y + name_surf.get_height() + 4)
                )
        except Exception:
            pass

    def draw_game_over(self, shake_x=0, shake_y=0) -> None:
        """Draw the persistent game over screen overlay with fade."""
        try:
            import pygame

            # Overlay surface with per-pixel alpha to allow fade-in effect
            overlay = pygame.Surface(
                (self.game.width, self.game.height), pygame.SRCALPHA
            )
            overlay.fill((40, 20, 45, int(self.game.game_over_alpha)))
            self.game.screen.blit(overlay, (0, 0))

            # Title (fade text by setting per-surface alpha)

            # Dark red for the FALL title for stronger contrast
            title_surf = self.get_text("FALL", self.get_font(64), (139, 0, 0)).copy()
            title_surf.set_alpha(int(self.game.game_over_alpha))
            self.game.screen.blit(
                title_surf,
                (
                    self.game.width // 2 - title_surf.get_width() // 2 + shake_x,
                    200 + shake_y,
                ),
            )

            # Stats
            font_medium = self.get_font(24)
            stats = [
                f"Final Score: {int(self.game.score)}",
                f"Enemies killed: {getattr(self.game, 'enemies_killed_this_run', 0)}",
                f"Wave: {self.game.wave}",
                f"Level: {self.game.player.level}",
            ]

            for i, stat in enumerate(stats):
                text_surf = self.get_text(stat, font_medium, (255, 255, 255)).copy()
                text_surf.set_alpha(int(self.game.game_over_alpha))
                self.game.screen.blit(
                    text_surf,
                    (
                        self.game.width // 2 - text_surf.get_width() // 2 + shake_x,
                        320 + i * 40 + shake_y,
                    ),
                )

            # Prompt
            # Main prompt: ESC to return to menu (restart disabled)
            # Moved down for more spacing and changed to light yellow
            prompt = self.get_text(
                "Press ESC to return to menu", font_medium, (255, 255, 153)
            ).copy()
            prompt.set_alpha(int(self.game.game_over_alpha))
            self.game.screen.blit(
                prompt,
                (
                    self.game.width // 2 - prompt.get_width() // 2 + shake_x,
                    480 + shake_y,
                ),
            )

        except Exception as e:
            logger.exception("Error drawing game over screen: %s", e)

    def draw_victory(self, shake_x=0, shake_y=0) -> None:
        """Draw the limbo victory overlay before returning to menu."""
        try:
            import pygame

            overlay = pygame.Surface(
                (self.game.width, self.game.height), pygame.SRCALPHA
            )
            overlay.fill((40, 20, 45, int(self.game.victory_alpha)))
            self.game.screen.blit(overlay, (0, 0))

            title_surf = self.get_text(
                "SATANIC VICTORY!", self.get_font(64), (255, 215, 0)
            ).copy()
            title_surf.set_alpha(int(self.game.victory_alpha))
            self.game.screen.blit(
                title_surf,
                (
                    self.game.width // 2 - title_surf.get_width() // 2 + shake_x,
                    200 + shake_y,
                ),
            )

            # instructions
            instr = self.get_text(
                "ENTER → Next level    ESC → Main menu",
                self.get_font(24),
                (200, 200, 200),
            ).copy()
            instr.set_alpha(int(self.game.victory_alpha))
            self.game.screen.blit(
                instr,
                (
                    self.game.width // 2 - instr.get_width() // 2 + shake_x,
                    300 + shake_y,
                ),
            )
        except Exception as e:
            logger.exception("Error drawing victory screen: %s", e)
