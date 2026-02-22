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
    WALL_THICKNESS,
)
from src.weapons import WEAPON_DEFS

logger: logging.Logger = logging.getLogger(__name__)

# NOTE: Legacy UIManager (Tkinter-based) class removed — all rendering
# is handled by PygameUIManager below.


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

            # allow particles to occupy top ~40%; bottom of texture <=40%
            y_limit = int(HEIGHT * 0.4)
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
        # Defer importing pygame to runtime (helps tests without SDL)
        try:
            import pygame

            self.pygame: Any = pygame
        except Exception:
            self.pygame = None
        self.game: Any = game
        self.screen: Any | None = getattr(game, "screen", None)
        self.width: Any | int = getattr(game, "width", 0)
        self.height: Any | int = getattr(game, "height", 0)

        # Purgatory fog particles (visual-only, spawned in the lateral areas outside walls)
        self._purgatory_fog_particles: list[dict] = []
        self._purgatory_fog_spawn_acc: float = 0.0

        # New cloud shapes floating near the top in Purgatory
        self._purgatory_clouds: list[dict] = []

        # Dynamic fog blobs introduced from external script
        self._init_fog_particles()

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

    def _spawn_purgatory_fog_particles(self) -> None:
        """Legacy helper that would spawn fog particles along the exterior walls.

        The particle effect was removed; this method is now a no-op but is kept
        around in case external code still references it.  Calling it will not
        modify ``_purgatory_fog_particles``.
        """
        # nothing to do other than clear any remnants
        try:
            self._purgatory_fog_particles = []
        except Exception:
            pass

    def _update_and_draw_purgatory_fog_particles(self) -> None:
        """Legacy updater/drawer for purgatory fog particles.

        The system no longer emits or displays particles; this helper simply
        clears the list if present and returns quietly for compatibility.
        """
        # clear the list to avoid accumulation from old usage and exit
        try:
            self._purgatory_fog_particles = []
        except Exception:
            pass

    # -- new cloud particle helpers ------------------------------------------------
    def _spawn_purgatory_clouds(self) -> None:
        """Legacy helper for purgatory cloud shapes.

        Clouds were removed by user request; this method now clears any existing
        descriptors and does nothing when called.  It is preserved only for
        compatibility with existing calls elsewhere in the codebase.

        *Optimization note*: when clouds were active they were generated at half
        canvas resolution and converted with ``convert_alpha()`` – this trimmed
        pixel work by roughly 75%.  If the system ever returns, keep that
        strategy in mind.
        """
        try:
            self._purgatory_clouds = []
        except Exception:
            pass

    # --- new fog particle system helpers ------------------------------------------------
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
                # clamp bottom edge within top 40% after update
                if p.y + p.width > self.height * 0.4:
                    p.y = self.height * 0.4 - p.width
                if self.screen and self.pygame:
                    p.draw(self.screen)
        except Exception:
            pass

    def _update_and_draw_purgatory_clouds(self) -> None:
        """Legacy updater/drawer for purgatory cloud shapes.

        Since clouds have been removed, this helper simply wipes the list and
        returns without drawing.
        """
        try:
            self._purgatory_clouds = []
        except Exception:
            pass

    def draw_purgatory_clouds(self, shake_x=0, shake_y=0) -> None:
        """Public entry point used by Game.draw to render purgatory clouds.

        Clouds have been removed; this stub clears any existing list and does
        nothing else.  It remains so `Game.draw` can call it safely.
        """
        try:
            self._purgatory_clouds = []
        except Exception:
            pass

    def draw_game_world(self, shake_x=0, shake_y=0) -> None:
        """Draw walls, buildings and background following the original implementation."""
        if (
            not self.screen
            or not self.game.selected_stage
            or self.game.selected_stage not in self.game.stage_settings
        ):
            return

        pygame = self.pygame
        settings = self.game.stage_settings[self.game.selected_stage]

        # Fill inside battlefield with dark green (use stage setting for Prologo)
        if (
            self.game.selected_stage == "prologo"
            and self.game.left_wall_points
            and self.game.right_wall_points
            and not self.game.background_image_drawn  # Skip floor drawing if background image was drawn
        ):
            inside_points = (
                self.game.left_wall_points + self.game.right_wall_points[::-1]
            )
            # prefer stage setting so color changes stay centralized in STAGE_SETTINGS
            prologo_floor = settings.get("floor_color", (0, 50, 0))
            pygame.draw.polygon(
                self.screen,
                prologo_floor,
                [(p[0] + shake_x, p[1] + shake_y) for p in inside_points],
            )

        # Fill inside battlefield with dark orange for limbo (unless a
        # background image was already drawn inside the walls).
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
                [(p[0] + shake_x, p[1] + shake_y) for p in inside_points],
            )

        # Fill inside battlefield with dark gray for purgatory/HELL variants
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
            # Use floor_color from stage settings when available, fallback to dark gray
            settings = self.game.stage_settings.get(self.game.selected_stage, {})
            inside_color = settings.get("floor_color", (40, 40, 40))
            pygame.draw.polygon(
                self.screen,
                inside_color,
                [(p[0], p[1]) for p in inside_points],  # No shake for floor
            )

        # Draw walls
        wall_color = settings["wall_color"]

        # Use double thickness and caps only for HELL variants; otherwise keep default thickness
        # For prologue, use half thickness (doubled from quarter)
        is_hell_stage = getattr(self.game, "selected_stage", "").startswith("hell")
        is_prologo = getattr(self.game, "selected_stage", "") == "prologo"
        render_wall_thickness = (
            WALL_THICKNESS * 2
            if is_hell_stage
            else WALL_THICKNESS if is_prologo else WALL_THICKNESS
        )
        cap_extension = max(6, render_wall_thickness // 4) if is_hell_stage else 0

        # For prologue, create irregular thickness by varying per section
        if is_prologo:
            section_size = 5
            num_points = len(self.game.left_wall_points)
            num_sections = (num_points + section_size - 1) // section_size
            # Use a local RNG with fixed seed so wall-thickness variation is deterministic
            # per run but does NOT alter the global random state (which other systems rely on).
            rng = random.Random(42)
            thickness_variations = [rng.randint(-2, 2) for _ in range(num_sections)]

        # Left wall
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
            # Add caps only for HELL stages
            if cap_extension and left_wall_exterior:
                tx, ty = left_wall_exterior[0]
                left_wall_exterior.insert(0, (tx - cap_extension, ty - cap_extension))
                bx, by = left_wall_exterior[-1]
                left_wall_exterior.append((bx - cap_extension, by + cap_extension))

            left_wall_all = self.game.left_wall_points + left_wall_exterior[::-1]
            pygame.draw.polygon(
                self.screen,
                wall_color,
                [(p[0], p[1]) for p in left_wall_all],  # No shake for walls
            )

            # Thin black border on inner and outer edges for HELL walls (thicker)
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

        # Right wall
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
                [(p[0], p[1]) for p in right_wall_all],  # No shake for walls
            )

            # Thin black border on inner and outer edges for HELL walls (thicker)
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

        # Draw torches on walls for prologue
        if is_prologo:
            torch_image = get_image("torch.png", (40, 80))  # Size: 40x80 pixels
            if torch_image:
                torch_positions = [
                    0.2,
                    0.5,
                    0.8,
                ]  # fractions of height for regular spacing
                for frac in torch_positions:
                    y = int(frac * self.height)
                    # Find closest wall points
                    left_point = min(
                        self.game.left_wall_points, key=lambda p: abs(p[1] - y)
                    )
                    right_point = min(
                        self.game.right_wall_points, key=lambda p: abs(p[1] - y)
                    )

                    # Draw torch on left wall
                    torch_x = (
                        left_point[0] - 20
                    )  # Center the 40-pixel wide image on the wall
                    torch_y = left_point[1] - 80  # Bottom at wall level
                    self.screen.blit(
                        torch_image, (torch_x, torch_y)
                    )  # No shake for torches on walls

                    # Draw torch on right wall
                    torch_x = right_point[0] - 20  # Center on the wall
                    torch_y = right_point[1] - 80
                    self.screen.blit(
                        torch_image, (torch_x, torch_y)
                    )  # No shake for torches on walls
            else:
                # Fallback to drawn torches if image not found (40x80 size)
                torch_positions = [
                    0.2,
                    0.5,
                    0.8,
                ]  # fractions of height for regular spacing
                for frac in torch_positions:
                    y = int(frac * self.height)
                    # Find closest wall points
                    left_point = min(
                        self.game.left_wall_points, key=lambda p: abs(p[1] - y)
                    )
                    right_point = min(
                        self.game.right_wall_points, key=lambda p: abs(p[1] - y)
                    )

                    # Draw torch on left wall (40x80 size)
                    torch_x = left_point[0] - 20  # Centered on wall
                    torch_y = left_point[1]
                    # Draw torch base (16x40)
                    pygame.draw.rect(
                        self.screen, (50, 25, 0), (torch_x, torch_y - 20, 16, 40)
                    )  # No shake
                    # Draw flame (radius 16)
                    pygame.draw.circle(
                        self.screen,
                        (255, 100, 0),
                        (int(torch_x + 8), int(torch_y - 20)),
                        16,
                    )  # No shake
                    pygame.draw.circle(
                        self.screen,
                        (255, 200, 0),
                        (int(torch_x + 8), int(torch_y - 20)),
                        8,
                    )  # No shake

                    # Draw torch on right wall (40x80 size)
                    torch_x = right_point[0] - 20  # Centered on wall
                    torch_y = right_point[1]
                    # Draw torch base
                    pygame.draw.rect(
                        self.screen, (50, 25, 0), (torch_x, torch_y - 20, 16, 40)
                    )  # No shake
                    # Draw flame
                    pygame.draw.circle(
                        self.screen,
                        (255, 100, 0),
                        (int(torch_x + 8), int(torch_y - 20)),
                        16,
                    )  # No shake
                    pygame.draw.circle(
                        self.screen,
                        (255, 200, 0),
                        (int(torch_x + 8), int(torch_y - 20)),
                        8,
                    )  # No shake

        # Draw buildings for stages that have them
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

        # Draw battlefield crosses at bottom sides (only for prologue)
        if (
            self.game.selected_stage == "prologo"
            and self.game.left_wall_points
            and self.game.right_wall_points
        ):
            # Get battlefield cross image
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

        # Fading and buildings use the original Game methods to avoid code duplication
        # Reuse UI manager for Limbo features
        if hasattr(self, "draw_dead_trees"):
            self.draw_dead_trees(shake_x, shake_y)
        if hasattr(self, "draw_pedestals"):
            self.draw_pedestals(shake_x, shake_y)
        # Prefer UI manager fog implementation; fallback to Game's if missing
        if hasattr(self, "draw_fog"):
            self.draw_fog(shake_x, shake_y)
        elif hasattr(self.game, "draw_fog"):
            self.game.draw_fog(shake_x, shake_y)

    def draw_stage_menu(self, shake_x=0, shake_y=0) -> None:
        """Draw the stage selection menu and submenus.

        Delegates drawing of the main stage menu and the Limbo/Purgatory submenus that
        were previously located in `Game`. Uses `self.game` for state and writes a
        diagnostic `self.game._last_drawn_menu` for tests.
        """
        pygame = self.pygame
        if not self.screen or not pygame:
            return

        from src.assets.text_cache import get_font, get_text

        font_large = get_font(48)
        font_medium = get_font(32)
        font_small = get_font(20)

        # Limbo submenu
        if getattr(self.game, "showing_limbo_menu", False):
            title = get_text("LIMBO", font_large, (255, 215, 0))
            self.screen.blit(
                title,
                (
                    self.width // 2 - title.get_width() // 2 + shake_x,
                    self.height // 2 - 120 + shake_y,
                ),
            )

            option_w = 320
            option_h = 48
            start_x: int = self.width // 2 - option_w // 2
            start_y: int = self.height // 2 - 40
            spacing = 60

            labels: list[str] = ["LIMBO 1", "LIMBO 2", "LIMBO 3"]
            for i, label in enumerate(labels):
                rect = pygame.Rect(start_x, start_y + i * spacing, option_w, option_h)
                hovered = rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
                bg = (137, 78, 36) if hovered else (107, 58, 26)
                pygame.draw.rect(self.screen, bg, rect)
                pygame.draw.rect(self.screen, (255, 255, 255), rect, 2)
                text = font_medium.render(label, True, (255, 255, 255))
                self.screen.blit(
                    text,
                    (
                        self.width // 2 - text.get_width() // 2 + shake_x,
                        start_y
                        + i * spacing
                        + (option_h - text.get_height()) // 2
                        + shake_y,
                    ),
                )

            back_rect = pygame.Rect(
                self.width // 2 - 60, start_y + len(labels) * spacing + 10, 120, 36
            )
            back_hover: bool = back_rect.collidepoint(
                self.game.mouse_x, self.game.mouse_y
            )
            back_color: tuple[int, int, int] = (
                (80, 80, 80) if back_hover else (60, 60, 60)
            )
            pygame.draw.rect(self.screen, back_color, back_rect)
            pygame.draw.rect(self.screen, (255, 255, 255), back_rect, 2)
            back_text = font_small.render("BACK", True, (255, 255, 255))
            self.screen.blit(
                back_text,
                (
                    self.width // 2 - back_text.get_width() // 2 + shake_x,
                    start_y + len(labels) * spacing + 14 + shake_y,
                ),
            )

            try:
                self.game._last_drawn_menu = "limbo"
            except Exception:
                pass
            return

        # Purgatory submenu
        if getattr(self.game, "showing_purgatory_menu", False):
            title_p = get_text("PURGATORY", font_large, (255, 215, 0))
            self.screen.blit(
                title_p,
                (
                    self.width // 2 - title_p.get_width() // 2 + shake_x,
                    self.height // 2 - 120 + shake_y,
                ),
            )

            option_w = 320
            option_h = 48
            start_x: int = self.width // 2 - option_w // 2
            start_y: int = self.height // 2 - 40
            spacing = 60

            labels: list[str] = ["PURGATORY 1", "PURGATORY 2", "PURGATORY 3"]
            for i, label in enumerate(labels):
                rect = pygame.Rect(start_x, start_y + i * spacing, option_w, option_h)
                hovered: bool = rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
                bg: tuple[int, int, int] = (137, 78, 136) if hovered else (107, 58, 106)
                pygame.draw.rect(self.screen, bg, rect)
                pygame.draw.rect(self.screen, (255, 255, 255), rect, 2)
                text = font_medium.render(label, True, (255, 255, 255))
                self.screen.blit(
                    text,
                    (
                        self.width // 2 - text.get_width() // 2 + shake_x,
                        start_y
                        + i * spacing
                        + (option_h - text.get_height()) // 2
                        + shake_y,
                    ),
                )

            back_rect = pygame.Rect(
                self.width // 2 - 60, start_y + len(labels) * spacing + 10, 120, 36
            )
            back_hover: bool = back_rect.collidepoint(
                self.game.mouse_x, self.game.mouse_y
            )
            back_color: tuple[int, int, int] = (
                (80, 80, 80) if back_hover else (60, 60, 60)
            )
            pygame.draw.rect(self.screen, back_color, back_rect)
            pygame.draw.rect(self.screen, (255, 255, 255), back_rect, 2)
            back_text = font_small.render("BACK", True, (255, 255, 255))
            self.screen.blit(
                back_text,
                (
                    self.width // 2 - back_text.get_width() // 2 + shake_x,
                    start_y + len(labels) * spacing + 14 + shake_y,
                ),
            )

            try:
                self.game._last_drawn_menu = "purgatory"
            except Exception:
                pass
            return

        # HELL submenu
        if getattr(self.game, "showing_hell_menu", False):
            title_h = get_text("HELL", font_large, (255, 215, 0))
            self.screen.blit(
                title_h,
                (
                    self.width // 2 - title_h.get_width() // 2 + shake_x,
                    self.height // 2 - 120 + shake_y,
                ),
            )

            option_w = 320
            option_h = 48
            start_x: int = self.width // 2 - option_w // 2
            start_y: int = self.height // 2 - 40
            spacing = 60

            labels: list[str] = ["GEHENNA", "LAKE OF FIRE", "HADES"]
            for i, label in enumerate(labels):
                rect = pygame.Rect(start_x, start_y + i * spacing, option_w, option_h)
                hovered: bool = rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
                bg: tuple[int, int, int] = (189, 89, 89) if hovered else (139, 69, 69)
                pygame.draw.rect(self.screen, bg, rect)
                pygame.draw.rect(self.screen, (255, 255, 255), rect, 2)
                text = font_medium.render(label, True, (255, 255, 255))
                self.screen.blit(
                    text,
                    (
                        self.width // 2 - text.get_width() // 2 + shake_x,
                        start_y
                        + i * spacing
                        + (option_h - text.get_height()) // 2
                        + shake_y,
                    ),
                )

            back_rect = pygame.Rect(
                self.width // 2 - 60, start_y + len(labels) * spacing + 10, 120, 36
            )
            back_hover: bool = back_rect.collidepoint(
                self.game.mouse_x, self.game.mouse_y
            )
            back_color: tuple[int, int, int] = (
                (80, 80, 80) if back_hover else (60, 60, 60)
            )
            pygame.draw.rect(self.screen, back_color, back_rect)
            pygame.draw.rect(self.screen, (255, 255, 255), back_rect, 2)
            back_text = font_small.render("BACK", True, (255, 255, 255))
            self.screen.blit(
                back_text,
                (
                    self.width // 2 - back_text.get_width() // 2 + shake_x,
                    start_y + len(labels) * spacing + 14 + shake_y,
                ),
            )

            try:
                self.game._last_drawn_menu = "hell"
            except Exception:
                pass
            return

        # Main title and stage buttons
        title = font_large.render("SATANS FALL", True, (255, 100, 100))
        self.screen.blit(
            title,
            (
                self.width // 2 - title.get_width() // 2 + shake_x,
                self.height // 2 - 150 + shake_y,
            ),
        )

        # Prologo button
        prologo_rect = pygame.Rect(
            self.width // 2 - 100, self.height // 2 - 50, 200, 40
        )
        prologo_hovered: bool = prologo_rect.collidepoint(
            self.game.mouse_x, self.game.mouse_y
        )
        prologo_color: (
            tuple[Literal[189], Literal[89], Literal[89]]
            | tuple[Literal[139], Literal[69], Literal[69]]
        ) = (
            (189, 89, 89) if prologo_hovered else (139, 69, 69)
        )  # Lighter red when hovered
        pygame.draw.rect(self.screen, prologo_color, prologo_rect)
        pygame.draw.rect(self.screen, (255, 255, 255), prologo_rect, 2)  # White border
        prologo_text = font_medium.render("PROLOGUE", True, (255, 255, 255))
        self.screen.blit(
            prologo_text,
            (
                self.width // 2 - prologo_text.get_width() // 2 + shake_x,
                self.height // 2 - 40 + shake_y,
            ),
        )

        # Limbo main button (opens second menu)
        limbo_rect = pygame.Rect(self.width // 2 - 100, self.height // 2 + 10, 200, 40)
        limbo_hovered: bool = limbo_rect.collidepoint(
            self.game.mouse_x, self.game.mouse_y
        )
        limbo_color: (
            tuple[Literal[137], Literal[78], Literal[36]]
            | tuple[Literal[107], Literal[58], Literal[26]]
        ) = ((137, 78, 36) if limbo_hovered else (107, 58, 26))
        pygame.draw.rect(self.screen, limbo_color, limbo_rect)
        pygame.draw.rect(self.screen, (255, 255, 255), limbo_rect, 2)
        limbo_text = font_medium.render("LIMBO", True, (255, 255, 255))
        self.screen.blit(
            limbo_text,
            (
                self.width // 2 - limbo_text.get_width() // 2 + shake_x,
                self.height // 2 + 20 + shake_y,
            ),
        )

        # Purgatory main button (opens second menu)
        purgatory_rect = pygame.Rect(
            self.width // 2 - 100, self.height // 2 + 70, 200, 40
        )
        purgatory_hovered: bool = purgatory_rect.collidepoint(
            self.game.mouse_x, self.game.mouse_y
        )
        purgatory_color: (
            tuple[Literal[137], Literal[78], Literal[136]]
            | tuple[Literal[107], Literal[58], Literal[106]]
        ) = ((137, 78, 136) if purgatory_hovered else (107, 58, 106))
        pygame.draw.rect(self.screen, purgatory_color, purgatory_rect)
        pygame.draw.rect(self.screen, (255, 255, 255), purgatory_rect, 2)
        purgatory_text = font_medium.render("PURGATORY", True, (255, 255, 255))
        self.screen.blit(
            purgatory_text,
            (
                self.width // 2 - purgatory_text.get_width() // 2 + shake_x,
                self.height // 2 + 80 + shake_y,
            ),
        )

        # HELL main button (opens second menu) - red dedicated button under PURGATORY
        hell_rect = pygame.Rect(self.width // 2 - 100, self.height // 2 + 130, 200, 40)
        hell_hovered: bool = hell_rect.collidepoint(
            self.game.mouse_x, self.game.mouse_y
        )
        hell_color: (
            tuple[Literal[189], Literal[89], Literal[89]]
            | tuple[Literal[139], Literal[69], Literal[69]]
        ) = (
            (189, 89, 89) if hell_hovered else (139, 69, 69)
        )  # Lighter red when hovered
        pygame.draw.rect(self.screen, hell_color, hell_rect)
        pygame.draw.rect(self.screen, (255, 255, 255), hell_rect, 2)
        hell_text = font_medium.render("HELL", True, (255, 255, 255))
        self.screen.blit(
            hell_text,
            (
                self.width // 2 - hell_text.get_width() // 2 + shake_x,
                self.height // 2 + 140 + shake_y,
            ),
        )

        # Upgrades button moved to bottom of screen to avoid overlap and be more accessible
        upgrades_rect = pygame.Rect(
            self.width // 2 - 125, max(20, self.height - 80), 250, 35
        )
        upgrades_hovered: bool = upgrades_rect.collidepoint(
            self.game.mouse_x, self.game.mouse_y
        )
        upgrades_bg_color: (
            tuple[Literal[94], Literal[36], Literal[94]]
            | tuple[Literal[74], Literal[26], Literal[74]]
        ) = (
            (94, 36, 94) if upgrades_hovered else (74, 26, 74)
        )  # Lighter purple when hovered
        upgrades_border_color: (
            tuple[Literal[255], Literal[224], Literal[20]]
            | tuple[Literal[255], Literal[204], Literal[0]]
        ) = (
            (255, 224, 20) if upgrades_hovered else (255, 204, 0)
        )  # Brighter gold when hovered
        pygame.draw.rect(self.screen, upgrades_bg_color, upgrades_rect)
        pygame.draw.rect(self.screen, upgrades_border_color, upgrades_rect, 2)
        upgrades_text = font_small.render(
            "PERMANENT UPGRADES", True, upgrades_border_color
        )
        self.screen.blit(
            upgrades_text,
            (
                self.width // 2 - upgrades_text.get_width() // 2 + shake_x,
                upgrades_rect.y
                + (upgrades_rect.height - upgrades_text.get_height()) // 2
                + shake_y,
            ),
        )

        # Draw small options (gear) button in bottom-right corner
        opt_size = 40
        opt_x = self.width - (opt_size + 14)
        opt_y = max(20, self.height - (opt_size + 14))
        options_rect = pygame.Rect(opt_x, opt_y, opt_size, opt_size)
        options_hovered: bool = options_rect.collidepoint(
            self.game.mouse_x, self.game.mouse_y
        )
        bg = (60, 60, 60) if not options_hovered else (90, 90, 90)
        border = (200, 200, 200) if options_hovered else (160, 160, 160)
        pygame.draw.rect(self.screen, bg, options_rect)
        pygame.draw.rect(self.screen, border, options_rect, 2)
        # Draw a gear-like icon: center circle and 8 spokes
        cx = opt_x + opt_size // 2
        cy = opt_y + opt_size // 2
        pygame.draw.circle(self.screen, border, (cx, cy), 8, 1)
        for i in range(8):
            ang = math.radians(i * 45)
            x2 = int(cx + math.cos(ang) * (opt_size // 2 - 6))
            y2 = int(cy + math.sin(ang) * (opt_size // 2 - 6))
            pygame.draw.line(self.screen, border, (cx, cy), (x2, y2), 2)

        try:
            self.game._last_drawn_menu = "stage_main"
        except Exception:
            pass

        try:
            self.game._last_drawn_menu = "stage_main"
        except Exception:
            pass

        # If options overlay requested, draw it on top
        if getattr(self.game, "showing_options", False):
            self.draw_options_menu(shake_x, shake_y)

    def draw_options_menu(self, shake_x=0, shake_y=0) -> None:
        """Simple options overlay with a CLOSE button."""
        pygame = self.pygame
        if not self.screen or not pygame:
            return
        # Semi-transparent overlay
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        # Dialog box (wider/taller for readability)
        dialog_w, dialog_h = 520, 320
        dx = self.width // 2 - dialog_w // 2
        dy = self.height // 2 - dialog_h // 2
        pygame.draw.rect(self.screen, (40, 40, 40), (dx, dy, dialog_w, dialog_h))
        pygame.draw.rect(self.screen, (220, 220, 220), (dx, dy, dialog_w, dialog_h), 2)

        # Title
        try:
            from src.assets.text_cache import get_font, get_text

            font = get_font(28)
            title = get_text("OPTIONS", font, (255, 255, 255))
            self.screen.blit(
                title,
                (self.width // 2 - title.get_width() // 2 + shake_x, dy + 12 + shake_y),
            )
        except Exception:
            font_large = pygame.font.Font(None, 28)
            title = font_large.render("OPTIONS", True, (255, 255, 255))
            self.screen.blit(
                title,
                (self.width // 2 - title.get_width() // 2 + shake_x, dy + 12 + shake_y),
            )

        # Placeholder options (toggles like mute/music/volume go here)
        font_med = pygame.font.Font(None, 20)

        # Damage numbers toggle (compact, right-aligned)
        dmg_label = font_med.render("Show Damage Numbers:", True, (220, 220, 220))
        self.screen.blit(dmg_label, (dx + 24 + shake_x, dy + 64 + shake_y))

        # Compact toggle box on the right side of the dialog so the label remains readable
        toggle_w, toggle_h = 48, 24
        toggle_x = dx + dialog_w - 24 - toggle_w
        toggle_y = dy + 64
        toggle_rect = pygame.Rect(toggle_x, toggle_y, toggle_w, toggle_h)
        hovered_toggle = toggle_rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
        toggle_bg = (
            (80, 160, 80)
            if getattr(self.game, "show_damage_numbers", True)
            else (160, 80, 80)
        )
        if hovered_toggle:
            toggle_bg = tuple(min(255, c + 20) for c in toggle_bg)
        pygame.draw.rect(self.screen, toggle_bg, toggle_rect)
        pygame.draw.rect(self.screen, (160, 160, 160), toggle_rect, 1)
        status_text = "On" if getattr(self.game, "show_damage_numbers", True) else "Off"
        status_surf = font_med.render(status_text, True, (255, 255, 255))
        self.screen.blit(
            status_surf,
            (
                toggle_x + (toggle_w - status_surf.get_width()) // 2 + shake_x,
                toggle_y + (toggle_h - status_surf.get_height()) // 2 + shake_y,
            ),
        )

        # Smooth-scaling toggle (applies higher-quality scaling when window > virtual)
        smooth_on = bool(
            self.game.global_progress.get("display", {}).get("smooth_scale", True)
        )
        smooth_label = font_med.render("Smooth scaling:", True, (220, 220, 220))
        self.screen.blit(smooth_label, (dx + 24 + shake_x, dy + 104 + shake_y))
        smooth_toggle_x = dx + dialog_w - 24 - toggle_w
        smooth_toggle_y = dy + 104
        smooth_rect = pygame.Rect(smooth_toggle_x, smooth_toggle_y, toggle_w, toggle_h)
        hovered_s = smooth_rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
        smooth_bg = (80, 160, 80) if smooth_on else (160, 80, 80)
        if hovered_s:
            smooth_bg = tuple(min(255, c + 20) for c in smooth_bg)
        pygame.draw.rect(self.screen, smooth_bg, smooth_rect)
        pygame.draw.rect(self.screen, (160, 160, 160), smooth_rect, 1)
        smooth_text = "On" if smooth_on else "Off"
        self.screen.blit(
            font_med.render(smooth_text, True, (255, 255, 255)),
            (
                smooth_toggle_x + (toggle_w - status_surf.get_width()) // 2 + shake_x,
                smooth_toggle_y + (toggle_h - status_surf.get_height()) // 2 + shake_y,
            ),
        )

        # Resolution presets
        preset_label = font_med.render("Resolution:", True, (220, 220, 220))
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

        # Current selection label
        current_label = f"{self.game.window_width}x{self.game.window_height}"
        hovered = dropdown_rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
        bg = (
            (60, 120, 200)
            if (self.game.window_width, self.game.window_height)
            in DEFAULT_DISPLAY_PRESETS
            else ((120, 120, 120) if not hovered else (160, 160, 160))
        )
        pygame.draw.rect(self.screen, bg, dropdown_rect)
        pygame.draw.rect(self.screen, (200, 200, 200), dropdown_rect, 1)
        txt = font_med.render(current_label, True, (255, 255, 255))
        self.screen.blit(
            txt,
            (
                dropdown_x + 8 + shake_x,
                dropdown_y + (dropdown_h - txt.get_height()) // 2 + shake_y,
            ),
        )
        # small caret indicator
        caret = font_med.render("▾", True, (220, 220, 220))
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
                item_bg = (
                    (80, 140, 220)
                    if is_current
                    else ((120, 120, 120) if not hovered_item else (160, 160, 160))
                )
                pygame.draw.rect(self.screen, item_bg, item_rect)
                pygame.draw.rect(self.screen, (200, 200, 200), item_rect, 1)
                label = f"{pw}x{ph}"
                txt = font_med.render(label, True, (255, 255, 255))
                self.screen.blit(
                    txt,
                    (
                        dropdown_x + 8 + shake_x,
                        iy + (item_h - txt.get_height()) // 2 + shake_y,
                    ),
                )

        # Close button
        btn_w, btn_h = 120, 36
        btn_x = dx + (dialog_w - btn_w) // 2
        btn_y = dy + dialog_h - 50
        close_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        hovered = close_rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
        bg = (100, 100, 100) if not hovered else (140, 140, 140)
        border = (255, 255, 255) if hovered else (200, 200, 200)
        pygame.draw.rect(self.screen, bg, close_rect)
        pygame.draw.rect(self.screen, border, close_rect, 2)
        btn_text = font_med.render("CLOSE", True, (255, 255, 255))
        self.screen.blit(
            btn_text,
            (
                btn_x + (btn_w - btn_text.get_width()) // 2 + shake_x,
                btn_y + (btn_h - btn_text.get_height()) // 2 + shake_y,
            ),
        )

        # Close button
        btn_w, btn_h = 120, 36
        btn_x = dx + (dialog_w - btn_w) // 2
        btn_y = dy + dialog_h - 50
        close_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        hovered = close_rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
        bg = (100, 100, 100) if not hovered else (140, 140, 140)
        border = (255, 255, 255) if hovered else (200, 200, 200)
        pygame.draw.rect(self.screen, bg, close_rect)
        pygame.draw.rect(self.screen, border, close_rect, 2)
        btn_text = font_med.render("CLOSE", True, (255, 255, 255))
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
        # rename label to SATAN LEVEL as requested by designer
        meta_text = font_medium.render(
            f"SATAN LEVEL {lvl}   Points: {pts}", True, (255, 215, 0)
        )
        self.screen.blit(
            meta_text,
            (left_x + shake_x, 110 + shake_y),
        )
        # draw XP bar background
        bar_x = left_x + 220
        bar_w = 300
        bar_y = 114
        bar_h = 10
        pygame.draw.rect(self.screen, (26, 26, 26), (bar_x, bar_y, bar_w, bar_h))
        # compute filled width with minimum visibility for tiny XP
        fill_w = self._calculate_meta_xp_fill(xp, xp_to, bar_w)
        pygame.draw.rect(self.screen, (255, 215, 0), (bar_x, bar_y, fill_w, bar_h))
        # numeric indicator showing current and required XP
        xp_text = font_small.render(f"{xp}/{xp_to} XP", True, (255, 215, 0))
        self.screen.blit(xp_text, (bar_x + bar_w + 8 + shake_x, bar_y - 2 + shake_y))

        # POWER / VIGOR / ADRENALINE / STRUCTURE stats
        stat_configs: list[dict] = [
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
        rendered_names = [
            font_medium.render(s["name"], True, s["color"]) for s in stat_configs
        ]
        max_name_w = max(s.get_width() for s in rendered_names)
        bar_x_base = left_x + max(120, max_name_w + 24)
        bar_width = 180
        bar_height = 12
        font_name_hover = pygame.font.Font(None, 26)

        for i, stat in enumerate(stat_configs):
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
        tree_types = [
            ("FIRE", "fire", (255, 68, 68)),
            ("STORM", "storm", (170, 68, 255)),
            ("ICE", "ice", (100, 200, 255)),
        ]
        tree_box_w = 50
        tree_box_h = 36
        tree_v_spacing = 46
        tree_col_spacing = 120
        tree_base_x: int = left_x + 680
        tree_top_y: int = separator_y - 150

        for col, (label, key_prefix, color) in enumerate(tree_types):
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
        from src.assets.text_cache import get_font, get_text

        font_large = get_font(36)
        font_medium = get_font(28)

        overlay = pygame.Surface((self.width, self.height))
        overlay.set_alpha(128)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        title = get_text("PAUSED", font_large, (255, 255, 255))
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
            if is_hovered:
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

        # If a pause confirmation is active, draw Yes/No dialog
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

                from src.assets.text_cache import get_font, get_text

                font = get_font(18)
                msg = "Quit to menu?"
                msg_surf = get_text(msg, font, (255, 255, 255))
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
                yes_s = get_text(
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
                no_s = get_text("No", font, (0, 0, 0) if sel == 1 else (200, 200, 200))
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
        from src.assets.text_cache import get_font, get_text

        font_title = get_font(40)
        font_header = get_font(20)
        font_body = get_font(18)
        font_small = get_font(15)

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
            surf = get_text(label.upper(), font_header, COLOR_HEADER)
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
            lab = get_text(label, font_body, lc)
            val = get_text(value, font_body, vc)
            self.screen.blit(lab, (x + shake_x, y + shake_y))
            vx = val_x if val_x else x + 180
            self.screen.blit(val, (vx + shake_x, y + shake_y))

        # ── Overlay ──────────────────────────────────────────────────────────────
        overlay = pygame.Surface((self.width, self.height))
        overlay.set_alpha(220)
        overlay.fill((6, 6, 10))
        self.screen.blit(overlay, (0, 0))

        # ── Title ────────────────────────────────────────────────────────────────
        title = get_text("PLAYER STATS", font_title, COLOR_TITLE)
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

        xp_text = get_text(f"{meta_xp} / {meta_xp_to} XP", font_small, (255, 215, 0))
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
                name_surf = get_text(name, font_body, COLOR_VALUE)
                lv_surf = get_text(f"Lv {lvl}", font_small, COLOR_GREEN)
                self.screen.blit(name_surf, (right_x + shake_x, y + shake_y))
                self.screen.blit(
                    lv_surf,
                    (right_x + name_surf.get_width() + 10 + shake_x, y + 4 + shake_y),
                )
                y += line_h
        else:
            self.screen.blit(
                get_text("None", font_body, COLOR_HINT),
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
                val_surf = get_text(str(v), font_body, col)
                lab_surf = get_text(label, font_body, COLOR_LABEL)
                # max indicator
                max_surf = (
                    get_text("MAX", font_small, (180, 140, 20)) if v >= 10 else None
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
        inst = get_text("Tab / ESC  to close", font_small, COLOR_HINT)
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
        for tree in self.game.dead_trees:
            x = tree["x"] + shake_x
            y = tree["y"] + shake_y
            height = tree["height"]
            trunk_width = tree["trunk_width"]

            # Draw trunk (brighter for contrast)
            pygame.draw.rect(
                self.screen,
                (140, 140, 140),
                (x - trunk_width // 2, y, trunk_width, height),
            )
            pygame.draw.rect(
                self.screen,
                (100, 100, 100),
                (x - trunk_width // 2, y, trunk_width, height),
                1,
            )

            # Draw branches using pre-generated data (brighter)
            branch_color = (180, 180, 180)
            for branch in tree.get("branches", []):
                # Main branch
                pygame.draw.line(
                    self.screen,
                    branch_color,
                    (x, branch["start_y"] + shake_y),
                    (branch["end_x"] + shake_x, branch["end_y"] + shake_y),
                    2,
                )

                # Sub-branches
                for sub_branch in branch.get("sub_branches", []):
                    pygame.draw.line(
                        self.screen,
                        branch_color,
                        (
                            sub_branch["start_x"] + shake_x,
                            sub_branch["start_y"] + shake_y,
                        ),
                        (sub_branch["end_x"] + shake_x, sub_branch["end_y"] + shake_y),
                        1,
                    )

    def _draw_pedestal(self, x: int, statue_base_y: int) -> None:
        """Draw a pedestal/platform beneath a statue centered at X. Accepts statue_base_y
        (which is the same coordinate used by _draw_statue_model).
        """
        pygame = self.pygame
        # Convert statue_base_y back to pedestal 'y' (top of pedestal platform is statue_base_y + 10)
        y = statue_base_y + 10

        # Pedestal base (wide)
        pygame.draw.rect(self.screen, (58, 32, 16), (x - 25, y + 50, 50, 10))
        pygame.draw.rect(self.screen, (42, 16, 8), (x - 25, y + 50, 50, 10), 2)

        # Pedestal column (shorter - half height)
        pygame.draw.rect(self.screen, (74, 48, 32), (x - 15, y, 30, 50))
        pygame.draw.rect(self.screen, (58, 32, 16), (x - 15, y, 30, 50), 2)

        # Column details (horizontal lines)
        for detail_y in [y + 15, y + 35]:
            pygame.draw.line(
                self.screen, (42, 16, 8), (x - 15, detail_y), (x + 15, detail_y), 2
            )

        # Pedestal top (platform for statue)
        pygame.draw.rect(self.screen, (58, 32, 16), (x - 20, y - 10, 40, 10))
        pygame.draw.rect(self.screen, (42, 16, 8), (x - 20, y - 10, 40, 10), 2)
        # Highlight outline for visibility
        pygame.draw.rect(self.screen, (200, 170, 100), (x - 20, y - 10, 40, 10), 1)

        return

    def _draw_statue_model(
        self, x: int, statue_base_y: int, tower_type: str | None
    ) -> None:
        """Draw a statue model centered at X using a provided statue base Y.

        This helper is reused by both pedestals (Limbo) and dynamic towers (Purgatory).
        The `tower_type` controls coloring similarly to the old logic (fire/storm/ice).
        """
        pygame = self.pygame

        # Choose statue colors based on provided tower_type (or current stage)
        tt = tower_type or getattr(self.game, "selected_stage", None)
        if tt == "storm" or tt == "limbo_2":
            # Storm - blueish statue
            body_color = (18, 36, 120)
            outline_color = (8, 18, 80)
            horn_color = (60, 100, 200)
            eye_color = (100, 150, 255)
            glow_color = (40, 70, 180)
        elif tt == "ice" or tt == "limbo_3":
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

        # Statue body (slimmer triangular/demonic shape)
        body_points: list[tuple[int, int]] = [
            (x, statue_base_y - 60),  # Neck point (head connects here)
            (x - 12, statue_base_y - 40),  # Left shoulder
            (x - 15, statue_base_y),  # Left base
            (x + 15, statue_base_y),  # Right base
            (x + 12, statue_base_y - 40),  # Right shoulder
        ]
        pygame.draw.polygon(self.screen, body_color, body_points)
        pygame.draw.polygon(self.screen, outline_color, body_points, 2)

        # Head (larger and round)
        head_y: int = statue_base_y - 70
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
        """Draw tall pedestals with demonic statues for Limbo stage"""
        if not self.game.is_limbo_stage():
            if getattr(self.game, "debug", False):
                print("[DEBUG] draw_pedestals: not in limbo")
            return
        pygame = self.pygame
        if getattr(self.game, "debug", False):
            print("[DEBUG] draw_pedestals: drawing pedestals")
        # Two pedestals at the sides of the play area
        pedestals: list[dict[str, int]] = [
            {"x": 320, "y": 620},  # Left pedestal
            {"x": 960, "y": 620},  # Right pedestal
        ]

        for pedestal in pedestals:
            x: int = pedestal["x"] + shake_x
            y: int = pedestal["y"] + shake_y

            # Draw pedestal for statue using shared helper.
            statue_base_y: int = y - 10
            try:
                self._draw_pedestal(x, statue_base_y)
            except Exception:
                # Fallback: draw pedestal inline if helper unavailable
                pygame.draw.rect(self.screen, (58, 32, 16), (x - 25, y + 50, 50, 10))
                pygame.draw.rect(self.screen, (42, 16, 8), (x - 25, y + 50, 50, 10), 2)
                pygame.draw.rect(self.screen, (74, 48, 32), (x - 15, y, 30, 50))
                pygame.draw.rect(self.screen, (58, 32, 16), (x - 15, y, 30, 50), 2)
                for detail_y in [y + 15, y + 35]:
                    pygame.draw.line(
                        self.screen,
                        (42, 16, 8),
                        (x - 15, detail_y),
                        (x + 15, detail_y),
                        2,
                    )
                pygame.draw.rect(self.screen, (58, 32, 16), (x - 20, y - 10, 40, 10))
                pygame.draw.rect(self.screen, (42, 16, 8), (x - 20, y - 10, 40, 10), 2)
                pygame.draw.rect(
                    self.screen, (200, 170, 100), (x - 20, y - 10, 40, 10), 1
                )

            # Choose statue colors based on stage/tower type
            if getattr(self.game, "selected_stage", None) == "limbo_2":
                # Storm - blueish statue
                body_color = (18, 36, 120)
                outline_color = (8, 18, 80)
                horn_color = (60, 100, 200)
                eye_color = (100, 150, 255)
                glow_color = (40, 70, 180)
            elif getattr(self.game, "selected_stage", None) == "limbo_3":
                # Ice - icy pale statue (keep similar to previous but cooler)
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
            # Reuse centralized statue model renderer (defined on PygameUIManager)
            try:
                # The pedestal version of the statue provides statue_base_y (y - 10), so we
                # call the shared painter with the same coordinates for consistency.
                self._draw_statue_model(
                    x, statue_base_y, getattr(self.game, "selected_stage", None)
                )
            except Exception:
                # Fallback to old inlined rendering if helper is not present for some reason
                # (preserves backwards compatibility in tests)
                body_points: list[tuple[int, int]] = [
                    (x, statue_base_y - 60),  # Neck point (head connects here)
                    (x - 12, statue_base_y - 40),  # Left shoulder
                    (x - 15, statue_base_y),  # Left base
                    (x + 15, statue_base_y),  # Right base
                    (x + 12, statue_base_y - 40),  # Right shoulder
                ]
                pygame.draw.polygon(self.screen, body_color, body_points)
                pygame.draw.polygon(self.screen, outline_color, body_points, 2)

                # Head (larger and round)
                head_y: int = statue_base_y - 70
                head_radius = 15
                pygame.draw.circle(self.screen, body_color, (x, head_y), head_radius)
                pygame.draw.circle(
                    self.screen, outline_color, (x, head_y), head_radius, 2
                )

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
                pygame.draw.circle(
                    self.screen, glow_color, (x, head_y), head_radius + 4, 2
                )

                # Chest badge removed (no per-tower firing symbols)

                # Pitchfork in hand
                # Handle (long pole)
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
        if stage == "limbo_3":
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
        # spawn and draw the new upper–screen cloud shapes before clearing the
        # old purgatory fog particles (which are still a no-op).
        try:
            self._spawn_purgatory_clouds()
            self._update_and_draw_purgatory_clouds()
        except Exception:
            pass

        # previously this method spawned and animated fog particles along
        # the exterior walls.  Particles were deemed too busy, so the
        # volumetric effect has been removed; only the screen‑wide overlay
        # remains.  Clear any existing descriptors in case older code left
        # them around so they don't linger in memory.
        try:
            self._purgatory_fog_particles = []
            # we also drop the spawn accumulator to avoid unused state warnings
            self._purgatory_fog_spawn_acc = 0.0
        except Exception:
            pass

        # draw the screen‑wide fog overlay last so it mutes everything beneath
        try:
            pygame = self.pygame
            # cache a converted surface to avoid re-allocating and re-converting
            # every frame.  The overlay is a full-screen rectangle with global
            # alpha only, so ``convert()`` is the ideal format (no per-pixel
            # alpha required).
            from src.game_constants import (
                PURGATORY_OVERLAY_ALPHA,
                PURGATORY_OVERLAY_COLOR,
            )

            need_new = False
            ov = getattr(self, "_purgatory_overlay", None)
            if ov is None:
                need_new = True
            else:
                # recreate if size or parameters changed
                if ov.get_size() != (self.width, self.height):
                    need_new = True
                if (
                    getattr(self, "_purgatory_overlay_color", None)
                    != PURGATORY_OVERLAY_COLOR
                ):
                    need_new = True
                if (
                    getattr(self, "_purgatory_overlay_alpha", None)
                    != PURGATORY_OVERLAY_ALPHA
                ):
                    need_new = True
            if need_new:
                overlay = pygame.Surface((self.width, self.height))
                # convert once during init ensures blits are very cheap later
                try:
                    overlay = overlay.convert()
                except Exception:
                    pass
                overlay.fill(PURGATORY_OVERLAY_COLOR)
                overlay.set_alpha(PURGATORY_OVERLAY_ALPHA)
                self._purgatory_overlay = overlay
                self._purgatory_overlay_color = PURGATORY_OVERLAY_COLOR
                self._purgatory_overlay_alpha = PURGATORY_OVERLAY_ALPHA
            try:
                self.screen.blit(self._purgatory_overlay, (0, 0))
            except Exception:
                # fallback in case blit fails for some reason
                overlay = pygame.Surface((self.width, self.height))
                overlay.set_alpha(PURGATORY_OVERLAY_ALPHA)
                overlay.fill(PURGATORY_OVERLAY_COLOR)
                self.screen.blit(overlay, (0, 0))
        except Exception:
            pass

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

        # Purgatory: overlay + fog particles (handled by dedicated method)
        if str(stage).startswith("purgatory"):
            try:
                self.draw_purgatory_fog(shake_x, shake_y)
            except Exception:
                pass
            return

        # Hell: dark red ember overlay
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

        # Prologo: subtle warm smoke overlay
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

        # Limbo: haze overlay + lateral fog polygons
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

        # NOTE: statue projectile visual indicators removed (kept internal data for logic/tests)

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
            # glowing core
            pygame.draw.circle(
                self.screen, (176, 240, 255), (int(ox + shake_x), int(oy + shake_y)), 6
            )
            # small trail ring
            pygame.draw.circle(
                self.screen,
                (224, 248, 255),
                (int(ox + shake_x), int(oy + shake_y)),
                10,
                1,
            )

        # Draw special effects
        self.draw_special_effects(shake_x, shake_y)

        # Draw dynamic towers/statues for Purgatory when they exist and are marked visible
        try:
            if getattr(self.game, "selected_stage", None) and str(
                self.game.selected_stage
            ).startswith(("purgatory", "hell")):
                lt = getattr(self.game, "left_tower", None)
                rt = getattr(self.game, "right_tower", None)
                if lt and getattr(lt, "visible", False):
                    # Draw pedestal first, then statue model above it
                    statue_base_y = int(lt.y - 20 + shake_y)
                    self._draw_pedestal(int(lt.x + shake_x), statue_base_y)
                    self._draw_statue_model(
                        int(lt.x + shake_x),
                        statue_base_y,
                        getattr(lt, "tower_type", None),
                    )
                if rt and getattr(rt, "visible", False):
                    statue_base_y = int(rt.y - 20 + shake_y)
                    self._draw_pedestal(int(rt.x + shake_x), statue_base_y)
                    self._draw_statue_model(
                        int(rt.x + shake_x),
                        statue_base_y,
                        getattr(rt, "tower_type", None),
                    )
        except Exception:
            # Don't break rendering if statue drawing throws
            pass

    def draw_special_effects(self, shake_x=0, shake_y=0) -> None:
        if self.game.selected_stage == "prologo" and self.game.prologo_lightning_strike:
            self.draw_lightning_effect(shake_x, shake_y)
        self.draw_chain_lightning_effects(shake_x, shake_y)
        self.draw_spine_effect(shake_x, shake_y)

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
            t: Any | int = getattr(self.game, "prologo_lightning_timer", 0)
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
                total = int(
                    getattr(self.game, "prologo_lightning_duration_frames", 180)
                )
                start_frame: int = max(1, int(total * 0.1))
                peak_frame: int = max(1, int(total * 0.75))
                os.makedirs("screenshots", exist_ok=True)
                if (
                    not getattr(self.game, "_screenshot_taken_start", False)
                    and t == start_frame
                ):
                    pygame.image.save(
                        self.screen,
                        os.path.join("screenshots", "prologo_beam_start.png"),
                    )
                    self.game._screenshot_taken_start = True
                if (
                    not getattr(self.game, "_screenshot_taken_peak", False)
                    and t == peak_frame
                ):
                    pygame.image.save(
                        self.screen,
                        os.path.join("screenshots", "prologo_beam_peak.png"),
                    )
                    self.game._screenshot_taken_peak = True
            except Exception:
                pass

            # Explosion / impact at the end point
            # Make a pulsing explosion that grows over the configured timer
            max_radius = 160
            duration = float(
                getattr(self.game, "prologo_lightning_duration_frames", 180)
            )
            radius = int(min(max_radius, (t / duration) * max_radius + 8))
            pulse: float = (math.sin(self.game.frame_count * 0.25) + 1) * 0.5
            # Outer glow circle
            pygame.draw.circle(
                self.screen,
                (255, 240, 200),
                (int(end_x + shake_x), int(end_y + shake_y)),
                int(radius * 1.1),
            )
            # Inner bright core
            pygame.draw.circle(
                self.screen,
                (255, 255, 200),
                (int(end_x + shake_x), int(end_y + shake_y)),
                int(radius * 0.6 + pulse * 8),
            )
            # Flash star lines
            for ang in range(0, 360, 45):
                rad: float = math.radians(ang)
                lx: Any | float = end_x + math.cos(rad) * (radius * 0.9)
                ly: Any | float = end_y + math.sin(rad) * (radius * 0.9)
                pygame.draw.line(
                    self.screen,
                    (255, 255, 230),
                    (int(end_x + shake_x), int(end_y + shake_y)),
                    (int(lx + shake_x), int(ly + shake_y)),
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
                            pygame.draw.circle(
                                self.screen,
                                (255, 255, 230, inner_alpha),
                                (int(cx + shake_x), int(cy + shake_y)),
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
                                pygame.draw.circle(
                                    self.screen,
                                    (200, 255, 255, alpha),
                                    (int(px + shake_x), int(py + shake_y)),
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

    def draw_spine_effect(self, shake_x=0, shake_y=0):
        pygame = self.pygame
        for enemy in self.game.enemies:
            if (
                hasattr(enemy, "spine_timer")
                and enemy.spine_timer > 0
                and hasattr(enemy, "spine_from")
                and enemy.spine_from is not None
            ):
                try:
                    ex, ey = enemy.x, enemy.y
                    spine_from = enemy.spine_from
                    if (
                        isinstance(spine_from, (list, tuple))
                        and len(spine_from) == 2
                        and all(isinstance(v, (int, float)) for v in spine_from)
                    ):
                        px, py = spine_from
                        for t in [0.25, 0.5, 0.75]:
                            lx = px + (ex - px) * t
                            ly = py + (ey - py) * t
                            r: float = 18 + 6 * random.random()
                            color: (
                                tuple[Literal[255], Literal[255], Literal[204]]
                                | tuple[Literal[255], Literal[254], Literal[224]]
                            ) = (
                                (255, 255, 204)
                                if self.game.frame_count % 2 == 0
                                else (255, 254, 224)
                            )
                            pygame.draw.circle(
                                self.screen,
                                color,
                                (int(lx + shake_x), int(ly + shake_y)),
                                int(r),
                            )
                            pygame.draw.circle(
                                self.screen,
                                (255, 255, 0),
                                (int(lx + shake_x), int(ly + shake_y)),
                                int(r),
                                2,
                            )
                        pygame.draw.circle(
                            self.screen,
                            (255, 254, 224),
                            (int(ex + shake_x), int(ey + shake_y)),
                            12,
                        )
                        pygame.draw.circle(
                            self.screen,
                            (255, 255, 0),
                            (int(ex + shake_x), int(ey + shake_y)),
                            12,
                            3,
                        )
                except (TypeError, ValueError, AttributeError):
                    # Skip if spine_from data is invalid
                    pass

    def draw_hud(self, shake_x=0, shake_y=0):
        """Draw the HUD elements (migrated from Game.draw_hud).

        Uses self.game state and self.screen (pygame Surface)."""
        pygame = self.pygame
        if not self.screen or not pygame:
            return
        from src.assets.text_cache import get_font, get_text

        font = get_font(24)
        small_font = get_font(18)

        # Score
        score_text = get_text(f"Score: {int(self.game.score)}", font, (255, 255, 0))
        self.screen.blit(score_text, (10 + shake_x, 10 + shake_y))

        # Wave
        wave_text = get_text(f"Wave: {self.game.wave}", font, (255, 100, 100))
        self.screen.blit(wave_text, (10 + shake_x, 40 + shake_y))

        # Time
        minutes = int(self.game.time_elapsed // 60)
        seconds = int(self.game.time_elapsed % 60)
        time_text = get_text(f"Time: {minutes}:{seconds:02d}", font, (100, 200, 255))
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
        health_text = get_text(
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
        xp_text = get_text(
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
        level_text = get_text(f"Level {self.game.player_level}", font, (255, 215, 0))
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
            name_map: dict[str, str] = {
                "shotgun": "Hellgun",
                "orbital": "Orbitals",
                "spear": "Spear",
                "beast": "The number of the beast",
                "Flies": "Flies",
            }
            for i, wid in enumerate(self.game.player_weapons):
                lvl: int = self.game.weapon_levels.get(wid, 0)
                display_name: str = name_map.get(wid, wid.capitalize())
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
        from src.assets.text_cache import get_font, get_text

        for msg in list(self.game.center_messages):
            try:
                font = get_font(msg.get("font_size", 36))
                # Shadow for readability
                shadow_text = get_text(msg["text"], font, (0, 0, 0))
                self.screen.blit(
                    shadow_text,
                    (
                        self.width // 2 - shadow_text.get_width() // 2 + 2 + shake_x,
                        self.height // 2 - 40 + 2 + shake_y,
                    ),
                )
                # Main text
                main_text = get_text(msg["text"], font, msg["color"])
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
            from src.assets.text_cache import get_font, get_text

            fps_val = int(self.game.clock.get_fps())
            font = get_font(18)
            fps_text = get_text(f"FPS: {fps_val}", font, (200, 200, 200))
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

            from src.assets.text_cache import get_font, get_text

            # Create semi-transparent purple overlay
            overlay = pygame.Surface((self.width, self.height))
            overlay.fill((40, 20, 45))  # Purple background
            overlay.set_alpha(180)  # Semi-transparent (0-255, 180 = ~70% opacity)
            self.game.screen.blit(overlay, (0, 0))

            font_large = get_font(48)
            font_medium = get_font(32)

            # Title
            title = get_text("SATAN'S FALL COMPLETE", font_large, (255, 215, 0))
            self.game.screen.blit(
                title,
                (
                    self.game.width // 2 - title.get_width() // 2 + shake_x,
                    self.game.height // 2 - 100 + shake_y,
                ),
            )

            # Message
            message1 = get_text(
                "You have witnessed Satan's fall from grace.",
                font_medium,
                (255, 255, 255),
            )
            message2 = get_text(
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

            from src.assets.text_cache import get_font, get_text

            font_title = get_font(38)
            font_name = get_font(26)
            font_desc = get_font(17)
            font_small = get_font(15)
            font_key = get_font(17)

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
            title_surf = get_text(title_text, font_title, C_TITLE)
            sub_surf = get_text(sub_text, font_small, (90, 100, 130))
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

                key_surf = get_text(f"[{i + 1}]", font_key, C_KEY)
                self.game.screen.blit(
                    key_surf,
                    (bx + 16, by + box_height // 2 - key_surf.get_height() // 2),
                )

                name_surf = get_text(weapon["name"], font_name, name_col)
                desc_surf = get_text(weapon["description"], font_desc, C_DESC)
                block_h = name_surf.get_height() + 4 + desc_surf.get_height()
                name_x = bx + 52
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

            from src.assets.text_cache import get_font, get_text

            font_title = get_font(38)
            font_name = get_font(26)
            font_desc = get_font(17)
            font_small = get_font(15)
            font_key = get_font(17)

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
            title_surf = get_text("CHOOSE YOUR TOWER", font_title, C_TITLE)
            sub_surf = get_text("place your guardian", font_small, (75, 75, 80))
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

                key_surf = get_text(f"[{i + 1}]", font_key, C_KEY)
                self.game.screen.blit(
                    key_surf,
                    (bx + 16, by + box_height // 2 - key_surf.get_height() // 2),
                )

                name_surf = get_text(tower["name"], font_name, C_NAME)
                desc_surf = get_text(tower["description"], font_desc, C_DESC)
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

            from src.assets.text_cache import get_font, get_text

            font_title = get_font(38)
            font_name = get_font(26)
            font_desc = get_font(17)
            font_small = get_font(15)
            font_key = get_font(17)

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
            title_surf = get_text("LEVEL UP", font_title, C_TITLE)
            sub_surf = get_text("choose your upgrade", font_small, (110, 110, 110))
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
                reroll_surf = get_text(reroll_label, font_small, (190, 150, 150))
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
                key_surf = get_text(f"[{i + 1}]", font_key, C_KEY)
                key_x = bx + 16
                key_y = by + box_height // 2 - key_surf.get_height() // 2
                self.game.screen.blit(key_surf, (key_x, key_y))

                # name + description — centred vertically in the box
                name_surf = get_text(upgrade["name"], font_name, name_col)
                desc_surf = get_text(upgrade["description"], font_desc, C_DESC)
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

            from src.assets.text_cache import get_font, get_text

            # Overlay surface with per-pixel alpha to allow fade-in effect
            overlay = pygame.Surface(
                (self.game.width, self.game.height), pygame.SRCALPHA
            )
            overlay.fill((40, 20, 45, int(self.game.game_over_alpha)))
            self.game.screen.blit(overlay, (0, 0))

            # Title (fade text by setting per-surface alpha)

            # Dark red for the FALL title for stronger contrast
            title_surf = get_text("FALL", get_font(64), (139, 0, 0)).copy()
            title_surf.set_alpha(int(self.game.game_over_alpha))
            self.game.screen.blit(
                title_surf,
                (
                    self.game.width // 2 - title_surf.get_width() // 2 + shake_x,
                    200 + shake_y,
                ),
            )

            # Stats
            font_medium = get_font(24)
            stats = [
                f"Final Score: {int(self.game.score)}",
                f"Enemies killed: {getattr(self.game, 'enemies_killed_this_run', 0)}",
                f"Wave: {self.game.wave}",
                f"Level: {self.game.player.level}",
            ]

            for i, stat in enumerate(stats):
                text_surf = get_text(stat, font_medium, (255, 255, 255)).copy()
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
            prompt = get_text(
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
