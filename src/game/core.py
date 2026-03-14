import logging
import math
import random
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import pygame
from pygame.key import ScancodeWrapper

from src.assets.manager import get_image
from src.balance import (
    DEFAULT_DAMAGE_REDUCTION_MULTIPLIER,
    DEFAULT_PROJECTILE_SIZE_MULTIPLIER,
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
)
from src.entities.player import Player
from src.game.persistence import (
    get_profile_info,
    load_last_profile_slot,
    load_permanent_stats,
    migrate_legacy_save,
    profile_path,
    save_permanent_stats,
)
from src.game.ui_helpers import FloatingText
from src.game.weapons import init_player_weapons, init_weapons
from src.game_constants import (
    BARRIER_DESPAWN_TIME,
    BARRIER_HEIGHT,
    BARRIER_HP,
    BARRIER_MAX_COUNT,
    BARRIER_SPAWN_DELAY,
    BARRIER_SPAWN_INTERVAL_MAX,
    BARRIER_SPAWN_INTERVAL_MIN,
    BARRIER_WIDTH,
    DEFAULT_FPS,
    DEFAULT_HEIGHT,
    DEFAULT_PLAYER_ANIM_SPEED,
    DEFAULT_WAVE_DURATION,
    DEFAULT_WIDTH,
    HELL_BARRIER_X_MAX,
    HELL_BARRIER_X_MIN,
    HELL_BARRIER_Y_MAX,
    HELL_BARRIER_Y_MIN,
    HELL_STAGES,
    LIMBO_LAMP_OFFSET,
    LIMBO_LAMP_SIZE,
    LIMBO_LAMP_SPACING,
    LIMBO_STAGES,
    PURGATORY_STAGES,
    STAGE_SETTINGS,
    WALL_THICKNESS,
)
from src.game_state import GameStateManager
from src.projectile import FliesProjectile
from src.systems.collision_system import CollisionSystem
from src.systems.enemy_manager import EnemyManager
from src.systems.input_handler import InputHandler
from src.systems.spawn_system import SpawnSystem
from src.systems.upgrade_system import UpgradeSystem
from src.systems.weapon_system import WeaponSystem
from src.ui import PygameUIManager
from src.weapons import WEAPON_DEFS

if TYPE_CHECKING:
    from src.systems.projectile_manager import ProjectileManager

logger: logging.Logger = logging.getLogger(__name__)

# Global reference to running game instance (set in Game.__init__)
CURRENT_GAME = None


class Game:
    def __setattr__(self, name, value):
        """Prevent use of the obsolete ``score_multiplier`` attribute.

        Attempts to set or get ``score_multiplier`` now raise, so callers are
        forced to remove their references rather than silently be ignored.
        """
        if name == "score_multiplier":
            raise AttributeError("score_multiplier attribute has been removed")
        super().__setattr__(name, value)

    def __getattr__(self, name):
        if name == "score_multiplier":
            raise AttributeError("score_multiplier attribute has been removed")
        raise AttributeError(
            f"{type(self).__name__!r} object has no attribute {name!r}"
        )

    def __init__(
        self,
        fast_forward_prologo: bool = False,
        fast_forward_limbo_final: bool = False,
        fast_forward_prologo_force_lightning: bool = False,
        debug: bool = False,
    ) -> None:
        pygame.init()
        pygame.mixer.init()

        # Debug fast-forward flags (set by CLI/tests)
        self.fast_forward_prologo: bool = fast_forward_prologo
        self.fast_forward_limbo_final: bool = fast_forward_limbo_final
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
        self._init_managers()

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

    def _load_last_profile_slot(self) -> int | None:
        """Load the last selected profile slot from any profile's save file."""
        return load_last_profile_slot()

    def _init_game_state(self) -> None:
        # Early defaults to ensure robust construction even if later init fails
        # Profile system state (check FIRST — before setting menu flags)
        # active_profile_slot: 1, 2 or 3; None = no profile selected yet
        self.active_profile_slot: int | None = self._load_last_profile_slot()
        # If no profile selected, go straight to profiles menu on startup
        if self.active_profile_slot is None:
            self.showing_main_menu = False
            self.showing_profiles_menu = True
        else:
            self.showing_main_menu = True
            self.showing_profiles_menu = False

        self.showing_stage_menu = False
        self.showing_permanent_upgrades = False
        self.showing_prologo_end = False
        self.showing_unlock_overlay = False
        self.unlock_overlay_alpha = 0.0
        # Submenu flags (Limbo / Purgatory / Hell) — ensure they exist on construction
        self.showing_limbo_menu = False
        self.showing_purgatory_menu = False
        self.showing_hell_menu = False
        # Tower choice state (used by purgatory/tower selection flows)
        self.awaiting_tower_choice: bool = False
        self.is_initial_tower_choice: bool = False
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
        # Exit confirmation state (True when waiting for YES/NO confirmation)
        self.exit_confirm_pending: bool = False
        # Currently-selected option in the pause menu (0 = Resume, 1 = Quit)
        self.pause_menu_option: int = 0
        # Text-input state for naming a profile
        self.editing_profile_name: bool = False
        self.editing_profile_slot: int | None = None
        self.profile_name_input: str = ""
        # Per-slot delete confirmation: slot → True when pending confirmation
        self.profile_delete_confirm: dict = (
            {}
            if not hasattr(self, "profile_delete_confirm")
            else self.profile_delete_confirm
        )

        # Options overlay state (opened from the main menu gear button)
        self.showing_options: bool = False
        # Options UI state: resolution dropdown open/closed
        self.options_resolution_dropdown_open: bool = False

        # Options: toggle for showing floating damage numbers
        self.show_damage_numbers: bool = True
        # Option to mute/enable game sounds (procedural and assets)
        self.sounds_enabled: bool = True

        # Track if background image was drawn this frame
        self.background_image_drawn: bool = False

        # Persistent stats container must exist early so other init code can reference it
        self.permanent_stats: Dict[str, int] = {}
        # ensure some meta‑progression keys exist so callers can increment
        # without worrying about KeyError
        self.global_progress: Dict[str, Any] = getattr(self, "global_progress", {})
        self.global_progress.setdefault("meta_xp", 0)
        self.global_progress.setdefault("meta_level", 1)
        self.global_progress.setdefault("meta_points", 0)
        self.global_progress.setdefault("stages_cleared", {})
        self.global_progress.setdefault("pending_unlock_notifications", [])
        self.projectile_manager: "ProjectileManager | None" = None

        # Centralized floating text pool for damage numbers and feedback (world coords)
        self.floating_texts: List[FloatingText] = []
        # Health drops spawned by wave bosses; each entry is a dict containing
        # x, y, vy (falling velocity), heal amount and radius.  Updated every
        # frame in ``_update_health_drops`` and rendered by the UI.
        self.health_drops: List[Dict[str, Any]] = []
        # Center-screen messages (used by UI and GameStateManager)
        self.center_messages: List[Dict[str, Any]] = []

        # Statue / tower defaults used by Limbo/stage logic and tests
        try:
            self.statue_fire_rate: int = STATUE_FIRE_RATE
        except (AttributeError, TypeError, ValueError, KeyError):
            self.statue_fire_rate: int = 1
        self.statue_cooldown: int = 0
        self.statue_next_left: bool = True
        self.left_tower = None
        self.right_tower = None

        # per-wave difficulty slope may vary by stage; limbo levels are slightly
        # easier (see `get_difficulty_multiplier_per_wave`).

        # Tower special state owned by TowerSpecialSystem (self.tower_special).
        # Backing fields are proxied via @property/@setter pairs below so that
        # external code (tests, systems) can continue using game.tower_energy, etc.
        self._tower_energy: int = 0
        self._tower_energy_max: int = 100
        self._tower_energy_per_hit: int = 5
        self._fire_special_charges: int = 0
        self._fire_special_timer: int = 0
        self._fire_special_index: int = 0
        self._pending_fire_clicks: List[dict] = []
        self._fire_smoke: List[dict] = []
        self._right_mouse_held: bool = False
        self._voltaic_active: bool = False
        self._voltaic_time_left: int = 0
        self._voltaic_x: float = 0.0
        self._voltaic_y: float = 0.0
        self._voltaic_accum: dict[int, int] = {}
        self._VOLTAIC_MAYHEM_MAX_DURATION: int = 0
        self._VOLTAIC_MAYHEM_IMPACT_RADIUS: int = 0
        self._VOLTAIC_MAYHEM_SPEED: int = 0

        # Register self as current running game for modules that need quick access
        global CURRENT_GAME
        CURRENT_GAME = self
        # also update package-level alias so imports from `src.game` see the same
        try:
            import src.game as _pkg

            _pkg.CURRENT_GAME = self
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        # Gameplay defaults used by tests and early update paths
        self.stage_start_countdown = 0
        self.stage_start_timer = 0
        self.countdown_fade_timer = 0  # Timer for fade-out effect
        self.show_fps: bool = True
        self.paused = False
        self._paused_by_blasphemy5 = False
        self.awaiting_upgrade = False
        self.selected_upgrade_index = 0
        self.awaiting_weapon_choice = False
        self.selected_weapon_index = 0
        self.showing_game_over = False
        self._game_over_triggered = (
            False  # Prevents re-triggering game over during same run
        )
        self.game_over_alpha = 0
        self.game_over_fade_duration_ms = GAME_OVER_FADE_DURATION_MS
        # Calculate per-frame fade speed for game over alpha
        self.game_over_fade_speed = max(
            1, int(255 / ((self.game_over_fade_duration_ms / 1000.0) * self.fps))
        )
        # Blasphemy 5 state is now managed by Blasphemy5System (initialized in _init_managers)
        # Old attributes are kept for backward compat but delegated via properties

        self.player_xp = 0
        self.player_level = 1
        self.xp_to_next_level = XP_BASE

    # --- Tower Special System: backward-compatible property forwarding ---
    # When tower_special is initialized, these properties route through to it.
    # Before that, they use private backing fields.

    @property
    def tower_energy(self) -> int:
        ts = getattr(self, "tower_special", None)
        return ts.tower_energy if ts is not None else self._tower_energy

    @tower_energy.setter
    def tower_energy(self, val: int) -> None:
        ts = getattr(self, "tower_special", None)
        if ts is not None:
            ts.tower_energy = val
        else:
            self._tower_energy = val

    @property
    def tower_energy_max(self) -> int:
        ts = getattr(self, "tower_special", None)
        return ts.tower_energy_max if ts is not None else self._tower_energy_max

    @tower_energy_max.setter
    def tower_energy_max(self, val: int) -> None:
        ts = getattr(self, "tower_special", None)
        if ts is not None:
            ts.tower_energy_max = val
        else:
            self._tower_energy_max = val

    @property
    def tower_energy_per_hit(self) -> int:
        ts = getattr(self, "tower_special", None)
        return ts.tower_energy_per_hit if ts is not None else self._tower_energy_per_hit

    @tower_energy_per_hit.setter
    def tower_energy_per_hit(self, val: int) -> None:
        ts = getattr(self, "tower_special", None)
        if ts is not None:
            ts.tower_energy_per_hit = val
        else:
            self._tower_energy_per_hit = val

    @property
    def fire_special_charges(self) -> int:
        ts = getattr(self, "tower_special", None)
        return ts.fire_special_charges if ts is not None else self._fire_special_charges

    @fire_special_charges.setter
    def fire_special_charges(self, val: int) -> None:
        ts = getattr(self, "tower_special", None)
        if ts is not None:
            ts.fire_special_charges = val
        else:
            self._fire_special_charges = val

    @property
    def fire_special_timer(self) -> int:
        ts = getattr(self, "tower_special", None)
        return ts.fire_special_timer if ts is not None else self._fire_special_timer

    @fire_special_timer.setter
    def fire_special_timer(self, val: int) -> None:
        ts = getattr(self, "tower_special", None)
        if ts is not None:
            ts.fire_special_timer = val
        else:
            self._fire_special_timer = val

    @property
    def fire_special_index(self) -> int:
        ts = getattr(self, "tower_special", None)
        return ts.fire_special_index if ts is not None else self._fire_special_index

    @fire_special_index.setter
    def fire_special_index(self, val: int) -> None:
        ts = getattr(self, "tower_special", None)
        if ts is not None:
            ts.fire_special_index = val
        else:
            self._fire_special_index = val

    @property
    def pending_fire_clicks(self) -> List[dict]:
        ts = getattr(self, "tower_special", None)
        return ts.pending_fire_clicks if ts is not None else self._pending_fire_clicks

    @pending_fire_clicks.setter
    def pending_fire_clicks(self, val: List[dict]) -> None:
        ts = getattr(self, "tower_special", None)
        if ts is not None:
            ts.pending_fire_clicks = val
        else:
            self._pending_fire_clicks = val

    @property
    def fire_smoke(self) -> List[dict]:
        ts = getattr(self, "tower_special", None)
        return ts.fire_smoke if ts is not None else self._fire_smoke

    @fire_smoke.setter
    def fire_smoke(self, val: List[dict]) -> None:
        ts = getattr(self, "tower_special", None)
        if ts is not None:
            ts.fire_smoke = val
        else:
            self._fire_smoke = val

    @property
    def right_mouse_held(self) -> bool:
        """Legacy flag exposed for tests and compatibility.

        Historically this tracked whether the player was holding the right
        mouse button so the storm special could cancel when released.  With
        the new toggle behaviour it now simply mirrors the active state of
        the Voltaic Mayhem beam when possible; the input handler keeps it in sync.
        """
        ts = getattr(self, "tower_special", None)
        return ts.right_mouse_held if ts is not None else self._right_mouse_held

    @right_mouse_held.setter
    def right_mouse_held(self, val: bool) -> None:
        # setter exists primarily so tests can manipulate the flag; the
        # input handler will update it automatically when the special
        # toggles.  The underlying value isn't relied on for game logic
        # aside from legacy compatibility.
        ts = getattr(self, "tower_special", None)
        if ts is not None:
            ts.right_mouse_held = val
        else:
            self._right_mouse_held = val

    @property
    def voltaic_active(self) -> bool:
        ts = getattr(self, "tower_special", None)
        return ts.voltaic_active if ts is not None else self._voltaic_active

    @voltaic_active.setter
    def voltaic_active(self, val: bool) -> None:
        ts = getattr(self, "tower_special", None)
        if ts is not None:
            ts.voltaic_active = val
        else:
            self._voltaic_active = val

    @property
    def voltaic_time_left(self) -> int:
        ts = getattr(self, "tower_special", None)
        return ts.voltaic_time_left if ts is not None else self._voltaic_time_left

    @voltaic_time_left.setter
    def voltaic_time_left(self, val: int) -> None:
        ts = getattr(self, "tower_special", None)
        if ts is not None:
            ts.voltaic_time_left = val
        else:
            self._voltaic_time_left = val

    @property
    def voltaic_x(self) -> float:
        ts = getattr(self, "tower_special", None)
        return ts.voltaic_x if ts is not None else self._voltaic_x

    @voltaic_x.setter
    def voltaic_x(self, val: float) -> None:
        ts = getattr(self, "tower_special", None)
        if ts is not None:
            ts.voltaic_x = val
        else:
            self._voltaic_x = val

    @property
    def voltaic_y(self) -> float:
        ts = getattr(self, "tower_special", None)
        return ts.voltaic_y if ts is not None else self._voltaic_y

    @voltaic_y.setter
    def voltaic_y(self, val: float) -> None:
        ts = getattr(self, "tower_special", None)
        if ts is not None:
            ts.voltaic_y = val
        else:
            self._voltaic_y = val

    @property
    def _voltaic_accum(self) -> dict[int, int]:
        ts = getattr(self, "tower_special", None)
        return (
            ts._voltaic_accum
            if ts is not None
            else getattr(self, "__voltaic_accum_backing", {})
        )

    @_voltaic_accum.setter
    def _voltaic_accum(self, val: dict[int, int]) -> None:
        ts = getattr(self, "tower_special", None)
        if ts is not None:
            ts._voltaic_accum = val
        else:
            setattr(self, "__voltaic_accum_backing", val)

    @property
    def VOLTAIC_MAYHEM_MAX_DURATION(self) -> int:
        ts = getattr(self, "tower_special", None)
        return (
            ts.VOLTAIC_MAYHEM_MAX_DURATION
            if ts is not None
            else self._VOLTAIC_MAYHEM_MAX_DURATION
        )

    @VOLTAIC_MAYHEM_MAX_DURATION.setter
    def VOLTAIC_MAYHEM_MAX_DURATION(self, val: int) -> None:
        ts = getattr(self, "tower_special", None)
        if ts is not None:
            ts.VOLTAIC_MAYHEM_MAX_DURATION = val
        else:
            self._VOLTAIC_MAYHEM_MAX_DURATION = val

    @property
    def VOLTAIC_MAYHEM_IMPACT_RADIUS(self) -> int:
        ts = getattr(self, "tower_special", None)
        return (
            ts.VOLTAIC_MAYHEM_IMPACT_RADIUS
            if ts is not None
            else self._VOLTAIC_MAYHEM_IMPACT_RADIUS
        )

    @VOLTAIC_MAYHEM_IMPACT_RADIUS.setter
    def VOLTAIC_MAYHEM_IMPACT_RADIUS(self, val: int) -> None:
        ts = getattr(self, "tower_special", None)
        if ts is not None:
            ts.VOLTAIC_MAYHEM_IMPACT_RADIUS = val
        else:
            self._VOLTAIC_MAYHEM_IMPACT_RADIUS = val

    @property
    def VOLTAIC_MAYHEM_SPEED(self) -> int:
        ts = getattr(self, "tower_special", None)
        return ts.VOLTAIC_MAYHEM_SPEED if ts is not None else self._VOLTAIC_MAYHEM_SPEED

    @VOLTAIC_MAYHEM_SPEED.setter
    def VOLTAIC_MAYHEM_SPEED(self, val: int) -> None:
        ts = getattr(self, "tower_special", None)
        if ts is not None:
            ts.VOLTAIC_MAYHEM_SPEED = val
        else:
            self._VOLTAIC_MAYHEM_SPEED = val

    def special_unlocked(self) -> bool:
        """Delegate to TowerSpecialSystem."""
        return self.tower_special.special_unlocked() if self.tower_special else False

    def charge_tower_energy(self, amount: int | None = None) -> None:
        """Delegate to TowerSpecialSystem."""
        if self.tower_special:
            self.tower_special.charge_tower_energy(amount)

    def is_tower_special_ready(self) -> bool:
        """Delegate to TowerSpecialSystem."""
        return (
            self.tower_special.is_tower_special_ready() if self.tower_special else False
        )

    def _dist_point_to_segment(
        self, px: float, py: float, x1: float, y1: float, x2: float, y2: float
    ) -> float:
        """Delegate to TowerSpecialSystem."""
        return (
            self.tower_special._dist_point_to_segment(px, py, x1, y1, x2, y2)
            if self.tower_special
            else 0.0
        )

    def activate_tower_special(self) -> bool:
        """Delegate to TowerSpecialSystem."""
        return (
            self.tower_special.activate_tower_special() if self.tower_special else False
        )

    def use_fire_charge(self) -> bool:
        """Delegate to TowerSpecialSystem."""
        return self.tower_special.use_fire_charge() if self.tower_special else False

    def _spawn_fire_special(self, x: float, y: float) -> None:
        """Delegate to TowerSpecialSystem."""
        if self.tower_special:
            self.tower_special._spawn_fire_special(x, y)

    def _update_fire_smoke(self) -> None:
        """Delegate to TowerSpecialSystem."""
        if self.tower_special:
            self.tower_special._update_fire_smoke()

    def update_voltaic_mayhem(self) -> None:
        """Delegate to TowerSpecialSystem."""
        if self.tower_special:
            self.tower_special.update_voltaic_mayhem()

    # ===== Blasphemy 5 System Properties ===== #
    # These properties delegate to Blasphemy5System for backward compatibility

    @property
    def blasphemy_5_invisible(self) -> bool:
        """Delegate to Blasphemy5System (read by ui.py)."""
        return (
            self.blasphemy5_system.blasphemy_5_invisible
            if self.blasphemy5_system
            else False
        )

    @property
    def blasphemy_5_invulnerable(self) -> bool:
        """Delegate to Blasphemy5System (read by collision_system.py)."""
        return (
            self.blasphemy5_system.blasphemy_5_invulnerable
            if self.blasphemy5_system
            else False
        )

    @property
    def blasphemy_5_blink_particles(self) -> list[dict]:
        """Delegate to Blasphemy5System (read by ui.py)."""
        return (
            self.blasphemy5_system.blasphemy_5_blink_particles
            if self.blasphemy5_system
            else []
        )

    @property
    def blasphemy_5_blink_cooldown(self) -> int:
        """Delegate to Blasphemy5System (read/written by tests)."""
        return (
            self.blasphemy5_system.blasphemy_5_blink_cooldown
            if self.blasphemy5_system
            else 0
        )

    @blasphemy_5_blink_cooldown.setter
    def blasphemy_5_blink_cooldown(self, value: int) -> None:
        if self.blasphemy5_system:
            self.blasphemy5_system.blasphemy_5_blink_cooldown = value

    @property
    def blasphemy_5_blink_state(self) -> int:
        """Delegate to Blasphemy5System (read/written by tests)."""
        return (
            self.blasphemy5_system.blasphemy_5_blink_state
            if self.blasphemy5_system
            else 0
        )

    @blasphemy_5_blink_state.setter
    def blasphemy_5_blink_state(self, value: int) -> None:
        if self.blasphemy5_system:
            self.blasphemy5_system.blasphemy_5_blink_state = value

    @property
    def blasphemy_5_blink_timer(self) -> int:
        """Delegate to Blasphemy5System (read/written by tests)."""
        return (
            self.blasphemy5_system.blasphemy_5_blink_timer
            if self.blasphemy5_system
            else 0
        )

    @blasphemy_5_blink_timer.setter
    def blasphemy_5_blink_timer(self, value: int) -> None:
        if self.blasphemy5_system:
            self.blasphemy5_system.blasphemy_5_blink_timer = value

    @property
    def blasphemy_5_blink_target_x(self) -> float:
        """Delegate to Blasphemy5System (read/written by tests)."""
        return (
            self.blasphemy5_system.blasphemy_5_blink_target_x
            if self.blasphemy5_system
            else 0.0
        )

    @blasphemy_5_blink_target_x.setter
    def blasphemy_5_blink_target_x(self, value: float) -> None:
        if self.blasphemy5_system:
            self.blasphemy5_system.blasphemy_5_blink_target_x = value

    @property
    def blasphemy_5_blink_target_y(self) -> float:
        """Delegate to Blasphemy5System (read/written by tests)."""
        return (
            self.blasphemy5_system.blasphemy_5_blink_target_y
            if self.blasphemy5_system
            else 0.0
        )

    @blasphemy_5_blink_target_y.setter
    def blasphemy_5_blink_target_y(self, value: float) -> None:
        if self.blasphemy5_system:
            self.blasphemy5_system.blasphemy_5_blink_target_y = value

    @property
    def blasphemy_5_blink_origin_x(self) -> float:
        """Delegate to Blasphemy5System (read by tests)."""
        return (
            self.blasphemy5_system.blasphemy_5_blink_origin_x
            if self.blasphemy5_system
            else 0.0
        )

    @property
    def blasphemy_5_blink_origin_y(self) -> float:
        """Delegate to Blasphemy5System (read by tests)."""
        return (
            self.blasphemy5_system.blasphemy_5_blink_origin_y
            if self.blasphemy5_system
            else 0.0
        )

    @property
    def blasphemy_5_revived(self) -> bool:
        """Delegate to Blasphemy5System (read by reset_run, tests)."""
        return (
            self.blasphemy5_system.blasphemy_5_revived
            if self.blasphemy5_system
            else False
        )

    @blasphemy_5_revived.setter
    def blasphemy_5_revived(self, value: bool) -> None:
        if self.blasphemy5_system:
            self.blasphemy5_system.blasphemy_5_revived = value

    def _init_weapons(self) -> None:
        init_weapons(self)

    def _init_player(self) -> None:
        # Game state
        self.player: Player = Player(self.width // 2, self.height - 80)
        # allow player to access game flags (e.g. growth aura)
        try:
            self.player.game = self
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        self.enemies: Any = pygame.sprite.Group()
        self.projectiles: Any = pygame.sprite.Group()
        self.enemy_projectiles: Any = pygame.sprite.Group()
        self.bosses: Any = pygame.sprite.Group()

        # Allow limited vertical movement (centered on player's baseline).
        # `player_vertical_range` is the total allowed vertical span in pixels.
        # Movement is allowed only *upwards* from the starting baseline.
        self.player_vertical_range: int = 250  # +50px vertical range
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
        # Rerolls available for upgrades (initialized from blasphemy_9 per-run pool at run start)
        self.upgrade_rerolls_remaining: int = 0
        # Weapon choice state and progression
        init_player_weapons(self)

        # Track upgrade levels (how many times each has been taken)
        self.upgrade_levels: Dict[str, int] = {
            "damage": 0,
            "fire_rate": 0,
            "max_health": 0,
            "projectile_size": 0,
            "armor": 0,
        }

        # Permanent stats (meta-progression)
        # Ensure we don't overwrite loaded/persisted stats; set defaults only if missing
        self.permanent_stats.setdefault("power", 0)
        self.permanent_stats.setdefault("vigor", 0)
        self.permanent_stats.setdefault("adrenaline", 0)
        self.permanent_stats.setdefault("structure", 0)

    def _init_entities(self) -> None:
        # Enemy manager (handles pooling/spawning helpers)
        self.collision_system = CollisionSystem(self)
        self.enemy_manager: EnemyManager | None = None
        try:
            self.enemy_manager = EnemyManager(self)
            # Keep initial rates in sync (populate manager fields)
            if hasattr(self, "enemy_spawn_rate"):
                self.enemy_manager.enemy_spawn_rate = self.enemy_spawn_rate
            if hasattr(self, "enemy_spawn_timer"):
                self.enemy_manager.enemy_spawn_timer = self.enemy_spawn_timer
        except (AttributeError, TypeError, ValueError, KeyError):
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
        self.player_facing_right = (
            True  # Track horizontal movement direction for walk animation
        )

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
        # Limbo Final boss
        self._limbo_final_boss_spawned = False

        # Limbo horde event (for regular limbo levels)
        self.limbo_horde_started: bool = False
        # timer used for spawn gating (resets each spawn)
        self.limbo_horde_timer: int = 0
        # track how many frames have elapsed since the horde began; needed to
        # adjust the spawn rate partway through the event
        self.limbo_horde_elapsed: int = 0
        self.limbo_horde_active: bool = False
        self.limbo_horde_completed: bool = False
        # Victory is triggered when boss_limbo_horde dies; countdown starts when
        # all enemies have been cleared from the screen
        self.limbo_horde_victory_timer: int = 0
        # Flag set when boss dies; victory countdown starts once room is empty
        self.limbo_horde_ready_for_victory: bool = False
        # Track horde progress: initial total enemies/bosses, killed count, remaining count
        self.limbo_horde_initial: int = 0
        self.limbo_horde_killed: int = 0
        self.limbo_horde_remaining: int = 0
        # Limbo Final kill countdown (starts when boss_limbo is slain)
        self.limbo_final_victory_timer: int = 0
        self.limbo_final_victory_started: bool = False
        # Scripted satan growth event triggered after fourth horde phase.
        self.satan_growth_active: bool = False
        self.satan_growth_elapsed: int = 0
        self.satan_growth_duration: int = 0  # will be set when triggered
        # record initial player dimensions for scaling
        self.satan_growth_orig_width: int | None = None
        self.satan_growth_orig_height: int | None = None

        # Purgatory horde event (for purgatory levels, no boss, no buff)
        self.purgatory_horde_started: bool = False
        self.purgatory_horde_timer: int = 0
        self.purgatory_horde_elapsed: int = 0
        self.purgatory_horde_active: bool = False
        self.purgatory_horde_completed: bool = False
        self.purgatory_horde_initial: int = 0
        self.purgatory_horde_killed: int = 0
        self.purgatory_horde_remaining: int = 0
        self.purgatory_horde_phase_index: int = 0
        self.purgatory_horde_schedule: list[dict[str, Any]] = []
        # Purgatory explosion (malevolent wave) triggered after 60s horde duration
        self.purgatory_horde_wave_timer: float = 0.0  # tracks expansion of red wave
        self.purgatory_horde_explosion_ready: bool = False  # triggered after 60s
        self.purgatory_horde_victory_timer: int = (
            0  # countdown 5s before victory screen
        )

        # Hell stage barriers
        self.barriers: List[Dict[str, Any]] = []
        self._barrier_spawn_timer: float = 0.0
        self._barrier_next_interval: float = random.uniform(
            BARRIER_SPAWN_INTERVAL_MIN, BARRIER_SPAWN_INTERVAL_MAX
        )

        # victory overlay state
        self.showing_victory: bool = False
        self.victory_alpha: int = 0
        self.victory_fade_duration_ms: int = GAME_OVER_FADE_DURATION_MS
        self.victory_fade_speed: int = max(
            1, int(255 / ((self.victory_fade_duration_ms / 1000.0) * self.fps))
        )
        self.victory_display_timer: int = 0

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

    def _init_managers(self) -> None:
        # Load assets
        self.load_assets()

        # Migrate legacy save file to profile system on first launch
        self._migrate_legacy_save()

        # Initialize global_progress dict, then load any persisted save data so
        # the setdefault calls below only fill in keys missing from the file.
        self.global_progress: Dict[str, Any] = {}
        # Only load if a profile slot is already selected (e.g. on rematch)
        if getattr(self, "active_profile_slot", None) is not None:
            self.load_permanent_stats()

        # Meta‑progression defaults. keys here are safe to call repeatedly.
        self.global_progress.setdefault("meta_xp", 0)
        self.global_progress.setdefault("meta_level", 1)
        self.global_progress.setdefault("meta_points", 0)
        # tracks whether a stage has granted its one-time clear reward
        self.global_progress.setdefault("stages_cleared", {})

        # Apply any persisted display preferences (window size / fullscreen)
        try:
            self.apply_display_prefs()
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        # Apply saved audio preference (migrate from top-level to audio dict)
        try:
            aud = self.global_progress.setdefault("audio", {})
            # legacy support: previously may have stored 'sounds_enabled' directly
            if "sounds_enabled" in self.global_progress and "enabled" not in aud:
                aud["enabled"] = self.global_progress.get("sounds_enabled", True)
            self.sounds_enabled = aud.get("enabled", True)
            aud["enabled"] = self.sounds_enabled
        except (AttributeError, TypeError, ValueError, KeyError):
            # fallback to default
            self.sounds_enabled = True

        # Initialize Pygame UI manager (handles drawing)
        self.ui: PygameUIManager = PygameUIManager(self)

        # Initialize GameStateManager (centralize wave/xp/upgrades/etc.)
        self.game_state: GameStateManager = GameStateManager(self)

        # Initialize WeaponSystem (handles weapon firing and projectile creation)
        try:
            self.weapon_system = WeaponSystem(self)
        except (AttributeError, TypeError, ValueError, KeyError):
            self.weapon_system = None

        # Initialize SpawnSystem (handles enemy spawning and wave progression)
        try:
            self.spawn_system = SpawnSystem(self)
        except (AttributeError, TypeError, ValueError, KeyError):
            self.spawn_system = None

        # Initialize UpgradeSystem (handles weapon upgrades and permanent stats)
        try:
            self.upgrade_system = UpgradeSystem(self)
        except (AttributeError, TypeError, ValueError, KeyError):
            self.upgrade_system = None

        # Initialize InputHandler (handles keyboard and mouse input)
        try:
            self.input_handler = InputHandler(self)
        except (AttributeError, TypeError, ValueError, KeyError):
            self.input_handler = None

        # Initialize TowerSpecialSystem (handles energy bar and fire/blizzard/Voltaic Mayhem specials)
        try:
            from src.systems.tower_special_system import TowerSpecialSystem

            self.tower_special = TowerSpecialSystem(self)
        except (AttributeError, TypeError, ValueError, KeyError):
            self.tower_special = None

        # Initialize Blasphemy5System (handles blink teleport and revive)
        try:
            from src.systems.blasphemy5_system import Blasphemy5System

            self.blasphemy5_system = Blasphemy5System(self)
        except (AttributeError, TypeError, ValueError, KeyError):
            self.blasphemy5_system = None

        # Initialize ScoreSystem (handles meta-progression: XP, levels, points)
        try:
            from src.systems.score_system import ScoreSystem

            self.score_system = ScoreSystem(self)
        except (AttributeError, TypeError, ValueError, KeyError):
            self.score_system = None

        # Initialize DeathSystem (handles enemy/boss death, health drops, XP awards)
        try:
            from src.systems.death_system import DeathSystem

            self.death_system = DeathSystem(self)
        except (AttributeError, TypeError, ValueError, KeyError):
            self.death_system = None

        # Initialize ParticleSystem (handles rendering and updating particle effects)
        try:
            from src.systems.particle_system import ParticleSystem

            self.particle_system = ParticleSystem(self)
        except (AttributeError, TypeError, ValueError, KeyError):
            self.particle_system = None

        # Initialize ProjectileManager (handles pooling/spawn management)
        try:
            from src.systems.projectile_manager import ProjectileManager

            self.projectile_manager = ProjectileManager(self)
        except (AttributeError, TypeError, ValueError, KeyError):
            self.projectile_manager = None

        # Final debug check to show what ended up in permanent_stats (use logger, not print)
        try:
            logger.debug(
                "Final permanent_stats after Game.__init__: %s", self.permanent_stats
            )
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        # Apply any persisted display preferences (window size / fullscreen)
        try:
            self.apply_display_prefs()
        except (AttributeError, TypeError, ValueError, KeyError):
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
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        try:
            dsp = self.global_progress.setdefault("display", {})
            dsp["window_size"] = [self.window_width, self.window_height]
        except (AttributeError, TypeError, ValueError, KeyError):
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
        except (AttributeError, TypeError, ValueError, KeyError):
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

    # Limbo Final boss flag (spawn at ~180s)
    @property
    def limbo_final_boss_spawned(self) -> bool:
        if self.enemy_manager is not None:
            return getattr(self.enemy_manager, "limbo_final_boss_spawned", False)
        return getattr(self, "_limbo_final_boss_spawned", False)

    @limbo_final_boss_spawned.setter
    def limbo_final_boss_spawned(self, val: bool) -> None:
        if self.enemy_manager is not None:
            self.enemy_manager.limbo_final_boss_spawned = val
        else:
            self._limbo_final_boss_spawned = val

    @property
    def limbo_final_boss_immortal(self) -> bool:
        if self.enemy_manager is not None:
            return getattr(self.enemy_manager, "limbo_final_boss_immortal", False)
        return getattr(self, "_limbo_final_boss_immortal", False)

    @limbo_final_boss_immortal.setter
    def limbo_final_boss_immortal(self, val: bool) -> None:
        if self.enemy_manager is not None:
            self.enemy_manager.limbo_final_boss_immortal = val
        else:
            self._limbo_final_boss_immortal = val

    @property
    def limbo_final_lightning_strike(self) -> bool:
        if self.enemy_manager is not None:
            return getattr(self.enemy_manager, "limbo_final_lightning_strike", False)
        return getattr(self, "_limbo_final_lightning_strike", False)

    @limbo_final_lightning_strike.setter
    def limbo_final_lightning_strike(self, val: bool) -> None:
        if self.enemy_manager is not None:
            self.enemy_manager.limbo_final_lightning_strike = val
        else:
            self._limbo_final_lightning_strike = val

    @property
    def limbo_final_lightning_timer(self) -> int:
        if self.enemy_manager is not None:
            return getattr(self.enemy_manager, "limbo_final_lightning_timer", 0)
        return getattr(self, "_limbo_final_lightning_timer", 0)

    @limbo_final_lightning_timer.setter
    def limbo_final_lightning_timer(self, val: int) -> None:
        if self.enemy_manager is not None:
            self.enemy_manager.limbo_final_lightning_timer = val
        else:
            self._limbo_final_lightning_timer = val

    @property
    def limbo_final_lightning_duration_frames(self) -> int:
        if self.enemy_manager is not None:
            return getattr(
                self.enemy_manager,
                "limbo_final_lightning_duration_frames",
                180 + 2 * self.fps,
            )
        return getattr(
            self, "_limbo_final_lightning_duration_frames", 180 + 2 * self.fps
        )

    @limbo_final_lightning_duration_frames.setter
    def limbo_final_lightning_duration_frames(self, val: int) -> None:
        if self.enemy_manager is not None:
            self.enemy_manager.limbo_final_lightning_duration_frames = val
        else:
            self._limbo_final_lightning_duration_frames = val

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
            "enemy_crusader.png",  # optional custom asset for the new crusader type
            "enemy_inquisitor.png",  # optional custom sprite for non-boss inquisitor
            "boss_small.png",
            "boss_medium.png",
            "boss_big.png",
            "boss_final.png",
            "boss_limbo_horde.png",  # optional asset for Limbo horde boss
            "projectile.png",
            "enemy_projectile.png",
            "battlefield_cross.png",  # Bloody cross for battlefield decoration
            # optional Limbo battlefield image (see STAGE_SETTINGS)
            "limbo_battlefield.png",
            # optional Limbo external/full‑screen image (see STAGE_SETTINGS)
            "limbo_background.png",
            # optional Purgatory background(s) (see STAGE_SETTINGS)
            "purgatory_background.png",
            "purgatory_battlefield.png",
            # optional custom statue/tower assets for the three tower types.  game
            # will gracefully fall back to vector art if these are missing.
            "statue_fire.png",
            "statue_storm.png",
            "statue_ice.png",
            # optional Hell stage barrier assets
            "barrier_wood.png",
            "barrier_damaged.png",
            # optional Limbo wall lamp assets
            "lamp1.png",
        ]

        # Preload originals for quick subsequent scaling
        try:
            preload_images(asset_files)
        except (AttributeError, TypeError, ValueError, KeyError):
            # Preloading is best-effort; proceed even if it fails in headless/testing envs
            pass

        for asset in asset_files:
            try:
                self.assets[asset] = get_image(asset)
            except (AttributeError, TypeError, ValueError, KeyError):
                self.assets[asset] = None

    def generate_walls(self) -> None:
        """Generate irregular wall points for collision detection"""

        self.left_wall_points = []
        self.right_wall_points = []
        # Note: fog cache will auto-invalidate on next _build_fog_cache call because
        # the list objects (id()) have changed

        for y in range(0, self.height + 1, 20):
            progress: float = y / self.height
            # Default width per-stage (may be overridden for stage-specific behavior)
            if self.is_limbo_stage():
                width_at_y = 680 - (progress * 280)
            elif self.selected_stage and str(self.selected_stage) in HELL_STAGES:
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
            if self.selected_stage and str(self.selected_stage) in HELL_STAGES:
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

    def generate_limbo_lamps(self) -> None:
        """Generate decorative lamps along limbo walls at regular intervals."""
        if not self.is_limbo_stage():
            self.limbo_lamps = []
            return

        self.limbo_lamps = []
        spacing = LIMBO_LAMP_SPACING  # 120 pixels between lamps

        # Collect candidates first, then filter to get 4 lamps per side
        left_candidates = []
        if self.left_wall_points:
            last_y = -999
            flip = False
            for point in self.left_wall_points:
                if point[1] - last_y >= spacing:
                    lamp_x = point[0] + LIMBO_LAMP_OFFSET  # Inside wall (positive offset)
                    lamp_y = point[1]  # Top-left corner for blit
                    left_candidates.append({"x": lamp_x, "y": lamp_y, "side": "left", "flip": flip})
                    flip = not flip  # Alternate flip
                    last_y = point[1]

        right_candidates = []
        if self.right_wall_points:
            last_y = -999
            flip = False
            for point in self.right_wall_points:
                if point[1] - last_y >= spacing:
                    lamp_x = point[0] - LIMBO_LAMP_OFFSET  # Inside wall (negative offset, symmetric to left)
                    lamp_y = point[1]  # Top-left corner for blit
                    right_candidates.append({"x": lamp_x, "y": lamp_y, "side": "right", "flip": flip})
                    flip = not flip  # Alternate flip
                    last_y = point[1]

        # Skip first (top, cut off) and last 2 (bottom), take 4 from middle
        if len(left_candidates) > 3:
            self.limbo_lamps.extend(left_candidates[1:5])  # indices 1,2,3,4
        if len(right_candidates) > 3:
            self.limbo_lamps.extend(right_candidates[1:5])  # indices 1,2,3,4

        logger.info("Generated %d limbo lamps for stage %s", len(self.limbo_lamps), self.selected_stage)

    def is_limbo_stage(self) -> bool:
        """Return True if the currently selected stage is any variant of Limbo."""
        return bool(self.selected_stage and str(self.selected_stage) in LIMBO_STAGES)

    def is_hell_stage(self) -> bool:
        """Return True if the currently selected stage is any variant of Hell."""
        return bool(self.selected_stage and str(self.selected_stage) in HELL_STAGES)

    def is_purgatory_stage(self) -> bool:
        """Return True if the currently selected stage is any variant of Purgatory.

        This helper is used by drawing logic so battlefield images can be masked
        to the wall polygon in the same way as prologue/limbo.
        """
        return bool(
            self.selected_stage and str(self.selected_stage) in PURGATORY_STAGES
        )

    # --- Helpers for test compatibility ---
    def _enemies_iter(self):
        """Return a list of enemy objects regardless of underlying storage type."""
        if hasattr(self.enemies, "sprites"):
            return self.enemies.sprites()
        try:
            return list(self.enemies)
        except (AttributeError, TypeError, ValueError, KeyError):
            return []

    def _enemy_pos(self, e):
        """Return (x, y) for an enemy.

        Handles both object-style enemies (attributes) and simple dictionaries
        used in tests.  Using ``getattr`` on a dict returns the default value,
        so we check for mapping keys explicitly first.
        """
        if isinstance(e, dict):
            return e.get("x", 0), e.get("y", 0)
        return getattr(e, "x", 0), getattr(e, "y", 0)

    def _enemy_radius(self, e):
        """Return radius for an enemy, supporting dicts as well."""
        if isinstance(e, dict):
            return e.get("radius", 12)
        return getattr(e, "radius", 12)

    def _projectile_radius(self, proj):
        return self.collision_system._projectile_radius(proj)

    def _get_projectile_metadata(self, projectile):
        return self.collision_system._get_projectile_metadata(projectile)

    def _get_hit_enemies_for_projectile(self, projectile):
        return self.collision_system._get_hit_enemies_for_projectile(projectile)

    def _build_spatial_grid(self):
        return self.collision_system._build_spatial_grid()

    def _remove_offscreen_projectiles(self):
        return self.collision_system._remove_offscreen_projectiles()

    def _apply_ice_puddles(self):
        return self.collision_system._apply_ice_puddles()

    def _propagate_burn(self, source_enemy):
        return self.collision_system._propagate_burn(source_enemy)

    def clamp_to_walls(self, x_pos):
        """Keep position within the walls"""
        if not self.left_wall_points or not self.right_wall_points:
            return x_pos

        wall_thickness = WALL_THICKNESS
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

        wall_thickness = WALL_THICKNESS
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
            # GIF recording frame capture
            if getattr(self, "_gif_recording", False):
                self.input_handler._capture_gif_frame()
            self.clock.tick(self.fps)
        self.save_permanent_stats()
        logger.info("Game ended")

    def draw(self) -> None:
        """Main draw method"""
        try:
            # Calculate screen shake — suppress during any pause/overlay state
            shake_x: int = 0
            shake_y: int = 0
            _game_is_paused = (
                self.paused
                or self.showing_main_menu
                or self.showing_stage_menu
                or self.showing_permanent_upgrades
                or getattr(self, "showing_profiles_menu", False)
                or self.showing_game_over
                or getattr(self, "showing_victory", False)
                or getattr(self, "showing_prologo_end", False)
                or getattr(self, "awaiting_upgrade", False)
                or getattr(self, "awaiting_weapon_choice", False)
                or getattr(self, "awaiting_tower_choice", False)
            )
            if self.shake_timer > 0 and not _game_is_paused:
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
                external_drawn = False
                if bg_external_image_name:
                    bg_external_image = get_image(
                        bg_external_image_name,
                        (self.screen.get_width(), self.screen.get_height()),
                    )
                    if bg_external_image:
                        self.screen.blit(bg_external_image, (0, 0))
                        external_drawn = True
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
                        # For prologue and Limbo, use polygon masking to fit the
                        # slanted/irregular walls.  Limbo variants behave exactly like
                        # prologo in this respect so they avoid the rectangular
                        # clipping area which would leave gaps when walls lean.
                        # stages with non‑rectangular fence polygons need masking
                        if (
                            self.selected_stage == "prologo"
                            or self.is_limbo_stage()
                            or self.is_purgatory_stage()
                        ):
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

                                # Check if cached masked image is still valid
                                cache_key = (
                                    bg_image_name,
                                    id(self.left_wall_points),
                                    len(self.left_wall_points),
                                )
                                if getattr(
                                    self, "_masked_bg_cache_key", None
                                ) != cache_key or not getattr(
                                    self, "_masked_bg_cache", None
                                ):
                                    # Cache miss or invalidated: rebuild masked surface
                                    # Create mask from polygon
                                    mask_surface = pygame.Surface(
                                        (bbox_width, bbox_height), pygame.SRCALPHA
                                    )
                                    mask_surface.fill((0, 0, 0, 0))  # Transparent

                                    # Translate points to mask coordinates
                                    translated_points = [
                                        (p[0] - min_x, p[1] - min_y)
                                        for p in inside_points
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

                                    # Store in cache for future frames
                                    self._masked_bg_cache = masked_image
                                    self._masked_bg_cache_pos = (min_x, min_y)
                                    self._masked_bg_cache_key = cache_key

                                # Use cached masked surface
                                self.screen.blit(
                                    self._masked_bg_cache, self._masked_bg_cache_pos
                                )
                                self.background_image_drawn = True
                            else:
                                # if the main battlefield image is missing, do not
                                # overwrite the previously drawn external background;
                                # let UI logic later fill the interior if needed.
                                if not external_drawn:
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
                                if not external_drawn:
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
                            if not external_drawn:
                                self.screen.fill(stage_settings["bg_color"])
                else:
                    if not external_drawn:
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
                # Clouds are large, decorative shapes that should appear behind
                # enemies and other objects; draw them after the world but before
                # game objects are rendered.  The UI manager handles purgatory
                # stages internally.
                self.draw_game_objects(shake_x, shake_y)
                # Fog must be drawn after world/objects so it tints enemies and player
                try:
                    self.draw_fog(shake_x, shake_y)
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
                self.draw_skullboom_particles(shake_x, shake_y)
                self.draw_ice_particles(shake_x, shake_y)
                self.draw_ice_puddles(shake_x, shake_y)
                # Draw centralized floating texts (damage numbers, etc.)
                try:
                    self.draw_floating_texts(shake_x, shake_y)
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
                # Draw special effects (lightning, explosions, waves, etc.)
                try:
                    self.draw_special_effects(shake_x, shake_y)
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

            # Draw UI
            self.draw_ui(shake_x, shake_y)

            # FPS counter — always on top, no shake
            if hasattr(self, "ui") and hasattr(self.ui, "draw_fps_counter"):
                self.ui.draw_fps_counter()

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
            except (AttributeError, TypeError, ValueError, KeyError):
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
        """Delegate pedestal drawing to Pygame UI manager.

        Pedestals were removed from the visible game world; the UI implementation
        now performs no drawing.  This method remains for compatibility with
        existing codepaths.
        """
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

    def _draw_particles(
        self,
        particles: list,
        color_fn,
        alpha_fn,
        shake_x: int = 0,
        shake_y: int = 0,
        filter_fn=None,
    ) -> None:
        """Delegate to ParticleSystem."""
        if self.particle_system:
            return self.particle_system.draw_particles(
                self.screen, particles, color_fn, alpha_fn, shake_x, shake_y, filter_fn
            )

    def draw_skullboom_particles(self, shake_x: int = 0, shake_y: int = 0) -> None:
        """Delegate to ParticleSystem."""
        if self.particle_system:
            return self.particle_system.draw_skullboom_particles(shake_x, shake_y)

    def _draw_skullboom_particles_old(self, shake_x=0, shake_y=0) -> None:
        """DEPRECATED: Use ParticleSystem instead."""
        pass

    def spawn_floating_text(
        self,
        text: str,
        x: float,
        y: float,
        *,
        color=(255, 255, 255),
        outline_color: tuple[int, int, int] | None = None,
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
            # Avoid duplicates: if a text with same string + position already exists,
            # remove it if the new one has a different color (e.g. red crit replacing
            # plain white) or skip adding if exactly identical. This prevents the
            # white number appearing beneath a red crit.
            for existing in list(self.floating_texts):
                try:
                    if (
                        existing.text == text
                        and abs(existing.x - x) < 0.5
                        and abs(existing.y - y) < 0.5
                    ):
                        if existing.color != tuple(color):
                            try:
                                self.floating_texts.remove(existing)
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass
                        else:
                            # same color/position/text already queued
                            return
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

            ft = FloatingText(
                text,
                x,
                y,
                color=color,
                outline_color=outline_color,
                font_size=font_size,
                vy=vy,
                life=life,
            )
            self.floating_texts.append(ft)
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def _floating_text_style_for_projectile(
        self, projectile, base_color=(255, 255, 255), base_font_size=20
    ):
        return self.collision_system._floating_text_style_for_projectile(
            projectile, base_color, base_font_size
        )

    def _update_floating_texts(self) -> None:
        if not getattr(self, "floating_texts", None):
            return
        alive = []
        for ft in list(self.floating_texts):
            try:
                ft.update()
                if ft.alive:
                    alive.append(ft)
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
        self.floating_texts = alive

    def _update_health_drops(self) -> None:
        """Move health drops downward and handle collection by the player.

        Wrapper delegating to DeathSystem. See DeathSystem.update_health_drops()
        """
        if self.death_system:
            return self.death_system.update_health_drops()

    def _update_barriers(self) -> None:
        """Spawn, age, and despawn hell barriers. Only active on hell stages."""
        if not self.is_hell_stage():
            return
        if self.time_elapsed < BARRIER_SPAWN_DELAY:
            return

        dt = 1.0 / self.fps

        # Age and remove dead/expired barriers
        self.barriers = [
            b for b in self.barriers if b["hp"] > 0 and b["despawn_timer"] > 0
        ]
        for b in self.barriers:
            b["despawn_timer"] -= dt

        # Spawn new barrier if below max
        if len(self.barriers) >= BARRIER_MAX_COUNT:
            return

        self._barrier_spawn_timer += dt
        if self._barrier_spawn_timer < self._barrier_next_interval:
            return

        self._barrier_spawn_timer = 0.0
        # Pick a new random interval for next spawn
        self._barrier_next_interval = random.uniform(
            BARRIER_SPAWN_INTERVAL_MIN, BARRIER_SPAWN_INTERVAL_MAX
        )

        for _attempt in range(10):
            bx = random.randint(HELL_BARRIER_X_MIN, HELL_BARRIER_X_MAX - BARRIER_WIDTH)
            by = random.randint(HELL_BARRIER_Y_MIN, HELL_BARRIER_Y_MAX - BARRIER_HEIGHT)
            candidate = pygame.Rect(
                bx - 20, by - 20, BARRIER_WIDTH + 40, BARRIER_HEIGHT + 40
            )
            if any(candidate.colliderect(b["rect"]) for b in self.barriers):
                continue
            self.barriers.append(
                {
                    "x": bx,
                    "y": by,
                    "w": BARRIER_WIDTH,
                    "h": BARRIER_HEIGHT,
                    "hp": BARRIER_HP,
                    "max_hp": BARRIER_HP,
                    "rect": pygame.Rect(bx, by, BARRIER_WIDTH, BARRIER_HEIGHT),
                    "despawn_timer": BARRIER_DESPAWN_TIME,
                }
            )
            break

    def draw_floating_texts(self, shake_x: int = 0, shake_y: int = 0) -> None:
        """Delegate to ParticleSystem."""
        if self.particle_system:
            return self.particle_system.draw_floating_texts(shake_x, shake_y)

    def draw_ice_particles(self, shake_x: int = 0, shake_y: int = 0) -> None:
        """Delegate to ParticleSystem."""
        if self.particle_system:
            return self.particle_system.draw_ice_particles(shake_x, shake_y)

    def draw_ice_puddles(self, shake_x: int = 0, shake_y: int = 0) -> None:
        """Delegate to ParticleSystem."""
        if self.particle_system:
            return self.particle_system.draw_ice_puddles(shake_x, shake_y)

    def _draw_blizzard_spiral_particles(
        self, puddle: dict, px: float, py: float, radius: int
    ) -> None:
        """Delegate to ParticleSystem."""
        if self.particle_system:
            return self.particle_system._draw_blizzard_spiral_particles(
                puddle, px, py, radius
            )

    def add_score(self, points) -> None:
        """Add unmodified points to the game's score.

        This keeps `Game.score` and `GameStateManager.score` in sync.  Meta-XP
        is awarded at a 1:1 ratio with the raw points value; the previous
        `score_multiplier` has been removed and is now ignored.
        """
        try:
            amt = int(points)
            self.score += amt

            try:
                if (
                    hasattr(self, "game_state")
                    and getattr(self.game_state, "score", None) is not None
                ):
                    self.game_state.score += amt
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

            # award meta xp using helper (handles leveling and points)
            try:
                self.award_meta_xp(amt)
            except Exception as e:
                logger.exception(f"Failed to award meta_xp({amt}): {e}")
        except Exception as e:
            logger.exception(f"Failed in add_score: {e}")

    def draw_ui(self, shake_x=0, shake_y=0) -> None:
        """Delegate UI drawing work to the Pygame UI manager where appropriate."""
        # Draw stage start countdown (kept here to avoid changing menu ordering)
        if self.stage_start_countdown > 0:
            font_large: pygame.Font = pygame.font.SysFont("chiller", 90)
            countdown_text: pygame.Surface = font_large.render(
                str(self.stage_start_countdown), True, (180, 140, 20)
            )
            # Apply fade-out effect in last 0.5 seconds (30 frames at 60 FPS)
            alpha = 255
            fade_start_frames = 30
            if self.countdown_fade_timer > self.fps - fade_start_frames:
                # Fade from 255 to 0 over last 30 frames
                frames_into_fade = self.countdown_fade_timer - (self.fps - fade_start_frames)
                alpha = max(0, 255 - int(255 * frames_into_fade / fade_start_frames))

            countdown_text.set_alpha(alpha)

            # Draw main text (no outline)
            self.screen.blit(
                countdown_text,
                (
                    self.width // 2 - countdown_text.get_width() // 2 + shake_x,
                    self.height // 2 - countdown_text.get_height() // 2 + shake_y,
                ),
            )

        # If victory overlay active, draw that first and skip everything else
        if getattr(self, "showing_victory", False):
            if hasattr(self, "ui") and hasattr(self.ui, "draw_victory"):
                self.ui.draw_victory(shake_x, shake_y)
            return

        # Draw menus (delegated to existing Game methods to preserve behavior)
        # Profiles menu has highest priority — shown instead of anything else
        if getattr(self, "showing_profiles_menu", False):
            self.draw_profiles_menu(shake_x, shake_y)
            return

        # If game over is active, draw overlay and skip other UI
        if self.showing_game_over:
            self.draw_game_over(shake_x, shake_y)
            return

        # Draw HUD if in game
        if (
            self.selected_stage
            and not self.showing_main_menu
            and not self.showing_stage_menu
            and not self.showing_permanent_upgrades
        ):
            self.ui.draw_hud(shake_x, shake_y)

        if self.showing_main_menu:
            self.draw_main_menu(shake_x, shake_y)
        elif self.showing_stage_menu:
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
        elif self.paused and not getattr(self, "_paused_by_blasphemy5", False):
            # Do not show the standard pause menu when the pause was caused by
            # a temporary blasphemy_5 revive — display only centered messages.
            self.draw_pause_menu(shake_x, shake_y)

        # Always draw pause confirmation dialog if active (can appear even without pause menu)
        # This allows ALT+F4 to show quit confirmation during gameplay
        if getattr(self, "pause_confirmation", None):
            if hasattr(self, "ui") and hasattr(
                self.ui, "draw_pause_confirmation_dialog"
            ):
                self.ui.draw_pause_confirmation_dialog(shake_x, shake_y)

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

    def draw_main_menu(self, shake_x=0, shake_y=0) -> None:
        """Wrapper: delegate main menu drawing to UI manager."""
        if hasattr(self, "ui") and hasattr(self.ui, "draw_main_menu"):
            self.ui.draw_main_menu(shake_x, shake_y)
        # Draw unlock overlay if showing
        if getattr(self, "showing_unlock_overlay", False):
            if hasattr(self, "ui") and hasattr(self.ui, "effects"):
                self.ui.effects.draw_unlock_overlay(shake_x, shake_y)
        return None

    def draw_profiles_menu(self, shake_x=0, shake_y=0) -> None:
        """Wrapper: delegate profiles menu drawing to UI manager."""
        if hasattr(self, "ui") and hasattr(self.ui, "draw_profiles_menu"):
            self.ui.draw_profiles_menu(shake_x, shake_y)
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

    def draw_prologo_end(self, shake_x=0, shake_y=0) -> None:
        """Draw the prologo completion screen"""
        if hasattr(self, "ui") and hasattr(self.ui, "draw_prologo_end"):
            self.ui.draw_prologo_end(shake_x, shake_y)
        return None

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
        if hasattr(self, "ui") and hasattr(self.ui, "draw_weapon_selection"):
            self.ui.draw_weapon_selection(shake_x, shake_y)
        return None

    def draw_tower_selection(self, shake_x=0, shake_y=0) -> None:
        """Draw tower selection screen (Purgatory)."""
        if hasattr(self, "ui") and hasattr(self.ui, "draw_tower_selection"):
            self.ui.draw_tower_selection(shake_x, shake_y)
        return None

    def _player_stats_display_items(self):
        """Return (key, value) pairs to display in the player stats sheet."""
        if self.upgrade_system is not None:
            return self.upgrade_system._player_stats_display_items()

    def permanent_stat_effect_text(self, key: str, level: int) -> str:
        """Return a human-friendly description of the per-level and total effect for a permanent stat."""
        if self.upgrade_system is not None:
            return self.upgrade_system.permanent_stat_effect_text(key, level)

    def _enforce_center_requirement(self, key_prefix: str) -> None:
        """Ensure the center tier (7) is only active when a full column of 3 exists."""
        if self.upgrade_system is not None:
            return self.upgrade_system._enforce_center_requirement(key_prefix)

    def apply_permanent_stats(self) -> None:
        """Apply permanent stat effects to both game-level and player-level multipliers."""
        if self.upgrade_system is not None:
            return self.upgrade_system.apply_permanent_stats()

    def _player_damage_vs_burning(self, projectile, enemy, base_damage):
        return self.collision_system._player_damage_vs_burning(
            projectile, enemy, base_damage
        )

    def _skill_tooltip_lines(self, key_prefix: str, tier: int) -> list:
        """Return list of text lines to show in a tooltip for a given skill tree tier."""
        if self.upgrade_system is not None:
            return self.upgrade_system._skill_tooltip_lines(key_prefix, tier)

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
        if hasattr(self, "ui") and hasattr(self.ui, "draw_upgrade_selection"):
            self.ui.draw_upgrade_selection(shake_x, shake_y)
        return None

    def handle_events(self) -> None:
        return self.input_handler.handle_events() if self.input_handler else None

    def handle_keydown(self, key):
        return self.input_handler.handle_keydown(key) if self.input_handler else None

    def handle_mouse_click(self, pos, button=1):
        return (
            self.input_handler.handle_mouse_click(pos, button)
            if self.input_handler
            else None
        )

    def show_stage_menu(self) -> None:
        # opening the stage menu represents leaving the current level; energy
        # and special state should not persist when the player returns.
        if self.tower_special is not None:
            self.tower_special.reset()
        return self.input_handler.show_stage_menu() if self.input_handler else None

    def show_permanent_upgrades(self) -> None:
        return (
            self.input_handler.show_permanent_upgrades() if self.input_handler else None
        )

    def select_stage(self, stage) -> None:
        result = self.input_handler.select_stage(stage) if self.input_handler else None
        # if we just picked a limbo stage, apply the spawn rate penalty so wave0
        # reflects the slower pace immediately.  final limbo should be treated the
        # same as the other limbo variants.
        if stage in ("limbo", "limbo_2", "limbo_3", "limbo_final"):
            from src.balance import LIMBO_SPAWN_RATE_PENALTY

            try:
                self.enemy_spawn_rate += LIMBO_SPAWN_RATE_PENALTY
                if hasattr(self, "enemy_manager") and self.enemy_manager is not None:
                    self.enemy_manager.enemy_spawn_rate = self.enemy_spawn_rate
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

        # limbo_final is extra punishing: ramp slopes should be doubled
        if stage == "limbo_final":
            try:
                self.spawn_ramp_slope_pre = SPAWN_RAMP_SLOPE_PRE * 2
                self.spawn_ramp_slope_post = SPAWN_RAMP_SLOPE_POST * 2
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
        return result

    def generate_dead_trees(self) -> None:
        """Generate dead tree data once for Limbo stage"""
        self.dead_trees = [
            {"x": 390, "y": 76, "height": 58, "trunk_width": 3},
            {"x": 515, "y": 52, "height": 68, "trunk_width": 4},
            {"x": 645, "y": 96, "height": 46, "trunk_width": 3},
            {"x": 772, "y": 62, "height": 62, "trunk_width": 5},
            {"x": 898, "y": 84, "height": 52, "trunk_width": 3},
        ]

        for tree in self.dead_trees:
            h = tree["height"]
            tw = tree["trunk_width"]

            # Pre-generate trunk crack/texture marks for deterministic rendering
            tree["cracks"] = []
            for _ in range(random.randint(2, 4)):
                tree["cracks"].append(
                    {
                        "x_off": random.randint(-tw + 1, tw - 1),
                        "y_frac": random.uniform(0.15, 0.90),
                        "length": random.randint(5, 14),
                        "dir": random.choice([-1, 1]),
                    }
                )

            # 40% chance of trunk splitting into two tines (Y-fork)
            if random.random() < 0.40:
                tree["split"] = {
                    "frac": random.uniform(0.28, 0.55),
                    "left_dx": random.randint(5, 12),
                    "left_dy": random.randint(8, 18),
                    "right_dx": random.randint(5, 12),
                    "right_dy": random.randint(8, 18),
                }
            else:
                tree["split"] = None

            tree["branches"] = []
            num_branches: int = random.randint(3, 5)

            for i in range(num_branches):
                # Branches ONLY in the upper half of the trunk (crown region).
                # frac 0.0 = trunk tip (top of screen), frac 0.5 = midpoint.
                frac = (i / max(num_branches - 1, 1)) * 0.5
                branch_start_y = tree["y"] + h * frac

                # Short, gnarled branches — lower ones slightly longer
                length_base = int(8 + 10 * frac * 2)  # 8 at tip, ~18 at mid
                branch_length: int = random.randint(
                    max(6, length_base - 4), max(10, length_base + 5)
                )
                branch_angle: int = random.choice([-1, 1])

                # Crown twigs reach more upward; mid branches spread more horizontal
                if frac < 0.20:
                    rise = random.randint(8, 16)
                else:
                    rise = random.randint(3, 9)
                branch_end_y = branch_start_y - rise

                thickness = 2 if frac >= 0.15 else 1

                branch = {
                    "start_y": branch_start_y,
                    "end_x": tree["x"] + branch_length * branch_angle,
                    "end_y": branch_end_y,
                    "thickness": thickness,
                    "sub_branches": [],
                }

                # Sub-branches: 0–1 per main branch (sparse)
                if random.random() < 0.50:
                    t = random.uniform(0.40, 0.70)
                    sub_sx = tree["x"] + (branch["end_x"] - tree["x"]) * t
                    sub_sy = branch_start_y + (branch_end_y - branch_start_y) * t
                    sub_len = random.randint(4, 9)
                    sub_ang = random.choice([-1, 1])
                    sub_rise = random.randint(2, 6)
                    branch["sub_branches"].append(
                        {
                            "start_x": sub_sx,
                            "start_y": sub_sy,
                            "end_x": sub_sx + sub_len * sub_ang,
                            "end_y": sub_sy - sub_rise,
                            "sub_branches": [],
                        }
                    )

                tree["branches"].append(branch)

    def reset_run(self) -> None:
        """Reset game state for a new run

        This also clears any accumulated tower energy.  Energy is stored on the
        *Game* object and counts as run-specific; carrying it between runs would
        allow players to stockpile specials when returning to the main menu, which
        violates the design.  Tests ensure this behaviour.
        """
        # tower energy and special state belongs to a single run/level, so clear it up front
        if self.tower_special is not None:
            self.tower_special.reset()

        # Reset Blasphemy 5 system (revive + blink state)
        if self.blasphemy5_system is not None:
            self.blasphemy5_system.reset()
        self._paused_by_blasphemy5 = False

        # Reset player position and per-run upgrades
        self.player.x = self.width // 2
        self.player.y = self.height - 80
        self.player.health = self.player.max_health
        # Per-run upgrade attributes — must be reset so they don't carry over between runs
        self.player.shield_charges = 0
        self.player.shield_upgrade_level = 0
        self.player.shield_cooldown_timer = 0
        self.player.kill_explosion_enabled = False
        self.player.kill_explosion_upgrades = 0
        self.player.kill_counter = 0
        self.player.regen_per_5s = 0.0
        self.player.regen_timer = 0
        self.player.base_speed = 220.0  # restore original before apply_permanent_stats re-applies blasphemy_7
        self.player.speed = 220.0

        # Reset game over flag so it can be triggered again in this run
        self._game_over_triggered = False

        # Reset run counters
        self.enemies_killed_this_run = 0

        # Reset multipliers (base values; perma upgrades applied by apply_permanent_stats)
        self.player_damage = PLAYER_BASE_DAMAGE
        self.damage_multiplier = 1.0
        self.fire_rate_multiplier = 1.0
        self.projectile_size_multiplier = 1.0
        # Apply STRUCTURE effect (2% damage reduction per level)
        self.damage_reduction_multiplier = 1.0 - (
            self.permanent_stats.get("structure", 0) * 0.02
        )
        # Ensure permanent stat effects are applied immediately (also sets xp_multiplier)
        self.apply_permanent_stats()

        # Initialize Blasphemy 9 per-run reroll pool (2 rerolls per level, consumable across level-ups)
        # Example: blasphemy_9 == 3 -> upgrade_rerolls_remaining = 6 for the run
        self.upgrade_rerolls_remaining = self.permanent_stats.get("blasphemy_9", 0) * 2

        # Reset game state
        self.enemies.empty()
        self.projectiles.empty()
        self.enemy_projectiles.empty()
        self.bosses.empty()
        self.skullboom_particles.clear()
        self.blasphemy5_particles.clear()
        self.skullboom_explosions.clear()
        self.ice_particles.clear()
        self.ice_puddles.clear()

        self.wave = 0
        self.wave_time = 0.0
        # Reset spawn timer to the configured spawn rate (avoid immediate spawn)
        self.enemy_spawn_timer = self.base_spawn_rate
        self.enemy_spawn_rate = self.base_spawn_rate
        self.spawn_accel_timer = 20 * self.fps
        self.time_elapsed = 0.0
        # clear giant cooldown when a new run begins so the first giant
        # isn't accidentally blocked by leftover state from a previous play.
        if getattr(self, "spawn_system", None) is not None:
            try:
                self.spawn_system.last_giant_spawn_time = -float("inf")
                self.spawn_system.pentagram_spawned = False
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
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
        self._limbo_final_boss_spawned = False
        self.limbo_final_boss_immortal = False
        self.limbo_final_lightning_timer = 0
        self.limbo_final_lightning_strike = False

        # Reset limbo horde tracking
        self.limbo_horde_started = False
        self.limbo_horde_timer = 0
        self.limbo_horde_elapsed = 0
        self.limbo_horde_active = False
        self.limbo_horde_completed = False
        self.limbo_horde_ready_for_victory = False
        self.limbo_horde_initial = 0
        self.limbo_horde_killed = 0
        self.limbo_horde_remaining = 0
        self.limbo_horde_schedule = []
        self.limbo_horde_phase_index = 0
        # clear any pending limbo final victory countdown
        self.limbo_final_victory_timer = 0
        self.limbo_final_victory_started = False
        # reset satan growth state
        self.satan_growth_active = False
        self.satan_growth_elapsed = 0
        self.satan_growth_duration = 0
        self.satan_growth_orig_width = None
        self.satan_growth_orig_height = None
        self.satan_growth_persistent = False

        # Reset purgatory horde tracking
        self.purgatory_horde_started = False
        self.purgatory_horde_timer = 0
        self.purgatory_horde_elapsed = 0
        self.purgatory_horde_active = False
        self.purgatory_horde_completed = False
        self.purgatory_horde_initial = 0
        self.purgatory_horde_killed = 0
        self.purgatory_horde_remaining = 0
        self.purgatory_horde_schedule = []
        self.purgatory_horde_phase_index = 0
        self.purgatory_horde_wave_timer = 0.0
        self.purgatory_horde_explosion_ready = False
        self.purgatory_horde_victory_timer = 0

        # Reset hell barriers
        self.barriers = []
        self._barrier_spawn_timer = 0.0
        self._barrier_next_interval = random.uniform(
            BARRIER_SPAWN_INTERVAL_MIN, BARRIER_SPAWN_INTERVAL_MAX
        )

        # Reset limbo lamps (decorative wall elements)
        self.limbo_lamps = []

        # Reset stage start countdown
        self.stage_start_countdown = 0
        self.stage_start_timer = 0
        self.countdown_fade_timer = 0

        # Reset weapons and upgrades
        self.player_weapons = []
        self.weapon_levels = {}
        self.orbitals = []
        self.burst_count = 0
        self.burst_cooldown = 0
        self.shake_timer = 0
        self.shake_intensity = 0
        # Reset alternating statue cooldown and ensure left fires first
        self.statue_cooldown = 0
        self.statue_next_left = True

        # Reset player stats (keep permanent upgrades)
        self.player.xp = 0
        self.player.level = 1
        self.player.xp_to_next_level = XP_BASE
        # Permanent upgrade application:
        # 'power' gives +5% damage per level
        self.player.damage_multiplier = 1.0 + (
            self.permanent_stats.get("power", 0) * 0.05
        )
        # 'adrenaline' gives +5% fire rate per level
        self.player.fire_rate_multiplier = 1.0 + (
            self.permanent_stats.get("adrenaline", 0) * 0.05
        )
        self.player.projectile_size_multiplier = DEFAULT_PROJECTILE_SIZE_MULTIPLIER
        # Apply permanent STRUCTURE, Blasphemy 3 and Blasphemy 6 effects to player (damage reduction)
        self.player.damage_reduction_multiplier = max(
            0.0,
            DEFAULT_DAMAGE_REDUCTION_MULTIPLIER
            - (self.permanent_stats.get("structure", 0) * 0.03)
            - (self.permanent_stats.get("blasphemy_3", 0) * 0.10)
            - (self.permanent_stats.get("blasphemy_6", 0) * 0.10),
        )
        # Apply VIGOR + Blasphemy 1 effects to player max health
        # (blasphemy_2 no longer increases max HP; it only provides periodic regen
        # at 0.5 HP every 2s per level)
        self.player.max_health = (
            PLAYER_BASE_HEALTH
            + (self.permanent_stats.get("vigor", 0) * 10)
            + (self.permanent_stats.get("blasphemy_1", 0) * 15)
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
            "shield": 0,
            "kill_explosion": 0,
            "movement_speed": 0,
            "health_regen": 0,
            "xp": 0,
            "tower_fire_rate": 0,
        }

        self.paused = False
        self.awaiting_upgrade = False
        self.awaiting_weapon_choice = False
        # Reset tower choice state as well to avoid stale flags causing premature countdown
        self.awaiting_tower_choice = False
        self.tower_choices = []
        self.selected_tower_index = 0
        self.is_initial_tower_choice = False

    # ------------------------------------------------------------------
    # Meta‑progression helpers (delegated to ScoreSystem)
    # ------------------------------------------------------------------

    def get_meta_xp_to_next_level(self) -> int:
        """Return the amount of meta‑XP required for the next meta level."""
        if self.score_system:
            return self.score_system.get_meta_xp_to_next_level()
        return 1000

    def award_meta_xp(self, xp: int) -> None:
        """Increment meta XP and handle any level-ups."""
        if self.score_system:
            self.score_system.award_meta_xp(xp)

    def award_stage_clear(self, stage: str) -> bool:
        """Award the one-time completion reward for a stage."""
        if self.score_system:
            return self.score_system.award_stage_clear(stage)
        return False

    def record_enemy_kill(self) -> None:
        """Record a single enemy kill for the current run."""
        self.enemies_killed_this_run += 1
        if self.score_system:
            self.score_system.record_enemy_kill()

    def _profile_path(self, slot: int):
        """Return the Path for a given profile slot (1-3)."""
        return profile_path(slot)

    def _migrate_legacy_save(self) -> None:
        """Move permanent_stats.json → profile_1.json on first launch with new profile system."""
        migrate_legacy_save()

    def load_permanent_stats(self) -> None:
        """Load permanent stats and global meta-progress from disk."""
        load_permanent_stats(self)

    def save_permanent_stats(self) -> None:
        """Write permanent stats and global meta-progress to disk."""
        save_permanent_stats(self)

    def get_profile_info(self, slot: int) -> dict:
        """Return display info for a profile slot without loading full stats into game state."""
        return get_profile_info(slot)

    def select_profile(self, slot: int) -> None:
        """Set the active profile slot and load its data."""
        # Save the CURRENT profile before switching so in-memory progress isn't lost
        if getattr(self, "active_profile_slot", None) is not None:
            try:
                self.save_permanent_stats()
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
        self.active_profile_slot = slot
        # Reset stats before loading so old data doesn't bleed in
        self.permanent_stats = {}
        self.global_progress = {}
        self.global_progress.setdefault("meta_xp", 0)
        self.global_progress.setdefault("meta_level", 1)
        self.global_progress.setdefault("meta_points", 0)
        self.global_progress.setdefault("stages_cleared", {})
        self.load_permanent_stats()
        # Fill any gaps with defaults
        self.global_progress.setdefault("meta_xp", 0)
        self.global_progress.setdefault("meta_level", 1)
        self.global_progress.setdefault("meta_points", 0)
        self.global_progress.setdefault("stages_cleared", {})
        # Ensure profile_name is set
        self.global_progress.setdefault("profile_name", f"Profile {slot}")
        # Save selected slot so it persists across sessions
        self.global_progress["active_profile_slot"] = slot
        try:
            self.save_permanent_stats()
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        logger.info("Selected profile slot %s", slot)

    def delete_profile(self, slot: int) -> None:
        """Delete a profile slot file and deactivate if it was active."""
        path = self._profile_path(slot)
        try:
            path.unlink(missing_ok=True)
            logger.info("Deleted profile slot %s", slot)
        except Exception as e:
            logger.warning("Could not delete profile %s: %s", slot, e)
        if getattr(self, "active_profile_slot", None) == slot:
            self.active_profile_slot = None
            self.permanent_stats = {}
            self.global_progress = {}
            self.global_progress.setdefault("meta_xp", 0)
            self.global_progress.setdefault("meta_level", 1)
            self.global_progress.setdefault("meta_points", 0)
            self.global_progress.setdefault("stages_cleared", {})

    def reset_game(self) -> None:
        """Reset everything EXCEPT permanent upgrades.

        Upgrades are still stored in memory for the duration of the Game object,
        but there is no longer any mechanism to save them between sessions.  A
        fresh Game() will always start with zero permanent stats.
        """
        # Persist meta progress (XP, level, points) before resetting the run
        if getattr(self, "active_profile_slot", None) is not None:
            try:
                self.save_permanent_stats()
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
        self.reset_run()
        self.selected_stage = None
        # Preserve `permanent_stats` so assigned points remain across runs until the
        # player explicitly upgrades/downgrades them in the Permanent Upgrades menu.
        self.showing_main_menu = True
        self.showing_stage_menu = False
        self.showing_profiles_menu = False
        self.showing_permanent_upgrades = False
        # Reset game over overlay so it doesn't persist when returning to menu
        self.showing_game_over = False
        self.game_over_alpha = 0
        # Check if there are pending unlock notifications from the last run
        if self.global_progress.get("pending_unlock_notifications"):
            self.showing_unlock_overlay = True
            self.unlock_overlay_alpha = 0.0
        else:
            self.showing_unlock_overlay = False
            self.unlock_overlay_alpha = 0.0

    def toggle_pause(self) -> None:
        return self.input_handler.toggle_pause() if self.input_handler else None

    def get_difficulty_multiplier_per_wave(self) -> float:
        """Return the per-wave difficulty increment for the current stage.

        The global ``DIFFICULTY_MULTIPLIER_PER_WAVE`` value applies everywhere
        except on the three limbo stages, which use a slightly smaller value to
        soften the curve due to the late-game horde event.
        """
        from src.balance import (
            DIFFICULTY_MULTIPLIER_PER_WAVE,
            LIMBO_DIFFICULTY_MULTIPLIER_PER_WAVE,
        )

        if getattr(self, "selected_stage", None) in ("limbo", "limbo_2", "limbo_3"):
            return LIMBO_DIFFICULTY_MULTIPLIER_PER_WAVE
        return DIFFICULTY_MULTIPLIER_PER_WAVE

    def update_game(self) -> None:
        """Compatibility wrapper used by tests to advance one frame of game logic.

        Tests may call this while menus are active; temporarily force the game into
        in-game state so timers and spawning logic advance for deterministic tests.
        """
        prev_states = (
            self.showing_stage_menu,
            self.showing_permanent_upgrades,
            self.showing_prologo_end,
            self.showing_main_menu,
        )
        self.showing_stage_menu = False
        self.showing_permanent_upgrades = False
        self.showing_prologo_end = False
        self.showing_main_menu = False
        try:
            return self.update()
        finally:
            (
                self.showing_stage_menu,
                self.showing_permanent_upgrades,
                self.showing_prologo_end,
                self.showing_main_menu,
            ) = prev_states

    def stop_game_loop(self) -> None:
        """Stop the running game loop (used by tests and GUI tear-down)."""
        self.running = False
        try:
            pygame.quit()
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def execute_pause_option(self) -> None:
        return self.input_handler.execute_pause_option() if self.input_handler else None

    def continue_to_limbo(self) -> None:
        return self.input_handler.continue_to_limbo() if self.input_handler else None

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

    def _update_pre_guard_state(self) -> None:
        """Update state that must tick even while paused (before early-return guards)."""
        # update any fire-special smoke particles that are drifting
        self._update_fire_smoke()

        # Update Blasphemy 5 system (blink animation + cooldown + auto-resume)
        if self.blasphemy5_system:
            self.blasphemy5_system.update()

        # Check if the horde boss has died (independent of projectile collisions).
        # If boss_limbo_horde is dead and we haven't set the victory flag yet,
        # do so now so the countdown can begin.
        if getattr(self, "limbo_horde_active", False) and not getattr(
            self, "limbo_horde_completed", False
        ):
            for boss in list(self.bosses):
                if (
                    getattr(boss, "enemy_type", "") == "boss_limbo_horde"
                    and boss.health <= 0
                ):
                    # Boss has died; trigger victory setup
                    try:
                        self.limbo_horde_boss_killed = True
                        self.limbo_horde_active = False
                        self.limbo_horde_completed = True
                        self.limbo_horde_ready_for_victory = True
                        print(
                            f"[LIMBO_HORDE] Boss death detected in update! "
                            f"Setting victory ready. Enemies: {len(self.enemies)}, Bosses: {len(self.bosses)}"
                        )
                        # Clear all remaining enemies and bosses immediately
                        try:
                            self.enemies.empty()
                            self.bosses.empty()
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass

        # If the horde has been defeated we don't immediately show the
        # victory overlay; we want to wait until every enemy has actually
        # vanished from the screen.  When boss_limbo_horde dies it sets
        # ``limbo_horde_ready_for_victory`` but the countdown is postponed
        # until the enemy group empties.  The check is performed here during
        # the normal per-frame update so the final removal gets a chance to run.
        # In extremely rare situations the flag might be lost (e.g. exotic race
        # conditions, or tests that mutate the state directly).  We still want
        # a countdown to start once the room is empty if the horde is marked
        # completed, so include that as a fallback condition.  Also only run
        # the check if a timer isn't already active to avoid spinning the
        # counter back up repeatedly.
        should_check = getattr(self, "limbo_horde_ready_for_victory", False)
        if (
            not should_check
            and getattr(self, "limbo_horde_completed", False)
            and not getattr(self, "limbo_horde_ready_for_victory", False)
            and getattr(self, "limbo_horde_victory_timer", 0) <= 0
        ):
            should_check = True
            if getattr(self, "debug", False):
                logger.debug(
                    "[LIMBO_HORDE] Fallback victory timer check (completed but no ready flag)"
                )
        if should_check:
            # wait for *all* foes to vanish: both normal enemies and any bosses
            enemies_empty = (not getattr(self, "enemies", None)) or len(
                self.enemies
            ) == 0
            bosses_empty = (not getattr(self, "bosses", None)) or len(self.bosses) == 0
            if getattr(self, "debug", False):
                logger.debug(
                    f"[LIMBO_HORDE] ready_for_victory check: enemies_empty={enemies_empty} bosses_empty={bosses_empty} enemy_count={len(self.enemies)} boss_count={len(self.bosses)}"
                )
            if enemies_empty and bosses_empty:
                try:
                    self.limbo_horde_victory_timer = int(self.fps * 5)
                except (AttributeError, TypeError, ValueError, KeyError):
                    self.limbo_horde_victory_timer = 0
                # consume the flag so we don't trigger again
                self.limbo_horde_ready_for_victory = False
                if getattr(self, "debug", False):
                    logger.debug(
                        f"[LIMBO_HORDE] Victory timer started: {self.limbo_horde_victory_timer} frames"
                    )

        # After limbo explosion we wait a moment then show victory screen
        # Timer decrements every frame once it's been set
        if getattr(self, "limbo_horde_victory_timer", 0) > 0:
            self.limbo_horde_victory_timer -= 1
            if (
                getattr(self, "debug", False)
                and self.limbo_horde_victory_timer % 30 == 0
            ):
                logger.debug(
                    f"[LIMBO_HORDE] Victory timer countdown: {self.limbo_horde_victory_timer} frames remaining"
                )
            if self.limbo_horde_victory_timer <= 0:
                # begin full victory overlay sequence (will stay until keypress)
                if getattr(self, "debug", False):
                    print(
                        "[LIMBO_HORDE] Victory timer expired! Showing victory screen!"
                    )
                self.showing_victory = True
                self.victory_alpha = 0

        # Purgatory horde explosion: triggered after 60 seconds (3600 frames @ 60 fps)
        # Unlike Limbo, this is time-based not boss-death-based
        if getattr(self, "purgatory_horde_active", False) and not getattr(
            self, "purgatory_horde_explosion_ready", False
        ):
            # Check if 60 seconds have elapsed since horde started
            if self.purgatory_horde_elapsed >= 60 * self.fps:
                # Trigger the explosion wave
                try:
                    self.purgatory_horde_explosion_ready = True
                    self.purgatory_horde_active = False
                    self.purgatory_horde_completed = True
                    self.purgatory_horde_wave_timer = 0.0
                    # Trigger screen shake (light intensity, 2 seconds duration)
                    self.shake_intensity = 4
                    self.shake_timer = int(2 * self.fps)
                    print(
                        f"[PURGATORY_HORDE] 60s elapsed! Triggering malevolent wave. "
                        f"Enemies: {len(self.enemies)}, Bosses: {len(self.bosses)}"
                    )
                    # Clear all remaining enemies immediately
                    try:
                        self.enemies.empty()
                        self.bosses.empty()
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

        # Purgatory wave expansion and victory countdown
        if getattr(self, "purgatory_horde_explosion_ready", False):
            # Expand the wave (lasts ~2 seconds at 400px expansion speed - half of original 800px)
            self.purgatory_horde_wave_timer += 1.0 / self.fps  # delta time in seconds
            # After 2 seconds of expansion, start the victory countdown
            if self.purgatory_horde_wave_timer >= 2.0:
                # Start 5-second countdown before showing victory
                if self.purgatory_horde_victory_timer <= 0:
                    self.purgatory_horde_victory_timer = int(self.fps * 5)
                    self.purgatory_horde_explosion_ready = False
                    if getattr(self, "debug", False):
                        print(
                            f"[PURGATORY_HORDE] Wave expansion complete! Starting victory countdown: "
                            f"{self.purgatory_horde_victory_timer} frames"
                        )

        # Purgatory victory countdown
        if getattr(self, "purgatory_horde_victory_timer", 0) > 0:
            self.purgatory_horde_victory_timer -= 1
            if (
                getattr(self, "debug", False)
                and self.purgatory_horde_victory_timer % 30 == 0
            ):
                logger.debug(
                    f"[PURGATORY_HORDE] Victory timer countdown: {self.purgatory_horde_victory_timer} frames remaining"
                )
            if self.purgatory_horde_victory_timer <= 0:
                # Show victory screen
                if getattr(self, "debug", False):
                    print(
                        "[PURGATORY_HORDE] Victory timer expired! Showing victory screen!"
                    )
                self.showing_victory = True
                self.victory_alpha = 0

        # Handle limbo final boss countdown separately; when it expires we show
        # the specialized defeat screen rather than the generic overlay.
        if getattr(self, "limbo_final_victory_timer", 0) > 0:
            self.limbo_final_victory_timer -= 1
            # optionally log every second when debugging
            if (
                getattr(self, "debug", False)
                and self.limbo_final_victory_timer % self.fps == 0
            ):
                logger.debug(
                    f"[LIMBO_FINAL] Countdown: {self.limbo_final_victory_timer} frames remaining"
                )
            if self.limbo_final_victory_timer <= 0:
                if getattr(self, "debug", False):
                    print("[LIMBO_FINAL] Countdown expired, triggering defeat")
                try:
                    self.limbo_final_defeat()
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
        # update victory overlay fade if active
        if getattr(self, "showing_victory", False):
            if self.victory_alpha < 255:
                self.victory_alpha = min(
                    255, self.victory_alpha + self.victory_fade_speed
                )
            # do not auto-dismiss; input handler will clear the flag

    def _remove_dead_enemies(self) -> None:
        """Remove dead enemies and award score/XP.

        Wrapper delegating to DeathSystem. See DeathSystem.remove_dead_enemies()
        """
        if self.death_system:
            return self.death_system.remove_dead_enemies()

    def _remove_dead_bosses(self) -> None:
        """Remove dead bosses and award score/XP.

        Wrapper delegating to DeathSystem. See DeathSystem.remove_dead_bosses()
        """
        if self.death_system:
            return self.death_system.remove_dead_bosses()

    def _cull_offscreen_projectiles(self) -> None:
        """Remove projectiles that have gone off-screen."""
        # Remove player projectiles that go off-screen top
        for projectile in self.projectiles:
            if projectile.y < 0:
                projectile.kill()

        # Remove enemy projectiles that go off-screen in any direction
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

    def _update_particle_effects(self) -> None:
        """Update all particle systems and puddle effects."""
        # Delegate particle updates to ParticleSystem
        if self.particle_system:
            self.particle_system.update_particles()

        # Handle blizzard expiry damage (special logic not in ParticleSystem)
        if hasattr(self, "blizzard_puddles"):
            # collect those that will expire this frame
            expired = []
            new_puddles = []
            for puddle in self.blizzard_puddles:
                if puddle.get("timer", 0) <= 1:
                    expired.append(puddle.copy())
                else:
                    new_puddles.append(puddle)
            # apply explosion damage for expired blizzard zones
            if expired:
                try:
                    from src.game_constants import BLIZZARD_EXPIRE_DAMAGE
                except (AttributeError, TypeError, ValueError, KeyError):
                    BLIZZARD_EXPIRE_DAMAGE = 0
                for p in expired:
                    # damage normal enemies
                    for enemy in list(self.enemies):
                        ex, ey = self._enemy_pos(enemy)
                        dx = ex - p["x"]
                        dy = ey - p["y"]
                        if dx * dx + dy * dy <= p["radius"] * p["radius"]:
                            _betype = getattr(enemy, "enemy_type", "")
                            _bshield = getattr(enemy, "shield_hp", 0) > 0
                            try:
                                if (
                                    _betype in ("pentagram_fire", "pentagram_storm")
                                    and _bshield
                                ):
                                    pass  # blizzard does not penetrate fire/storm elemental shields
                                elif _betype == "pentagram_ice" and _bshield:
                                    # blizzard dissolves ice pentagram's shield
                                    absorbed = min(
                                        enemy.shield_hp, BLIZZARD_EXPIRE_DAMAGE
                                    )
                                    enemy.shield_hp -= absorbed
                                    remainder = BLIZZARD_EXPIRE_DAMAGE - absorbed
                                    if remainder > 0:
                                        enemy.health = max(0, enemy.health - remainder)
                                else:
                                    enemy.health = max(
                                        0, enemy.health - BLIZZARD_EXPIRE_DAMAGE
                                    )
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass
                            # show damage text above enemy (suppress if blocked)
                            try:
                                if not (
                                    _bshield
                                    and _betype in ("pentagram_fire", "pentagram_storm")
                                ):
                                    self.spawn_floating_text(
                                        str(int(BLIZZARD_EXPIRE_DAMAGE)),
                                        ex,
                                        ey - self._enemy_radius(enemy) - 8,
                                    )
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass
                    # damage bosses as well
                    if hasattr(self, "bosses") and self.bosses:
                        items = (
                            self.bosses.sprites()
                            if hasattr(self.bosses, "sprites")
                            else list(self.bosses)
                        )
                        for boss in items:
                            bx, by = self._enemy_pos(boss)
                            dx = bx - p["x"]
                            dy = by - p["y"]
                            if dx * dx + dy * dy <= p["radius"] * p["radius"]:
                                try:
                                    boss.health = max(
                                        0, boss.health - BLIZZARD_EXPIRE_DAMAGE
                                    )
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                                try:
                                    self.spawn_floating_text(
                                        str(int(BLIZZARD_EXPIRE_DAMAGE)),
                                        bx,
                                        by - self._enemy_radius(boss) - 8,
                                    )
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
            self.blizzard_puddles = new_puddles
            for puddle in self.blizzard_puddles:
                puddle["timer"] -= 1

    def update(self) -> None:
        """Primary per-frame update called from ``update_game``.

        This method contains the majority of in-game logic; ``update_game``
        temporarily forces the game into in-game state so tests can call it
        without menus interfering.
        """
        self._update_pre_guard_state()

        # Handle stage start countdown
        if self.stage_start_countdown > 0:
            self.countdown_fade_timer += 1
            self.stage_start_timer -= 1
            if self.stage_start_timer <= 0:
                self.stage_start_countdown -= 1
                self.countdown_fade_timer = 0  # Reset fade timer for new number
                if self.stage_start_countdown > 0:
                    self.stage_start_timer = self.fps  # Reset for next second
                else:
                    self.stage_start_timer = 0  # Countdown finished
            self.update_center_messages()
            return

        if (
            self.showing_stage_menu
            or self.showing_permanent_upgrades
            or getattr(self, "showing_profiles_menu", False)
            or self.showing_prologo_end
            or self.showing_options
            or self.showing_main_menu
            or not self.selected_stage
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
            # If paused because of blasphemy_5 revive, still update the revive visuals
            if self.paused and getattr(self, "_paused_by_blasphemy5", False):
                # update explosion timers so ring/alpha animate while paused
                self.skullboom_explosions = [
                    e for e in self.skullboom_explosions if e.get("timer", 0) > 0
                ]
                for explosion in self.skullboom_explosions:
                    # decrement timer when explosion was spawned by revive too
                    try:
                        explosion["timer"] -= 1
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass
                # update blasphemy5 particles so they animate during pause
                try:
                    for p in list(getattr(self, "blasphemy5_particles", [])):
                        p.update()
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
            self.update_center_messages()
            return

        # Increment frame counter for animations
        self.frame_count += 1

        # Update tower special system (fire/blizzard/Voltaic Mayhem)
        if self.tower_special is not None:
            self.tower_special.update()

        # Update time
        self.time_elapsed += 1 / self.fps
        self.wave_time += 1 / self.fps

        # Handle input
        self.handle_input()

        # Update player
        self.player.update(self.width)
        self.player.x = self.clamp_to_walls(self.player.x)

        # Check for game over BEFORE regen so player doesn't heal from zero HP
        # This must happen early so regen doesn't revive the player
        if self.player.health <= 0:
            if self._handle_blasphemy5_revive():
                return
            # During a lightning strike in either Prologo or Limbo Final we don't
            # immediately enter game over; the end-of-stage screen will be shown
            # later when the lightning timer completes.  This prevents the early
            # "GAME OVER" overlay from popping up while the beam/explosion plays.
            if not (
                (self.selected_stage == "prologo" and self.prologo_lightning_strike)
                or (
                    self.selected_stage == "limbo_final"
                    and getattr(self, "limbo_final_lightning_strike", False)
                )
            ):
                # Only trigger game over once per run; use flag to prevent re-triggering
                if not self._game_over_triggered:
                    self._game_over_triggered = True
                    self.game_over()
                return  # Stop all further updates when game over triggers

        # VIGOR: periodic regeneration (0.5 HP every 5s per level)
        # BLASPHEMY_2: flat regen independent of VIGOR, now 0.5 HP every 2s per level
        vigor_level = self.permanent_stats.get("vigor", 0)
        blasphemy2_level = self.permanent_stats.get("blasphemy_2", 0)
        # Heal from vigor every 5 seconds
        if vigor_level and (self.frame_count % (5 * self.fps) == 0):
            heal = 0.5 * vigor_level
            if heal:
                self.player.health = min(
                    self.player.max_health, self.player.health + heal
                )

        # Heal from blasphemy_2 every 2 seconds
        if blasphemy2_level and (self.frame_count % (2 * self.fps) == 0):
            heal = 0.5 * blasphemy2_level
            if heal:
                self.player.health = min(
                    self.player.max_health, self.player.health + heal
                )

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
            if isinstance(proj, FliesProjectile):
                # Pass both regular enemies and any boss sprites so Flies
                # homing can prioritize boss targets (including end-of-wave bosses).
                targets = []
                try:
                    # Add regular enemies (list or Group)
                    targets.extend(
                        list(self.enemies) if hasattr(self.enemies, "__iter__") else []
                    )
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
                try:
                    # Add bosses (Group or list)
                    if hasattr(getattr(self, "bosses", None), "sprites"):
                        targets.extend(self.bosses.sprites())
                    elif getattr(self, "bosses", None) is not None:
                        targets.extend(list(self.bosses))
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
                proj.update(targets, self.player)

        # Apply ice puddle slowing effects before enemy movement
        if self.collision_system:
            self.collision_system.apply_ice_puddle_slowing()

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
        self._remove_dead_enemies()

        # Bosses may be stored similarly
        if hasattr(self.bosses, "update"):
            try:
                self.bosses.update(self.player, self)
            except TypeError:
                try:
                    self.bosses.update()
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
        else:
            for b in list(self.bosses):
                if hasattr(b, "update"):
                    try:
                        b.update(self.player, self)
                    except TypeError:
                        try:
                            b.update(self.player)
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass

        self._remove_dead_bosses()

        self._cull_offscreen_projectiles()

        # Update orbitals
        if "orbital" in self.player_weapons:
            self.update_orbitals()

        # Update SkullBoom auto-fire
        if "skullboom" in self.player_weapons:
            self.update_skullboom()

        # Update enemy spawning
        self.update_enemy_spawning()

        # Update wave progression
        self.update_wave_progression()

        # Update prologo/limbo_final events (timed boss spawns & lightning)
        if self.selected_stage in ("prologo", "limbo_final"):
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
        self.collision_system.handle_collisions()

        self._update_particle_effects()

        # Update floating texts (drawn later)
        self._update_floating_texts()

        # Update health drop positions / player collisions
        self._update_health_drops()

        # Update barrier spawning/aging (hell stages only)
        self._update_barriers()

        # Update statue/tower weapons for Limbo and Purgatory
        if self.is_limbo_stage() or (
            self.selected_stage
            and str(self.selected_stage).startswith(("purgatory", "hell"))
        ):
            self.update_statue_weapons()

        # Update screen shake
        if self.shake_timer > 0:
            self.shake_timer -= 1

        # Update center messages
        self.update_center_messages()

    def execute_blasphemy5_blink(self) -> None:
        """Execute Blasphemy 5 blink ability: teleport 120px in movement direction.

        Delegates to Blasphemy5System.
        """
        if self.blasphemy5_system:
            self.blasphemy5_system.execute_blasphemy5_blink()

    def _handle_blasphemy5_revive(self) -> bool:
        """Handle blasphemy-10 one-time player revive on death.

        Delegates to Blasphemy5System.
        Returns True if revive was triggered, False otherwise.
        """
        if self.blasphemy5_system:
            return self.blasphemy5_system._handle_blasphemy5_revive()
        return False

    def update_blasphemy5_blink_animation(self) -> None:
        """Update blink animation state and execute teleport when ready.

        Delegates to Blasphemy5System (called from _update_pre_guard_state).
        """
        if self.blasphemy5_system:
            self.blasphemy5_system.update_blasphemy5_blink_animation()

    def handle_input(self) -> None:
        """Handle player movement input"""
        keys: ScancodeWrapper = pygame.key.get_pressed()

        # Movement (disable during lightning)
        if not (
            (self.selected_stage == "prologo" and self.prologo_lightning_strike)
            or (
                self.selected_stage == "limbo_final"
                and getattr(self, "limbo_final_lightning_strike", False)
            )
        ):
            moving = False
            moving_horizontal = False  # Track if moving left/right (for walk animation)

            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                self.player.velocity_x = -self.player.speed
                self.player_facing_right = False  # Track direction for walk animation
                moving = True
                moving_horizontal = True
            elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                self.player.velocity_x = self.player.speed
                self.player_facing_right = True  # Track direction for walk animation
                moving = True
                moving_horizontal = True
            else:
                self.player.velocity_x = 0

            # Vertical movement (W / S) - does NOT use walk animation
            if keys[pygame.K_w] or keys[pygame.K_UP]:
                self.player.move_up()
                moving = True
            elif keys[pygame.K_s] or keys[pygame.K_DOWN]:
                self.player.move_down()
                moving = True

            # Update player animation
            # Always increment anim_frame for wobble/sway effect (works in all directions)
            if moving:
                self.player_anim_timer += 1
                if self.player_anim_timer >= self.player_anim_speed:
                    self.player_anim_timer = 0
                    self.player_anim_frame = (self.player_anim_frame + 1) % 8
            else:
                # When not moving, still cycle the frame slowly for idle bobbing
                self.player_anim_timer += 1
                if self.player_anim_timer >= self.player_anim_speed * 2:
                    self.player_anim_timer = 0
                    self.player_anim_frame = (self.player_anim_frame + 1) % 8

            # Set is_moving flag only for horizontal movement (determines if walk frames show)
            if moving_horizontal:
                self.player_is_moving = True
            else:
                self.player_is_moving = False

    def update_weapon_firing(self) -> None:
        """Handle automatic weapon firing"""
        if self.weapon_system is not None:
            return self.weapon_system.update_weapon_firing()

    def fire_basic_weapon(self, aim_x, aim_y) -> None:
        """Fire basic projectile"""
        if self.weapon_system is not None:
            return self.weapon_system.fire_basic_weapon(aim_x, aim_y)

    def fire_hellgun(self, aim_x, aim_y) -> None:
        """Fire hellgun pellets"""
        if self.weapon_system is not None:
            return self.weapon_system.fire_hellgun(aim_x, aim_y)

    def fire_spear(self, aim_x, aim_y) -> None:
        """Fire piercing spear"""
        if self.weapon_system is not None:
            return self.weapon_system.fire_spear(aim_x, aim_y)

    def fire_demon_strike(self, aim_x, aim_y) -> None:
        """Fire DemonStrike: vertical-only rolling ball that pierces and slows enemies.

        Behavior:
        - Velocity constrained to perfectly vertical direction (vx = 0).
        - Pierces every enemy hit (pierce_all = True) and deals one instance of damage per enemy (same damage formula as spear).
        - Applies slow effect (50% speed) for 2 seconds on hit.
        """
        if self.weapon_system is not None:
            return self.weapon_system.fire_demon_strike(aim_x, aim_y)

    def fire_flies(self, aim_x, aim_y) -> None:
        """Fire homing Flies projectiles"""
        if self.weapon_system is not None:
            return self.weapon_system.fire_flies(aim_x, aim_y)

    def fire_skullboom(self, aim_x, aim_y) -> None:
        """Fire explosive SkullBoom"""
        if self.weapon_system is not None:
            return self.weapon_system.fire_skullboom(aim_x, aim_y)

    def _orbital_cooldown_range(self) -> tuple[int, int]:
        """Return cooldown range for orbitals based on level (delegates to weapons helper)"""
        if self.weapon_system is not None:
            return self.weapon_system._orbital_cooldown_range()
        return (0, 0)

    def create_orbitals(self) -> None:
        """Initialize orbital sentinels around player"""
        if self.weapon_system is not None:
            return self.weapon_system.create_orbitals()

    def update_orbitals(self) -> None:
        """Update orbital sentinels and handle orbital firing."""
        if self.weapon_system is not None:
            return self.weapon_system.update_orbitals()

    def update_skullboom(self) -> None:
        """Update SkullBoom auto-fire"""
        if self.weapon_system is not None:
            return self.weapon_system.update_skullboom()

    def update_statue_weapons(self) -> None:
        """Update Limbo statue weapons"""
        if self.weapon_system is not None:
            return self.weapon_system.update_statue_weapons()

    def handle_collisions(self):
        return self.collision_system.handle_collisions()

    def trigger_level_up(self) -> None:
        """Pause game and show upgrade choices"""
        if self.upgrade_system is not None:
            return self.upgrade_system.trigger_level_up()

    def generate_upgrade_choices(self):
        """Generate 3 random upgrade choices of different types"""
        if self.upgrade_system is not None:
            return self.upgrade_system.generate_upgrade_choices()

    def reroll_upgrade_choices(self) -> bool:
        """Consume one reroll (if available) and replace the current upgrade choices.

        Returns True if new choices were generated (different ids), False otherwise.
        """
        if self.upgrade_system is not None:
            return self.upgrade_system.reroll_upgrade_choices()

    def generate_initial_weapon_choices(self):
        """Delegate to GameStateManager for initial weapon choices."""
        if self.upgrade_system is not None:
            return self.upgrade_system.generate_initial_weapon_choices()

    def generate_weapon_choices(self):
        """Generate weapon choices"""
        if self.upgrade_system is not None:
            return self.upgrade_system.generate_weapon_choices()

    def generate_weapon_upgrade_choices(self):
        """Generate weapon upgrade choices for owned weapons"""
        if self.upgrade_system is not None:
            return self.upgrade_system.generate_weapon_upgrade_choices()

    def apply_weapon(self, weapon_id) -> None:
        if self.upgrade_system is not None:
            return self.upgrade_system.apply_weapon(weapon_id)

    def generate_initial_tower_choices(self) -> list[dict[str, Any]]:
        """Fallback generator for tower choices (mirrors GameStateManager)."""
        if self.upgrade_system is not None:
            return self.upgrade_system.generate_initial_tower_choices()

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
        if self.upgrade_system is not None:
            return self.upgrade_system.apply_tower(tower_id)

    def update_enemy_spawning(self) -> None:
        """Handle enemy spawning logic (delegates timing to EnemyManager when present)."""
        if self.spawn_system is None:
            if getattr(self, "debug", False):
                logger.debug("[Game] spawn_system is None")
            return
        if getattr(self, "debug", False):
            logger.debug("[Game] delegate to spawn_system")
        return self.spawn_system.update_enemy_spawning()

    def update_wave_progression(self) -> None:
        """Handle wave progression and boss spawning"""
        if self.spawn_system is not None:
            return self.spawn_system.update_wave_progression()

    def update_prologo_events(self) -> None:
        """Handle special Prologo events (managed by EnemyManager when present)"""
        if self.spawn_system is not None:
            return self.spawn_system.update_prologo_events()

    def generate_lightning(self) -> None:
        """Generate lightning bolt path"""
        if self.spawn_system is not None:
            return self.spawn_system.generate_lightning()

    def game_over(self) -> None:
        """Enter the game over state (persistent) and reset fade animation."""
        # Ensure other end screens are not active
        self.showing_prologo_end = False
        # If the stage menu was accidentally left open (seen on FALL), close it
        self.showing_stage_menu = False

        # Show the game over overlay and stop gameplay updates
        self.showing_game_over = True
        self.paused = True

        # Reset fade animation state and kickstart first frame so player sees immediate change
        self.game_over_alpha = min(255, self.game_over_fade_speed)

        # Stop any screen shake immediately so the overlay is stable
        self.shake_timer = 0
        self.shake_intensity = 0

        # Persist meta progress so XP earned this run isn't lost
        if getattr(self, "active_profile_slot", None) is not None:
            try:
                self.save_permanent_stats()
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

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
        if hasattr(self, "ui") and hasattr(self.ui, "draw_game_over"):
            self.ui.draw_game_over(shake_x, shake_y)
        return None

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

    def limbo_final_defeat(self) -> None:
        """Show Limbo Final stage end screen"""
        # mimic Prologo's defeat layout but with custom Italian text explaining
        # that Satan has been pushed back from Limbo and now faces Purgatory.
        self.showing_prologo_end = True
        self.paused = True
        self.screen.fill((40, 20, 45))
        font_large = pygame.font.Font(None, 54)
        text = font_large.render("LIMBO FALL", True, (139, 0, 0))
        self.screen.blit(text, (self.width // 2 - text.get_width() // 2, 150))

        # Description
        font_medium = pygame.font.Font(None, 18)
        text = font_medium.render(
            "Satana è stato respinto dal Limbo e deve ora combattere nel Purgatorio",
            True,
            (200, 200, 200),
        )
        self.screen.blit(text, (self.width // 2 - text.get_width() // 2, 220))

        # award meta reward on first defeat of the Limbo Final stage
        try:
            if self.award_stage_clear("limbo_final"):
                self.show_centered_message("META POINT GAINED!", 1800, (255, 215, 0))
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

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
        """Spawn an enemy at the top of the screen"""
        if self.spawn_system is not None:
            return self.spawn_system.spawn_enemy()

    def spawn_enemy_projectiles(self) -> None:
        """Have some enemies shoot projectiles at the player"""
        if self.spawn_system is not None:
            return self.spawn_system.spawn_enemy_projectiles()

    def spawn_giant_enemy(self) -> None:
        """Spawn a giant enemy at random edge (delegates to EnemyManager)."""
        if self.spawn_system is not None:
            return self.spawn_system.spawn_giant_enemy()

    def spawn_crusader_enemy(self) -> None:
        """Spawn a rare crusader enemy (very slow/tanky)."""
        if self.spawn_system is not None:
            return self.spawn_system.spawn_crusader_enemy()

    def spawn_big_enemy(self) -> None:
        """Spawn a big enemy (giant). Delegates to EnemyManager if available."""
        if self.spawn_system is not None:
            return self.spawn_system.spawn_big_enemy()

    def spawn_reinforcements(self, x=None, y=None, count=None):
        """Spawn a short-lived cluster of reinforcements near (x,y) or at a random building."""
        if self.spawn_system is not None:
            return self.spawn_system.spawn_reinforcements(x, y, count)

    def spawn_boss(self, boss_type) -> None:
        """Spawn a boss of the specified type (delegates to EnemyManager)."""
        if self.spawn_system is not None:
            return self.spawn_system.spawn_boss(boss_type)

    def spawn_health_drop(self, x: float, y: float, heal: int) -> None:
        """Create a healing bonus that falls from (x,y).

        Wrapper delegating to DeathSystem. See DeathSystem.spawn_health_drop()
        """
        if self.death_system:
            return self.death_system.spawn_health_drop(x, y, heal)

    def show_upgrades(self) -> None:
        """Show level up upgrade selection"""
        if self.upgrade_system is not None:
            return self.upgrade_system.show_upgrades()

    def apply_upgrade(self, upgrade) -> None:
        """Apply the selected upgrade"""
        if self.upgrade_system is not None:
            return self.upgrade_system.apply_upgrade(upgrade)
