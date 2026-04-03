"""ParticleSystem — handles rendering and updating of particle effects.

Manages explosion rings, blizzard spirals, floating damage text, ice particles,
and related visual effects. All particle state lives on the Game object; this
system is purely responsible for update and draw logic.
"""

from __future__ import annotations

import logging
import math
import random
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from src.game import Game

logger = logging.getLogger(__name__)


class ParticleSystem:
    """Manages rendering and updating of particle effects."""

    def __init__(self, game: Game) -> None:
        self.game = game

    def draw_particles(
        self,
        surface: pygame.Surface,
        particles: list,
        color_fn,
        alpha_fn,
        shake_x: int = 0,
        shake_y: int = 0,
        filter_fn=None,
    ) -> None:
        """Generic particle drawing helper.

        Args:
            surface: Target pygame surface to draw on
            particles: List of particle objects with x, y, size, life attributes
            color_fn: Callable(particle) -> (r, g, b) or (r, g, b, a)
            alpha_fn: Callable(particle) -> alpha_value (0-255)
            shake_x, shake_y: Screen shake offset
            filter_fn: Optional callable(particle) -> bool to filter particles to draw
        """
        try:
            for p in particles:
                try:
                    # Apply optional filter (e.g., distance culling for blasphemy5)
                    if filter_fn and not filter_fn(p):
                        continue

                    # Get color and alpha
                    color = color_fn(p)
                    alpha = alpha_fn(p)

                    # Handle both RGB and RGBA colors
                    if len(color) == 3:
                        color = (*color, alpha)

                    # Draw particle as small circle
                    surf = pygame.Surface(
                        (p.size * 2 + 2, p.size * 2 + 2), pygame.SRCALPHA
                    )
                    pygame.draw.circle(surf, color, (p.size + 1, p.size + 1), p.size)
                    surface.blit(
                        surf,
                        (int(p.x - p.size) + shake_x, int(p.y - p.size) + shake_y),
                    )
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def draw_skullboom_particles(self, shake_x: int = 0, shake_y: int = 0) -> None:
        """Draw SkullBoom explosion particles and area effects."""
        g = self.game
        # Draw explosion area effects first (behind particles)
        if g.skullboom_explosions:
            try:
                for explosion in g.skullboom_explosions:
                    center_x = int(explosion["x"] + shake_x)
                    center_y = int(explosion["y"] + shake_y)

                    # Calculate fade based on timer
                    progress = explosion["timer"] / explosion["max_timer"]
                    alpha = int(255 * progress * 0.6)  # Max 60% opacity

                    # Compute current radius.  A fixed indicator stays at max_radius
                    if explosion.get("indicator"):
                        current_radius = explosion["max_radius"]
                        # darker purple filled disc with greater transparency
                        alpha = int(50)  # reduced opacity for interior
                    elif explosion.get("revive"):
                        # eased progression (slower early, faster near the end)
                        eased = 1 - (progress**1.6)
                        base_offset = 0.0  # revive starts small and expands
                        current_radius = int(
                            explosion["max_radius"]
                            * (base_offset + eased * (1 - base_offset))
                        )
                    else:
                        # Legacy behaviour for other explosions (keeps existing look)
                        current_radius = int(
                            explosion["max_radius"] * (1 - progress + 0.3)
                        )  # Start small, expand

                    # Create irregular ring by drawing multiple arc segments
                    num_segments = 12  # Number of segments to create irregular shape
                    segment_angle = 2 * math.pi / num_segments

                    # Outer glow ring - use explosion-specific color when present
                    try:
                        from src.game_constants import FIRE_SPECIAL_EXPLOSION_COLOR
                    except (AttributeError, TypeError, ValueError, KeyError):
                        FIRE_SPECIAL_EXPLOSION_COLOR = (200, 100, 40)
                    base_col = explosion.get("color", FIRE_SPECIAL_EXPLOSION_COLOR)
                    glow_color = (base_col[0], base_col[1], base_col[2], alpha // 3)

                    # orange halo for normal (non-revive, non-indicator) explosions
                    if not explosion.get("indicator") and not explosion.get("revive"):
                        halo_alpha = int(120 * (1 - progress))
                        try:
                            # silver halo outline
                            pygame.draw.circle(
                                g.screen,
                                (200, 200, 200, halo_alpha),  # silver halo
                                (center_x, center_y),
                                current_radius + int(10 * progress),
                                2,
                            )
                            # transparent inner pulse particle, expands faster and more transparent
                            inner_alpha = int(80 * (1 - progress))
                            inner_rad = int(current_radius * (0.5 + 0.8 * progress))
                            # draw inner particle on temp surface for alpha
                            part = pygame.Surface(
                                (inner_rad * 2 + 4, inner_rad * 2 + 4), pygame.SRCALPHA
                            )
                            pygame.draw.circle(
                                part,
                                (200, 200, 200, inner_alpha),
                                (inner_rad + 2, inner_rad + 2),
                                inner_rad,
                            )
                            g.screen.blit(
                                part,
                                (center_x - inner_rad - 2, center_y - inner_rad - 2),
                            )
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass

                    # if indicator, draw a solid translucent filled circle to mark area
                    if explosion.get("indicator"):
                        try:
                            # translucent dark purple fill via temporary surface
                            col = explosion.get("color", (100, 0, 100))
                            surf = pygame.Surface(
                                (current_radius * 2 + 4, current_radius * 2 + 4),
                                pygame.SRCALPHA,
                            )
                            pygame.draw.circle(
                                surf,
                                (col[0], col[1], col[2], 40),
                                (current_radius + 2, current_radius + 2),
                                current_radius,
                            )
                            g.screen.blit(
                                surf,
                                (
                                    center_x - current_radius - 2,
                                    center_y - current_radius - 2,
                                ),
                            )
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                    for i in range(num_segments):
                        start_angle = i * segment_angle + random.uniform(
                            -0.3, 0.3
                        )  # Add randomness
                        end_angle = (i + 1) * segment_angle + random.uniform(-0.3, 0.3)
                        radius_variation = (
                            current_radius + 3 + random.uniform(-2, 2)
                        )  # Vary radius

                        # Draw arc segment
                        pygame.draw.arc(
                            g.screen,
                            glow_color[:3],
                            (
                                center_x - radius_variation,
                                center_y - radius_variation,
                                radius_variation * 2,
                                radius_variation * 2,
                            ),
                            start_angle,
                            end_angle,
                            max(1, int(3 * progress)),
                        )

                    # Inner trail for revive explosions: large, pulsing halo (orange-leaning)
                    if explosion.get("revive"):
                        try:
                            # Make the inner halo very large (nearly the explosion radius)
                            inner_radius = max(6, int(current_radius * 0.88))
                            inner_alpha = max(0, min(220, int(220 * progress)))

                            # Pulsing animation driven by explosion elapsed frames so it
                            # continues to animate even when global frame_count is paused.
                            elapsed = explosion.get("max_timer", 0) - explosion.get(
                                "timer", 0
                            )
                            freq_hz = 2.0
                            phase = (elapsed / max(1, g.fps)) * (2 * math.pi) * freq_hz
                            pulse = 1.0 + 0.06 * math.sin(phase)  # +/-6% scale

                            display_radius = max(4, int(inner_radius * pulse))
                            display_alpha = max(
                                0,
                                min(
                                    255,
                                    int(inner_alpha * (0.9 + 0.1 * math.sin(phase))),
                                ),
                            )

                            trail_surf = pygame.Surface(
                                (display_radius * 2 + 10, display_radius * 2 + 10),
                                pygame.SRCALPHA,
                            )
                            trail_col = explosion.get(
                                "inner_color", explosion.get("color", (255, 120, 80))
                            )
                            # Draw pulsing inner halo (slightly softer fill)
                            pygame.draw.circle(
                                trail_surf,
                                (
                                    trail_col[0],
                                    trail_col[1],
                                    trail_col[2],
                                    display_alpha,
                                ),
                                (display_radius + 5, display_radius + 5),
                                display_radius,
                            )
                            g.screen.blit(
                                trail_surf,
                                (
                                    center_x - display_radius - 5,
                                    center_y - display_radius - 5,
                                ),
                            )
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass

                    # Draw skullboom particles (orange/brown color), clipped to
                    # the current explosion radius so they don't spill across
                    # the whole battlefield.
                    _ex = explosion["x"]
                    _ey = explosion["y"]
                    _er = max(current_radius, 1)
                    self.draw_particles(
                        g.screen,
                        g.skullboom_particles,
                        color_fn=lambda p: (255, 180, 80),
                        alpha_fn=lambda p: max(30, int(255 * (p.life / 40))),
                        shake_x=shake_x,
                        shake_y=shake_y,
                        filter_fn=lambda p, ex=_ex, ey=_ey, er=_er: (
                            math.hypot(p.x - ex, p.y - ey) <= er
                        ),
                    )

                    # Particles specific to blasphemy_5 revive (draw in red/orange)
                    # Only draw particles that are currently inside the expanding ring
                    revive_center_x = explosion["x"]
                    revive_center_y = explosion["y"]
                    self.draw_particles(
                        g.screen,
                        getattr(g, "blasphemy5_particles", []),
                        color_fn=lambda p: getattr(p, "color_override", (255, 80, 80)),
                        alpha_fn=lambda p: max(30, int(255 * (p.life / 48))),
                        shake_x=shake_x,
                        shake_y=shake_y,
                        filter_fn=lambda p: (
                            math.hypot(p.x - revive_center_x, p.y - revive_center_y)
                            <= current_radius
                        ),
                    )
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

    def draw_floating_texts(self, shake_x: int = 0, shake_y: int = 0) -> None:
        """Draw all floating texts to screen applying shake offsets."""
        g = self.game
        if not getattr(g, "floating_texts", None):
            return
        try:
            from src.assets.text_cache import get_font, get_text
        except (AttributeError, TypeError, ValueError, KeyError):
            return
        try:
            for ft in g.floating_texts:
                try:
                    font = get_font(ft.font_size)
                    # determine alpha and screen coordinates up front so both outline
                    # and fill use the same reference point.  Previously these were
                    # computed *after* attempting to draw the outline which meant the
                    # outline code referenced undefined variables (``alpha``/``sx``/``sy``)
                    # and would abort via an exception, effectively drawing a second
                    # standalone word instead of a stroked glyph.
                    alpha = ft.fade_alpha()
                    sx = int(
                        ft.x
                        - get_text(ft.text, font, ft.color).get_width() / 2
                        + shake_x
                    )
                    sy = (
                        int(ft.y + shake_y)
                        - get_text(ft.text, font, ft.color).get_height()
                    )

                    # draw outline first if requested (use more offsets for a thicker
                    # stroke so the effect is clearly visible; diagonals help avoid
                    # holes in corners).
                    if getattr(ft, "outline_color", None):
                        outline_surf = get_text(ft.text, font, ft.outline_color).copy()
                        try:
                            outline_surf.set_alpha(alpha)
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                        # blit around the center pixel
                        for ox_off, oy_off in (
                            (-1, 0),
                            (1, 0),
                            (0, -1),
                            (0, 1),
                            (-1, -1),
                            (-1, 1),
                            (1, -1),
                            (1, 1),
                        ):
                            g.screen.blit(outline_surf, (sx + ox_off, sy + oy_off))

                    surf = get_text(ft.text, font, ft.color).copy()
                    try:
                        surf.set_alpha(alpha)
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass
                    g.screen.blit(surf, (sx, sy))
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        # Draw particles
        if not g.skullboom_particles:
            return

    def draw_cocytus_particles(self, shake_x: int = 0, shake_y: int = 0) -> None:
        """Draw Cocytus shard particles — near-white, smooth circles."""
        g = self.game
        particles = getattr(g, "cocytus_particles", None)
        if not particles:
            return
        self.draw_particles(
            g.screen,
            particles,
            color_fn=lambda p: (210, 240, 255),
            alpha_fn=lambda p: max(30, int(255 * (p.life / 25))),
            shake_x=shake_x,
            shake_y=shake_y,
        )

    def draw_ice_particles(self, shake_x: int = 0, shake_y: int = 0) -> None:
        """Draw ice explosion particles."""
        g = self.game
        if not g.ice_particles:
            return
        self.draw_particles(
            g.screen,
            g.ice_particles,
            color_fn=lambda p: (100, 200, 255),
            alpha_fn=lambda p: max(30, int(255 * (p.life / 30))),
            shake_x=shake_x,
            shake_y=shake_y,
        )

    def draw_ice_puddles(self, shake_x: int = 0, shake_y: int = 0) -> None:
        """Draw puddles (ice or blizzard) that slow enemies with organic shapes."""
        g = self.game
        any_puddles = (getattr(g, "ice_puddles", []) or []) + (
            getattr(g, "blizzard_puddles", []) or []
        )
        if not any_puddles:
            return
        try:
            for puddle in any_puddles:
                px = puddle["x"] + shake_x
                py = puddle["y"] + shake_y
                radius = puddle["radius"]

                # For Blizzard puddles, radius should grow from 0 to max over time.
                if puddle.get("blizzard"):
                    try:
                        from src.game_constants import (
                            BLIZZARD_GROWTH_MULTIPLIER,
                            BLIZZARD_MAX_DURATION,
                        )
                    except (AttributeError, TypeError, ValueError, KeyError):
                        BLIZZARD_MAX_DURATION = 1
                        BLIZZARD_GROWTH_MULTIPLIER = 1.0
                    # compute progress of lifetime (0 at spawn, 1 at end) and
                    # apply growth multiplier to make the expansion a bit quicker.
                    growth = 1 - (puddle.get("timer", 0) / BLIZZARD_MAX_DURATION)
                    growth *= BLIZZARD_GROWTH_MULTIPLIER
                    if growth > 1:
                        growth = 1
                    radius = int(radius * growth)
                    if radius < 1:
                        radius = 1

                is_cocytus = puddle.get("source") == "cocytus"

                # Fade out as timer decreases
                progress = puddle["timer"] / (5 * 60)  # Max 5 seconds
                if is_cocytus:
                    # Faster fade: squared progress + lower max alpha
                    alpha = int(70 * (progress ** 1.6))
                else:
                    alpha = int(70 * progress)  # Max 70 alpha (more transparent)

                # Create irregular shape instead of perfect circle
                # Use puddle position as seed for consistent but varied shapes
                random.seed(int(px + py))

                # Generate 24-32 points around the center with varying radii for very smooth curves
                num_points = random.randint(24, 32)
                points = []

                for i in range(num_points):
                    angle = (2 * math.pi * i) / num_points
                    if is_cocytus:
                        # ±3% variation for clean, almost circular shape
                        radius_variation = radius * (0.97 + random.random() * 0.06)
                    elif puddle.get("blizzard"):
                        # ±4% instead of ±8% variation
                        radius_variation = radius * (0.96 + random.random() * 0.08)
                    else:
                        # Vary radius by ±8% for subtle organic variation with very smooth curves
                        radius_variation = radius * (0.92 + random.random() * 0.16)

                    x = px + math.cos(angle) * radius_variation
                    y = py + math.sin(angle) * radius_variation
                    points.append((int(x), int(y)))

                # Reset random seed to avoid affecting other random operations
                random.seed()

                # Pick fill color based on puddle source
                if is_cocytus:
                    fill_color = (200, 235, 255, alpha)
                else:
                    fill_color = (100, 200, 255, alpha)

                # Draw irregular puddle shape
                surf = pygame.Surface(
                    (radius * 2 + 20, radius * 2 + 20), pygame.SRCALPHA
                )
                pygame.draw.polygon(
                    surf,
                    fill_color,
                    [
                        (p[0] - (px - radius - 10), p[1] - (py - radius - 10))
                        for p in points
                    ],
                )

                # Add clean border using the same points (no random offset for crisp edges)
                border_points = [
                    (p[0] - (px - radius - 10), p[1] - (py - radius - 10))
                    for p in points
                ]

                # Draw border — Cocytus gets bright white border, blizzard thick cyan, default thin
                if is_cocytus:
                    border_color = (230, 248, 255, min(255, int(alpha * 0.95)))
                    border_width = 2
                elif puddle.get("blizzard"):
                    border_color = (180, 240, 255, min(255, alpha))
                    border_width = 4
                else:
                    border_color = (180, 235, 255, min(255, int(alpha * 1.1)))
                    border_width = 2
                pygame.draw.polygon(surf, border_color, border_points, border_width)

                # Add a faint semi-transparent glow around the border for blizzard
                # to soften the edges.  We draw a slightly larger polygon with low
                # alpha on top of the existing border.
                if puddle.get("blizzard"):
                    glow_color = (180, 240, 255, alpha // 6)
                    glow_width = border_width + 2
                    pygame.draw.polygon(surf, glow_color, border_points, glow_width)

                # For blizzard, also draw a faint perfect circle outline to give
                # a hint of roundness beneath the organic shape.
                if puddle.get("blizzard"):
                    pygame.draw.circle(
                        surf,
                        (180, 240, 255, alpha // 3),
                        (radius + 10, radius + 10),
                        radius,
                        1,
                    )

                g.screen.blit(surf, (int(px - radius - 10), int(py - radius - 10)))

                # Draw spiral snowflake particles for blizzard puddles
                if puddle.get("blizzard"):
                    self._draw_blizzard_spiral_particles(puddle, px, py, radius)
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def _draw_blizzard_spiral_particles(
        self, puddle: dict, px: float, py: float, radius: int
    ) -> None:
        """Draw spiral snowflake particles rotating inward inside blizzard puddles."""
        g = self.game
        try:
            from src.game_constants import (
                BLIZZARD_PARTICLE_ALIGNED_RATIO,
                BLIZZARD_PARTICLE_COUNT,
                BLIZZARD_PARTICLE_EXPANSION,
                BLIZZARD_PARTICLE_MAX_ALPHA,
                BLIZZARD_PARTICLE_S_CURVE_AMPLITUDE,
                BLIZZARD_PARTICLE_S_CURVE_RADIAL,
                BLIZZARD_PARTICLE_SIZE,
                BLIZZARD_PARTICLE_SPAWN_DELAY,
                BLIZZARD_PARTICLE_SPEED,
                BLIZZARD_PARTICLE_SPIRAL_SPEED,
            )
        except (AttributeError, TypeError, ValueError, KeyError):
            BLIZZARD_PARTICLE_COUNT = 100
            BLIZZARD_PARTICLE_SPEED = 0.5
            BLIZZARD_PARTICLE_SPIRAL_SPEED = 0.03
            BLIZZARD_PARTICLE_SIZE = 3
            BLIZZARD_PARTICLE_MAX_ALPHA = 100
            BLIZZARD_PARTICLE_SPAWN_DELAY = 2
            BLIZZARD_PARTICLE_ALIGNED_RATIO = 0.7
            BLIZZARD_PARTICLE_S_CURVE_AMPLITUDE = 0.25
            BLIZZARD_PARTICLE_S_CURVE_RADIAL = 0.15
            BLIZZARD_PARTICLE_EXPANSION = 0.35

        # Initialize particle list on first frame
        if "spiral_particles" not in puddle:
            puddle["spiral_particles"] = []
            puddle["_prev_timer"] = puddle.get("timer", 0)
            puddle["_spawn_frame"] = 0  # track frame for gradual spawning
            # Create particles but don't spawn them all at once - will spawn gradually
            max_spawn_dist = radius * 0.70

            # Determine which particles will have S-curve alignment
            num_aligned = int(BLIZZARD_PARTICLE_COUNT * BLIZZARD_PARTICLE_ALIGNED_RATIO)
            aligned_indices = set(
                random.sample(range(BLIZZARD_PARTICLE_COUNT), num_aligned)
            )

            for i in range(BLIZZARD_PARTICLE_COUNT):
                angle = (2 * math.pi * i) / BLIZZARD_PARTICLE_COUNT
                dist = max_spawn_dist * 0.85 + random.uniform(-10, 10)
                # Random color variant for each particle (white/light blue shades)
                color_variant = random.randint(0, 2)

                # Check if this particle should follow S-curve alignment
                is_aligned = i in aligned_indices

                puddle["spiral_particles"].append(
                    {
                        "angle": angle,
                        "dist": dist,
                        "spawn_dist": dist,  # track original spawn distance
                        "color_variant": color_variant,  # 0=white, 1=light_blue, 2=pale_cyan
                        "spawn_frame": i
                        * BLIZZARD_PARTICLE_SPAWN_DELAY,  # delay spawning
                        "active": False,  # not visible until spawn_frame is reached
                        "aligned": is_aligned,  # follows S-curve pattern for rotatory effect
                    }
                )

        particles = puddle["spiral_particles"]
        current_timer = puddle.get("timer", 0)
        prev_timer = puddle.get("_prev_timer", current_timer)
        time_delta = prev_timer - current_timer  # timer decreases over time
        puddle["_prev_timer"] = current_timer
        puddle["_spawn_frame"] += 1

        screen_width = g.screen.get_width()
        screen_height = g.screen.get_height()

        for particle in particles:
            # Check if particle should be active yet (gradual spawning)
            if particle["spawn_frame"] > puddle["_spawn_frame"]:
                continue  # Not yet time to spawn this particle
            particle["active"] = True
            # Update spiral animation: move inward while rotating
            particle["angle"] += time_delta * BLIZZARD_PARTICLE_SPIRAL_SPEED
            particle["dist"] -= time_delta * BLIZZARD_PARTICLE_SPEED

            angle = particle["angle"]
            dist = particle["dist"]

            # For aligned particles, apply a strong S-curve offset based on angle
            # This creates a visible wave-like pattern that emphasizes rotatory motion
            if particle.get("aligned", False):
                # Apply sine wave oscillation for rotatory S-curve effect (angular)
                angle_offset = math.sin(angle * 2) * BLIZZARD_PARTICLE_S_CURVE_AMPLITUDE
                angle += angle_offset

                # Also apply radial offset for more visible S-curve displacement
                radial_offset = math.sin(angle * 1.5) * (
                    radius * BLIZZARD_PARTICLE_S_CURVE_RADIAL
                )
                dist = dist + radial_offset

                # Apply expansion effect near respawn: particles should bulge outward as they approach center
                # This creates a "breathing" effect where particles push back out before respawning
                spawn_dist = particle.get("spawn_dist", radius * 0.70)
                normalized_dist = (
                    dist / spawn_dist if spawn_dist > 0 else 1.0
                )  # 1.0 at spawn, ~0 at center
                expansion_push = math.sin(normalized_dist * math.pi) * (
                    spawn_dist * BLIZZARD_PARTICLE_EXPANSION
                )
                dist = dist + expansion_push

            # Respawn particles that have moved too far inward (limit to 70% radius)
            max_spawn_dist = radius * 0.70
            if dist <= BLIZZARD_PARTICLE_SIZE * 2:
                particle["spawn_dist"] = max_spawn_dist * 0.85 + random.uniform(-10, 10)
                particle["dist"] = particle["spawn_dist"]
                particle["angle"] = random.uniform(0, 2 * math.pi)
                angle = particle["angle"]
                dist = particle["dist"]

            # Clamp distance to avoid going negative
            if dist < 0:
                dist = 0

            # Calculate screen position
            px_particle = px + math.cos(angle) * dist
            py_particle = py + math.sin(angle) * dist

            # Skip if particle is outside screen bounds
            if (
                px_particle < -50
                or px_particle > screen_width + 50
                or py_particle < -50
                or py_particle > screen_height + 50
            ):
                particle["spawn_dist"] = max_spawn_dist * 0.85 + random.uniform(-10, 10)
                particle["dist"] = particle["spawn_dist"]
                particle["angle"] = random.uniform(0, 2 * math.pi)
                continue

            # Skip inactive particles
            if not particle.get("active", False):
                continue

            # Fade alpha based on distance to center (closer = more transparent)
            # Use reduced alpha (max 100) for subtle effect
            distance_ratio = dist / radius if radius > 0 else 0
            particle_alpha = max(0, int(BLIZZARD_PARTICLE_MAX_ALPHA * distance_ratio))

            if particle_alpha > 5:
                # Select color based on variant (white/light_blue_violet/pale_cyan)
                color_variant = particle.get("color_variant", 0)
                if color_variant == 0:
                    # Pure white
                    color = (255, 255, 255, particle_alpha)
                elif color_variant == 1:
                    # Light blue-violet (more purple-blue)
                    color = (220, 200, 255, particle_alpha)
                else:
                    # Pale cyan (unchanged)
                    color = (180, 240, 250, particle_alpha)

                # Draw snowflake using a small SRCALPHA surface for each visible particle
                particle_size_pixels = BLIZZARD_PARTICLE_SIZE * 2 + 4
                particle_surf = pygame.Surface(
                    (particle_size_pixels, particle_size_pixels), pygame.SRCALPHA
                )

                # Draw snowflake circle
                pygame.draw.circle(
                    particle_surf,
                    color,
                    (particle_size_pixels // 2, particle_size_pixels // 2),
                    BLIZZARD_PARTICLE_SIZE,
                )

                # Add very subtle glow
                if particle_alpha > 30:
                    glow_alpha = max(0, particle_alpha // 4)
                    pygame.draw.circle(
                        particle_surf,
                        (color[0], color[1], color[2], glow_alpha),
                        (particle_size_pixels // 2, particle_size_pixels // 2),
                        BLIZZARD_PARTICLE_SIZE + 1,
                        1,
                    )

                # Blit to screen
                g.screen.blit(
                    particle_surf,
                    (
                        int(px_particle - particle_size_pixels // 2),
                        int(py_particle - particle_size_pixels // 2),
                    ),
                )

    def update_particles(self) -> None:
        """Update particle lists by removing dead particles and updating live ones."""
        g = self.game

        self.skullboom_particles = [
            p for p in g.skullboom_particles if getattr(p, "alive", True)
        ]
        for p in g.skullboom_particles:
            p.update()

        # Update blasphemy_5 particles (red revive explosion particles)
        g.blasphemy5_particles = [p for p in g.blasphemy5_particles if p.alive]
        for p in g.blasphemy5_particles:
            p.update()

        # Update ice particles
        g.ice_particles = [p for p in g.ice_particles if p.alive]
        for p in g.ice_particles:
            p.update()

        # Update Cocytus shard particles
        if getattr(g, "cocytus_particles", None):
            g.cocytus_particles = [p for p in g.cocytus_particles if p.alive]
            for p in g.cocytus_particles:
                p.update()

        # Update SkullBoom explosions
        g.skullboom_explosions = [e for e in g.skullboom_explosions if e["timer"] > 0]
        for explosion in g.skullboom_explosions:
            explosion["timer"] -= 1

        # Update ice puddles
        g.ice_puddles = [p for p in g.ice_puddles if p["timer"] > 0]
        for puddle in g.ice_puddles:
            puddle["timer"] -= 1

        # Blizzard puddles share behaviour with ice puddles but use their own list.
        # ensure they expire after the configured duration so the zone vanishes.
        if hasattr(g, "blizzard_puddles"):
            g.blizzard_puddles = [p for p in g.blizzard_puddles if p["timer"] > 0]
            for puddle in g.blizzard_puddles:
                puddle["timer"] -= 1
