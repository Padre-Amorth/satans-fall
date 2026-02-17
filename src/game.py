import json
import logging
import math
import random
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, TypedDict

import pygame
from pygame.key import ScancodeWrapper

from src.assets.manager import get_image
from src.balance import (
    BURST_FIRE_RATE,
    BURST_MAX,
    BURST_PAUSE,
    DEFAULT_DAMAGE_REDUCTION_MULTIPLIER,
    DEFAULT_PROJECTILE_SIZE_MULTIPLIER,
    ENEMY_BASE_SPEEDS,
    GAME_OVER_FADE_DURATION_MS,
    MAX_EXTRA_WEAPONS,
    PLAYER_BASE_DAMAGE,
    PLAYER_BASE_HEALTH,
    REINFORCEMENT_COUNT,
    REINFORCEMENT_DELAY_MS,
    SPAWN_MIN_RATE,
    SPAWN_RAMP_SLOPE_POST,
    SPAWN_RAMP_SLOPE_PRE,
    SPAWN_RAMP_START_WAVE,
    STATUE_FIRE_RATE,
    XP_BASE,
    XP_GROWTH,
)
from src.core.entities.tower import Tower, TowerManager
from src.entities.enemy import BurnParticle, Enemy, IceParticle
from src.entities.player import Player
from src.game_constants import (
    DEFAULT_FPS,
    DEFAULT_HEIGHT,
    DEFAULT_PLAYER_ANIM_SPEED,
    DEFAULT_WAVE_DURATION,
    DEFAULT_WIDTH,
    STAGE_SETTINGS,
    WALL_THICKNESS,
)
from src.game_state import GameStateManager
from src.projectile import Projectile, SoulDrainProjectile
from src.systems.enemy_manager import EnemyManager
from src.ui import PygameUIManager
from src.weapons import (
    WEAPON_DEFS,
    DemonStrike_cooldown,
    beast_damage,
    get_orbital_count,
    get_weapon_definitions,
    get_weapon_upgrade_description,
    orbital_cooldown_range,
    shotgun_cooldown,
    shotgun_pellet_damage,
    shotgun_pellets,
    skull_bomb_cooldown,
    skull_bomb_damage,
    skull_bomb_explosion_radius,
    soul_drain_cd,
    soul_drain_projectile_count,
    spear_cooldown,
)


class StatConfig(TypedDict):
    name: str
    key: str
    color: tuple[int, int, int]
    y: int


if TYPE_CHECKING:
    from src.systems.projectile_manager import ProjectileManager

logger: logging.Logger = logging.getLogger(__name__)
LOG = logging.getLogger(__name__)

# Global reference to running game instance (set in Game.__init__)
CURRENT_GAME = None


class FloatingText:
    """Simple floating text for damage/feedback displayed on screen."""

    def __init__(
        self,
        text: str,
        x: float,
        y: float,
        *,
        color=(255, 255, 255),
        font_size: int = 20,
        vy: float = -1.2,
        life: int = 70,
        max_rise_pixels: int = 12,
    ):
        self.text = str(text)
        self.x = float(x)
        self.y = float(y)
        self.initial_y = float(y)
        # Maximum number of pixels the text may rise before stopping
        self.max_rise_pixels = int(max_rise_pixels)
        self.vy = float(vy)
        self.life = int(life)
        self.max_life = int(life)
        self.color = tuple(color)
        self.font_size = int(font_size)

    def update(self) -> None:
        # Move
        self.y += self.vy

        # Enforce maximum rise: do not allow the text to rise above initial_y - max_rise_pixels
        try:
            if (self.initial_y - self.y) > self.max_rise_pixels:
                # Clamp position and stop upward motion
                self.y = self.initial_y - float(self.max_rise_pixels)
                self.vy = 0.0

        except Exception:
            pass

        # While text is fading (past 60% of life), reduce movement speed smoothly
        try:
            if self.life < (self.max_life * 0.6):
                # Damp velocity toward zero so upward motion slows as it fades
                self.vy *= 0.92
                # apply a smaller upward pull to keep slight motion
                self.vy -= 0.02
            else:
                # normal upward acceleration early on
                self.vy -= 0.05
        except Exception:
            # Fallback behavior
            self.vy -= 0.03
        self.life -= 1

    @property
    def alive(self) -> bool:
        return self.life > 0

    def fade_alpha(self) -> int:
        try:
            # Slower fade due to larger max_life; just map life ratio to alpha
            return max(0, int(255 * (self.life / max(1, self.max_life))))
        except Exception:
            return 255


class Game:
    def __init__(
        self,
        fast_forward_prologo: bool = False,
        fast_forward_prologo_force_lightning: bool = False,
        debug: bool = False,
        permanent_stats_file: Optional[str | Path] = None,
    ) -> None:
        pygame.init()
        pygame.mixer.init()

        # Debug fast-forward flags (set by CLI/tests)
        self.fast_forward_prologo: bool = fast_forward_prologo
        self.fast_forward_prologo_force_lightning: bool = (
            fast_forward_prologo_force_lightning
        )
        self.fast_forward_applied = False

        # Debug flag to control debug output
        self.debug: bool = debug

        self._init_display()
        self._init_game_state()
        self._init_player()
        self._init_weapons()
        self._init_entities()
        self._init_managers(permanent_stats_file)

    def _init_display(self) -> None:
        # Virtual/internal resolution (keep `self.screen` API unchanged for UI/tests)
        self.width = DEFAULT_WIDTH
        self.height = DEFAULT_HEIGHT
        # Render target used by game/UI code
        self.screen: pygame.Surface = pygame.Surface((self.width, self.height))
        # Actual window/display surface (may be resized / fullscreen)
        self.window_width = self.width
        self.window_height = self.height
        self.window_surface: pygame.Surface = pygame.display.set_mode(
            (self.window_width, self.window_height), pygame.RESIZABLE
        )
        pygame.display.set_caption("Satan's Roguelite - Vampire Survivors Style")
        self.clock = pygame.time.Clock()
        self.running = True
        self.fps = DEFAULT_FPS
        # Fullscreen state
        self._is_fullscreen = False

    def _cached_overlay(self, use_alpha: bool = False) -> pygame.Surface:
        """Return a cached overlay surface sized to the virtual resolution (lazy-resized).
        Keeps a small per-instance cache to avoid allocating large surfaces every frame.
        """
        attr = "_overlay_alpha" if use_alpha else "_overlay"
        surf = getattr(self, attr, None)
        if surf is None or surf.get_size() != (self.width, self.height):
            flags = pygame.SRCALPHA if use_alpha else 0
            surf = pygame.Surface((self.width, self.height), flags)
            setattr(self, attr, surf)
        # Clear before reuse
        if use_alpha:
            surf.fill((0, 0, 0, 0))
        else:
            surf.fill((0, 0, 0))
        return surf

    def _init_game_state(self) -> None:
        # Early defaults to ensure robust construction even if later init fails
        self.showing_stage_menu = True
        self.showing_permanent_upgrades = False
        self.showing_prologo_end = False
        self.left_wall_points: List[tuple] = []
        self.right_wall_points: List[tuple] = []
        self.player_weapons: List[str] = []
        self._max_extra_weapons = MAX_EXTRA_WEAPONS

        # Show player stats overlay (toggle with 'I')
        self.showing_player_stats = False
        # Run-specific counters
        self.enemies_killed_this_run: int = 0

        # Pause confirmation state (None or dict with {'action': 'quit', 'selection': 0|1})
        self.pause_confirmation: dict | None = None

        # Options overlay state (opened from the main menu gear button)
        self.showing_options: bool = False
        # Options UI state: resolution dropdown open/closed
        self.options_resolution_dropdown_open: bool = False

        # Options: toggle for showing floating damage numbers
        self.show_damage_numbers: bool = True

        # Track if background image was drawn this frame
        self.background_image_drawn: bool = False

        # Persistent stats container must exist early so other init code can reference it
        self.permanent_stats: Dict[str, int] = {}
        self.projectile_manager: "ProjectileManager | None" = None

        # Centralized floating text pool for damage numbers and feedback (world coords)
        self.floating_texts: List[FloatingText] = []

        # Register self as current running game for modules that need quick access
        global CURRENT_GAME
        CURRENT_GAME = self
        # Gameplay defaults used by tests and early update paths
        self.stage_start_countdown = 0
        self.stage_start_timer = 0
        self.paused = False
        self.awaiting_upgrade = False
        self.selected_upgrade_index = 0
        self.awaiting_weapon_choice = False
        self.selected_weapon_index = 0
        self.showing_game_over = False
        self.game_over_alpha = 0
        self.game_over_fade_duration_ms = GAME_OVER_FADE_DURATION_MS
        # Calculate per-frame fade speed for game over alpha
        self.game_over_fade_speed = max(
            1, int(255 / ((self.game_over_fade_duration_ms / 1000.0) * self.fps))
        )
        self.player_xp = 0
        self.player_level = 1
        self.xp_to_next_level = XP_BASE

    def _init_weapons(self) -> None:
        # Weapon and cooldown defaults needed by weapon update logic
        self.weapon_levels: Dict[str, int] = {}
        self.burst_fire_rate = BURST_FIRE_RATE
        self.burst_cooldown = 0
        self.burst_max = BURST_MAX
        self.burst_pause = BURST_PAUSE
        self.burst_count = 0
        self.fire_rate_multiplier = 1.0
        self.hellgun_cooldown_timer = 0
        self.spear_cooldown_timer = 0
        self.DemonStrike_cooldown_timer = 0
        self.soul_drain_cooldown_timer = 0
        self.skull_bomb_cooldown_timer = 0
        # Skull bomb particles and explosion effects
        self.skull_bomb_particles: List[Any] = []
        self.skull_bomb_explosions: List[Dict[str, Any]] = []
        # Ice particles for explosions
        self.ice_particles: List[Any] = []
        # Ice puddles for slowing enemies
        self.ice_puddles: List[Dict[str, Any]] = []
        # Orbital defaults
        self.orbital_count = 3
        self.orbitals: List[Dict[str, Any]] = []

    def _init_player(self) -> None:
        # Game state
        self.player: Player = Player(self.width // 2, self.height - 80)
        self.enemies: Any = pygame.sprite.Group()
        self.projectiles: Any = pygame.sprite.Group()
        self.enemy_projectiles: Any = pygame.sprite.Group()
        self.bosses: Any = pygame.sprite.Group()

        # Allow limited vertical movement (centered on player's baseline).
        # `player_vertical_range` is the total allowed vertical span in pixels.
        # Movement is allowed only *upwards* from the starting baseline.
        self.player_vertical_range: int = 200  # user-requested default
        half_range = self.player_vertical_range // 2
        baseline_y = int(self.player.y)
        self.player_vertical_min_y = baseline_y - half_range
        # Do not allow movement below the starting baseline (max == baseline)
        self.player_vertical_max_y = baseline_y
        # Expose to player instance so `Player.update` can clamp itself without
        # changing the player.update signature used in many places.
        setattr(self.player, "vertical_min_y", self.player_vertical_min_y)
        setattr(self.player, "vertical_max_y", self.player_vertical_max_y)

        # Backwards compatibility: simple list of statue projectile dicts used by
        # older code and tests. New code also stores Projectiles in self.projectiles.
        self.statue_projectiles: list = []

        # Reinforcements
        self.reinforcement_delay_ms = REINFORCEMENT_DELAY_MS
        self.reinforcement_count = REINFORCEMENT_COUNT

        self.score = 0
        self.difficulty_multiplier = 1.0
        self.player_damage = PLAYER_BASE_DAMAGE

        # XP and Level system (already set in _init_game_state, but multipliers here)
        self.damage_multiplier = 1.0
        self.fire_rate_multiplier = 1.0
        self.projectile_size_multiplier = 1.0
        self.damage_reduction_multiplier = 1.0
        self.awaiting_upgrade = False
        self.upgrade_choices: List[Dict[str, Any]] = []
        self.selected_upgrade_index = 0
        # Weapon choice state (every 3 levels)
        self.awaiting_weapon_choice = False
        self.weapon_choices: List[Dict[str, Any]] = []
        self.selected_weapon_index = 0
        self.is_initial_weapon_choice = False
        self.player_weapons = []
        self._max_extra_weapons = MAX_EXTRA_WEAPONS
        # Base weapon progression

        # Track upgrade levels (how many times each has been taken)
        self.upgrade_levels: Dict[str, int] = {
            "damage": 0,
            "fire_rate": 0,
            "max_health": 0,
            "projectile_size": 0,
            "armor": 0,
        }

        # Weapon levels
        self.weapon_levels = {}

        # Permanent stats (meta-progression)
        # Ensure we don't overwrite loaded/persisted stats; set defaults only if missing
        self.permanent_stats.setdefault("power", 0)
        self.permanent_stats.setdefault("vigor", 0)
        self.permanent_stats.setdefault("adrenaline", 0)
        self.permanent_stats.setdefault("structure", 0)

    def _init_entities(self) -> None:
        # Frame counter for animations
        self.frame_count = 0

        # Player animation
        self.player_anim_frame = 0
        self.player_anim_timer = 0
        self.player_anim_speed = (
            DEFAULT_PLAYER_ANIM_SPEED  # frames between animation changes (slower)
        )
        self.player_is_moving = False

        # Boss system
        # State is proxied to EnemyManager when present via properties
        self._wave_boss_spawned = False

        # Prologo special events (backed by private attributes; manager may proxy)
        self._prologo_final_boss_spawned = False
        self._prologo_final_boss_defeated = False
        self._prologo_final_boss_immortal = False
        self._prologo_lightning_timer = 0
        # Duration (frames) between lightning strike start and showing ending screen.
        # Default was 180 (3s); add 2 more seconds as requested (2 * fps)
        self.prologo_lightning_duration_frames: int = 180 + 2 * self.fps
        self._prologo_lightning_strike = False
        self.lightning_points: List[tuple] = []

        # Buildings (set per stage)
        self.buildings: List[Dict[str, Any]] = []

        # Limbo features
        self.dead_trees: List[Dict[str, Any]] = []
        # Single cooldown used for both statues; toggle to alternate (left->right->left...)
        self.statue_cooldown = 0
        self.statue_next_left = True
        self.statue_fire_rate = STATUE_FIRE_RATE  # Centralized statue fire rate

        # Towers (statues) manager instances (left/right)
        self.left_tower = Tower(320, 530, fire_rate=self.statue_fire_rate)
        # record base stats so permanent modifiers can be reapplied cleanly
        self.left_tower._base_damage = self.left_tower.damage
        self.left_tower._base_fire_rate = self.left_tower.fire_rate
        self.right_tower = Tower(960, 530, fire_rate=self.statue_fire_rate)
        self.right_tower._base_damage = self.right_tower.damage
        self.right_tower._base_fire_rate = self.right_tower.fire_rate
        # Tower selection state (Purgatory)
        self.awaiting_tower_choice = False
        self.tower_choices: List[Dict[str, Any]] = []
        self.selected_tower_index = 0
        self.is_initial_tower_choice = False

        # Center messages
        self.center_messages: List[Dict[str, Any]] = []

        # Menu state (submenu for Limbo)
        self.showing_limbo_menu = False
        # Menu state (submenu for Purgatory)
        self.showing_purgatory_menu = False
        # Menu state (submenu for HELL)
        self.showing_hell_menu = False

        # Game variables
        self.wave = 0
        self.wave_time = 0.0
        self.wave_duration = DEFAULT_WAVE_DURATION  # seconds
        # Initialize spawn timer from the configured rate so the first spawn
        # doesn't occur immediately during tests or right after reset.
        self.enemy_spawn_rate = 72  # frames between spawns
        self.base_spawn_rate = 72  # base frames between spawns
        self.enemy_spawn_timer = self.enemy_spawn_rate

        # Wave ramp settings (centralized)
        self.spawn_ramp_start_wave = SPAWN_RAMP_START_WAVE
        self.spawn_ramp_slope_pre = SPAWN_RAMP_SLOPE_PRE
        self.spawn_ramp_slope_post = SPAWN_RAMP_SLOPE_POST
        self.spawn_min_rate = SPAWN_MIN_RATE

        # Spawn acceleration
        self.spawn_accel_timer = 20 * self.fps
        self.time_elapsed = 0.0

        # Enemy manager (handles pooling/spawning helpers)
        self.enemy_manager: EnemyManager | None = None
        try:
            self.enemy_manager = EnemyManager(self)
            # Keep initial rates in sync (populate manager fields)
            if hasattr(self, "enemy_spawn_rate"):
                self.enemy_manager.enemy_spawn_rate = self.enemy_spawn_rate
            if hasattr(self, "enemy_spawn_timer"):
                self.enemy_manager.enemy_spawn_timer = self.enemy_spawn_timer
        except Exception:
            self.enemy_manager = None

        # Frame counter for animations
        self.frame_count = 0

        # Player animation
        self.player_anim_frame = 0
        self.player_anim_timer = 0
        self.player_anim_speed = (
            DEFAULT_PLAYER_ANIM_SPEED  # frames between animation changes (slower)
        )
        self.player_is_moving = False

        # Boss system
        # State is proxied to EnemyManager when present via properties
        self._wave_boss_spawned = False

        # Prologo special events (backed by private attributes; manager may proxy)
        self._prologo_final_boss_spawned = False
        self._prologo_final_boss_defeated = False
        self._prologo_final_boss_immortal = False
        self._prologo_lightning_timer = 0
        # Duration (frames) between lightning strike start and showing ending screen.
        # Default was 180 (3s); add 2 more seconds as requested (2 * fps)
        self.prologo_lightning_duration_frames = 180 + 2 * self.fps
        self._prologo_lightning_strike = False
        self.lightning_points = []

        # Stage system
        self.selected_stage: Optional[str] = None
        # Default stage settings centralized in src.game_constants
        self.stage_settings: dict[str, Any] = STAGE_SETTINGS.copy()

        # Game variables
        self.wave = 0
        self.wave_time = 0.0
        self.wave_duration = DEFAULT_WAVE_DURATION  # seconds
        # Initialize spawn timer to the configured rate so gameplay doesn't
        # spawn enemies the instant the game starts during tests
        self.enemy_spawn_rate = 72  # frames between spawns
        self.base_spawn_rate = 72  # base frames between spawns
        self.enemy_spawn_timer = self.enemy_spawn_rate

        # Wave ramp settings (centralized)
        self.spawn_ramp_start_wave = SPAWN_RAMP_START_WAVE
        self.spawn_ramp_slope_pre = SPAWN_RAMP_SLOPE_PRE
        self.spawn_ramp_slope_post = SPAWN_RAMP_SLOPE_POST
        self.spawn_min_rate = SPAWN_MIN_RATE

        # Spawn acceleration
        self.spawn_accel_timer = 20 * self.fps
        self.time_elapsed = 0.0

        # Giant enemy spawning (supports manager-backed timers via properties)
        # Note: these are proxied to EnemyManager when present
        self.big_enemy_timer: int = 12 * self.fps
        self.big_enemy_fast_interval: int = 9 * self.fps
        self.big_spawned_this_wave = False

        # Initialize orbitals
        self.orbitals = []
        # Spatial grid (built on-demand in collision handler)
        self.spatial_grid: Any | None = None
        # Screen shake defaults
        self.shake_timer = 0
        self.shake_intensity = 0

        # Mouse tracking
        self.mouse_x: int = self.width // 2
        self.mouse_y: int = self.height // 2

        # Reinforcements
        self.reinforcement_delay_ms = REINFORCEMENT_DELAY_MS
        self.reinforcement_count = REINFORCEMENT_COUNT

    def _init_managers(self, permanent_stats_file: Optional[str | Path]) -> None:
        # Load assets
        self.load_assets()

        # Persistence: determine file for storing permanent stats & global progress (can be overridden in tests)
        if permanent_stats_file is not None:
            self.permanent_stats_file: Path = Path(permanent_stats_file)
        else:
            self.permanent_stats_file = (
                Path(__file__).resolve().parents[1] / "permanent_stats.json"
            )

        # Container for other persistent global progress (flexible dict of JSON-serializable values)
        self.global_progress: Dict[str, Any] = {}

        # Load persisted data if present (backwards-compatible: file may contain only a flat dict of stats)
        self.load_permanent_stats()

        # Initialize Pygame UI manager (handles drawing)
        self.ui: PygameUIManager = PygameUIManager(self)

        # Initialize GameStateManager (centralize wave/xp/upgrades/etc.)
        self.game_state: GameStateManager = GameStateManager(self)

        # Initialize ProjectileManager (handles pooling/spawn management)
        try:
            from src.systems.projectile_manager import ProjectileManager

            self.projectile_manager = ProjectileManager(self)
        except Exception:
            self.projectile_manager = None

        # Re-load persisted permanent stats after all initialization to ensure
        # any later initialization code doesn't overwrite saved values.
        try:
            self.load_permanent_stats()
        except Exception:
            pass

        # Ensure skill-tree keys exist even if persistent file was missing
        try:
            self._ensure_permanent_stat_keys()
        except Exception:
            pass

        # Final debug check to show what ended up in permanent_stats (use logger, not print)
        try:
            logger.debug(
                "Final permanent_stats after Game.__init__: %s", self.permanent_stats
            )
        except Exception:
            pass

        # Apply any persisted display preferences (window size / fullscreen)
        try:
            self.apply_display_prefs()
        except Exception:
            pass

    # Display / fullscreen helpers ------------------------------------------------
    def apply_display_prefs(self) -> None:
        """Apply persisted display preferences from self.global_progress.

        Important: on startup we DO NOT override the game's default window size
        (DEFAULT_WIDTH x DEFAULT_HEIGHT). Persisted `window_size` is still stored
        and used when the user applies a preset during runtime, but it is **not**
        auto-applied on launch. The persisted `fullscreen` flag *is* applied.
        """
        dsp = (
            self.global_progress.get("display", {})
            if getattr(self, "global_progress", None)
            else {}
        )
        if not isinstance(dsp, dict):
            return

        # Persisted `fullscreen` flag is intentionally ignored on startup —
        # fullscreen is no longer exposed as a user option.

    def set_window_size(self, w: int, h: int) -> None:
        """Programmatically set window size (updates display, exits fullscreen, and persists)."""
        self.window_width, self.window_height = int(w), int(h)
        try:
            self.window_surface = pygame.display.set_mode(
                (self.window_width, self.window_height), pygame.RESIZABLE
            )
        except Exception:
            pass
        try:
            dsp = self.global_progress.setdefault("display", {})
            dsp["window_size"] = [self.window_width, self.window_height]
            self.save_permanent_stats()
        except Exception:
            pass

    def _window_to_virtual(self, pos: tuple[int, int]) -> tuple[int, int]:
        """Convert a position in window coordinates to virtual (game) coordinates.

        This maps mouse/events coming from the OS/window (which are in the
        actual window surface pixel space) into the internal render surface
        coordinate space used by menus and game logic (`self.width` x
        `self.height`). Returns integer coordinates clamped to the virtual
        resolution.
        """
        try:
            wx, wy = int(pos[0]), int(pos[1])
        except Exception:
            return (0, 0)
        ww = max(1, getattr(self, "window_width", self.width))
        wh = max(1, getattr(self, "window_height", self.height))
        # Map proportionally on each axis
        vx = int(wx * (self.width / ww))
        vy = int(wy * (self.height / wh))
        # Clamp
        vx = max(0, min(self.width - 1, vx))
        vy = max(0, min(self.height - 1, vy))
        return (vx, vy)

    # Backwards-compatible properties to proxy timer state to EnemyManager when present
    @property
    def big_enemy_timer(self) -> int:
        if self.enemy_manager is not None:
            return self.enemy_manager.big_enemy_timer
        return getattr(self, "_big_enemy_timer", 0)

    @big_enemy_timer.setter
    def big_enemy_timer(self, val: int) -> None:
        if self.enemy_manager is not None:
            self.enemy_manager.big_enemy_timer = val
        else:
            self._big_enemy_timer = val

    @property
    def big_spawned_this_wave(self) -> bool:
        if self.enemy_manager is not None:
            return self.enemy_manager.big_spawned_this_wave
        return getattr(self, "_big_spawned_this_wave", False)

    @big_spawned_this_wave.setter
    def big_spawned_this_wave(self, val: bool) -> None:
        if self.enemy_manager is not None:
            self.enemy_manager.big_spawned_this_wave = val
        else:
            self._big_spawned_this_wave = val

    @property
    def big_enemy_fast_interval(self) -> int:
        if self.enemy_manager is not None:
            return self.enemy_manager.big_enemy_fast_interval
        return getattr(self, "_big_enemy_fast_interval", 9 * self.fps)

    @big_enemy_fast_interval.setter
    def big_enemy_fast_interval(self, val: int) -> None:
        if self.enemy_manager is not None:
            self.enemy_manager.big_enemy_fast_interval = val
        else:
            self._big_enemy_fast_interval = val

    # Wave boss flag proxy
    @property
    def wave_boss_spawned(self) -> bool:
        if self.enemy_manager is not None:
            return getattr(self.enemy_manager, "wave_boss_spawned", False)
        return getattr(self, "_wave_boss_spawned", False)

    @wave_boss_spawned.setter
    def wave_boss_spawned(self, val: bool) -> None:
        if self.enemy_manager is not None:
            self.enemy_manager.wave_boss_spawned = val
        else:
            self._wave_boss_spawned = val

    # Prologo boss / lightning proxies
    @property
    def prologo_final_boss_spawned(self) -> bool:
        if self.enemy_manager is not None:
            return getattr(self.enemy_manager, "prologo_final_boss_spawned", False)
        return getattr(self, "_prologo_final_boss_spawned", False)

    @prologo_final_boss_spawned.setter
    def prologo_final_boss_spawned(self, val: bool) -> None:
        if self.enemy_manager is not None:
            self.enemy_manager.prologo_final_boss_spawned = val
        else:
            self._prologo_final_boss_spawned = val

    @property
    def prologo_final_boss_immortal(self) -> bool:
        if self.enemy_manager is not None:
            return getattr(self.enemy_manager, "prologo_final_boss_immortal", False)
        return getattr(self, "_prologo_final_boss_immortal", False)

    @prologo_final_boss_immortal.setter
    def prologo_final_boss_immortal(self, val: bool) -> None:
        if self.enemy_manager is not None:
            self.enemy_manager.prologo_final_boss_immortal = val
        else:
            self._prologo_final_boss_immortal = val

    @property
    def prologo_lightning_strike(self) -> bool:
        if self.enemy_manager is not None:
            return getattr(self.enemy_manager, "prologo_lightning_strike", False)
        return getattr(self, "_prologo_lightning_strike", False)

    @prologo_lightning_strike.setter
    def prologo_lightning_strike(self, val: bool) -> None:
        if self.enemy_manager is not None:
            self.enemy_manager.prologo_lightning_strike = val
        else:
            self._prologo_lightning_strike = val

    @property
    def prologo_lightning_timer(self) -> int:
        if self.enemy_manager is not None:
            return getattr(self.enemy_manager, "prologo_lightning_timer", 0)
        return getattr(self, "_prologo_lightning_timer", 0)

    @prologo_lightning_timer.setter
    def prologo_lightning_timer(self, val: int) -> None:
        if self.enemy_manager is not None:
            self.enemy_manager.prologo_lightning_timer = val
        else:
            self._prologo_lightning_timer = val

    @property
    def prologo_final_boss_defeated(self) -> bool:
        if self.enemy_manager is not None:
            return getattr(self.enemy_manager, "prologo_final_boss_defeated", False)
        return getattr(self, "_prologo_final_boss_defeated", False)

    @prologo_final_boss_defeated.setter
    def prologo_final_boss_defeated(self, val: bool) -> None:
        if self.enemy_manager is not None:
            self.enemy_manager.prologo_final_boss_defeated = val
        else:
            self._prologo_final_boss_defeated = val

    @property
    def game_state(self):
        """Return `GameStateManager` if set, otherwise `self` for backwards compatibility."""
        return getattr(self, "_game_state", self)

    @game_state.setter
    def game_state(self, value):
        self._game_state = value

    @property
    def max_extra_weapons(self):
        """Max extra weapons: 3 in all stages."""
        return self._max_extra_weapons

    def load_assets(self) -> None:
        """Load game assets using the centralized `AssetManager`"""
        from src.assets.manager import get_image, preload_images

        self.assets: Dict[str, pygame.Surface | None] = {}
        asset_files: List[str] = [
            "satan.png",
            "enemy_weak.png",
            "enemy_normal.png",
            "enemy_strong.png",
            "enemy_angel.png",
            "enemy_giant.png",
            "enemy_inquisitor.png",  # optional custom sprite for non-boss inquisitor
            "boss_small.png",
            "boss_medium.png",
            "boss_big.png",
            "boss_final.png",
            "projectile.png",
            "enemy_projectile.png",
            "battlefield_cross.png",  # Bloody cross for battlefield decoration
            "limbo_battlefield.png",
        ]

        # Preload originals for quick subsequent scaling
        try:
            preload_images(asset_files)
        except Exception:
            # Preloading is best-effort; proceed even if it fails in headless/testing envs
            pass

        for asset in asset_files:
            try:
                self.assets[asset] = get_image(asset)
            except Exception:
                self.assets[asset] = None

    def generate_walls(self) -> None:
        """Generate irregular wall points for collision detection"""

        self.left_wall_points = []
        self.right_wall_points = []

        for y in range(0, self.height + 1, 20):
            progress: float = y / self.height
            # Default width per-stage (may be overridden for stage-specific behavior)
            if self.is_limbo_stage():
                width_at_y = 680 - (progress * 280)
            elif self.selected_stage and str(self.selected_stage).startswith("hell"):
                # HELL: make walls totally vertical — narrowed by 50px per side (100px total)
                width_at_y = 620.0  # 720 - 100 (50px per side)
            elif self.selected_stage and str(self.selected_stage).startswith(
                "purgatory"
            ):
                # Purgatory retains previous layout
                width_at_y = 720 - (progress * 240)
            elif self.selected_stage == "prologo":
                # Prologo: widened by 60px total (30px per side)
                width_at_y = 620 - (progress * 240)
            else:
                width_at_y = 560 - (progress * 240)

            # Irregularity creates small horizontal wobble; disable for HELL to keep walls vertical
            if self.selected_stage and str(self.selected_stage).startswith("hell"):
                irregularity = 0.0
            else:
                irregularity = math.sin(y / 80) * 5 + math.cos(y / 60) * 3
                if self.selected_stage == "prologo":
                    irregularity += math.sin(y / 35) * 2 + math.cos(y / 47) * 1

            left_x = (self.width - width_at_y) // 2 + irregularity
            right_x = (self.width + width_at_y) // 2 + irregularity

            self.left_wall_points.append((left_x, y))
            self.right_wall_points.append((right_x, y))

        # For prologue, make the bottom third of walls perfectly vertical with smooth transition
        if self.selected_stage == "prologo":
            total_points = len(self.left_wall_points)
            bottom_third_count = total_points // 3

            if bottom_third_count > 0:
                # Get the X position of the bottom-most point and make walls slightly wider in vertical section
                bottom_left_x = (
                    self.left_wall_points[-1][0] - 5
                )  # Move left wall slightly inward
                bottom_right_x = (
                    self.right_wall_points[-1][0] + 5
                )  # Move right wall slightly outward

                # Create smooth transition over the last 6 points to avoid step
                transition_points = 6
                start_transition = total_points - bottom_third_count - transition_points

                for i in range(max(0, start_transition), total_points):
                    if i >= total_points - bottom_third_count:
                        # We're in the vertical section - interpolate based on position
                        vertical_progress = (
                            i - (total_points - bottom_third_count)
                        ) / bottom_third_count
                        vertical_progress = min(1.0, max(0.0, vertical_progress))

                        # For smooth transition, blend between the curved position and vertical position
                        original_left_x = self.left_wall_points[i][0]
                        original_right_x = self.right_wall_points[i][0]

                        # The closer we get to the bottom, the more vertical we become
                        new_left_x = (
                            original_left_x
                            + (bottom_left_x - original_left_x) * vertical_progress
                        )
                        new_right_x = (
                            original_right_x
                            + (bottom_right_x - original_right_x) * vertical_progress
                        )

                        self.left_wall_points[i] = (
                            new_left_x,
                            self.left_wall_points[i][1],
                        )
                        self.right_wall_points[i] = (
                            new_right_x,
                            self.right_wall_points[i][1],
                        )

    def is_limbo_stage(self) -> bool:
        """Return True if the currently selected stage is any variant of Limbo."""
        return bool(
            self.selected_stage and str(self.selected_stage).startswith("limbo")
        )

    # --- Helpers for test compatibility ---
    def _enemies_iter(self):
        """Return a list of enemy objects regardless of underlying storage type."""
        if hasattr(self.enemies, "sprites"):
            return self.enemies.sprites()
        try:
            return list(self.enemies)
        except Exception:
            return []

    def _enemy_pos(self, e):
        """Return (x, y) for an enemy object."""
        return getattr(e, "x", 0), getattr(e, "y", 0)

    def _enemy_radius(self, e):
        """Return radius for an enemy object."""
        return getattr(e, "radius", 12)

    def _projectile_radius(self, proj: Any) -> int:
        """Return radius for a projectile object.

        - Handles Projectile instances and objects with a `rect`.
        """
        r = getattr(proj, "radius", None)
        if r is not None:
            try:
                return int(r)
            except Exception:
                pass
        rect = getattr(proj, "rect", None)
        if rect is not None:
            try:
                return int(rect.width // 2)
            except Exception:
                pass
        return 5

    def _get_projectile_metadata(self, projectile: Any) -> Dict[str, Any]:
        """Normalize commonly used projectile metadata into a dict for tests.

        Returns: { effect, slow_duration, slow_factor, burn_duration, burn_dps }
        """
        effect = getattr(projectile, "effect", None)
        slow_duration = getattr(projectile, "slow_duration", 120)
        slow_factor = getattr(projectile, "slow_factor", 0.5)
        burn_duration = getattr(projectile, "burn_duration", 180)
        burn_dps = getattr(projectile, "burn_damage_per_second", 4.0)
        # Permanent upgrade interaction (fire_2) - double burn effects
        if getattr(self, "permanent_stats", None) and self.permanent_stats.get(
            "fire_2", 0
        ):
            try:
                burn_duration = int(burn_duration * 2)
            except Exception:
                pass
            try:
                burn_dps = burn_dps * 2
            except Exception:
                pass
        return {
            "effect": effect,
            "slow_duration": slow_duration,
            "slow_factor": slow_factor,
            "burn_duration": burn_duration,
            "burn_dps": burn_dps,
        }

    def _get_hit_enemies_for_projectile(self, projectile: Any) -> list[Any]:
        """Return enemies hit by projectile (supports dict/list and Group).

        - Uses spatial_grid when available; otherwise falls back to pygame.sprite
          collision or manual list scanning.
        """
        hit_enemies: list[Any] = []
        try:
            px = float(getattr(projectile, "x", 0))
            py = float(getattr(projectile, "y", 0))
            pr = self._projectile_radius(projectile)
            sg = getattr(self, "spatial_grid", None)
            if sg is not None:
                candidates = sg.query_circle(px, py, pr)
            else:
                candidates = []
            for enemy in candidates:
                ex, ey = self._enemy_pos(enemy)
                er = self._enemy_radius(enemy)
                dx = ex - px
                dy = ey - py
                if dx * dx + dy * dy <= (pr + er) * (pr + er):
                    hit_enemies.append(enemy)
            if not hit_enemies:
                # Try pygame Group collision when possible
                if hasattr(self.enemies, "sprites") and hasattr(projectile, "rect"):
                    hit_enemies = pygame.sprite.spritecollide(
                        projectile, self.enemies, False
                    )
                else:
                    try:
                        for enemy in list(self.enemies):
                            ex, ey = self._enemy_pos(enemy)
                            er = self._enemy_radius(enemy)
                            dx = ex - px
                            dy = ey - py
                            if dx * dx + dy * dy <= (pr + er) * (pr + er):
                                hit_enemies.append(enemy)
                    except Exception:
                        hit_enemies = []
        except Exception:
            hit_enemies = []
        return hit_enemies

    def _build_spatial_grid(self) -> None:
        """Create or rebuild the SpatialGrid used by collision queries (test helper)."""
        try:
            from src.utils.spatial_grid import SpatialGrid

            enemies_iter = self._enemies_iter()
            if not hasattr(self, "spatial_grid") or self.spatial_grid is None:
                cell_size = getattr(self, "spatial_grid_cell_size", 120)
                self.spatial_grid = SpatialGrid(
                    cell_size=cell_size, width=self.width, height=self.height
                )
            try:
                self.spatial_grid.build(enemies_iter)
            except Exception:
                self.spatial_grid = None
        except Exception:
            self.spatial_grid = None

    def _remove_offscreen_projectiles(self) -> None:
        """Remove projectiles that left the screen (Group or list).

        Kept simple for tests: remove sprites whose y is offscreen and filter lists.
        """
        projs = getattr(self, "projectiles", [])
        # Group-based
        if hasattr(projs, "sprites"):
            for p in list(projs):
                try:
                    if getattr(p, "y", None) is not None and p.y < 0:
                        p.kill()
                except Exception:
                    pass
        else:
            projs = [
                p
                for p in list(projs)
                if not (getattr(p, "y", None) is not None and p.y < 0)
            ]
            self.projectiles = projs

    def _apply_ice_puddles(self):
        """Apply slowing effect from active ice puddles to nearby enemies (test helper)."""
        try:
            for puddle in getattr(self, "ice_puddles", []) or []:
                if puddle.get("timer", 0) <= 0:
                    continue
                px = float(puddle.get("x", 0))
                py = float(puddle.get("y", 0))
                pr = float(puddle.get("radius", 0))
                slow_factor = float(puddle.get("slow_factor", 0.5))
                for enemy in self._enemies_iter():
                    try:
                        ex, ey = self._enemy_pos(enemy)
                        if (ex - px) ** 2 + (ey - py) ** 2 <= pr * pr:
                            if not hasattr(enemy, "original_speed"):
                                enemy.original_speed = getattr(enemy, "speed", 0)
                            enemy.speed = enemy.original_speed * slow_factor
                            enemy.slow_factor = slow_factor
                    except Exception:
                        # ignore per-enemy errors when applying puddle slow
                        pass
                # Bosses
                try:
                    if hasattr(self, "bosses") and self.bosses:
                        bosses = (
                            self.bosses.sprites()
                            if hasattr(self.bosses, "sprites")
                            else list(self.bosses)
                        )
                        for boss in bosses:
                            bx, by = self._enemy_pos(boss)
                            if (bx - px) ** 2 + (by - py) ** 2 <= pr * pr:
                                if not hasattr(boss, "original_speed"):
                                    boss.original_speed = getattr(boss, "speed", 0)
                                boss.speed = boss.original_speed * slow_factor
                                boss.slow_factor = slow_factor
                except Exception:
                    pass
        except Exception:
            pass

    def _propagate_burn(self, source_enemy):
        """Propagate a burn from source_enemy to nearby enemies.

        - Uses propagation parameters set on the source (radius, dps, duration).
        - Applies burn to nearby enemies but does NOT schedule further propagation
          (prevents infinite chaining).
        - Handles both dict-based and sprite-based enemies.
        """
        # Support both dict-based and sprite/object-based enemies as the source.
        try:
            if isinstance(source_enemy, dict):
                radius = float(source_enemy.get("burn_propagate_radius", 0))
                dps = float(source_enemy.get("burn_propagate_dps", 0))
                duration = int(source_enemy.get("burn_propagate_duration", 0))
                source_hops = int(source_enemy.get("burn_propagate_hops", 0))
            else:
                radius = float(getattr(source_enemy, "burn_propagate_radius", 0))
                dps = float(getattr(source_enemy, "burn_propagate_dps", 0))
                duration = int(getattr(source_enemy, "burn_propagate_duration", 0))
                source_hops = int(getattr(source_enemy, "burn_propagate_hops", 0))
        except Exception:
            return

        if radius <= 0 or dps <= 0 or duration <= 0:
            return

        # Find nearby enemies and apply burn to them (excluding the source)
        for other in self._enemies_iter():
            # Skip the source itself
            if other is source_enemy:
                continue

            ox, oy = self._enemy_pos(other)
            sx, sy = self._enemy_pos(source_enemy)
            dist_sq = (ox - sx) ** 2 + (oy - sy) ** 2
            if dist_sq <= radius * radius:
                # Apply burn to dict-based enemies
                if isinstance(other, dict):
                    # only apply if not already burning
                    if other.get("burn_timer", 0) <= 0:
                        other["burn_timer"] = duration
                        other["burn_damage_per_second"] = dps
                        other["burn_tick_counter"] = getattr(self, "fps", 60)
                        # If the source has hops remaining, allow this propagated burn to
                        # further propagate when that enemy dies (chain behavior).
                        if source_hops > 0:
                            new_hops = max(0, source_hops - 1)
                            other["burn_propagate_hops"] = new_hops
                            if new_hops > 0:
                                other["burn_propagate_on_death"] = True
                                other["burn_propagate_radius"] = radius
                                other["burn_propagate_dps"] = dps
                                other["burn_propagate_duration"] = duration
                        # Spawn a small floating text to indicate propagation (best-effort)
                        try:
                            ex, ey = self._enemy_pos(other)
                            self.spawn_floating_text(
                                "burn", ex, ey - other.get("radius", 12) - 8
                            )
                        except Exception:
                            pass
                else:
                    # sprite-based enemy objects
                    if (
                        not hasattr(other, "burn_timer")
                        or getattr(other, "burn_timer", 0) <= 0
                    ):
                        other.burn_timer = duration
                        other.burn_damage_per_second = dps
                        other.burn_tick_timer = getattr(self, "fps", 60)
                        # If the source has hops remaining, allow chaining for sprite enemies too
                        if source_hops > 0:
                            new_hops = max(0, source_hops - 1)
                            try:
                                other.burn_propagate_hops = new_hops
                                if new_hops > 0:
                                    other.burn_propagate_on_death = True
                                    other.burn_propagate_radius = radius
                                    other.burn_propagate_dps = dps
                                    other.burn_propagate_duration = duration
                            except Exception:
                                pass
                        try:
                            self.spawn_floating_text(
                                "burn",
                                other.x,
                                other.y - getattr(other, "radius", 12) - 8,
                            )
                        except Exception:
                            pass
                        # Visual: orange chain from source -> target
                        try:
                            sx, sy = self._enemy_pos(source_enemy)
                            ex, ey = self._enemy_pos(other)
                            self.game_state.chain_lightning_effects.append(
                                {
                                    "points": [(sx, sy), (ex, ey)],
                                    "timer": 6,
                                    "color": (255, 140, 0),
                                }
                            )
                        except Exception:
                            pass
        # Also consider boss sprites separately (they're stored in self.bosses).
        # Bosses are sprite-based; apply the same propagation logic as above.
        if hasattr(self, "bosses") and getattr(self, "bosses", None):
            try:
                boss_list = (
                    self.bosses.sprites()
                    if hasattr(self.bosses, "sprites")
                    else list(self.bosses)
                )
                for other in boss_list:
                    # Skip source if it's the same object/dict
                    if other is source_enemy:
                        continue
                    ox, oy = self._enemy_pos(other)
                    sx, sy = self._enemy_pos(source_enemy)
                    dist_sq = (ox - sx) ** 2 + (oy - sy) ** 2
                    if dist_sq <= radius * radius:
                        # Apply burn to boss sprites (if not already burning)
                        if (
                            not hasattr(other, "burn_timer")
                            or getattr(other, "burn_timer", 0) <= 0
                        ):
                            other.burn_timer = duration
                            other.burn_damage_per_second = dps
                            other.burn_tick_timer = getattr(self, "fps", 60)
                            if source_hops > 0:
                                new_hops = max(0, source_hops - 1)
                                try:
                                    other.burn_propagate_hops = new_hops
                                    if new_hops > 0:
                                        other.burn_propagate_on_death = True
                                        other.burn_propagate_radius = radius
                                        other.burn_propagate_dps = dps
                                        other.burn_propagate_duration = duration
                                except Exception:
                                    pass
                            try:
                                self.spawn_floating_text(
                                    "burn",
                                    other.x,
                                    other.y - getattr(other, "radius", 12) - 8,
                                )
                            except Exception:
                                pass
                            # Visual: small orange chain effect boss <- source
                            try:
                                self.game_state.chain_lightning_effects.append(
                                    {
                                        "points": [(sx, sy), (ox, oy)],
                                        "timer": 6,
                                        "color": (255, 140, 0),
                                    }
                                )
                            except Exception:
                                pass
            except Exception:
                pass

    def clamp_to_walls(self, x_pos):
        """Keep position within the walls"""
        if not self.left_wall_points or not self.right_wall_points:
            return x_pos

        wall_thickness = (
            WALL_THICKNESS if self.selected_stage == "prologo" else WALL_THICKNESS
        )
        left_boundary = (
            max(point[0] for point in self.left_wall_points) + wall_thickness
        )
        right_boundary = (
            min(point[0] for point in self.right_wall_points) - wall_thickness
        )

        return max(left_boundary, min(x_pos, right_boundary))

    def random_x_between_walls(self, margin: int = 0) -> int:
        """Return a uniformly random X coordinate inside the playable walls.

        If walls are not present this falls back to a full-width random value.
        `margin` insets the returned range from the left/right walls (useful for
        reinforcements or UI elements that need a safe distance from edges).
        """
        # Fallback when walls not generated
        if not self.left_wall_points or not self.right_wall_points:
            low = max(0, margin)
            high = max(0, self.width - margin)
            return random.randint(low, high)

        wall_thickness = (
            WALL_THICKNESS if self.selected_stage == "prologo" else WALL_THICKNESS
        )
        left_boundary = int(
            max(point[0] for point in self.left_wall_points) + wall_thickness + margin
        )
        right_boundary = int(
            min(point[0] for point in self.right_wall_points) - wall_thickness - margin
        )

        # Clamp to valid screen bounds and guard against degenerate ranges
        left_boundary = max(0, left_boundary)
        right_boundary = min(self.width, right_boundary)
        if left_boundary >= right_boundary:
            # Degenerate case: fallback to clamped midpoint
            return max(left_boundary, min(left_boundary, right_boundary))

        return random.randint(left_boundary, right_boundary)

    def run(self) -> None:
        """Main game loop"""
        logger.info("Game starting...")
        while self.running:
            self.handle_events()
            self.handle_input()
            self.update()
            self.draw()
            self.clock.tick(self.fps)
        logger.info("Game ended")

    def draw(self) -> None:
        """Main draw method"""
        try:
            # Calculate screen shake
            shake_x: int = 0
            shake_y: int = 0
            if self.shake_timer > 0:
                shake_x = random.randint(-self.shake_intensity, self.shake_intensity)
                shake_y = random.randint(-self.shake_intensity, self.shake_intensity)

            # Clear screen with background color or image
            self.background_image_drawn = False
            if self.selected_stage and self.selected_stage in self.stage_settings:
                stage_settings: dict[str, Any] = self.stage_settings[
                    self.selected_stage
                ]

                # First, draw external background image if available
                bg_external_image_name = stage_settings.get("bg_image_external")
                if bg_external_image_name:
                    bg_external_image = get_image(
                        bg_external_image_name,
                        (self.screen.get_width(), self.screen.get_height()),
                    )
                    if bg_external_image:
                        self.screen.blit(bg_external_image, (0, 0))
                    else:
                        # Fallback to bg_color if image not found
                        self.screen.fill(stage_settings["bg_color"])
                else:
                    # No external background image, use bg_color
                    self.screen.fill(stage_settings["bg_color"])

                bg_image_name = stage_settings.get("bg_image")
                if bg_image_name:
                    # Calculate game area boundaries
                    if self.left_wall_points and self.right_wall_points:
                        # For prologue and Limbo, use polygon masking to fit the slanted/irregular walls
                        if self.selected_stage == "prologo" or self.is_limbo_stage():
                            inside_points = (
                                self.left_wall_points + self.right_wall_points[::-1]
                            )

                            # Calculate bounding box
                            min_x = min(p[0] for p in inside_points)
                            max_x = max(p[0] for p in inside_points)
                            min_y = min(p[1] for p in inside_points)
                            max_y = max(p[1] for p in inside_points)

                            bbox_width = max_x - min_x
                            bbox_height = max_y - min_y

                            bg_image = get_image(
                                bg_image_name, (bbox_width, bbox_height)
                            )
                            if bg_image:
                                # Don't fill with bg_color here - let external background show through

                                # Create mask from polygon
                                mask_surface = pygame.Surface(
                                    (bbox_width, bbox_height), pygame.SRCALPHA
                                )
                                mask_surface.fill((0, 0, 0, 0))  # Transparent

                                # Translate points to mask coordinates
                                translated_points = [
                                    (p[0] - min_x, p[1] - min_y) for p in inside_points
                                ]
                                pygame.draw.polygon(
                                    mask_surface,
                                    (255, 255, 255, 255),
                                    translated_points,
                                )

                                # Create mask object
                                mask = pygame.mask.from_surface(mask_surface)

                                # Create masked surface
                                masked_image = mask.to_surface(
                                    bg_image,
                                    setsurface=bg_image.copy(),
                                    unsetcolor=(0, 0, 0, 0),
                                )

                                self.screen.blit(masked_image, (min_x, min_y))
                                self.background_image_drawn = True
                            else:
                                self.screen.fill(stage_settings["bg_color"])
                        else:
                            # For other stages, use rectangular area
                            wall_thickness = WALL_THICKNESS
                            left_x = (
                                max(point[0] for point in self.left_wall_points)
                                + wall_thickness
                            )
                            right_x = (
                                min(point[0] for point in self.right_wall_points)
                                - wall_thickness
                            )
                            top_y = 0
                            bottom_y = self.screen.get_height()

                            game_area_width = right_x - left_x
                            game_area_height = bottom_y - top_y

                            bg_image = get_image(
                                bg_image_name, (game_area_width, game_area_height)
                            )
                            if bg_image:
                                self.screen.blit(bg_image, (left_x, top_y))
                                self.background_image_drawn = True
                            else:
                                self.screen.fill(stage_settings["bg_color"])
                    else:
                        # Fallback to full screen if walls not defined
                        bg_image = get_image(
                            bg_image_name,
                            (self.screen.get_width(), self.screen.get_height()),
                        )
                        if bg_image:
                            self.screen.blit(bg_image, (0, 0))
                            self.background_image_drawn = True
                        else:
                            self.screen.fill(stage_settings["bg_color"])
                else:
                    self.screen.fill(stage_settings["bg_color"])
            else:
                # Main menu background — use very-dark gray instead of bluish tone
                self.screen.fill((8, 8, 8))

            # Draw game world if in game
            if (
                self.selected_stage
                and not self.showing_stage_menu
                and not self.showing_permanent_upgrades
            ):
                self.draw_game_world(shake_x, shake_y)
                self.draw_game_objects(shake_x, shake_y)
                self.draw_skull_bomb_particles(shake_x, shake_y)
                self.draw_ice_particles(shake_x, shake_y)
                self.draw_ice_puddles(shake_x, shake_y)
                # Draw centralized floating texts (damage numbers, etc.)
                try:
                    self.draw_floating_texts(shake_x, shake_y)
                except Exception:
                    pass

            # Draw UI
            self.draw_ui(shake_x, shake_y)

            # Scale virtual surface to actual window and update display
            try:
                # Determine whether to use higher-quality smoothing
                dsp = (
                    self.global_progress.get("display", {})
                    if getattr(self, "global_progress", None)
                    else {}
                )
                smooth_pref = dsp.get("smooth_scale", None)
                # Default behavior: use smoothing when upscaling (unless user explicitly disabled)
                if smooth_pref is None:
                    use_smooth = (
                        self.window_width > self.width
                        or self.window_height > self.height
                    )
                else:
                    use_smooth = bool(smooth_pref)

                if use_smooth and hasattr(pygame.transform, "smoothscale"):
                    scaled = pygame.transform.smoothscale(
                        self.screen, (self.window_width, self.window_height)
                    )
                else:
                    scaled = pygame.transform.scale(
                        self.screen, (self.window_width, self.window_height)
                    )
                self.window_surface.blit(scaled, (0, 0))
            except Exception:
                # Fallback to direct flip if something goes wrong
                pass
            pygame.display.flip()
        except Exception as e:
            logger.exception("Error in draw method: %s", e)
            import traceback

            traceback.print_exc()

    def draw_game_world(self, shake_x=0, shake_y=0) -> None:
        """Delegate game world drawing to the Pygame UI manager."""
        if hasattr(self, "ui") and hasattr(self.ui, "draw_game_world"):
            self.ui.draw_game_world(shake_x, shake_y)
        return None

    def draw_dead_trees(self, shake_x=0, shake_y=0) -> None:
        """Delegate dead tree drawing to Pygame UI manager."""
        if hasattr(self, "ui") and hasattr(self.ui, "draw_dead_trees"):
            self.ui.draw_dead_trees(shake_x, shake_y)
        return None

    def draw_pedestals(self, shake_x=0, shake_y=0) -> None:
        """Delegate pedestal drawing to Pygame UI manager."""
        if hasattr(self, "ui") and hasattr(self.ui, "draw_pedestals"):
            self.ui.draw_pedestals(shake_x, shake_y)
        return None

    def draw_fog(self, shake_x=0, shake_y=0) -> None:
        """Delegate fog drawing to Pygame UI manager."""
        if hasattr(self, "ui") and hasattr(self.ui, "draw_fog"):
            self.ui.draw_fog(shake_x, shake_y)
        return None

    def draw_game_objects(self, shake_x=0, shake_y=0) -> None:
        """Delegate drawing of objects to the Pygame UI manager."""
        if hasattr(self, "ui") and hasattr(self.ui, "draw_game_objects"):
            self.ui.draw_game_objects(shake_x, shake_y)
        return None

    def draw_special_effects(self, shake_x=0, shake_y=0) -> None:
        """Delegate special effects to Pygame UI manager."""
        if hasattr(self, "ui") and hasattr(self.ui, "draw_special_effects"):
            self.ui.draw_special_effects(shake_x, shake_y)
        return None

    def draw_lightning_effect(self, shake_x=0, shake_y=0):
        """Delegate lightning effect drawing to Pygame UI manager."""
        if hasattr(self, "ui") and hasattr(self.ui, "draw_lightning_effect"):
            self.ui.draw_lightning_effect(shake_x, shake_y)
        return None

    def draw_spine_effect(self, shake_x=0, shake_y=0):
        """Delegate spine effect drawing to Pygame UI manager."""
        if hasattr(self, "ui") and hasattr(self.ui, "draw_spine_effect"):
            self.ui.draw_spine_effect(shake_x, shake_y)
        return None

    def draw_skull_bomb_particles(self, shake_x=0, shake_y=0) -> None:
        """Draw skull bomb explosion particles and area effects"""
        # Draw explosion area effects first (behind particles)
        if self.skull_bomb_explosions:
            try:
                for explosion in self.skull_bomb_explosions:
                    center_x = int(explosion["x"] + shake_x)
                    center_y = int(explosion["y"] + shake_y)

                    # Calculate fade based on timer
                    progress = explosion["timer"] / explosion["max_timer"]
                    alpha = int(255 * progress * 0.6)  # Max 60% opacity

                    # Draw expanding irregular ring effect instead of perfect circles
                    current_radius = int(
                        explosion["max_radius"] * (1 - progress + 0.3)
                    )  # Start small, expand

                    # Create irregular ring by drawing multiple arc segments
                    num_segments = 12  # Number of segments to create irregular shape
                    segment_angle = 2 * math.pi / num_segments

                    # Outer glow ring - irregular
                    glow_color = (255, 150, 50, alpha // 3)  # Semi-transparent orange
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
                            self.screen,
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

                    # Particles
                    for p in list(self.skull_bomb_particles):
                        try:
                            p.update()
                            # Draw as small filled circles with alpha based on life
                            surf = pygame.Surface(
                                (p.size * 2 + 2, p.size * 2 + 2), pygame.SRCALPHA
                            )
                            alpha_p = max(30, int(255 * (p.life / 40)))
                            pygame.draw.circle(
                                surf,
                                (255, 180, 80, alpha_p),
                                (p.size + 1, p.size + 1),
                                p.size,
                            )
                            self.screen.blit(
                                surf,
                                (
                                    int(p.x - p.size) + shake_x,
                                    int(p.y - p.size) + shake_y,
                                ),
                            )
                        except Exception:
                            pass
            except Exception:
                pass

    def spawn_floating_text(
        self,
        text: str,
        x: float,
        y: float,
        *,
        color=(255, 255, 255),
        font_size: int = 20,
        vy: float = -1.2,
        life: int = 70,
    ) -> None:
        """Create and register a floating text shown in world coordinates.

        Respects the user's option to show/hide damage numbers (via
        `self.show_damage_numbers`). If disabled, function is a no-op.
        """
        try:
            if not getattr(self, "show_damage_numbers", True):
                return
            ft = FloatingText(
                text, x, y, color=color, font_size=font_size, vy=vy, life=life
            )
            self.floating_texts.append(ft)
        except Exception:
            pass

    def _update_floating_texts(self) -> None:
        if not getattr(self, "floating_texts", None):
            return
        alive = []
        for ft in list(self.floating_texts):
            try:
                ft.update()
                if ft.alive:
                    alive.append(ft)
            except Exception:
                pass
        self.floating_texts = alive

    def draw_floating_texts(self, shake_x: int = 0, shake_y: int = 0) -> None:
        """Draw all floating texts to self.screen applying shake offsets."""
        if not getattr(self, "floating_texts", None):
            return
        try:
            from src.assets.text_cache import get_font, get_text
        except Exception:
            return
        try:
            for ft in list(self.floating_texts):
                try:
                    font = get_font(ft.font_size)
                    surf = get_text(ft.text, font, ft.color).copy()
                    alpha = ft.fade_alpha()
                    try:
                        surf.set_alpha(alpha)
                    except Exception:
                        pass
                    sx = int(ft.x - surf.get_width() / 2 + shake_x)
                    sy = int(ft.y + shake_y) - surf.get_height()
                    self.screen.blit(surf, (sx, sy))
                except Exception:
                    pass
        except Exception:
            pass

        # Draw particles
        if not self.skull_bomb_particles:
            return

        try:
            pass
        except Exception:
            pass

    def draw_ice_particles(self, shake_x=0, shake_y=0) -> None:
        """Draw ice explosion particles"""
        if not self.ice_particles:
            return
        try:
            for p in list(self.ice_particles):
                try:
                    # Draw as small filled circles with alpha based on life (blue-ish color for ice)
                    surf = pygame.Surface(
                        (p.size * 2 + 2, p.size * 2 + 2), pygame.SRCALPHA
                    )
                    alpha_p = max(
                        30, int(255 * (p.life / 30))
                    )  # Ice particles live up to 30 frames
                    pygame.draw.circle(
                        surf, (100, 200, 255, alpha_p), (p.size + 1, p.size + 1), p.size
                    )
                    self.screen.blit(
                        surf, (int(p.x - p.size) + shake_x, int(p.y - p.size) + shake_y)
                    )
                except Exception:
                    pass
        except Exception:
            pass

    def draw_ice_puddles(self, shake_x=0, shake_y=0) -> None:
        """Draw ice puddles that slow enemies with irregular, organic shapes"""
        if not self.ice_puddles:
            return
        try:
            for puddle in self.ice_puddles:
                px = puddle["x"] + shake_x
                py = puddle["y"] + shake_y
                radius = puddle["radius"]
                # Fade out as timer decreases
                progress = puddle["timer"] / (5 * 60)  # Max 5 seconds
                alpha = int(100 * progress)  # Max 100 alpha

                # Create irregular shape instead of perfect circle
                # Use puddle position as seed for consistent but varied shapes
                random.seed(int(px + py))

                # Generate 24-32 points around the center with varying radii for very smooth curves
                num_points = random.randint(24, 32)
                points = []

                for i in range(num_points):
                    angle = (2 * math.pi * i) / num_points
                    # Vary radius by ±8% for subtle organic variation with very smooth curves
                    radius_variation = radius * (0.92 + random.random() * 0.16)

                    x = px + math.cos(angle) * radius_variation
                    y = py + math.sin(angle) * radius_variation
                    points.append((int(x), int(y)))

                # Reset random seed to avoid affecting other random operations
                random.seed()

                # Draw irregular puddle shape
                surf = pygame.Surface(
                    (radius * 2 + 20, radius * 2 + 20), pygame.SRCALPHA
                )
                pygame.draw.polygon(
                    surf,
                    (100, 200, 255, alpha),
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

                # Draw border as a clean polygon outline
                pygame.draw.polygon(surf, (150, 220, 255, alpha // 2), border_points, 2)

                self.screen.blit(surf, (int(px - radius - 10), int(py - radius - 10)))
        except Exception:
            pass

    def add_score(self, points) -> None:
        """Add points to the game's score applying the global `score_multiplier`.

        This keeps `Game.score` and `GameStateManager.score` in sync.
        """
        try:
            mult = getattr(self, "score_multiplier", 1.0)
            amt = int(points * mult)
            self.score += amt
            try:
                if (
                    hasattr(self, "game_state")
                    and getattr(self.game_state, "score", None) is not None
                ):
                    self.game_state.score += amt
            except Exception:
                pass
        except Exception:
            pass

    def draw_ui(self, shake_x=0, shake_y=0) -> None:
        """Delegate UI drawing work to the Pygame UI manager where appropriate."""
        # Draw stage start countdown (kept here to avoid changing menu ordering)
        if self.stage_start_countdown > 0:
            font_large: pygame.Font = pygame.font.SysFont("chiller", 72)
            countdown_text: pygame.Surface = font_large.render(
                str(self.stage_start_countdown), True, (220, 180, 20)
            )
            self.screen.blit(
                countdown_text,
                (
                    self.width // 2 - countdown_text.get_width() // 2 + shake_x,
                    self.height // 2 - countdown_text.get_height() // 2 + shake_y,
                ),
            )

        # If game over is active, draw overlay and skip other UI
        if self.showing_game_over:
            self.draw_game_over(shake_x, shake_y)
            return

        # Draw HUD if in game
        if (
            self.selected_stage
            and not self.showing_stage_menu
            and not self.showing_permanent_upgrades
        ):
            self.ui.draw_hud(shake_x, shake_y)

        # Draw menus (delegated to existing Game methods to preserve behavior)
        if self.showing_stage_menu:
            self.draw_stage_menu(shake_x, shake_y)
        elif self.showing_permanent_upgrades:
            self.draw_permanent_upgrades(shake_x, shake_y)
        elif self.showing_player_stats:
            self.draw_player_stats(shake_x, shake_y)
        elif self.showing_prologo_end:
            self.draw_prologo_end(shake_x, shake_y)
        elif self.awaiting_weapon_choice:
            self.draw_weapon_selection(shake_x, shake_y)
        elif self.awaiting_tower_choice:
            self.draw_tower_selection(shake_x, shake_y)
        elif self.awaiting_upgrade:
            self.draw_upgrade_selection(shake_x, shake_y)
        elif self.paused:
            self.draw_pause_menu(shake_x, shake_y)

    def draw_hud(self, shake_x=0, shake_y=0) -> None:
        """Backward-compatible wrapper that delegates HUD drawing to UI manager."""
        if hasattr(self, "ui") and hasattr(self.ui, "draw_hud"):
            self.ui.draw_hud(shake_x, shake_y)
        return None

    def draw_center_messages(self, shake_x=0, shake_y=0) -> None:
        """Backward-compatible wrapper: delegate to UI manager's implementation."""
        if hasattr(self, "ui") and hasattr(self.ui, "draw_center_messages"):
            self.ui.draw_center_messages(shake_x, shake_y)
        return None

    def draw_stage_menu(self, shake_x=0, shake_y=0) -> None:
        """Backward-compatible wrapper: delegate stage/menu drawing to UI manager."""
        if hasattr(self, "ui") and hasattr(self.ui, "draw_stage_menu"):
            self.ui.draw_stage_menu(shake_x, shake_y)
        return None

    def draw_permanent_upgrades(self, shake_x=0, shake_y=0) -> None:
        """Backward-compatible wrapper that delegates to UI manager."""
        if hasattr(self, "ui") and hasattr(self.ui, "draw_permanent_upgrades"):
            self.ui.draw_permanent_upgrades(shake_x, shake_y)
        return None

    def _draw_permanent_upgrades_impl(self, shake_x=0, shake_y=0) -> None:
        """Draw the permanent upgrades menu"""
        font_large = pygame.font.Font(None, 36)
        font_medium = pygame.font.Font(None, 24)
        font_small = pygame.font.Font(None, 18)

        # Title
        left_x: int = self.width // 2 - 420  # moved further left

        title: pygame.Surface = font_large.render(
            "PERMANENT UPGRADES", True, (220, 180, 20)
        )
        self.screen.blit(title, (left_x + shake_x, 50 + shake_y))

        # Subtitle
        subtitle: pygame.Surface = font_small.render(
            "Upgrade your demonic powers", True, (136, 136, 136)
        )
        self.screen.blit(
            subtitle,
            (left_x + shake_x, 85 + shake_y),
        )

        # Stats display
        stat_configs: list[StatConfig] = [
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

        for stat in stat_configs:
            # Check hover for stat name
            name_rect = pygame.Rect(left_x, stat["y"], 120, 30)
            is_hovered: bool = name_rect.collidepoint(self.mouse_x, self.mouse_y)

            # Stat name (brighter if hovered and can upgrade)
            name_color: tuple[int, int, int] = stat["color"]
            if is_hovered and self.permanent_stats[stat["key"]] < 10:
                # Brighten the color when hovered (explicit 3-tuple to satisfy mypy)
                col = stat["color"]
                name_color = (
                    min(255, col[0] + 50),
                    min(255, col[1] + 50),
                    min(255, col[2] + 50),
                )
            elif self.permanent_stats[stat["key"]] >= 10:
                # Gray out if maxed
                name_color = (100, 100, 100)

            name_text: pygame.Surface = font_medium.render(
                stat["name"], True, name_color
            )
            # Slightly lower the stat name so it aligns better visually with the bar
            name_y = (
                stat["y"] + 13 + shake_y
            )  # moved down 7px total (3px up from previous)
            self.screen.blit(name_text, (left_x + shake_x, name_y))

            # Stat value
            value: int = self.permanent_stats[stat["key"]]
            value_text: pygame.Surface = font_small.render(
                f"Level: {value}", True, (255, 255, 255)
            )
            self.screen.blit(value_text, (left_x + 200 + shake_x, stat["y"] + shake_y))

            # Effect per level and total effect (e.g., "+2% per level (10% total)")
            effect_text = self.permanent_stat_effect_text(stat["key"], value)
            if effect_text:
                eff_surf: pygame.Surface = font_small.render(
                    effect_text, True, (180, 180, 180)
                )
                # Align effect text vertically with the stat bar (bar centered at stat["y"] + 15, bar_height = 12)
                eff_y = (
                    stat["y"] + 15 + (12 // 2) - (eff_surf.get_height() // 2) + shake_y
                )
                self.screen.blit(eff_surf, (left_x + 340 + shake_x, eff_y))

            # MAX indicator if at max level
            if value >= 10:
                max_text: pygame.Surface = font_small.render("MAX", True, (255, 215, 0))
                self.screen.blit(
                    max_text, (left_x + 270 + shake_x, stat["y"] + shake_y)
                )

            # Bar background
            bar_x: int = left_x + 120
            bar_y = stat["y"] + 15
            bar_width = 200
            bar_height = 12

            # Bar background (original color)
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

            # Bar fill (shows progress, currently just level-based)
            if value > 0:
                fill_width: float = min(
                    bar_width, (value / 10) * bar_width
                )  # Max 10 levels for now
                pygame.draw.rect(
                    self.screen,
                    stat["color"],
                    (bar_x + shake_x, bar_y + shake_y, fill_width, bar_height),
                )

        # Separator line
        separator_y = 320
        pygame.draw.line(
            self.screen,
            (68, 68, 68),
            (left_x + shake_x, separator_y + shake_y),
            (left_x + 430 + shake_x, separator_y + shake_y),
            2,
        )

        # Blasphemies section
        classic_text: pygame.Surface = font_medium.render(
            "BLASPHEMIES", True, (136, 136, 136)
        )
        self.screen.blit(
            classic_text,
            (
                left_x + shake_x,
                separator_y + 30 + shake_y,
            ),
        )

        # Placeholder boxes for future upgrades (2 rows of 5)
        box_width = 80  # slightly smaller
        # make boxes perfectly square
        box_height = box_width
        box_spacing = 100
        start_x: int = (
            left_x + box_spacing // 2 - 40
        )  # nudge left more (Blasphemies only)

        # First row
        box_y1: int = separator_y + 60
        # try global_progress override first, otherwise default filename
        asset_name = (
            self.global_progress.get("blasphemy_box_asset")
            if getattr(self, "global_progress", None)
            else None
        ) or "blasphemy_box.png"
        box_asset = get_image(asset_name, (box_width, box_height))

        for i in range(5):
            box_x = start_x + (i * box_spacing)
            if box_asset:
                self.screen.blit(
                    box_asset, (box_x - box_width // 2 + shake_x, box_y1 + shake_y)
                )
                pygame.draw.rect(
                    self.screen,
                    (51, 51, 51),
                    (
                        box_x - box_width // 2 + shake_x,
                        box_y1 + shake_y,
                        box_width,
                        box_height,
                    ),
                    1,
                )
            else:
                pygame.draw.rect(
                    self.screen,
                    (26, 26, 26),
                    (
                        box_x - box_width // 2 + shake_x,
                        box_y1 + shake_y,
                        box_width,
                        box_height,
                    ),
                )
                pygame.draw.rect(
                    self.screen,
                    (51, 51, 51),
                    (
                        box_x - box_width // 2 + shake_x,
                        box_y1 + shake_y,
                        box_width,
                        box_height,
                    ),
                    1,
                )

            # Show Roman numerals for top-row blasphemy boxes (multi-level)
            key = f"blasphemy_{i+1}"
            lvl = self.permanent_stats.get(key, 0)
            if lvl:
                # Show Roman numerals only (I, II, III) in a larger font
                roman_map = {1: "I", 2: "II", 3: "III"}
                roman = roman_map.get(lvl, "")
                if roman:
                    # darker red for Roman numeral inside the box (improved contrast)
                    lvl_surf = font_large.render(roman, True, (120, 20, 20))
                    sx = box_x - lvl_surf.get_width() // 2 + shake_x
                    sy = box_y1 + box_height // 2 - lvl_surf.get_height() // 2 + shake_y
                    self.screen.blit(lvl_surf, (sx, sy))

        # Second row
        box_y2: int = box_y1 + box_height + 20
        for i in range(5):
            box_x = start_x + (i * box_spacing)
            pygame.draw.rect(
                self.screen,
                (26, 26, 26),
                (
                    box_x - box_width // 2 + shake_x,
                    box_y2 + shake_y,
                    box_width,
                    box_height,
                ),
            )
            pygame.draw.rect(
                self.screen,
                (51, 51, 51),
                (
                    box_x - box_width // 2 + shake_x,
                    box_y2 + shake_y,
                    box_width,
                    box_height,
                ),
                1,
            )

        # Skill trees (three vertical columns: FIRE, STORM, ICE) on the right side
        tree_types = [
            ("FIRE", "fire", (255, 68, 68)),
            ("STORM", "storm", (170, 68, 255)),
            ("ICE", "ice", (100, 200, 255)),
        ]
        tree_box_w = 50
        tree_box_h = 36
        tree_v_spacing = 46
        tree_col_spacing = 120  # increased spacing between tree columns to reduce overlap (adjusted by +10px)
        # Move trees further right and much higher
        tree_base_x: int = left_x + 680  # moved right
        tree_top_y: int = separator_y - 150  # moved much higher

        for col_idx, (label, key_prefix, color) in enumerate(tree_types):
            col_x = tree_base_x + col_idx * tree_col_spacing
            # Title
            lbl_surf: pygame.Surface = font_small.render(label, True, color)
            self.screen.blit(
                lbl_surf,
                (
                    col_x - lbl_surf.get_width() // 2 + shake_x,
                    tree_top_y - 28 + shake_y,
                ),
            )

            # Layout: two columns of 3 (left and right) and a centered 7th box below
            # Bring inner columns very close (boxes nearly touch)
            inner_col_offset = tree_box_w // 2 + 1
            left_col_x = col_x - inner_col_offset
            right_col_x = col_x + inner_col_offset

            # Draw 3 rows for left and right columns
            for row in range(3):
                y = tree_top_y + row * tree_v_spacing
                # Left column tier index (1..3)
                left_tier = row + 1
                left_key = f"{key_prefix}_{left_tier}"
                left_active = bool(self.permanent_stats.get(left_key, 0))
                left_bg = color if left_active else (26, 26, 26)
                left_border = (
                    tuple(min(255, c + 20) for c in color)
                    if left_active
                    else (51, 51, 51)
                )
                left_rect = (
                    left_col_x - tree_box_w // 2 + shake_x,
                    y + shake_y,
                    tree_box_w,
                    tree_box_h,
                )
                pygame.draw.rect(self.screen, left_bg, left_rect)
                pygame.draw.rect(self.screen, left_border, left_rect, 1)
                # Label

                # Right column tier index (4..6)
                right_tier = 4 + row
                right_key = f"{key_prefix}_{right_tier}"
                right_active = bool(self.permanent_stats.get(right_key, 0))
                right_bg = color if right_active else (26, 26, 26)
                right_border = (
                    tuple(min(255, c + 20) for c in color)
                    if right_active
                    else (51, 51, 51)
                )
                right_rect = (
                    right_col_x - tree_box_w // 2 + shake_x,
                    y + shake_y,
                    tree_box_w,
                    tree_box_h,
                )
                pygame.draw.rect(self.screen, right_bg, right_rect)
                pygame.draw.rect(self.screen, right_border, right_rect, 1)

                # Tooltip when hovering over left or right rects
                try:
                    mouse_point = (self.mouse_x, self.mouse_y)
                except Exception:
                    mouse_point = (0, 0)

                if pygame.Rect(*left_rect).collidepoint(mouse_point):
                    tooltip_lines = self._skill_tooltip_lines(key_prefix, left_tier)
                    if tooltip_lines:
                        # Fixed tooltip position: centered under this tree column, below graphics
                        tooltip_x = col_x
                        tooltip_y = (
                            tree_top_y + 3 * tree_v_spacing + tree_box_h + 12 + shake_y
                        )
                        self._draw_tooltip(
                            tooltip_lines,
                            tooltip_x,
                            tooltip_y,
                            font_small,
                            anchor_center=True,
                        )

                if pygame.Rect(*right_rect).collidepoint(mouse_point):
                    tooltip_lines = self._skill_tooltip_lines(key_prefix, right_tier)
                    if tooltip_lines:
                        tooltip_x = col_x
                        tooltip_y = (
                            tree_top_y + 3 * tree_v_spacing + tree_box_h + 12 + shake_y
                        )
                        self._draw_tooltip(
                            tooltip_lines,
                            tooltip_x,
                            tooltip_y,
                            font_small,
                            anchor_center=True,
                        )

            # Center bottom tier (7)
            center_y = tree_top_y + 3 * tree_v_spacing
            center_key = f"{key_prefix}_7"
            center_active = bool(self.permanent_stats.get(center_key, 0))
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
            pygame.draw.rect(self.screen, center_bg, center_rect)
            pygame.draw.rect(self.screen, center_border, center_rect, 1)

            # Tooltip when hovering over center rect (tier 7)
            try:
                mouse_point = (self.mouse_x, self.mouse_y)
            except Exception:
                mouse_point = (0, 0)

            if pygame.Rect(*center_rect).collidepoint(mouse_point):
                tooltip_lines = self._skill_tooltip_lines(key_prefix, 7)
                if tooltip_lines:
                    tooltip_x = col_x
                    tooltip_y = (
                        tree_top_y + 3 * tree_v_spacing + tree_box_h + 12 + shake_y
                    )
                    self._draw_tooltip(
                        tooltip_lines,
                        tooltip_x,
                        tooltip_y,
                        font_small,
                        anchor_center=True,
                    )

        # Instructions
        instructions: pygame.Surface = font_medium.render(
            "Left click to upgrade | Right click to downgrade | ESC to return",
            True,
            (200, 200, 200),
        )
        self.screen.blit(
            instructions,
            (
                left_x + shake_x,
                self.height - 50 + shake_y,
            ),
        )

    def draw_prologo_end(self, shake_x=0, shake_y=0) -> None:
        """Draw the prologo completion screen"""
        # Create semi-transparent purple overlay
        overlay = self._cached_overlay()
        overlay.fill((40, 20, 45))  # Purple background
        overlay.set_alpha(180)  # Semi-transparent (0-255, 180 = ~70% opacity)
        self.screen.blit(overlay, (0, 0))

        font_large = pygame.font.Font(None, 48)
        font_medium = pygame.font.Font(None, 32)

        # Title
        title: pygame.Surface = font_large.render(
            "SATAN'S FALL COMPLETE", True, (255, 215, 0)
        )
        self.screen.blit(
            title,
            (
                self.width // 2 - title.get_width() // 2 + shake_x,
                self.height // 2 - 100 + shake_y,
            ),
        )

        # Message
        message1: pygame.Surface = font_medium.render(
            "You have witnessed Satan's fall from grace.", True, (255, 255, 255)
        )
        message2: pygame.Surface = font_medium.render(
            "Now face the endless torment of Limbo.", True, (255, 255, 255)
        )

        self.screen.blit(
            message1,
            (
                self.width // 2 - message1.get_width() // 2 + shake_x,
                self.height // 2 - 20 + shake_y,
            ),
        )
        self.screen.blit(
            message2,
            (
                self.width // 2 - message2.get_width() // 2 + shake_x,
                self.height // 2 + 20 + shake_y,
            ),
        )

    def draw_pause_menu(self, shake_x=0, shake_y=0) -> None:
        """Backward-compatible wrapper that delegates to UI manager."""
        if hasattr(self, "ui") and hasattr(self.ui, "draw_pause_menu"):
            if hasattr(self, "ui") and hasattr(self.ui, "draw_pause_menu"):
                self.ui.draw_pause_menu(shake_x, shake_y)
            return None
        return None

    def _draw_pause_menu_impl(self, shake_x=0, shake_y=0) -> None:
        """Draw the pause menu"""
        from src.assets.text_cache import get_font, get_text

        font_large = get_font(36)
        font_medium = get_font(28)

        # Semi-transparent overlay
        overlay = pygame.Surface((self.width, self.height))
        overlay.set_alpha(128)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        # Title
        title: pygame.Surface = get_text("PAUSED", font_large, (255, 255, 255))
        self.screen.blit(
            title,
            (
                self.width // 2 - title.get_width() // 2 + shake_x,
                self.height // 2 - 100 + shake_y,
            ),
        )

        # Options
        options: List[str] = ["Resume", "Quit to Menu"]
        option_height = 40
        for i, option in enumerate(options):
            y_pos: int = self.height // 2 - 20 + i * option_height

            # Check if mouse is hovering over this option
            # Approximate text bounds (since we don't have exact text width here)
            text_width: int = len(option) * 14  # Rough estimate
            option_rect = pygame.Rect(
                self.width // 2 - text_width // 2, y_pos, text_width, option_height
            )
            is_hovered: bool = option_rect.collidepoint(self.mouse_x, self.mouse_y)

            # Update selected option if hovered
            if is_hovered:
                self.pause_menu_option = i

            # Color based on selection or hover
            is_selected: bool = i == self.pause_menu_option
            if is_selected or is_hovered:
                color: tuple[int, int, int] = (
                    (220, 180, 20) if is_selected else (180, 160, 20)
                )
            else:
                color = (255, 255, 255)

            text = font_medium.render(option, True, color)
            self.screen.blit(
                text,
                (self.width // 2 - text.get_width() // 2 + shake_x, y_pos + shake_y),
            )

    def draw_weapon_selection(self, shake_x=0, shake_y=0) -> None:
        """Draw weapon selection screen"""
        from src.assets.text_cache import get_font, get_text

        font_large = get_font(36)
        font_medium = get_font(24)
        font_small = get_font(18)

        # Semi-transparent overlay
        overlay = pygame.Surface((self.width, self.height))
        overlay.set_alpha(80)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        # Title
        title: pygame.Surface = get_text(
            "CHOOSE YOUR WEAPON", font_large, (220, 180, 20)
        )
        self.screen.blit(
            title, (self.width // 2 - title.get_width() // 2 + shake_x, 100 + shake_y)
        )

        # Weapon options in boxes
        cx: int = self.width // 2
        box_width = 700
        box_height = 100
        spacing = 20

        # Layout Calculation
        total_height: int = (
            len(self.weapon_choices) * box_height
            + (len(self.weapon_choices) - 1) * spacing
        )
        start_y: int = self.height // 2 - total_height // 2 + 30
        x_pos: int = cx - box_width // 2

        for i, weapon in enumerate(self.weapon_choices):
            y_pos: int = start_y + i * (box_height + spacing)

            # Check if mouse is hovering over this weapon
            mouse_rect = pygame.Rect(x_pos, y_pos, box_width, box_height)
            is_hovered: bool = mouse_rect.collidepoint(self.mouse_x, self.mouse_y)

            # Update selected index if hovered
            if is_hovered:
                self.selected_weapon_index = i

            # Draw box background - highlight if selected or hovered
            is_selected: bool = i == self.selected_weapon_index
            if is_selected or is_hovered:
                box_color = (100, 100, 100) if is_selected else (75, 75, 75)
            else:
                box_color = (50, 50, 50)
            pygame.draw.rect(
                self.screen,
                box_color,
                (x_pos + shake_x, y_pos + shake_y, box_width, box_height),
            )
            pygame.draw.rect(
                self.screen,
                (150, 150, 150),
                (x_pos + shake_x, y_pos + shake_y, box_width, box_height),
                2,
            )

            # Weapon name
            name_text: pygame.Surface = font_medium.render(
                weapon["name"], True, (220, 180, 20)
            )
            self.screen.blit(name_text, (x_pos + 20 + shake_x, y_pos + 10 + shake_y))

            # Weapon description
            desc_text: pygame.Surface = font_small.render(
                weapon["description"], True, (200, 200, 200)
            )
            self.screen.blit(desc_text, (x_pos + 20 + shake_x, y_pos + 40 + shake_y))

    def draw_tower_selection(self, shake_x=0, shake_y=0) -> None:
        """Draw tower selection screen (Purgatory)."""
        from src.assets.text_cache import get_font, get_text

        font_large = get_font(36)
        font_medium = get_font(24)
        font_small = get_font(18)

        # Semi-transparent overlay
        overlay = pygame.Surface((self.width, self.height))
        overlay.set_alpha(80)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        # Title
        title: pygame.Surface = get_text(
            "CHOOSE YOUR TOWER", font_large, (220, 180, 20)
        )
        self.screen.blit(
            title, (self.width // 2 - title.get_width() // 2 + shake_x, 100 + shake_y)
        )

        # Tower options in boxes
        cx: int = self.width // 2
        box_width = 500
        box_height = 80
        spacing = 20

        # Layout Calculation
        total_height: int = (
            len(self.tower_choices) * box_height
            + (len(self.tower_choices) - 1) * spacing
        )
        start_y: int = self.height // 2 - total_height // 2 + 30
        x_pos: int = cx - box_width // 2

        for i, tower in enumerate(self.tower_choices):
            y_pos: int = start_y + i * (box_height + spacing)

            # Check if mouse is hovering over this option
            mouse_rect = pygame.Rect(x_pos, y_pos, box_width, box_height)
            is_hovered: bool = mouse_rect.collidepoint(self.mouse_x, self.mouse_y)

            # Update selected index if hovered
            if is_hovered:
                self.selected_tower_index = i

            # Draw box background - highlight if selected or hovered
            is_selected: bool = i == self.selected_tower_index
            if is_selected or is_hovered:
                box_color = (100, 100, 100) if is_selected else (75, 75, 75)
            else:
                box_color = (50, 50, 50)
            pygame.draw.rect(
                self.screen,
                box_color,
                (x_pos + shake_x, y_pos + shake_y, box_width, box_height),
            )
            pygame.draw.rect(
                self.screen,
                (150, 150, 150),
                (x_pos + shake_x, y_pos + shake_y, box_width, box_height),
                2,
            )

            # Tower name
            name_text: pygame.Surface = font_medium.render(
                tower["name"], True, (220, 180, 20)
            )
            self.screen.blit(name_text, (x_pos + 20 + shake_x, y_pos + 10 + shake_y))

            # Tower description
            desc_text: pygame.Surface = font_small.render(
                tower["description"], True, (200, 200, 200)
            )
            self.screen.blit(desc_text, (x_pos + 20 + shake_x, y_pos + 40 + shake_y))

    def _player_stats_display_items(self):
        """Return (key, value) pairs to display in the player stats sheet.

        Exclude keys related to towers/statues and elemental skill trees (fire/storm/ice).
        """
        import re

        def is_excluded(k: str) -> bool:
            if any(tok in k for tok in ("tower", "statue")):
                return True
            if re.match(r"^(fire|storm|ice)(?:_|$)", k):
                return True
            return False

        return [(k, v) for k, v in self.permanent_stats.items() if not is_excluded(k)]

    def permanent_stat_effect_text(self, key: str, level: int) -> str:
        """Return a human-friendly description of the per-level and total effect for a permanent stat."""
        if key == "power":
            per = 5.0
            total = per * level
            return f"+{per:.0f}% dmg/level ({total:.0f}% total)"
        if key == "vigor":
            per = 10
            total = per * level
            regen_per_tick = 0.5 * level
            # format regen with no trailing .0 when integer, else one decimal
            regen_str = (
                f"{regen_per_tick:.1f}"
                if regen_per_tick % 1
                else f"{int(regen_per_tick)}"
            )
            return f"+{per:d} HP/level ({total:d} HP total); +0.5 HP every 5s/level ({regen_str} HP every 5s)"
        if key == "adrenaline":
            per = 5.0
            total = per * level
            return f"+{per:.0f}% fire rate/level ({total:.0f}% total)"
        if key == "structure":
            per = 3.0
            total = per * level
            xp_total_pct = int(round(per * level))
            return f"-{per:.0f}% dmg taken/level ({total:.0f}% total); +3% XP/level (+{xp_total_pct}% XP total)"
        # Blasphemy-specific descriptions
        if key.startswith("blasphemy"):
            # Blasphemy 1: +5% damage/level
            if key == "blasphemy_1":
                per = 10.0
                total = per * level
                return f"+{per:.0f}% dmg/level ({total:.0f}% total)"
            # Blasphemy 2: +20 HP/level
            if key == "blasphemy_2":
                per = 20
                total = per * level
                return f"+{per:d} HP/level ({total:d} HP total)"
            # Blasphemy 3: +10% fire rate/level
            if key == "blasphemy_3":
                per = 10.0
                total = per * level
                return f"+{per:.0f}% fire rate/level ({total:.0f}% total)"
            # Blasphemy 4: +10% XP/level
            if key == "blasphemy_4":
                per = 10.0
                total = per * level
                return f"+{per:.0f}% XP/level ({total:.0f}% total)"
            # Other blasphemies: no per-level descriptive effect
            return ""
        return ""

    def _enforce_center_requirement(self, key_prefix: str) -> None:
        """Ensure the center tier (7) is only active when a full column of 3 exists.

        If the condition is broken, the center tier is cleared automatically.
        """
        center_key = f"{key_prefix}_7"
        left_full = all(
            self.permanent_stats.get(f"{key_prefix}_{i+1}", 0) for i in range(3)
        )
        right_full = all(
            self.permanent_stats.get(f"{key_prefix}_{4 + i}", 0) for i in range(3)
        )
        if self.permanent_stats.get(center_key, 0) and not (left_full or right_full):
            self.permanent_stats[center_key] = 0
            logger.info(
                "Clearing center tier %s because no column is fully active", center_key
            )

    def apply_permanent_stats(self) -> None:
        """Apply permanent stat effects to both game-level and player-level multipliers.

        This should be called when permanent stats change so the in-game values reflect
        the upgrades immediately (not only after reset_game()).
        """
        # Damage multiplier: 'power' gives +5% per level; blasphemy_1 gives +10% per level
        self.damage_multiplier = (
            1.0
            + (self.permanent_stats.get("power", 0) * 0.05)
            + (self.permanent_stats.get("blasphemy_1", 0) * 0.10)
        )
        # Fire rate multiplier: 'adrenaline' gives +5% per level; blasphemy_3 gives +10% per level
        self.fire_rate_multiplier = (
            1.0
            + (self.permanent_stats.get("adrenaline", 0) * 0.05)
            + (self.permanent_stats.get("blasphemy_3", 0) * 0.10)
        )
        # Apply other effects for consistency
        self.projectile_size_multiplier = 1.0 + (
            self.permanent_stats.get("projectile_size", 0) * 0.0
        )
        # STRUCTURE: now -3% damage taken per level and +3% XP gained per level
        self.damage_reduction_multiplier = 1.0 - (
            self.permanent_stats.get("structure", 0) * 0.03
        )
        # XP multiplier used whenever the game awards XP to the player (default 1.0)
        # Include blasphemy_4 which grants +10% XP per level
        self.xp_multiplier = (
            1.0
            + (self.permanent_stats.get("structure", 0) * 0.03)
            + (self.permanent_stats.get("blasphemy_4", 0) * 0.10)
        )

        # Ensure the player object also reflects the new multipliers
        try:
            self.player.damage_multiplier = self.damage_multiplier
            self.player.fire_rate_multiplier = self.fire_rate_multiplier
            self.player.projectile_size_multiplier = self.projectile_size_multiplier
            self.player.damage_reduction_multiplier = self.damage_reduction_multiplier
            # Ensure player's max health reflects VIGOR + Blasphemy 2 (+20 HP per level)
            try:
                self.player.max_health = (
                    PLAYER_BASE_HEALTH
                    + (self.permanent_stats.get("vigor", 0) * 10)
                    + (self.permanent_stats.get("blasphemy_2", 0) * 20)
                )
                if getattr(self.player, "health", 0) > self.player.max_health:
                    self.player.health = self.player.max_health
            except Exception:
                pass
        except Exception:
            pass

        # Enforce center-tier requirements for all trees after applying
        for prefix in ("fire", "storm", "ice"):
            self._enforce_center_requirement(prefix)

        # --- Apply skill-tree effects for towers/statues (right-column tiers 4..6) ---
        # Right-column slots (4..6) give +10% damage and +10% fire rate per active slot.
        self.tower_damage_multiplier = {"fire": 1.0, "storm": 1.0, "ice": 1.0}
        self.tower_fire_rate_multiplier = {"fire": 1.0, "storm": 1.0, "ice": 1.0}
        # Precompute left-column special effects for certain trees (e.g. STORM chain bonus)
        # Slot-specific weights: storm_1 and storm_3 grant +2 chain targets each; storm_2 provides a
        # special effect (chain-kill lightning explosion) and does NOT increase chain count.
        storm_left_count = (
            2 * self.permanent_stats.get("storm_1", 0)
            + 0 * self.permanent_stats.get("storm_2", 0)
            + 2 * self.permanent_stats.get("storm_3", 0)
        )

        for prefix in ("fire", "storm", "ice"):
            right_count = sum(
                self.permanent_stats.get(f"{prefix}_{i}", 0) for i in (4, 5, 6)
            )
            # ICE right-column grants +20% damage per active slot; FIRE remains +10%
            if prefix == "ice":
                dmg_mult = 1.0 + (right_count * 0.20)
            else:
                dmg_mult = 1.0 + (right_count * 0.10)
            # STORM right-column grants +20% fire rate per active slot (damage handled above)
            if prefix == "storm":
                fr_mult = 1.0 + (right_count * 0.20)
            else:
                fr_mult = 1.0 + (right_count * 0.10)
            self.tower_damage_multiplier[prefix] = dmg_mult
            self.tower_fire_rate_multiplier[prefix] = fr_mult

            # Apply to existing tower instances (left/right) when types match
            for t in (
                getattr(self, "left_tower", None),
                getattr(self, "right_tower", None),
            ):
                if t is None:
                    continue
                if getattr(t, "tower_type", None) != prefix:
                    continue
                # ensure base values are recorded once
                if not hasattr(t, "_base_damage"):
                    t._base_damage = t.damage
                if not hasattr(t, "_base_fire_rate"):
                    t._base_fire_rate = t.fire_rate
                # Record base chain_targets for storm towers so upgrades can stack from a known baseline
                if prefix == "storm" and not hasattr(t, "_base_chain_targets"):
                    t._base_chain_targets = getattr(t, "chain_targets", 3)
                # Apply multipliers (damage scales up; fire_rate is cooldown so divide by multiplier)
                t.damage = int(round(t._base_damage * dmg_mult))
                t.fire_rate = max(1, int(round(t._base_fire_rate / fr_mult)))

                # Apply STORM left-column chain bonus (+1 chain target per active left-slot)
                if prefix == "storm":
                    extra_chain = storm_left_count
                    t.chain_targets = getattr(t, "_base_chain_targets", 3) + extra_chain

                # Apply ICE left-column area damage effect (ice_1: projectiles deal area damage)
                if prefix == "ice" and self.permanent_stats.get("ice_1", 0):
                    t.explosion_radius = 60  # Area damage radius for ice projectiles
                    # Apply ICE_2 upgrade: +50% to both puddle radius and explosion radius
                    if self.permanent_stats.get("ice_2", 0):
                        t.explosion_radius = int(60 * 1.5)  # 90

    def _player_damage_vs_burning(self, projectile, enemy, base_damage: int) -> int:
        """Return adjusted damage for player projectiles against burning enemies.

        Applies when `fire_3` permanent is active and the *source* of the projectile
        is the player (not a statue/tower or enemy). Returns an int.
        """
        try:
            # Only consider non-enemy projectiles that are not from statues
            is_player_proj = (
                not getattr(projectile, "is_enemy_projectile", False)
            ) and (getattr(projectile, "source", None) != "statue")
            if not is_player_proj:
                return base_damage
            if not self.permanent_stats.get("fire_3", 0):
                return base_damage
            # Check whether the target is burning
            if getattr(enemy, "burn_timer", 0) > 0:
                return int(round(base_damage * 1.25))
        except Exception:
            pass
        return base_damage

    def _skill_tooltip_lines(self, key_prefix: str, tier: int) -> list:
        """Return list of text lines to show in a tooltip for a given skill tree tier.

        This includes Title, Status (Unlocked/Locked), and the requirement string.
        """

        # Show an effect description where available. For right-column
        # skill tiers (4..6) we display the per-slot effect that applies to towers/statues.
        lines: list[str] = []

        # Right-column tiers (4-6) grant tower/statue bonuses per active slot.
        if tier in (4, 5, 6):
            # ICE: +20% damage per slot; STORM: +20% fire rate per slot; FIRE: +10% dmg & +10% FR
            if key_prefix == "storm":
                lines.append("+10% dmg, +20% fire rate")
            elif key_prefix == "ice":
                lines.append("+20% dmg, +10% fire rate")
            else:
                lines.append("+10% dmg, +10% fire rate")
        else:
            # Special text for FIRE left-column tier 1: burn propagation
            if key_prefix == "fire" and tier == 1:
                lines.append("Burn spreads to nearby enemies on death (chains up to 2)")
            # FIRE left-column tier 2: double burn duration and burn DPS
            elif key_prefix == "fire" and tier == 2:
                lines.append("Burn duration ×2; burn DPS ×2")
            # FIRE left-column tier 3: bonus vs burning enemies
            elif key_prefix == "fire" and tier == 3:
                lines.append("+25% damage to burning enemies")
            # STORM left-column tiers (1..3): tier-specific effects
            elif key_prefix == "storm" and tier in (1, 2, 3):
                if tier == 1:
                    lines.append("Chain lightning +2 targets")
                elif tier == 2:
                    lines.append(
                        "Chain-kills trigger lightning explosion — damages nearby enemies"
                    )
                else:  # tier == 3
                    lines.append("Chain lightning +2 targets")
            # ICE left-column tier 1: area damage and slow
            elif key_prefix == "ice" and tier == 1:
                lines.append("Projectiles deal area damage and create slowing puddles")
            # ICE left-column tier 2: increased area
            elif key_prefix == "ice" and tier == 2:
                lines.append("+50% puddle area and area damage radius")
            # ICE left-column tier 3: piercing projectiles
            elif key_prefix == "ice" and tier == 3:
                lines.append(
                    "Projectiles pierce through enemies, slowing all hit targets"
                )
            else:
                # Keep a generic placeholder for other tiers (keeps UI compact)
                lines.append("")

        return lines

    def _draw_tooltip(
        self,
        lines: list,
        x: int,
        y: int,
        font: pygame.font.Font,
        anchor_center: bool = False,
    ) -> None:
        """Render a small tooltip box with given lines.

        If anchor_center is True, x is treated as the center x coordinate (tooltip will be centered on it);
        otherwise x and y represent the top-left corner as before.
        """
        padding_x = 8
        padding_y = 6
        line_surfs = [font.render(line, True, (255, 255, 255)) for line in lines]
        width = max(s.get_width() for s in line_surfs) + padding_x * 2
        height = (
            sum(s.get_height() for s in line_surfs)
            + padding_y * 2
            + (len(line_surfs) - 1) * 4
        )
        # Compute top-left coordinates
        if anchor_center:
            tx = int(x - width // 2)
        else:
            tx = x
        ty = y
        # Ensure tooltip stays inside screen bounds
        tx = max(4, min(tx, self.width - width - 4))
        ty = max(4, min(ty, self.height - height - 4))
        # Background
        bg_rect = pygame.Rect(tx, ty, width, height)
        pygame.draw.rect(self.screen, (30, 30, 30), bg_rect)
        pygame.draw.rect(self.screen, (120, 120, 120), bg_rect, 1)
        # Blit lines
        cur_y = ty + padding_y
        for s in line_surfs:
            self.screen.blit(s, (tx + padding_x, cur_y))
            cur_y += s.get_height() + 4

    def draw_player_stats(self, shake_x=0, shake_y=0) -> None:
        """Backward-compatible wrapper that delegates to UI manager."""
        if hasattr(self, "ui") and hasattr(self.ui, "draw_player_stats"):
            if hasattr(self, "ui") and hasattr(self.ui, "draw_player_stats"):
                self.ui.draw_player_stats(shake_x, shake_y)
            return None
        return None

    def _draw_player_stats_impl(self, shake_x=0, shake_y=0) -> None:
        """Draw a player stats sheet overlay showing current stats and progress."""
        from src.assets.text_cache import get_font, get_text

        font_huge = get_font(36)
        font_large = get_font(28)
        font_medium = get_font(20)
        font_small = get_font(16)

        # Overlay
        overlay = self._cached_overlay()
        overlay.set_alpha(200)
        overlay.fill((10, 10, 10))
        self.screen.blit(overlay, (0, 0))

        title = get_text("PLAYER STATS", font_huge, (255, 215, 0))
        self.screen.blit(
            title, (self.width // 2 - title.get_width() // 2 + shake_x, 40 + shake_y)
        )

        left_col_x = self.width // 2 - 420 + shake_x
        mid_col_x = self.width // 2 - 80 + shake_x
        right_col_x = self.width // 2 + 260 + shake_x
        start_y = 100 + shake_y
        line_h = 28

        # Core info
        core_lines = [
            ("Level", str(self.player_level)),
            ("XP", f"{int(self.player_xp)}/{int(self.xp_to_next_level)}"),
            ("Score", str(int(self.score))),
            ("Damage %", f"{(self.damage_multiplier - 1.0) * 100:.0f}%"),
            ("Fire rate %", f"{(1.0 - self.fire_rate_multiplier) * -100:.0f}%"),
            (
                "Projectile size %",
                f"{(self.projectile_size_multiplier - 1.0) * 100:.0f}%",
            ),
            (
                "Damage reduction %",
                f"{(1.0 - self.damage_reduction_multiplier) * 100:.0f}%",
            ),
        ]

        for i, (label, val) in enumerate(core_lines):
            y = start_y + i * line_h
            lab = get_text(f"{label}:", font_medium, (200, 200, 200))
            val_s = get_text(val, font_medium, (255, 255, 255))
            self.screen.blit(lab, (left_col_x, y))
            self.screen.blit(val_s, (left_col_x + 160, y))

        # Health
        y = start_y + len(core_lines) * line_h + 10
        health_label = get_text("Health:", font_medium, (200, 200, 200))
        health_val = get_text(
            f"{int(self.player.health)}/{int(self.player.max_health)}",
            font_medium,
            (255, 255, 255),
        )
        self.screen.blit(health_label, (left_col_x, y))
        self.screen.blit(health_val, (left_col_x + 160, y))

        # Weapons and levels
        w_y = start_y
        self.screen.blit(
            get_text("Weapons", font_large, (255, 215, 0)), (mid_col_x, w_y - 30)
        )
        for i, wid in enumerate(self.player_weapons):
            lvl = self.weapon_levels.get(wid, 0)
            name = WEAPON_DEFS.get(wid, {}).get("name", wid.replace("_", " ").title())
            txt = get_text(f"{name} Lv{lvl}", font_medium, (220, 220, 220))
            self.screen.blit(txt, (mid_col_x, w_y + i * line_h))

        # Upgrade levels
        u_y = start_y
        self.screen.blit(
            get_text("Upgrades", font_large, (255, 215, 0)), (right_col_x, u_y - 30)
        )
        for i, (k, v) in enumerate(self.upgrade_levels.items()):
            txt = get_text(f"{k}: {v}", font_medium, (220, 220, 220))
            self.screen.blit(txt, (right_col_x, u_y + i * line_h))

        # Permanent stats (excluding tower/statue and elemental keys)
        ps_y = u_y + len(self.upgrade_levels) * line_h + 20
        self.screen.blit(
            get_text("Permanent Stats", font_large, (255, 215, 0)),
            (right_col_x, ps_y - 30),
        )
        display_stats = self._player_stats_display_items()
        for i, (k, v) in enumerate(display_stats):
            txt = get_text(f"{k}: {v}", font_small, (200, 200, 200))
            self.screen.blit(txt, (right_col_x, ps_y + i * (line_h - 6)))

        # Close instructions (Tab instead of I)
        inst = get_text("Press Tab or ESC to close", font_small, (180, 180, 180))
        self.screen.blit(
            inst,
            (
                self.width // 2 - inst.get_width() // 2 + shake_x,
                self.height - 50 + shake_y,
            ),
        )

    def draw_upgrade_selection(self, shake_x=0, shake_y=0) -> None:
        """Draw upgrade selection screen"""
        from src.assets.text_cache import get_font, get_text

        font_large = get_font(36)
        font_medium = get_font(24)
        font_small = get_font(18)

        # Semi-transparent overlay
        overlay = pygame.Surface((self.width, self.height))
        overlay.set_alpha(128)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        # Title
        title: pygame.Surface = get_text(
            "LEVEL UP - CHOOSE UPGRADE", font_large, (220, 180, 20)
        )
        self.screen.blit(
            title, (self.width // 2 - title.get_width() // 2 + shake_x, 100 + shake_y)
        )

        # Upgrade options in boxes
        cx: int = self.width // 2
        box_width = 700
        box_height = 100
        spacing = 20
        total_height: int = (
            len(self.upgrade_choices) * box_height
            + (len(self.upgrade_choices) - 1) * spacing
        )
        start_y: int = self.height // 2 - total_height // 2 + 30
        x_pos: int = cx - box_width // 2

        for i, upgrade in enumerate(self.upgrade_choices):
            y_pos: int = start_y + i * (box_height + spacing)

            # Check if mouse is hovering over this upgrade
            mouse_rect = pygame.Rect(x_pos, y_pos, box_width, box_height)
            is_hovered: bool = mouse_rect.collidepoint(self.mouse_x, self.mouse_y)

            # Update selected index if hovered
            if is_hovered:
                self.selected_upgrade_index = i

            # Draw box background - highlight if selected or hovered
            is_selected: bool = i == self.selected_upgrade_index
            if is_selected or is_hovered:
                box_color = (100, 100, 100) if is_selected else (75, 75, 75)
            else:
                box_color = (50, 50, 50)
            pygame.draw.rect(
                self.screen,
                box_color,
                (x_pos + shake_x, y_pos + shake_y, box_width, box_height),
            )
            pygame.draw.rect(
                self.screen,
                (150, 150, 150),
                (x_pos + shake_x, y_pos + shake_y, box_width, box_height),
                2,
            )

            # Upgrade name
            name_text: pygame.Surface = font_medium.render(
                upgrade["name"], True, (220, 180, 20)
            )
            self.screen.blit(name_text, (x_pos + 20 + shake_x, y_pos + 10 + shake_y))

            # Upgrade description
            desc_text: pygame.Surface = font_small.render(
                upgrade["description"], True, (200, 200, 200)
            )
            self.screen.blit(desc_text, (x_pos + 20 + shake_x, y_pos + 40 + shake_y))

    def handle_events(self) -> None:
        for event in pygame.event.get():
            # Explicitly ignore mouse wheel events globally to prevent accidental scrolling
            if event.type == pygame.MOUSEWHEEL:
                # Intentionally do nothing (ignore)
                continue
            if event.type == pygame.QUIT:
                logger.info("[EVENT] QUIT received")
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self.handle_keydown(event.key)
            elif event.type == pygame.MOUSEMOTION:
                # Convert window coords to virtual coords so hover logic uses the
                # same coordinate space as UI drawing (self.width x self.height).
                self.mouse_x, self.mouse_y = self._window_to_virtual(event.pos)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # Map incoming (window) mouse click position to virtual coords
                virt_pos = self._window_to_virtual(event.pos)
                self.handle_mouse_click(virt_pos, event.button)
            elif event.type == pygame.VIDEORESIZE:
                # Window resized by user/OS — update actual window surface (virtual surface unchanged)
                self.window_width, self.window_height = event.w, event.h
                try:
                    self.window_surface = pygame.display.set_mode(
                        (self.window_width, self.window_height), pygame.RESIZABLE
                    )
                except Exception:
                    pass
                try:
                    self.global_progress.setdefault("display", {})["window_size"] = [
                        self.window_width,
                        self.window_height,
                    ]
                    self.save_permanent_stats()
                except Exception:
                    pass
            elif event.type == pygame.USEREVENT + 1:
                logger.info("[EVENT] USEREVENT+1 (reinforcements) fired")
                # Reinforcement timer event
                self.spawn_reinforcements()
                # Clear the timer after firing
                pygame.time.set_timer(pygame.USEREVENT + 1, 0)
            elif event.type == pygame.USEREVENT + 2:
                # USEREVENT+2 is used to return to menu after various timed events.
                # If the game over overlay is active, ignore timer-based returns so the
                # user must press Enter/Esc to proceed.
                logger.info("[EVENT] USEREVENT+2 fired")
                if self.showing_game_over:
                    logger.info(
                        "USEREVENT+2 ignored because game over overlay is active"
                    )
                    # Clear any stray timer so it doesn't keep firing
                    pygame.time.set_timer(pygame.USEREVENT + 2, 0)
                else:
                    logger.info("USEREVENT+2 handling: returning to menu")
                    self.show_stage_menu()
                    pygame.time.set_timer(pygame.USEREVENT + 2, 0)

        # Final load to ensure persistent stats survive any later init code
        try:
            self.load_permanent_stats()
        except Exception:
            pass

    def handle_keydown(self, key):
        # If a pause confirmation dialog is active, it takes absolute precedence
        if getattr(self, "pause_confirmation", None):
            # Toggle selection (0 = Yes, 1 = No)
            if key == pygame.K_LEFT or key == pygame.K_UP:
                self.pause_confirmation["selection"] = max(
                    0, self.pause_confirmation["selection"] - 1
                )
                return
            elif key == pygame.K_RIGHT or key == pygame.K_DOWN:
                self.pause_confirmation["selection"] = min(
                    1, self.pause_confirmation["selection"] + 1
                )
                return
            elif key == pygame.K_RETURN or key == pygame.K_SPACE or key == pygame.K_y:
                # Confirm
                if self.pause_confirmation["selection"] == 0:
                    action = self.pause_confirmation["action"]
                    self.pause_confirmation = None
                    if action == "quit":
                        self.reset_game()
                else:
                    # Cancel
                    self.pause_confirmation = None
                return
            elif key == pygame.K_n or key == pygame.K_ESCAPE:
                # Explicit cancel
                self.pause_confirmation = None
                return

        if self.showing_stage_menu:
            if key == pygame.K_p:
                self.select_stage("prologo")
            elif key == pygame.K_l:
                # Open the Limbo second menu (keyboard shortcut)
                self.showing_limbo_menu = True
            elif key == pygame.K_g:
                # Open the Purgatory second menu (keyboard shortcut)
                self.showing_purgatory_menu = True
            elif key == pygame.K_ESCAPE:
                # Close any open submenu
                if self.showing_limbo_menu:
                    self.showing_limbo_menu = False
                elif self.showing_purgatory_menu:
                    self.showing_purgatory_menu = False
                elif self.showing_hell_menu:
                    self.showing_hell_menu = False
            elif key == pygame.K_u:
                self.show_permanent_upgrades()
        elif self.showing_permanent_upgrades:
            if key == pygame.K_ESCAPE:
                self.show_stage_menu()
        elif self.showing_prologo_end:
            if key == pygame.K_RETURN:
                self.continue_to_limbo()
            elif key == pygame.K_ESCAPE:
                self.reset_game()
        elif self.showing_stage_menu and self.showing_limbo_menu:
            if key == pygame.K_ESCAPE:
                self.showing_limbo_menu = False
        elif self.showing_stage_menu and self.showing_purgatory_menu:
            if key == pygame.K_ESCAPE:
                self.showing_purgatory_menu = False
        elif self.showing_stage_menu and self.showing_hell_menu:
            if key == pygame.K_ESCAPE:
                self.showing_hell_menu = False
        elif self.showing_game_over:
            # When the game-over overlay is active:
            # Restart disabled: ignore Enter/Space, ESC returns to the main menu.
            if key == pygame.K_RETURN or key == pygame.K_SPACE:
                # Restart is disabled — ignore Enter/Space
                return
            elif key == pygame.K_ESCAPE:
                logger.info("Escape pressed on game over screen; returning to menu")
                self.show_stage_menu()
        elif self.showing_player_stats:
            # Close stats overlay with ESC or Tab
            if key == pygame.K_ESCAPE or key == pygame.K_TAB:
                self.showing_player_stats = False
                self.paused = False
        elif self.awaiting_weapon_choice:
            if key == pygame.K_1 and len(self.weapon_choices) > 0:
                self.apply_weapon(self.weapon_choices[0]["id"])
        elif self.awaiting_tower_choice:
            if key == pygame.K_1 and len(self.tower_choices) > 0:
                self.apply_tower(self.tower_choices[0]["id"])
            elif key == pygame.K_2 and len(self.tower_choices) > 1:
                self.apply_tower(self.tower_choices[1]["id"])
            elif key == pygame.K_3 and len(self.tower_choices) > 2:
                self.apply_tower(self.tower_choices[2]["id"])
            elif key == pygame.K_UP:
                self.selected_tower_index = max(0, self.selected_tower_index - 1)
                try:
                    self.game_state.tower_choice_index = self.selected_tower_index
                except Exception:
                    pass
            elif key == pygame.K_DOWN:
                self.selected_tower_index = min(
                    max(0, len(self.tower_choices) - 1), self.selected_tower_index + 1
                )
                try:
                    self.game_state.tower_choice_index = self.selected_tower_index
                except Exception:
                    pass
            elif key == pygame.K_RETURN or key == pygame.K_SPACE:
                self.apply_tower(self.tower_choices[self.selected_tower_index]["id"])
            elif key == pygame.K_ESCAPE and not self.is_initial_tower_choice:
                # Cancel tower selection and resume
                self.awaiting_tower_choice = False
                self.paused = False
                try:
                    self.game_state.awaiting_tower_choice = False
                except Exception:
                    pass
        # Close limbo submenu with ESC
        elif self.showing_stage_menu and self.showing_limbo_menu:
            if key == pygame.K_ESCAPE:
                self.showing_limbo_menu = False

            elif key == pygame.K_2 and len(self.weapon_choices) > 1:
                self.apply_weapon(self.weapon_choices[1]["id"])
            elif key == pygame.K_3 and len(self.weapon_choices) > 2:
                self.apply_weapon(self.weapon_choices[2]["id"])
            elif key == pygame.K_UP:
                self.selected_weapon_index: int = max(0, self.selected_weapon_index - 1)
                # Keep GameStateManager in sync so UI highlights update
                try:
                    self.game_state.selected_weapon_index = self.selected_weapon_index
                except Exception:
                    pass
            elif key == pygame.K_DOWN:
                self.selected_weapon_index: int = min(
                    max(0, len(self.weapon_choices) - 1), self.selected_weapon_index + 1
                )
                try:
                    self.game_state.selected_weapon_index = self.selected_weapon_index
                except Exception:
                    pass
            elif key == pygame.K_RETURN or key == pygame.K_SPACE:
                self.apply_weapon(self.weapon_choices[self.selected_weapon_index]["id"])
            elif key == pygame.K_ESCAPE and not self.is_initial_weapon_choice:
                # Cancel weapon selection and resume game (only for non-initial choices)
                self.awaiting_weapon_choice = False
                self.paused = False
                try:
                    self.game_state.awaiting_weapon_choice = False
                except Exception:
                    pass
        elif self.awaiting_upgrade:
            # Allow selection only via hotkeys 1-3 or direct mouse click. Arrow navigation
            # and Enter/Space confirmation are intentionally disabled.
            if key == pygame.K_1 and len(self.upgrade_choices) > 0:
                self.apply_upgrade(self.upgrade_choices[0])
            elif key == pygame.K_2 and len(self.upgrade_choices) > 1:
                self.apply_upgrade(self.upgrade_choices[1])
            elif key == pygame.K_3 and len(self.upgrade_choices) > 2:
                self.apply_upgrade(self.upgrade_choices[2])
            elif key == pygame.K_ESCAPE:
                # Cancel upgrade selection and resume game
                self.awaiting_upgrade = False
                self.paused = False
                try:
                    self.game_state.awaiting_upgrade = False
                except Exception:
                    pass
        # Confirmation dialog handling (takes precedence when active)
        elif self.pause_confirmation:
            # Toggle selection (0 = Yes, 1 = No)
            if key == pygame.K_LEFT or key == pygame.K_UP:
                self.pause_confirmation["selection"] = max(
                    0, self.pause_confirmation["selection"] - 1
                )
            elif key == pygame.K_RIGHT or key == pygame.K_DOWN:
                self.pause_confirmation["selection"] = min(
                    1, self.pause_confirmation["selection"] + 1
                )
            elif key == pygame.K_RETURN or key == pygame.K_SPACE or key == pygame.K_y:
                # Confirm
                if self.pause_confirmation["selection"] == 0:
                    action = self.pause_confirmation["action"]
                    self.pause_confirmation = None
                    if action == "quit":
                        self.reset_game()
                else:
                    # Cancel
                    self.pause_confirmation = None
            elif key == pygame.K_n or key == pygame.K_ESCAPE:
                # Explicit cancel
                self.pause_confirmation = None
        elif self.paused:
            if key == pygame.K_UP or key == pygame.K_w:
                self.pause_menu_option = max(0, self.pause_menu_option - 1)
            elif key == pygame.K_DOWN or key == pygame.K_s:
                self.pause_menu_option = min(1, self.pause_menu_option + 1)
            elif key == pygame.K_RETURN or key == pygame.K_SPACE:
                self.execute_pause_option()
        else:
            if key == pygame.K_ESCAPE:
                self.toggle_pause()
            if key == pygame.K_TAB:
                # Toggle player stats overlay when in-game
                self.showing_player_stats = not self.showing_player_stats
                # Pause game while viewing stats
                self.paused = self.showing_player_stats

    def handle_mouse_click(self, pos, button=1):
        """Handle mouse clicks in menus

        Mouse wheel buttons are ignored to prevent accidental menu selection.
        """
        try:
            # Ignore mouse wheel buttons (4/5) globally
            if button in (4, 5):
                return

            # If a pause confirmation dialog is active, allow Yes/No to be clicked
            if getattr(self, "pause_confirmation", None):
                dialog_w, dialog_h = 260, 70
                dx = self.width // 2 - dialog_w // 2
                # Align dialog click area with UI; accept legacy +20 layout as well
                dy_base = self.height // 2 - dialog_h // 2
                # Button regions: smaller buttons (match UI) with padding
                btn_w = 80
                btn_h = 28
                # Accept both the current and the legacy vertical offsets so tests
                # relying on different layouts remain stable.
                for dy in (dy_base, dy_base + 20):
                    yes_rect = pygame.Rect(dx + 10, dy + 30, btn_w, btn_h)
                    no_rect = pygame.Rect(
                        dx + dialog_w - btn_w - 10, dy + 30, btn_w, btn_h
                    )
                    if yes_rect.collidepoint(pos):
                        # Confirm Yes
                        action = self.pause_confirmation["action"]
                        self.pause_confirmation = None
                        if action == "quit":
                            self.reset_game()
                        return
                    elif no_rect.collidepoint(pos):
                        # Cancel (No)
                        self.pause_confirmation = None
                        return

            if self.showing_stage_menu:
                # Check stage selection buttons
                prologo_rect = pygame.Rect(
                    self.width // 2 - 100, self.height // 2 - 50, 200, 40
                )
                limbo_rect = pygame.Rect(
                    self.width // 2 - 100, self.height // 2 + 10, 200, 40
                )
                purgatory_rect = pygame.Rect(
                    self.width // 2 - 100, self.height // 2 + 70, 200, 40
                )
                hell_rect = pygame.Rect(
                    self.width // 2 - 100, self.height // 2 + 130, 200, 40
                )

                # If options overlay is open, check for clicks on its controls
                if getattr(self, "showing_options", False):
                    dialog_w, dialog_h = 520, 320
                    dx = self.width // 2 - dialog_w // 2
                    dy = self.height // 2 - dialog_h // 2

                    # Damage numbers toggle rect (compact right-aligned)
                    toggle_w, toggle_h = 48, 24
                    toggle_x = dx + dialog_w - 24 - toggle_w
                    toggle_y = dy + 64
                    toggle_rect = pygame.Rect(toggle_x, toggle_y, toggle_w, toggle_h)
                    if toggle_rect.collidepoint(pos):
                        # Toggle option
                        try:
                            self.show_damage_numbers = not self.show_damage_numbers
                        except Exception:
                            pass
                        return

                    # Smooth-scaling toggle (moved up after removing fullscreen option)
                    smooth_toggle_x = dx + dialog_w - 24 - toggle_w
                    smooth_toggle_y = dy + 104
                    smooth_toggle_rect = pygame.Rect(
                        smooth_toggle_x, smooth_toggle_y, toggle_w, toggle_h
                    )
                    if smooth_toggle_rect.collidepoint(pos):
                        try:
                            dsp = self.global_progress.setdefault("display", {})
                            dsp["smooth_scale"] = not dsp.get("smooth_scale", True)
                            self.save_permanent_stats()
                        except Exception:
                            pass
                        return

                    # Resolution presets dropdown
                    try:
                        from src.game_constants import DEFAULT_DISPLAY_PRESETS
                    except Exception:
                        DEFAULT_DISPLAY_PRESETS = [(1280, 720)]
                    btn_w, btn_h = 140, 28
                    start_x = dx + 24
                    btn_y = dy + 248
                    dropdown_x, dropdown_y = start_x, btn_y
                    dropdown_w, dropdown_h = btn_w, btn_h

                    # Click the dropdown header to open/close
                    dropdown_rect = pygame.Rect(
                        dropdown_x, dropdown_y, dropdown_w, dropdown_h
                    )
                    if dropdown_rect.collidepoint(pos):
                        self.options_resolution_dropdown_open = not getattr(
                            self, "options_resolution_dropdown_open", False
                        )
                        return

                    # If dropdown is open, check for selection clicks
                    if getattr(self, "options_resolution_dropdown_open", False):
                        item_h = 24
                        item_spacing = 2
                        for i, (pw, ph) in enumerate(DEFAULT_DISPLAY_PRESETS):
                            iy = dropdown_y + dropdown_h + i * (item_h + item_spacing)
                            item_rect = pygame.Rect(dropdown_x, iy, dropdown_w, item_h)
                            if item_rect.collidepoint(pos):
                                try:
                                    self.set_window_size(pw, ph)
                                except Exception:
                                    pass
                                self.options_resolution_dropdown_open = False
                                return
                        # Click outside items will close the dropdown (fall through)
                        return

                    close_rect = pygame.Rect(
                        dx + (dialog_w - 120) // 2, dy + dialog_h - 50, 120, 36
                    )
                    if close_rect.collidepoint(pos):
                        self.showing_options = False
                        return
                    # ignore other clicks while options overlay open
                    return
                # Upgrades button moved to bottom of screen to avoid overlap and be more accessible
                upgrades_rect = pygame.Rect(
                    self.width // 2 - 125, max(20, self.height - 80), 250, 35
                )

                if self.showing_limbo_menu:
                    # Coordinates should match draw_stage_menu limbo layout
                    option_w = 320
                    option_h = 48
                    start_x: int = self.width // 2 - option_w // 2
                    start_y: int = self.height // 2 - 40
                    spacing = 60

                    limbo1_rect = pygame.Rect(start_x, start_y, option_w, option_h)
                    limbo2_rect = pygame.Rect(
                        start_x, start_y + spacing, option_w, option_h
                    )
                    limbo3_rect = pygame.Rect(
                        start_x, start_y + spacing * 2, option_w, option_h
                    )
                    back_rect = pygame.Rect(
                        self.width // 2 - 60, start_y + spacing * 3 + 10, 120, 36
                    )

                    if limbo1_rect.collidepoint(pos):
                        self.showing_limbo_menu = False
                        self.select_stage("limbo")
                        return
                    elif limbo2_rect.collidepoint(pos):
                        self.showing_limbo_menu = False
                        self.select_stage("limbo_2")
                        return
                    elif limbo3_rect.collidepoint(pos):
                        self.showing_limbo_menu = False
                        self.select_stage("limbo_3")
                        return
                    elif back_rect.collidepoint(pos):
                        self.showing_limbo_menu = False
                        return

                if self.showing_purgatory_menu:
                    option_w = 320
                    option_h = 48
                    start_x: int = self.width // 2 - option_w // 2
                    start_y: int = self.height // 2 - 40
                    spacing = 60

                    purg1_rect = pygame.Rect(start_x, start_y, option_w, option_h)
                    purg2_rect = pygame.Rect(
                        start_x, start_y + spacing, option_w, option_h
                    )
                    purg3_rect = pygame.Rect(
                        start_x, start_y + spacing * 2, option_w, option_h
                    )
                    purg_back_rect = pygame.Rect(
                        self.width // 2 - 60, start_y + spacing * 3 + 10, 120, 36
                    )

                    if purg1_rect.collidepoint(pos):
                        self.select_stage("purgatory")
                        self.showing_purgatory_menu = False
                        return
                    elif purg2_rect.collidepoint(pos):
                        self.select_stage("purgatory_2")
                        self.showing_purgatory_menu = False
                        return
                    elif purg3_rect.collidepoint(pos):
                        self.select_stage("purgatory_3")
                        self.showing_purgatory_menu = False
                        return
                    elif purg_back_rect.collidepoint(pos):
                        self.showing_purgatory_menu = False
                        return
                    # Defensive logging in case user reports that submenu doesn't show
                    logger.debug(
                        "Purgatory submenu click handling: purgatory_menu=%s, pos=%s",
                        self.showing_purgatory_menu,
                        pos,
                    )

                if self.showing_hell_menu:
                    option_w = 320
                    option_h = 48
                    start_x: int = self.width // 2 - option_w // 2
                    start_y: int = self.height // 2 - 40
                    spacing = 60

                    hell1_rect = pygame.Rect(start_x, start_y, option_w, option_h)
                    hell2_rect = pygame.Rect(
                        start_x, start_y + spacing, option_w, option_h
                    )
                    hell3_rect = pygame.Rect(
                        start_x, start_y + spacing * 2, option_w, option_h
                    )
                    hell_back_rect = pygame.Rect(
                        self.width // 2 - 60, start_y + spacing * 3 + 10, 120, 36
                    )

                    if hell1_rect.collidepoint(pos):
                        self.select_stage("hell")
                        self.showing_hell_menu = False
                        return
                    elif hell2_rect.collidepoint(pos):
                        self.select_stage("hell_2")
                        self.showing_hell_menu = False
                        return
                    elif hell3_rect.collidepoint(pos):
                        self.select_stage("hell_3")
                        self.showing_hell_menu = False
                        return
                    elif hell_back_rect.collidepoint(pos):
                        self.showing_hell_menu = False
                        return
                    logger.debug(
                        "HELL submenu click handling: hell_menu=%s, pos=%s",
                        self.showing_hell_menu,
                        pos,
                    )

                # If no submenu handled the click, proceed to main menu handling
                if prologo_rect.collidepoint(pos):
                    self.select_stage("prologo")
                elif limbo_rect.collidepoint(pos):
                    # Open the limbo submenu (second menu)
                    self.showing_limbo_menu = True
                elif purgatory_rect.collidepoint(pos):
                    # Open the purgatory submenu (second menu)
                    logger.debug("Mouse click: opening Purgatory submenu")
                    self.showing_purgatory_menu = True
                    self.showing_limbo_menu = False
                    self.showing_hell_menu = False
                    # Keep stage menu visible while showing submenu
                    self.showing_stage_menu = True
                elif hell_rect.collidepoint(pos):
                    # Open the HELL submenu (second menu)
                    logger.debug("Mouse click: opening HELL submenu")
                    self.showing_hell_menu = True
                    self.showing_limbo_menu = False
                    self.showing_purgatory_menu = False
                    # Keep stage menu visible while showing submenu
                    self.showing_stage_menu = True
                elif upgrades_rect.collidepoint(pos):
                    self.show_permanent_upgrades()
                # Options (gear) button bottom-right
                options_rect = pygame.Rect(
                    self.width - 54, max(20, self.height - 54), 40, 40
                )
                if options_rect.collidepoint(pos):
                    # Only open options from main stage menu
                    self.showing_options = True
                    return
            elif self.showing_permanent_upgrades:
                # Handle clicks on permanent stat upgrades
                stat_configs = [
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

                # Use same left offset as drawing code so clicks line up with text
                left_x = self.width // 2 - 420
                for stat in stat_configs:
                    # Check if click is on the stat name area
                    name_rect = pygame.Rect(left_x, stat["y"], 120, 30)
                    if name_rect.collidepoint(pos):
                        if (
                            button == 1 and self.permanent_stats[stat["key"]] < 10
                        ):  # Left click to upgrade
                            self.permanent_stats[stat["key"]] += 1
                            # Persist the change immediately
                            self.save_permanent_stats()
                            # Apply changes immediately in-game
                            self.apply_permanent_stats()
                            self.show_centered_message(
                                f"{stat['name']} upgraded to level {self.permanent_stats[stat['key']]}!",
                                120,
                                stat["color"],
                                24,
                            )
                        elif (
                            button == 3 and self.permanent_stats[stat["key"]] > 0
                        ):  # Right click to downgrade
                            self.permanent_stats[stat["key"]] -= 1
                            self.save_permanent_stats()
                            self.apply_permanent_stats()
                            self.show_centered_message(
                                f"{stat['name']} downgraded to level {self.permanent_stats[stat['key']]}!",
                                120,
                                stat["color"],
                                24,
                            )
                        return

                # --- Blasphemies grid (two rows of 5) click handling ---
                # Coordinates mirror the drawing code so clicks line up with boxes
                box_width = 80
                box_height = 60
                box_spacing = 100
                start_x = left_x + box_spacing // 2 - 40
                separator_y = 320
                box_y1 = separator_y + 60

                # Top row (1..5)
                for i in range(5):
                    box_x = start_x + (i * box_spacing)
                    rect = pygame.Rect(
                        box_x - box_width // 2, box_y1, box_width, box_height
                    )
                    key = f"blasphemy_{i+1}"
                    if rect.collidepoint(pos):
                        # Treat blasphemy slots 1..4 as multi-level (0..3); others toggle
                        if key in (
                            "blasphemy_1",
                            "blasphemy_2",
                            "blasphemy_3",
                            "blasphemy_4",
                        ):
                            if button == 1 and self.permanent_stats.get(key, 0) < 3:
                                self.permanent_stats[key] = (
                                    self.permanent_stats.get(key, 0) + 1
                                )
                                self.save_permanent_stats()
                                self.apply_permanent_stats()
                                self.show_centered_message(
                                    f"Blasphemy {i+1} upgraded to level {self.permanent_stats[key]}!",
                                    100,
                                    (200, 80, 80),
                                    20,
                                )
                            elif button == 3 and self.permanent_stats.get(key, 0) > 0:
                                self.permanent_stats[key] = (
                                    self.permanent_stats.get(key, 0) - 1
                                )
                                self.save_permanent_stats()
                                self.apply_permanent_stats()
                                self.show_centered_message(
                                    f"Blasphemy {i+1} downgraded to level {self.permanent_stats[key]}!",
                                    100,
                                    (200, 80, 80),
                                    20,
                                )
                        else:
                            # Other blasphemy slots toggle on/off (boolean)
                            if button == 1 and not self.permanent_stats.get(key, 0):
                                self.permanent_stats[key] = 1
                                self.save_permanent_stats()
                                self.apply_permanent_stats()
                                self.show_centered_message(
                                    f"Blasphemy {i+1} unlocked!",
                                    100,
                                    (200, 80, 80),
                                    20,
                                )
                            elif button == 3 and self.permanent_stats.get(key, 0):
                                self.permanent_stats[key] = 0
                                self.save_permanent_stats()
                                self.apply_permanent_stats()
                                self.show_centered_message(
                                    f"Blasphemy {i+1} locked!",
                                    100,
                                    (200, 80, 80),
                                    20,
                                )
                        return

                # Second row (6..10)
                box_y2 = box_y1 + box_height + 20
                for i in range(5):
                    box_x = start_x + (i * box_spacing)
                    rect = pygame.Rect(
                        box_x - box_width // 2, box_y2, box_width, box_height
                    )
                    key = f"blasphemy_{6 + i}"
                    if rect.collidepoint(pos):
                        if button == 1 and not self.permanent_stats.get(key, 0):
                            self.permanent_stats[key] = 1
                            self.save_permanent_stats()
                            self.apply_permanent_stats()
                            self.show_centered_message(
                                f"Blasphemy {6 + i} unlocked!",
                                100,
                                (200, 80, 80),
                                20,
                            )
                        elif button == 3 and self.permanent_stats.get(key, 0):
                            self.permanent_stats[key] = 0
                            self.save_permanent_stats()
                            self.apply_permanent_stats()
                            self.show_centered_message(
                                f"Blasphemy {6 + i} locked!",
                                100,
                                (200, 80, 80),
                                20,
                            )
                        return

                # Handle clicks on the 3 skill trees on the right side
                tree_types = [
                    ("FIRE", "fire", (255, 68, 68)),
                    ("STORM", "storm", (170, 68, 255)),
                    ("ICE", "ice", (100, 200, 255)),
                ]
                tree_box_w = 50
                tree_box_h = 36
                tree_v_spacing = 46
                tree_col_spacing = 120
                # Compute same left anchor used for drawing
                left_x = self.width // 2 - 420
                tree_base_x: int = left_x + 680  # moved right to match drawing
                tree_top_y: int = 320 - 150  # moved much higher to match drawing

                for col_idx, (label, key_prefix, color) in enumerate(tree_types):
                    col_x = tree_base_x + col_idx * tree_col_spacing
                    # Bring inner columns very close (boxes nearly touch)
                    inner_col_offset = tree_box_w // 2 + 1
                    left_col_x = col_x - inner_col_offset
                    right_col_x = col_x + inner_col_offset

                    # check left and right 3x2 grid
                    for row in range(3):
                        y = tree_top_y + row * tree_v_spacing
                        # left tier
                        left_tier = row + 1
                        left_key = f"{key_prefix}_{left_tier}"
                        left_rect = pygame.Rect(
                            left_col_x - tree_box_w // 2, y, tree_box_w, tree_box_h
                        )
                        if left_rect.collidepoint(pos):
                            if button == 1:
                                prev_ok = (
                                    True
                                    if left_tier == 1
                                    else all(
                                        self.permanent_stats.get(
                                            f"{key_prefix}_{i+1}", 0
                                        )
                                        for i in range(left_tier - 1)
                                    )
                                )
                                if (
                                    not self.permanent_stats.get(left_key, 0)
                                    and prev_ok
                                ):
                                    self.permanent_stats[left_key] = 1
                                    self.save_permanent_stats()
                                    self.show_centered_message(
                                        f"{label} tier {left_tier} unlocked!",
                                        120,
                                        color,
                                        20,
                                    )
                            elif button == 3:
                                if self.permanent_stats.get(left_key, 0):
                                    # clear this and any higher tiers in left column
                                    for r2 in range(row, 3):
                                        k = f"{key_prefix}_{r2+1}"
                                        self.permanent_stats[k] = 0
                                    # ensure center cleared if condition no longer holds
                                    self._enforce_center_requirement(key_prefix)
                                    self.save_permanent_stats()
                                    self.show_centered_message(
                                        f"{label} tier {left_tier} downgraded!",
                                        120,
                                        color,
                                        20,
                                    )
                            return

                        # right tier
                        right_tier = 4 + row
                        right_key = f"{key_prefix}_{right_tier}"
                        right_rect = pygame.Rect(
                            right_col_x - tree_box_w // 2, y, tree_box_w, tree_box_h
                        )
                        if right_rect.collidepoint(pos):
                            if button == 1:
                                if right_tier == 4:
                                    prev_ok = True
                                else:
                                    # check that previous tiers in right column are active (4..right_tier-1)
                                    prev_ok = all(
                                        self.permanent_stats.get(f"{key_prefix}_{i}", 0)
                                        for i in range(4, right_tier)
                                    )
                                if (
                                    not self.permanent_stats.get(right_key, 0)
                                    and prev_ok
                                ):
                                    self.permanent_stats[right_key] = 1
                                    self.save_permanent_stats()
                                    self.show_centered_message(
                                        f"{label} tier {right_tier} unlocked!",
                                        120,
                                        color,
                                        20,
                                    )
                            elif button == 3:
                                if self.permanent_stats.get(right_key, 0):
                                    for r2 in range(row, 3):
                                        k = f"{key_prefix}_{4 + r2}"
                                        self.permanent_stats[k] = 0
                                    self._enforce_center_requirement(key_prefix)
                                    self.save_permanent_stats()
                                    self.show_centered_message(
                                        f"{label} tier {right_tier} downgraded!",
                                        120,
                                        color,
                                        20,
                                    )
                            return

                    # center bottom
                    center_y = tree_top_y + 3 * tree_v_spacing
                    center_rect = pygame.Rect(
                        col_x - tree_box_w // 2, center_y, tree_box_w, tree_box_h
                    )
                    if center_rect.collidepoint(pos):
                        center_key = f"{key_prefix}_7"
                        if button == 1:
                            # can unlock only if at least one column of 3 is full
                            left_full = all(
                                self.permanent_stats.get(f"{key_prefix}_{i+1}", 0)
                                for i in range(3)
                            )
                            right_full = all(
                                self.permanent_stats.get(f"{key_prefix}_{4 + i}", 0)
                                for i in range(3)
                            )
                            if not self.permanent_stats.get(center_key, 0) and (
                                left_full or right_full
                            ):
                                self.permanent_stats[center_key] = 1
                                self.save_permanent_stats()
                                self.show_centered_message(
                                    f"{label} final tier unlocked!", 120, color, 20
                                )
                        elif button == 3:
                            if self.permanent_stats.get(center_key, 0):
                                self.permanent_stats[center_key] = 0
                                self.save_permanent_stats()
                                self.show_centered_message(
                                    f"{label} final tier downgraded!", 120, color, 20
                                )
                        return
            elif self.awaiting_weapon_choice and self.weapon_choices:
                # Weapon selection (vertical list)
                cx: int = self.width // 2
                box_width = 700
                box_height = 100
                spacing = 20
                total_height: int = (
                    len(self.weapon_choices) * box_height
                    + (len(self.weapon_choices) - 1) * spacing
                )
                start_y: int = self.height // 2 - total_height // 2 + 30
                x_pos: int = cx - box_width // 2

                for i in range(len(self.weapon_choices)):
                    y_pos: int = start_y + i * (box_height + spacing)
                    if (
                        x_pos <= pos[0] <= x_pos + box_width
                        and y_pos <= pos[1] <= y_pos + box_height
                    ):
                        self.apply_weapon(self.weapon_choices[i]["id"])
                        return
            elif self.awaiting_tower_choice and self.tower_choices:
                # Tower selection (vertical list)
                cx: int = self.width // 2
                box_width = 500
                box_height = 80
                spacing = 20
                total_height: int = (
                    len(self.tower_choices) * box_height
                    + (len(self.tower_choices) - 1) * spacing
                )
                start_y: int = self.height // 2 - total_height // 2 + 30
                x_pos: int = cx - box_width // 2

                for i in range(len(self.tower_choices)):
                    y_pos: int = start_y + i * (box_height + spacing)
                    if (
                        x_pos <= pos[0] <= x_pos + box_width
                        and y_pos <= pos[1] <= y_pos + box_height
                    ):
                        self.apply_tower(self.tower_choices[i]["id"])
                        return
            elif self.awaiting_upgrade and self.upgrade_choices:
                # Upgrade selection (vertical list)
                cx: int = self.width // 2
                box_width = 700
                box_height = 100
                spacing = 20
                total_height: int = (
                    len(self.upgrade_choices) * box_height
                    + (len(self.upgrade_choices) - 1) * spacing
                )
                start_y: int = self.height // 2 - total_height // 2 + 30
                x_pos: int = cx - box_width // 2

                for i in range(len(self.upgrade_choices)):
                    y_pos: int = start_y + i * (box_height + spacing)
                    if (
                        x_pos <= pos[0] <= x_pos + box_width
                        and y_pos <= pos[1] <= y_pos + box_height
                    ):
                        self.apply_upgrade(i)
                        return
            elif self.paused:
                # Pause menu options (now 2 options: Resume, Quit to Menu)
                options_y_start: int = self.height // 2 - 20
                option_height = 40
                for i in range(2):
                    option_y: int = options_y_start + i * option_height
                    # Check if click is within a reasonable area around the text
                    if (
                        option_y - 20 <= pos[1] <= option_y + 20
                        and self.width // 2 - 150 <= pos[0] <= self.width // 2 + 150
                    ):
                        self.pause_menu_option: int = i
                        self.execute_pause_option()
                        return
        except Exception as e:
            logger.exception("Error handling mouse click: %s", e)
            try:
                self.show_centered_message(
                    "An error occurred handling click", 2000, (255, 100, 100)
                )
            except Exception:
                pass
            return

    def show_stage_menu(self) -> None:
        """Show stage selection menu"""
        self.showing_stage_menu = True
        self.showing_permanent_upgrades = False
        self.showing_prologo_end = False
        # If we were showing the game over overlay, clear it and resume normal menu state
        self.showing_game_over = False
        self.paused = False
        self.game_over_alpha = 0
        # Clear any selected stage so the main menu is truly reset
        self.selected_stage = None

    def show_permanent_upgrades(self) -> None:
        """Show permanent stats upgrade menu"""
        self.showing_stage_menu = False
        self.showing_permanent_upgrades = True
        self.showing_prologo_end = False

    def select_stage(self, stage) -> None:
        """Select a stage and prepare for gameplay"""
        logger.info("Selecting stage: %s", stage)
        self.selected_stage = stage
        # Keep GameStateManager in sync so initial-choice logic uses the
        # currently selected stage (fixes Purgatory-only weapon availability).
        try:
            if hasattr(self, "game_state") and self.game_state is not None:
                self.game_state.selected_stage = stage
        except Exception:
            pass
        self.showing_stage_menu = False
        self.showing_permanent_upgrades = False

        # Set stage-specific buildings/spawn points
        if stage == "prologo":
            self.buildings = [
                {"x": 460, "y": 70},  # Outer left church - raised 5 pixels
                {"x": 520, "y": 75},  # Left church
                {"x": 640, "y": 60},  # Center cathedral
                {"x": 760, "y": 75},  # Right church
                {"x": 820, "y": 70},  # Outer right church - raised 5 pixels
            ]
        else:  # limbo
            self.buildings = []  # No buildings in limbo

        # Generate stage-specific features
        if str(stage).startswith("limbo"):
            self.generate_dead_trees()
            # Configure statue/tower types per Limbo level
            if stage == "limbo":
                # Limbo 1 -> Fire
                self.left_tower = Tower(
                    320, 530, fire_rate=self.statue_fire_rate, tower_type="fire"
                )
                self.left_tower._base_damage = self.left_tower.damage
                self.left_tower._base_fire_rate = self.left_tower.fire_rate
                self.right_tower = Tower(
                    960, 530, fire_rate=self.statue_fire_rate, tower_type="fire"
                )
                self.right_tower._base_damage = self.right_tower.damage
                self.right_tower._base_fire_rate = self.right_tower.fire_rate
            elif stage == "limbo_2":
                # Limbo 2 -> Storm
                self.left_tower = Tower(
                    320, 530, fire_rate=self.statue_fire_rate, tower_type="storm"
                )
                self.left_tower._base_damage = self.left_tower.damage
                self.left_tower._base_fire_rate = self.left_tower.fire_rate
                self.right_tower = Tower(
                    960, 530, fire_rate=self.statue_fire_rate, tower_type="storm"
                )
                self.right_tower._base_damage = self.right_tower.damage
                self.right_tower._base_fire_rate = self.right_tower.fire_rate
            elif stage == "limbo_3":
                # Limbo 3 -> Ice
                self.left_tower = Tower(
                    320, 530, fire_rate=self.statue_fire_rate, tower_type="ice"
                )
                self.left_tower._base_damage = self.left_tower.damage
                self.left_tower._base_fire_rate = self.left_tower.fire_rate
                self.right_tower = Tower(
                    960, 530, fire_rate=self.statue_fire_rate, tower_type="ice"
                )
                self.right_tower._base_damage = self.right_tower.damage
                self.right_tower._base_fire_rate = self.right_tower.fire_rate
        elif str(stage).startswith(("purgatory", "hell")):
            # Purgatory/HELL is a stage category with three variants. For parity with Limbo,
            # set up no buildings and trigger initial weapon/tower choice behavior.
            self.buildings = []  # No buildings in purgatory/hell for now

            # Determine tower type by variant (fire / storm / ice)
            if stage in ("purgatory", "hell"):
                tower_type = "fire"
            elif stage in ("purgatory_2", "hell_2"):
                tower_type = "storm"
            elif stage in ("purgatory_3", "hell_3"):
                tower_type = "ice"
            else:
                tower_type = "fire"

            self.left_tower = Tower(
                320, 530, fire_rate=self.statue_fire_rate, tower_type=tower_type
            )
            self.left_tower._base_damage = self.left_tower.damage
            self.left_tower._base_fire_rate = self.left_tower.fire_rate
            self.right_tower = Tower(
                960, 530, fire_rate=self.statue_fire_rate, tower_type=tower_type
            )
            self.right_tower._base_damage = self.right_tower.damage
            self.right_tower._base_fire_rate = self.right_tower.fire_rate

            # Keep towers hidden until the player confirms the tower selection
            # to avoid confusing pre-selection visuals.
            self.left_tower.visible = False
            self.right_tower.visible = False
        self.generate_walls()

        # Reset game state for new run
        self.reset_run()

        # Prologo-specific starting weapon
        if stage == "prologo":
            self.player_weapons = ["beast"]
            self.weapon_levels = {"beast": 1}
            self.game_state.player_weapons = ["beast"]
            self.game_state.weapon_levels = {"beast": 1}
        elif str(stage).startswith("limbo"):
            # For Limbo, ask GameStateManager to initiate an initial weapon choice
            self.is_initial_weapon_choice = True
            try:
                self.game_state.show_initial_weapon_choice()
                # Mirror immediately into Game local view for deterministic behavior in the same frame
                self.awaiting_weapon_choice = self.game_state.awaiting_weapon_choice
                self.weapon_choices = list(self.game_state.weapon_choices)
                self.selected_weapon_index = self.game_state.weapon_choice_index
            except Exception:
                # Fallback behavior (in case GS isn't available)
                self.awaiting_weapon_choice = True
                self.weapon_choices = self.generate_initial_weapon_choices()
                self.selected_weapon_index = 0

            # Do not start countdown yet
        elif str(stage).startswith(("purgatory", "hell")):
            # For Purgatory/HELL, mimic Limbo's initial weapon selection behavior and enable tower choice
            self.is_initial_weapon_choice = True
            self.is_initial_tower_choice = True
            try:
                self.game_state.show_initial_weapon_choice()
                self.awaiting_weapon_choice = self.game_state.awaiting_weapon_choice
                self.weapon_choices = list(self.game_state.weapon_choices)
                self.selected_weapon_index = self.game_state.weapon_choice_index
            except Exception:
                self.awaiting_weapon_choice = True
                self.weapon_choices = self.generate_initial_weapon_choices()
                self.selected_weapon_index = 0

            # Also prepare tower selection for Purgatory/HELL
            try:
                self.game_state.show_initial_tower_choice()
                self.awaiting_tower_choice = self.game_state.awaiting_tower_choice
                self.tower_choices = list(self.game_state.tower_choices)
                self.selected_tower_index = self.game_state.tower_choice_index
            except Exception:
                self.awaiting_tower_choice = True
                self.tower_choices = (
                    self.game_state.generate_initial_tower_choices()
                    if hasattr(self, "game_state")
                    else [
                        {
                            "id": "fire",
                            "name": "Fire Tower",
                            "description": "Damage: 10 — Burn nearby enemies (4 DPS, 3s)",
                        },
                        {
                            "id": "storm",
                            "name": "Storm Tower",
                            "description": "Damage: 10 (projectile ~9) — Chains to multiple enemies",
                        },
                        {
                            "id": "ice",
                            "name": "Ice Tower",
                            "description": "Damage: 15 — Slows enemies 50% for 2s",
                        },
                    ]
                )
                self.selected_tower_index = 0

            # Do not start countdown yet

        # Start 3-second countdown before gameplay begins (unless initial weapon or tower choice)
        if not self.is_initial_weapon_choice and not self.is_initial_tower_choice:
            self.stage_start_countdown = 3  # 3 seconds
            self.stage_start_timer = self.fps  # 1 second in frames
        logger.debug("Stage selected, game should start")

        # Debug: fast-forward to Prologo final boss if requested
        if (
            stage == "prologo"
            and getattr(self, "fast_forward_prologo", False)
            and not getattr(self, "fast_forward_applied", False)
        ):
            logger.debug(
                "Fast-forward: setting time_elapsed to trigger final boss events"
            )
            # Set time beyond final-boss spawn time and process prologo events immediately
            self.time_elapsed = (
                236  # > 235 so update_prologo_events spawns boss immediately
            )
            self.update_prologo_events()

            # Optionally force the boss to become immortal and force a lightning strike for quick repro
            if getattr(self, "fast_forward_prologo_force_lightning", False):
                logger.debug(
                    "Fast-forward: forcing immortal state to trigger lightning immediately"
                )
                # Find the final boss we just spawned
                final_boss = None
                for b in self.bosses:
                    if getattr(b, "enemy_type", "") == "boss_final":
                        final_boss = b
                        break
                if final_boss is not None:
                    # Reduce health under 10% and set immortal so regen will begin
                    final_boss.health = final_boss.max_health * 0.05
                    self.prologo_final_boss_immortal = True
                    # Run the regen loop a few times to push boss back to full and trigger lightning
                    for i in range(2000):
                        self.update_prologo_events()
                        if self.prologo_lightning_strike:
                            logger.debug(
                                "Lightning strike triggered after %s iterations", i + 1
                            )
                            break
                else:
                    logger.debug("Could not find final boss to force lightning")
            self.fast_forward_applied = True

    def generate_dead_trees(self) -> None:
        """Generate dead tree data once for Limbo stage"""
        self.dead_trees = [
            {"x": 400, "y": 80, "height": 70, "trunk_width": 4},
            {"x": 520, "y": 50, "height": 90, "trunk_width": 5},
            {"x": 640, "y": 100, "height": 55, "trunk_width": 3},
            {"x": 760, "y": 65, "height": 80, "trunk_width": 6},
            {"x": 880, "y": 85, "height": 65, "trunk_width": 4},
        ]

        # Generate branches for each tree
        for tree in self.dead_trees:
            tree["branches"] = []
            num_branches: int = random.randint(3, 5)

            for i in range(num_branches):
                branch_y = tree["y"] + tree["height"] * (0.2 + i * 0.2)
                branch_length: int = random.randint(15, 30)
                branch_angle: int = random.choice([-1, 1])
                branch_end_y = branch_y - random.randint(5, 15)

                branch = {
                    "start_y": branch_y,
                    "end_x": tree["x"] + branch_length * branch_angle,
                    "end_y": branch_end_y,
                    "sub_branches": [],
                }

                # Add sub-branches
                if random.random() > 0.5:
                    sub_x = tree["x"] + branch_length * branch_angle * 0.6
                    sub_y = branch_y - random.randint(3, 8)
                    sub_end_x = sub_x + random.randint(5, 12) * branch_angle
                    sub_end_y = sub_y - random.randint(3, 8)
                    branch["sub_branches"].append(
                        {
                            "start_x": sub_x,
                            "start_y": sub_y,
                            "end_x": sub_end_x,
                            "end_y": sub_end_y,
                        }
                    )

                tree["branches"].append(branch)

    def reset_run(self) -> None:
        """Reset game state for a new run"""
        # Reset player
        self.player.x = self.width // 2
        self.player.y = self.height - 80
        self.player.health = self.player.max_health

        # Reset run counters
        self.enemies_killed_this_run = 0

        # Reset multipliers (base values; perma upgrades applied by apply_permanent_stats)
        self.damage_multiplier = 1.0
        self.fire_rate_multiplier = 1.0
        self.projectile_size_multiplier = 1.0
        # Apply STRUCTURE effect (3% damage reduction per level)
        self.damage_reduction_multiplier = 1.0 - (
            self.permanent_stats["structure"] * 0.03
        )
        # Ensure permanent stat effects are applied immediately (also sets xp_multiplier)
        self.apply_permanent_stats()

        # Reset game state
        self.enemies.empty()
        self.projectiles.empty()
        self.enemy_projectiles.empty()
        self.bosses.empty()
        self.skull_bomb_particles.clear()
        self.skull_bomb_explosions.clear()
        self.ice_particles.clear()
        self.ice_puddles.clear()

        self.wave = 0
        self.wave_time = 0.0
        # Reset spawn timer to the configured spawn rate (avoid immediate spawn)
        self.enemy_spawn_timer = self.base_spawn_rate
        self.enemy_spawn_rate = self.base_spawn_rate
        self.spawn_accel_timer = 20 * self.fps
        self.time_elapsed = 0.0
        self.big_enemy_timer = 12 * self.fps
        self.big_spawned_this_wave = False
        self.wave_boss_spawned = False

        # Reset prologo events
        self.prologo_final_boss_spawned = False
        self.prologo_final_boss_defeated = False
        self.prologo_final_boss_immortal = False
        self.prologo_lightning_timer = 0
        self.prologo_lightning_strike = False
        self.lightning_points = []

        # Reset stage start countdown
        self.stage_start_countdown = 0
        self.stage_start_timer = 0

        # Reset weapons and upgrades
        self.player_weapons = []
        self.weapon_levels = {}
        self.orbitals = []
        self.burst_count = 0
        self.burst_cooldown = 0
        self.shake_timer = 0
        # Reset alternating statue cooldown and ensure left fires first
        self.statue_cooldown = 0
        self.statue_next_left = True
        self.is_initial_weapon_choice = False

        # Reset player stats (keep permanent upgrades)
        self.player.xp = 0
        self.player.level = 1
        self.player.xp_to_next_level = XP_BASE
        # Permanent upgrade application:
        # 'power' gives +5% damage per level; blasphemy_1 gives +10% dmg/level
        self.player.damage_multiplier = (
            1.0
            + (self.permanent_stats["power"] * 0.05)
            + (self.permanent_stats.get("blasphemy_1", 0) * 0.10)
        )
        # 'adrenaline' gives +5% fire rate per level
        self.player.fire_rate_multiplier = 1.0 + (
            self.permanent_stats["adrenaline"] * 0.05
        )
        self.player.projectile_size_multiplier = DEFAULT_PROJECTILE_SIZE_MULTIPLIER
        # Apply permanent STRUCTURE effect to player (3% damage reduction per level)
        self.player.damage_reduction_multiplier = (
            DEFAULT_DAMAGE_REDUCTION_MULTIPLIER
            - (self.permanent_stats["structure"] * 0.03)
        )
        self.player.max_health = (
            PLAYER_BASE_HEALTH
            + (self.permanent_stats["vigor"] * 10)
            + (self.permanent_stats.get("blasphemy_2", 0) * 20)
        )
        self.player.health = self.player.max_health

        # Reset game level/XP tracking
        self.player_level = 1
        self.player_xp = 0
        self.xp_to_next_level = 100
        self.score = 0
        self.difficulty_multiplier = 1.0

        self.upgrade_levels = {
            "damage": 0,
            "fire_rate": 0,
            "max_health": 0,
            "projectile_size": 0,
            "armor": 0,
        }

        self.paused = False
        self.awaiting_upgrade = False
        self.awaiting_weapon_choice = False
        # Reset tower choice state as well to avoid stale flags causing premature countdown
        self.awaiting_tower_choice = False
        self.tower_choices = []
        self.selected_tower_index = 0
        self.is_initial_tower_choice = False

    def _ensure_permanent_stat_keys(self) -> None:
        """Ensure full set of permanent stat keys (backwards compatibility)."""
        keys = [
            "fire_1",
            "fire_2",
            "fire_3",
            "fire_4",
            "fire_5",
            "fire_6",
            "fire_7",
            "storm_1",
            "storm_2",
            "storm_3",
            "storm_4",
            "storm_5",
            "storm_6",
            "storm_7",
            "ice_1",
            "ice_2",
            "ice_3",
            "ice_4",
            "ice_5",
            "ice_6",
            "ice_7",
            # Blasphemies grid (2 rows of 5) — added for permanent upgrades
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
        ]
        for k in keys:
            self.permanent_stats.setdefault(k, 0)

    def record_enemy_kill(self) -> None:
        """Record a single enemy kill for the current run."""
        try:
            self.enemies_killed_this_run = (
                int(getattr(self, "enemies_killed_this_run", 0)) + 1
            )
        except Exception:
            try:
                self.enemies_killed_this_run = (
                    getattr(self, "enemies_killed_this_run", 0) + 1
                )
            except Exception:
                pass

    def load_permanent_stats(self) -> None:
        """Load persistent data from disk if file exists. Backwards-compatible.

        Supported formats:
        - Older flat dict: {"power": 1, "vigor": 0, ...} -> treated as permanent_stats
        - New wrapper: {"permanent_stats": {...}, "global_progress": {...}}"""
        try:
            if hasattr(self, "permanent_stats_file"):
                logger.debug("Checking persistent file: %s", self.permanent_stats_file)
            if (
                hasattr(self, "permanent_stats_file")
                and self.permanent_stats_file.exists()
            ):
                logger.debug(
                    "Loading persistent data from %s", self.permanent_stats_file
                )
                with open(self.permanent_stats_file, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                # New wrapper format
                if isinstance(data, dict) and (
                    "permanent_stats" in data or "global_progress" in data
                ):
                    ps = data.get("permanent_stats", {})
                    gp = data.get("global_progress", {})
                    if isinstance(ps, dict):
                        for k, v in ps.items():
                            if isinstance(v, int):
                                self.permanent_stats[k] = v
                    if isinstance(gp, dict):
                        # Accept JSON-serializable types for global progress
                        self.global_progress.update(gp)
                elif isinstance(data, dict):
                    # Backwards-compatible: flat dict treated as permanent_stats
                    for k, v in data.items():
                        if isinstance(v, int):
                            self.permanent_stats[k] = v
                self._ensure_permanent_stat_keys()
                # Remove legacy keys related to old tower/statue formats that should no longer be present
                self._prune_legacy_permanent_keys()
                logger.debug(
                    "Loaded permanent_stats: %s; global_progress: %s",
                    self.permanent_stats,
                    self.global_progress,
                )
        except Exception as e:
            logger.exception("Failed to load persistent data: %s", e)

    def _prune_legacy_permanent_keys(self) -> None:
        """Remove legacy permanent_stats keys that refer to old tower/statue formats.

        Keys containing 'tower' or 'statue' are considered legacy and removed to avoid
        showing or persisting outdated data structures.
        """
        removed = []
        for k in list(self.permanent_stats.keys()):
            if "tower" in k or "statue" in k:
                removed.append(k)
                self.permanent_stats.pop(k, None)
        if removed:
            logger.info("Pruned legacy permanent_stats keys: %s", removed)

    def save_permanent_stats(self) -> None:
        """Persist current permanent stats and global progress to disk."""
        try:
            p = self.permanent_stats_file
            logger.debug("Saving persistent data to %s", p)
            if not p.parent.exists():
                p.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "permanent_stats": self.permanent_stats,
                "global_progress": self.global_progress,
            }
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            logger.debug("Persistent data saved, file exists: %s", p.exists())
        except Exception as e:
            logger.exception("Failed to save persistent data: %s", e)

    def reset_game(self) -> None:
        """Reset everything EXCEPT permanent upgrades (they persist until player changes them)."""
        self.reset_run()
        self.selected_stage = None
        # Preserve `permanent_stats` so assigned points remain across runs until the
        # player explicitly upgrades/downgrades them in the Permanent Upgrades menu.
        # Ensure all expected keys exist for backward compatibility.
        self._ensure_permanent_stat_keys()
        self.showing_stage_menu = True

    def toggle_pause(self) -> None:
        """Toggle pause state"""
        if not self.awaiting_upgrade and not self.showing_prologo_end:
            self.paused = not self.paused
            if self.paused:
                self.pause_menu_option = 0

    def update_game(self) -> None:
        """Compatibility wrapper used by tests to advance one frame of game logic.

        Tests may call this while menus are active; temporarily force the game into
        in-game state so timers and spawning logic advance for deterministic tests.
        """
        prev_states = (
            self.showing_stage_menu,
            self.showing_permanent_upgrades,
            self.showing_prologo_end,
        )
        self.showing_stage_menu = False
        self.showing_permanent_upgrades = False
        self.showing_prologo_end = False
        try:
            return self.update()
        finally:
            (
                self.showing_stage_menu,
                self.showing_permanent_upgrades,
                self.showing_prologo_end,
            ) = prev_states

    def stop_game_loop(self) -> None:
        """Stop the running game loop (used by tests and GUI tear-down)."""
        self.running = False
        try:
            pygame.quit()
        except Exception:
            pass

    def execute_pause_option(self) -> None:
        """Execute the selected pause menu option"""
        if self.pause_menu_option == 0:  # Resume
            self.paused = False
            return
        elif self.pause_menu_option == 1:  # Quit to Menu
            # Show confirmation dialog instead of quitting immediately
            self.pause_confirmation = {"action": "quit", "selection": 0}
            return

    def continue_to_limbo(self) -> None:
        """Continue from prologo to Limbo stage"""
        self.showing_prologo_end = False
        self.selected_stage = "limbo"
        self.generate_dead_trees()
        self.reset_run()

    def show_centered_message(
        self, text, duration_ms=1800, color=(255, 204, 0), font_size=36
    ) -> None:
        """Enqueue a centered banner message"""
        frames: int = max(1, int(duration_ms / (1000.0 / self.fps)))
        self.center_messages.append(
            {"text": text, "color": color, "font_size": font_size, "frames": frames}
        )

    def update_center_messages(self) -> None:
        """Update and remove expired center messages"""
        for msg in self.center_messages[:]:
            msg["frames"] -= 1
            if msg["frames"] <= 0:
                self.center_messages.remove(msg)

    def update(self) -> None:
        # Handle stage start countdown
        if self.stage_start_countdown > 0:
            self.stage_start_timer -= 1
            if self.stage_start_timer <= 0:
                self.stage_start_countdown -= 1
                if self.stage_start_countdown > 0:
                    self.stage_start_timer = self.fps  # Reset for next second
                else:
                    self.stage_start_timer = 0  # Countdown finished
            self.update_center_messages()
            return

        if (
            self.showing_stage_menu
            or self.showing_permanent_upgrades
            or self.showing_prologo_end
        ):
            self.update_center_messages()
            return

        # If game over overlay is active, progress fade animation but skip gameplay updates
        if self.showing_game_over:
            self.update_game_over()
            self.update_center_messages()
            return

        # Sync with game_state
        self.awaiting_weapon_choice = self.game_state.awaiting_weapon_choice
        self.weapon_choices = self.game_state.weapon_choices
        self.awaiting_upgrade = self.game_state.awaiting_upgrade
        self.upgrade_choices = self.game_state.upgrade_choices
        # Sync values from the `GameStateManager` (already declared in __init__)
        self.selected_weapon_index = self.game_state.selected_weapon_index
        self.selected_upgrade_index = self.game_state.selected_upgrade_index

        # Also pause game updates while awaiting a tower choice to prevent the run from starting
        if (
            self.paused
            or self.awaiting_upgrade
            or self.awaiting_weapon_choice
            or getattr(self, "awaiting_tower_choice", False)
        ):
            self.update_center_messages()
            return

        # Increment frame counter for animations
        self.frame_count += 1

        # Update time
        self.time_elapsed += 1 / self.fps
        self.wave_time += 1 / self.fps

        # Handle input
        self.handle_input()

        # Update player
        self.player.update(self.width)
        self.player.x = self.clamp_to_walls(self.player.x)

        # VIGOR: periodic regeneration (0.5 HP every 5s per level)
        vigor_level = self.permanent_stats.get("vigor", 0)
        # Heal a flat 0.5 HP per level every 5 seconds
        if vigor_level and (self.frame_count % (5 * self.fps) == 0):
            heal = 0.5 * vigor_level
            self.player.health = min(self.player.max_health, self.player.health + heal)

        # Check for level up
        if self.player_xp >= self.xp_to_next_level:
            self.trigger_level_up()

        # Auto-attack system
        self.update_weapon_firing()

        # Update game objects
        self.projectiles.update()
        self.enemy_projectiles.update()

        # Update special projectiles
        for proj in self.projectiles:
            if isinstance(proj, SoulDrainProjectile):
                # Pass both regular enemies and any boss sprites so Soul Drain
                # homing can prioritize boss targets (including end-of-wave bosses).
                targets = []
                try:
                    # Add regular enemies (list or Group)
                    targets.extend(
                        list(self.enemies) if hasattr(self.enemies, "__iter__") else []
                    )
                except Exception:
                    pass
                try:
                    # Add bosses (Group or list)
                    if hasattr(getattr(self, "bosses", None), "sprites"):
                        targets.extend(self.bosses.sprites())
                    elif getattr(self, "bosses", None) is not None:
                        targets.extend(list(self.bosses))
                except Exception:
                    pass
                proj.update(targets, self.player)

        # Apply ice puddle slowing effects before enemy movement
        for enemy in self.enemies:
            ex, ey = self._enemy_pos(enemy)
            in_puddle = False
            max_slow_factor = 1.0

            # Check all active puddles
            for puddle in self.ice_puddles:
                px, py = puddle["x"], puddle["y"]
                radius = puddle["radius"]
                slow_factor = puddle["slow_factor"]

                dx = ex - px
                dy = ey - py
                distance = math.sqrt(dx * dx + dy * dy)
                if distance <= radius:
                    in_puddle = True
                    max_slow_factor = min(max_slow_factor, slow_factor)

            # Apply or remove slowing effect
            if in_puddle:
                # Save original speed if not already saved
                if not hasattr(enemy, "original_speed"):
                    enemy.original_speed = getattr(enemy, "speed", 100)
                enemy.speed = enemy.original_speed * max_slow_factor
                enemy.slow_factor = max_slow_factor
            else:
                # Restore normal speed
                if hasattr(enemy, "original_speed"):
                    enemy.speed = getattr(enemy, "original_speed", enemy.speed)
                    try:
                        del enemy.original_speed
                    except Exception:
                        pass
                enemy.slow_factor = 1.0

            # Check bosses too
            if hasattr(self, "bosses") and self.bosses:
                for boss in self.bosses:
                    if hasattr(boss, "x") and hasattr(boss, "y"):
                        bx, by = boss.x, boss.y
                        in_puddle = False
                        max_slow_factor = 1.0

                        # Check all active puddles
                        for puddle in self.ice_puddles:
                            px, py = puddle["x"], puddle["y"]
                            radius = puddle["radius"]
                            slow_factor = puddle["slow_factor"]

                            dx = bx - px
                            dy = by - py
                            distance = math.sqrt(dx * dx + dy * dy)
                            if distance <= radius:
                                in_puddle = True
                                max_slow_factor = min(max_slow_factor, slow_factor)

                        # Apply or remove slowing effect
                        if in_puddle:
                            # Save original speed if not already saved
                            if not hasattr(boss, "original_speed"):
                                boss.original_speed = getattr(boss, "speed", 100)
                            boss.speed = boss.original_speed * max_slow_factor
                            boss.slow_factor = max_slow_factor
                        else:
                            # Restore normal speed
                            if hasattr(boss, "original_speed"):
                                boss.speed = getattr(boss, "original_speed", boss.speed)
                                delattr(boss, "original_speed")
                            boss.slow_factor = 1.0

        # Enemies may be a pygame Group or a simple list of dicts (tests use lists)
        if hasattr(self.enemies, "update"):
            try:
                self.enemies.update(self.player, self)
            except TypeError:
                # Some group implementations may not pass the same args
                try:
                    self.enemies.update()
                except Exception as e:
                    logger.exception("Error updating enemy group: %s", e)
        else:
            # Iterate and call update on any enemy objects that expose it
            for ent in list(self.enemies):
                if hasattr(ent, "update"):
                    try:
                        ent.update(self.player, self)
                    except TypeError:
                        try:
                            ent.update(self.player)
                        except Exception as e:
                            logger.exception("Error updating entity: %s", e)
        # Check for dead enemies after update (e.g., from burn damage over time) and remove them
        if hasattr(self.enemies, "sprites"):
            for enemy in list(self.enemies.sprites()):
                if hasattr(enemy, "health") and enemy.health <= 0:
                    self.add_score(enemy.max_health * 18 * self.difficulty_multiplier)
                    type_xp_local = {
                        "weak": 10,
                        "normal": 16,
                        "strong": 25,
                        "giant": 50,
                        "angel": 22,
                    }
                    base_xp_local = type_xp_local.get(
                        str(getattr(enemy, "enemy_type", "")), 12
                    )
                    self.player_xp += int(
                        round(base_xp_local * getattr(self, "xp_multiplier", 1.0))
                    )
                    if self.player_xp >= self.xp_to_next_level:
                        self.trigger_level_up()
                    try:
                        if (
                            getattr(enemy, "burn_propagate_on_death", False)
                            or getattr(enemy, "burn_propagate_hops", 0) > 0
                        ):
                            try:
                                self._propagate_burn(enemy)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        enemy.kill()
                    except Exception:
                        pass
        else:
            for enemy in list(self.enemies):
                # Plain-list enemies (object instances expected)
                if getattr(enemy, "health", 0) <= 0:
                    self.add_score(
                        getattr(enemy, "max_health", 10)
                        * 18
                        * self.difficulty_multiplier
                    )
                    try:
                        if (
                            getattr(enemy, "burn_propagate_on_death", False)
                            or getattr(enemy, "burn_propagate_hops", 0) > 0
                        ):
                            try:
                                self._propagate_burn(enemy)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    base_xp_local = 12
                    try:
                        base_xp_local = {
                            "weak": 10,
                            "normal": 16,
                            "strong": 25,
                            "giant": 50,
                            "angel": 22,
                        }.get(str(getattr(enemy, "enemy_type", "")), 12)
                    except Exception:
                        base_xp_local = 12
                    self.player_xp += int(
                        round(base_xp_local * getattr(self, "xp_multiplier", 1.0))
                    )
                    if self.player_xp >= self.xp_to_next_level:
                        self.trigger_level_up()
                    try:
                        self.record_enemy_kill()
                    except Exception:
                        pass
                    try:
                        # Call kill() if implemented, then ensure removal from plain list
                        if hasattr(enemy, "kill"):
                            try:
                                enemy.kill()
                            except Exception:
                                pass
                        try:
                            # Always attempt to remove from the plain list container
                            self.enemies.remove(enemy)
                        except Exception:
                            pass
                    except Exception:
                        pass

                # Object/sprite enemies stored in a plain list (support for tests)
                elif hasattr(enemy, "health") and enemy.health <= 0:
                    try:
                        self.add_score(
                            enemy.max_health * 18 * self.difficulty_multiplier
                        )
                    except Exception:
                        pass
                    type_xp_local = {
                        "weak": 10,
                        "normal": 16,
                        "strong": 25,
                        "giant": 50,
                        "angel": 22,
                    }
                    base_xp_local = type_xp_local.get(
                        str(getattr(enemy, "enemy_type", "")), 12
                    )
                    try:
                        self.player_xp += int(
                            round(base_xp_local * getattr(self, "xp_multiplier", 1.0))
                        )
                    except Exception:
                        pass
                    if self.player_xp >= self.xp_to_next_level:
                        self.trigger_level_up()
                    # Propagate burn if flagged
                    try:
                        if (
                            getattr(enemy, "burn_propagate_on_death", False)
                            or getattr(enemy, "burn_propagate_hops", 0) > 0
                        ):
                            try:
                                self._propagate_burn(enemy)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        # If enemy implements kill(), call it for symmetry with Group
                        enemy.kill()
                    except Exception:
                        pass
                    try:
                        # remove from the plain list
                        self.enemies.remove(enemy)
                        try:
                            self.record_enemy_kill()
                        except Exception:
                            pass
                    except Exception:
                        pass

        # Bosses may be stored similarly
        if hasattr(self.bosses, "update"):
            try:
                self.bosses.update(self.player, self)
            except TypeError:
                try:
                    self.bosses.update()
                except Exception:
                    pass
        else:
            for b in list(self.bosses):
                if hasattr(b, "update"):
                    try:
                        b.update(self.player, self)
                    except TypeError:
                        try:
                            b.update(self.player)
                        except Exception:
                            pass

        # Check for dead bosses after update (e.g., from burn damage over time) and remove them
        if hasattr(self.bosses, "sprites"):
            for boss in list(self.bosses.sprites()):
                if hasattr(boss, "health") and boss.health <= 0:
                    # Boss death handling (similar to enemy death but with different XP multiplier)
                    # For now, use enemy-like handling; adjust if bosses have special death logic
                    self.add_score(boss.max_health * 25)  # Bosses give more score
                    boss_xp_map = {"medium": 80, "big": 150, "final": 400}
                    boss_base_xp = boss_xp_map.get(
                        boss.enemy_type.replace("boss_", ""), 100
                    )
                    self.player_xp += int(
                        round(boss_base_xp * getattr(self, "xp_multiplier", 1.0))
                    )
                    if self.player_xp >= self.xp_to_next_level:
                        self.trigger_level_up()
                    # Propagate burn on boss death if applicable
                    try:
                        if (
                            getattr(boss, "burn_propagate_on_death", False)
                            or getattr(boss, "burn_propagate_hops", 0) > 0
                        ):
                            try:
                                self._propagate_burn(boss)
                            except Exception:
                                pass
                    except Exception:
                        pass

                    # If a medium (wave) boss dies by any cause, schedule reinforcements
                    try:
                        if getattr(boss, "enemy_type", "") == "boss_medium":
                            # Show the centered HUD message and schedule the reinforcement timer
                            try:
                                self.show_centered_message(
                                    "REINFORCEMENTS INCOMING!", 1800, (255, 204, 0)
                                )
                            except Exception:
                                pass
                            try:
                                # Clear any existing reinforcement timer then schedule a new one
                                pygame.time.set_timer(pygame.USEREVENT + 1, 0)
                                pygame.time.set_timer(
                                    pygame.USEREVENT + 1, self.reinforcement_delay_ms
                                )
                            except Exception:
                                pass
                    except Exception:
                        pass

                    boss.kill()  # Remove dead boss
        else:
            for boss in list(self.bosses):
                if isinstance(boss, dict) and boss.get("health", 0) <= 0:
                    self.add_score(
                        boss.get("max_health", 100) * 25 * self.difficulty_multiplier
                    )  # Assuming bosses have higher multiplier
                    if self.player_xp >= self.xp_to_next_level:
                        self.trigger_level_up()
                    # Propagate burn on boss death if applicable
                    try:
                        if (
                            boss.get("burn_propagate_on_death", False)
                            or boss.get("burn_propagate_hops", 0) > 0
                        ):
                            try:
                                self._propagate_burn(boss)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        self.bosses.remove(boss)
                    except Exception:
                        pass

        # Process burn timers for dict-based enemies
        if not hasattr(self.enemies, "update"):
            for enemy in list(self.enemies):
                # Only process dict-backed enemies in this branch; object-based
                # enemies are updated via their own `.update()` (above).
                if not isinstance(enemy, dict):
                    continue
                if enemy.get("burn_timer", 0) > 0:
                    enemy["burn_timer"] -= 1

                    # Burn tick handling
                    enemy.setdefault("burn_tick_counter", self.fps)
                    enemy["burn_tick_counter"] -= 1
                    if enemy["burn_tick_counter"] <= 0:
                        bdps = enemy.get("burn_damage_per_second", 1.0)
                        # apply integer damage
                        dmg = bdps
                        enemy["health"] -= dmg
                        # spawn centralized floating text for burn tick
                        try:
                            ex, ey = self._enemy_pos(enemy)
                            self.spawn_floating_text(
                                str(int(dmg)), ex, ey - enemy.get("radius", 12) - 8
                            )
                        except Exception:
                            pass
                        enemy["burn_tick_counter"] = self.fps
                        if enemy["health"] <= 0:
                            # If this dying enemy should propagate its burn on death, do so
                            if (
                                enemy.get("burn_propagate_on_death", False)
                                or enemy.get("burn_propagate_hops", 0) > 0
                            ):
                                try:
                                    self._propagate_burn(enemy)
                                except Exception:
                                    pass
                            try:
                                try:
                                    self.record_enemy_kill()
                                except Exception:
                                    pass
                                self.enemies.remove(enemy)
                            except Exception:
                                pass

        # Remove projectiles that go off-screen
        for projectile in self.projectiles:
            if projectile.y < 0:
                projectile.kill()
        for projectile in self.enemy_projectiles:
            if projectile.y > self.height:
                projectile.kill()

        # Update orbitals
        if "orbital" in self.player_weapons:
            self.update_orbitals()

        # Update skull bomb auto-fire
        if "skull_bomb" in self.player_weapons:
            self.update_skull_bomb()

        # Update enemy spawning
        self.update_enemy_spawning()

        # Update wave progression
        self.update_wave_progression()

        # Update prologo events
        if self.selected_stage == "prologo":
            self.update_prologo_events()

        # Update chain lightning effects (for all stages)
        self.game_state.chain_lightning_effects = [
            effect
            for effect in self.game_state.chain_lightning_effects
            if effect.get("timer", 0) > 0
        ]
        for effect in self.game_state.chain_lightning_effects:
            effect["timer"] -= 1

        # Handle collisions
        self.handle_collisions()

        # Update skull bomb particles
        self.skull_bomb_particles = [p for p in self.skull_bomb_particles if p.alive]
        for p in self.skull_bomb_particles:
            p.update()

        # Update ice particles
        self.ice_particles = [p for p in self.ice_particles if p.alive]
        for p in self.ice_particles:
            p.update()

        # Update skull bomb explosions
        self.skull_bomb_explosions = [
            e for e in self.skull_bomb_explosions if e["timer"] > 0
        ]
        for explosion in self.skull_bomb_explosions:
            explosion["timer"] -= 1

        # Update ice puddles
        self.ice_puddles = [p for p in self.ice_puddles if p["timer"] > 0]
        for puddle in self.ice_puddles:
            puddle["timer"] -= 1

        # Update floating texts (drawn later)
        self._update_floating_texts()

        # Update floating texts
        self._update_floating_texts()

        # Update statue/tower weapons for Limbo and Purgatory
        if self.is_limbo_stage() or (
            self.selected_stage
            and str(self.selected_stage).startswith(("purgatory", "hell"))
        ):
            self.update_statue_weapons()

        # Remove off-screen projectiles
        for projectile in self.projectiles:
            if projectile.y < 0:
                projectile.kill()

        for projectile in self.enemy_projectiles:
            if (
                projectile.y > self.height
                or projectile.x < 0
                or projectile.x > self.width
            ):
                projectile.kill()

        # Remove off-screen statue projectiles
        for projectile in self.statue_projectiles[:]:
            if (
                getattr(projectile, "y", 0) < 0
                or getattr(projectile, "y", 0) > self.height
                or getattr(projectile, "x", 0) < 0
                or getattr(projectile, "x", 0) > self.width
            ):
                self.statue_projectiles.remove(projectile)

        # Update screen shake
        if self.shake_timer > 0:
            self.shake_timer -= 1

        # Update center messages
        self.update_center_messages()

        # Check for game over
        if self.player.health <= 0:
            if not (self.selected_stage == "prologo" and self.prologo_lightning_strike):
                self.game_over()

    def handle_input(self) -> None:
        """Handle player movement input"""
        keys: ScancodeWrapper = pygame.key.get_pressed()

        # Movement (disable during lightning)
        if not (self.selected_stage == "prologo" and self.prologo_lightning_strike):
            moving = False
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                self.player.velocity_x = -self.player.speed
                moving = True
            elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                self.player.velocity_x = self.player.speed
                moving = True
            else:
                self.player.velocity_x = 0

            # Vertical movement (W / S)
            if keys[pygame.K_w] or keys[pygame.K_UP]:
                self.player.move_up()
                moving = True
            elif keys[pygame.K_s] or keys[pygame.K_DOWN]:
                self.player.move_down()
                moving = True

            # Update player animation
            if moving:
                self.player_is_moving = True
                self.player_anim_timer += 1
                if self.player_anim_timer >= self.player_anim_speed:
                    self.player_anim_timer = 0
                    self.player_anim_frame = (self.player_anim_frame + 1) % 8
            else:
                self.player_is_moving = False
                self.player_anim_frame = 0
                self.player_anim_timer = 0

    def update_weapon_firing(self) -> None:
        """Handle automatic weapon firing"""
        if self.selected_stage == "prologo" and self.prologo_lightning_strike:
            return  # No firing during lightning

        # Calculate aim direction
        dx: int | Any = self.mouse_x - self.player.x
        dy = self.mouse_y - self.player.y
        dist: float = math.hypot(dx, dy)
        if dist > 0:
            aim_vel_x: float | Any = (dx / dist) * 500
            aim_vel_y = (dy / dist) * 500
        else:
            aim_vel_x = 0
            aim_vel_y = -500

        # Base weapon firing (burst system) - only if player has beast
        if "beast" in self.player_weapons:
            if self.burst_cooldown > 0:
                self.burst_cooldown -= 1
            else:
                beast_level = self.weapon_levels.get("beast", 0)
                beast_rate_multiplier = 1 + beast_level * 0.05
                effective_burst_fire_rate: int = max(
                    1,
                    int(
                        self.burst_fire_rate
                        / (self.fire_rate_multiplier * beast_rate_multiplier)
                    ),
                )
                effective_burst_max: int = self.burst_max
                effective_burst_pause: int = max(6, self.burst_pause)

                if (
                    self.time_elapsed % (effective_burst_fire_rate / self.fps)
                    < 1 / self.fps
                ):
                    if self.burst_count < effective_burst_max:
                        self.fire_basic_weapon(aim_vel_x, aim_vel_y)
                        self.burst_count += 1
                    else:
                        self.burst_cooldown = effective_burst_pause
                        self.burst_count = 0

        # Special weapons
        if "shotgun" in self.player_weapons and self.hellgun_cooldown_timer <= 0:
            self.fire_hellgun(aim_vel_x, aim_vel_y)
            slevel = self.weapon_levels.get("shotgun", 0)
            cd_shot: float = shotgun_cooldown(slevel)
            self.hellgun_cooldown_timer = int(cd_shot * self.fps)

        if "spear" in self.player_weapons and self.spear_cooldown_timer <= 0:
            self.fire_spear(aim_vel_x, aim_vel_y)
            slevel = self.weapon_levels.get("spear", 0)
            cd: float = spear_cooldown(slevel)
            self.spear_cooldown_timer = int(cd * self.fps)

        # DemonStrike: vertical-only rolling ball, pierces and slows
        if (
            "DemonStrike" in self.player_weapons
            and getattr(self, "DemonStrike_cooldown_timer", 0) <= 0
        ):
            self.fire_demon_strike(aim_vel_x, aim_vel_y)
            ds_level = self.weapon_levels.get("DemonStrike", 0)
            cd_ds: float = DemonStrike_cooldown(ds_level)
            self.DemonStrike_cooldown_timer = int(cd_ds * self.fps)

        if "Soul Drain" in self.player_weapons and self.soul_drain_cooldown_timer <= 0:
            self.fire_soul_drain(aim_vel_x, aim_vel_y)
            slevel = self.weapon_levels.get("Soul Drain", 0)
            cd_sec: float = soul_drain_cd(slevel)
            self.soul_drain_cooldown_timer = int(cd_sec * self.fps)

        # Update weapon cooldowns
        if self.hellgun_cooldown_timer > 0:
            self.hellgun_cooldown_timer -= 1
        if self.spear_cooldown_timer > 0:
            self.spear_cooldown_timer -= 1
        if getattr(self, "DemonStrike_cooldown_timer", 0) > 0:
            self.DemonStrike_cooldown_timer -= 1
        if self.soul_drain_cooldown_timer > 0:
            self.soul_drain_cooldown_timer -= 1

    def fire_basic_weapon(self, aim_x, aim_y) -> None:
        """Fire basic projectile"""
        base_damage = int(self.player_damage * self.damage_multiplier)

        # Apply beast weapon damage bonus (+5% per level)
        beast_level: int = self.weapon_levels.get("beast", 0)
        if beast_level > 0:
            try:
                # Use centralized helper to compute beast-adjusted damage
                base_damage = beast_damage(beast_level, base_damage)
            except Exception:
                # Fallback to old percentage behaviour if helper missing
                base_damage = int(base_damage * (1 + beast_level * 0.05))

        base_radius = int(8 * self.projectile_size_multiplier)

        # If player has the 'beast' weapon, make basic projectiles visibly larger
        # Fixed increase: +25% radius for beast projectiles (all levels)
        if self.weapon_levels.get("beast", 0) > 0:
            base_radius = max(1, int(base_radius * 1.25))

        projectile: Projectile = Projectile(
            self.player.x,
            self.player.y,
            aim_x,
            aim_y,
            damage=base_damage,
            radius=base_radius,
        )
        self.projectiles.add(projectile)
        mgr = self.projectile_manager
        if mgr is not None:
            try:
                mgr.register(projectile)
            except Exception:
                pass

    def fire_hellgun(self, aim_x, aim_y) -> None:
        """Fire hellgun pellets"""
        slevel: int = self.weapon_levels.get("shotgun", 0)
        pellets: int = shotgun_pellets(slevel)
        spread_deg = WEAPON_DEFS.get("shotgun", {}).get("spread_deg", 12)
        angle: float = math.atan2(aim_y, aim_x)

        for p in range(pellets):
            if pellets > 1:
                a = angle + math.radians(
                    -spread_deg / 2 + p * (spread_deg / (pellets - 1))
                )
            else:
                a = angle
            vx: float = math.cos(a) * 500
            vy: float = math.sin(a) * 500

            # Per-pellet damage now remapped by helper so Lv1..Lv6 => 20..30 (scaled by player damage)
            base_player = int(self.player_damage * self.damage_multiplier)
            base_damage = shotgun_pellet_damage(slevel, base_player)
            base_radius = int(5 * self.projectile_size_multiplier * 1.0)
            # Increase pellet collision/visual radius by +2 px as requested
            base_radius = max(1, base_radius + 2)

            pellet: Projectile = Projectile(
                self.player.x,
                self.player.y,
                vx,
                vy,
                damage=base_damage,
                radius=base_radius,
                weapon_type="shotgun",
            )
            self.projectiles.add(pellet)
            mgr = self.projectile_manager
            if mgr is not None:
                try:
                    mgr.register(pellet)
                except Exception:
                    pass

    def fire_spear(self, aim_x, aim_y) -> None:
        """Fire piercing spear"""
        slevel: int = self.weapon_levels.get("spear", 0)
        spear_damage: int = max(
            2,
            int(self.player_damage * self.damage_multiplier * 0.5 + slevel * 2),
        )
        speed_factor: float = 800 / 500.0
        vx = int(aim_x * speed_factor)
        vy = int(aim_y * speed_factor)
        spear_radius: int = max(4, int(5 * self.projectile_size_multiplier * 1.1))

        spear: Projectile = Projectile(
            self.player.x,
            self.player.y,
            vx,
            vy,
            damage=spear_damage,
            radius=spear_radius,
            weapon_type="spear",
        )
        spear.pierce_all = True
        self.projectiles.add(spear)
        mgr = self.projectile_manager
        if mgr is not None:
            try:
                mgr.register(spear)
            except Exception:
                pass

    def fire_demon_strike(self, aim_x, aim_y) -> None:
        """Fire DemonStrike: vertical-only rolling ball that pierces and slows enemies.

        Behavior:
        - Velocity constrained to perfectly vertical direction (vx = 0).
        - Pierces every enemy hit (pierce_all = True) and deals one instance of damage per enemy (same damage formula as spear).
        - Applies slow effect (50% speed) for 2 seconds on hit.
        """
        dlevel: int = self.weapon_levels.get("DemonStrike", 0)
        # Damage scaling: keep player-damage component, add +10 damage per weapon level
        dmg: int = max(
            2, int(self.player_damage * self.damage_multiplier * 0.5) + dlevel * 10
        )
        # Read tuned speed from weapon defs so it's centrally configurable

        # Constrain horizontal velocity to zero so the ball travels perfectly vertical.
        # Use constant speed for consistency, regardless of aim_y magnitude
        vy = 250 if aim_y >= 0 else -250
        vx = 0
        # Radius: use requested base diameter (rounded) from WEAPON_DEFS, scaled by projectile_size_multiplier,
        # then add per-level radius increases.
        base_diam = WEAPON_DEFS.get("DemonStrike", {}).get("base_diameter", None)
        if base_diam is not None:
            base_r_calc = int(
                round((base_diam * self.projectile_size_multiplier) / 2.0)
            )
        else:
            base_r_calc = int(
                WEAPON_DEFS.get("DemonStrike", {}).get("base_radius", 9)
                * self.projectile_size_multiplier
            )
        per_level_inc = WEAPON_DEFS.get("DemonStrike", {}).get(
            "radius_increase_per_level", 0
        )
        radius: int = max(7, base_r_calc + dlevel * per_level_inc)

        ball = Projectile(
            self.player.x,
            self.player.y,
            vx,
            vy,
            damage=dmg,
            radius=radius,
            weapon_type="DemonStrike",
        )
        ball.pierce_all = True
        # Slow metadata handled by collision system
        ball.effect = "slow"
        ball.slow_duration = int(2 * getattr(self, "fps", 60))
        ball.slow_factor = 0.5

        self.projectiles.add(ball)
        mgr = self.projectile_manager
        if mgr is not None:
            try:
                mgr.register(ball)
            except Exception:
                pass

    def fire_soul_drain(self, aim_x, aim_y) -> None:
        """Fire homing soul drain projectiles"""
        slevel: int = self.weapon_levels.get("Soul Drain", 0)
        # Use centralized helper to determine projectile count (base is now 2)
        num_projectiles = soul_drain_projectile_count(slevel)
        damage_mult = (
            1.0 + (slevel >= 3) * 0.1 + (slevel >= 5) * 0.1
        )  # Lv3 & Lv5: +10% damage
        heal_mult = (
            1.0 + (slevel >= 3) * 0.1 + (slevel >= 5) * 0.1
        )  # Lv3 & Lv5: +10% heal

        # Read base_heal from weapon defs so changes propagate consistently
        base_heal = WEAPON_DEFS.get("Soul Drain", {}).get("base_heal", 2)

        for i in range(num_projectiles):
            # Spread slightly
            angle_offset = (i - (num_projectiles - 1) / 2) * 0.3
            # Initial velocity reduced to make projectiles at least half as fast
            vx = (aim_x * math.cos(angle_offset) - aim_y * math.sin(angle_offset)) * 0.5
            vy = (aim_x * math.sin(angle_offset) + aim_y * math.cos(angle_offset)) * 0.5

            soul_proj = SoulDrainProjectile(
                self.player.x,
                self.player.y,
                vx,
                vy,
                damage=int(
                    WEAPON_DEFS.get("Soul Drain", {}).get("base_damage", 10)
                    * damage_mult
                ),
                heal_amount=int(base_heal * heal_mult),
                level=slevel,
            )
            self.projectiles.add(soul_proj)
            mgr = self.projectile_manager
            if mgr is not None:
                try:
                    mgr.register(soul_proj)
                except Exception:
                    pass

    def fire_skull_bomb(self, aim_x, aim_y) -> None:
        """Fire explosive skull bomb"""
        slevel: int = self.weapon_levels.get("skull_bomb", 0)
        damage = skull_bomb_damage(slevel)
        explosion_radius = skull_bomb_explosion_radius(slevel)

        # Create skull projectile
        # Slightly slower than basic projectiles (≈26% slower than 500 px/s)
        vx = aim_x * 370
        vy = aim_y * 370

        skull: Projectile = Projectile(
            self.player.x,
            self.player.y,
            vx,
            vy,
            damage=damage,
            radius=11,  # Medium skull (30% smaller than doubled size)
            weapon_type="skull_bomb",
        )
        # Store explosion radius in projectile for later use
        skull.explosion_radius = explosion_radius

        self.projectiles.add(skull)
        mgr = self.projectile_manager
        if mgr is not None:
            try:
                mgr.register(skull)
            except Exception:
                pass

    def _orbital_cooldown_range(self) -> tuple[int, int]:
        """Return cooldown range for orbitals based on level (delegates to weapons helper)"""
        olevel: int = self.weapon_levels.get("orbital", 0)
        return orbital_cooldown_range(olevel)

    def create_orbitals(self) -> None:
        """Initialize orbital sentinels around player"""

        self.orbitals = []
        min_cd, max_cd = self._orbital_cooldown_range()
        for i in range(self.orbital_count):
            self.orbitals.append(
                {
                    "angle": 2 * math.pi * i / max(1, self.orbital_count),
                    "dist": 70,
                    "cooldown": random.randint(min_cd, max_cd),
                    "x": self.player.x,
                    "y": self.player.y,
                }
            )

    def update_orbitals(self) -> None:
        """Update orbital sentinels and handle orbital firing."""

        # Ensure orbitals exist and match desired count
        if (
            not getattr(self, "orbitals", None)
            or len(self.orbitals) != self.orbital_count
        ):
            self.create_orbitals()

        spin_base = 0.06
        spin = spin_base + 0.003 * self.weapon_levels.get("orbital", 0)

        for orb in self.orbitals:
            orb["angle"] = orb.get("angle", 0) + spin
            orb["x"] = self.player.x + math.cos(orb["angle"]) * orb.get("dist", 70)
            orb["y"] = self.player.y + math.sin(orb["angle"]) * orb.get("dist", 70)
            orb["cooldown"] = orb.get("cooldown", 0) - 1

            if orb["cooldown"] <= 0:
                ox = orb.get("x", self.player.x)
                oy = orb.get("y", self.player.y)

                # Select nearest target among enemies and bosses if present
                targets = []
                # Enemies (supports Group or list/dict)
                if hasattr(self.enemies, "sprites"):
                    targets.extend(self.enemies.sprites())
                else:
                    try:
                        targets.extend(list(self.enemies))
                    except Exception:
                        pass

                # Bosses (may be stored separately)
                if hasattr(self.bosses, "sprites"):
                    targets.extend(self.bosses.sprites())
                else:
                    try:
                        targets.extend(list(self.bosses))
                    except Exception:
                        pass

                if targets:
                    # Helper to get x,y for different target representations
                    def _pos(e):
                        if isinstance(e, dict):
                            return e.get("x", 0), e.get("y", 0)
                        return getattr(e, "x", 0), getattr(e, "y", 0)

                    target = min(
                        targets,
                        key=lambda e: math.hypot(_pos(e)[0] - ox, _pos(e)[1] - oy),
                    )
                    tx, ty = _pos(target)
                    dx = tx - ox
                    dy = ty - oy
                else:
                    dx = self.mouse_x - ox
                    dy = self.mouse_y - oy

                dist = math.hypot(dx, dy)
                if dist > 0:
                    speed = 420
                    # Apply orbital damage upgrades at levels 3 and 5 (+10% each)

                    vel_x = (dx / dist) * speed
                    vel_y = (dy / dist) * speed
                else:
                    vel_x = 0
                    vel_y = -420

                dist = math.hypot(dx, dy)
                if dist > 0:
                    speed = 420
                    vel_x = (dx / dist) * speed
                    vel_y = (dy / dist) * speed
                else:
                    vel_x = 0
                    vel_y = -420

                projectile = Projectile(
                    ox,
                    oy,
                    vel_x,
                    vel_y,
                    damage=int(
                        8
                        * self.damage_multiplier
                        * (
                            1.0
                            + (self.weapon_levels.get("orbital", 0) >= 3) * 0.1
                            + (self.weapon_levels.get("orbital", 0) >= 5) * 0.1
                        )
                    ),
                    radius=int(4 * self.projectile_size_multiplier),
                    source="orbital",
                )
                self.projectiles.add(projectile)
                mgr = self.projectile_manager
                if mgr is not None:
                    try:
                        mgr.register(projectile)
                    except Exception:
                        pass

                min_cd, max_cd = self._orbital_cooldown_range()
                orb["cooldown"] = random.randint(min_cd, max_cd)

    def update_skull_bomb(self) -> None:
        """Update skull bomb auto-fire"""

        if self.skull_bomb_cooldown_timer > 0:
            self.skull_bomb_cooldown_timer -= 1
            return

        # Always aim at mouse position
        dx = self.mouse_x - self.player.x
        dy = self.mouse_y - self.player.y

        dist = math.hypot(dx, dy)
        if dist > 0:
            # Normalize direction
            dx /= dist
            dy /= dist
        else:
            dx, dy = 1, 0  # Default right

        # Fire skull bomb
        self.fire_skull_bomb(dx, dy)

        # Set cooldown
        slevel = self.weapon_levels.get("skull_bomb", 0)
        cd: float = skull_bomb_cooldown(slevel)
        self.skull_bomb_cooldown_timer = int(cd * self.fps)

    def update_statue_weapons(self) -> None:
        """Update Limbo statue weapons"""

        # Helper to get iterable of enemies (supports Group or plain list/dicts)
        def _enemy_iter():
            if hasattr(self.enemies, "sprites"):
                return self.enemies.sprites()
            try:
                return list(self.enemies)
            except Exception:
                return []

        def _pos(e):
            if isinstance(e, dict):
                return e.get("x", 0), e.get("y", 0)
            return getattr(e, "x", 0), getattr(e, "y", 0)

        # Statues alternate firing: single cooldown drives both sides and toggles the next side
        self.statue_cooldown -= 1
        if self.statue_cooldown <= 0:
            enemies_list = _enemy_iter()
            if enemies_list:
                # Choose side based on flag (default to left)
                if getattr(self, "statue_next_left", True):
                    proj = self.left_tower.fire_at_closest(enemies_list)
                else:
                    proj = self.right_tower.fire_at_closest(enemies_list)
                if proj:
                    # Support both single Projectile and list of Projectiles
                    if isinstance(proj, list):
                        for p in proj:
                            try:
                                self.projectiles.add(p)
                                # Register with projectile manager if applicable
                                if getattr(
                                    self, "projectile_manager", None
                                ) is not None and not isinstance(p, dict):
                                    try:
                                        mgr = self.projectile_manager
                                        if mgr is not None:
                                            mgr.register(p)
                                    except Exception:
                                        pass
                            except Exception:
                                self.projectiles.append(p)
                            # Normalize statue projectile to a small object (no dicts)
                            try:
                                sp = type("StatueProj", (), {})()
                                sp.x = getattr(p, "x", 0)
                                sp.y = getattr(p, "y", 0)
                                sp.vx = getattr(p, "vel_x", getattr(p, "vx", 0))
                                sp.vy = getattr(p, "vel_y", getattr(p, "vy", 0))
                                sp.radius = getattr(p, "radius", 6)
                                sp.source = getattr(p, "source", "statue")
                                sp.appearance = getattr(p, "appearance", None)
                                self.statue_projectiles.append(sp)
                            except Exception:
                                pass
                    else:
                        try:
                            self.projectiles.add(proj)
                            if self.projectile_manager is not None and isinstance(
                                proj, Projectile
                            ):
                                try:
                                    mgr = self.projectile_manager
                                    if mgr is not None:
                                        mgr.register(proj)
                                except Exception:
                                    pass
                        except Exception:
                            self.projectiles.append(proj)
                        try:
                            sp = type("StatueProj", (), {})()
                            sp.x = getattr(proj, "x", 0)
                            sp.y = getattr(proj, "y", 0)
                            sp.vx = getattr(proj, "vel_x", getattr(proj, "vx", 0))
                            sp.vy = getattr(proj, "vel_y", getattr(proj, "vy", 0))
                            sp.radius = getattr(proj, "radius", 6)
                            sp.source = getattr(proj, "source", "statue")
                            sp.appearance = getattr(proj, "appearance", None)
                            self.statue_projectiles.append(sp)
                        except Exception:
                            pass
                    # Reset cooldown and flip next side
                    self.statue_cooldown = self.statue_fire_rate
                    self.statue_next_left = not getattr(self, "statue_next_left", True)

        # Update statue projectiles with homing (delegated to TowerManager)
        enemies_list = _enemy_iter()
        # Collect statue projectiles from the main projectile pool
        statue_projs = []
        try:
            # pygame Group iterable
            for p in self.projectiles:
                if getattr(p, "source", None) == "statue":
                    statue_projs.append(p)
        except Exception:
            for p in self.projectiles:
                if getattr(p, "source", None) == "statue":
                    statue_projs.append(p)

        TowerManager.apply_homing(statue_projs, enemies_list)

    def handle_collisions(self) -> None:
        """Handle all collision detection"""

        # Build or update spatial grid for enemies (reused if present)
        try:
            from src.utils.spatial_grid import SpatialGrid

            enemies_iter = self._enemies_iter()
            if not hasattr(self, "spatial_grid") or self.spatial_grid is None:
                # Use configurable cell size
                cell_size = getattr(self, "spatial_grid_cell_size", 120)
                self.spatial_grid = SpatialGrid(
                    cell_size=cell_size, width=self.width, height=self.height
                )
            # Build grid from current enemy positions
            try:
                self.spatial_grid.build(enemies_iter)
            except Exception:
                # If building fails, fall back to not using the grid
                self.spatial_grid = None
        except Exception:
            self.spatial_grid = None

        # Projectiles hit enemies
        for projectile in list(self.projectiles):
            try:
                LOG.debug(
                    "handle_collisions: processing projectile id=%s appearance=%s effect=%s rect=%s",
                    id(projectile),
                    getattr(projectile, "appearance", None),
                    getattr(projectile, "effect", None),
                    getattr(projectile, "rect", None),
                )
            except Exception:
                pass
            primary_target = None
            # Projectile metadata (object-only canonical representation)
            effect = getattr(projectile, "effect", None)
            slow_duration = getattr(projectile, "slow_duration", 120)
            slow_factor = getattr(projectile, "slow_factor", 0.5)
            burn_duration = getattr(projectile, "burn_duration", 180)
            burn_dps = getattr(projectile, "burn_damage_per_second", 4.0)
            # FIRE left-column tier 2: double burn duration and burn DPS
            if getattr(self, "permanent_stats", None) and self.permanent_stats.get(
                "fire_2", 0
            ):
                try:
                    burn_duration = int(burn_duration * 2)
                except Exception:
                    pass
                try:
                    burn_dps = burn_dps * 2
                except Exception:
                    pass
            # Flag to indicate we've processed this projectile via the spatial-grid branch
            processed_projectile = False
            # Ensure we always have an iterable for hit enemies
            hit_enemies: list[Any] = []

            # If we have a spatial grid and projectile exposes position, use it
            sg = self.spatial_grid
            if sg is not None and hasattr(projectile, "x"):
                try:
                    px = getattr(projectile, "x", 0)
                    py = getattr(projectile, "y", 0)
                    pr = getattr(
                        projectile,
                        "radius",
                        getattr(projectile, "rect", None)
                        and (projectile.rect.width // 2)
                        or 5,
                    )
                    sg = self.spatial_grid
                    if sg is not None:
                        candidates = sg.query_circle(px, py, pr)
                    else:
                        candidates = []
                    # Narrow candidates by precise circle overlap
                    hit_enemies = []
                    for enemy in candidates:
                        ex, ey = self._enemy_pos(enemy)
                        er = self._enemy_radius(enemy)
                        dx = ex - px
                        dy = ey - py
                        if dx * dx + dy * dy <= (pr + er) * (pr + er):
                            hit_enemies.append(enemy)
                except Exception:
                    # If anything goes wrong, fall back to pygame.sprite.spritecollide if available
                    if hasattr(self.enemies, "sprites") and hasattr(projectile, "rect"):
                        hit_enemies = pygame.sprite.spritecollide(
                            projectile, self.enemies, False
                        )
                    else:
                        hit_enemies = []
                try:
                    px = getattr(projectile, "x", 0)
                    py = getattr(projectile, "y", 0)
                    pr = getattr(
                        projectile,
                        "radius",
                        getattr(projectile, "rect", None)
                        and (projectile.rect.width // 2)
                        or 5,
                    )
                    sg = self.spatial_grid
                    if sg is not None:
                        candidates = sg.query_circle(px, py, pr)
                    else:
                        candidates = []
                    # Narrow candidates by precise circle overlap
                    hit_enemies = []
                    for enemy in candidates:
                        ex, ey = self._enemy_pos(enemy)
                        er = self._enemy_radius(enemy)
                        dx = ex - px
                        dy = ey - py
                        if dx * dx + dy * dy <= (pr + er) * (pr + er):
                            hit_enemies.append(enemy)
                except Exception:
                    # If anything goes wrong, fall back to pygame.sprite.spritecollide if available
                    if hasattr(self.enemies, "sprites") and hasattr(projectile, "rect"):
                        hit_enemies = pygame.sprite.spritecollide(
                            projectile, self.enemies, False
                        )
                    else:
                        hit_enemies = []
            # For skull bombs and ice projectiles, also check collision with bosses
            if getattr(projectile, "weapon_type", None) == "skull_bomb" or (
                getattr(projectile, "appearance", None) == "ice_statue"
                and hasattr(projectile, "explosion_radius")
            ):
                if hasattr(self, "bosses") and self.bosses:
                    if hasattr(self.bosses, "sprites") and hasattr(projectile, "rect"):
                        boss_hits = pygame.sprite.spritecollide(
                            projectile, self.bosses, False
                        )
                        hit_enemies.extend(boss_hits)
                    elif hasattr(
                        projectile, "x"
                    ):  # Check distance-based collision with bosses
                        px = getattr(projectile, "x", 0)
                        py = getattr(projectile, "y", 0)
                        pr = getattr(projectile, "radius", 5)
                        for boss in self.bosses:
                            if hasattr(boss, "x") and hasattr(boss, "y"):
                                bx, by = boss.x, boss.y
                                br = getattr(boss, "radius", 20)
                                dx = bx - px
                                dy = by - py
                                if dx * dx + dy * dy <= (pr + br) * (pr + br):
                                    hit_enemies.append(boss)

            # Prefer the nearest hit candidate to be processed as primary (avoid multiple targets in same frame)
            try:
                if len(hit_enemies) > 1:
                    # Allow multi-hit for statues / piercing projectiles (ICE3, spear-like behaviour)
                    appearance = getattr(projectile, "appearance", None)
                    is_statue = appearance in ("ice_statue", "storm_statue")
                    pierce_attr = (
                        getattr(projectile, "pierce_all", False)
                        or getattr(projectile, "pierce_count", 0) > 0
                    )
                    # If not a special multi-hit projectile, prefer the nearest target only
                    if not (is_statue or pierce_attr):
                        px = getattr(projectile, "x", 0)
                        py = getattr(projectile, "y", 0)
                        hit_enemies.sort(
                            key=lambda e: (self._enemy_pos(e)[0] - px) ** 2
                            + (self._enemy_pos(e)[1] - py) ** 2
                        )
                        hit_enemies = [hit_enemies[0]]
                    try:
                        # Debug: hit candidates filtered
                        pass
                    except Exception:
                        pass
            except Exception:
                pass

            # ICE projectile: if it hit any enemy, ensure ICE3 first-hit flag is set
            if getattr(projectile, "appearance", None) == "ice_statue" and hit_enemies:
                # If ICE3 is active, mark this projectile as having hit its first enemy
                if self.permanent_stats.get("ice_3", 0) and not hasattr(
                    projectile, "has_hit_first_enemy"
                ):
                    projectile.has_hit_first_enemy = True

            # Special handling for ice projectiles with area damage
            if getattr(projectile, "appearance", None) == "ice_statue" and hit_enemies:
                # Check if ICE3 is active for piercing behavior
                ice3_active = self.permanent_stats.get("ice_3", 0)

                if ice3_active:
                    # ICE3: First hit creates puddle and area damage, then pierces with direct damage + slow
                    has_exploded = getattr(projectile, "has_exploded", False)

                    # Initialize hit tracking if not exists
                    if not hasattr(projectile, "hit_enemy_ids"):
                        projectile.hit_enemy_ids = set()

                    # Apply direct damage + slow to hit enemies (only once per enemy)
                    for enemy in hit_enemies:
                        # Create unique enemy ID
                        if isinstance(enemy, dict):
                            enemy_id = id(enemy)  # Use object id for dict enemies
                        else:
                            enemy_id = id(enemy)  # Use object id for sprite enemies

                        # Skip if already hit by this projectile
                        if enemy_id in projectile.hit_enemy_ids:
                            continue

                        # Mark as hit
                        projectile.hit_enemy_ids.add(enemy_id)

                        try:
                            # Apply damage
                            dmg_to_apply = getattr(projectile, "damage", 0)
                            if id(enemy) in getattr(projectile, "_hit_ids", set()):
                                pass
                            else:
                                try:
                                    LOG.debug(
                                        "handle_collisions ICE3-hit: proj_id=%s effect=%s enemy_id=%s pre_hit_ids=%s",
                                        id(projectile),
                                        getattr(projectile, "effect", None),
                                        id(enemy),
                                        getattr(projectile, "_hit_ids", None),
                                    )
                                except Exception:
                                    pass
                                enemy.take_damage(dmg_to_apply)
                                try:
                                    LOG.debug(
                                        "handle_collisions ICE3-hit-done: proj_id=%s enemy_id=%s post_hit_ids=%s",
                                        id(projectile),
                                        id(enemy),
                                        getattr(projectile, "_hit_ids", None),
                                    )
                                except Exception:
                                    pass
                            # Apply slow effect (object-style)
                            slow_duration = getattr(projectile, "slow_duration", 120)
                            slow_factor = getattr(projectile, "slow_factor", 0.5)
                            enemy.slow_timer = max(
                                getattr(enemy, "slow_timer", 0), slow_duration
                            )
                            enemy.slow_factor = min(
                                getattr(enemy, "slow_factor", 1.0), slow_factor
                            )
                            if not hasattr(enemy, "original_speed"):
                                enemy.original_speed = getattr(enemy, "speed", 0)
                            enemy.speed = enemy.original_speed * enemy.slow_factor
                            try:
                                ex, ey = self._enemy_pos(enemy)
                                self.spawn_floating_text(
                                    str(dmg_to_apply),
                                    ex,
                                    ey - self._enemy_radius(enemy) - 8,
                                    color=(100, 200, 255),
                                )
                            except Exception:
                                pass
                        except Exception:
                            if isinstance(enemy, dict):
                                dmg_to_apply = getattr(projectile, "damage", 0)
                                enemy["health"] = max(
                                    0, enemy.get("health", 0) - dmg_to_apply
                                )
                                enemy["slow_timer"] = max(
                                    enemy.get("slow_timer", 0),
                                    getattr(projectile, "slow_duration", 120),
                                )
                                enemy["slow_factor"] = min(
                                    enemy.get("slow_factor", 1.0),
                                    getattr(projectile, "slow_factor", 0.5),
                                )
                                try:
                                    ex, ey = self._enemy_pos(enemy)
                                    self.spawn_floating_text(
                                        str(dmg_to_apply),
                                        ex,
                                        ey - enemy.get("radius", 12) - 8,
                                        color=(100, 200, 255),
                                    )
                                except Exception:
                                    pass

                    # Ensure _hit_ids includes hit_enemy_ids so the subsequent explosion
                    # doesn't damage the same enemies again
                    if not hasattr(projectile, "_hit_ids"):
                        projectile._hit_ids = set()
                    projectile._hit_ids.update(
                        getattr(projectile, "hit_enemy_ids", set())
                    )

                    # First hit: create explosion and puddle
                    if not has_exploded:
                        # Create ice explosion particles
                        num_particles = random.randint(8, 12)
                        for _ in range(num_particles):
                            angle = random.uniform(0, 2 * math.pi)
                            speed = random.uniform(20, 100)
                            vx = math.cos(angle) * speed
                            vy = math.sin(angle) * speed
                            offset_x = random.uniform(-5, 5)
                            offset_y = random.uniform(-5, 5)
                            try:
                                life = random.randint(15, 30)
                                size = random.randint(2, 5)
                                p_ice = IceParticle(
                                    px + offset_x,
                                    py + offset_y,
                                    vx,
                                    vy,
                                    life=life,
                                    size=size,
                                )
                                self.ice_particles.append(p_ice)
                            except Exception:
                                pass

                        # Create ice puddle at impact point
                        puddle_radius = 40
                        if self.permanent_stats.get("ice_2", 0):
                            puddle_radius = int(40 * 1.5)  # 60 with ice_2 upgrade
                        self.ice_puddles.append(
                            {
                                "x": px,
                                "y": py,
                                "radius": puddle_radius,  # Puddle radius
                                "timer": 5 * 60,  # 5 seconds at 60 FPS
                                "slow_factor": 0.5,  # 50% speed reduction
                                "slow_duration": 30,  # 0.5 seconds slow when entering puddle
                            }
                        )

                        # Damage and slow all enemies within explosion radius
                        explosion_radius = getattr(
                            projectile, "explosion_radius", puddle_radius
                        )
                        all_targets = []
                        all_targets.extend(self.enemies)
                        if hasattr(self, "bosses") and self.bosses:
                            if hasattr(self.bosses, "sprites"):
                                all_targets.extend(self.bosses.sprites())
                            else:
                                all_targets.extend(self.bosses)

                        for enemy in all_targets:
                            ex, ey = self._enemy_pos(enemy)
                            dx = ex - px
                            dy = ey - py
                            distance = math.sqrt(dx * dx + dy * dy)
                            if distance <= explosion_radius:
                                try:
                                    # Apply damage
                                    dmg_to_apply = getattr(projectile, "damage", 0)
                                    if id(enemy) in getattr(
                                        projectile, "_hit_ids", set()
                                    ):
                                        pass
                                    else:
                                        enemy.take_damage(dmg_to_apply)
                                    # Apply slow effect (object-style)
                                    slow_duration = getattr(
                                        projectile, "slow_duration", 120
                                    )
                                    slow_factor = getattr(
                                        projectile, "slow_factor", 0.5
                                    )
                                    enemy.slow_timer = max(
                                        getattr(enemy, "slow_timer", 0), slow_duration
                                    )
                                    enemy.slow_factor = min(
                                        getattr(enemy, "slow_factor", 1.0), slow_factor
                                    )
                                    if not hasattr(enemy, "original_speed"):
                                        enemy.original_speed = getattr(
                                            enemy, "speed", 0
                                        )
                                        enemy.speed = (
                                            enemy.original_speed * enemy.slow_factor
                                        )
                                    try:
                                        ex, ey = self._enemy_pos(enemy)
                                        self.spawn_floating_text(
                                            str(dmg_to_apply),
                                            ex,
                                            ey - self._enemy_radius(enemy) - 8,
                                            color=(100, 200, 255),
                                        )
                                    except Exception:
                                        pass
                                except Exception:
                                    if isinstance(enemy, dict):
                                        dmg_to_apply = getattr(projectile, "damage", 0)
                                        enemy["health"] = max(
                                            0, enemy.get("health", 0) - dmg_to_apply
                                        )
                                        enemy["slow_timer"] = max(
                                            enemy.get("slow_timer", 0),
                                            getattr(projectile, "slow_duration", 120),
                                        )
                                        enemy["slow_factor"] = min(
                                            enemy.get("slow_factor", 1.0),
                                            getattr(projectile, "slow_factor", 0.5),
                                        )
                                        try:
                                            ex, ey = self._enemy_pos(enemy)
                                            self.spawn_floating_text(
                                                str(dmg_to_apply),
                                                ex,
                                                ey - enemy.get("radius", 12) - 8,
                                                color=(100, 200, 255),
                                            )
                                        except Exception:
                                            pass

                        # Mark projectile as having exploded
                        projectile.has_exploded = True

                    # Don't remove projectile - it continues piercing
                    processed_projectile = True
                    continue  # Skip normal processing
                else:
                    # Create ice explosion particles
                    num_particles = random.randint(8, 12)
                    for _ in range(num_particles):
                        angle = random.uniform(0, 2 * math.pi)
                        speed = random.uniform(20, 100)
                        vx = math.cos(angle) * speed
                        vy = math.sin(angle) * speed
                    offset_x = random.uniform(-5, 5)
                    offset_y = random.uniform(-5, 5)
                    try:
                        life = random.randint(15, 30)
                        size = random.randint(2, 5)
                        p_ice_local = IceParticle(
                            px + offset_x, py + offset_y, vx, vy, life=life, size=size
                        )
                        self.ice_particles.append(p_ice_local)
                    except Exception:
                        pass

                # Create ice puddle at impact point
                puddle_radius = 40
                if self.permanent_stats.get("ice_2", 0):
                    puddle_radius = int(40 * 1.5)  # 60 with ice_2 upgrade
                self.ice_puddles.append(
                    {
                        "x": px,
                        "y": py,
                        "radius": puddle_radius,  # Puddle radius
                        "timer": 5 * 60,  # 5 seconds at 60 FPS
                        "slow_factor": 0.5,  # 50% speed reduction
                        "slow_duration": 30,  # 0.5 seconds slow when entering puddle
                    }
                )

                # Damage and slow all enemies within explosion radius
                explosion_radius = getattr(
                    projectile, "explosion_radius", puddle_radius
                )
                all_targets = []
                all_targets.extend(self.enemies)
                if hasattr(self, "bosses") and self.bosses:
                    if hasattr(self.bosses, "sprites"):
                        all_targets.extend(self.bosses.sprites())
                    else:
                        all_targets.extend(self.bosses)

                for enemy in all_targets:
                    ex, ey = self._enemy_pos(enemy)
                    dx = ex - px
                    dy = ey - py
                    distance = math.sqrt(dx * dx + dy * dy)
                    if distance <= explosion_radius:
                        try:
                            # Apply damage (skip if already hit by this projectile)
                            dmg_to_apply = getattr(projectile, "damage", 0)
                            if id(enemy) in getattr(
                                projectile, "_hit_ids", set()
                            ) or id(enemy) in getattr(
                                projectile, "hit_enemy_ids", set()
                            ):
                                pass
                            else:
                                enemy.take_damage(dmg_to_apply)
                            # Apply slow effect (support dict *and* Enemy instances)
                            slow_duration = getattr(projectile, "slow_duration", 120)
                            slow_factor = getattr(projectile, "slow_factor", 0.5)
                            if isinstance(enemy, dict):
                                enemy["slow_timer"] = max(
                                    enemy.get("slow_timer", 0), slow_duration
                                )
                                enemy["slow_factor"] = min(
                                    enemy.get("slow_factor", 1.0), slow_factor
                                )
                            else:
                                enemy.slow_timer = max(
                                    getattr(enemy, "slow_timer", 0), slow_duration
                                )
                                enemy.slow_factor = min(
                                    getattr(enemy, "slow_factor", 1.0), slow_factor
                                )
                                if not hasattr(enemy, "original_speed"):
                                    enemy.original_speed = enemy.speed
                                enemy.speed = enemy.original_speed * enemy.slow_factor
                            try:
                                ex, ey = self._enemy_pos(enemy)
                                self.spawn_floating_text(
                                    str(dmg_to_apply),
                                    ex,
                                    ey - self._enemy_radius(enemy) - 8,
                                    color=(100, 200, 255),
                                )
                            except Exception:
                                pass
                        except Exception:
                            if isinstance(enemy, dict):
                                dmg_to_apply = getattr(projectile, "damage", 0)
                                enemy["health"] = max(
                                    0, enemy.get("health", 0) - dmg_to_apply
                                )
                                enemy["slow_timer"] = max(
                                    enemy.get("slow_timer", 0),
                                    getattr(projectile, "slow_duration", 120),
                                )
                                enemy["slow_factor"] = min(
                                    enemy.get("slow_factor", 1.0),
                                    getattr(projectile, "slow_factor", 0.5),
                                )
                                try:
                                    ex, ey = self._enemy_pos(enemy)
                                    self.spawn_floating_text(
                                        str(dmg_to_apply),
                                        ex,
                                        ey - enemy.get("radius", 12) - 8,
                                        color=(100, 200, 255),
                                    )
                                except Exception:
                                    pass

                # Remove projectile after explosion
                try:
                    projectile.kill()
                except Exception:
                    try:
                        self.projectiles.remove(projectile)
                    except Exception:
                        pass
                processed_projectile = True
                continue  # Skip normal processing

            for enemy in hit_enemies:
                try:
                    # Debug logging removed
                    pass
                except Exception:
                    pass
                if primary_target is None:
                    primary_target = enemy
                    try:
                        # Debug logging removed
                        pass
                    except Exception:
                        pass

                # Avoid multiple hits on the same enemy by this projectile
                hit_ids = None
                try:
                    # Canonical hit-tracking on Projectile objects (legacy dict paths removed)
                    if not hasattr(projectile, "_hit_ids"):
                        projectile._hit_ids = set()
                    hit_ids = projectile._hit_ids
                    if not hasattr(projectile, "_hit_boss_types"):
                        projectile._hit_boss_types = set()
                    # If this exact enemy was already hit by this projectile, skip
                    if id(enemy) in hit_ids:
                        continue
                    # If this is a boss (or boss part) and we've already hit a boss
                    # of the same logical type with this projectile, skip further hits
                    try:
                        etype = getattr(enemy, "enemy_type", "")
                        if (
                            isinstance(etype, str)
                            and etype.startswith("boss_")
                            and etype in getattr(projectile, "_hit_boss_types", set())
                        ):
                            continue
                    except Exception:
                        pass
                except Exception:
                    hit_ids = None

                # Special handling for soul drain
                if getattr(projectile, "weapon_type", None) == "Soul Drain":
                    # Apply instant damage on contact — use projectile.damage (and
                    # respect FIRE tier-3 via the centralized helper) rather than a
                    # fixed '2'. Also show the correct damage floating text.
                    try:
                        dmg_to_apply = self._player_damage_vs_burning(
                            projectile, enemy, getattr(projectile, "damage", 0)
                        )
                    except Exception:
                        dmg_to_apply = getattr(projectile, "damage", 0)

                    if hasattr(enemy, "take_damage"):
                        try:
                            enemy.take_damage(dmg_to_apply)
                        except Exception:
                            try:
                                enemy.health = max(
                                    0, getattr(enemy, "health", 0) - dmg_to_apply
                                )
                            except Exception:
                                pass

                    # Fallback when .take_damage isn't available: adjust attribute
                    if not hasattr(enemy, "take_damage"):
                        try:
                            enemy.health = max(
                                0, getattr(enemy, "health", 0) - int(dmg_to_apply)
                            )
                        except Exception:
                            pass
                    try:
                        ex, ey = self._enemy_pos(enemy)
                        try:
                            base = getattr(projectile, "damage", 0)
                            is_player_proj = (
                                not getattr(projectile, "is_enemy_projectile", False)
                            ) and (getattr(projectile, "source", None) != "statue")
                            color = (
                                (255, 200, 0)
                                if (
                                    self.permanent_stats.get("fire_3", 0)
                                    and is_player_proj
                                    and dmg_to_apply > base
                                )
                                else (255, 255, 255)
                            )
                        except Exception:
                            color = (255, 255, 255)
                        self.spawn_floating_text(
                            str(int(dmg_to_apply)),
                            ex,
                            ey - self._enemy_radius(enemy) - 8,
                            color=color,
                        )
                    except Exception:
                        pass

                    # Apply drain effect (secondary periodic damage/heal)
                    if (
                        not hasattr(enemy, "drain_timer")
                        or getattr(enemy, "drain_timer", 0) <= 0
                    ):
                        try:
                            enemy.drain_timer = 4 * 60  # 4 seconds
                            enemy.drain_damage = projectile.damage
                            enemy.drain_heal = projectile.heal_amount
                            enemy.drain_source = projectile  # To track
                        except Exception:
                            # dict-style enemy
                            if isinstance(enemy, dict):
                                enemy["drain_timer"] = 4 * 60
                                enemy["drain_damage"] = projectile.damage
                                enemy["drain_heal"] = projectile.heal_amount
                                enemy["drain_source"] = projectile

                    # Record this hit so the same projectile won't process the same enemy again
                    try:
                        if not hasattr(projectile, "_hit_ids"):
                            projectile._hit_ids = set()
                        projectile._hit_ids.add(id(enemy))
                    except Exception:
                        pass

                    # Mark as processed so we don't run the later plain-list / fallback
                    # collision branch for the same projectile in this frame.
                    processed_projectile = True

                    # We've handled Soul Drain for this contact — skip the normal damage path
                    continue
                    try:
                        projectile.kill()  # Remove projectile after attaching
                    except Exception:
                        try:
                            self.projectiles.remove(projectile)
                        except Exception:
                            pass
                    break  # Only attach to one enemy
                elif getattr(projectile, "weapon_type", None) == "skull_bomb":
                    # Skull bomb explodes on contact, damaging all enemies in radius
                    explosion_radius = getattr(projectile, "explosion_radius", 50)
                    px = getattr(projectile, "x", 0)
                    py = getattr(projectile, "y", 0)

                    # Create explosion particles - more irregular and varied
                    num_particles = random.randint(
                        12, 18
                    )  # More particles for denser effect
                    for _ in range(num_particles):
                        # More varied angle distribution - sometimes clustered, sometimes spread
                        angle_variation = random.uniform(0, 2 * math.pi)
                        if random.random() < 0.3:  # 30% chance of clustering
                            angle_variation += random.uniform(
                                -0.5, 0.5
                            )  # Small cluster
                        angle = angle_variation

                        # More extreme speed distribution - some fast, some slow
                        speed = random.choice(
                            [
                                random.uniform(30, 80),  # Slow particles
                                random.uniform(80, 150),  # Medium particles
                                random.uniform(150, 250),  # Fast particles
                            ]
                        )

                        vx = math.cos(angle) * speed
                        vy = math.sin(angle) * speed

                        # More varied starting positions
                        offset_x = random.uniform(-8, 8)
                        offset_y = random.uniform(-8, 8)

                        try:
                            # More varied life and size
                            life = random.randint(10, 40)  # Wider range
                            size = random.randint(1, 6)  # Smaller to larger
                            p_burn = BurnParticle(
                                px + offset_x,
                                py + offset_y,
                                vx,
                                vy,
                                life=life,
                                size=size,
                            )
                            self.skull_bomb_particles.append(p_burn)
                        except Exception:
                            pass

                    # Create explosion area effect
                    self.skull_bomb_explosions.append(
                        {
                            "x": px,
                            "y": py,
                            "radius": explosion_radius,
                            "max_radius": explosion_radius,
                            "timer": 15,  # Duration in frames
                            "max_timer": 15,
                        }
                    )

                    # Damage all enemies within explosion radius
                    all_targets = []
                    # Add regular enemies
                    all_targets.extend(self.enemies)
                    # Add bosses
                    if hasattr(self, "bosses") and self.bosses:
                        if hasattr(self.bosses, "sprites"):
                            all_targets.extend(self.bosses.sprites())
                        else:
                            all_targets.extend(self.bosses)

                    for enemy in all_targets:
                        ex, ey = self._enemy_pos(enemy)
                        dx = ex - px
                        dy = ey - py
                        distance = math.sqrt(dx * dx + dy * dy)
                        if distance <= explosion_radius:
                            try:
                                dmg_to_apply = self._player_damage_vs_burning(
                                    projectile, enemy, getattr(projectile, "damage", 0)
                                )
                                if id(enemy) in getattr(projectile, "_hit_ids", set()):
                                    pass
                                else:
                                    enemy.take_damage(dmg_to_apply)
                                try:
                                    ex, ey = self._enemy_pos(enemy)
                                    # Highlight numeric damage yellow if FIRE tier-3 bonus applied
                                    try:
                                        base = getattr(projectile, "damage", 0)
                                        is_player_proj = (
                                            not getattr(
                                                projectile, "is_enemy_projectile", False
                                            )
                                        ) and (
                                            getattr(projectile, "source", None)
                                            != "statue"
                                        )
                                        color = (
                                            (255, 200, 0)
                                            if (
                                                self.permanent_stats.get("fire_3", 0)
                                                and is_player_proj
                                                and dmg_to_apply > base
                                            )
                                            else (255, 255, 255)
                                        )
                                    except Exception:
                                        color = (255, 255, 255)
                                    self.spawn_floating_text(
                                        str(dmg_to_apply),
                                        ex,
                                        ey - self._enemy_radius(enemy) - 8,
                                        color=color,
                                    )
                                except Exception:
                                    pass
                            except Exception:
                                if isinstance(enemy, dict):
                                    dmg_to_apply = self._player_damage_vs_burning(
                                        projectile,
                                        enemy,
                                        getattr(projectile, "damage", 0),
                                    )
                                    enemy["health"] = max(
                                        0, enemy.get("health", 0) - dmg_to_apply
                                    )
                                    try:
                                        ex, ey = self._enemy_pos(enemy)
                                        try:
                                            base = getattr(projectile, "damage", 0)
                                            is_player_proj = (
                                                not getattr(
                                                    projectile,
                                                    "is_enemy_projectile",
                                                    False,
                                                )
                                            ) and (
                                                getattr(projectile, "source", None)
                                                != "statue"
                                            )
                                            color = (
                                                (255, 200, 0)
                                                if (
                                                    self.permanent_stats.get(
                                                        "fire_3", 0
                                                    )
                                                    and is_player_proj
                                                    and dmg_to_apply > base
                                                )
                                                else (255, 255, 255)
                                            )
                                        except Exception:
                                            color = (255, 255, 255)
                                        self.spawn_floating_text(
                                            str(dmg_to_apply),
                                            ex,
                                            ey - enemy.get("radius", 12) - 8,
                                            color=color,
                                        )
                                    except Exception:
                                        pass

                    # Remove projectile after explosion
                    try:
                        projectile.kill()
                    except Exception:
                        try:
                            self.projectiles.remove(projectile)
                        except Exception:
                            pass
                    processed_projectile = True
                    break  # Stop processing hits for this projectile
                else:
                    # Normal projectile damage
                    try:
                        try:
                            # Normal hit on target
                            ex, ey = self._enemy_pos(enemy)
                        except Exception:
                            pass
                        # Apply possible FIRE tier-3 player bonus vs burning enemies
                        dmg_to_apply = self._player_damage_vs_burning(
                            projectile, enemy, getattr(projectile, "damage", 0)
                        )
                        enemy.take_damage(dmg_to_apply)
                        try:
                            ex, ey = self._enemy_pos(enemy)
                            try:
                                base = (
                                    projectile.get("damage", 0)
                                    if isinstance(projectile, dict)
                                    else getattr(projectile, "damage", 0)
                                )
                                is_player_proj = (
                                    not getattr(
                                        projectile, "is_enemy_projectile", False
                                    )
                                ) and (getattr(projectile, "source", None) != "statue")
                                color = (
                                    (255, 200, 0)
                                    if (
                                        self.permanent_stats.get("fire_3", 0)
                                        and is_player_proj
                                        and dmg_to_apply > base
                                    )
                                    else (255, 255, 255)
                                )
                            except Exception:
                                color = (255, 255, 255)
                            try:
                                ex, ey = self._enemy_pos(enemy)
                                self.spawn_floating_text(
                                    str(dmg_to_apply),
                                    ex,
                                    ey - self._enemy_radius(enemy) - 8,
                                    color=color,
                                )
                            except Exception:
                                pass
                        except Exception:
                            pass
                        # Storm-statue projectiles should be removed on first contact (apply chain immediately)
                        if getattr(projectile, "appearance", None) == "storm_statue":
                            # Apply chain lightning to nearby enemies (primary already hit)
                            try:
                                chain = getattr(projectile, "chain_targets", 0)
                                if (
                                    chain
                                    and chain > 1
                                    and not getattr(projectile, "_chain_applied", False)
                                ):
                                    chain_points = [
                                        (
                                            self._enemy_pos(enemy)[0],
                                            self._enemy_pos(enemy)[1],
                                        )
                                    ]
                                    # Gather nearby candidates from sprite group
                                    others = []
                                    max_chain_distance = 300
                                    for other in self.enemies.sprites():
                                        if other is enemy:
                                            continue
                                        if getattr(other, "health", 0) <= 0:
                                            continue
                                        ox, oy = self._enemy_pos(other)
                                        exx, eyy = self._enemy_pos(enemy)
                                        dist = math.hypot(ox - exx, oy - eyy)
                                        if dist <= max_chain_distance:
                                            others.append((dist, other))
                                    others.sort(key=lambda t: t[0])
                                    to_chain = min(len(others), chain - 1)
                                    for _, targ in others[:to_chain]:
                                        try:
                                            targ.take_damage(projectile.damage * 2)
                                        except Exception:
                                            try:
                                                targ.health -= projectile.damage * 2
                                            except Exception:
                                                pass
                                        tx, ty = self._enemy_pos(targ)
                                        chain_points.append((tx, ty))

                                        # death handling for chained targets (sprite-based)
                                        if getattr(targ, "health", 0) <= 0:
                                            try:
                                                self.add_score(
                                                    targ.max_health
                                                    * 18
                                                    * self.difficulty_multiplier
                                                )
                                            except Exception:
                                                pass
                                            try:
                                                type_xp_local = {
                                                    "weak": 10,
                                                    "normal": 16,
                                                    "strong": 25,
                                                    "giant": 50,
                                                    "angel": 22,
                                                }
                                                base_xp_local = type_xp_local.get(
                                                    str(
                                                        getattr(targ, "enemy_type", "")
                                                    ),
                                                    12,
                                                )
                                                self.player_xp += int(
                                                    round(
                                                        base_xp_local
                                                        * getattr(
                                                            self, "xp_multiplier", 1.0
                                                        )
                                                    )
                                                )
                                                if (
                                                    self.player_xp
                                                    >= self.xp_to_next_level
                                                ):
                                                    self.trigger_level_up()
                                            except Exception:
                                                pass
                                            try:
                                                if (
                                                    getattr(
                                                        targ,
                                                        "burn_propagate_on_death",
                                                        False,
                                                    )
                                                    or getattr(
                                                        targ, "burn_propagate_hops", 0
                                                    )
                                                    > 0
                                                ):
                                                    try:
                                                        self._propagate_burn(targ)
                                                    except Exception:
                                                        pass
                                            except Exception:
                                                pass

                                            # storm_2: create lightning explosion on chain-kill
                                            try:
                                                if self.permanent_stats.get(
                                                    "storm_2", 0
                                                ):
                                                    cx, cy = self._enemy_pos(targ)
                                                    explosion_radius = 120
                                                    explosion_dmg = getattr(
                                                        projectile, "damage", 0
                                                    )
                                                    all_targets = []
                                                    all_targets.extend(
                                                        self.enemies
                                                        if hasattr(
                                                            self.enemies, "sprites"
                                                        )
                                                        else self.enemies
                                                    )
                                                    if (
                                                        hasattr(self, "bosses")
                                                        and self.bosses
                                                    ):
                                                        if hasattr(
                                                            self.bosses, "sprites"
                                                        ):
                                                            all_targets.extend(
                                                                self.bosses.sprites()
                                                            )
                                                        else:
                                                            all_targets.extend(
                                                                self.bosses
                                                            )
                                                    explosion_points = [(cx, cy)]
                                                    for ex_target in all_targets:
                                                        if ex_target is targ:
                                                            continue
                                                        try:
                                                            ex, ey = self._enemy_pos(
                                                                ex_target
                                                            )
                                                        except Exception:
                                                            continue
                                                        dist = math.hypot(
                                                            ex - cx, ey - cy
                                                        )
                                                        if dist <= explosion_radius:
                                                            try:
                                                                ex_target.take_damage(
                                                                    explosion_dmg
                                                                )
                                                            except Exception:
                                                                if isinstance(
                                                                    ex_target, dict
                                                                ):
                                                                    ex_target[
                                                                        "health"
                                                                    ] = max(
                                                                        0,
                                                                        ex_target.get(
                                                                            "health", 0
                                                                        )
                                                                        - explosion_dmg,
                                                                    )
                                                            explosion_points.append(
                                                                (ex, ey)
                                                            )
                                                    if len(explosion_points) > 1:
                                                        try:
                                                            # richer visual metadata for storm_2 on-kill explosion
                                                            self.game_state.chain_lightning_effects.append(
                                                                {
                                                                    "points": explosion_points,
                                                                    "timer": 16,
                                                                    "color": (
                                                                        120,
                                                                        220,
                                                                        255,
                                                                    ),
                                                                    "explosion": True,
                                                                    "radius": explosion_radius,
                                                                }
                                                            )
                                                        except Exception:
                                                            pass
                                            except Exception:
                                                pass

                                            try:
                                                try:
                                                    self.record_enemy_kill()
                                                except Exception:
                                                    pass
                                                targ.kill()
                                            except Exception:
                                                try:
                                                    try:
                                                        self.record_enemy_kill()
                                                    except Exception:
                                                        pass
                                                    self.enemies.remove(targ)
                                                except Exception:
                                                    pass
                                    if len(chain_points) > 1:
                                        self.game_state.chain_lightning_effects.append(
                                            {"points": chain_points, "timer": 8}
                                        )
                                    projectile._chain_applied = True
                            except Exception:
                                pass

                            try:
                                projectile.kill()
                            except Exception:
                                try:
                                    self.projectiles.remove(projectile)
                                except Exception:
                                    pass
                    except Exception:
                        if isinstance(enemy, dict):
                            dmg_to_apply = self._player_damage_vs_burning(
                                projectile,
                                enemy,
                                (
                                    projectile.get("damage", 0)
                                    if isinstance(projectile, dict)
                                    else getattr(projectile, "damage", 0)
                                ),
                            )
                            enemy["health"] = max(
                                0, enemy.get("health", 0) - dmg_to_apply
                            )
                            try:
                                ex, ey = self._enemy_pos(enemy)
                                try:
                                    base = (
                                        projectile.get("damage", 0)
                                        if isinstance(projectile, dict)
                                        else getattr(projectile, "damage", 0)
                                    )
                                    is_player_proj = (
                                        not getattr(
                                            projectile, "is_enemy_projectile", False
                                        )
                                    ) and (
                                        getattr(projectile, "source", None) != "statue"
                                    )
                                    color = (
                                        (255, 200, 0)
                                        if (
                                            self.permanent_stats.get("fire_3", 0)
                                            and is_player_proj
                                            and dmg_to_apply > base
                                        )
                                        else (255, 255, 255)
                                    )
                                except Exception:
                                    color = (255, 255, 255)
                                self.spawn_floating_text(
                                    str(dmg_to_apply),
                                    ex,
                                    ey - enemy.get("radius", 12) - 8,
                                    color=color,
                                )
                            except Exception:
                                pass

                            # Legacy dict-style storm-statue handling removed — use object-style storm processing above
                            pass

                # Record this hit so projectile won't hit the same enemy again
                try:
                    if hit_ids is None:
                        if not hasattr(projectile, "_hit_ids"):
                            projectile._hit_ids = set()
                        hit_ids = projectile._hit_ids
                    hit_ids.add(id(enemy))
                    # For bosses, also remember the boss-type so multi-part bosses
                    # or duplicate boss sub-sprites won't be damaged multiple times
                    try:
                        etype = getattr(enemy, "enemy_type", "")
                        if isinstance(etype, str) and etype.startswith("boss_"):
                            if isinstance(projectile, dict):
                                projectile.setdefault("_hit_boss_types", set()).add(
                                    etype
                                )
                            else:
                                if not hasattr(projectile, "_hit_boss_types"):
                                    projectile._hit_boss_types = set()
                                projectile._hit_boss_types.add(etype)
                    except Exception:
                        pass
                except Exception:
                    pass

                # Apply slow effect if projectile has it (Ice towers)
                if effect == "slow":
                    if (
                        not hasattr(enemy, "slow_timer")
                        or getattr(enemy, "slow_timer", 0) <= 0
                    ):
                        try:
                            enemy.slow_timer = slow_duration
                            enemy.slow_factor = slow_factor
                            if not hasattr(enemy, "original_speed"):
                                enemy.original_speed = enemy.speed
                            enemy.speed = enemy.speed * enemy.slow_factor
                        except Exception:
                            if isinstance(enemy, dict):
                                enemy["slow_timer"] = slow_duration
                                enemy["slow_factor"] = slow_factor

                    # Add ice explosion particles
                    if isinstance(enemy, dict):
                        ice_parts = enemy.setdefault("ice_particles", [])
                        for _ in range(5):  # 5 ice shards
                            vx = random.uniform(-50, 50)
                            vy = random.uniform(-30, -10)
                            ice_parts.append(
                                {
                                    "x": enemy["x"],
                                    "y": enemy["y"],
                                    "vx": vx,
                                    "vy": vy,
                                    "life": 20,
                                    "size": 2,
                                }
                            )
                    else:
                        for _ in range(10):  # More ice shards for better visibility
                            vx = random.uniform(-60, 60)
                            vy = random.uniform(-40, 20)  # Some go up, some down
                            p_ice_enemy = IceParticle(
                                enemy.x,
                                enemy.y,
                                vx,
                                vy,
                                life=25,
                                size=random.randint(1, 3),
                            )
                            enemy.ice_particles.append(p_ice_enemy)

                # Apply burn effect (Fire towers)
                if effect == "burn":
                    # Only apply if not already burning
                    try:
                        if isinstance(enemy, dict):
                            enemy.setdefault("burn_timer", 0)
                            if enemy.get("burn_timer", 0) <= 0:
                                enemy["burn_timer"] = burn_duration
                                enemy["burn_damage_per_second"] = burn_dps
                                enemy["burn_tick_counter"] = getattr(self, "fps", 60)
                                # If FIRE tier 1 is active, mark this burn to propagate when the enemy dies
                                # (do not rely on projectile.appearance — any burn source should be eligible).
                                try:
                                    if self.permanent_stats.get("fire_1", 0):
                                        # Mark this burn to propagate when the enemy dies; allow
                                        # chaining up to 3 additional enemies.
                                        enemy["burn_propagate_on_death"] = True
                                        enemy["burn_propagate_radius"] = 150
                                        enemy["burn_propagate_dps"] = burn_dps
                                        enemy["burn_propagate_duration"] = burn_duration
                                        enemy["burn_propagate_hops"] = 2
                                except Exception:
                                    pass
                        else:
                            if (
                                not hasattr(enemy, "burn_timer")
                                or getattr(enemy, "burn_timer", 0) <= 0
                            ):
                                enemy.burn_timer = burn_duration
                                enemy.burn_damage_per_second = burn_dps
                                # Counter for per-second ticks
                                enemy.burn_tick_timer = getattr(self, "fps", 60)
                                # For sprite-based enemies, attach propagation-on-death attrs when applicable
                                try:
                                    if self.permanent_stats.get("fire_1", 0):
                                        enemy.burn_propagate_on_death = True
                                        enemy.burn_propagate_radius = 150
                                        enemy.burn_propagate_dps = burn_dps
                                        enemy.burn_propagate_duration = burn_duration
                                        enemy.burn_propagate_hops = 2
                                except Exception:
                                    pass
                    except Exception:
                        pass

                # Handle projectile piercing / kill (object-style only)
                p_pierce_all = getattr(projectile, "pierce_all", False)
                p_pierce_count = getattr(projectile, "pierce_count", 0)
                # ICE3: Ice projectiles pierce through all enemies
                if getattr(
                    projectile, "appearance", None
                ) == "ice_statue" and self.permanent_stats.get("ice_3", 0):
                    p_pierce_all = True

                if p_pierce_all:
                    pass  # Spear pierces through everything
                elif p_pierce_count > 0:
                    # decrement remaining pierces and remove if exhausted (object-style)
                    projectile.pierce_count = getattr(projectile, "pierce_count", 0) - 1
                    p_pierce_count = projectile.pierce_count

                    if p_pierce_count <= 0:
                        try:
                            projectile.kill()
                        except Exception:
                            try:
                                self.projectiles.remove(projectile)
                            except Exception:
                                pass
                        except Exception:
                            pass
                else:
                    # Default: remove / kill projectile after a hit
                    try:
                        if isinstance(projectile, dict):
                            try:
                                self.projectiles.remove(projectile)
                            except Exception:
                                pass
                        else:
                            projectile.kill()
                    except Exception:
                        pass

                    # Death handling for dict-based enemies
                    if isinstance(enemy, dict):
                        if enemy.get("health", 0) <= 0:
                            self.add_score(
                                enemy.get("max_health", 10)
                                * 18
                                * self.difficulty_multiplier
                            )
                            type_xp_local = {
                                "weak": 10,
                                "normal": 16,
                                "strong": 25,
                                "giant": 50,
                                "angel": 22,
                            }
                            base_xp_local = type_xp_local.get(
                                str(enemy.get("type", "")), 12
                            )
                            self.player_xp += int(
                                round(
                                    base_xp_local * getattr(self, "xp_multiplier", 1.0)
                                )
                            )
                            if self.player_xp >= self.xp_to_next_level:
                                self.trigger_level_up()
                            # Propagate burn on death if flagged
                            try:
                                if (
                                    enemy.get("burn_propagate_on_death", False)
                                    or enemy.get("burn_propagate_hops", 0) > 0
                                ):
                                    try:
                                        self._propagate_burn(enemy)
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            try:
                                self.enemies.remove(enemy)
                            except Exception:
                                pass
                        break

                    # Death handling for object-based enemies
                    if getattr(enemy, "health", None) is not None:
                        if enemy.health <= 0:
                            self.add_score(
                                enemy.max_health * 18 * self.difficulty_multiplier
                            )
                            # Give XP on kill (per-type table, flat values)
                            type_xp_local = {
                                "weak": 10,
                                "normal": 16,
                                "strong": 25,
                                "giant": 50,
                                "angel": 22,
                            }
                            base_xp_local = type_xp_local.get(
                                str(enemy.enemy_type), 12
                            )  # fallback XP
                            self.player_xp += int(
                                round(
                                    base_xp_local * getattr(self, "xp_multiplier", 1.0)
                                )
                            )
                            if self.player_xp >= self.xp_to_next_level:
                                self.trigger_level_up()
                            # Ensure propagation fires even if killed by a weapon/projectile
                            try:
                                if (
                                    getattr(enemy, "burn_propagate_on_death", False)
                                    or getattr(enemy, "burn_propagate_hops", 0) > 0
                                ):
                                    try:
                                        self._propagate_burn(enemy)
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            enemy.kill()  # Remove dead enemy
                        break

                try:
                    # Debug logging removed
                    pass
                except Exception:
                    pass
                # Chain hits: storm projectiles can hit additional distinct enemies
                if primary_target is not None:
                    try:
                        # Debug logging removed
                        pass
                    except Exception:
                        pass
                    chain = getattr(projectile, "chain_targets", 0)
                    if (
                        chain
                        and chain > 1
                        and not getattr(projectile, "_chain_applied", False)
                    ):
                        others = []
                        # Gather other enemy candidates within chain range
                        max_chain_distance = (
                            300  # Maximum distance for chain lightning (pixels)
                        )
                        for other in self.enemies.sprites():
                            if other is primary_target:
                                continue
                            if getattr(other, "health", 0) <= 0:
                                continue
                            ox, oy = self._enemy_pos(other)
                            exx, eyy = self._enemy_pos(primary_target)
                            dist = math.hypot(ox - exx, oy - eyy)
                            if (
                                dist <= max_chain_distance
                            ):  # Only consider enemies within range
                                others.append((dist, other))
                        others.sort(key=lambda t: t[0])
                        to_chain = min(len(others), chain - 1)

                        # Debug logging for chain targets
                        try:
                            LOG.debug(
                                "Storm chain: primary=%s, chain=%s, candidates=%s",
                                primary_target,
                                chain,
                                [o[1] for o in others],
                            )
                        except Exception:
                            pass

                        # Store chain lightning effect for visual
                        chain_points = [
                            (
                                self._enemy_pos(primary_target)[0],
                                self._enemy_pos(primary_target)[1],
                            )
                        ]

                        for _, targ in others[:to_chain]:
                            # Apply damage to chained targets (prefer take_damage)
                            damaged = False
                            try:
                                try:
                                    # Chain: apply damage to secondary target
                                    pass
                                except Exception:
                                    pass
                                targ.take_damage(projectile.damage * 2)
                                damaged = True
                                try:
                                    # Chain: damage applied
                                    pass
                                except Exception:
                                    pass
                            except Exception:
                                try:
                                    try:
                                        # Chain: apply damage to secondary target
                                        pass
                                    except Exception:
                                        pass
                                    targ.health -= projectile.damage * 2
                                    damaged = True
                                    try:
                                        # Chain: damage applied
                                        pass
                                    except Exception:
                                        pass
                                except Exception:
                                    pass

                            # Record that this projectile hit the chained target so it won't be hit again
                            try:
                                if not hasattr(projectile, "_hit_ids"):
                                    projectile._hit_ids = set()
                                projectile._hit_ids.add(id(targ))
                                try:
                                    LOG.debug(
                                        "handle_collisions: projectile id=%s chained-damaged targ id=%s; _hit_ids=%s",
                                        id(projectile),
                                        id(targ),
                                        getattr(projectile, "_hit_ids", None),
                                    )
                                except Exception:
                                    pass
                            except Exception:
                                pass

                            # Debug log if damage wasn't applied
                            try:
                                if not damaged:
                                    LOG.debug(
                                        "Storm chain: failed to damage target %s", targ
                                    )
                            except Exception:
                                pass

                            # Add to chain points for visual effect
                            tx, ty = self._enemy_pos(targ)
                            chain_points.append((tx, ty))

                            # death handling for chained-target sprites
                            if getattr(targ, "health", 0) <= 0:
                                self.add_score(
                                    targ.max_health * 18 * self.difficulty_multiplier
                                )
                                type_xp_local = {
                                    "weak": 10,
                                    "normal": 16,
                                    "strong": 25,
                                    "giant": 50,
                                    "angel": 22,
                                }
                                base_xp_local = type_xp_local.get(
                                    str(targ.enemy_type), 12
                                )
                                self.player_xp += int(
                                    round(
                                        base_xp_local
                                        * getattr(self, "xp_multiplier", 1.0)
                                    )
                                )
                                if self.player_xp >= self.xp_to_next_level:
                                    self.trigger_level_up()
                                # Propagate burn on death even if killed by a weapon/projectile
                                try:
                                    if (
                                        getattr(targ, "burn_propagate_on_death", False)
                                        or getattr(targ, "burn_propagate_hops", 0) > 0
                                    ):
                                        try:
                                            self._propagate_burn(targ)
                                        except Exception:
                                            pass
                                except Exception:
                                    pass

                                # If storm_2 permanent is active, chained-target kills create a
                                # lightning explosion that damages nearby enemies.
                                try:
                                    if self.permanent_stats.get("storm_2", 0):
                                        # Capture center before removing target
                                        try:
                                            cx, cy = self._enemy_pos(targ)
                                        except Exception:
                                            cx, cy = 0, 0
                                        explosion_radius = 120  # pixels
                                        # Explosion damage scales with the projectile's base damage
                                        try:
                                            explosion_dmg = getattr(
                                                projectile, "damage", 0
                                            )
                                        except Exception:
                                            explosion_dmg = 0

                                        # Gather targets (enemies + bosses)
                                        all_targets = []
                                        all_targets.extend(
                                            self.enemies
                                            if hasattr(self.enemies, "sprites")
                                            else self.enemies
                                        )
                                        if hasattr(self, "bosses") and self.bosses:
                                            if hasattr(self.bosses, "sprites"):
                                                all_targets.extend(
                                                    self.bosses.sprites()
                                                )
                                            else:
                                                all_targets.extend(self.bosses)

                                        explosion_points = [(cx, cy)]
                                        for ex_target in all_targets:
                                            if ex_target is targ:
                                                continue
                                            try:
                                                ex, ey = self._enemy_pos(ex_target)
                                            except Exception:
                                                continue
                                            dx = ex - cx
                                            dy = ey - cy
                                            distance = math.hypot(dx, dy)
                                            if distance <= explosion_radius:
                                                # Apply damage to nearby enemy
                                                try:
                                                    ex_target.take_damage(explosion_dmg)
                                                except Exception:
                                                    if isinstance(ex_target, dict):
                                                        ex_target["health"] = max(
                                                            0,
                                                            ex_target.get("health", 0)
                                                            - explosion_dmg,
                                                        )
                                                explosion_points.append((ex, ey))

                                        # Add short chain/lightning visuals from the killed enemy to affected neighbours
                                        if len(explosion_points) > 1:
                                            try:
                                                self.game_state.chain_lightning_effects.append(
                                                    {
                                                        "points": explosion_points,
                                                        "timer": 12,
                                                        "color": (120, 220, 255),
                                                        "explosion": True,
                                                        "radius": explosion_radius,
                                                    }
                                                )
                                            except Exception:
                                                pass
                                except Exception:
                                    pass

                                try:
                                    try:
                                        self.record_enemy_kill()
                                    except Exception:
                                        pass
                                    targ.kill()
                                except Exception:
                                    try:
                                        try:
                                            self.record_enemy_kill()
                                        except Exception:
                                            pass
                                        self.enemies.remove(targ)
                                    except Exception:
                                        pass

                        # Add chain lightning effect to game state
                        if len(chain_points) > 1:
                            try:
                                # Debug logging removed
                                pass
                            except Exception:
                                pass
                            try:
                                # Diagnostic: health snapshot
                                pass
                            except Exception:
                                pass
                            self.game_state.chain_lightning_effects.append(
                                {
                                    "points": chain_points,
                                    "timer": 8,  # Show for 8 frames
                                }
                            )
                        # Mark chain applied so we don't duplicate
                        projectile._chain_applied = True
            if processed_projectile:
                continue
            else:
                # Enemies stored as a simple iterable (dicts or object instances)
                # Quick boss check for list-backed enemy collections (ensure projectiles
                # that hit bosses are handled even when enemies are not a Sprite Group)
                try:
                    if (
                        hasattr(projectile, "rect")
                        and hasattr(self, "bosses")
                        and self.bosses
                    ):
                        boss_hits = pygame.sprite.spritecollide(
                            projectile, self.bosses, False
                        )
                        if boss_hits:
                            for boss in boss_hits:
                                try:
                                    # Apply direct damage to boss
                                    bd_local = self._player_damage_vs_burning(
                                        projectile,
                                        boss,
                                        getattr(projectile, "damage", 0),
                                    )
                                    boss.take_damage(bd_local)
                                except Exception:
                                    pass

                                # Apply projectile effects to boss (burn/slow)
                                try:
                                    if getattr(projectile, "effect", None) == "slow":
                                        if (
                                            not hasattr(boss, "slow_timer")
                                            or getattr(boss, "slow_timer", 0) <= 0
                                        ):
                                            boss.slow_timer = getattr(
                                                projectile, "slow_duration", 120
                                            )
                                            boss.slow_factor = getattr(
                                                projectile, "slow_factor", 0.5
                                            )
                                            if not hasattr(boss, "original_speed"):
                                                boss.original_speed = boss.speed
                                            boss.speed = boss.speed * boss.slow_factor
                                    elif getattr(projectile, "effect", None) == "burn":
                                        if (
                                            not hasattr(boss, "burn_timer")
                                            or getattr(boss, "burn_timer", 0) <= 0
                                        ):
                                            boss.burn_timer = burn_duration
                                            boss.burn_damage_per_second = burn_dps
                                            boss.burn_tick_timer = getattr(
                                                self, "fps", 60
                                            )
                                except Exception:
                                    pass

                                # Record that this projectile has hit this boss/type so
                                # it won't hit again on subsequent frames
                                try:
                                    if not hasattr(projectile, "_hit_ids"):
                                        projectile._hit_ids = set()
                                    projectile._hit_ids.add(id(boss))
                                    if not hasattr(projectile, "_hit_boss_types"):
                                        projectile._hit_boss_types = set()
                                    projectile._hit_boss_types.add(
                                        getattr(boss, "enemy_type", "")
                                    )
                                except Exception:
                                    pass

                                # Remove projectile after hitting a boss (default)
                                try:
                                    projectile.kill()
                                except Exception:
                                    try:
                                        self.projectiles.remove(projectile)
                                    except Exception:
                                        pass
                                # Mark as processed so we don't run the later boss-collision
                                # branch again for the same projectile in this frame.
                                processed_projectile = True
                                continue
                    proj_px = getattr(projectile, "x", 0)
                    proj_py = getattr(projectile, "y", 0)
                    proj_pr = getattr(
                        projectile,
                        "radius",
                        (
                            projectile.get("radius", 0)
                            if isinstance(projectile, dict)
                            else 0
                        ),
                    )
                except Exception:
                    proj_px = proj_py = proj_pr = 0

                # Ensure candidates is fresh for the plain-list collision pass
                candidates = []

                for enemy in list(self.enemies):
                    ex, ey = self._enemy_pos(enemy)
                    er = self._enemy_radius(enemy)
                    dx = ex - proj_px
                    dy = ey - proj_py
                    # precise circle overlap check
                    d2 = dx * dx + dy * dy
                    try:
                        thresh = (er + proj_pr) * (er + proj_pr)

                        if d2 <= thresh:
                            candidates.append((d2, enemy))
                    except Exception:
                        pass

                # Normalize candidate entries to (dist_sq, enemy) tuples so
                # downstream code can assume a consistent structure.
                normalized = []
                for c in candidates:
                    if isinstance(c, tuple) and len(c) >= 2:
                        normalized.append((c[0], c[1]))
                    else:
                        try:
                            ex, ey = self._enemy_pos(c)
                            d2 = (ex - proj_px) ** 2 + (ey - proj_py) ** 2
                        except Exception:
                            d2 = 0
                        normalized.append((d2, c))

                if len(normalized) > 1:
                    normalized.sort(key=lambda t: t[0])
                    hit_enemies = [normalized[0][1]]
                else:
                    hit_enemies = [n[1] for n in normalized]

                # Process only the nearest overlapping enemy (if any)
                for enemy in hit_enemies:
                    # Canonical projectile attributes (object-style)
                    px = getattr(projectile, "x", 0)
                    py = getattr(projectile, "y", 0)
                    pr = getattr(projectile, "radius", 0)
                    p_damage = getattr(projectile, "damage", 0)
                    p_pierce_all = getattr(projectile, "pierce_all", False)
                    p_pierce_count = getattr(projectile, "pierce_count", 0)

                    # Hit
                    # Avoid multiple hits on the same enemy by this projectile
                    hit_ids = None
                    try:
                        if not hasattr(projectile, "_hit_ids"):
                            projectile._hit_ids = set()
                        hit_ids = projectile._hit_ids
                        if id(enemy) in hit_ids:
                            continue
                    except Exception:
                        hit_ids = None
                    # object-style enemy (removed dict-compat)
                    dmg_to_apply = self._player_damage_vs_burning(
                        projectile, enemy, p_damage
                    )
                    try:
                        enemy.take_damage(dmg_to_apply)
                    except Exception:
                        try:
                            enemy.health = max(
                                0, getattr(enemy, "health", 0) - dmg_to_apply
                            )
                        except Exception:
                            pass

                    # Record this hit so projectile won't hit the same enemy again
                    try:
                        if hit_ids is None:
                            if not hasattr(projectile, "_hit_ids"):
                                projectile._hit_ids = set()
                            hit_ids = projectile._hit_ids
                        hit_ids.add(id(enemy))
                        try:
                            LOG.debug(
                                "handle_collisions: projectile id=%s damaged enemy id=%s; _hit_ids=%s",
                                id(projectile),
                                id(enemy),
                                getattr(projectile, "_hit_ids", None),
                            )
                        except Exception:
                            pass

                    except Exception:
                        pass

                        # Apply slow (object-style)
                        if effect == "slow":
                            if not hasattr(enemy, "original_speed"):
                                enemy.original_speed = getattr(enemy, "speed", 100)
                            enemy.slow_timer = slow_duration
                            enemy.slow_factor = slow_factor
                            enemy.speed = enemy.original_speed * enemy.slow_factor

                            # Add ice explosion particles (object-style)
                            if not hasattr(enemy, "ice_particles"):
                                enemy.ice_particles = []
                            ex, ey = self._enemy_pos(enemy)
                            for _ in range(10):  # More ice shards for better visibility
                                vx = random.uniform(-60, 60)
                                vy = random.uniform(-40, 20)  # Some go up, some down
                                enemy.ice_particles.append(
                                    IceParticle(
                                        ex,
                                        ey,
                                        vx,
                                        vy,
                                        life=25,
                                        size=random.randint(1, 3),
                                    )
                                )

                        # Apply burn (object-style)
                        if effect == "burn":
                            # only apply if enemy not already burning
                            if getattr(enemy, "burn_timer", 0) <= 0:
                                enemy.burn_timer = burn_duration
                                enemy.burn_damage_per_second = burn_dps
                                enemy.burn_tick_counter = self.fps

                        # Handle projectile piercing / kill (object-style)
                        p_pierce_all = getattr(projectile, "pierce_all", False)
                        p_pierce_count = getattr(projectile, "pierce_count", 0)

                        if p_pierce_all:
                            pass
                        elif p_pierce_count > 0:
                            # decrement and persist on projectile object
                            projectile.pierce_count = (
                                getattr(projectile, "pierce_count", 0) - 1
                            )
                            p_pierce_count = projectile.pierce_count
                            if p_pierce_count <= 0:
                                try:
                                    projectile.kill()
                                except Exception:
                                    try:
                                        self.projectiles.remove(projectile)
                                    except Exception:
                                        pass
                        else:
                            try:
                                projectile.kill()
                            except Exception:
                                try:
                                    self.projectiles.remove(projectile)
                                except Exception:
                                    pass

                        # Death handling for enemies (object-style)
                        if getattr(enemy, "health", 0) <= 0:
                            self.add_score(
                                enemy.get("max_health", 10)
                                * 18
                                * self.difficulty_multiplier
                            )
                            type_xp_local = {
                                "weak": 10,
                                "normal": 16,
                                "strong": 25,
                                "giant": 50,
                                "angel": 22,
                            }
                            base_xp_local = type_xp_local.get(
                                str(enemy.get("type")), 12
                            )
                            self.player_xp += int(
                                round(
                                    base_xp_local * getattr(self, "xp_multiplier", 1.0)
                                )
                            )
                            if self.player_xp >= self.xp_to_next_level:
                                self.trigger_level_up()
                            # Ensure burn propagation happens on death regardless of damage source
                            try:
                                if (
                                    enemy.get("burn_propagate_on_death", False)
                                    or enemy.get("burn_propagate_hops", 0) > 0
                                ):
                                    try:
                                        self._propagate_burn(enemy)
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            try:
                                self.enemies.remove(enemy)
                            except ValueError:
                                pass

                        # Chain hits: storm projectiles can hit additional distinct enemies
                        if isinstance(projectile, dict):
                            chain = projectile.get("chain_targets", 0)
                        else:
                            chain = getattr(projectile, "chain_targets", 0)
                        if (
                            chain
                            and chain > 1
                            and not getattr(projectile, "_chain_applied", False)
                        ):
                            # Build a safe snapshot of nearby candidates (exclude the primary)
                            others = []
                            max_chain_distance = 300
                            for other in list(self.enemies):
                                if other is enemy:
                                    continue
                                if other.get("health", 0) <= 0:
                                    continue
                                dx_o = other.get("x", 0) - enemy.get("x", 0)
                                dy_o = other.get("y", 0) - enemy.get("y", 0)
                                dist = math.hypot(dx_o, dy_o)
                                if dist <= max_chain_distance:
                                    others.append((dist, other))
                            others.sort(key=lambda t: t[0])
                            to_chain = min(len(others), chain - 1)
                            chain_points = [(enemy.get("x", 0), enemy.get("y", 0))]
                            for targ_dist, targ in others[:to_chain]:
                                # Damage the target (secondary)
                                try:
                                    # dict chain: before damage
                                    pass
                                except Exception:
                                    pass
                                eff = self._player_damage_vs_burning(
                                    projectile, targ, p_damage
                                )
                                targ["health"] -= eff * 2
                                try:
                                    # dict chain: after damage
                                    pass
                                except Exception:
                                    pass
                                # Record this hit to prevent further hits from the same projectile
                                try:
                                    if not hasattr(projectile, "_hit_ids"):
                                        projectile._hit_ids = set()
                                    projectile._hit_ids.add(id(targ))
                                except Exception:
                                    pass
                                tx, ty = self._enemy_pos(targ)
                                chain_points.append((tx, ty))
                                if targ["health"] <= 0:
                                    self.add_score(
                                        targ.get("max_health", 10)
                                        * 18
                                        * self.difficulty_multiplier
                                    )
                                    base_xp = 12
                                    self.player_xp += int(
                                        round(
                                            base_xp
                                            * getattr(self, "xp_multiplier", 1.0)
                                        )
                                    )
                                    if self.player_xp >= self.xp_to_next_level:
                                        self.trigger_level_up()
                                    # Propagate burn on death even if killed by a weapon/projectile
                                    try:
                                        if (
                                            targ.get("burn_propagate_on_death", False)
                                            or targ.get("burn_propagate_hops", 0) > 0
                                        ):
                                            try:
                                                self._propagate_burn(targ)
                                            except Exception:
                                                pass
                                    except Exception:
                                        pass
                                    try:
                                        self.enemies.remove(targ)
                                    except Exception:
                                        pass
                            if len(chain_points) > 1:
                                self.game_state.chain_lightning_effects.append(
                                    {"points": chain_points, "timer": 8}
                                )
                                projectile._chain_applied = True
                                processed_projectile = True

                    else:
                        # Object-based enemy (sprite/instance)
                        try:
                            dmg_to_apply = self._player_damage_vs_burning(
                                projectile, enemy, p_damage
                            )
                            # Skip if this projectile already recorded a hit on this enemy
                            if id(enemy) in getattr(projectile, "_hit_ids", set()):
                                pass
                            else:
                                enemy.take_damage(dmg_to_apply)

                            # Remove storm projectiles on contact (apply chain immediately)
                            if (
                                getattr(projectile, "appearance", None)
                                == "storm_statue"
                            ):
                                try:
                                    chain = getattr(projectile, "chain_targets", 0)
                                    if (
                                        chain
                                        and chain > 1
                                        and not getattr(
                                            projectile, "_chain_applied", False
                                        )
                                    ):
                                        chain_points = [
                                            (
                                                self._enemy_pos(enemy)[0],
                                                self._enemy_pos(enemy)[1],
                                            )
                                        ]
                                        others = []
                                        max_chain_distance = 300
                                        for other in self._enemies_iter():
                                            if other is enemy:
                                                continue
                                            if getattr(other, "health", 0) <= 0:
                                                continue
                                            ox, oy = self._enemy_pos(other)
                                            exx, eyy = self._enemy_pos(enemy)
                                            dist = math.hypot(ox - exx, oy - eyy)
                                            if dist <= max_chain_distance:
                                                others.append((dist, other))
                                        others.sort(key=lambda t: t[0])
                                        to_chain = min(len(others), chain - 1)
                                        for i in range(to_chain):
                                            targ = others[i][1]
                                            try:
                                                eff = self._player_damage_vs_burning(
                                                    projectile, targ, p_damage
                                                )
                                                try:
                                                    LOG.debug(
                                                        "handle_collisions chain: proj_id=%s targ_id=%s pre_hit_ids=%s",
                                                        id(projectile),
                                                        id(targ),
                                                        getattr(
                                                            projectile, "_hit_ids", None
                                                        ),
                                                    )
                                                except Exception:
                                                    pass
                                                try:
                                                    targ.take_damage(eff * 2)
                                                    damaged = True
                                                except Exception:
                                                    try:
                                                        targ.health -= eff * 2
                                                        damaged = True
                                                    except Exception:
                                                        pass
                                                try:
                                                    LOG.debug(
                                                        "handle_collisions chain-done: proj_id=%s targ_id=%s post_hit_ids=%s",
                                                        id(projectile),
                                                        id(targ),
                                                        getattr(
                                                            projectile, "_hit_ids", None
                                                        ),
                                                    )
                                                except Exception:
                                                    pass
                                            except Exception:
                                                try:
                                                    eff = (
                                                        self._player_damage_vs_burning(
                                                            projectile, targ, p_damage
                                                        )
                                                    )
                                                    targ.health -= eff * 2
                                                except Exception:
                                                    pass
                                            except Exception:
                                                try:
                                                    eff = (
                                                        self._player_damage_vs_burning(
                                                            projectile, targ, p_damage
                                                        )
                                                    )
                                                    targ.health -= eff * 2
                                                except Exception:
                                                    pass
                                            tx, ty = self._enemy_pos(targ)
                                            chain_points.append((tx, ty))
                                        if len(chain_points) > 1:
                                            self.game_state.chain_lightning_effects.append(
                                                {"points": chain_points, "timer": 8}
                                            )
                                        projectile._chain_applied = True
                                except Exception:
                                    pass

                                try:
                                    projectile.kill()
                                except Exception:
                                    try:
                                        self.projectiles.remove(projectile)
                                    except Exception:
                                        pass
                        except Exception:
                            try:
                                enemy.health -= self._player_damage_vs_burning(
                                    projectile, enemy, p_damage
                                )
                            except Exception:
                                pass

                        # Record this hit so projectile won't hit the same enemy again
                        try:
                            if hit_ids is None:
                                if not hasattr(projectile, "_hit_ids"):
                                    projectile._hit_ids = set()
                                hit_ids = projectile._hit_ids
                            hit_ids.add(id(enemy))
                        except Exception:
                            pass

                        # Apply slow effect if projectile has it (Ice towers)
                        if effect == "slow":
                            if (
                                not hasattr(enemy, "slow_timer")
                                or getattr(enemy, "slow_timer", 0) <= 0
                            ):
                                enemy.slow_timer = slow_duration
                                enemy.slow_factor = slow_factor
                                if not hasattr(enemy, "original_speed"):
                                    enemy.original_speed = enemy.speed
                                enemy.speed = enemy.speed * enemy.slow_factor

                        # Apply burn effect (Fire towers)
                        if effect == "burn":
                            if (
                                not hasattr(enemy, "burn_timer")
                                or getattr(enemy, "burn_timer", 0) <= 0
                            ):
                                enemy.burn_timer = burn_duration
                                enemy.burn_damage_per_second = burn_dps
                                # Counter for per-second ticks
                                enemy.burn_tick_timer = getattr(self, "fps", 60)

                        # Handle projectile piercing / kill (support dict or object projectiles)
                        if p_pierce_all:
                            pass
                        elif p_pierce_count > 0:
                            # decrement and persist on projectile object (object-only)
                            projectile.pierce_count = (
                                getattr(projectile, "pierce_count", 0) - 1
                            )
                            p_pierce_count = projectile.pierce_count
                            if p_pierce_count <= 0:
                                try:
                                    projectile.kill()
                                except Exception:
                                    try:
                                        self.projectiles.remove(projectile)
                                    except Exception:
                                        pass
                        else:
                            try:
                                projectile.kill()
                            except Exception:
                                try:
                                    self.projectiles.remove(projectile)
                                except Exception:
                                    pass
                            else:
                                projectile.kill()

                        # Death handling for object enemies
                        if getattr(enemy, "health", 0) <= 0:
                            self.add_score(
                                enemy.max_health * 18 * self.difficulty_multiplier
                            )
                            type_xp_local = {
                                "weak": 10,
                                "normal": 16,
                                "strong": 25,
                                "giant": 50,
                                "angel": 22,
                            }
                            base_xp_local = type_xp_local.get(
                                str(enemy.enemy_type), 12
                            )  # fallback XP
                            self.player_xp += int(
                                round(
                                    base_xp_local * getattr(self, "xp_multiplier", 1.0)
                                )
                            )
                            if self.player_xp >= self.xp_to_next_level:
                                self.trigger_level_up()
                            # Ensure propagation fires even if enemy was killed by a weapon/projectile
                            try:
                                if (
                                    getattr(enemy, "burn_propagate_on_death", False)
                                    or getattr(enemy, "burn_propagate_hops", 0) > 0
                                ):
                                    try:
                                        # DIAG: log propagation call for sprite-based death
                                        LOG.debug(
                                            "_propagate_burn called from projectile-kill for sprite enemy; burn_propagate_on_death=%s, hops=%s",
                                            getattr(
                                                enemy, "burn_propagate_on_death", False
                                            ),
                                            getattr(enemy, "burn_propagate_hops", 0),
                                        )
                                        self._propagate_burn(enemy)
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                        try:
                            self.record_enemy_kill()
                        except Exception:
                            pass
                        # Chain hits: storm projectiles can hit additional distinct enemies
                        if isinstance(projectile, dict):
                            chain = projectile.get("chain_targets", 0)
                        else:
                            chain = getattr(projectile, "chain_targets", 0)
                        if (
                            chain
                            and chain > 1
                            and not getattr(projectile, "_chain_applied", False)
                        ):
                            others = []
                            # Gather other enemy candidates
                            for other in self._enemies_iter():
                                if other is enemy:
                                    continue
                                if getattr(other, "health", 0) <= 0:
                                    continue
                                ox, oy = self._enemy_pos(other)
                                exx, eyy = self._enemy_pos(enemy)
                                dist = math.hypot(ox - exx, oy - eyy)
                                others.append((dist, other))
                            others.sort(key=lambda t: t[0])
                            to_chain = min(len(others), chain - 1)

                            # Prepare visual chain points (always include primary)
                            chain_points = [
                                (self._enemy_pos(enemy)[0], self._enemy_pos(enemy)[1])
                            ]

                            for i in range(to_chain):
                                targ = others[i][1]
                                if isinstance(targ, dict):
                                    eff = self._player_damage_vs_burning(
                                        projectile, targ, p_damage
                                    )
                                    targ["health"] -= (
                                        eff * 2
                                    )  # Increased damage for secondary targets
                                    if targ["health"] <= 0:
                                        self.add_score(
                                            targ.get("max_health", 10)
                                            * 18
                                            * self.difficulty_multiplier
                                        )
                                        type_xp_local = {
                                            "weak": 10,
                                            "normal": 16,
                                            "strong": 25,
                                            "giant": 50,
                                            "angel": 22,
                                        }
                                        base_xp_local = type_xp_local.get(
                                            str(targ.get("type")), 12
                                        )
                                        self.player_xp += int(
                                            round(
                                                base_xp_local
                                                * getattr(self, "xp_multiplier", 1.0)
                                            )
                                        )
                                        if self.player_xp >= self.xp_to_next_level:
                                            self.trigger_level_up()
                                        try:
                                            try:
                                                self.record_enemy_kill()
                                            except Exception:
                                                pass
                                            self.enemies.remove(targ)
                                        except Exception:
                                            pass
                                else:
                                    try:
                                        eff = self._player_damage_vs_burning(
                                            projectile, targ, p_damage
                                        )
                                        targ.take_damage(
                                            eff * 2
                                        )  # Increased damage for secondary targets
                                    except Exception:
                                        try:
                                            eff = self._player_damage_vs_burning(
                                                projectile, targ, p_damage
                                            )
                                            targ.health -= (
                                                eff * 2
                                            )  # Increased damage for secondary targets
                                        except Exception:
                                            pass
                                    if getattr(targ, "health", 0) <= 0:
                                        self.add_score(
                                            targ.max_health
                                            * 18
                                            * self.difficulty_multiplier
                                        )
                                        type_xp_local = {
                                            "weak": 10,
                                            "normal": 16,
                                            "strong": 25,
                                            "giant": 50,
                                            "angel": 22,
                                        }
                                        base_xp_local = type_xp_local.get(
                                            targ.enemy_type, 12
                                        )
                                        self.player_xp += int(
                                            round(
                                                base_xp_local
                                                * getattr(self, "xp_multiplier", 1.0)
                                            )
                                        )
                                        if self.player_xp >= self.xp_to_next_level:
                                            self.trigger_level_up()
                                        try:
                                            self.record_enemy_kill()
                                        except Exception:
                                            pass
                                        targ.kill()

                                # add visual point for this chained target
                                tx, ty = self._enemy_pos(targ)
                                chain_points.append((tx, ty))

                            # append visual effect when we actually chained at least once
                            if len(chain_points) > 1:
                                self.game_state.chain_lightning_effects.append(
                                    {"points": chain_points, "timer": 8}
                                )
                            projectile._chain_applied = True
                            processed_projectile = True
                    break

            # Projectiles hit bosses (only for sprite projectiles)
            hit_bosses: List[Any] = []
            if hasattr(projectile, "rect"):
                hit_bosses = pygame.sprite.spritecollide(projectile, self.bosses, False)
            # Debug: show projectile -> boss collision detection (debug-level)
            try:
                LOG.debug(
                    "projectile.appearance=%s, projectile.effect=%s, hit_bosses_count=%s",
                    getattr(projectile, "appearance", None),
                    getattr(projectile, "effect", None),
                    len(hit_bosses),
                )
            except Exception:
                pass
            for boss in hit_bosses:
                # Skip if this projectile already hit this exact boss instance
                try:
                    LOG.debug(
                        "handle_collisions: processing boss hit. projectile.effect=%s, effect_var=%s",
                        getattr(projectile, "effect", None),
                        locals().get("effect", None),
                    )
                    if not hasattr(projectile, "_hit_ids"):
                        projectile._hit_ids = set()
                    hit_ids_local = projectile._hit_ids
                    if not hasattr(projectile, "_hit_boss_types"):
                        projectile._hit_boss_types = set()
                    hit_boss_types_local = projectile._hit_boss_types
                    if id(boss) in hit_ids_local or (
                        getattr(boss, "enemy_type", "") in hit_boss_types_local
                    ):
                        continue
                except Exception:
                    pass

                if boss.enemy_type == "boss_final" and self.selected_stage == "prologo":
                    if self.prologo_final_boss_immortal:
                        continue  # Invulnerable
                    else:
                        bd = self._player_damage_vs_burning(
                            projectile, boss, getattr(projectile, "damage", 0)
                        )
                        boss.take_damage(bd)
                        if boss.health <= boss.max_health * 0.1:
                            self.prologo_final_boss_immortal = True
                            boss.health = int(boss.max_health * 0.1)
                else:
                    bd = self._player_damage_vs_burning(
                        projectile, boss, getattr(projectile, "damage", 0)
                    )
                    boss.take_damage(bd)

                # Ensure projectiles that carry slow/burn also apply to bosses (defensive/duplicate path)
                try:
                    if getattr(projectile, "effect", None) == "slow":
                        # apply slow metadata directly from projectile as a defensive path
                        try:
                            if (
                                not hasattr(boss, "slow_timer")
                                or getattr(boss, "slow_timer", 0) <= 0
                            ):
                                boss.slow_timer = getattr(
                                    projectile, "slow_duration", 120
                                )
                                boss.slow_factor = getattr(
                                    projectile, "slow_factor", 0.5
                                )
                                if not hasattr(boss, "original_speed"):
                                    boss.original_speed = boss.speed
                                boss.speed = boss.speed * boss.slow_factor
                        except Exception:
                            pass
                    if getattr(projectile, "effect", None) == "burn":
                        # Only apply burn if not already burning
                        if (
                            not hasattr(boss, "burn_timer")
                            or getattr(boss, "burn_timer", 0) <= 0
                        ):
                            boss.burn_timer = burn_duration
                            boss.burn_damage_per_second = burn_dps
                            boss.burn_tick_timer = getattr(self, "fps", 60)
                            # If FIRE tier 1 is active, mark this burn to propagate on death
                            try:
                                if self.permanent_stats.get("fire_1", 0):
                                    boss.burn_propagate_on_death = True
                                    boss.burn_propagate_radius = 150
                                    boss.burn_propagate_dps = burn_dps
                                    boss.burn_propagate_duration = burn_duration
                                    boss.burn_propagate_hops = 2
                            except Exception:
                                pass
                    elif getattr(projectile, "effect", None) == "slow":
                        if (
                            not hasattr(boss, "slow_timer")
                            or getattr(boss, "slow_timer", 0) <= 0
                        ):
                            boss.slow_timer = slow_duration
                            boss.slow_factor = slow_factor
                            if not hasattr(boss, "original_speed"):
                                boss.original_speed = boss.speed
                            boss.speed = boss.speed * boss.slow_factor
                except Exception:
                    pass

                # Fallback: ensure slow from projectiles is applied to bosses even if
                # the primary code path above was skipped due to an edge-case.
                try:
                    if (
                        getattr(projectile, "effect", None) == "slow"
                        and getattr(boss, "slow_timer", 0) <= 0
                    ):
                        boss.slow_timer = getattr(projectile, "slow_duration", 120)
                        boss.slow_factor = getattr(projectile, "slow_factor", 0.5)
                        if not hasattr(boss, "original_speed"):
                            boss.original_speed = boss.speed
                        boss.speed = boss.speed * boss.slow_factor
                except Exception:
                    pass
                # Record that this projectile has hit this boss/type so it won't hit again
                try:
                    if not hasattr(projectile, "_hit_ids"):
                        projectile._hit_ids = set()
                    projectile._hit_ids.add(id(boss))
                    if not hasattr(projectile, "_hit_boss_types"):
                        projectile._hit_boss_types = set()
                    projectile._hit_boss_types.add(getattr(boss, "enemy_type", ""))
                except Exception:
                    pass

                # Handle projectile piercing for bosses too
                # NOTE: Spears should not pierce bosses — treat spear as single-hit for bosses
                if (
                    getattr(projectile, "pierce_all", False)
                    and getattr(projectile, "weapon_type", None) != "spear"
                ):
                    # Non-spear projectiles that pierce may continue through bosses
                    pass
                elif getattr(projectile, "pierce_count", 0) > 0:
                    projectile.pierce_count -= 1
                    if projectile.pierce_count <= 0:
                        projectile.kill()
                else:
                    # Default: remove projectile after hitting a boss (also covers spear)
                    projectile.kill()

                if boss.health <= 0:
                    self.add_score(boss.max_health * 25)
                    # Give XP for boss kill (per-type table, flat values)
                    boss_xp_map: Dict[str, int] = {
                        "medium": 80,
                        "big": 150,
                        "final": 400,
                    }
                    boss_base_xp: int = boss_xp_map.get(
                        boss.enemy_type.replace("boss_", ""), 100
                    )
                    self.player_xp += int(
                        round(boss_base_xp * getattr(self, "xp_multiplier", 1.0))
                    )
                    if self.player_xp >= self.xp_to_next_level:
                        self.trigger_level_up()
                    boss.kill()  # Remove dead boss
                    if boss.enemy_type == "boss_medium":
                        self.show_centered_message(
                            "REINFORCEMENTS INCOMING!", 1800, (255, 204, 0)
                        )
                        # Clear any existing reinforcement timer and schedule new one
                        pygame.time.set_timer(pygame.USEREVENT + 1, 0)
                        pygame.time.set_timer(
                            pygame.USEREVENT + 1, self.reinforcement_delay_ms
                        )
                    elif (
                        boss.enemy_type == "boss_final"
                        and not self.prologo_final_boss_immortal
                    ):
                        self.prologo_final_boss_defeated = True
                break

            # Chain hits for bosses: storm projectiles can hit additional distinct enemies
            if hit_bosses:
                primary_boss = hit_bosses[0]  # First boss hit
                chain = getattr(projectile, "chain_targets", 0)
                if chain and chain > 1:
                    others = []
                    # Gather other enemy candidates within chain range (both enemies and bosses)
                    max_chain_distance = (
                        300  # Maximum distance for chain lightning (pixels)
                    )

                    # Check other bosses
                    for other_boss in self.bosses.sprites():
                        if other_boss is primary_boss:
                            continue
                        if getattr(other_boss, "health", 0) <= 0:
                            continue
                        bx, by = self._enemy_pos(other_boss)
                        px, py = self._enemy_pos(primary_boss)
                        dist = math.hypot(bx - px, by - py)
                        if dist <= max_chain_distance:
                            others.append((dist, other_boss))

                    # Check regular enemies
                    for other_enemy in self.enemies.sprites():
                        if getattr(other_enemy, "health", 0) <= 0:
                            continue
                        ex, ey = self._enemy_pos(other_enemy)
                        px, py = self._enemy_pos(primary_boss)
                        dist = math.hypot(ex - px, ey - py)
                        if dist <= max_chain_distance:
                            others.append((dist, other_enemy))

                    others.sort(key=lambda t: t[0])
                    to_chain = min(len(others), chain - 1)

                    # Store chain lightning effect for visual
                    chain_points = [
                        (
                            self._enemy_pos(primary_boss)[0],
                            self._enemy_pos(primary_boss)[1],
                        )
                    ]

                    for i in range(to_chain):
                        targ = others[i][1]
                        eff = self._player_damage_vs_burning(
                            projectile, targ, getattr(projectile, "damage", 0)
                        )
                        targ.take_damage(
                            eff * 2
                        )  # Increased damage for secondary targets

                        # Add to chain points for visual effect
                        tx, ty = self._enemy_pos(targ)
                        chain_points.append((tx, ty))

                        # death handling for chained targets
                        if targ.health <= 0:
                            if hasattr(
                                targ, "enemy_type"
                            ) and targ.enemy_type.startswith("boss_"):
                                # Boss death handling
                                self.add_score(targ.max_health * 25)
                                boss_xp_map = {
                                    "medium": 80,
                                    "big": 150,
                                    "final": 400,
                                }
                                boss_base_xp = boss_xp_map.get(
                                    targ.enemy_type.replace("boss_", ""), 100
                                )
                                self.player_xp += int(
                                    round(
                                        boss_base_xp
                                        * getattr(self, "xp_multiplier", 1.0)
                                    )
                                )
                                if self.player_xp >= self.xp_to_next_level:
                                    self.trigger_level_up()
                                targ.kill()
                            else:
                                # Regular enemy death handling
                                self.add_score(
                                    targ.max_health * 18 * self.difficulty_multiplier
                                )
                                type_xp_local = {
                                    "weak": 10,
                                    "normal": 16,
                                    "strong": 25,
                                    "giant": 50,
                                    "angel": 22,
                                }
                                base_xp_local = type_xp_local.get(targ.enemy_type, 12)
                                self.player_xp += int(
                                    round(
                                        base_xp_local
                                        * getattr(self, "xp_multiplier", 1.0)
                                    )
                                )
                                if self.player_xp >= self.xp_to_next_level:
                                    self.trigger_level_up()
                                targ.kill()
                                if self.player_xp >= self.xp_to_next_level:
                                    self.trigger_level_up()
                                targ.kill()

                    # Add chain lightning effect to game state
                    if len(chain_points) > 1:
                        self.game_state.chain_lightning_effects.append(
                            {"points": chain_points, "timer": 8}  # Show for 8 frames
                        )
                        # Mark chain applied so we don't duplicate
                        projectile._chain_applied = True
        hit_projectiles: List[Any] = pygame.sprite.spritecollide(
            self.player, self.enemy_projectiles, False
        )
        for projectile in hit_projectiles:
            actual_damage = projectile.damage * self.damage_reduction_multiplier
            self.player.take_damage(actual_damage)
            # Apply slow effect to player if projectile carries it
            try:
                if getattr(projectile, "effect", None) == "slow":
                    slow_duration = getattr(projectile, "slow_duration", 120)
                    slow_factor = getattr(projectile, "slow_factor", 0.5)
                    if (
                        not hasattr(self.player, "slow_timer")
                        or getattr(self.player, "slow_timer", 0) <= 0
                    ):
                        self.player.slow_timer = slow_duration
                        self.player.slow_factor = slow_factor
                        if not hasattr(self.player, "original_speed"):
                            self.player.original_speed = self.player.speed
                        self.player.speed = self.player.speed * self.player.slow_factor
            except Exception:
                pass

            # Trigger screen & player shake
            self.shake_timer = 8
            self.shake_intensity = max(self.shake_intensity, 8)
            projectile.kill()

        # Enemies hit player
        if hasattr(self.enemies, "sprites"):
            hit_enemies = pygame.sprite.spritecollide(self.player, self.enemies, False)
            for enemy in hit_enemies:
                actual_damage = (
                    enemy.damage / self.fps
                ) * self.damage_reduction_multiplier
                self.player.take_damage(actual_damage)
                contact_damage_to_enemy: float = 2.0 / self.fps
                enemy.take_damage(contact_damage_to_enemy, show_floating=False)
                if self.frame_count % 10 == 0:
                    # Shorter, weaker shake for contact
                    self.shake_timer = 6
                    self.shake_intensity = max(self.shake_intensity, 6)

                    # Spawn burn particles on both enemy and player to show fiery contact (increased visibility)
                    try:
                        # Enemy particles (sprite) - slightly more and larger/longer-lived
                        for _ in range(random.randint(3, 6)):
                            vx = random.uniform(-30, 30)
                            vy = random.uniform(15, 40)
                            p_burn_enemy = BurnParticle(
                                enemy.x + random.uniform(-8, 8),
                                enemy.y - 8 + random.uniform(-4, 4),
                                vx,
                                vy,
                                life=random.randint(18, 44),
                                size=random.randint(3, 5),
                            )
                            try:
                                enemy.burn_particles.append(p_burn_enemy)
                            except Exception:
                                pass
                        # Player particles - same stronger effect
                        if not hasattr(self.player, "burn_particles"):
                            self.player.burn_particles = []
                        for _ in range(random.randint(3, 6)):
                            vx = random.uniform(-30, 30)
                            vy = random.uniform(15, 40)
                            p_burn_player_local = BurnParticle(
                                self.player.x + random.uniform(-16, 16),
                                self.player.y - 8 + random.uniform(-4, 4),
                                vx,
                                vy,
                                life=random.randint(18, 44),
                                size=random.randint(3, 5),
                            )
                            self.player.burn_particles.append(p_burn_player_local)
                    except Exception:
                        pass

                # Armor spine effect
                if self.upgrade_levels.get("armor", 0) > 0:
                    reflect_ratio: float = min(0.3 * self.upgrade_levels["armor"], 0.9)
                    reflected = actual_damage * reflect_ratio
                    enemy.take_damage(reflected, show_floating=False)
                    # Visual effect: draw red spikes from player to enemy
                    if getattr(enemy, "spine_timer", 0) <= 0:
                        enemy.spine_timer = 4  # show for 4 frames
                    if not hasattr(enemy, "spine_from") or enemy.spine_from is None:
                        enemy.spine_from = [self.player.x, self.player.y]
        else:
            for enemy in list(self.enemies):
                ex, ey = self._enemy_pos(enemy)
                er = self._enemy_radius(enemy)
                dx = ex - self.player.x
                dy = ey - self.player.y
                if dx * dx + dy * dy <= (er + (self.player.width // 2)) ** 2:
                    actual_damage = (
                        getattr(enemy, "damage", 5) / self.fps
                    ) * self.damage_reduction_multiplier
                    self.player.take_damage(actual_damage)
                    contact_damage_to_enemy = 2.0 / self.fps
                    # Object-style enemy damage on contact
                    try:
                        enemy.take_damage(contact_damage_to_enemy, show_floating=False)
                    except Exception:
                        # Best-effort fallback to attribute mutation
                        try:
                            enemy.health = max(
                                0, getattr(enemy, "health", 0) - contact_damage_to_enemy
                            )
                        except Exception:
                            pass
                    if self.frame_count % 10 == 0:
                        # Shorter, weaker shake for contact
                        self.shake_timer = 6
                        self.shake_intensity = max(self.shake_intensity, 6)

                        # Enemy instance: append BurnParticle objects
                        try:
                            if not hasattr(enemy, "burn_particles"):
                                enemy.burn_particles = []
                            for _ in range(random.randint(3, 6)):
                                vx = random.uniform(-30, 30)
                                vy = random.uniform(15, 40)
                                from src.entities.enemy import BurnParticle as _BP

                                p = _BP(
                                    enemy.x + random.uniform(-8, 8),
                                    enemy.y - 8 + random.uniform(-4, 4),
                                    vx,
                                    vy,
                                    life=random.randint(18, 44),
                                    size=random.randint(3, 5),
                                )
                                enemy.burn_particles.append(p)
                        except Exception:
                            pass

                        # Player particles
                        try:
                            if not hasattr(self.player, "burn_particles"):
                                self.player.burn_particles = []
                            for _ in range(random.randint(2, 4)):
                                vx = random.uniform(-20, 20)
                                vy = random.uniform(10, 30)
                                from src.entities.enemy import BurnParticle as _BP

                                p = _BP(
                                    self.player.x + random.uniform(-12, 12),
                                    self.player.y - 8 + random.uniform(-2, 2),
                                    vx,
                                    vy,
                                    life=random.randint(12, 30),
                                    size=random.randint(2, 4),
                                )
                                self.player.burn_particles.append(p)
                        except Exception:
                            pass

                    # Armor spine effect (best-effort for dicts)
                    if self.upgrade_levels.get("armor", 0) > 0:
                        reflect_ratio = min(0.3 * self.upgrade_levels["armor"], 0.9)
                        reflected = actual_damage * reflect_ratio
                        if not isinstance(enemy, dict):
                            enemy.take_damage(reflected, show_floating=False)
                        if (
                            not isinstance(enemy, dict)
                            and getattr(enemy, "spine_timer", 0) <= 0
                        ):
                            enemy.spine_timer = 4
                        if (
                            not isinstance(enemy, dict)
                            and not hasattr(enemy, "spine_from")
                            or getattr(enemy, "spine_from", None) is None
                        ):
                            enemy.spine_from = [self.player.x, self.player.y]
        # Bosses hit player
        hit_bosses = pygame.sprite.spritecollide(self.player, self.bosses, False)
        for boss in hit_bosses:
            contact_damage = (boss.damage / self.fps) * self.damage_reduction_multiplier
            self.player.take_damage(contact_damage)
            if self.frame_count % 10 == 0:
                # Boss contact should produce a noticeable shake
                self.shake_timer = 6
                self.shake_intensity = max(self.shake_intensity, 6)

        # Update soul drain effects on enemies
        for enemy in list(self.enemies):
            if hasattr(enemy, "drain_timer") and enemy.drain_timer > 0:
                enemy.drain_timer -= 1
                if enemy.drain_timer % 60 == 0:  # Every second
                    damage = getattr(enemy, "drain_damage", 1)
                    heal = getattr(enemy, "drain_heal", 1)
                    enemy.take_damage(damage)
                    # spawn centralized floating text for drain tick
                    try:
                        ex, ey = self._enemy_pos(enemy)
                        self.spawn_floating_text(
                            str(int(damage)), ex, ey - self._enemy_radius(enemy) - 8
                        )
                    except Exception:
                        pass
                    self.player.health = min(
                        self.player.max_health, self.player.health + heal
                    )
                if enemy.drain_timer <= 0:
                    # Remove drain attributes
                    if hasattr(enemy, "drain_timer"):
                        delattr(enemy, "drain_timer")
                    if hasattr(enemy, "drain_damage"):
                        delattr(enemy, "drain_damage")
                    if hasattr(enemy, "drain_heal"):
                        delattr(enemy, "drain_heal")
                    if hasattr(enemy, "drain_source"):
                        delattr(enemy, "drain_source")

        # If enemies is a plain list, update drain timers for object enemies
        if not hasattr(self.enemies, "update"):
            for enemy in list(self.enemies):
                if getattr(enemy, "drain_timer", 0) > 0:
                    enemy.drain_timer -= 1
                    if enemy.drain_timer % 60 == 0:
                        damage = getattr(enemy, "drain_damage", 1)
                        heal = getattr(enemy, "drain_heal", 1)
                        try:
                            enemy.take_damage(damage)
                        except Exception:
                            try:
                                enemy.health = max(
                                    0, getattr(enemy, "health", 0) - damage
                                )
                            except Exception:
                                pass
                        try:
                            ex, ey = self._enemy_pos(enemy)
                            self.spawn_floating_text(
                                str(int(damage)), ex, ey - self._enemy_radius(enemy) - 8
                            )
                        except Exception:
                            pass
                        self.player.health = min(
                            self.player.max_health, self.player.health + heal
                        )
                    if enemy.drain_timer <= 0:
                        for attr in (
                            "drain_timer",
                            "drain_damage",
                            "drain_heal",
                            "drain_source",
                        ):
                            if hasattr(enemy, attr):
                                try:
                                    delattr(enemy, attr)
                                except Exception:
                                    pass

        # Update spine timers
        for enemy in self.enemies:
            if hasattr(enemy, "spine_timer") and enemy.spine_timer > 0:
                enemy.spine_timer -= 1
                if enemy.spine_timer <= 0:
                    enemy.spine_from = None

        # Update slow timers for all enemies
        for enemy in self.enemies:
            if hasattr(enemy, "slow_timer") and getattr(enemy, "slow_timer", 0) > 0:
                enemy.slow_timer -= 1
                if enemy.slow_timer <= 0:
                    # Reset slow_factor for enemy objects
                    if hasattr(enemy, "slow_factor"):
                        enemy.slow_factor = 1.0
                    # Reset speed if original_speed was saved
                    if hasattr(enemy, "original_speed"):
                        enemy.speed = getattr(enemy, "original_speed", enemy.speed)
                        delattr(enemy, "original_speed")

        # Update slow timers for bosses
        if hasattr(self, "bosses") and self.bosses:
            for boss in self.bosses:
                if hasattr(boss, "slow_timer") and getattr(boss, "slow_timer", 0) > 0:
                    boss.slow_timer -= 1
                    if boss.slow_timer <= 0:
                        # Reset slow_factor for bosses
                        if hasattr(boss, "slow_factor"):
                            boss.slow_factor = 1.0
                        # Reset speed if original_speed was saved
                        if hasattr(boss, "original_speed"):
                            boss.speed = getattr(boss, "original_speed", boss.speed)
                            if hasattr(boss, "original_speed"):
                                delattr(boss, "original_speed")

        # Orbitals damage enemies on contact
        if "orbital" in self.player_weapons:
            for orbital in self.orbitals:
                ox = orbital.get("x", self.player.x)
                oy = orbital.get("y", self.player.y)
                for enemy in self._enemies_iter():
                    ex, ey = self._enemy_pos(enemy)
                    dist = math.hypot(ex - ox, ey - oy)
                    if dist < enemy.radius + 6:  # orbital radius is 6
                        enemy.take_damage(1.0 / self.fps)  # slight damage per frame
                for boss in self.bosses:
                    dist = math.hypot(boss.x - ox, boss.y - oy)
                    if dist < boss.radius + 6:
                        boss.take_damage(1.0 / self.fps)

        # Check for level up
        if self.player_xp >= self.xp_to_next_level:
            self.trigger_level_up()

    def trigger_level_up(self) -> None:
        """Pause game and show upgrade choices"""
        # Determine what choices to show based on current level before incrementing
        # (previously stored 'current_level' was unused and removed)

        self.player_xp -= self.xp_to_next_level
        self.player_level += 1
        # XP curve: XP_BASE * (XP_GROWTH ^ (level - 1))
        self.xp_to_next_level = int(XP_BASE * (XP_GROWTH ** (self.player_level - 1)))

        # Levels 3 and 6: weapon choices (new weapons + upgrades if available)
        if self.player_level in [3, 6]:
            self.awaiting_upgrade = False
            self.awaiting_weapon_choice = True
            self.weapon_choices = self.generate_weapon_choices()

            # At level 6 we explicitly show only new weapons (no upgrades)
            # For levels >6 weapon upgrades can still be added by other logic if desired.

            # If no weapon choices available, fall back to normal upgrades
            if not self.weapon_choices:
                self.awaiting_weapon_choice = False
                self.awaiting_upgrade = True
                self.upgrade_choices = self.generate_upgrade_choices()
                self.selected_upgrade_index = 0
            else:
                self.selected_weapon_index = 0

            self.paused = True
        else:
            # Levels 1, 2, 4, 5, 7+: normal upgrades + base weapon upgrade + weapon upgrades when available
            self.awaiting_weapon_choice = False
            self.awaiting_upgrade = True
            self.upgrade_choices = self.generate_upgrade_choices()
            self.selected_upgrade_index = 0
            self.paused = True

        # --- Keep GameStateManager in sync so UI renders selection screens correctly ---
        try:
            gs: Any | None = getattr(self, "game_state", None)
            if gs is not None:
                gs.player_xp = self.player_xp
                gs.player_level = self.player_level
                gs.xp_to_next_level = self.xp_to_next_level

                gs.awaiting_weapon_choice = self.awaiting_weapon_choice
                gs.awaiting_upgrade = self.awaiting_upgrade
                gs.weapon_choices = (
                    list(self.weapon_choices) if hasattr(self, "weapon_choices") else []
                )
                gs.upgrade_choices = (
                    list(self.upgrade_choices)
                    if hasattr(self, "upgrade_choices")
                    else []
                )
                gs.weapon_choice_index = getattr(self, "selected_weapon_index", 0)
                gs.upgrade_choice_index = getattr(self, "selected_upgrade_index", 0)
        except Exception:
            # Keep level-up resilient; UI may still show default behavior
            pass

    def generate_upgrade_choices(self):
        """Generate 3 random upgrade choices of different types"""

        # Define upgrade patterns inline
        def get_upgrade_patterns():
            return [
                {
                    "id": "damage",
                    "name": "Damage +10%",
                    "description": "Increase damage by 10%",
                    "apply": lambda self=self: setattr(
                        self, "player_damage", int(self.player_damage * 1.1)
                    ),
                },
                {
                    "id": "fire_rate",
                    "name": "Fire Rate +10%",
                    "description": "Increase fire rate by 10%",
                    "apply": lambda self=self: setattr(
                        self, "fire_rate_multiplier", self.fire_rate_multiplier * 1.1
                    ),
                },
                {
                    "id": "max_health",
                    "name": "Max Health +20",
                    "description": "Increase maximum health by 20",
                    "apply": lambda self=self: (
                        setattr(self.player, "max_health", self.player.max_health + 20),
                        setattr(self.player, "health", self.player.health + 20),
                    ),
                },
                {
                    "id": "projectile_size",
                    "name": "Projectile Size +10%",
                    "description": "Increase projectile size by 10%",
                    "apply": lambda self=self: setattr(
                        self,
                        "projectile_size_multiplier",
                        self.projectile_size_multiplier * 1.1,
                    ),
                },
                {
                    "id": "armor",
                    "name": "Armor +5%",
                    "description": "Reduce damage taken by 5%",
                    "apply": lambda self=self: setattr(
                        self,
                        "damage_reduction_multiplier",
                        self.damage_reduction_multiplier * 0.95,
                    ),
                },
            ]

        def get_weapon_upgrade_patterns(game):
            weapon_upgrades = []
            # Generate upgrades for each owned weapon
            for weapon_id in game.player_weapons:
                current_level: int = game.weapon_levels.get(weapon_id, 0)
                max_level: int = getattr(
                    game,
                    "max_weapon_level",
                    WEAPON_DEFS.get(weapon_id, {}).get("max_level", 6),
                )
                if current_level < max_level:
                    weapon_names: Dict[str, str] = {
                        "shotgun": "Hellgun",
                        "orbital": "Orbitals",
                        "spear": "Spear",
                        "skull_bomb": "Skull Bomb",
                        "beast": "The number of the beast",
                    }
                    weapon_name: str = weapon_names.get(weapon_id, weapon_id.title())
                    upgrade_name: str = f"{weapon_name} Lv.{current_level + 1}"
                    upgrade_desc: str = (
                        f"Upgrade {weapon_name} to level {current_level + 1}"
                    )
                    weapon_upgrades.append(
                        {
                            "id": f"{weapon_id}_upgrade",
                            "name": upgrade_name,
                            "description": upgrade_desc,
                            "apply": lambda w=weapon_id: game.apply_weapon(
                                f"{w}_upgrade"
                            ),
                        }
                    )
            return weapon_upgrades

        all_upgrades = get_upgrade_patterns()

        # Group upgrades by their type/id to ensure variety
        upgrade_groups = {}
        for upgrade in all_upgrades:
            upgrade_id = upgrade["id"]
            if upgrade_id not in upgrade_groups:
                upgrade_groups[upgrade_id] = []
            upgrade_groups[upgrade_id].append(upgrade)

        # Convert to the format expected by the Pygame version
        processed_upgrades = []
        for upgrade_id, upgrades in upgrade_groups.items():
            # Randomly select one upgrade from each type

            selected_upgrade = random.choice(upgrades)
            processed_upgrades.append(
                {
                    "id": selected_upgrade["id"],
                    "name": selected_upgrade["name"],
                    "description": selected_upgrade["description"],
                    "apply": lambda u=selected_upgrade: u["apply"](self),
                }
            )

        # Add weapon upgrades if available (always include when available)
        weapon_upgrades = get_weapon_upgrade_patterns(self)
        if weapon_upgrades:
            # Convert weapon upgrades to the expected format
            for upgrade in weapon_upgrades:
                processed_upgrades.append(
                    {
                        "id": upgrade["id"],
                        "name": upgrade["name"],
                        "description": upgrade["description"],
                        "apply": upgrade["apply"],
                    }
                )

        # Randomly select 3 upgrades from all available (normal + weapon upgrades)
        choices = random.sample(processed_upgrades, min(3, len(processed_upgrades)))

        return choices

    def generate_initial_weapon_choices(self):
        """Delegate to GameStateManager for initial weapon choices."""
        try:
            return self.game_state.generate_initial_weapon_choices()
        except Exception:
            # Fallback local generation (rare)
            initial_weapons: List[Dict[str, str]] = [
                {
                    "id": "shotgun",
                    "name": "Hellgun",
                    "description": "Fires multiple pellets in a spread pattern",
                },
                {
                    "id": "orbital",
                    "name": "Orbitals",
                    "description": "Summon orbiting sentinels that auto-fire",
                },
                {
                    "id": "spear",
                    "name": "Spear",
                    "description": "Pierces through multiple enemies",
                },
                {
                    "id": "beast",
                    "name": "The number of the beast",
                    "description": "Unleash demonic power with devastating attacks",
                },
                {
                    "id": "Soul Drain",
                    "name": "Soul Drain",
                    "description": "Fires homing soul projectiles that drain life from enemies and heal the player",
                },
            ]
            choices: List[Dict[str, str]] = random.sample(
                initial_weapons, min(3, len(initial_weapons))
            )
            return [
                {"id": c["id"], "name": c["name"], "description": c["description"]}
                for c in choices
            ]

    def generate_weapon_choices(self):
        """Generate weapon choices"""

        # Use centralized weapon definitions
        all_weapons: List[Dict[str, str]] = get_weapon_definitions()
        all_weapon_ids = [w["id"] for w in all_weapons]

        # At player level 6 we must *always* propose 3 new weapons (no upgrades)
        if getattr(self, "player_level", None) == 6:
            # Respect `available_from` even when offering level‑6 acquisition choices.
            unowned = [w for w in all_weapon_ids if w not in self.player_weapons]

            # Filter unowned list by availability for current stage
            def _is_available_for_stage(wid: str) -> bool:
                wdef = WEAPON_DEFS.get(wid, {})
                available_from = wdef.get("available_from")
                if not available_from:
                    return True
                af = str(available_from).lower()
                if af == "purgatory":
                    return bool(
                        self.selected_stage
                        and str(self.selected_stage).startswith(("purgatory", "hell"))
                    )
                if af == "limbo":
                    return bool(
                        self.selected_stage and str(self.selected_stage) != "prologo"
                    )
                return True

            filtered_unowned = [w for w in unowned if _is_available_for_stage(w)]

            choices: List[Dict[str, str]] = []
            if filtered_unowned:
                # If fewer than 3 unowned weapons, sample with replacement to reach 3
                if len(filtered_unowned) >= 3:
                    selected = random.sample(filtered_unowned, 3)
                else:
                    selected = [random.choice(filtered_unowned) for _ in range(3)]
                for weapon in selected:
                    choices.append(
                        {
                            "id": f"acquire_{weapon}",
                            "name": WEAPON_DEFS[weapon]["name"],
                            "description": WEAPON_DEFS[weapon]["description"],
                        }
                    )
            else:
                # No unowned weapons available for this stage: fallback to picking (with replacement)
                # from the set of weapons that are allowed in this stage.
                allowed = [w for w in all_weapon_ids if _is_available_for_stage(w)]
                if not allowed:
                    allowed = all_weapon_ids
                selected = [random.choice(allowed) for _ in range(3)]
                for weapon in selected:
                    choices.append(
                        {
                            "id": f"acquire_{weapon}",
                            "name": WEAPON_DEFS.get(weapon, {}).get("name", weapon),
                            "description": WEAPON_DEFS.get(weapon, {}).get(
                                "description", ""
                            ),
                        }
                    )
            return choices[:3]

        # Default behavior (non-level-6): offer up to 3 new weapon choices
        # Convert to the format expected by the Pygame version
        all_weapons = [
            {
                "id": weapon["id"],
                "name": weapon["name"],
                "description": weapon["description"],
                "apply": lambda w=weapon["id"]: self.apply_weapon(w),
            }
            for weapon in all_weapons
        ]

        # Filter out weapons the player already has or if at max capacity
        available_weapons: List[Dict[str, str]] = []
        for w in all_weapons:
            wid = w["id"]
            if wid in self.player_weapons:
                continue
            # Respect optional 'available_from' in WEAPON_DEFS (e.g. Purgatory-only weapons)
            wdef = WEAPON_DEFS.get(wid, {})
            available_from = wdef.get("available_from")
            if available_from:
                af = str(available_from).lower()
                # Purgatory-only weapons (also allowed in HELL)
                if af == "purgatory":
                    if not (
                        self.selected_stage
                        and str(self.selected_stage).startswith(("purgatory", "hell"))
                    ):
                        continue
                # Limbo-or-later weapons (not available in Prologo)
                if af == "limbo":
                    # require that we're NOT in prologo; accept limbo, limbo_2, purgatory, etc.
                    if not (
                        self.selected_stage and str(self.selected_stage) != "prologo"
                    ):
                        continue
            available_weapons.append(w)

        # If player already has max weapons, don't offer new weapons
        if len(self.player_weapons) >= self.max_extra_weapons:
            available_weapons = []

        # If no new weapons available, return empty list
        if not available_weapons:
            return []

        # Return up to 3 weapon choices

        return random.sample(available_weapons, min(3, len(available_weapons)))

    def generate_weapon_upgrade_choices(self):
        """Generate weapon upgrade choices for owned weapons"""
        weapon_upgrades = []

        # Generate upgrades for each owned weapon
        for weapon_id in self.player_weapons:
            current_level: int = self.weapon_levels.get(weapon_id, 0)
            max_level: int = getattr(
                self,
                "max_weapon_level",
                WEAPON_DEFS.get(weapon_id, {}).get("max_level", 6),
            )  # Default max level

            if current_level < max_level:
                weapon_name: str = WEAPON_DEFS.get(weapon_id, {}).get(
                    "name", weapon_id.title()
                )
                upgrade_name: str = f"{weapon_name} Lv.{current_level + 1}"
                upgrade_desc: str = get_weapon_upgrade_description(
                    weapon_id, current_level + 1
                )

                weapon_upgrades.append(
                    {
                        "id": f"{weapon_id}_upgrade",
                        "name": upgrade_name,
                        "description": upgrade_desc,
                        "weapon_id": weapon_id,
                    }
                )

        # Return up to 2 weapon upgrade choices
        return random.sample(weapon_upgrades, min(2, len(weapon_upgrades)))

    def apply_weapon(self, weapon_id) -> None:
        """Apply a weapon or weapon upgrade

        Supports three id forms:
        - "{weapon}_upgrade" to upgrade an owned weapon
        - "acquire_{weapon}" to acquire a new weapon (used in level-6 choices)
        - "{weapon}" to directly acquire a weapon (legacy)
        """
        # Normalize acquisition id (acquire_xxx)
        if isinstance(weapon_id, str) and weapon_id.startswith("acquire_"):
            weapon_id = weapon_id.replace("acquire_", "")

        # Check if this is a weapon upgrade
        if weapon_id.endswith("_upgrade"):
            base_weapon_id = weapon_id.replace("_upgrade", "")
            if base_weapon_id in self.player_weapons:
                # Upgrade existing weapon
                current_level: int = self.weapon_levels.get(base_weapon_id, 0)
                self.weapon_levels[base_weapon_id] = current_level + 1

                # Special handling for orbital upgrades
                if base_weapon_id == "orbital":
                    self.orbital_count = get_orbital_count(
                        self.weapon_levels["orbital"]
                    )
                    self.create_orbitals()

                logger.info(
                    f"Upgraded {base_weapon_id} to level {self.weapon_levels[base_weapon_id]}"
                )
        elif (
            weapon_id not in self.player_weapons
            and len(self.player_weapons) < self.max_extra_weapons
        ):
            # Acquire new weapon
            self.player_weapons.append(weapon_id)
            self.weapon_levels[weapon_id] = 1
            self.game_state.player_weapons = self.player_weapons.copy()
            self.game_state.weapon_levels = self.weapon_levels.copy()
            if weapon_id == "orbital":
                self.orbital_count = 3
                self.create_orbitals()

        # Resume the game (but keep game paused if a tower choice is pending)
        self.awaiting_weapon_choice = False
        if not (
            getattr(self, "is_initial_tower_choice", False)
            or getattr(self, "awaiting_tower_choice", False)
        ):
            # Only unpause if there is no tower selection pending
            self.paused = False
        # Sync weapon state into GameStateManager
        try:
            self.game_state.awaiting_weapon_choice = False
            self.game_state.weapon_choices = []
            self.game_state.weapon_choice_index = 0
            self.game_state.player_weapons = self.player_weapons.copy()
            self.game_state.weapon_levels = self.weapon_levels.copy()
        except Exception:
            pass

        # If this was initial weapon choice, either start the countdown or proceed to tower choice
        if self.is_initial_weapon_choice:
            self.is_initial_weapon_choice = False
            # If a tower selection is also required (Purgatory), show it next instead of starting countdown
            if self.is_initial_tower_choice:
                try:
                    self.game_state.show_initial_tower_choice()
                    self.awaiting_tower_choice = self.game_state.awaiting_tower_choice
                    self.tower_choices = list(self.game_state.tower_choices)
                    self.selected_tower_index = self.game_state.tower_choice_index
                except Exception:
                    self.awaiting_tower_choice = True
                    self.tower_choices = self.generate_initial_tower_choices()
                    self.selected_tower_index = 0
            else:
                self.stage_start_countdown = 3  # 3 seconds
                self.stage_start_timer = self.fps  # 1 second in frames

    def generate_initial_tower_choices(self) -> list[dict[str, Any]]:
        """Fallback generator for tower choices (mirrors GameStateManager)."""
        return [
            {
                "id": "fire",
                "name": "Fire Tower",
                "description": "Damage: 10 — Burn nearby enemies (4 DPS, 3s)",
            },
            {
                "id": "storm",
                "name": "Storm Tower",
                "description": "Damage: 10 (projectile ~9) — Chains to multiple enemies",
            },
            {
                "id": "ice",
                "name": "Ice Tower",
                "description": "Damage: 15 — Slows enemies 50% for 2s",
            },
        ]

    def _wall_x_at(self, side: str, y: float) -> float:
        """Return wall x coordinate for given side ('left' or 'right') nearest to provided y."""
        points = self.left_wall_points if side == "left" else self.right_wall_points
        if not points:
            return 320.0 if side == "left" else 960.0
        # Find nearest y sample
        nearest = min(points, key=lambda p: abs(p[1] - y))
        return float(nearest[0])

    def apply_tower(self, tower_id: str) -> None:
        """Apply the selected tower type for Purgatory and place towers at the bottom outside walls."""
        # Normalize ids if necessary
        tower_type = tower_id

        # Place towers just outside the walls near the bottom / player
        desired_y = min(self.height - 60, getattr(self.player, "y", self.height - 80))
        # Get wall edge X at approximately the desired_y
        left_wall_x = self._wall_x_at("left", desired_y)
        right_wall_x = self._wall_x_at("right", desired_y)
        # Place towers outside walls (offset by wall thickness + margin)
        margin = 30
        left_x = left_wall_x - WALL_THICKNESS - margin
        right_x = right_wall_x + WALL_THICKNESS + margin

        # Clamp within screen bounds as a safety
        left_x = max(20, left_x)
        right_x = min(self.width - 20, right_x)

        # Configure both left and right towers to the chosen type at computed positions
        self.left_tower = Tower(
            left_x, desired_y, fire_rate=self.statue_fire_rate, tower_type=tower_type
        )
        self.left_tower._base_damage = self.left_tower.damage
        self.left_tower._base_fire_rate = self.left_tower.fire_rate
        self.right_tower = Tower(
            right_x, desired_y, fire_rate=self.statue_fire_rate, tower_type=tower_type
        )
        self.right_tower._base_damage = self.right_tower.damage
        self.right_tower._base_fire_rate = self.right_tower.fire_rate
        # Ensure visibility after player actively chose towers
        self.left_tower.visible = True
        self.right_tower.visible = True
        # Re-apply permanent stat effects so created towers immediately reflect skill-tree bonuses
        try:
            self.apply_permanent_stats()
        except Exception:
            pass

        # Resume game flow
        self.awaiting_tower_choice = False
        # Unpause only if there is no other pending initial selection
        if not getattr(self, "is_initial_weapon_choice", False):
            self.paused = False
        try:
            self.game_state.awaiting_tower_choice = False
            self.game_state.tower_choices = []
            self.game_state.tower_choice_index = 0
        except Exception:
            pass

        # If this was an initial tower choice, clear flag and start countdown if no other initial choice remains
        if self.is_initial_tower_choice:
            self.is_initial_tower_choice = False
            if not self.is_initial_weapon_choice:
                self.stage_start_countdown = 3
                self.stage_start_timer = self.fps

    def update_enemy_spawning(self) -> None:
        """Handle enemy spawning logic (delegates timing to EnemyManager when present)."""
        # Use manager timers if manager exists
        if self.enemy_manager is not None:
            self.enemy_manager.enemy_spawn_timer -= 1
            if self.enemy_manager.enemy_spawn_timer <= 0:
                self.spawn_enemy()
                if self.selected_stage == "prologo":
                    self.enemy_manager.enemy_spawn_timer = int(
                        self.enemy_manager.enemy_spawn_rate * 1.5
                    )
                else:
                    self.enemy_manager.enemy_spawn_timer = (
                        self.enemy_manager.enemy_spawn_rate
                    )
        else:
            self.enemy_spawn_timer -= 1
            if self.enemy_spawn_timer <= 0:
                self.spawn_enemy()
                if self.selected_stage == "prologo":
                    self.enemy_spawn_timer = int(self.enemy_spawn_rate * 1.5)
                else:
                    self.enemy_spawn_timer = self.enemy_spawn_rate

        # Periodic big enemy spawn (delegate to EnemyManager when present)
        if self.enemy_manager is not None:
            try:
                self.enemy_manager.update_big_enemy_timer()
            except Exception:
                # Fallback to legacy behavior
                self.big_enemy_timer -= 1
                if self.big_enemy_timer <= 0 and not self.big_spawned_this_wave:
                    self.spawn_big_enemy()
                    self.big_spawned_this_wave = True
                    if self.wave >= 6:
                        self.big_enemy_timer = self.big_enemy_fast_interval
                    else:
                        self.big_enemy_timer = 12 * self.fps

            # Also allow EnemyManager to occasionally spawn non-boss inquisitors in Purgatory
            try:
                self.enemy_manager.update_inquisitor_spawns()
            except Exception:
                pass
        else:
            self.big_enemy_timer -= 1
            if self.big_enemy_timer <= 0 and not self.big_spawned_this_wave:
                self.spawn_big_enemy()
                self.big_spawned_this_wave = True
                if self.wave >= 6:
                    self.big_enemy_timer = self.big_enemy_fast_interval
                else:
                    self.big_enemy_timer = 12 * self.fps

        # Spawn acceleration
        self.spawn_accel_timer -= 1
        if self.spawn_accel_timer <= 0:
            # Update both game and manager rates to keep them in sync
            new_rate = max(self.spawn_min_rate, int(self.enemy_spawn_rate * 0.99))
            self.enemy_spawn_rate = new_rate
            if self.enemy_manager is not None:
                self.enemy_manager.enemy_spawn_rate = new_rate
            self.spawn_accel_timer = 20 * self.fps

    def update_wave_progression(self) -> None:
        """Handle wave progression and boss spawning"""
        # Wave progression based on elapsed seconds or on explicit frame boundary
        frames_per_wave = int(self.wave_duration * self.fps)
        frame_boundary_hit: bool = (
            frames_per_wave > 0
            and self.frame_count % frames_per_wave == 0
            and self.frame_count != 0
        )

        if self.wave_time >= self.wave_duration or frame_boundary_hit:
            self.wave += 1
            self.wave_time = 0
            # Reset wave boss flag (proxy to manager when available)
            if self.enemy_manager is not None:
                try:
                    self.enemy_manager.wave_boss_spawned = False
                except Exception:
                    self.wave_boss_spawned = False
            else:
                self.wave_boss_spawned = False

            # Reset prologo final boss flags if any (proxy to manager when available)
            # Skip reset for prologo to prevent multiple spawns
            if self.selected_stage != "prologo":
                if self.enemy_manager is not None:
                    try:
                        self.enemy_manager.prologo_final_boss_spawned = False
                        self.enemy_manager.prologo_final_boss_defeated = False
                        self.enemy_manager.prologo_final_boss_immortal = False
                        self.enemy_manager.prologo_lightning_timer = 0
                        self.enemy_manager.prologo_lightning_strike = False
                    except Exception:
                        self.prologo_final_boss_spawned = False
                        self.prologo_final_boss_defeated = False
                        self.prologo_final_boss_immortal = False
                        self.prologo_lightning_timer = 0
                        self.prologo_lightning_strike = False
                else:
                    self.prologo_final_boss_spawned = False
                    self.prologo_final_boss_defeated = False
                    self.prologo_final_boss_immortal = False
                    self.prologo_lightning_timer = 0
                    self.prologo_lightning_strike = False

            # Keep big spawn flag in manager if available
            if self.enemy_manager is not None:
                try:
                    self.enemy_manager.big_spawned_this_wave = False
                except Exception:
                    self.big_spawned_this_wave = False
            else:
                self.big_spawned_this_wave = False

            # Adjust spawn rate based on wave
            if self.wave < self.spawn_ramp_start_wave:
                self.enemy_spawn_rate = max(
                    self.spawn_min_rate,
                    int(self.base_spawn_rate - self.wave * self.spawn_ramp_slope_pre),
                )
                if self.enemy_manager is not None:
                    self.enemy_manager.enemy_spawn_rate = self.enemy_spawn_rate
            else:
                self.enemy_spawn_rate = max(
                    self.spawn_min_rate,
                    int(self.base_spawn_rate - self.wave * self.spawn_ramp_slope_post),
                )
                if self.enemy_manager is not None:
                    self.enemy_manager.enemy_spawn_rate = self.enemy_spawn_rate

            self.difficulty_multiplier = 1.0 + (self.wave * 0.12)

        # Spawn boss at 38 seconds (delegate to manager when available)
        if self.enemy_manager is not None:
            try:
                self.enemy_manager.update_wave_boss(self.wave_time)
            except Exception:
                # Fallback to legacy behavior
                if not self.wave_boss_spawned and self.wave_time >= 38:
                    if not (
                        self.selected_stage == "prologo"
                        and self.prologo_final_boss_spawned
                    ):
                        if self.wave % 3 == 0 and self.wave > 0:
                            self.spawn_boss("big")
                        else:
                            self.spawn_boss("mid")
                    self.wave_boss_spawned = True
        else:
            if not self.wave_boss_spawned and self.wave_time >= 38:
                if not (
                    self.selected_stage == "prologo" and self.prologo_final_boss_spawned
                ):
                    if self.wave % 3 == 0 and self.wave > 0:
                        self.spawn_boss("big")
                    else:
                        self.spawn_boss("mid")
                self.wave_boss_spawned = True

        # Ensure giant spawns at 12 seconds if not already spawned
        if self.wave_time >= 12:
            if self.enemy_manager is not None:
                if not self.enemy_manager.big_spawned_this_wave:
                    self.spawn_big_enemy()
                    self.enemy_manager.big_spawned_this_wave = True
            else:
                if not self.big_spawned_this_wave:
                    self.spawn_big_enemy()
                    self.big_spawned_this_wave = True

        # Ensure wave boss spawning is handled by manager when available
        if self.enemy_manager is not None:
            # manager.update_wave_boss already called earlier; nothing else required here
            pass

    def update_prologo_events(self) -> None:
        """Handle special Prologo events (managed by EnemyManager when present)"""
        if self.enemy_manager is not None:
            try:
                self.enemy_manager.update_prologo_events()
                return
            except Exception:
                # Fallback to legacy behavior below
                pass

        # Final boss at 3:55 (235 seconds) - delegate to manager when available
        if self.enemy_manager is not None:
            try:
                self.enemy_manager.update_prologo_events()
            except Exception:
                # fallback to legacy behavior
                if (
                    self.selected_stage == "prologo"
                    and not self.prologo_final_boss_spawned
                    and self.time_elapsed >= 235
                ):
                    logger.info(
                        "[PROLOGO] Spawning final boss at time %s", self.time_elapsed
                    )
                    self.spawn_boss("final")
                    self.prologo_final_boss_spawned = True
        else:
            if (
                self.selected_stage == "prologo"
                and not self.prologo_final_boss_spawned
                and self.time_elapsed >= 235
            ):
                logger.info(
                    "[PROLOGO] Spawning final boss at time %s", self.time_elapsed
                )
                self.spawn_boss("final")
                self.prologo_final_boss_spawned = True

        # Lightning strike when immortal boss reaches full health
        if self.selected_stage == "prologo" and self.prologo_lightning_strike:
            self.prologo_lightning_timer += 1
            if self.prologo_lightning_timer >= self.prologo_lightning_duration_frames:
                self.prologo_defeat()

        # Boss regeneration when immortal
        for boss in self.bosses:
            if (
                boss.enemy_type == "boss_final"
                and self.prologo_final_boss_immortal
                and boss.health < boss.max_health
            ):
                boss.health = min(boss.health + 3.0, boss.max_health)
                if boss.health >= boss.max_health and not self.prologo_lightning_strike:
                    logger.info(
                        "[PROLOGO] Final boss reached full health — triggering lightning strike"
                    )
                    self.prologo_lightning_strike = True
                    self.generate_lightning()
                    logger.debug(
                        "[PROLOGO] Lightning points generated: %s",
                        (
                            len(self.lightning_points)
                            if hasattr(self, "lightning_points")
                            else None
                        ),
                    )
                    self.player.health = 0

    def generate_lightning(self) -> None:
        """Generate lightning bolt path"""
        try:
            # Use player's current x as bolt origin, ensure numeric
            bolt_x = int(getattr(self.player, "x", self.width // 2))
            player_y = int(getattr(self.player, "y", self.height))
            segments = 10
            pts = []
            pts.append((bolt_x, 0))
            prev_x: int = bolt_x

            for i in range(segments):
                next_y = int((i + 1) * (player_y / segments))
                # Random step but clamp to screen bounds
                next_x = int(prev_x + random.randint(-25, 25))
                next_x = max(0, min(self.width, next_x))
                next_y = max(0, min(self.height, next_y))
                pts.append((next_x, next_y))
                prev_x = next_x

            pts.append((bolt_x, player_y))
            # Final assign
            self.lightning_points = pts
        except Exception as e:
            logger.exception("Exception while generating lightning: %s", e)
            import traceback

            traceback.print_exc()
            self.lightning_points = []

    def game_over(self) -> None:
        """Enter the game over state (persistent) and reset fade animation."""
        # Ensure other end screens are not active
        self.showing_prologo_end = False
        # Show the game over overlay and stop gameplay updates
        self.showing_game_over = True
        self.paused = True

        # Reset fade animation state and kickstart first frame so player sees immediate change
        self.game_over_alpha = min(255, self.game_over_fade_speed)

        # Stop any screen shake immediately so the overlay is stable
        self.shake_timer = 0
        self.shake_intensity = 0

        # Do not schedule an automatic return to menu; require explicit key press
        logger.info("Game over triggered; showing game over screen (awaiting keypress)")

    def update_game_over(self) -> None:
        """Progress the game-over fade animation."""
        try:
            if self.game_over_alpha < 255:
                self.game_over_alpha = min(
                    255, self.game_over_alpha + self.game_over_fade_speed
                )
        except Exception as e:
            logger.exception("Error in update_game_over: %s", e)

    def draw_game_over(self, shake_x=0, shake_y=0) -> None:
        """Draw the persistent game over screen overlay with fade."""
        try:
            from src.assets.text_cache import get_font, get_text

            # Overlay surface with per-pixel alpha to allow fade-in effect
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((40, 20, 45, int(self.game_over_alpha)))
            self.screen.blit(overlay, (0, 0))

            # Title (fade text by setting per-surface alpha)

            # Dark red for the FALL title for stronger contrast
            title_surf = get_text("FALL", get_font(64), (139, 0, 0)).copy()
            title_surf.set_alpha(int(self.game_over_alpha))
            self.screen.blit(
                title_surf,
                (
                    self.width // 2 - title_surf.get_width() // 2 + shake_x,
                    200 + shake_y,
                ),
            )

            # Stats
            font_medium = get_font(24)
            stats: List[str] = [
                f"Final Score: {int(self.score)}",
                f"Enemies killed: {getattr(self, 'enemies_killed_this_run', 0)}",
                f"Wave: {self.wave}",
                f"Level: {self.player.level}",
            ]

            for i, stat in enumerate(stats):
                text_surf = get_text(stat, font_medium, (255, 255, 255)).copy()
                text_surf.set_alpha(int(self.game_over_alpha))
                self.screen.blit(
                    text_surf,
                    (
                        self.width // 2 - text_surf.get_width() // 2 + shake_x,
                        320 + i * 40 + shake_y,
                    ),
                )

            # Prompt
            # Main prompt: ESC to return to menu (restart disabled)
            # Moved down for more spacing and changed to light yellow
            prompt = get_text(
                "Press ESC to return to menu", font_medium, (255, 255, 153)
            ).copy()
            prompt.set_alpha(int(self.game_over_alpha))
            self.screen.blit(
                prompt,
                (
                    self.width // 2 - prompt.get_width() // 2 + shake_x,
                    480 + shake_y,
                ),
            )

        except Exception as e:
            logger.exception("Error drawing game over screen: %s", e)

    def prologo_defeat(self) -> None:
        """Show Prologo defeat screen"""
        self.showing_prologo_end = True
        self.paused = True

        # Clear screen with very dark background for better text visibility
        self.screen.fill(
            (40, 20, 45)
        )  # Lighter purple background for better visibility

        # Title
        font_large = pygame.font.Font(None, 54)
        # Use dark red for the defeat title as well
        text = font_large.render("THE FALL", True, (139, 0, 0))
        self.screen.blit(text, (self.width // 2 - text.get_width() // 2, 150))

        # Description
        font_medium = pygame.font.Font(None, 18)
        text = font_medium.render(
            "Struck down by divine wrath, begin your descent into the underworld",
            True,
            (200, 200, 200),
        )
        self.screen.blit(text, (self.width // 2 - text.get_width() // 2, 220))

        # Stats
        stats: List[str] = [
            f"Score: {int(self.score)}",
            f"Level: {self.player.level}",
            f"Time: {int((self.time_elapsed * 1.3) // 60)}:{int((self.time_elapsed * 1.3) % 60):02d}",
        ]

        for i, stat in enumerate(stats):
            text = font_medium.render(stat, True, (255, 255, 255))
            self.screen.blit(
                text, (self.width // 2 - text.get_width() // 2, 300 + i * 40)
            )

        # Continue prompt
        text = font_medium.render(
            "Press ENTER to continue to Limbo", True, (100, 200, 255)
        )
        self.screen.blit(text, (self.width // 2 - text.get_width() // 2, 500))

        text = font_medium.render("or ESC to return to menu", True, (150, 150, 150))
        self.screen.blit(text, (self.width // 2 - text.get_width() // 2, 540))

    def spawn_enemy(self) -> None:
        # Spawn from top of screen (pick X uniformly between the walls)
        x = self.random_x_between_walls()
        y = -20

        # Choose enemy type based on wave and random chance
        rand: float = random.random()
        # Choose health and speed based on type
        health: float = 0.0
        if self.wave >= 5 and rand < 0.05:  # 5% chance for giant after wave 5
            enemy_type = "giant"
            health = 160 * self.difficulty_multiplier  # Doubled from 80
            # Base non-boss giant speed (from balance)
            speed = ENEMY_BASE_SPEEDS.get("giant", 45)
        # Allow a small chance for 'strong' already in waves 1-2 (10%), larger chance in later waves
        elif self.wave < 3 and rand < 0.10:  # 10% chance for strong in waves 1-2
            enemy_type = "strong"
            health = 70 * self.difficulty_multiplier
            speed = ENEMY_BASE_SPEEDS.get("strong", 60)
        elif self.wave >= 3 and rand < 0.15:  # 15% chance for strong after wave 3
            enemy_type = "strong"
            health = 70 * self.difficulty_multiplier  # Doubled from 35
            # Strong enemies (from balance)
            speed = ENEMY_BASE_SPEEDS.get("strong", 60)
        elif rand < 0.3:  # 30% chance for normal
            enemy_type = "normal"
            health = 50 * self.difficulty_multiplier  # Doubled from 25
            # Normal enemies (from balance)
            speed = ENEMY_BASE_SPEEDS.get("normal", 75)
        elif rand < 0.5:  # 20% chance for angel
            enemy_type = "angel"
            health = 40 * self.difficulty_multiplier  # Doubled from 20
            # Angel speed (from balance)
            speed = ENEMY_BASE_SPEEDS.get("angel", 60)
        else:  # 25% chance for weak
            enemy_type = "weak"
            health = 30 * self.difficulty_multiplier  # Doubled from 15
            # Weak enemies (from balance)
            speed = ENEMY_BASE_SPEEDS.get("weak", 35)

        # Use EnemyManager when available
        if self.enemy_manager is not None:
            try:
                self.enemy_manager.spawn(x, y, enemy_type, health, speed)
            except Exception:
                enemy = Enemy(x, y, enemy_type, health, speed)
                if hasattr(self.enemies, "add"):
                    self.enemies.add(enemy)
                else:
                    self.enemies.append(enemy)
        else:
            enemy = Enemy(x, y, enemy_type, health, speed)
            if hasattr(self.enemies, "add"):
                self.enemies.add(enemy)
            else:
                self.enemies.append(enemy)

    def spawn_enemy_projectiles(self) -> None:
        """Have some enemies shoot projectiles at the player"""
        # Only some enemies shoot (angels, inquisitor-normal, and bosses)
        shooting_enemies = []
        for enemy in self.enemies:
            if enemy.enemy_type in ["angel"] or (
                enemy.enemy_type == "normal"
                and getattr(enemy, "appearance", None) == "inquisitor"
            ):
                shooting_enemies.append(enemy)
        for boss in self.bosses:
            if boss.enemy_type in [
                "boss_medium",
                "boss_big",
                "boss_final",
                "boss_inquisitor",
            ]:
                shooting_enemies.append(boss)

        # Limit to 2-3 shooters at a time
        shooting_enemies = shooting_enemies[:3]

        for enemy in shooting_enemies:
            # Calculate direction to player
            dx = self.player.x - enemy.x
            dy = self.player.y - enemy.y
            distance: float = math.sqrt(dx * dx + dy * dy)

            if distance > 0:
                # Normalize direction
                dx /= distance
                dy /= distance

                # Create projectile
                speed = 200
                projectile: Projectile = Projectile(
                    enemy.x,
                    enemy.y,
                    dx * speed,
                    dy * speed,
                    damage=8,
                    radius=4,
                    is_enemy_projectile=True,
                )
                self.enemy_projectiles.add(projectile)

    def spawn_giant_enemy(self) -> None:
        """Spawn a giant enemy at random edge (delegates to EnemyManager)."""
        if self.enemy_manager is not None:
            try:
                self.enemy_manager.spawn_giant_enemy()
                return
            except Exception:
                pass

        # Fallback to original behavior
        side: str = random.choice(["left", "right", "top"])

        if side == "left":
            x = -30
            y = random.randint(0, self.height)
        elif side == "right":
            x = self.width + 30
            y = random.randint(0, self.height)
        else:  # top
            x = self.random_x_between_walls()
            y = -30

        enemy_type = "giant"
        health: float = 100 * self.difficulty_multiplier
        # Base non-boss giant speed (from balance)
        speed = ENEMY_BASE_SPEEDS.get("giant", 45)
        enemy: Enemy = Enemy(x, y, enemy_type, health, speed)
        if hasattr(self.enemies, "add"):
            self.enemies.add(enemy)
        else:
            self.enemies.append(enemy)

    def spawn_big_enemy(self) -> None:
        """Spawn a big enemy (giant). Delegates to EnemyManager if available."""
        if self.enemy_manager is not None:
            try:
                self.enemy_manager.spawn_giant_enemy()
                return
            except Exception:
                pass

        x = self.random_x_between_walls()
        y = -30

        enemy_type = "giant"
        health: float = 100 * self.difficulty_multiplier
        # Base non-boss giant speed (spawn fallback)
        speed = ENEMY_BASE_SPEEDS.get("giant", 45)
        enemy: Enemy = Enemy(x, y, enemy_type, health, speed)
        if hasattr(self.enemies, "add"):
            self.enemies.add(enemy)
        else:
            self.enemies.append(enemy)

    def spawn_reinforcements(self, x=None, y=None, count=None):
        """Spawn a short-lived cluster of reinforcements near (x,y) or at a random building.
        If x,y are None the spawn will originate from a random building at the top.
        `count` overrides the default reinforcement_count."""
        try:
            if x is None or y is None:
                if self.buildings:  # If there are buildings (prologo)
                    building: Dict[str, Any] = random.choice(self.buildings)
                    x = building["x"] + random.randint(-20, 20)
                    # Clamp building-based spawn inside walls
                    x = self.clamp_to_walls(x)
                    y = building["y"]
                else:  # No buildings (limbo), spawn at random top position
                    x = self.random_x_between_walls(margin=100)
                    y = 50
            if count is None:
                count: int = self.reinforcement_count

            # If this is an "extra" reinforcement (e.g., mid-boss doubled call), reduce enemies by 1/3
            # to make the extra wave smaller and less overwhelming. This is a silent adjustment.
            if count > self.reinforcement_count:
                count: int = max(1, int(round(count * 2.0 / 3.0)))

            # Choose types biased to normal/angel
            weights: List[float] = [
                0.3,
                0.4,
                0.2,
                0.3,
            ]  # Bias toward normals and angels
            for i in range(count):
                etype: str = random.choices(
                    ["weak", "normal", "strong", "angel"], weights=weights
                )[0]

                # Scatter reinforced enemies in a broader area to avoid clustering
                angle: float = random.uniform(0, 2 * math.pi)
                r: int = random.randint(40, 160)
                rx = int(x + math.cos(angle) * r)
                ry = int(y + math.sin(angle) * r)

                # Clamp positions into the playable area
                rx: int = max(30, min(self.width - 30, rx))
                # Also clamp to walls so reinforcements don't appear outside bounds
                rx = self.clamp_to_walls(rx)
                # Keep regular enemies generally in the upper area when spawning from top
                if etype != "angel":
                    ry: int = max(40, min(self.height - 120, ry))
                else:
                    # Angels always spawn from the top band
                    rx: int = max(50, min(self.width - 50, rx))
                    ry = 50

                if etype == "weak":
                    enemy_type = "weak"
                    health = int(15 * self.difficulty_multiplier * 1.1)
                    speed = ENEMY_BASE_SPEEDS.get("weak", 35)
                elif etype == "normal":
                    enemy_type = "normal"
                    health = int(25 * self.difficulty_multiplier * 1.1)
                    speed = ENEMY_BASE_SPEEDS.get("normal", 75)
                elif etype == "strong":
                    enemy_type = "strong"
                    health = int(45 * self.difficulty_multiplier * 1.1)
                    speed = ENEMY_BASE_SPEEDS.get("strong", 60)
                else:  # angel
                    enemy_type = "angel"
                    health = int(30 * self.difficulty_multiplier * 1.1)
                    speed = ENEMY_BASE_SPEEDS.get("angel", 60)

                enemy: Enemy = Enemy(rx, ry, enemy_type, health, speed)
                self.enemies.add(enemy)
        except Exception as e:
            logger.exception("Error spawning reinforcements: %s", e)
            import traceback

            traceback.print_exc()

    def spawn_boss(self, boss_type) -> None:
        """Spawn a boss of the specified type (delegates to EnemyManager)."""
        if self.enemy_manager is not None:
            try:
                self.enemy_manager.spawn_boss(boss_type)
                return
            except Exception:
                pass

        # Spawn boss at top center
        x: int = self.width // 2
        y = -50

        # Decide health and speed per boss type
        health: float = 0.0
        if boss_type == "final":
            enemy_type = "boss_final"
            health = 1000 * self.difficulty_multiplier
            speed = ENEMY_BASE_SPEEDS.get("boss_final", 40)
        elif boss_type == "big":
            enemy_type = "boss_big"
            health = 600 * self.difficulty_multiplier
            speed = ENEMY_BASE_SPEEDS.get("boss_big", 40)
        else:  # mid
            enemy_type = "boss_medium"
            health = 300 * self.difficulty_multiplier
            speed = ENEMY_BASE_SPEEDS.get("boss_medium", 45)

        boss: Enemy = Enemy(x, y, enemy_type, health, speed)
        self.bosses.add(boss)

    def show_upgrades(self) -> None:
        """Show level up upgrade selection"""
        self.awaiting_upgrade = True
        self.paused = True
        self.upgrade_choices = self.generate_upgrade_choices()
        self.selected_upgrade_index = 0

    def apply_upgrade(self, upgrade) -> None:
        """Apply the selected upgrade"""
        if isinstance(upgrade, int):
            # If passed an index, get the upgrade dict
            upgrade = self.upgrade_choices[upgrade]

        # Call the apply function from the upgrade dict
        try:
            upgrade["apply"]()
        except Exception as e:
            logger.exception(
                "Error applying upgrade %s: %s", upgrade.get("name", "unknown"), e
            )

        # Update upgrade levels for tracking
        upgrade_id = upgrade["id"]
        if upgrade_id not in self.upgrade_levels:
            self.upgrade_levels[upgrade_id] = 0
        self.upgrade_levels[upgrade_id] += 1

        # Resume the game
        self.awaiting_upgrade = False
        self.paused = False
        # Keep GameStateManager in sync about upgrade selection and flags
        try:
            self.game_state.awaiting_upgrade = False
            self.game_state.upgrade_choices = []
            self.game_state.upgrade_choice_index = 0
        except Exception:
            pass
