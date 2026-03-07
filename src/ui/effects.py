"""UI Effects Renderer: Special effects, lightning, selections, HUD overlays."""

import logging
import math
import os
import random
from typing import TYPE_CHECKING, Any, Literal

from src.assets.manager import get_image
from src.game_constants import (
    SELECTION_BOX_HEIGHT,
    SELECTION_BOX_SPACING,
    SELECTION_BOX_WIDTH,
    WEAPON_ICON_PADDING,
    WEAPON_ICON_SIZE,
)
from src.ui.constants import _WEAPON_HUD_NAMES

if TYPE_CHECKING:
    from src.game.core import Game

logger: logging.Logger = logging.getLogger(__name__)


class UIEffectsRenderer:
    """Handles all special effects rendering: explosions, lightning, selections, HUD overlays."""

    def __init__(self, ui_manager):
        """
        Args:
            ui_manager: Reference to PygameUIManager (parent).
        """
        self.ui = ui_manager
        self.game: Game = ui_manager.game

    # ========== EFFECTS & HUD RENDERING METHODS ==========

    def _draw_tower_energy_bar(self, shake_x: int = 0, shake_y: int = 0) -> None:
        """Draw the shared tower energy bar in the bottom‑right corner.

        The bar is now vertical (growing from bottom to top) and twice as
        thick as the original horizontal design. It still turns gold when full.
        """
        # obtain a local pygame reference like other draw helpers
        pygame = self.ui.pygame
        g = self.game
        if not hasattr(g, "tower_energy") or not hasattr(g, "tower_energy_max"):
            return
        try:
            cur = float(getattr(g, "tower_energy", 0))
            mx = float(getattr(g, "tower_energy_max", 0))
        except (AttributeError, TypeError, ValueError, KeyError):
            return
        if mx <= 0:
            return
        # bar dimensions – vertical orientation (bottom→top)
        bar_w = 16  # twice as thick as the old horizontal bar
        bar_h = 100  # height of the bar
        bar_x = self.ui.width - bar_w - 20
        bar_y = self.ui.height - bar_h - 20
        # background (slightly lighter so empty bar stands out on dark scenes)
        pygame.draw.rect(self.ui.screen, (40, 40, 40), (bar_x, bar_y, bar_w, bar_h))
        # outline/border
        pygame.draw.rect(
            self.ui.screen, (120, 120, 120), (bar_x, bar_y, bar_w, bar_h), 1
        )
        # fill from bottom based on current energy
        fill_h = int(bar_h * min(1.0, cur / mx))
        if fill_h > 0:
            color = (255, 215, 0) if cur >= mx else (200, 200, 200)
            fill_y = bar_y + bar_h - fill_h
            pygame.draw.rect(self.ui.screen, color, (bar_x, fill_y, bar_w, fill_h))

    def draw_special_effects(self, shake_x=0, shake_y=0) -> None:
        # local import ensures pygame is always available inside this method
        try:
            import pygame
        except (AttributeError, TypeError, ValueError, KeyError):
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
                        self.ui.screen.blit(
                            surf,
                            (
                                int(eff["x"] - current) + shake_x,
                                int(eff["y"] - current) + shake_y,
                            ),
                        )
                        # jagged yellow outline resembling skullboom's glow
                        try:
                            import math as math_module

                            num_segments = 10
                            for i in range(num_segments):
                                angle1 = (
                                    2 * math_module.pi * i
                                ) / num_segments + random.uniform(-0.2, 0.2)
                                angle2 = (
                                    2 * math_module.pi * (i + 1)
                                ) / num_segments + random.uniform(-0.2, 0.2)
                                rvar = current + 3 + random.uniform(-2, 2)
                                pygame.draw.arc(
                                    self.ui.screen,
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
                        except (
                            AttributeError,
                            TypeError,
                            ValueError,
                            KeyError,
                            pygame.error,
                        ):
                            pass
                    except (
                        AttributeError,
                        TypeError,
                        ValueError,
                        KeyError,
                        pygame.error,
                    ):
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
                        self.ui.screen.blit(
                            surf,
                            (
                                int(s.get("x", 0) - size) + shake_x,
                                int(s.get("y", 0) - size) + shake_y,
                            ),
                        )
                    except (
                        AttributeError,
                        TypeError,
                        ValueError,
                        KeyError,
                        pygame.error,
                    ):
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
                        self.ui.screen.blit(
                            surf,
                            (
                                int(mx - radius) + shake_x - 4,
                                int(my - radius) + shake_y - 4,
                            ),
                        )
                    except (
                        AttributeError,
                        TypeError,
                        ValueError,
                        KeyError,
                        pygame.error,
                    ):
                        pass
                    # draw a few lightning-style rays from center outward
                    try:
                        import math as math_mod

                        segments = 4
                        for i in range(segments):
                            angle = random.random() * 2 * math_mod.pi
                            length = random.uniform(radius * 0.6, radius)
                            start_x = mx
                            start_y = my
                            end_x = mx + math_mod.cos(angle) * length
                            end_y = my + math_mod.sin(angle) * length
                            # draw as small jagged polyline
                            points = [(start_x, start_y)]
                            steps = int(length / 10)
                            for s in range(1, steps):
                                frac = s / float(steps)
                                px = mx + math_mod.cos(angle) * length * frac
                                py = my + math_mod.sin(angle) * length * frac
                                # random offset perpendicular
                                perp = (-math_mod.sin(angle), math_mod.cos(angle))
                                offset = random.uniform(-5, 5)
                                px += perp[0] * offset
                                py += perp[1] * offset
                                points.append((px, py))
                            points.append((end_x, end_y))
                            pygame.draw.lines(
                                self.ui.screen,
                                (200, 255, 255),
                                False,
                                [(int(x), int(y)) for x, y in points],
                                1,
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

            # Draw Purgatory horde malevolent red wave (expands from player)
            if getattr(self.game, "purgatory_horde_wave_timer", 0.0) > 0.0:
                try:
                    wave_timer = getattr(self.game, "purgatory_horde_wave_timer", 0.0)
                    # Wave expands at 400 pixels/second for 2 seconds total (halved speed)
                    max_radius = 800
                    current_radius = int((wave_timer / 2.0) * max_radius)

                    if current_radius > 0 and self.game.player:
                        # Get player center position
                        px = int(self.game.player.x) + shake_x
                        py = int(self.game.player.y) + shake_y

                        # Calculate alpha: full at start, fades out as it expands
                        alpha = int(255 * (1.0 - min(1.0, wave_timer / 2.0)))

                        if alpha > 0:
                            # Create expanding wave surface with alpha
                            size = current_radius * 2 + 4
                            wave_surf = pygame.Surface((size, size), pygame.SRCALPHA)
                            center = current_radius + 2

                            # Draw multiple rings for wave effect (red, dark red gradient)
                            # Outer: bright red with transparency
                            pygame.draw.circle(
                                wave_surf,
                                (255, 50, 50, alpha),
                                (center, center),
                                current_radius,
                                max(
                                    1, int(3 * (1.0 - wave_timer / 2.0))
                                ),  # outer edge width
                            )
                            # Inner bright ring
                            inner_radius = max(1, int(current_radius * 0.85))
                            if inner_radius > 0:
                                pygame.draw.circle(
                                    wave_surf,
                                    (255, 100, 100, int(alpha * 0.7)),
                                    (center, center),
                                    inner_radius,
                                    max(1, int(2 * (1.0 - wave_timer / 2.0))),
                                )

                            # Blit wave to screen
                            self.ui.screen.blit(
                                wave_surf,
                                (
                                    px - current_radius - 2,
                                    py - current_radius - 2,
                                ),
                            )

                            # Draw translucent reddish veil between the two halos
                            mid_radius_inner = int(current_radius * 0.85)
                            mid_radius_outer = current_radius
                            veil_surf = pygame.Surface((size, size), pygame.SRCALPHA)
                            veil_alpha = int(
                                40 * (1.0 - wave_timer / 2.0)
                            )  # Subtle transparency
                            if veil_alpha > 0:
                                pygame.draw.circle(
                                    veil_surf,
                                    (200, 80, 80, veil_alpha),  # Reddish tint
                                    (center, center),
                                    mid_radius_outer,
                                )
                                pygame.draw.circle(
                                    veil_surf,
                                    (200, 80, 80, 0),  # Transparent inner
                                    (center, center),
                                    mid_radius_inner,
                                )
                            self.ui.screen.blit(
                                veil_surf,
                                (
                                    px - current_radius - 2,
                                    py - current_radius - 2,
                                ),
                            )

                            # Draw infernal fire particles between the two halos
                            mid_radius_inner = int(current_radius * 0.85)
                            mid_radius_outer = current_radius

                            # Spawn particles in the ring between inner and outer halo
                            import math

                            num_particles = max(8, int(current_radius / 40))
                            for i in range(num_particles):
                                angle = (
                                    wave_timer * 3.0 + (i / num_particles) * 2 * math.pi
                                ) % (2 * math.pi)

                                # Particle position between inner and outer radius
                                progress = (
                                    (i + wave_timer * 2) % num_particles / num_particles
                                )
                                particle_radius = (
                                    mid_radius_inner
                                    + (mid_radius_outer - mid_radius_inner) * progress
                                )

                                particle_x = px + math.cos(angle) * particle_radius
                                particle_y = py + math.sin(angle) * particle_radius

                                # Dark red with orange speckles
                                if i % 3 == 0:
                                    color = (255, 120, 0, alpha)  # Orange
                                else:
                                    color = (180, 20, 20, alpha)  # Dark red

                                particle_size = max(
                                    4, int(8 * (1.0 - wave_timer / 2.0))
                                )
                                pygame.draw.circle(
                                    self.ui.screen,
                                    color,
                                    (int(particle_x), int(particle_y)),
                                    particle_size,
                                )
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

        self.draw_chain_lightning_effects(shake_x, shake_y)

    def draw_lightning_effect(self, shake_x=0, shake_y=0):
        pygame = self.ui.pygame
        if not self.ui.screen or not pygame:
            return
        try:
            # Screen flash based on a pulsing alpha (use frame_count)
            flash_alpha: float = abs(math.sin(self.game.frame_count * 0.18))
            if flash_alpha > 0.25:
                overlay = pygame.Surface(
                    (self.ui.width, self.ui.height), pygame.SRCALPHA
                )
                alpha = int(min(255, 180 * flash_alpha))
                overlay.fill((255, 255, 255, alpha))
                self.ui.screen.blit(overlay, (0, 0))

            # Draw falling light beam (replaces bolt) and keep explosion
            pts: Any | None = getattr(self.game, "lightning_points", None)
            if pts and len(pts) > 0:
                end_x, end_y = pts[-1]
            else:
                end_x = int(getattr(self.game.player, "x", self.ui.width // 2))
                end_y = int(getattr(self.game.player, "y", self.ui.height - 80))

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
            beam_surf = pygame.Surface((self.ui.width, self.ui.height), pygame.SRCALPHA)
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
            self.ui.screen.blit(beam_surf, (0, 0))

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
                        self.ui.screen,
                        os.path.join("screenshots", f"{suffix}_beam_start.png"),
                    )
                    self.game._screenshot_taken_start = True
                if (
                    not getattr(self.game, "_screenshot_taken_peak", False)
                    and t == peak_frame
                ):
                    pygame.image.save(
                        self.ui.screen,
                        os.path.join("screenshots", f"{suffix}_beam_peak.png"),
                    )
                    self.game._screenshot_taken_peak = True
            except (
                AttributeError,
                TypeError,
                ValueError,
                KeyError,
                PermissionError,
                OSError,
            ):
                pass

            # Explosion / impact at the end point
            # Make a pulsing explosion that grows over the configured timer
            max_radius = 160
            radius = int(min(max_radius, (t / float(total)) * max_radius + 8))
            pulse: float = (math.sin(self.game.frame_count * 0.25) + 1) * 0.5
            # Outer glow circle
            pygame.draw.circle(
                self.ui.screen,
                (255, 240, 200),
                self.ui._apply_shake(end_x, end_y, shake_x, shake_y),
                int(radius * 1.1),
            )
            end_xs, end_ys = self.ui._apply_shake(end_x, end_y, shake_x, shake_y)
            pygame.draw.circle(
                self.ui.screen,
                (255, 255, 200),
                (end_xs, end_ys),
                int(radius * 0.6 + pulse * 8),
            )
            for ang in range(0, 360, 45):
                rad: float = math.radians(ang)
                lx: Any | float = end_x + math.cos(rad) * (radius * 0.9)
                ly: Any | float = end_y + math.sin(rad) * (radius * 0.9)
                lxs, lys = self.ui._apply_shake(lx, ly, shake_x, shake_y)
                pygame.draw.line(
                    self.ui.screen,
                    (255, 255, 230),
                    (end_xs, end_ys),
                    (lxs, lys),
                    3,
                )
            else:
                # Fallback: vertical beam above player like old behavior
                player_x: Any | int = getattr(self.game.player, "x", self.ui.width // 2)
                player_y: Any | int = getattr(
                    self.game.player, "y", self.ui.height - 80
                )
                beam_width = 8
                beam_x: Any | int = player_x
                pygame.draw.line(
                    self.ui.screen,
                    (255, 255, 200),
                    (beam_x + shake_x, 0 + shake_y),
                    (beam_x + shake_x, player_y + shake_y),
                    beam_width + 12,
                )
        except (AttributeError, TypeError, ValueError, KeyError):
            # Avoid breaking the game if drawing fails
            logger.exception("draw_lightning_effect failed")

    def draw_chain_lightning_effects(self, shake_x=0, shake_y=0) -> None:
        """Draw chain lightning effects between enemies"""
        pygame = self.ui.pygame
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
                            self.ui.screen.blit(
                                glow_surf,
                                (
                                    int(cx - radius) + shake_x - 4,
                                    int(cy - radius) + shake_y - 4,
                                ),
                            )
                        except (
                            AttributeError,
                            TypeError,
                            ValueError,
                            KeyError,
                            pygame.error,
                        ):
                            pass

                        # Inner bright core
                        try:
                            inner_alpha = min(255, alpha + 40)
                            cxs, cys = self.ui._apply_shake(cx, cy, shake_x, shake_y)
                            pygame.draw.circle(
                                self.ui.screen,
                                (255, 255, 230, inner_alpha),
                                (cxs, cys),
                                max(3, int(radius * 0.15)),
                            )
                        except (
                            AttributeError,
                            TypeError,
                            ValueError,
                            KeyError,
                            pygame.error,
                        ):
                            pass

                        # Irregular radial lightning bolts for emphasis
                        try:
                            for ang in range(0, 360, 45):
                                rad = math.radians(ang)
                                ex = cx + math.cos(rad) * (radius * 0.9)
                                ey = cy + math.sin(rad) * (radius * 0.9)
                                radial_points = self.ui._generate_lightning_path(
                                    cx + shake_x,
                                    cy + shake_y,
                                    ex + shake_x,
                                    ey + shake_y,
                                    segments=4,
                                    max_offset=4,
                                )
                                for j in range(len(radial_points) - 1):
                                    pygame.draw.line(
                                        self.ui.screen,
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
                        except (
                            AttributeError,
                            TypeError,
                            ValueError,
                            KeyError,
                            pygame.error,
                        ):
                            pass

                        # Sparks at destination points (short-lived bright dots)
                        try:
                            for px, py in points[1:]:
                                pxs, pys = self.ui._apply_shake(
                                    px, py, shake_x, shake_y
                                )
                                pygame.draw.circle(
                                    self.ui.screen,
                                    (200, 255, 255, alpha),
                                    (pxs, pys),
                                    4,
                                )
                        except (
                            AttributeError,
                            TypeError,
                            ValueError,
                            KeyError,
                            pygame.error,
                        ):
                            pass
                    except (
                        AttributeError,
                        TypeError,
                        ValueError,
                        KeyError,
                        pygame.error,
                    ):
                        pass

                # Draw jagged lines between consecutive points
                # Draw the jagged line segments. Allow effect-provided color (RGB) and apply alpha fade.
                color_base = effect.get("color", (150, 200, 255))
                try:
                    if len(color_base) >= 3:
                        color = (color_base[0], color_base[1], color_base[2], alpha)
                    else:
                        color = (150, 200, 255, alpha)
                except (AttributeError, TypeError, ValueError, KeyError):
                    color = (150, 200, 255, alpha)

                if is_explosion:
                    # For explosion, draw independent lightning bolts from center to each target
                    center_x, center_y = points[0]
                    for target_x, target_y in points[1:]:
                        lightning_points = self.ui._generate_lightning_path(
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
                                self.ui.screen,
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
                        lightning_points = self.ui._generate_lightning_path(
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
                                self.ui.screen,
                                color,
                                lightning_points[j],
                                lightning_points[j + 1],
                                thickness,
                            )
        except (AttributeError, TypeError, ValueError, KeyError):
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

        Uses self.game state and self.ui.screen (pygame Surface)."""
        pygame = self.ui.pygame
        if not self.ui.screen or not pygame:
            return

        font = self.ui.get_font(24)
        small_font = self.ui.get_font(18)

        # Score
        score_text = self.ui.get_text(
            f"Score: {int(self.game.score)}", font, (255, 255, 0)
        )
        self.ui.screen.blit(score_text, (10 + shake_x, 10 + shake_y))

        # Wave
        wave_text = self.ui.get_text(f"Wave: {self.game.wave}", font, (255, 100, 100))
        self.ui.screen.blit(wave_text, (10 + shake_x, 40 + shake_y))

        # Time
        minutes = int(self.game.time_elapsed // 60)
        seconds = int(self.game.time_elapsed % 60)
        time_text = self.ui.get_text(
            f"Time: {minutes}:{seconds:02d}", font, (100, 200, 255)
        )
        self.ui.screen.blit(time_text, (10 + shake_x, 70 + shake_y))

        # Health bar
        bar_width = 200
        bar_height = 20
        bar_x: int = self.ui.width - bar_width - 10
        bar_y = 10

        # Background
        pygame.draw.rect(
            self.ui.screen,
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
            self.ui.screen,
            health_color,
            (bar_x + shake_x, bar_y + shake_y, bar_width * health_ratio, bar_height),
        )
        # Border
        pygame.draw.rect(
            self.ui.screen,
            (255, 255, 255),
            (bar_x + shake_x, bar_y + shake_y, bar_width, bar_height),
            2,
        )

        # Health text
        health_text = self.ui.get_text(
            f"{int(self.game.player.health)}/{int(self.game.player.max_health)}",
            small_font,
            (255, 255, 255),
        )
        self.ui.screen.blit(
            health_text,
            (
                bar_x + bar_width // 2 - health_text.get_width() // 2 + shake_x,
                bar_y + bar_height // 2 - health_text.get_height() // 2 + shake_y,
            ),
        )

        # XP bar
        xp_bar_y = 40
        pygame.draw.rect(
            self.ui.screen,
            (100, 100, 100),
            (bar_x + shake_x, xp_bar_y + shake_y, bar_width, bar_height),
        )
        xp_ratio: float = self.game.player_xp / max(1, self.game.xp_to_next_level)
        # XP bar in darker purple
        pygame.draw.rect(
            self.ui.screen,
            (120, 34, 160),
            (bar_x + shake_x, xp_bar_y + shake_y, bar_width * xp_ratio, bar_height),
        )
        pygame.draw.rect(
            self.ui.screen,
            (255, 255, 255),
            (bar_x + shake_x, xp_bar_y + shake_y, bar_width, bar_height),
            2,
        )

        # XP text
        xp_text = self.ui.get_text(
            f"{int(self.game.player_xp)}/{int(self.game.xp_to_next_level)}",
            small_font,
            (255, 255, 255),
        )
        self.ui.screen.blit(
            xp_text,
            (
                bar_x + bar_width // 2 - xp_text.get_width() // 2 + shake_x,
                xp_bar_y + bar_height // 2 - xp_text.get_height() // 2 + shake_y,
            ),
        )

        # Level
        level_text = self.ui.get_text(
            f"Level {self.game.player_level}", font, (255, 215, 0)
        )
        self.ui.screen.blit(
            level_text,
            (
                bar_x + bar_width // 2 - level_text.get_width() // 2 + shake_x,
                xp_bar_y + bar_height + 5 + shake_y,
            ),
        )

        # Weapon HUD - show extra weapons with levels
        hud_x: int = self.ui.width - 10
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
                    self.ui.screen,
                    (22, 22, 22),
                    (hud_x - box_w + shake_x, y - 10 + shake_y, box_w, box_h),
                )
                pygame.draw.rect(
                    self.ui.screen,
                    (68, 68, 68),
                    (hud_x - box_w + shake_x, y - 10 + shake_y, box_w, box_h),
                    1,
                )

                weapon_text = small_font.render(display_text, True, (200, 200, 200))
                self.ui.screen.blit(
                    weapon_text,
                    (
                        hud_x - box_w // 2 - weapon_text.get_width() // 2 + shake_x,
                        y - 8 + shake_y,
                    ),
                )

                # If at max level, add MAX indicator
                if lvl >= getattr(self.game, "max_weapon_level", 6):
                    max_text = small_font.render("MAX", True, (255, 215, 0))
                    self.ui.screen.blit(
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
        pygame = self.ui.pygame
        if not self.ui.screen or not pygame:
            return

        for msg in list(self.game.center_messages):
            try:
                font = self.ui.get_font(msg.get("font_size", 36))
                # Shadow for readability
                shadow_text = self.ui.get_text(msg["text"], font, (0, 0, 0))
                self.ui.screen.blit(
                    shadow_text,
                    (
                        self.ui.width // 2 - shadow_text.get_width() // 2 + 2 + shake_x,
                        self.ui.height // 2 - 40 + 2 + shake_y,
                    ),
                )
                # Main text
                main_text = self.ui.get_text(msg["text"], font, msg["color"])
                self.ui.screen.blit(
                    main_text,
                    (
                        self.ui.width // 2 - main_text.get_width() // 2 + shake_x,
                        self.ui.height // 2 - 40 + shake_y,
                    ),
                )
            except (AttributeError, TypeError, ValueError, KeyError):
                logger.exception("Error drawing center message")
                # Remove the problematic message
                if msg in self.game.center_messages:
                    self.game.center_messages.remove(msg)

    def draw_fps_counter(self, shake_x: int = 0, shake_y: int = 0) -> None:
        """Draw the FPS counter in the top-right corner, always on top, no shake."""
        if not getattr(self.game, "show_fps", True):
            return
        pygame = self.ui.pygame
        if not self.ui.screen or not pygame:
            return
        try:
            fps_val = int(self.game.clock.get_fps())
            font = self.ui.get_font(18)
            fps_text = self.ui.get_text(f"FPS: {fps_val}", font, (200, 200, 200))
            x = self.ui.width - fps_text.get_width() - 6
            y = 6
            # Dark background for readability
            bg = pygame.Surface((fps_text.get_width() + 4, fps_text.get_height() + 2))
            bg.fill((0, 0, 0))
            bg.set_alpha(120)
            self.ui.screen.blit(bg, (x - 2, y - 1))
            self.ui.screen.blit(fps_text, (x, y))
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def draw_prologo_end(self, shake_x=0, shake_y=0) -> None:
        """Draw the prologo completion screen"""
        try:
            import pygame

            # Create semi-transparent purple overlay
            overlay = pygame.Surface((self.ui.width, self.ui.height))
            overlay.fill((40, 20, 45))  # Purple background
            overlay.set_alpha(180)  # Semi-transparent (0-255, 180 = ~70% opacity)
            self.game.screen.blit(overlay, (0, 0))

            font_large = self.ui.get_font(48)
            font_medium = self.ui.get_font(32)

            # Title
            title = self.ui.get_text("SATAN'S FALL COMPLETE", font_large, (255, 215, 0))
            self.game.screen.blit(
                title,
                (
                    self.game.width // 2 - title.get_width() // 2 + shake_x,
                    self.game.height // 2 - 100 + shake_y,
                ),
            )

            # Message
            message1 = self.ui.get_text(
                "You have witnessed Satan's fall from grace.",
                font_medium,
                (255, 255, 255),
            )
            message2 = self.ui.get_text(
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
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def draw_weapon_selection(self, shake_x=0, shake_y=0) -> None:
        """Draw weapon selection screen"""
        try:
            import pygame

            font_title = self.ui.get_font(38)
            font_name = self.ui.get_font(26)
            font_desc = self.ui.get_font(17)
            font_small = self.ui.get_font(15)
            font_key = self.ui.get_font(17)

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
            title_surf = self.ui.get_text(title_text, font_title, C_TITLE)
            sub_surf = self.ui.get_text(sub_text, font_small, (90, 100, 130))
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
                    icon_surf = get_image(
                        icon_path, (WEAPON_ICON_SIZE, WEAPON_ICON_SIZE)
                    )
                    # if the named asset wasn't found, try the alternate naming
                    # convention (strip or add "weapon_" prefix) so manually
                    # dropped files still work.
                    if icon_surf is None:
                        if icon_path.startswith("weapon_"):
                            alt = icon_path[len("weapon_") :]
                        else:
                            alt = f"weapon_{icon_path}"
                        icon_surf = get_image(alt, (WEAPON_ICON_SIZE, WEAPON_ICON_SIZE))
                    if icon_surf:
                        icon_y = by + (box_height - WEAPON_ICON_SIZE) // 2
                        self.game.screen.blit(icon_surf, (icon_start_x, icon_y))

                # key (e.g. "[1]") comes after icon/margin
                key_surf = self.ui.get_text(f"[{i + 1}]", font_key, C_KEY)
                self.game.screen.blit(
                    key_surf,
                    (content_x, by + box_height // 2 - key_surf.get_height() // 2),
                )
                content_x += key_surf.get_width() + WEAPON_ICON_PADDING

                name_surf = self.ui.get_text(weapon["name"], font_name, name_col)
                desc_surf = self.ui.get_text(weapon["description"], font_desc, C_DESC)
                block_h = name_surf.get_height() + 4 + desc_surf.get_height()
                name_x = content_x
                name_y = by + (box_height - block_h) // 2
                self.game.screen.blit(name_surf, (name_x, name_y))
                self.game.screen.blit(
                    desc_surf, (name_x, name_y + name_surf.get_height() + 4)
                )
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def draw_tower_selection(self, shake_x=0, shake_y=0) -> None:
        """Draw tower selection screen (Purgatory)."""
        try:
            import pygame

            font_title = self.ui.get_font(38)
            font_name = self.ui.get_font(26)
            font_desc = self.ui.get_font(17)
            font_small = self.ui.get_font(15)
            font_key = self.ui.get_font(17)

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
            title_surf = self.ui.get_text("CHOOSE YOUR TOWER", font_title, C_TITLE)
            sub_surf = self.ui.get_text("place your guardian", font_small, (75, 75, 80))
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

                key_surf = self.ui.get_text(f"[{i + 1}]", font_key, C_KEY)
                self.game.screen.blit(
                    key_surf,
                    (bx + 16, by + box_height // 2 - key_surf.get_height() // 2),
                )

                name_surf = self.ui.get_text(tower["name"], font_name, C_NAME)
                desc_surf = self.ui.get_text(tower["description"], font_desc, C_DESC)
                block_h = name_surf.get_height() + 4 + desc_surf.get_height()
                name_x = bx + 52
                name_y = by + (box_height - block_h) // 2
                self.game.screen.blit(name_surf, (name_x, name_y))
                self.game.screen.blit(
                    desc_surf, (name_x, name_y + name_surf.get_height() + 4)
                )
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def draw_upgrade_selection(self, shake_x=0, shake_y=0) -> None:
        """Draw upgrade selection screen"""
        try:
            import pygame

            font_title = self.ui.get_font(38)
            font_name = self.ui.get_font(26)
            font_desc = self.ui.get_font(17)
            font_small = self.ui.get_font(15)
            font_key = self.ui.get_font(17)

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
            title_surf = self.ui.get_text("LEVEL UP", font_title, C_TITLE)
            sub_surf = self.ui.get_text(
                "choose your upgrade", font_small, (110, 110, 110)
            )
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
                reroll_surf = self.ui.get_text(
                    reroll_label, font_small, (190, 150, 150)
                )
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
                key_surf = self.ui.get_text(f"[{i + 1}]", font_key, C_KEY)
                key_x = bx + 16
                key_y = by + box_height // 2 - key_surf.get_height() // 2
                self.game.screen.blit(key_surf, (key_x, key_y))

                # name + description — centred vertically in the box
                name_surf = self.ui.get_text(upgrade["name"], font_name, name_col)
                desc_surf = self.ui.get_text(upgrade["description"], font_desc, C_DESC)
                block_h = name_surf.get_height() + 4 + desc_surf.get_height()
                name_x = bx + 52
                name_y = by + (box_height - block_h) // 2
                self.game.screen.blit(name_surf, (name_x, name_y))
                self.game.screen.blit(
                    desc_surf, (name_x, name_y + name_surf.get_height() + 4)
                )
        except (AttributeError, TypeError, ValueError, KeyError):
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
            title_surf = self.ui.get_text(
                "FALL", self.ui.get_font(64), (139, 0, 0)
            ).copy()
            title_surf.set_alpha(int(self.game.game_over_alpha))
            self.game.screen.blit(
                title_surf,
                (
                    self.game.width // 2 - title_surf.get_width() // 2 + shake_x,
                    200 + shake_y,
                ),
            )

            # Stats
            font_medium = self.ui.get_font(24)
            stats = [
                f"Final Score: {int(self.game.score)}",
                f"Enemies killed: {getattr(self.game, 'enemies_killed_this_run', 0)}",
                f"Wave: {self.game.wave}",
                f"Level: {self.game.player.level}",
            ]

            for i, stat in enumerate(stats):
                text_surf = self.ui.get_text(stat, font_medium, (255, 255, 255)).copy()
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
            prompt = self.ui.get_text(
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

            title_surf = self.ui.get_text(
                "SATANIC VICTORY!", self.ui.get_font(64), (255, 215, 0)
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
            instr = self.ui.get_text(
                "ENTER → Next level    ESC → Main menu",
                self.ui.get_font(24),
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
