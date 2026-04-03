"""UI Game Renderer: World, objects, HUD, stage-specific rendering."""

import logging
import math
import random
from typing import TYPE_CHECKING

from src.assets.manager import get_image
from src.game_constants import (
    HELL_LAMP_SIZE,
    HELL_STAGES,
    LIMBO_LAMP_SIZE,
    PURGATORY_CAULDRON_SIZE,
    PURGATORY_STAGES,
    STATUE_ASSET_VERTICAL_OFFSET,
    STATUE_BASE_Y,
    WALL_BRICK_HELL,
    WALL_BRICK_LIMBO,
    WALL_BRICK_PROLOGO,
    WALL_BRICK_PURGATORY,
    WALL_THICKNESS,
)
from src.weapons import WEAPON_DEFS

if TYPE_CHECKING:
    from src.game.core import Game

logger: logging.Logger = logging.getLogger(__name__)


class UIGameRenderer:
    """Handles all game world rendering: floor, walls, buildings, objects, HUD."""

    # Lamp glow configuration by stage type
    _LAMP_GLOW_CONFIG = {
        "limbo": {"min_pulse": 0.55, "alpha": 100, "glow_offset": -3},
        "limbo_final": {"min_pulse": 0.45, "alpha": 100, "glow_offset": -3},
        "hell": {"min_pulse": 0.55, "alpha": 120, "glow_offset": -12},
        "prologo": {"min_pulse": 0.55, "alpha": 90, "glow_offset": -5},
    }

    def __init__(self, ui_manager):
        """
        Args:
            ui_manager: Reference to PygameUIManager (parent).
        """
        self.ui = ui_manager
        self.game: Game = ui_manager.game
        self._wall_brick_cache: dict = {}  # cache key → (surface, min_x, min_y)
        self._glow_ring_cache: dict = {}  # cache key → {ring: surface}

    def _calculate_pulse_value(
        self,
        current_time: float,
        pulse_speed: float,
        pulse_phase: float,
        min_value: float = 0.55,
    ) -> float:
        """Calculate pulsation intensity using sine wave.

        Args:
            current_time: Current elapsed time in seconds.
            pulse_speed: Pulsation frequency in Hz.
            pulse_phase: Phase offset in radians.
            min_value: Minimum pulse value (0.55 for normal, 0.45 for limbo_final).

        Returns:
            Pulse value between min_value and 1.0.
        """
        range_val = 1.0 - min_value
        return min_value + range_val * (
            0.5 + 0.5 * math.sin(2 * math.pi * pulse_speed * current_time + pulse_phase)
        )

    def _get_cached_glow_ring(self, pygame, ring: int, glow_color: tuple):
        """Get or create cached glow ring surface.

        Args:
            pygame: Pygame module reference.
            ring: Ring radius in pixels.
            glow_color: RGB color tuple (base color, alpha applied at draw time).

        Returns:
            Cached pygame.Surface with pre-drawn circle.
        """
        cache_key = (ring, glow_color)
        if cache_key not in self._glow_ring_cache:
            # Create surface once and cache it
            glow_surface = pygame.Surface((ring * 2, ring * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surface, (*glow_color, 255), (ring, ring), ring)
            self._glow_ring_cache[cache_key] = glow_surface
        return self._glow_ring_cache[cache_key]

    def _draw_glow_effect(
        self,
        pygame,
        glow_x: float,
        glow_y: float,
        glow_radius: int,
        glow_color: tuple,
        pulse_value: float,
        alpha_intensity: int = 100,
    ) -> None:
        """Draw pulsating glow with gradient effect using cached surfaces.

        Args:
            pygame: Pygame module reference.
            glow_x: Center X position of glow.
            glow_y: Center Y position of glow.
            glow_radius: Radius of glow in pixels.
            glow_color: RGB color tuple.
            pulse_value: Pulsation intensity (0-1).
            alpha_intensity: Base alpha intensity (100-120).
        """
        for ring in range(glow_radius, 0, -3):
            alpha = int(alpha_intensity * (1 - ring / glow_radius) * pulse_value)
            alpha = max(0, min(255, alpha))
            # Get cached surface (created only once)
            glow_surface = self._get_cached_glow_ring(pygame, ring, glow_color)
            # Apply alpha by setting it on the cached surface
            glow_surface.set_alpha(alpha)
            self.ui.screen.blit(glow_surface, (int(glow_x - ring), int(glow_y - ring)))

    # ========== GAME RENDERING METHODS ==========

    def _draw_floor_polygon(self, shake_x=0, shake_y=0) -> None:
        pygame = self.ui.pygame
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
                self.ui.screen,
                prologo_floor,
                self.ui._apply_shake_to_points(inside_points, shake_x, shake_y),
            )
        elif (
            self.game.is_limbo_stage()
            and self.game.left_wall_points
            and self.game.right_wall_points
            and not getattr(self.game, "background_image_drawn", False)
        ):
            # LIMBO: skip procedural floor polygon, use only the asset background
            pass
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
                self.ui.screen,
                inside_color,
                [(p[0], p[1]) for p in inside_points],
            )

    def _draw_walls(self, shake_x=0, shake_y=0) -> None:
        pygame = self.ui.pygame
        settings = self.game.stage_settings[self.game.selected_stage]
        wall_color = settings["wall_color"]

        is_hell_stage = self.game.is_hell_stage()
        is_prologo = str(self.game.selected_stage) == "prologo"
        is_limbo_stage = self.game.is_limbo_stage()
        render_wall_thickness = (
            WALL_THICKNESS * 2
            if is_hell_stage
            else WALL_THICKNESS if is_prologo else WALL_THICKNESS
        )
        cap_extension = max(6, render_wall_thickness // 4) if is_hell_stage else 0

        if is_prologo or is_limbo_stage:
            section_size = 5
            num_points = len(self.game.left_wall_points)
            num_sections = (num_points + section_size - 1) // section_size
            rng = random.Random(42)
            thickness_variations = [rng.randint(-2, 2) for _ in range(num_sections)]

        if self.game.left_wall_points:
            if is_prologo or is_limbo_stage:
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
                self.ui.screen,
                wall_color,
                [(p[0], p[1]) for p in left_wall_all],
            )
            self._draw_wall_bricks(
                self.game.left_wall_points, left_wall_exterior, shake_x, shake_y
            )

            self._draw_wall_edges(
                pygame, self.game.left_wall_points, left_wall_exterior, is_hell_stage
            )

        if self.game.right_wall_points:
            if is_prologo or is_limbo_stage:
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
                self.ui.screen,
                wall_color,
                [(p[0], p[1]) for p in right_wall_all],
            )
            self._draw_wall_bricks(
                self.game.right_wall_points, right_wall_exterior, shake_x, shake_y
            )

            self._draw_wall_edges(
                pygame, self.game.right_wall_points, right_wall_exterior, is_hell_stage
            )

    def _draw_wall_edges(
        self, pygame, wall_points, wall_exterior, is_hell: bool
    ) -> None:
        """Draw edge outlines on a single wall (left or right)."""
        try:
            inner_edge = [(int(p[0]), int(p[1])) for p in wall_points]
            outer_edge = [(int(p[0]), int(p[1])) for p in wall_exterior]
            if is_hell:
                color, width = (0, 0, 0), 4
            else:
                color, width = (30, 30, 30), 3
            pygame.draw.lines(self.ui.screen, color, False, inner_edge, width=width)
            pygame.draw.lines(self.ui.screen, color, False, outer_edge, width=width)
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def _draw_wall_bricks(self, inner_pts, outer_pts, shake_x=0, shake_y=0) -> None:
        """Draw a brick/stone pattern over the wall polygon using a cached mask surface."""
        if not inner_pts or not outer_pts:
            return

        stage = getattr(self.game, "selected_stage", "")

        # Cache key: first+last wall point coords + length + stage
        # Points never change mid-run; a new run regenerates points with different values
        cache_key = (
            inner_pts[0],
            inner_pts[-1],
            len(inner_pts),
            outer_pts[0],
            outer_pts[-1],
            len(outer_pts),
            stage,
        )
        cached = self._wall_brick_cache.get(cache_key)

        if cached is None:
            if stage == "prologo":
                cfg = WALL_BRICK_PROLOGO
            elif stage.startswith("limbo"):
                cfg = WALL_BRICK_LIMBO
            elif stage.startswith("purgatory"):
                cfg = WALL_BRICK_PURGATORY
            elif stage.startswith("hell"):
                cfg = WALL_BRICK_HELL
            else:
                cfg = WALL_BRICK_PROLOGO

            bw, bh = cfg["w"], cfg["h"]
            mortar = cfg["mortar"]
            base = cfg["base"]
            stagger = stage.startswith("limbo") or stage.startswith("purgatory")

            pygame = self.ui.pygame

            # Build polygon without shake (cache is shake-independent)
            poly = [(int(p[0]), int(p[1])) for p in inner_pts] + [
                (int(p[0]), int(p[1])) for p in reversed(outer_pts)
            ]

            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            w = max(1, max_x - min_x)
            h = max(1, max_y - min_y)

            brick_surf = pygame.Surface((w, h), pygame.SRCALPHA)
            rng = random.Random(42)

            row_idx = 0
            ly = 0
            while ly < h:
                row_h = bh + rng.randint(-1, 1)
                row_h = max(3, row_h)
                x_offset = rng.randint(0, bw) if (row_idx % 2 == 0) else 0
                row_y_offsets = []
                row_widths = []
                lx = -bw + x_offset
                while lx < w + bw:
                    brick_w = bw + rng.randint(-2, 2)
                    brick_w = max(4, brick_w)
                    y_off = rng.randint(-1, 1) if stagger else 0
                    row_y_offsets.append(y_off)
                    row_widths.append(brick_w)
                    lx += brick_w + 1
                lx = -bw + x_offset
                for brick_w, y_off in zip(row_widths, row_y_offsets):
                    v = rng.randint(-15, 15)
                    r = max(0, min(255, base[0] + v))
                    g = max(0, min(255, base[1] + v))
                    b = max(0, min(255, base[2] + v))
                    actual_h = max(2, row_h - abs(y_off))
                    pygame.draw.rect(
                        brick_surf,
                        (r, g, b, 255),
                        (lx, ly + max(y_off, 0), brick_w, actual_h),
                    )
                    pygame.draw.rect(
                        brick_surf,
                        (mortar[0], mortar[1], mortar[2], 255),
                        (lx, ly + max(y_off, 0), brick_w, actual_h),
                        1,
                    )
                    lx += brick_w + 1
                ly += row_h + 1
                row_idx += 1

            mask_surf = pygame.Surface((w, h), pygame.SRCALPHA)
            local_poly = [(px - min_x, py - min_y) for px, py in poly]
            pygame.draw.polygon(mask_surf, (255, 255, 255, 255), local_poly)
            brick_surf.blit(mask_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)

            cached = (brick_surf, min_x, min_y)
            self._wall_brick_cache[cache_key] = cached

        surf, min_x, min_y = cached
        self.ui.screen.blit(surf, (min_x + shake_x, min_y + shake_y))

    def _draw_limbo_lamps(self, shake_x=0, shake_y=0) -> None:
        """Draw decorative lamps along limbo walls with pulsating glow effect."""
        if not self.game.is_limbo_stage():
            return

        pygame = self.ui.pygame
        if not hasattr(self.game, "limbo_lamps"):
            logger.warning("Game has no limbo_lamps attribute")
            return

        if not self.game.limbo_lamps:
            logger.debug("No lamps to draw")
            return

        logger.debug("Drawing %d limbo lamps", len(self.game.limbo_lamps))
        # Use lamp2.png for limbo_final, lamp1.png for other limbo stages
        is_final = str(self.game.selected_stage) == "limbo_final"
        lamp_asset = "lamp2.png" if is_final else "lamp1.png"
        # Limbo_final lamps are 5px larger
        lamp_size = (32, 84) if is_final else LIMBO_LAMP_SIZE
        lamp_sprite = get_image(lamp_asset, lamp_size)
        if lamp_sprite is None:
            logger.warning(
                "%s not loaded, using circle fallback (stage: %s)",
                lamp_asset,
                self.game.selected_stage,
            )
            # Fallback: draw simple circles if asset not available
            for lamp in self.game.limbo_lamps:
                x = int(lamp["x"]) + shake_x
                y = int(lamp["y"]) + shake_y
                pygame.draw.circle(self.ui.screen, (255, 220, 100), (x, y), 12)
            return

        logger.debug("Drawing lamps with sprite")

        # Pre-compute right lamp indices for limbo_final offset calculations
        right_lamp_indices = (
            [
                idx
                for idx, lamp in enumerate(self.game.limbo_lamps)
                if lamp.get("side") == "right"
            ]
            if is_final
            else []
        )
        last_right_idx = right_lamp_indices[-1] if right_lamp_indices else -1

        # Current time for pulsation
        current_time = self.game.frame_count / self.game.fps

        # Get glow configuration for this stage
        stage_key = "limbo_final" if is_final else "limbo"
        glow_config = self._LAMP_GLOW_CONFIG[stage_key]
        glow_color = (
            (150, 50, 130) if is_final else (255, 100, 60)
        )  # Purple or red-orange

        for i, lamp in enumerate(self.game.limbo_lamps):
            x = int(lamp["x"]) + shake_x
            y = int(lamp["y"]) + shake_y

            # Apply limbo_final positioning adjustments
            if is_final:
                if lamp.get("side") == "left":
                    x += 3  # Move left-side lamps 3px inward
                elif lamp.get("side") == "right":
                    x -= 6  # 3px inward + 3px left
                    if i != last_right_idx:  # Not the bottommost right lamp
                        x -= 2  # Extra 2px left for upper right lamps

            # Calculate pulsation with stage-specific min value
            pulse_value = self._calculate_pulse_value(
                current_time,
                lamp.get("pulse_speed", 0.5),
                lamp.get("pulse_phase", 0),
                min_value=glow_config["min_pulse"],
            )

            # Draw pulsating glow (before lamp sprite)
            glow_radius = int(lamp.get("glow_radius", 35) * pulse_value)
            glow_x = x + lamp_size[0] // 2
            glow_y = y + lamp_size[1] // 3 + glow_config["glow_offset"]

            self._draw_glow_effect(
                pygame,
                glow_x,
                glow_y,
                glow_radius,
                glow_color,
                pulse_value,
                glow_config["alpha"],
            )

            # Draw lamp sprite
            sprite = lamp_sprite
            if lamp.get("flip", False):
                sprite = pygame.transform.flip(lamp_sprite, True, False)
            self.ui.screen.blit(sprite, (x, y))

    def _draw_purgatory_cauldrons(self, shake_x=0, shake_y=0) -> None:
        """Draw decorative cauldrons at bottom of purgatory arena."""
        if not self.game.is_purgatory_stage():
            return

        pygame = self.ui.pygame
        if not hasattr(self.game, "purgatory_cauldrons"):
            logger.warning("Game has no purgatory_cauldrons attribute")
            return

        if not self.game.purgatory_cauldrons:
            logger.debug("No purgatory cauldrons to draw")
            return

        logger.debug(
            "Drawing %d purgatory cauldrons", len(self.game.purgatory_cauldrons)
        )
        cauldron_sprite = get_image("purgatory_cauldron.png", PURGATORY_CAULDRON_SIZE)
        if cauldron_sprite is None:
            logger.debug("purgatory_cauldron.png not loaded, using circle fallback")
            # Fallback: draw simple circles if asset not available
            for cauldron in self.game.purgatory_cauldrons:
                x = int(cauldron["x"]) + PURGATORY_CAULDRON_SIZE[0] // 2 + shake_x
                y = int(cauldron["y"]) + PURGATORY_CAULDRON_SIZE[1] // 2 + shake_y
                pygame.draw.circle(self.ui.screen, (100, 40, 40), (x, y), 30)
            return

        logger.debug("Drawing cauldrons with sprite")
        for cauldron in self.game.purgatory_cauldrons:
            x = int(cauldron["x"]) + shake_x
            y = int(cauldron["y"]) + shake_y
            self.ui.screen.blit(cauldron_sprite, (x, y))

    def _draw_hell_lamps(self, shake_x=0, shake_y=0) -> None:
        """Draw decorative lamps at bottom corners of hell arena with pulsating glow."""
        if not self.game.is_hell_stage():
            return

        pygame = self.ui.pygame
        if not hasattr(self.game, "hell_lamps"):
            logger.warning("Game has no hell_lamps attribute")
            return

        if not self.game.hell_lamps:
            logger.debug("No hell lamps to draw")
            return

        logger.debug("Drawing %d hell lamps", len(self.game.hell_lamps))
        lamp_sprite = get_image("hell_lamp.png", HELL_LAMP_SIZE)
        if lamp_sprite is None:
            logger.debug("hell_lamp.png not loaded, using rectangle fallback")
            # Fallback: draw vertical rectangles if asset not available
            for lamp in self.game.hell_lamps:
                x = int(lamp["x"]) + shake_x
                y = int(lamp["y"]) + shake_y
                pygame.draw.rect(
                    self.ui.screen,
                    (200, 100, 0),
                    (x, y, HELL_LAMP_SIZE[0], HELL_LAMP_SIZE[1]),
                )
            return

        logger.debug("Drawing hell lamps with sprite")
        # Current time for pulsation
        current_time = self.game.frame_count / self.game.fps

        # Get glow configuration for hell stages
        glow_config = self._LAMP_GLOW_CONFIG["hell"]
        glow_color = (255, 100, 60)  # Red-orange

        for lamp in self.game.hell_lamps:
            x = int(lamp["x"]) + shake_x
            y = int(lamp["y"]) + shake_y

            # Calculate pulsation with stage-specific config
            pulse_value = self._calculate_pulse_value(
                current_time,
                lamp.get("pulse_speed", 0.5),
                lamp.get("pulse_phase", 0),
                min_value=glow_config["min_pulse"],
            )

            # Draw pulsating glow (before lamp sprite)
            glow_radius = int(lamp.get("glow_radius", 25) * pulse_value)
            glow_x = x + HELL_LAMP_SIZE[0] // 2
            glow_y = y + HELL_LAMP_SIZE[1] // 3 + glow_config["glow_offset"]

            self._draw_glow_effect(
                pygame,
                glow_x,
                glow_y,
                glow_radius,
                glow_color,
                pulse_value,
                glow_config["alpha"],
            )

            # Draw lamp sprite
            self.ui.screen.blit(lamp_sprite, (x, y))

    def _draw_torches(self, shake_x=0, shake_y=0) -> None:
        pygame = self.ui.pygame
        is_prologo = getattr(self.game, "selected_stage", "") == "prologo"
        if not is_prologo:
            return

        # Use generated torch data with pulsation if available
        prologo_torches = getattr(self.game, "prologo_torches", [])
        glow_config = self._LAMP_GLOW_CONFIG.get(
            "prologo", {"min_pulse": 0.55, "alpha": 90, "glow_offset": -5}
        )
        current_time = self.game.frame_count / self.game.fps if self.game else 0

        torch_image = get_image("torch.png", (40, 80))

        # Draw torches from generated list with pulsation
        if prologo_torches:
            for torch in prologo_torches:
                torch_x = torch["x"] + shake_x
                torch_y = torch["y"] + shake_y

                # Calculate pulsation
                pulse_value = self._calculate_pulse_value(
                    current_time,
                    torch.get("pulse_speed", 0.4),
                    torch.get("pulse_phase", 0),
                    glow_config["min_pulse"],
                )

                # Get torch color and glow radius
                glow_radius = torch.get("glow_radius", 18)
                glow_color = torch.get("glow_color", (255, 100, 60))

                # Draw glow effect
                glow_x = torch_x + 20  # Center of torch (40px wide)
                glow_y = (
                    torch_y + 40 + glow_config["glow_offset"]
                )  # Center-ish of flame

                self._draw_glow_effect(
                    pygame,
                    glow_x,
                    glow_y,
                    glow_radius,
                    glow_color,
                    pulse_value,
                    glow_config["alpha"],
                )

                # Draw torch sprite or fallback
                if torch_image:
                    self.ui.screen.blit(torch_image, (torch_x, torch_y))
                else:
                    # Draw torch fallback (stick + flame)
                    pygame.draw.rect(
                        self.ui.screen,
                        (50, 25, 0),
                        (torch_x + 12, torch_y + 20, 16, 40),
                    )
                    pygame.draw.circle(
                        self.ui.screen,
                        glow_color,
                        (int(torch_x + 20), int(torch_y + 20)),
                        int(16 * pulse_value),
                    )
                    pygame.draw.circle(
                        self.ui.screen,
                        (255, 200, 0),
                        (int(torch_x + 20), int(torch_y + 20)),
                        int(8 * pulse_value),
                    )
        else:
            # Fallback: draw basic torches at fixed positions (legacy behavior)
            torch_positions = [0.2, 0.5, 0.8]
            for frac in torch_positions:
                y = int(frac * self.ui.height)
                left_point = min(
                    self.game.left_wall_points, key=lambda p: abs(p[1] - y)
                )
                right_point = min(
                    self.game.right_wall_points, key=lambda p: abs(p[1] - y)
                )

                if torch_image:
                    torch_x = left_point[0] - 20
                    torch_y = left_point[1] - 80
                    self.ui.screen.blit(torch_image, (torch_x, torch_y))

                    torch_x = right_point[0] - 20
                    torch_y = right_point[1] - 80
                    self.ui.screen.blit(torch_image, (torch_x, torch_y))
                else:
                    torch_x = left_point[0] - 20
                    torch_y = left_point[1]
                    pygame.draw.rect(
                        self.ui.screen, (50, 25, 0), (torch_x, torch_y - 20, 16, 40)
                    )
                    pygame.draw.circle(
                        self.ui.screen,
                        (255, 100, 0),
                        (int(torch_x + 8), int(torch_y - 20)),
                        16,
                    )
                    pygame.draw.circle(
                        self.ui.screen,
                        (255, 200, 0),
                        (int(torch_x + 8), int(torch_y - 20)),
                        8,
                    )

                    torch_x = right_point[0] - 20
                    torch_y = right_point[1]
                    pygame.draw.rect(
                        self.ui.screen, (50, 25, 0), (torch_x, torch_y - 20, 16, 40)
                    )
                    pygame.draw.circle(
                        self.ui.screen,
                        (255, 100, 0),
                        (int(torch_x + 8), int(torch_y - 20)),
                        16,
                    )
                    pygame.draw.circle(
                        self.ui.screen,
                        (255, 200, 0),
                        (int(torch_x + 8), int(torch_y - 20)),
                        8,
                    )

    def _draw_cathedral_procedural(self, pygame, base_x: int, base_y: int) -> None:
        """Draw cathedral procedural pixel art (Prologo stage)."""
        if not self.ui.screen or not pygame:
            return

        cathedral_y = base_y + 50

        # Cathedral foundation/base (dark stone)
        foundation_color = (60, 45, 35)
        pygame.draw.rect(
            self.ui.screen,
            foundation_color,
            (base_x - 42, cathedral_y + 40, 84, 12),
        )

        # Main cathedral body (rectangular base) - light stone
        stone_color = (140, 120, 100)
        pygame.draw.rect(
            self.ui.screen, stone_color, (base_x - 35, cathedral_y, 70, 50)
        )

        # Central entrance doors (large, ornate)
        door_color = (80, 60, 45)
        pygame.draw.rect(
            self.ui.screen,
            door_color,
            (base_x - 12, cathedral_y + 25, 24, 25),
        )

        # Door frame/details (gold accents)
        gold_color = (180, 150, 50)
        pygame.draw.rect(
            self.ui.screen,
            gold_color,
            (base_x - 14, cathedral_y + 23, 28, 3),  # Top frame
        )
        pygame.draw.rect(
            self.ui.screen,
            gold_color,
            (base_x - 14, cathedral_y + 47, 28, 3),  # Bottom frame
        )
        pygame.draw.rect(
            self.ui.screen,
            gold_color,
            (base_x - 14, cathedral_y + 23, 3, 27),  # Left frame
        )
        pygame.draw.rect(
            self.ui.screen,
            gold_color,
            (base_x + 11, cathedral_y + 23, 3, 27),  # Right frame
        )

        # Rose window above entrance (stained glass)
        rose_window_color = (100, 150, 200)
        pygame.draw.circle(
            self.ui.screen,
            rose_window_color,
            (base_x, cathedral_y + 15),
            8,
        )

        # Side windows (stained glass)
        window_color = (120, 160, 210)
        # Left side windows
        pygame.draw.rect(
            self.ui.screen,
            window_color,
            (base_x - 28, cathedral_y + 12, 8, 12),
        )
        pygame.draw.rect(
            self.ui.screen,
            window_color,
            (base_x - 28, cathedral_y + 28, 8, 12),
        )
        # Right side windows
        pygame.draw.rect(
            self.ui.screen,
            window_color,
            (base_x + 20, cathedral_y + 12, 8, 12),
        )
        pygame.draw.rect(
            self.ui.screen,
            window_color,
            (base_x + 20, cathedral_y + 28, 8, 12),
        )

        # Window frames (stone)
        frame_color = (100, 85, 70)
        # Left frames
        pygame.draw.rect(
            self.ui.screen,
            frame_color,
            (base_x - 29, cathedral_y + 11, 10, 1),
        )
        pygame.draw.rect(
            self.ui.screen,
            frame_color,
            (base_x - 29, cathedral_y + 24, 10, 1),
        )
        pygame.draw.rect(
            self.ui.screen,
            frame_color,
            (base_x - 29, cathedral_y + 11, 1, 14),
        )
        pygame.draw.rect(
            self.ui.screen,
            frame_color,
            (base_x - 20, cathedral_y + 11, 1, 14),
        )
        pygame.draw.rect(
            self.ui.screen,
            frame_color,
            (base_x - 29, cathedral_y + 39, 10, 1),
        )
        pygame.draw.rect(
            self.ui.screen,
            frame_color,
            (base_x - 29, cathedral_y + 27, 1, 14),
        )
        pygame.draw.rect(
            self.ui.screen,
            frame_color,
            (base_x - 20, cathedral_y + 27, 1, 14),
        )
        # Right frames
        pygame.draw.rect(
            self.ui.screen,
            frame_color,
            (base_x + 19, cathedral_y + 11, 10, 1),
        )
        pygame.draw.rect(
            self.ui.screen,
            frame_color,
            (base_x + 19, cathedral_y + 24, 10, 1),
        )
        pygame.draw.rect(
            self.ui.screen,
            frame_color,
            (base_x + 19, cathedral_y + 11, 1, 14),
        )
        pygame.draw.rect(
            self.ui.screen,
            frame_color,
            (base_x + 28, cathedral_y + 11, 1, 14),
        )
        pygame.draw.rect(
            self.ui.screen,
            frame_color,
            (base_x + 19, cathedral_y + 39, 10, 1),
        )
        pygame.draw.rect(
            self.ui.screen,
            frame_color,
            (base_x + 19, cathedral_y + 27, 1, 14),
        )
        pygame.draw.rect(
            self.ui.screen,
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
        pygame.draw.polygon(self.ui.screen, roof_color, roof_points)

        # Roof ridge details
        ridge_color = (90, 75, 60)
        pygame.draw.line(
            self.ui.screen,
            ridge_color,
            (base_x - 35, cathedral_y - 5),
            (base_x + 35, cathedral_y - 5),
            2,
        )

        # Central spire - stone
        pygame.draw.rect(
            self.ui.screen,
            stone_color,
            (base_x - 5, cathedral_y - 55, 10, 25),
        )

        # Spire cross (large gold cross)
        pygame.draw.rect(
            self.ui.screen,
            gold_color,
            (base_x - 3, cathedral_y - 57, 6, 10),  # Vertical
        )
        pygame.draw.rect(
            self.ui.screen,
            gold_color,
            (base_x - 6, cathedral_y - 54, 12, 4),  # Horizontal
        )

        # Side towers (larger than before)
        tower_color = (130, 110, 90)
        # Left tower
        pygame.draw.rect(
            self.ui.screen,
            tower_color,
            (base_x - 50, cathedral_y - 15, 15, 35),
        )
        # Left tower roof
        pygame.draw.polygon(
            self.ui.screen,
            roof_color,
            [
                (base_x - 52, cathedral_y - 15),
                (base_x - 42, cathedral_y - 25),
                (base_x - 35, cathedral_y - 15),
            ],
        )
        # Left tower spire
        pygame.draw.rect(
            self.ui.screen,
            tower_color,
            (base_x - 45, cathedral_y - 35, 5, 10),
        )

        # Right tower
        pygame.draw.rect(
            self.ui.screen,
            tower_color,
            (base_x + 35, cathedral_y - 15, 15, 35),
        )
        # Right tower roof
        pygame.draw.polygon(
            self.ui.screen,
            roof_color,
            [
                (base_x + 35, cathedral_y - 15),
                (base_x + 42, cathedral_y - 25),
                (base_x + 47, cathedral_y - 15),
            ],
        )
        # Right tower spire
        pygame.draw.rect(
            self.ui.screen,
            tower_color,
            (base_x + 40, cathedral_y - 35, 5, 10),
        )

        # Tower windows
        pygame.draw.rect(
            self.ui.screen,
            window_color,
            (base_x - 47, cathedral_y - 5, 4, 6),  # Left tower window
        )
        pygame.draw.rect(
            self.ui.screen,
            window_color,
            (base_x + 39, cathedral_y - 5, 4, 6),  # Right tower window
        )

    def _draw_church_procedural(self, pygame, base_x: int, base_y: int) -> None:
        """Draw church procedural pixel art (Prologo stage)."""
        if not self.ui.screen or not pygame:
            return

        church_y = base_y + 50

        # Main church body (rectangular base) - stone color
        stone_color = (120, 100, 80)  # Brownish stone
        pygame.draw.rect(self.ui.screen, stone_color, (base_x - 20, church_y, 40, 28))

        # Church foundation/base (darker stone)
        foundation_color = (80, 60, 50)
        pygame.draw.rect(
            self.ui.screen,
            foundation_color,
            (base_x - 22, church_y + 25, 44, 8),
        )

        # Central door (darker rectangle)
        door_color = (60, 40, 30)
        pygame.draw.rect(
            self.ui.screen, door_color, (base_x - 6, church_y + 12, 12, 16)
        )

        # Door frame/details
        pygame.draw.rect(
            self.ui.screen,
            (100, 80, 60),
            (base_x - 7, church_y + 11, 14, 2),  # Top frame
        )
        pygame.draw.rect(
            self.ui.screen,
            (100, 80, 60),
            (base_x - 7, church_y + 27, 14, 2),  # Bottom frame
        )

        # Side windows
        window_color = (150, 180, 200)  # Light blue stained glass
        # Left window
        pygame.draw.rect(
            self.ui.screen, window_color, (base_x - 16, church_y + 8, 6, 8)
        )
        # Right window
        pygame.draw.rect(
            self.ui.screen, window_color, (base_x + 10, church_y + 8, 6, 8)
        )

        # Window frames (stone)
        pygame.draw.rect(
            self.ui.screen,
            stone_color,
            (base_x - 17, church_y + 7, 8, 1),  # Left top
        )
        pygame.draw.rect(
            self.ui.screen,
            stone_color,
            (base_x - 17, church_y + 16, 8, 1),  # Left bottom
        )
        pygame.draw.rect(
            self.ui.screen,
            stone_color,
            (base_x + 9, church_y + 7, 8, 1),  # Right top
        )
        pygame.draw.rect(
            self.ui.screen,
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
        pygame.draw.polygon(self.ui.screen, roof_color, roof_points)

        # Roof ridge detail
        ridge_color = (100, 80, 60)
        pygame.draw.line(
            self.ui.screen,
            ridge_color,
            (base_x - 20, church_y - 2),
            (base_x + 20, church_y - 2),
            2,
        )

        # Central spire - stone color
        pygame.draw.rect(
            self.ui.screen, stone_color, (base_x - 2, church_y - 28, 4, 12)
        )

        # Spire cross (gold color)
        cross_color = (200, 180, 50)
        pygame.draw.rect(
            self.ui.screen,
            cross_color,
            (base_x - 1, church_y - 30, 2, 6),  # Vertical
        )
        pygame.draw.rect(
            self.ui.screen,
            cross_color,
            (base_x - 2, church_y - 28, 4, 2),  # Horizontal
        )

        # Small bell tower windows
        pygame.draw.rect(
            self.ui.screen, window_color, (base_x - 1, church_y - 22, 2, 3)
        )

    def _draw_buildings(self, shake_x=0, shake_y=0) -> None:
        pygame = self.ui.pygame
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

                        self.ui.screen.blit(building_image, image_rect)
                        asset_loaded = True
                except (ImportError, AttributeError):
                    pass  # Fall back to procedural drawing

                # Fallback: procedural drawing if asset not found
                if not asset_loaded:
                    if i == 1:  # Center cathedral - larger
                        self.ui._draw_cathedral_procedural(pygame, base_x, base_y)
                    else:  # Side churches
                        self.ui._draw_church_procedural(pygame, base_x, base_y)

    def _draw_battlefield_crosses(self, shake_x: int = 0, shake_y: int = 0) -> None:
        """Draw battlefield crosses at bottom sides of Prologo stage."""
        pygame = self.ui.pygame
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
                self.ui.screen.blit(
                    battlefield_cross,
                    (left_bottom_x + shake_x, cross_y_position + shake_y),
                )
                self.ui.screen.blit(
                    battlefield_cross,
                    (right_bottom_x + shake_x, cross_y_position + shake_y),
                )

    def draw_game_world(self, shake_x=0, shake_y=0) -> None:
        """Draw walls, buildings and background following the original implementation."""
        if (
            not self.ui.screen
            or not self.game.selected_stage
            or self.game.selected_stage not in self.game.stage_settings
        ):
            return

        self.ui._draw_floor_polygon(shake_x, shake_y)
        self.ui._draw_walls(shake_x, shake_y)
        self.ui._draw_limbo_lamps(shake_x, shake_y)
        self._draw_purgatory_cauldrons(shake_x, shake_y)
        self._draw_hell_lamps(shake_x, shake_y)
        self.ui._draw_torches(shake_x, shake_y)
        self.ui._draw_buildings(shake_x, shake_y)
        self.ui._draw_battlefield_crosses(shake_x, shake_y)

        if hasattr(self, "draw_dead_trees"):
            self.draw_dead_trees(shake_x, shake_y)
        if hasattr(self, "draw_pedestals"):
            self.draw_pedestals(shake_x, shake_y)

    def draw_player_stats(self, shake_x=0, shake_y=0) -> None:
        """Draw the player stats panel."""
        pygame = self.ui.pygame
        if not self.ui.screen or not pygame:
            return

        font_title = self.ui.get_font(40)
        font_header = self.ui.get_font(20)
        font_body = self.ui.get_font(18)
        font_weapon = self.ui.get_font(20)  # Slightly larger for weapons
        font_small = self.ui.get_font(15)

        COLOR_TITLE = (220, 180, 40)
        COLOR_HEADER = (180, 80, 40)
        COLOR_LABEL = (150, 150, 150)
        COLOR_VALUE = (230, 230, 230)
        COLOR_DIVIDER = (80, 40, 20)
        COLOR_HINT = (100, 100, 100)
        COLOR_GREEN = (100, 180, 100)
        COLOR_RED = (200, 60, 60)
        COLOR_DARK_RED = (220, 100, 100)

        def _clean(key: str) -> str:
            return key.replace("_", " ").title()

        def _pct(v: float) -> str:
            sign = "+" if v >= 0 else ""
            return f"{sign}{v:.0f}%"

        def _draw_section_header(label: str, x: int, y: int, width: int = 260) -> int:
            surf = self.ui.get_text(label.upper(), font_header, COLOR_HEADER)
            self.ui.screen.blit(surf, (x + shake_x, y + shake_y))
            line_y = y + surf.get_height() + 4
            pygame.draw.line(
                self.ui.screen,
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
            lab = self.ui.get_text(label, font_body, lc)
            val = self.ui.get_text(value, font_body, vc)
            self.ui.screen.blit(lab, (x + shake_x, y + shake_y))
            vx = val_x if val_x else x + 180
            self.ui.screen.blit(val, (vx + shake_x, y + shake_y))

        # ── Overlay ──────────────────────────────────────────────────────────────
        overlay = pygame.Surface((self.ui.width, self.ui.height))
        overlay.set_alpha(220)
        overlay.fill((6, 6, 10))
        self.ui.screen.blit(overlay, (0, 0))

        # ── Title ────────────────────────────────────────────────────────────────
        title = self.ui.get_text("PLAYER STATS", font_title, COLOR_TITLE)
        tx = self.ui.width // 2 - title.get_width() // 2 + shake_x
        ty = 28 + shake_y
        self.ui.screen.blit(title, (tx, ty))
        bar_y = ty + title.get_height() + 5
        pygame.draw.line(
            self.ui.screen,
            COLOR_DIVIDER,
            (self.ui.width // 2 - 240 + shake_x, bar_y),
            (self.ui.width // 2 + 240 + shake_x, bar_y),
            1,
        )

        line_h = 28  # Spacing to prevent icon frame overlap
        left_x = self.ui.width // 2 - 430
        right_x = self.ui.width // 2 + 40
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
            self.ui.screen, (40, 40, 40), (bar_x, bar_y, bar_width, bar_height)
        )
        fill_w = self.ui._calculate_meta_xp_fill(meta_xp, meta_xp_to, bar_width)
        pygame.draw.rect(
            self.ui.screen, (255, 100, 100), (bar_x, bar_y, fill_w, bar_height)
        )

        xp_text = self.ui.get_text(
            f"{meta_xp} / {meta_xp_to} XP", font_small, (255, 215, 0)
        )
        self.ui.screen.blit(
            xp_text, (left_x + shake_x, bar_y + bar_height + 4 + shake_y)
        )

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
        pygame.draw.rect(self.ui.screen, (35, 8, 8), (bx, by, bar_w, bar_h))
        fill = int(bar_w * min(1.0, hp_cur / max(1, hp_max)))
        if fill > 0:
            pygame.draw.rect(self.ui.screen, COLOR_RED, (bx, by, fill, bar_h))
        pygame.draw.rect(self.ui.screen, (80, 30, 30), (bx, by, bar_w, bar_h), 1)
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
                val_surf = self.ui.get_text(str(v), font_body, col)
                lab_surf = self.ui.get_text(label, font_body, COLOR_LABEL)
                # max indicator
                max_surf = (
                    self.ui.get_text("MAX", font_small, (180, 140, 20))
                    if v >= 10
                    else None
                )
                self.ui.screen.blit(lab_surf, (right_x + shake_x, y + shake_y))
                self.ui.screen.blit(val_surf, (right_x + 160 + shake_x, y + shake_y))
                if max_surf:
                    self.ui.screen.blit(
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
                    pygame.draw.rect(self.ui.screen, pip_col, (px, pip_y, pip_w, pip_h))
                    pygame.draw.rect(
                        self.ui.screen,
                        (60, 40, 20) if filled else (50, 50, 50),
                        (px, pip_y, pip_w, pip_h),
                        1,
                    )
                y += lab_surf.get_height() + pip_h + 7 + 4

        y += 14

        # — Weapons —
        y = _draw_section_header("Weapons", right_x, y)
        weapons = list(self.game.player_weapons)
        if weapons:
            yellow = (255, 204, 0)
            icon_size = 32
            icon_padding = 16  # Increased from 8 to prevent overlap
            weapon_line_h = 40  # Increased spacing for weapon items
            for wid in weapons:
                lvl = self.game.weapon_levels.get(wid, 0)
                name = WEAPON_DEFS.get(wid, {}).get("name", _clean(wid))

                # Load weapon icon
                icon_surf = None
                icon_key = WEAPON_DEFS.get(wid, {}).get("icon")
                if not icon_key:
                    icon_key = f"weapon_{wid.lower()}.png"
                try:
                    icon_surf = get_image(icon_key, (icon_size, icon_size))
                    if icon_surf is None and icon_key.startswith("weapon_"):
                        # Try fallback: remove "weapon_" prefix
                        icon_surf = get_image(
                            icon_key[len("weapon_") :], (icon_size, icon_size)
                        )
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

                # Display FINAL FORM - Name for level 7, otherwise Name + number in yellow
                if lvl == 7:
                    display_text = f"FINAL FORM - {name}"
                    text_color = COLOR_DARK_RED
                    text_surf = self.ui.get_text(display_text, font_weapon, text_color)
                else:
                    # Render name in normal color, level number in yellow (larger font)
                    name_surf = self.ui.get_text(f"{name}  ", font_weapon, COLOR_VALUE)
                    # Use larger font for level number
                    font_lvl = self.ui.pygame.font.Font(
                        None, int(font_weapon.get_height() * 1.3)
                    )
                    lvl_surf = self.ui.get_text(f"{lvl}", font_lvl, yellow)
                    # Align number vertically to center
                    combined_height = max(name_surf.get_height(), lvl_surf.get_height())
                    combined_width = name_surf.get_width() + lvl_surf.get_width()
                    combined_surf = self.ui.pygame.Surface(
                        (combined_width, combined_height), self.ui.pygame.SRCALPHA
                    )
                    combined_surf.blit(name_surf, (0, 0))
                    lvl_y = (combined_height - lvl_surf.get_height()) // 2
                    combined_surf.blit(lvl_surf, (name_surf.get_width(), lvl_y))
                    text_surf = combined_surf

                # Draw icon if available
                text_x = right_x
                text_y = y
                if icon_surf is not None:
                    icon_y = y + (line_h - icon_size) // 2
                    frame_size = icon_size + 4  # Add 2px border on each side
                    frame_x = text_x - 2
                    frame_y = icon_y - 2
                    # Draw frame border
                    pygame.draw.rect(
                        self.ui.screen,
                        (100, 100, 100),
                        (frame_x + shake_x, frame_y + shake_y, frame_size, frame_size),
                        1,
                    )
                    # Draw icon inside frame
                    self.ui.screen.blit(icon_surf, (text_x + shake_x, icon_y + shake_y))
                    text_x += icon_size + icon_padding
                    # Center text vertically with frame
                    frame_center_y = frame_y + frame_size // 2
                    text_height = text_surf.get_height()
                    text_y = frame_center_y - text_height // 2

                self.ui.screen.blit(text_surf, (text_x + shake_x, text_y + shake_y))
                y += weapon_line_h
        else:
            self.ui.screen.blit(
                self.ui.get_text("None", font_body, COLOR_HINT),
                (right_x + shake_x, y + shake_y),
            )
            y += line_h

        # ── Close hint ───────────────────────────────────────────────────────────
        inst = self.ui.get_text("Tab / ESC  to close", font_small, COLOR_HINT)
        self.ui.screen.blit(
            inst,
            (
                self.ui.width // 2 - inst.get_width() // 2 + shake_x,
                self.ui.height - 34 + shake_y,
            ),
        )

        try:
            self.game._last_drawn_menu = "player_stats"
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def draw_dead_trees(self, shake_x=0, shake_y=0) -> None:
        # Debugging hook: log when drawing dead trees to help visibility issues
        try:
            if not self.game.is_limbo_stage() or not hasattr(self.game, "dead_trees"):
                return

            if not self.game.dead_trees:
                return
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        pygame = self.ui.pygame

        # Hellish palette — charred, bone-dry wood
        TRUNK_FILL = (72, 50, 38)
        TRUNK_EDGE = (32, 18, 12)
        TRUNK_HIGHLIGHT = (108, 78, 58)
        CRACK_COLOR = (42, 25, 16)

        # Base brown palette — charred, bone-dry wood
        BASE_BRANCH_COLOR = (65, 44, 32)
        BASE_BRANCH_SHADOW = (22, 11, 7)
        BASE_SUB_COLOR = (56, 36, 25)
        BASE_TWIG_COLOR = (46, 28, 18)

        def blend_color(base, accent, accent_ratio=0.4):
            """Blend base color with accent color (accent_ratio controls saturation)."""
            return tuple(
                int(base[i] * (1 - accent_ratio) + accent[i] * accent_ratio)
                for i in range(3)
            )

        # Stage-specific psychedelic color schemes (40% accent, 60% brown base)
        stage = str(self.game.selected_stage)
        stage_colors = {
            "limbo_final": {
                "branch": (200, 100, 180),  # Purple
                "branch_shadow": (150, 60, 120),  # Purple shadow
                "sub": (50, 200, 100),  # Bright green
                "twig": (100, 180, 80),  # Lime green
            },
            "limbo": {
                "branch": (180, 160, 50),  # Yellow
                "branch_shadow": (120, 100, 30),  # Yellow shadow
                "sub": (80, 200, 80),  # Bright green
                "twig": (120, 170, 60),  # Lime green
            },
        }

        # Use same color scheme for limbo_2 and limbo_3 as limbo
        if stage in ("limbo_2", "limbo_3"):
            colors = stage_colors["limbo"]
        else:
            colors = stage_colors.get(stage)

        if colors:
            BRANCH_COLOR = blend_color(BASE_BRANCH_COLOR, colors["branch"])
            BRANCH_SHADOW = blend_color(BASE_BRANCH_SHADOW, colors["branch_shadow"])
            SUB_COLOR = blend_color(BASE_SUB_COLOR, colors["sub"])
            TWIG_COLOR = blend_color(BASE_TWIG_COLOR, colors["twig"])
        else:
            BRANCH_COLOR = BASE_BRANCH_COLOR
            BRANCH_SHADOW = BASE_BRANCH_SHADOW
            SUB_COLOR = BASE_SUB_COLOR
            TWIG_COLOR = BASE_TWIG_COLOR

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
                pygame.draw.polygon(self.ui.screen, TRUNK_FILL, lower_poly)
                pygame.draw.polygon(self.ui.screen, TRUNK_EDGE, lower_poly, 1)
                pygame.draw.line(
                    self.ui.screen,
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
                pygame.draw.polygon(self.ui.screen, TRUNK_FILL, left_poly)
                pygame.draw.polygon(self.ui.screen, TRUNK_EDGE, left_poly, 1)

                # Right tine: diverges upper-right from fork point
                rx = x + split["right_dx"]
                ry = fork_y - split["right_dy"]
                right_poly = [
                    (x - 1, fork_y),
                    (x + fork_tw, fork_y),
                    (rx + tine_top, ry),
                    (rx - tine_top, ry),
                ]
                pygame.draw.polygon(self.ui.screen, TRUNK_FILL, right_poly)
                pygame.draw.polygon(self.ui.screen, TRUNK_EDGE, right_poly, 1)
            else:
                # Tapered trunk polygon: wider at base (y+height), narrow at crown (y)
                top_w = max(1, tw // 2)
                trunk_poly = [
                    (x - tw, y + height),
                    (x + tw, y + height),
                    (x + top_w, y),
                    (x - top_w, y),
                ]
                pygame.draw.polygon(self.ui.screen, TRUNK_FILL, trunk_poly)
                pygame.draw.polygon(self.ui.screen, TRUNK_EDGE, trunk_poly, 1)

                # Centre highlight stripe for depth
                pygame.draw.line(
                    self.ui.screen, TRUNK_HIGHLIGHT, (x, y + 3), (x, y + height - 3), 1
                )

            # Trunk cracks / texture marks
            for crack in tree.get("cracks", []):
                cx = x + crack["x_off"]
                cy = y + int(height * crack["y_frac"])
                half = crack["length"] // 2
                pygame.draw.line(
                    self.ui.screen,
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
                    self.ui.screen,
                    BRANCH_SHADOW,
                    (bsx + 1, bsy + 1),
                    (bex + 1, bey + 1),
                    bthick,
                )
                pygame.draw.line(
                    self.ui.screen, BRANCH_COLOR, (bsx, bsy), (bex, bey), bthick
                )

                for sub in branch.get("sub_branches", []):
                    ssx = int(sub["start_x"] + shake_x)
                    ssy = int(sub["start_y"] + shake_y)
                    sex = int(sub["end_x"] + shake_x)
                    sey = int(sub["end_y"] + shake_y)
                    pygame.draw.line(
                        self.ui.screen, SUB_COLOR, (ssx, ssy), (sex, sey), 1
                    )

                    for twig in sub.get("sub_branches", []):
                        pygame.draw.line(
                            self.ui.screen,
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
        pygame = self.ui.pygame

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
        except (AttributeError, TypeError, ValueError, KeyError):
            asset_img = None
        if asset_img:
            w, h = asset_img.get_size()
            # optionally flip horizontally when drawing on the right side of the
            # screen.  this mirrors imported assets for the right-hand statue
            # while leaving the left-hand one untouched.
            if x > (self.ui.width / 2):
                try:
                    asset_img = pygame.transform.flip(asset_img, True, False)
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
            # bottom-center anchor, with optional vertical offset
            y_pos = adjusted_base_y - h
            self.ui.screen.blit(asset_img, (x - w // 2, y_pos))
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
        pygame.draw.polygon(self.ui.screen, body_color, body_points)
        pygame.draw.polygon(self.ui.screen, outline_color, body_points, 2)

        # Head (larger and round)
        head_y: int = adjusted_base_y - 70
        head_radius = 15
        pygame.draw.circle(self.ui.screen, body_color, (x, head_y), head_radius)
        pygame.draw.circle(self.ui.screen, outline_color, (x, head_y), head_radius, 2)

        # Larger horns (from head)
        pygame.draw.line(
            self.ui.screen,
            horn_color,
            (x - 10, head_y - 10),
            (x - 20, head_y - 30),
            4,
        )
        pygame.draw.line(
            self.ui.screen,
            horn_color,
            (x + 10, head_y - 10),
            (x + 20, head_y - 30),
            4,
        )

        # Glowing eyes (on head)
        pygame.draw.circle(self.ui.screen, eye_color, (x - 7, head_y), 3)
        pygame.draw.circle(self.ui.screen, eye_color, (x + 7, head_y), 3)

        # Subtle glow ring around head for visibility
        pygame.draw.circle(self.ui.screen, glow_color, (x, head_y), head_radius + 4, 2)

        # Pitchfork in hand
        fork_x: int = x + 20  # Held to the right side
        fork_top_y: int = statue_base_y - 100
        fork_bottom_y: int = statue_base_y - 20
        pygame.draw.line(
            self.ui.screen,
            (42, 42, 42),
            (fork_x, fork_bottom_y),
            (fork_x, fork_top_y),
            3,
        )

        # Pitchfork prongs (3 prongs)
        prong_length = 15
        # Center prong
        pygame.draw.line(
            self.ui.screen,
            (74, 74, 74),
            (fork_x, fork_top_y),
            (fork_x, fork_top_y - prong_length),
            2,
        )
        # Left prong
        pygame.draw.line(
            self.ui.screen,
            (74, 74, 74),
            (fork_x - 6, fork_top_y),
            (fork_x - 6, fork_top_y - prong_length),
            2,
        )
        # Right prong
        pygame.draw.line(
            self.ui.screen,
            (74, 74, 74),
            (fork_x + 6, fork_top_y),
            (fork_x + 6, fork_top_y - prong_length),
            2,
        )
        # Connecting bar
        pygame.draw.line(
            self.ui.screen,
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
        pygame.draw.polygon(self.ui.screen, (74, 16, 16), left_wing_points)
        pygame.draw.polygon(self.ui.screen, (42, 0, 0), left_wing_points, 1)

        # Right wing (smaller to not interfere with pitchfork)
        right_wing_points: list[tuple[int, int]] = [
            (x + 12, statue_base_y - 40),
            (x + 28, statue_base_y - 45),
            (x + 23, statue_base_y - 30),
        ]
        pygame.draw.polygon(self.ui.screen, (74, 16, 16), right_wing_points)
        pygame.draw.polygon(self.ui.screen, (42, 0, 0), right_wing_points, 1)

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
            return
        # **Limbo Final** should not draw the static statues at all.  The
        # dynamic tower models that appear after the player chooses a tower
        # replace them, and drawing the ice statues early led to visual
        # overlap (the 'ice statue' complaint).  We also prevent firing while
        # the player is selecting a tower (handled in WeaponSystem).
        if getattr(self.game, "selected_stage", None) == "limbo_final":
            return

        # Two statues at the sides of the play area (no pedestals).  X coords
        # are moved inward by 50 pixels vs the original pedestal positions.
        # Y is the universal STATUE_BASE_Y constant shared with all other stages.
        statue_xs: list[int] = [370, 910]

        for sx in statue_xs:
            self.ui._draw_statue_model(
                sx + shake_x,
                STATUE_BASE_Y + shake_y,
                getattr(self.game, "selected_stage", None),
            )

    def _build_fog_cache(self) -> None:
        """Pre-render fog layers into cached surfaces.

        Cache is invalidated when wall points change or when stage is not Limbo.
        """
        if not self.game.is_limbo_stage():
            self.ui._fog_cache = None
            self.ui._fog_cache_signature = None
            return
        if not self.game.left_wall_points or not self.game.right_wall_points:
            self.ui._fog_cache = None
            self.ui._fog_cache_signature = None
            return

        # LIMBO: Skip lateral fog layers to show the background asset clearly
        self.ui._fog_cache = []
        self.ui._fog_cache_signature = None
        return

        # Create a signature from wall points to detect changes
        sig_left = tuple((int(x), int(y)) for (x, y) in self.game.left_wall_points)
        sig_right = tuple((int(x), int(y)) for (x, y) in self.game.right_wall_points)
        sig = (
            sig_left,
            sig_right,
            self.ui.width,
            self.ui.height,
            getattr(self.game, "selected_stage", None),
        )
        if getattr(self, "_fog_cache_signature", None) == sig and getattr(
            self, "_fog_cache", None
        ):
            return  # Cache still valid

        # Build cache
        pygame = self.ui.pygame
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
                fog_surface = pygame.Surface(
                    (self.ui.width, self.ui.height), pygame.SRCALPHA
                )
                pygame.draw.polygon(
                    fog_surface, color + (int(128 * opacity),), left_fog_points
                )
                try:
                    fog_surface = fog_surface.convert_alpha()
                except (AttributeError, TypeError, ValueError, KeyError):
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
                right_fog_points.append((self.ui.width, point[1]))
            if len(right_fog_points) > 2:
                fog_surface = pygame.Surface(
                    (self.ui.width, self.ui.height), pygame.SRCALPHA
                )
                pygame.draw.polygon(
                    fog_surface, color + (int(128 * opacity),), right_fog_points
                )
                try:
                    fog_surface = fog_surface.convert_alpha()
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
                cache.append(fog_surface)
            else:
                cache.append(None)

        self.ui._fog_cache = cache
        self.ui._fog_cache_signature = sig

    def draw_purgatory_fog(self, shake_x=0, shake_y=0) -> None:
        """Draw the semi–transparent gray haze overlay for purgatory stages.

        The earlier implementation also produced drifting fog particles along
        the lateral wall edges, but those were removed at the designer's
        request.  Only the flat overlay remains in use; the particle methods
        themselves still exist but are no longer invoked.
        """
        stage = getattr(self.game, "selected_stage", None)
        if not (stage and str(stage) in PURGATORY_STAGES):
            return
        if not self.ui.screen:
            return
        if not self.game.left_wall_points or not self.game.right_wall_points:
            return

        # update and render dynamic fog particles (new system)
        try:
            self.ui._update_and_draw_fog_particles()
        except (AttributeError, TypeError, ValueError, KeyError):
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
        if not self.ui.screen:
            return
        try:
            pygame = self.ui.pygame
            need_new = False
            ov = getattr(self.ui, cache_attr, None)
            if ov is None:
                need_new = True
            else:
                if ov.get_size() != (self.ui.width, self.ui.height):
                    need_new = True
                if getattr(self.ui, color_attr, None) != color:
                    need_new = True
                if getattr(self.ui, alpha_attr, None) != alpha:
                    need_new = True
            if need_new:
                overlay = pygame.Surface((self.ui.width, self.ui.height))
                try:
                    overlay = overlay.convert()
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
                overlay.fill(color)
                overlay.set_alpha(alpha)
                setattr(self.ui, cache_attr, overlay)
                setattr(self.ui, color_attr, color)
                setattr(self.ui, alpha_attr, alpha)
            self.ui.screen.blit(getattr(self.ui, cache_attr), (0, 0))
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def draw_fog(self, shake_x=0, shake_y=0) -> None:
        stage = getattr(self.game, "selected_stage", None)
        if not stage or not self.ui.screen:
            return

        if str(stage) in PURGATORY_STAGES:
            try:
                self.draw_purgatory_fog(shake_x, shake_y)
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
            return

        if str(stage) in HELL_STAGES:
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

        from src.game_constants import LIMBO_OVERLAY_ALPHA

        # Update and render LIMBO fog particles (vertical rising from sides)
        try:
            self.ui._update_and_draw_limbo_fog_particles()
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        # Choose overlay color and alpha based on limbo variant
        stage = getattr(self.game, "selected_stage", None)
        limbo_overlay_presets = {
            "limbo_2": ((80, 75, 55), LIMBO_OVERLAY_ALPHA),  # Orange tint
            "limbo_3": ((80, 60, 60), LIMBO_OVERLAY_ALPHA),  # Red tint
            "limbo_final": ((80, 45, 65), 100),  # Darker red with increased alpha
        }
        limbo_overlay_color, limbo_overlay_alpha = limbo_overlay_presets.get(
            stage, ((60, 60, 60), LIMBO_OVERLAY_ALPHA)  # Default gray
        )

        self._draw_stage_overlay(
            "_limbo_overlay",
            "_limbo_overlay_color",
            "_limbo_overlay_alpha",
            limbo_overlay_color,
            limbo_overlay_alpha,
        )

        # LIMBO: Skip lateral fog layers to show the background asset clearly
        return

    def draw_game_objects(self, shake_x=0, shake_y=0) -> None:
        if not self.ui.screen:
            return
        pygame = self.ui.pygame
        # Draw hell barriers BEFORE enemies (enemies appear in front)
        # Barriers look like wooden fences
        for b in getattr(self.game, "barriers", []):
            try:
                bx = int(b["x"]) + shake_x
                by = int(b["y"]) + shake_y
                bw, bh = b["w"], b["h"]
                hp, max_hp = b.get("hp", 0), b.get("max_hp", 1)

                # Try to use custom asset first, fallback to vector art
                asset_key = "barrier_damaged.png" if hp < max_hp else "barrier_wood.png"
                barrier_img = (
                    self.game.assets.get(asset_key)
                    if hasattr(self.game, "assets")
                    else None
                )

                if barrier_img is not None:
                    # Scale asset to barrier size and draw
                    try:
                        from src.assets.manager import get_image

                        scaled = get_image(asset_key, (bw, bh))
                        if scaled is not None:
                            self.ui.screen.blit(scaled, (bx, by))
                        else:
                            raise ValueError("Asset could not be scaled")
                    except Exception:
                        # Fallback to vector art if asset loading fails
                        barrier_img = None

                if barrier_img is None:
                    # Wooden fence colors (fallback vector art)
                    wood_dark = (101, 67, 33)  # dark brown
                    wood_light = (139, 90, 43)  # lighter brown
                    wood_highlight = (184, 134, 11)  # golden brown

                    # Main fence body
                    pygame.draw.rect(self.ui.screen, wood_dark, (bx, by, bw, bh))

                    # Vertical planks (3 pieces for variety)
                    plank_width = bw // 3
                    for i in range(3):
                        plank_x = bx + i * plank_width
                        # Alternate colors slightly for wooden texture
                        color = wood_light if i % 2 == 0 else (120, 80, 40)
                        pygame.draw.rect(
                            self.ui.screen, color, (plank_x, by, plank_width, bh)
                        )
                        # Highlight edge on each plank
                        pygame.draw.line(
                            self.ui.screen,
                            wood_highlight,
                            (plank_x + 2, by),
                            (plank_x + 2, by + bh),
                            1,
                        )

                    # Top reinforcement bar
                    pygame.draw.rect(self.ui.screen, (60, 40, 20), (bx, by, bw, 3))

                    # Bottom reinforcement bar
                    pygame.draw.rect(
                        self.ui.screen, (60, 40, 20), (bx, by + bh - 3, bw, 3)
                    )

                    # Outer border for depth
                    pygame.draw.rect(self.ui.screen, (40, 25, 10), (bx, by, bw, bh), 2)

                # HP bar BELOW the barrier — only when damaged (semi-transparent)
                hp, max_hp = b.get("hp", 0), b.get("max_hp", 1)
                if hp < max_hp:
                    frac = max(0.0, hp / max_hp)
                    bg_color = (40, 10, 10, 120)
                    fill_col = (200, 50, 50, 120) if frac > 0.3 else (255, 80, 0, 120)
                    bg_surf = pygame.Surface((bw, 5), pygame.SRCALPHA)
                    bg_surf.fill(bg_color)
                    self.ui.screen.blit(bg_surf, (bx, by + bh + 3))
                    fill_surf = pygame.Surface((int(bw * frac), 5), pygame.SRCALPHA)
                    fill_surf.fill(fill_col)
                    self.ui.screen.blit(fill_surf, (bx, by + bh + 3))
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
        # Draw voltaic mayhem before enemies and towers so towers cover it
        try:
            self.ui.effects.draw_voltaic_mayhem(shake_x, shake_y)
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        # Draw bloodstain decals (appears under enemies)
        for bloodstain in getattr(self.game, "bloodstains", []):
            try:
                bloodstain.draw(self.ui.screen, shake_x, shake_y)
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

        # Draw enemies (object-based Enemy instances only)
        for enemy in self.game.enemies:
            # Delegate drawing (and particle updates/emission) to the Enemy instance
            # to avoid duplicate particle emission/rendering from both UI and Enemy.
            try:
                enemy.draw(self.ui.screen, shake_x, shake_y)
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

        # Draw bosses
        for boss in self.game.bosses:
            boss.draw(self.ui.screen, shake_x, shake_y)

        # Draw projectiles
        for projectile in self.game.projectiles:
            projectile.draw(self.ui.screen, shake_x, shake_y)

        # Draw enemy projectiles
        for projectile in self.game.enemy_projectiles:
            projectile.draw(self.ui.screen, shake_x, shake_y)

        for drop in getattr(self.game, "health_drops", []):
            try:
                x = int(drop.get("x", 0) + shake_x)
                y = int(drop.get("y", 0) + shake_y)
                r = drop.get("radius", 8)
                alpha = self.ui._health_drop_alpha(drop)
                if pygame:
                    self.ui._draw_health_drop_particle(x, y, r, alpha)
                else:
                    pygame_mod = self.ui.pygame
                    if pygame_mod:
                        pygame_mod.draw.circle(self.ui.screen, (0, 200, 0), (x, y), r)
                        pygame_mod.draw.line(
                            self.ui.screen,
                            (255, 255, 255),
                            (x - r // 2, y),
                            (x + r // 2, y),
                            2,
                        )
                        pygame_mod.draw.line(
                            self.ui.screen,
                            (255, 255, 255),
                            (x, y - r // 2),
                            (x, y + r // 2),
                            2,
                        )
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

        # (statues/towers will be drawn later, after special effects, to ensure
        # they stay above everything including Voltaic Mayhem beams)

        # NOTE: statue projectile visual indicators removed (kept internal data for logic/tests)

        # Draw aura around player once satan growth has started; it remains
        # until the level ends.  we base the pulse on the global frame count so
        # it continues even after the animation period finishes.
        if (
            getattr(self.game, "satan_growth_persistent", False)
            and self.ui.screen is not None
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
                self.ui.screen.blit(aura, (aura_x, aura_y))
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

        # Draw player (skip if invisible during blink transit)
        if not getattr(self.game, "blasphemy_5_invisible", False):
            scale = getattr(self.game, "blasphemy_5_scale", 1.0)
            self.game.player.draw(
                self.ui.screen,
                shake_x,
                shake_y,
                self.game.player_anim_frame,
                self.game.player_is_moving,
                self.game.player_facing_right,
                scale=scale,
            )

        # Draw Blasphemy 5 blink particles (if any)
        try:
            blink_particles = getattr(self.game, "blasphemy_5_blink_particles", [])
            for p in list(blink_particles):
                try:
                    # Draw violet semi-transparent circle
                    size = p.get("size", 6)
                    surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
                    alpha = p.get("alpha", 160)
                    pygame.draw.circle(surf, (150, 100, 200, alpha), (size, size), size)
                    px = int(p["x"] + shake_x - size)
                    py = int(p["y"] + shake_y - size)
                    self.ui.screen.blit(surf, (px, py))
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

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
                        self.ui.screen.blit(
                            surf,
                            (int(p.x + shake_x - p.size), int(p.y + shake_y - p.size)),
                        )
                    except (
                        AttributeError,
                        TypeError,
                        ValueError,
                        KeyError,
                        pygame.error,
                    ):
                        pass
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        # Draw orbitals
        for orb in self.game.orbitals:
            ox = orb.get("x", self.game.player.x)
            oy = orb.get("y", self.game.player.y)
            ox_s, oy_s = self.ui._apply_shake(ox, oy, shake_x, shake_y)
            pygame.draw.circle(self.ui.screen, (176, 240, 255), (ox_s, oy_s), 5)
            pygame.draw.circle(
                self.ui.screen,
                (224, 248, 255),
                (ox_s, oy_s),
                9,
                1,
            )

        # Draw Hell fire particles BEFORE towers so towers layer on top
        self.ui.effects._draw_hell_fire_particles(shake_x, shake_y)

        # Draw pedestals (Limbo only)
        try:
            if hasattr(self, "draw_pedestals"):
                self.draw_pedestals(shake_x, shake_y)
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        # Draw tower energy bar (bottom-right) only if special unlocked and not prologo
        try:
            if self.game.special_unlocked():
                self.ui._draw_tower_energy_bar(shake_x, shake_y)
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def draw_towers(self, shake_x: int = 0, shake_y: int = 0) -> None:
        """Draw purgatory/hell/limbo_final towers on top of all special effects."""
        try:
            if getattr(self.game, "selected_stage", None) and (
                str(self.game.selected_stage).startswith(("purgatory", "hell"))
                or self.game.selected_stage == "limbo_final"
            ):
                lt = getattr(self.game, "left_tower", None)
                rt = getattr(self.game, "right_tower", None)
                if lt and getattr(lt, "visible", False):
                    self.ui._draw_statue_model(
                        int(lt.x + shake_x),
                        STATUE_BASE_Y + shake_y,
                        getattr(lt, "tower_type", None),
                    )
                if rt and getattr(rt, "visible", False):
                    self.ui._draw_statue_model(
                        int(rt.x + shake_x),
                        STATUE_BASE_Y + shake_y,
                        getattr(rt, "tower_type", None),
                    )
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
