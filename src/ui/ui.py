import logging
import math
import random
from typing import Any

from src.ui.effects import UIEffectsRenderer
from src.ui.menus import UIMenuSystem
from src.ui.renderer import UIGameRenderer

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
            except (AttributeError, RuntimeError):
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
                except (AttributeError, RuntimeError):
                    self._tinted_image = self.image
                    self._tinted_color = color
            try:
                surface.blit(self._tinted_image, (self.x, self.y))
            except (AttributeError, TypeError):
                surface.blit(self.image, (self.x, self.y))

    class LimboFogParticle:
        """Particle for LIMBO stages: moves vertically from bottom to top on side edges."""

        def __init__(self, ui, image, side="left"):
            self.ui = ui
            self.image = image
            self.width = image.get_width()
            self.side = side  # "left" or "right"
            self.reset(start_random=True)

        def reset(self, start_random=False):
            WIDTH = self.ui.width
            HEIGHT = self.ui.height
            from src.game_constants import (
                FOG_AMPLITUDE_RANGE,
                FOG_MAX_SPEED,
                FOG_MIN_SPEED,
                FOG_TIMER_RANGE,
            )

            # Vertical movement from bottom to top - concentrated in lower half
            # Start mostly in bottom 50% (60-100% of height) to keep particles visible longer
            if start_random:
                self.y = random.randint(int(HEIGHT * 0.6), HEIGHT)
            else:
                self.y = HEIGHT + random.randint(-50, 50)

            # Position on left or right edge with some horizontal offset
            if self.side == "left":
                self.x = random.randint(
                    -150, 100
                )  # Toward the left edge with more variation
            else:
                self.x = random.randint(
                    WIDTH - 500, WIDTH - 250
                )  # Toward the center from right with more variation

            # Reduced speeds so particles stay visible longer and accumulate in lower area
            self.speed = random.uniform(FOG_MIN_SPEED * 0.3, FOG_MAX_SPEED * 0.6)
            self.amplitude = random.uniform(*FOG_AMPLITUDE_RANGE)
            self.timer = random.uniform(*FOG_TIMER_RANGE)

        def update(self):
            # vertical upward movement
            self.y -= self.speed
            # horizontal sine-wave wobble
            self.timer += 0.02
            x_offset = math.sin(self.timer) * 0.5
            self.x += x_offset
            # reset when off top edge
            if self.y < -self.width:
                self.reset()

        def _apply_tint(self, color):
            """Pre-bake a tinted copy of the texture for the given color."""
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
            except (AttributeError, RuntimeError):
                pass
            self._tinted_image = img
            self._tinted_color = color

        def draw(self, surface):
            from src.game_constants import FOG_COLOR, PURGATORY_FOG_COLORS

            stage = getattr(self.ui.game, "selected_stage", None)

            # Choose color based on stage
            if stage == "limbo_2":
                color = (150, 180, 140)  # Greenish tint for limbo_2
            elif stage == "limbo_3":
                color = (200, 140, 100)  # Orangish tint for limbo_3
            elif stage == "limbo_final":
                color = (110, 50, 100)  # Dark purple tint for limbo_final
            else:
                color = PURGATORY_FOG_COLORS.get(stage, FOG_COLOR)

            # rebuild tinted texture only when color changes
            if getattr(self, "_tinted_color", None) != color:
                try:
                    self._apply_tint(color)
                except (AttributeError, RuntimeError):
                    self._tinted_image = self.image
                    self._tinted_color = color

            # Cache the final image (with alpha) to avoid copy+set_alpha every frame
            cache_key = (color, stage)
            if getattr(self, "_cached_draw_key", None) != cache_key:
                try:
                    img_to_draw = self._tinted_image.copy()
                    # limbo_1 (and limbo without suffix) uses slightly reduced alpha for subtlety
                    if (
                        stage == "limbo"
                        or stage is None
                        or not isinstance(stage, str)
                        or stage == "limbo_1"
                    ):
                        img_to_draw.set_alpha(int(255 * 0.7))  # 70% opacity for limbo_1
                    self._cached_draw_image = img_to_draw
                    self._cached_draw_key = cache_key
                except (AttributeError, TypeError):
                    self._cached_draw_image = self.image
                    self._cached_draw_key = cache_key

            try:
                surface.blit(self._cached_draw_image, (self.x, self.y))
            except (AttributeError, TypeError):
                surface.blit(self.image, (self.x, self.y))

    def __init__(self, game) -> None:
        try:
            import pygame

            self.pygame: Any = pygame
        except (AttributeError, TypeError, ValueError, KeyError):
            self.pygame = None
        self.game: Any = game
        self.screen: Any | None = getattr(game, "screen", None)
        self.width: Any | int = getattr(game, "width", 0)
        self.height: Any | int = getattr(game, "height", 0)

        from src.assets.text_cache import get_font, get_text

        self.get_font = get_font
        self.get_text = get_text

        # Load title image
        self.title_image = self._load_title_image()
        self._title_image_scaled = None  # Cache for scaled title image
        self._title_image_scaled_size = None  # Track cached size

        # Cache vignettes (main menu darkening strips)
        self._top_vignette = None
        self._bot_vignette = None
        self._vignette_size = None  # Track cached vignette dimensions

        # Cache overlay surface (options menu semi-transparent background)
        self._options_overlay = None
        self._options_overlay_size = None  # Track cached overlay dimensions

        self._init_fog_particles()
        self._init_limbo_fog_particles()

        # Instantiate the three subsystems for composition-based delegation
        self.menu_system = UIMenuSystem(self)
        self.renderer = UIGameRenderer(self)
        self.effects = UIEffectsRenderer(self)

    def _load_title_image(self):
        """Load the title image from assets/title.png. Returns None if not found or error occurs."""
        if not self.pygame:
            return None
        try:
            from src.assets.manager import get_image

            return get_image("title.png")
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        return None

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
        (e.g. 100 000).  We expose it separately so unit tests can verify the
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
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
            return surf
        except (AttributeError, TypeError, ValueError, KeyError):
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
        except (AttributeError, TypeError, ValueError, KeyError):
            self._fog_particles = []

    def _init_limbo_fog_particles(self) -> None:
        """Create LIMBO fog particles that move vertically from bottom to top."""
        try:
            from src.game_constants import (
                FOG_ALPHA,
                FOG_COLOR,
                FOG_TEXTURE_SIZE,
            )

            # Create texture once
            tex = self._create_fog_texture(FOG_TEXTURE_SIZE, FOG_COLOR, FOG_ALPHA)
            self._limbo_fog_particles_left: list[PygameUIManager.LimboFogParticle] = []
            self._limbo_fog_particles_right: list[PygameUIManager.LimboFogParticle] = []
            if tex:
                for _ in range(
                    12
                ):  # 12 particles per side for balance (presence without FPS hit)
                    self._limbo_fog_particles_left.append(
                        PygameUIManager.LimboFogParticle(self, tex, side="left")
                    )
                    self._limbo_fog_particles_right.append(
                        PygameUIManager.LimboFogParticle(self, tex, side="right")
                    )
            else:
                self._limbo_fog_particles_left = []
                self._limbo_fog_particles_right = []
        except (AttributeError, TypeError, ValueError, KeyError):
            self._limbo_fog_particles_left = []
            self._limbo_fog_particles_right = []

    def _update_and_draw_fog_particles_list(
        self, attr_name: str, clamp_height: bool = False
    ) -> None:
        """Helper to update and render fog particles from an attribute."""
        try:
            for p in list(getattr(self, attr_name, [])):
                p.update()
                if clamp_height and p.y + p.width > self.height * 0.50:
                    p.y = self.height * 0.50 - p.width
                if self.screen and self.pygame:
                    p.draw(self.screen)
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def _update_and_draw_limbo_fog_particles(self) -> None:
        """Update positions and render LIMBO fog particles."""
        self._update_and_draw_fog_particles_list("_limbo_fog_particles_left")
        self._update_and_draw_fog_particles_list("_limbo_fog_particles_right")

    def _update_and_draw_fog_particles(self) -> None:
        """Update positions and render all fog particles to the screen."""
        self._update_and_draw_fog_particles_list("_fog_particles", clamp_height=True)

    # ======================================================================
    # DELEGATION WRAPPERS for extracted subsystems
    # These methods delegate to specialized renderer classes for modularity
    # ======================================================================

    # --- Menu System Delegates -------------------------------------------

    def draw_main_menu(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.menu_system.draw_main_menu(shake_x, shake_y)

    def draw_profiles_menu(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.menu_system.draw_profiles_menu(shake_x, shake_y)

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
        return self.menu_system._draw_stage_submenu(
            title, labels, normal_color, hover_color, menu_key, shake_x, shake_y
        )

    def draw_stage_menu(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.menu_system.draw_stage_menu(shake_x, shake_y)

    def draw_options_menu(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.menu_system.draw_options_menu(shake_x, shake_y)

    def draw_permanent_upgrades(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.menu_system.draw_permanent_upgrades(shake_x, shake_y)

    def _draw_header_xp(self, left_x: int, shake_x: int = 0, shake_y: int = 0):
        return self.menu_system._draw_header_xp(left_x, shake_x, shake_y)

    def _draw_permanent_stats(
        self, left_x: int, shake_x: int = 0, shake_y: int = 0
    ) -> None:
        return self.menu_system._draw_permanent_stats(left_x, shake_x, shake_y)

    def _draw_blasphemies(
        self, left_x: int, separator_y: int, shake_x: int = 0, shake_y: int = 0
    ):
        return self.menu_system._draw_blasphemies(left_x, separator_y, shake_x, shake_y)

    def _draw_skill_trees(
        self, left_x: int, separator_y: int, shake_x: int = 0, shake_y: int = 0
    ) -> None:
        return self.menu_system._draw_skill_trees(left_x, separator_y, shake_x, shake_y)

    def _draw_instructions_and_sentinel(
        self, left_x: int, blasphemy_data: dict, shake_x: int = 0, shake_y: int = 0
    ) -> None:
        return self.menu_system._draw_instructions_and_sentinel(
            left_x, blasphemy_data, shake_x, shake_y
        )

    def _draw_exit_confirmation_dialog(
        self, pygame, shake_x: int = 0, shake_y: int = 0
    ) -> None:
        return self.menu_system._draw_exit_confirmation_dialog(pygame, shake_x, shake_y)

    def draw_pause_menu(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.menu_system.draw_pause_menu(shake_x, shake_y)

    def draw_pause_confirmation_dialog(
        self, shake_x: int = 0, shake_y: int = 0
    ) -> None:
        return self.menu_system.draw_pause_confirmation_dialog(shake_x, shake_y)

    # --- Game Renderer Delegates -----------------------------------------

    def _draw_floor_polygon(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.renderer._draw_floor_polygon(shake_x, shake_y)

    def _draw_walls(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.renderer._draw_walls(shake_x, shake_y)

    def _draw_torches(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.renderer._draw_torches(shake_x, shake_y)

    def _draw_limbo_lamps(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.renderer._draw_limbo_lamps(shake_x, shake_y)

    def _draw_cathedral_procedural(self, pygame, base_x: int, base_y: int) -> None:
        return self.renderer._draw_cathedral_procedural(pygame, base_x, base_y)

    def _draw_church_procedural(self, pygame, base_x: int, base_y: int) -> None:
        return self.renderer._draw_church_procedural(pygame, base_x, base_y)

    def _draw_buildings(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.renderer._draw_buildings(shake_x, shake_y)

    def _draw_battlefield_crosses(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.renderer._draw_battlefield_crosses(shake_x, shake_y)

    def draw_game_world(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.renderer.draw_game_world(shake_x, shake_y)

    def draw_player_stats(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.renderer.draw_player_stats(shake_x, shake_y)

    def draw_dead_trees(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.renderer.draw_dead_trees(shake_x, shake_y)

    def _draw_statue_model(self, x: int, statue_base_y: int, tower_type=None) -> None:
        return self.renderer._draw_statue_model(x, statue_base_y, tower_type)

    def draw_pedestals(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.renderer.draw_pedestals(shake_x, shake_y)

    def _build_fog_cache(self) -> None:
        return self.renderer._build_fog_cache()

    def draw_purgatory_fog(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.renderer.draw_purgatory_fog(shake_x, shake_y)

    def _draw_stage_overlay(
        self, cache_attr, color_attr, alpha_attr, color, alpha
    ) -> None:
        return self.renderer._draw_stage_overlay(
            cache_attr, color_attr, alpha_attr, color, alpha
        )

    def draw_fog(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.renderer.draw_fog(shake_x, shake_y)

    def draw_game_objects(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.renderer.draw_game_objects(shake_x, shake_y)

    def draw_towers(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.renderer.draw_towers(shake_x, shake_y)

    # --- Effects Renderer Delegates --------------------------------------

    def _draw_tower_energy_bar(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.effects._draw_tower_energy_bar(shake_x, shake_y)

    def draw_special_effects(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.effects.draw_special_effects(shake_x, shake_y)

    def draw_lightning_effect(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.effects.draw_lightning_effect(shake_x, shake_y)

    def draw_chain_lightning_effects(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.effects.draw_chain_lightning_effects(shake_x, shake_y)

    def _generate_lightning_path(
        self, start_x, start_y, end_x, end_y, segments=6, max_offset=8
    ):
        return self.effects._generate_lightning_path(
            start_x, start_y, end_x, end_y, segments, max_offset
        )

    def draw_hud(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.effects.draw_hud(shake_x, shake_y)

    def draw_center_messages(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.effects.draw_center_messages(shake_x, shake_y)

    def draw_fps_counter(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.effects.draw_fps_counter(shake_x, shake_y)

    def draw_prologo_end(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.effects.draw_prologo_end(shake_x, shake_y)

    def draw_weapon_selection(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.effects.draw_weapon_selection(shake_x, shake_y)

    def draw_tower_selection(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.effects.draw_tower_selection(shake_x, shake_y)

    def draw_upgrade_selection(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.effects.draw_upgrade_selection(shake_x, shake_y)

    def draw_game_over(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.effects.draw_game_over(shake_x, shake_y)

    def draw_victory(self, shake_x: int = 0, shake_y: int = 0) -> None:
        return self.effects.draw_victory(shake_x, shake_y)
