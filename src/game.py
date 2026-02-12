import logging
import math
import os
import random
import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Self, TypedDict, Optional

import pygame
from pygame.key import ScancodeWrapper

from src.entities.enemy import Enemy, IceParticle, BurnParticle
from src.entities.player import Player
from src.projectile import Projectile, SoulDrainProjectile
from src.ui import PygameUIManager
from src.game_state import GameStateManager
from src.core.entities.tower import Tower, TowerManager
from src.systems.enemy_manager import EnemyManager
from src.weapons import (
    WEAPON_DEFS,
    get_weapon_definitions,
    get_weapon_upgrade_description,
    get_orbital_count,
    orbital_cooldown_range,
    shotgun_pellets,
    shotgun_cooldown,
    spear_cooldown,
    soul_drain_cd,
    soul_drain_projectile_count,
    soul_drain_damage_heal_mult,
    skull_bomb_cooldown,
    skull_bomb_damage,
    skull_bomb_explosion_radius,
)
from src.balance import (
    XP_BASE,
    XP_GROWTH,
    PLAYER_BASE_DAMAGE,
    PLAYER_BASE_HEALTH,
    BURST_FIRE_RATE,
    BURST_MAX,
    BURST_PAUSE,
    STATUE_FIRE_RATE,
    BASE_SPAWN_RATE,
    SPAWN_MIN_RATE,
    SPAWN_RAMP_START_WAVE,
    SPAWN_RAMP_SLOPE_PRE,
    SPAWN_RAMP_SLOPE_POST,
    REINFORCEMENT_DELAY_MS,
    REINFORCEMENT_COUNT,
    DEFAULT_PROJECTILE_SIZE_MULTIPLIER,
    DEFAULT_FIRE_RATE_MULTIPLIER,
    DEFAULT_DAMAGE_REDUCTION_MULTIPLIER,
    MAX_EXTRA_WEAPONS,
    GAME_OVER_FADE_DURATION_MS,
    ENEMY_BASE_SPEEDS,
)

from src.game_constants import (
    DEFAULT_WIDTH,
    DEFAULT_HEIGHT,
    DEFAULT_FPS,
    DEFAULT_PLAYER_ANIM_SPEED,
    DEFAULT_WAVE_DURATION,
    STAGE_SETTINGS,
    WALL_THICKNESS,
)

class StatConfig(TypedDict):
    name: str
    key: str
    color: tuple[int, int, int]
    y: int

logger: logging.Logger = logging.getLogger(__name__)
LOG = logging.getLogger(__name__)

# Global reference to running game instance (set in Game.__init__)
CURRENT_GAME = None


class FloatingText:
    """Simple floating text for damage/feedback displayed on screen."""

    def __init__(self, text: str, x: float, y: float, *, color=(255, 255, 255), font_size: int = 20, vy: float = -1.2, life: int = 70, max_rise_pixels: int = 12):
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
        self.fast_forward_prologo_force_lightning: bool = fast_forward_prologo_force_lightning
        self.fast_forward_applied = False

        # Debug flag to control debug output
        self.debug: bool = debug

        self.width = DEFAULT_WIDTH
        self.height = DEFAULT_HEIGHT
        self.screen: pygame.Surface = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Satan's Roguelite - Vampire Survivors Style")
        self.clock = pygame.time.Clock()
        self.running = True
        self.fps = DEFAULT_FPS

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

        # Pause confirmation state (None or dict with {'action': 'quit', 'selection': 0|1})
        self.pause_confirmation: dict | None = None

        # Options overlay state (opened from the main menu gear button)
        self.showing_options: bool = False

        # Options: toggle for showing floating damage numbers
        self.show_damage_numbers: bool = True

        # Persistent stats container must exist early so other init code can reference it
        self.permanent_stats: Dict[str, int] = {}
        self.projectile_manager = None

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
        self.game_over_fade_speed = max(1, int(255 / ((self.game_over_fade_duration_ms / 1000.0) * self.fps)))
        self.player_xp = 0
        self.player_level = 1
        self.xp_to_next_level = XP_BASE
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
        self.soul_drain_cooldown_timer = 0
        self.skull_bomb_cooldown_timer = 0
        # Skull bomb particles and explosion effects
        self.skull_bomb_particles: List[Any] = []
        self.skull_bomb_explosions: List[Dict[str, Any]] = []
        # Orbital defaults
        self.orbital_count = 3
        self.orbitals = []

        # Game state
        self.player: Player = Player(self.width // 2, self.height - 80)
        self.enemies: Any = pygame.sprite.Group()
        self.projectiles: Any = pygame.sprite.Group()
        self.enemy_projectiles: Any = pygame.sprite.Group()
        self.bosses: Any = pygame.sprite.Group()


        # Backwards compatibility: simple list of statue projectile dicts used by
        # older code and tests. New code also stores Projectiles in self.projectiles.
        self.statue_projectiles: list = []

        # Reinforcements
        self.reinforcement_delay_ms = REINFORCEMENT_DELAY_MS
        self.reinforcement_count = REINFORCEMENT_COUNT

        self.score = 0
        self.difficulty_multiplier = 1.0
        self.player_damage = PLAYER_BASE_DAMAGE

        # XP and Level system
        self.player_xp = 0
        self.player_level = 1
        self.xp_to_next_level = XP_BASE
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
        self.player_weapons: List[str] = []
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
        self.weapon_levels: Dict[str, int] = {}

        # Permanent stats (meta-progression)
        # Ensure we don't overwrite loaded/persisted stats; set defaults only if missing
        self.permanent_stats.setdefault("power", 0)
        self.permanent_stats.setdefault("vigor", 0)
        self.permanent_stats.setdefault("adrenaline", 0)
        self.permanent_stats.setdefault("structure", 0)

        # Frame counter for animations
        self.frame_count = 0

        # Player animation
        self.player_anim_frame = 0
        self.player_anim_timer = 0
        self.player_anim_speed = DEFAULT_PLAYER_ANIM_SPEED  # frames between animation changes (slower)
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
        self.right_tower = Tower(960, 530, fire_rate=self.statue_fire_rate)
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

        # Load assets
        self.load_assets()

        # Persistence: determine file for storing permanent stats & global progress (can be overridden in tests)
        if permanent_stats_file is not None:
            self.permanent_stats_file: Path = Path(permanent_stats_file)
        else:
            self.permanent_stats_file = Path(__file__).resolve().parents[1] / "permanent_stats.json"

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
            logger.debug("Final permanent_stats after Game.__init__: %s", self.permanent_stats)
        except Exception:
            pass

        # Initialize orbitals
        self.orbitals: List[Dict[str, Any]] = []
        # Screen shake defaults
        self.shake_timer = 0
        self.shake_intensity = 0

        # Mouse tracking
        self.mouse_x: int = self.width // 2
        self.mouse_y: int = self.height // 2

        # Reinforcements
        self.reinforcement_delay_ms = REINFORCEMENT_DELAY_MS
        self.reinforcement_count = REINFORCEMENT_COUNT

        self.score = 0
        self.difficulty_multiplier = 1.0
        self.player_damage = PLAYER_BASE_DAMAGE

        # XP and Level system
        self.player_xp = 0
        self.player_level = 1
        self.xp_to_next_level = XP_BASE
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
        self.player_weapons: List[str] = []
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
        self.weapon_levels: Dict[str, int] = {}

        # Permanent stats (meta-progression)
        # Ensure we don't overwrite loaded/persisted stats; set defaults only if missing
        self.permanent_stats.setdefault("power", 0)
        self.permanent_stats.setdefault("vigor", 0)
        self.permanent_stats.setdefault("adrenaline", 0)
        self.permanent_stats.setdefault("structure", 0)

        # Frame counter for animations
        self.frame_count = 0

        # Player animation
        self.player_anim_frame = 0
        self.player_anim_timer = 0
        self.player_anim_speed = DEFAULT_PLAYER_ANIM_SPEED  # frames between animation changes (slower)
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

        # Stage system
        self.selected_stage: Optional[str] = None
        # Default stage settings centralized in src.game_constants
        self.stage_settings = STAGE_SETTINGS.copy()

        # Game variables
        self.wave = 0
        self.wave_time: float = 0.0
        self.wave_duration = DEFAULT_WAVE_DURATION  # seconds
        self.enemy_spawn_timer = 0
        self.base_spawn_rate = 72  # base frames between spawns
        self.enemy_spawn_rate = 72  # frames between spawns

        # Wave ramp settings (centralized)
        self.spawn_ramp_start_wave = SPAWN_RAMP_START_WAVE
        self.spawn_ramp_slope_pre = SPAWN_RAMP_SLOPE_PRE
        self.spawn_ramp_slope_post = SPAWN_RAMP_SLOPE_POST
        self.spawn_min_rate = SPAWN_MIN_RATE

        # Spawn acceleration
        self.spawn_accel_timer: int = 20 * self.fps
        self.time_elapsed: float = 0.0

        # Enemy manager (handles pooling/spawning helpers)
        try:
            self.enemy_manager = EnemyManager(self)
            # Keep initial rates in sync (populate manager fields)
            if hasattr(self, "enemy_spawn_rate"):
                self.enemy_manager.enemy_spawn_rate = self.enemy_spawn_rate
            if hasattr(self, "enemy_spawn_timer"):
                self.enemy_manager.enemy_spawn_timer = self.enemy_spawn_timer
        except Exception as e:
            logger.exception("Failed to create EnemyManager: %s", e)
            self.enemy_manager = None

        # Giant enemy spawning (supports manager-backed timers via properties)
        # Note: these are proxied to EnemyManager when present
        self.big_enemy_timer: int = 12 * self.fps
        self.big_enemy_fast_interval: int = 9 * self.fps
        self.big_spawned_this_wave = False

    # Backwards-compatible properties to proxy timer state to EnemyManager when present
    @property
    def big_enemy_timer(self) -> int:
        if getattr(self, "enemy_manager", None) is not None:
            return self.enemy_manager.big_enemy_timer
        return getattr(self, "_big_enemy_timer", 0)

    @big_enemy_timer.setter
    def big_enemy_timer(self, val: int) -> None:
        if getattr(self, "enemy_manager", None) is not None:
            self.enemy_manager.big_enemy_timer = val
        else:
            self._big_enemy_timer = val

    @property
    def big_spawned_this_wave(self) -> bool:
        if getattr(self, "enemy_manager", None) is not None:
            return self.enemy_manager.big_spawned_this_wave
        return getattr(self, "_big_spawned_this_wave", False)

    @big_spawned_this_wave.setter
    def big_spawned_this_wave(self, val: bool) -> None:
        if getattr(self, "enemy_manager", None) is not None:
            self.enemy_manager.big_spawned_this_wave = val
        else:
            self._big_spawned_this_wave = val

    @property
    def big_enemy_fast_interval(self) -> int:
        if getattr(self, "enemy_manager", None) is not None:
            return self.enemy_manager.big_enemy_fast_interval
        return getattr(self, "_big_enemy_fast_interval", 9 * self.fps)

    @big_enemy_fast_interval.setter
    def big_enemy_fast_interval(self, val: int) -> None:
        if getattr(self, "enemy_manager", None) is not None:
            self.enemy_manager.big_enemy_fast_interval = val
        else:
            self._big_enemy_fast_interval = val

    # Wave boss flag proxy
    @property
    def wave_boss_spawned(self) -> bool:
        if getattr(self, "enemy_manager", None) is not None:
            return getattr(self.enemy_manager, "wave_boss_spawned", False)
        return getattr(self, "_wave_boss_spawned", False)

    @wave_boss_spawned.setter
    def wave_boss_spawned(self, val: bool) -> None:
        if getattr(self, "enemy_manager", None) is not None:
            self.enemy_manager.wave_boss_spawned = val
        else:
            self._wave_boss_spawned = val

    # Prologo boss / lightning proxies
    @property
    def prologo_final_boss_spawned(self) -> bool:
        if getattr(self, "enemy_manager", None) is not None:
            return getattr(self.enemy_manager, "prologo_final_boss_spawned", False)
        return getattr(self, "_prologo_final_boss_spawned", False)

    @prologo_final_boss_spawned.setter
    def prologo_final_boss_spawned(self, val: bool) -> None:
        if getattr(self, "enemy_manager", None) is not None:
            self.enemy_manager.prologo_final_boss_spawned = val
        else:
            self._prologo_final_boss_spawned = val

    @property
    def prologo_final_boss_immortal(self) -> bool:
        if getattr(self, "enemy_manager", None) is not None:
            return getattr(self.enemy_manager, "prologo_final_boss_immortal", False)
        return getattr(self, "_prologo_final_boss_immortal", False)

    @prologo_final_boss_immortal.setter
    def prologo_final_boss_immortal(self, val: bool) -> None:
        if getattr(self, "enemy_manager", None) is not None:
            self.enemy_manager.prologo_final_boss_immortal = val
        else:
            self._prologo_final_boss_immortal = val

    @property
    def prologo_lightning_strike(self) -> bool:
        if getattr(self, "enemy_manager", None) is not None:
            return getattr(self.enemy_manager, "prologo_lightning_strike", False)
        return getattr(self, "_prologo_lightning_strike", False)

    @prologo_lightning_strike.setter
    def prologo_lightning_strike(self, val: bool) -> None:
        if getattr(self, "enemy_manager", None) is not None:
            self.enemy_manager.prologo_lightning_strike = val
        else:
            self._prologo_lightning_strike = val

    @property
    def prologo_lightning_timer(self) -> int:
        if getattr(self, "enemy_manager", None) is not None:
            return getattr(self.enemy_manager, "prologo_lightning_timer", 0)
        return getattr(self, "_prologo_lightning_timer", 0)

    @prologo_lightning_timer.setter
    def prologo_lightning_timer(self, val: int) -> None:
        if getattr(self, "enemy_manager", None) is not None:
            self.enemy_manager.prologo_lightning_timer = val
        else:
            self._prologo_lightning_timer = val

    @property
    def prologo_final_boss_defeated(self) -> bool:
        if getattr(self, "enemy_manager", None) is not None:
            return getattr(self.enemy_manager, "prologo_final_boss_defeated", False)
        return getattr(self, "_prologo_final_boss_defeated", False)

    @prologo_final_boss_defeated.setter
    def prologo_final_boss_defeated(self, val: bool) -> None:
        if getattr(self, "enemy_manager", None) is not None:
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
            "boss_small.png",
            "boss_medium.png",
            "boss_big.png",
            "boss_final.png",
            "projectile.png",
            "enemy_projectile.png",
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
            width_at_y: float = 0.0
            if self.is_limbo_stage():
                width_at_y = 680 - (progress * 280)
            elif self.selected_stage and str(self.selected_stage).startswith("purgatory"):
                # Wider layout for Purgatory: more horizontal space both at top and bottom
                # Top: ~720px, Bottom: ~480px (wider than Limbo's top 680/bottom 400)
                width_at_y = 720 - (progress * 240)
            else:
                width_at_y = 560 - (progress * 240)

            irregularity: float = math.sin(y / 80) * 5 + math.cos(y / 60) * 3
            if self.selected_stage == "prologo":
                irregularity += math.sin(y / 35) * 8 + math.cos(y / 47) * 6

            left_x: float = (self.width - width_at_y) // 2 + irregularity
            right_x: float = (self.width + width_at_y) // 2 + irregularity

            self.left_wall_points.append((left_x, y))
            self.right_wall_points.append((right_x, y))

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
        """Return (x, y) for an enemy object or dict."""
        if isinstance(e, dict):
            return e.get("x", 0), e.get("y", 0)
        return getattr(e, "x", 0), getattr(e, "y", 0)

    def _enemy_radius(self, e):
        """Return radius for an enemy object or dict."""
        if isinstance(e, dict):
            return e.get("radius", 12)
        return getattr(e, "radius", 12)

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

            # Clear screen with background color
            if self.selected_stage and self.selected_stage in self.stage_settings:
                bg_color = self.stage_settings[self.selected_stage]["bg_color"]
            else:
                bg_color = (20, 10, 30)
            self.screen.fill(bg_color)

            # Draw game world if in game
            if (
                self.selected_stage
                and not self.showing_stage_menu
                and not self.showing_permanent_upgrades
            ):
                self.draw_game_world(shake_x, shake_y)
                self.draw_game_objects(shake_x, shake_y)
                self.draw_skull_bomb_particles(shake_x, shake_y)
                # Draw centralized floating texts (damage numbers, etc.)
                try:
                    self.draw_floating_texts(shake_x, shake_y)
                except Exception:
                    pass

            # Draw UI
            self.draw_ui(shake_x, shake_y)

            # Update display
            pygame.display.flip()
        except Exception as e:
            logger.exception("Error in draw method: %s", e)
            import traceback

            traceback.print_exc()

    def draw_game_world(self, shake_x=0, shake_y=0) -> None:
        """Delegate game world drawing to the Pygame UI manager."""
        return self.ui.draw_game_world(shake_x, shake_y)

    def draw_dead_trees(self, shake_x=0, shake_y=0) -> None:
        """Delegate dead tree drawing to Pygame UI manager."""
        return self.ui.draw_dead_trees(shake_x, shake_y)

    def draw_pedestals(self, shake_x=0, shake_y=0) -> None:
        """Delegate pedestal drawing to Pygame UI manager."""
        return self.ui.draw_pedestals(shake_x, shake_y)

    def draw_fog(self, shake_x=0, shake_y=0) -> None:
        """Delegate fog drawing to Pygame UI manager."""
        return self.ui.draw_fog(shake_x, shake_y)

    def draw_game_objects(self, shake_x=0, shake_y=0) -> None:
        """Delegate drawing of objects to the Pygame UI manager."""
        return self.ui.draw_game_objects(shake_x, shake_y)

    def draw_special_effects(self, shake_x=0, shake_y=0) -> None:
        """Delegate special effects to Pygame UI manager."""
        return self.ui.draw_special_effects(shake_x, shake_y)

    def draw_lightning_effect(self, shake_x=0, shake_y=0):
        """Delegate lightning effect drawing to Pygame UI manager."""
        return self.ui.draw_lightning_effect(shake_x, shake_y)

    def draw_spine_effect(self, shake_x=0, shake_y=0):
        """Delegate spine effect drawing to Pygame UI manager."""
        return self.ui.draw_spine_effect(shake_x, shake_y)

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
                    current_radius = int(explosion["max_radius"] * (1 - progress + 0.3))  # Start small, expand
                    
                    # Create irregular ring by drawing multiple arc segments
                    num_segments = 12  # Number of segments to create irregular shape
                    segment_angle = 2 * math.pi / num_segments
                    
                    # Outer glow ring - irregular
                    glow_color = (255, 150, 50, alpha // 3)  # Semi-transparent orange
                    for i in range(num_segments):
                        start_angle = i * segment_angle + random.uniform(-0.3, 0.3)  # Add randomness
                        end_angle = (i + 1) * segment_angle + random.uniform(-0.3, 0.3)
                        radius_variation = current_radius + 3 + random.uniform(-2, 2)  # Vary radius
                        
                        # Draw arc segment
                        pygame.draw.arc(self.screen, glow_color[:3], 
                                      (center_x - radius_variation, center_y - radius_variation, 
                                       radius_variation * 2, radius_variation * 2),
                                      start_angle, end_angle, max(1, int(3 * progress)))
                    
                    # Particles
                    for p in list(self.skull_bomb_particles):
                        try:
                            p.update()
                            # Draw as small filled circles with alpha based on life
                            surf = pygame.Surface((p.size * 2 + 2, p.size * 2 + 2), pygame.SRCALPHA)
                            alpha_p = max(30, int(255 * (p.life / 40)))
                            pygame.draw.circle(surf, (255, 180, 80, alpha_p), (p.size + 1, p.size + 1), p.size)
                            self.screen.blit(surf, (int(p.x - p.size) + shake_x, int(p.y - p.size) + shake_y))
                        except Exception:
                            pass
            except Exception:
                pass

    def spawn_floating_text(self, text: str, x: float, y: float, *, color=(255, 255, 255), font_size: int = 20, vy: float = -1.2, life: int = 70) -> None:
        """Create and register a floating text shown in world coordinates.

        Respects the user's option to show/hide damage numbers (via
        `self.show_damage_numbers`). If disabled, function is a no-op.
        """
        try:
            if not getattr(self, 'show_damage_numbers', True):
                return
            ft = FloatingText(text, x, y, color=color, font_size=font_size, vy=vy, life=life)
            self.floating_texts.append(ft)
        except Exception:
            pass

    def _update_floating_texts(self) -> None:
        if not getattr(self, 'floating_texts', None):
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
        if not getattr(self, 'floating_texts', None):
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
            for p in self.skull_bomb_particles:
                # Draw as small red circles for explosion effect
                screen_x = int(p.x + shake_x)
                screen_y = int(p.y + shake_y)
                # Use alpha blending for fade effect
                alpha = min(255, p.life * 8)  # Fade out over time
                color = (255, 100, 50, alpha)  # Orange-red explosion color
                
                # Draw the particle
                pygame.draw.circle(self.screen, color[:3], (screen_x, screen_y), p.size)
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
            return self.ui.draw_hud(shake_x, shake_y)
        return None

    def draw_center_messages(self, shake_x=0, shake_y=0) -> None:
        """Backward-compatible wrapper: delegate to UI manager's implementation."""
        if hasattr(self, "ui") and hasattr(self.ui, "draw_center_messages"):
            return self.ui.draw_center_messages(shake_x, shake_y)
        return None

    def draw_stage_menu(self, shake_x=0, shake_y=0) -> None:
        """Backward-compatible wrapper: delegate stage/menu drawing to UI manager."""
        if hasattr(self, "ui") and hasattr(self.ui, "draw_stage_menu"):
            return self.ui.draw_stage_menu(shake_x, shake_y)
        return None

    def draw_permanent_upgrades(self, shake_x=0, shake_y=0) -> None:
        """Backward-compatible wrapper that delegates to UI manager."""
        if hasattr(self, "ui") and hasattr(self.ui, "draw_permanent_upgrades"):
            return self.ui.draw_permanent_upgrades(shake_x, shake_y)
        return None

    def _draw_permanent_upgrades_impl(self, shake_x=0, shake_y=0) -> None:
        """Draw the permanent upgrades menu"""
        font_large = pygame.font.Font(None, 36)
        font_medium = pygame.font.Font(None, 24)
        font_small = pygame.font.Font(None, 18)

        # Title
        left_x: int = self.width // 2 - 420  # moved further left

        title: pygame.Surface = font_large.render("PERMANENT UPGRADES", True, (220, 180, 20))
        self.screen.blit(
            title, (left_x + shake_x, 50 + shake_y)
        )

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

            name_text: pygame.Surface = font_medium.render(stat["name"], True, name_color)
            # Slightly lower the stat name so it aligns better visually with the bar
            name_y = stat["y"] + 13 + shake_y  # moved down 7px total (3px up from previous)
            self.screen.blit(
                name_text, (left_x + shake_x, name_y)
            )

            # Stat value
            value: int = self.permanent_stats[stat["key"]]
            value_text: pygame.Surface = font_small.render(f"Level: {value}", True, (255, 255, 255))
            self.screen.blit(
                value_text, (left_x + 200 + shake_x, stat["y"] + shake_y)
            )

            # Effect per level and total effect (e.g., "+2% per level (10% total)")
            effect_text = self.permanent_stat_effect_text(stat["key"], value)
            if effect_text:
                eff_surf: pygame.Surface = font_small.render(effect_text, True, (180, 180, 180))
                # Align effect text vertically with the stat bar (bar centered at stat["y"] + 15, bar_height = 12)
                eff_y = stat["y"] + 15 + (12 // 2) - (eff_surf.get_height() // 2) + shake_y
                self.screen.blit(
                    eff_surf, (left_x + 340 + shake_x, eff_y)
                )

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

        # Classic Upgrades section
        classic_text: pygame.Surface = font_medium.render("CLASSIC UPGRADES", True, (136, 136, 136))
        self.screen.blit(
            classic_text,
            (
                left_x + shake_x,
                separator_y + 30 + shake_y,
            ),
        )

        # Placeholder boxes for future upgrades (2 rows of 5)
        box_width = 80  # slightly smaller
        box_height = 60
        box_spacing = 100
        start_x: int = left_x + box_spacing // 2 - 40  # nudge left more (classic upgrades only)

        # First row
        box_y1: int = separator_y + 60
        for i in range(5):
            box_x = start_x + (i * box_spacing)
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

        for col, (label, key_prefix, color) in enumerate(tree_types):
            col_x = tree_base_x + col * tree_col_spacing
            # Title
            lbl_surf: pygame.Surface = font_small.render(label, True, color)
            self.screen.blit(
                lbl_surf, (col_x - lbl_surf.get_width() // 2 + shake_x, tree_top_y - 28 + shake_y)
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
                left_border = tuple(min(255, c + 20) for c in color) if left_active else (51, 51, 51)
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
                right_border = tuple(min(255, c + 20) for c in color) if right_active else (51, 51, 51)
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
                        tooltip_y = tree_top_y + 3 * tree_v_spacing + tree_box_h + 12 + shake_y
                        self._draw_tooltip(tooltip_lines, tooltip_x, tooltip_y, font_small, anchor_center=True)

                if pygame.Rect(*right_rect).collidepoint(mouse_point):
                    tooltip_lines = self._skill_tooltip_lines(key_prefix, right_tier)
                    if tooltip_lines:
                        tooltip_x = col_x
                        tooltip_y = tree_top_y + 3 * tree_v_spacing + tree_box_h + 12 + shake_y
                        self._draw_tooltip(tooltip_lines, tooltip_x, tooltip_y, font_small, anchor_center=True)

            # Center bottom tier (7)
            center_y = tree_top_y + 3 * tree_v_spacing
            center_key = f"{key_prefix}_7"
            center_active = bool(self.permanent_stats.get(center_key, 0))
            center_bg = color if center_active else (26, 26, 26)
            center_border = tuple(min(255, c + 20) for c in color) if center_active else (51, 51, 51)
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
                    tooltip_y = tree_top_y + 3 * tree_v_spacing + tree_box_h + 12 + shake_y
                    self._draw_tooltip(tooltip_lines, tooltip_x, tooltip_y, font_small, anchor_center=True)

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
        overlay = pygame.Surface((self.width, self.height))
        overlay.fill((40, 20, 45))  # Purple background
        overlay.set_alpha(180)  # Semi-transparent (0-255, 180 = ~70% opacity)
        self.screen.blit(overlay, (0, 0))

        font_large = pygame.font.Font(None, 48)
        font_medium = pygame.font.Font(None, 32)

        # Title
        title: pygame.Surface = font_large.render("SATAN'S FALL COMPLETE", True, (255, 215, 0))
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
        if hasattr(self, 'ui') and hasattr(self.ui, 'draw_pause_menu'):
            return self.ui.draw_pause_menu(shake_x, shake_y)
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
                color: tuple[int, int, int] = (220, 180, 20) if is_selected else (180, 160, 20)
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
        title: pygame.Surface = get_text("CHOOSE YOUR WEAPON", font_large, (220, 180, 20))
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
            len(self.weapon_choices) * box_height + (len(self.weapon_choices) - 1) * spacing
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
            name_text: pygame.Surface = font_medium.render(weapon["name"], True, (220, 180, 20))
            self.screen.blit(name_text, (x_pos + 20 + shake_x, y_pos + 10 + shake_y))

            # Weapon description
            desc_text: pygame.Surface = font_small.render(weapon["description"], True, (200, 200, 200))
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
        title: pygame.Surface = get_text("CHOOSE YOUR TOWER", font_large, (220, 180, 20))
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
            len(self.tower_choices) * box_height + (len(self.tower_choices) - 1) * spacing
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
            name_text: pygame.Surface = font_medium.render(tower["name"], True, (220, 180, 20))
            self.screen.blit(name_text, (x_pos + 20 + shake_x, y_pos + 10 + shake_y))

            # Tower description
            desc_text: pygame.Surface = font_small.render(tower["description"], True, (200, 200, 200))
            self.screen.blit(desc_text, (x_pos + 20 + shake_x, y_pos + 40 + shake_y))

    def _player_stats_display_items(self):
        """Return (key, value) pairs to display in the player stats sheet.

        Exclude keys related to towers/statues and elemental skill trees (fire/storm/ice).
        """
        import re

        def is_excluded(k: str) -> bool:
            if any(tok in k for tok in ("tower", "statue")):
                return True
            if re.match(r'^(fire|storm|ice)(?:_|$)', k):
                return True
            return False

        return [(k, v) for k, v in self.permanent_stats.items() if not is_excluded(k)]

    def permanent_stat_effect_text(self, key: str, level: int) -> str:
        """Return a human-friendly description of the per-level and total effect for a permanent stat."""
        if key == "power":
            per = 3.0
            total = per * level
            return f"+{per:.0f}% dmg/level ({total:.0f}% total)"
        if key == "vigor":
            per = 10
            total = per * level
            return f"+{per:d} HP/level ({total:d} HP total); +1% max HP regen every 3s/level"
        if key == "adrenaline":
            per = 5.0
            total = per * level
            return f"+{per:.0f}% fire rate/level ({total:.0f}% total)"
        if key == "structure":
            per = 5.0
            total = per * level
            return f"-{per:.0f}% dmg taken/level ({total:.0f}% total)"
        return ""

    def _enforce_center_requirement(self, key_prefix: str) -> None:
        """Ensure the center tier (7) is only active when a full column of 3 exists.

        If the condition is broken, the center tier is cleared automatically.
        """
        center_key = f"{key_prefix}_7"
        left_full = all(self.permanent_stats.get(f"{key_prefix}_{i+1}", 0) for i in range(3))
        right_full = all(self.permanent_stats.get(f"{key_prefix}_{4 + i}", 0) for i in range(3))
        if self.permanent_stats.get(center_key, 0) and not (left_full or right_full):
            self.permanent_stats[center_key] = 0
            logger.info("Clearing center tier %s because no column is fully active", center_key)

    def apply_permanent_stats(self) -> None:
        """Apply permanent stat effects to both game-level and player-level multipliers.

        This should be called when permanent stats change so the in-game values reflect
        the upgrades immediately (not only after reset_game()).
        """
        # Damage multiplier: 'power' gives +3% per level
        self.damage_multiplier = 1.0 + (self.permanent_stats.get("power", 0) * 0.03)
        # Fire rate multiplier: 'adrenaline' gives +5% per level
        self.fire_rate_multiplier = 1.0 + (self.permanent_stats.get("adrenaline", 0) * 0.05)
        # Apply other effects for consistency
        self.projectile_size_multiplier = 1.0 + (self.permanent_stats.get("projectile_size", 0) * 0.0)
        self.damage_reduction_multiplier = 1.0 - (self.permanent_stats.get("structure", 0) * 0.05)

        # Ensure the player object also reflects the new multipliers
        try:
            self.player.damage_multiplier = self.damage_multiplier
            self.player.fire_rate_multiplier = self.fire_rate_multiplier
            self.player.projectile_size_multiplier = self.projectile_size_multiplier
            self.player.damage_reduction_multiplier = self.damage_reduction_multiplier
        except Exception:
            pass

        # Enforce center-tier requirements for all trees after applying
        for prefix in ("fire", "storm", "ice"):
            self._enforce_center_requirement(prefix)

    def _skill_tooltip_lines(self, key_prefix: str, tier: int) -> list:
        """Return list of text lines to show in a tooltip for a given skill tree tier.

        This includes Title, Status (Unlocked/Locked), and the requirement string.
        """
        label_map = {"fire": "FIRE", "storm": "STORM", "ice": "ICE"}
        label = label_map.get(key_prefix, key_prefix.upper())
        key = f"{key_prefix}_{tier}"
        active = bool(self.permanent_stats.get(key, 0))

        # Show only status and reserve a line for the (future) effect description.
        # We intentionally omit requirement / unlock hints here to keep tooltip minimal;
        # the 'Effect:' line is a placeholder that will be populated once we add per-tier properties.
        lines: list[str] = []
        lines.append("Status: Unlocked" if active else "Status: Locked")
        # Placeholder for effect description; empty for now
        lines.append("Effect: ")

        return lines

    def _draw_tooltip(self, lines: list, x: int, y: int, font: pygame.font.Font, anchor_center: bool = False) -> None:
        """Render a small tooltip box with given lines.

        If anchor_center is True, x is treated as the center x coordinate (tooltip will be centered on it);
        otherwise x and y represent the top-left corner as before.
        """
        padding_x = 8
        padding_y = 6
        line_surfs = [font.render(l, True, (255, 255, 255)) for l in lines]
        width = max(s.get_width() for s in line_surfs) + padding_x * 2
        height = sum(s.get_height() for s in line_surfs) + padding_y * 2 + (len(line_surfs) - 1) * 4
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
        if hasattr(self, 'ui') and hasattr(self.ui, 'draw_player_stats'):
            return self.ui.draw_player_stats(shake_x, shake_y)
        return None

    def _draw_player_stats_impl(self, shake_x=0, shake_y=0) -> None:
        """Draw a player stats sheet overlay showing current stats and progress."""
        from src.assets.text_cache import get_font, get_text
        font_huge = get_font(36)
        font_large = get_font(28)
        font_medium = get_font(20)
        font_small = get_font(16)

        # Overlay
        overlay = pygame.Surface((self.width, self.height))
        overlay.set_alpha(200)
        overlay.fill((10, 10, 10))
        self.screen.blit(overlay, (0, 0))

        title = get_text("PLAYER STATS", font_huge, (255, 215, 0))
        self.screen.blit(title, (self.width // 2 - title.get_width() // 2 + shake_x, 40 + shake_y))

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
            ("Projectile size %", f"{(self.projectile_size_multiplier - 1.0) * 100:.0f}%"),
            ("Damage reduction %", f"{(1.0 - self.damage_reduction_multiplier) * 100:.0f}%"),
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
        health_val = get_text(f"{int(self.player.health)}/{int(self.player.max_health)}", font_medium, (255, 255, 255))
        self.screen.blit(health_label, (left_col_x, y))
        self.screen.blit(health_val, (left_col_x + 160, y))

        # Weapons and levels
        w_y = start_y
        self.screen.blit(get_text("Weapons", font_large, (255, 215, 0)), (mid_col_x, w_y - 30))
        for i, wid in enumerate(self.player_weapons):
            lvl = self.weapon_levels.get(wid, 0)
            name = WEAPON_DEFS.get(wid, {}).get("name", wid.replace("_", " ").title())
            txt = get_text(f"{name} Lv{lvl}", font_medium, (220, 220, 220))
            self.screen.blit(txt, (mid_col_x, w_y + i * line_h))

        # Upgrade levels
        u_y = start_y
        self.screen.blit(get_text("Upgrades", font_large, (255, 215, 0)), (right_col_x, u_y - 30))
        for i, (k, v) in enumerate(self.upgrade_levels.items()):
            txt = get_text(f"{k}: {v}", font_medium, (220, 220, 220))
            self.screen.blit(txt, (right_col_x, u_y + i * line_h))

        # Permanent stats (excluding tower/statue and elemental keys)
        ps_y = u_y + len(self.upgrade_levels) * line_h + 20
        self.screen.blit(get_text("Permanent Stats", font_large, (255, 215, 0)), (right_col_x, ps_y - 30))
        display_stats = self._player_stats_display_items()
        for i, (k, v) in enumerate(display_stats):
            txt = get_text(f"{k}: {v}", font_small, (200, 200, 200))
            self.screen.blit(txt, (right_col_x, ps_y + i * (line_h - 6)))

        # Close instructions (Tab instead of I)
        inst = get_text("Press Tab or ESC to close", font_small, (180, 180, 180))
        self.screen.blit(inst, (self.width // 2 - inst.get_width() // 2 + shake_x, self.height - 50 + shake_y))



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
        title: pygame.Surface = get_text("LEVEL UP - CHOOSE UPGRADE", font_large, (220, 180, 20))
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
            name_text: pygame.Surface = font_medium.render(upgrade["name"], True, (220, 180, 20))
            self.screen.blit(name_text, (x_pos + 20 + shake_x, y_pos + 10 + shake_y))

            # Upgrade description
            desc_text: pygame.Surface = font_small.render(upgrade["description"], True, (200, 200, 200))
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
                self.mouse_x, self.mouse_y = event.pos
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.handle_mouse_click(event.pos, event.button)
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
        if getattr(self, 'pause_confirmation', None):
            # Toggle selection (0 = Yes, 1 = No)
            if key == pygame.K_LEFT or key == pygame.K_UP:
                self.pause_confirmation['selection'] = max(0, self.pause_confirmation['selection'] - 1)
                return
            elif key == pygame.K_RIGHT or key == pygame.K_DOWN:
                self.pause_confirmation['selection'] = min(1, self.pause_confirmation['selection'] + 1)
                return
            elif key == pygame.K_RETURN or key == pygame.K_SPACE or key == pygame.K_y:
                # Confirm
                if self.pause_confirmation['selection'] == 0:
                    action = self.pause_confirmation['action']
                    self.pause_confirmation = None
                    if action == 'quit':
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
                self.selected_tower_index = min(max(0, len(self.tower_choices) - 1), self.selected_tower_index + 1)
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
                self.pause_confirmation['selection'] = max(0, self.pause_confirmation['selection'] - 1)
            elif key == pygame.K_RIGHT or key == pygame.K_DOWN:
                self.pause_confirmation['selection'] = min(1, self.pause_confirmation['selection'] + 1)
            elif key == pygame.K_RETURN or key == pygame.K_SPACE or key == pygame.K_y:
                # Confirm
                if self.pause_confirmation['selection'] == 0:
                    action = self.pause_confirmation['action']
                    self.pause_confirmation = None
                    if action == 'quit':
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
            if getattr(self, 'pause_confirmation', None):
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
                    no_rect = pygame.Rect(dx + dialog_w - btn_w - 10, dy + 30, btn_w, btn_h)
                    if yes_rect.collidepoint(pos):
                        # Confirm Yes
                        action = self.pause_confirmation['action']
                        self.pause_confirmation = None
                        if action == 'quit':
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

                # If options overlay is open, check for clicks on its CLOSE button
                if getattr(self, 'showing_options', False):
                    dialog_w, dialog_h = 360, 220
                    dx = self.width // 2 - dialog_w // 2
                    dy = self.height // 2 - dialog_h // 2

                    # Damage numbers toggle rect (compact right-aligned)
                    toggle_w, toggle_h = 48, 24
                    toggle_x = dx + dialog_w - 24 - toggle_w
                    toggle_y = dy + 56
                    toggle_rect = pygame.Rect(toggle_x, toggle_y, toggle_w, toggle_h)
                    if toggle_rect.collidepoint(pos):
                        # Toggle option
                        try:
                            self.show_damage_numbers = not self.show_damage_numbers
                        except Exception:
                            pass
                        return

                    close_rect = pygame.Rect(dx + (dialog_w - 120) // 2, dy + dialog_h - 50, 120, 36)
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
                    purg2_rect = pygame.Rect(start_x, start_y + spacing, option_w, option_h)
                    purg3_rect = pygame.Rect(start_x, start_y + spacing * 2, option_w, option_h)
                    purg_back_rect = pygame.Rect(self.width // 2 - 60, start_y + spacing * 3 + 10, 120, 36)

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
                    logger.debug("Purgatory submenu click handling: purgatory_menu=%s, pos=%s", self.showing_purgatory_menu, pos)

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
                    # Keep stage menu visible while showing submenu
                    self.showing_stage_menu = True
                elif upgrades_rect.collidepoint(pos):
                    self.show_permanent_upgrades()
                # Options (gear) button bottom-right
                options_rect = pygame.Rect(self.width - 54, max(20, self.height - 54), 40, 40)
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

                # Handle clicks on the 3 skill trees on the right side
                tree_types = [("FIRE", "fire", (255, 68, 68)), ("STORM", "storm", (170, 68, 255)), ("ICE", "ice", (100, 200, 255))]
                tree_box_w = 50
                tree_box_h = 36
                tree_v_spacing = 46
                tree_col_spacing = 120
                # Compute same left anchor used for drawing
                left_x = self.width // 2 - 420
                tree_base_x: int = left_x + 680  # moved right to match drawing
                tree_top_y: int = 320 - 150  # moved much higher to match drawing

                for col, (label, key_prefix, color) in enumerate(tree_types):
                    col_x = tree_base_x + col * tree_col_spacing
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
                        left_rect = pygame.Rect(left_col_x - tree_box_w // 2, y, tree_box_w, tree_box_h)
                        if left_rect.collidepoint(pos):
                            if button == 1:
                                prev_ok = True if left_tier == 1 else all(self.permanent_stats.get(f"{key_prefix}_{i+1}", 0) for i in range(left_tier-1))
                                if not self.permanent_stats.get(left_key, 0) and prev_ok:
                                    self.permanent_stats[left_key] = 1
                                    self.save_permanent_stats()
                                    self.show_centered_message(f"{label} tier {left_tier} unlocked!", 120, color, 20)
                            elif button == 3:
                                if self.permanent_stats.get(left_key, 0):
                                    # clear this and any higher tiers in left column
                                    for r2 in range(row, 3):
                                        k = f"{key_prefix}_{r2+1}"
                                        self.permanent_stats[k] = 0
                                    # ensure center cleared if condition no longer holds
                                    self._enforce_center_requirement(key_prefix)
                                    self.save_permanent_stats()
                                    self.show_centered_message(f"{label} tier {left_tier} downgraded!", 120, color, 20)
                            return

                        # right tier
                        right_tier = 4 + row
                        right_key = f"{key_prefix}_{right_tier}"
                        right_rect = pygame.Rect(right_col_x - tree_box_w // 2, y, tree_box_w, tree_box_h)
                        if right_rect.collidepoint(pos):
                            if button == 1:
                                if right_tier == 4:
                                    prev_ok = True
                                else:
                                    # check that previous tiers in right column are active (4..right_tier-1)
                                    prev_ok = all(self.permanent_stats.get(f"{key_prefix}_{i}", 0) for i in range(4, right_tier))
                                if not self.permanent_stats.get(right_key, 0) and prev_ok:
                                    self.permanent_stats[right_key] = 1
                                    self.save_permanent_stats()
                                    self.show_centered_message(f"{label} tier {right_tier} unlocked!", 120, color, 20)
                            elif button == 3:
                                if self.permanent_stats.get(right_key, 0):
                                    for r2 in range(row, 3):
                                        k = f"{key_prefix}_{4 + r2}"
                                        self.permanent_stats[k] = 0
                                    self._enforce_center_requirement(key_prefix)
                                    self.save_permanent_stats()
                                    self.show_centered_message(f"{label} tier {right_tier} downgraded!", 120, color, 20)
                            return

                    # center bottom
                    center_y = tree_top_y + 3 * tree_v_spacing
                    center_rect = pygame.Rect(col_x - tree_box_w // 2, center_y, tree_box_w, tree_box_h)
                    if center_rect.collidepoint(pos):
                        center_key = f"{key_prefix}_7"
                        if button == 1:
                            # can unlock only if at least one column of 3 is full
                            left_full = all(self.permanent_stats.get(f"{key_prefix}_{i+1}", 0) for i in range(3))
                            right_full = all(self.permanent_stats.get(f"{key_prefix}_{4 + i}", 0) for i in range(3))
                            if not self.permanent_stats.get(center_key, 0) and (left_full or right_full):
                                self.permanent_stats[center_key] = 1
                                self.save_permanent_stats()
                                self.show_centered_message(f"{label} final tier unlocked!", 120, color, 20)
                        elif button == 3:
                            if self.permanent_stats.get(center_key, 0):
                                self.permanent_stats[center_key] = 0
                                self.save_permanent_stats()
                                self.show_centered_message(f"{label} final tier downgraded!", 120, color, 20)
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
                self.show_centered_message("An error occurred handling click", 2000, (255, 100, 100))
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
        self.showing_stage_menu = False
        self.showing_permanent_upgrades = False

        # Set stage-specific buildings/spawn points
        if stage == "prologo":
            self.buildings = [
                {"x": 460, "y": 70},   # Outer left church - raised 5 pixels
                {"x": 520, "y": 75},   # Left church
                {"x": 640, "y": 60},   # Center cathedral
                {"x": 760, "y": 75},   # Right church
                {"x": 820, "y": 70},   # Outer right church - raised 5 pixels
            ]
        else:  # limbo
            self.buildings = []  # No buildings in limbo

        # Generate stage-specific features
        if str(stage).startswith("limbo"):
            self.generate_dead_trees()
            # Configure statue/tower types per Limbo level
            if stage == "limbo":
                # Limbo 1 -> Fire
                self.left_tower = Tower(320, 530, fire_rate=self.statue_fire_rate, tower_type="fire")
                self.right_tower = Tower(960, 530, fire_rate=self.statue_fire_rate, tower_type="fire")
            elif stage == "limbo_2":
                # Limbo 2 -> Storm
                self.left_tower = Tower(320, 530, fire_rate=self.statue_fire_rate, tower_type="storm")
                self.right_tower = Tower(960, 530, fire_rate=self.statue_fire_rate, tower_type="storm")
            elif stage == "limbo_3":
                # Limbo 3 -> Ice
                self.left_tower = Tower(320, 530, fire_rate=self.statue_fire_rate, tower_type="ice")
                self.right_tower = Tower(960, 530, fire_rate=self.statue_fire_rate, tower_type="ice")
        elif str(stage).startswith("purgatory"):
            # Purgatory is a new stage category with three variants. For parity with Limbo,
            # we set up no buildings and trigger an initial weapon choice.
            self.buildings = []  # No buildings in purgatory for now
            # Configure towers for Purgatory variants (use themed tower types)
            if stage == "purgatory":
                self.left_tower = Tower(320, 530, fire_rate=self.statue_fire_rate, tower_type="fire")
                self.right_tower = Tower(960, 530, fire_rate=self.statue_fire_rate, tower_type="fire")
            elif stage == "purgatory_2":
                self.left_tower = Tower(320, 530, fire_rate=self.statue_fire_rate, tower_type="storm")
                self.right_tower = Tower(960, 530, fire_rate=self.statue_fire_rate, tower_type="storm")
            elif stage == "purgatory_3":
                self.left_tower = Tower(320, 530, fire_rate=self.statue_fire_rate, tower_type="ice")
                self.right_tower = Tower(960, 530, fire_rate=self.statue_fire_rate, tower_type="ice")
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
        elif str(stage).startswith("purgatory"):
            # For Purgatory, we mimic Limbo's initial weapon selection behavior
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

            # Also prepare tower selection for Purgatory
            try:
                self.game_state.show_initial_tower_choice()
                self.awaiting_tower_choice = self.game_state.awaiting_tower_choice
                self.tower_choices = list(self.game_state.tower_choices)
                self.selected_tower_index = self.game_state.tower_choice_index
            except Exception:
                self.awaiting_tower_choice = True
                self.tower_choices = self.game_state.generate_initial_tower_choices() if hasattr(self, 'game_state') else [
                    {"id": "fire", "name": "Fire Tower", "description": "Burn nearby enemies"},
                    {"id": "storm", "name": "Storm Tower", "description": "Strike lightning at enemies"},
                    {"id": "ice", "name": "Ice Tower", "description": "Slow enemies with frost"},
                ]
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
                176  # > 175 so update_prologo_events spawns boss immediately
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

        # Reset multipliers (base values; perma upgrades applied by apply_permanent_stats)
        self.damage_multiplier = 1.0
        self.fire_rate_multiplier = 1.0
        self.projectile_size_multiplier = 1.0
        self.damage_reduction_multiplier = 1.0 - (
            self.permanent_stats["structure"] * 0.05
        )
        # Ensure permanent stat effects are applied immediately
        self.apply_permanent_stats()

        # Reset game state
        self.enemies.empty()
        self.projectiles.empty()
        self.enemy_projectiles.empty()
        self.bosses.empty()
        self.skull_bomb_particles.clear()
        self.skull_bomb_explosions.clear()

        self.wave = 0
        self.wave_time = 0.0
        self.enemy_spawn_timer = 0
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
        # 'power' gives +3% damage per level
        self.player.damage_multiplier = 1.0 + (self.permanent_stats["power"] * 0.03)
        # 'adrenaline' gives +5% fire rate per level
        self.player.fire_rate_multiplier = 1.0 + (
            self.permanent_stats["adrenaline"] * 0.05
        )
        self.player.projectile_size_multiplier = DEFAULT_PROJECTILE_SIZE_MULTIPLIER
        self.player.damage_reduction_multiplier = DEFAULT_DAMAGE_REDUCTION_MULTIPLIER - (
            self.permanent_stats["structure"] * 0.05
        )
        self.player.max_health = PLAYER_BASE_HEALTH + (self.permanent_stats["vigor"] * 10)
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
            "fire_1", "fire_2", "fire_3", "fire_4", "fire_5", "fire_6", "fire_7",
            "storm_1", "storm_2", "storm_3", "storm_4", "storm_5", "storm_6", "storm_7",
            "ice_1", "ice_2", "ice_3", "ice_4", "ice_5", "ice_6", "ice_7",
        ]
        for k in keys:
            self.permanent_stats.setdefault(k, 0)

    def load_permanent_stats(self) -> None:
        """Load persistent data from disk if file exists. Backwards-compatible.

        Supported formats:
        - Older flat dict: {"power": 1, "vigor": 0, ...} -> treated as permanent_stats
        - New wrapper: {"permanent_stats": {...}, "global_progress": {...}}"""
        try:
            if hasattr(self, "permanent_stats_file"):
                logger.debug("Checking persistent file: %s", self.permanent_stats_file)
            if hasattr(self, "permanent_stats_file") and self.permanent_stats_file.exists():
                logger.debug("Loading persistent data from %s", self.permanent_stats_file)
                with open(self.permanent_stats_file, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                # New wrapper format
                if isinstance(data, dict) and ("permanent_stats" in data or "global_progress" in data):
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
                logger.debug("Loaded permanent_stats: %s; global_progress: %s", self.permanent_stats, self.global_progress)
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
            self.showing_stage_menu, self.showing_permanent_upgrades, self.showing_prologo_end = prev_states

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
            self.pause_confirmation = {'action': 'quit', 'selection': 0}
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
        if self.paused or self.awaiting_upgrade or self.awaiting_weapon_choice or getattr(self, 'awaiting_tower_choice', False):
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

        # VIGOR: periodic regeneration (1% max HP every 3s * per-level)
        vigor_level = self.permanent_stats.get("vigor", 0)
        if vigor_level and (self.frame_count % (3 * self.fps) == 0):
            heal = self.player.max_health * (0.01 * vigor_level)
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
                proj.update(self.enemies, self.player)

        # Enemies may be a pygame Group or a simple list of dicts (tests use lists)
        if hasattr(self.enemies, "update"):
            try:
                self.enemies.update(self.player, self)
            except TypeError:
                # Some group implementations may not pass the same args
                try:
                    self.enemies.update()
                except Exception:
                    pass
        else:
            # Iterate and call update on any enemy objects that expose it
            for ent in list(self.enemies):
                if hasattr(ent, "update"):
                    try:
                        ent.update(self.player, self)
                    except TypeError:
                        try:
                            ent.update(self.player)
                        except Exception:
                            pass

        # Check for dead enemies after update (e.g., from burn damage over time) and remove them
        if hasattr(self.enemies, "sprites"):
            for enemy in list(self.enemies.sprites()):
                if hasattr(enemy, "health") and enemy.health <= 0:
                    self.score += int(enemy.max_health * 18 * self.difficulty_multiplier)
                    type_xp = {"weak": 10, "normal": 16, "strong": 25, "giant": 50, "angel": 22}
                    base_xp = type_xp.get(enemy.enemy_type, 12)
                    self.player_xp += base_xp
                    if self.player_xp >= self.xp_to_next_level:
                        self.trigger_level_up()
                    enemy.kill()  # Remove dead enemy
        else:
            for enemy in list(self.enemies):
                if isinstance(enemy, dict) and enemy.get("health", 0) <= 0:
                    self.score += int(enemy.get("max_health", 10) * 18 * self.difficulty_multiplier)
                    type_xp = {"weak": 10, "normal": 16, "strong": 25, "giant": 50, "angel": 22}
                    base_xp = type_xp.get(enemy.get("type"), 12)
                    self.player_xp += base_xp
                    if self.player_xp >= self.xp_to_next_level:
                        self.trigger_level_up()
                    try:
                        self.enemies.remove(enemy)
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
                    # Boss death handling (similar to enemy death but with different XP multiplier? Wait, bosses have their own handling elsewhere, but for burn we need this)
                    # For now, use enemy-like handling; adjust if bosses have special death logic
                    self.score += int(boss.max_health * 25)  # Bosses give more score
                    boss_xp_map = {"medium": 80, "big": 150, "final": 400}
                    boss_base_xp = boss_xp_map.get(boss.enemy_type.replace("boss_", ""), 100)
                    self.player_xp += boss_base_xp
                    if self.player_xp >= self.xp_to_next_level:
                        self.trigger_level_up()
                    boss.kill()  # Remove dead boss
        else:
            for boss in list(self.bosses):
                if isinstance(boss, dict) and boss.get("health", 0) <= 0:
                    self.score += int(boss.get("max_health", 100) * 25 * self.difficulty_multiplier)  # Assuming bosses have higher multiplier
                    boss_xp_map = {"medium": 80, "big": 150, "final": 400}
                    boss_base_xp = boss_xp_map.get(boss.get("type", "").replace("boss_", ""), 100)
                    self.player_xp += boss_base_xp
                    if self.player_xp >= self.xp_to_next_level:
                        self.trigger_level_up()
                    try:
                        self.bosses.remove(boss)
                    except Exception:
                        pass

        # Process burn timers for dict-based enemies
        if not hasattr(self.enemies, "update"):
            for enemy in list(self.enemies):
                if isinstance(enemy, dict) and enemy.get("burn_timer", 0) > 0:
                    enemy["burn_timer"] -= 1
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
                            self.spawn_floating_text(str(int(dmg)), ex, ey - enemy.get("radius", 12) - 8)
                        except Exception:
                            pass
                        enemy["burn_tick_counter"] = self.fps
                        if enemy["health"] <= 0:
                            try:
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
            effect for effect in self.game_state.chain_lightning_effects 
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
        
        # Update skull bomb explosions
        self.skull_bomb_explosions = [e for e in self.skull_bomb_explosions if e["timer"] > 0]
        for explosion in self.skull_bomb_explosions:
            explosion["timer"] -= 1

        # Update floating texts (drawn later)
        self._update_floating_texts()

        # Update floating texts
        self._update_floating_texts()

        # Update statue/tower weapons for Limbo and Purgatory
        if self.is_limbo_stage() or (self.selected_stage and str(self.selected_stage).startswith("purgatory")):
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
                projectile["y"] < 0
                or projectile["y"] > self.height
                or projectile["x"] < 0
                or projectile["x"] > self.width
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
                    1, int(self.burst_fire_rate / (self.fire_rate_multiplier * beast_rate_multiplier))
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
            cd_sec: float = shotgun_cooldown(slevel)
            self.hellgun_cooldown_timer = int(cd_sec * self.fps)

        if "spear" in self.player_weapons and self.spear_cooldown_timer <= 0:
            self.fire_spear(aim_vel_x, aim_vel_y)
            slevel = self.weapon_levels.get("spear", 0)
            cd: float = spear_cooldown(slevel)
            self.spear_cooldown_timer = int(cd * self.fps)

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
        if self.soul_drain_cooldown_timer > 0:
            self.soul_drain_cooldown_timer -= 1

    def fire_basic_weapon(self, aim_x, aim_y) -> None:
        """Fire basic projectile"""
        base_damage = int(self.player_damage * self.damage_multiplier)

        # Apply beast weapon damage bonus (+5% per level)
        beast_level: int = self.weapon_levels.get("beast", 0)
        if beast_level > 0:
            base_damage = int(base_damage * (1 + beast_level * 0.05))

        base_radius = int(8 * self.projectile_size_multiplier)

        projectile: Projectile = Projectile(
            self.player.x,
            self.player.y,
            aim_x,
            aim_y,
            damage=base_damage,
            radius=base_radius,
        )
        self.projectiles.add(projectile)
        if getattr(self, "projectile_manager", None) is not None:
            try:
                self.projectile_manager.register(projectile)
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

            # Apply shotgun damage multiplier and upgrade increments at levels 3 and 5 (+10% each)
            dmg_mult = 1.0 + (slevel >= 3) * 0.1 + (slevel >= 5) * 0.1
            base_damage = int(self.player_damage * self.damage_multiplier * 0.55 * dmg_mult)
            base_radius = int(5 * self.projectile_size_multiplier * 1.0)

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
            if getattr(self, "projectile_manager", None) is not None:
                try:
                    self.projectile_manager.register(pellet)
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
        if getattr(self, "projectile_manager", None) is not None:
            try:
                self.projectile_manager.register(spear)
            except Exception:
                pass

    def fire_soul_drain(self, aim_x, aim_y) -> None:
        """Fire homing soul drain projectiles"""
        slevel: int = self.weapon_levels.get("Soul Drain", 0)
        # Use centralized helper to determine projectile count (base is now 2)
        num_projectiles = soul_drain_projectile_count(slevel)
        damage_mult = 1.0 + (slevel >= 3) * 0.1 + (slevel >= 5) * 0.1  # Lv3 & Lv5: +10% damage
        heal_mult = 1.0 + (slevel >= 3) * 0.1 + (slevel >= 5) * 0.1  # Lv3 & Lv5: +10% heal
        
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
                damage=int(WEAPON_DEFS.get("Soul Drain", {}).get("base_damage", 10) * damage_mult),
                heal_amount=int(2 * heal_mult),
                level=slevel,
            )
            self.projectiles.add(soul_proj)
            if getattr(self, "projectile_manager", None) is not None:
                try:
                    self.projectile_manager.register(soul_proj)
                except Exception:
                    pass


    def fire_skull_bomb(self, aim_x, aim_y) -> None:
        """Fire explosive skull bomb"""
        slevel: int = self.weapon_levels.get("skull_bomb", 0)
        damage = skull_bomb_damage(slevel)
        explosion_radius = skull_bomb_explosion_radius(slevel)
        
        # Create skull projectile
        vx = aim_x * 320  # Slower than basic projectiles (20% reduction)
        vy = aim_y * 320
        
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
        if getattr(self, "projectile_manager", None) is not None:
            try:
                self.projectile_manager.register(skull)
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
        if not getattr(self, "orbitals", None) or len(self.orbitals) != self.orbital_count:
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

                    target = min(targets, key=lambda e: math.hypot(_pos(e)[0] - ox, _pos(e)[1] - oy))
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
                    olevel = self.weapon_levels.get("orbital", 0)
                    dmg_mult = 1.0 + (olevel >= 3) * 0.1 + (olevel >= 5) * 0.1
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
                    damage=int(8 * self.damage_multiplier * (1.0 + (self.weapon_levels.get("orbital", 0) >= 3) * 0.1 + (self.weapon_levels.get("orbital", 0) >= 5) * 0.1)),
                    radius=int(4 * self.projectile_size_multiplier),
                    source="orbital",
                )
                self.projectiles.add(projectile)
                if getattr(self, "projectile_manager", None) is not None:
                    try:
                        self.projectile_manager.register(projectile)
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
                                if getattr(self, "projectile_manager", None) is not None and not isinstance(p, dict):
                                    try:
                                        self.projectile_manager.register(p)
                                    except Exception:
                                        pass
                            except Exception:
                                self.projectiles.append(p)
                            # Maintain backwards-compatible simple dict list for UI/tests
                            try:
                                if isinstance(p, dict):
                                    # Ensure radius exists for UI rendering
                                    if "radius" not in p:
                                        p["radius"] = 6
                                    # Mark appearance if missing (best-effort)
                                    p.setdefault("appearance", p.get("appearance"))
                                    self.statue_projectiles.append(p)
                                else:
                                    self.statue_projectiles.append({
                                        "x": getattr(p, "x", 0),
                                        "y": getattr(p, "y", 0),
                                        "vx": getattr(p, "vel_x", getattr(p, "vx", 0)),
                                        "vy": getattr(p, "vel_y", getattr(p, "vy", 0)),
                                        "radius": getattr(p, "radius", 6),
                                        "source": getattr(p, "source", "statue"),
                                        "appearance": getattr(p, "appearance", None),
                                    })
                            except Exception:
                                pass
                    else:
                        try:
                            self.projectiles.add(proj)
                            if getattr(self, "projectile_manager", None) is not None and not isinstance(proj, dict):
                                try:
                                    self.projectile_manager.register(proj)
                                except Exception:
                                    pass
                        except Exception:
                            self.projectiles.append(proj)
                        try:
                            if isinstance(proj, dict):
                                proj.setdefault("appearance", proj.get("appearance"))
                                self.statue_projectiles.append(proj)
                            else:
                                self.statue_projectiles.append({
                                    "x": getattr(proj, "x", 0),
                                    "y": getattr(proj, "y", 0),
                                    "vx": getattr(proj, "vel_x", getattr(proj, "vx", 0)),
                                    "vy": getattr(proj, "vel_y", getattr(proj, "vy", 0)),
                                    "source": getattr(proj, "source", "statue"),
                                    "appearance": getattr(proj, "appearance", None),
                                })
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
            # If projectiles is a plain list (tests), filter dicts by 'source' key
            for p in self.projectiles:
                if isinstance(p, dict) and p.get("source") == "statue":
                    statue_projs.append(p)

        TowerManager.apply_homing(statue_projs, enemies_list)

        # Ensure backward-compatible statue projectile dicts have required keys
        try:
            for p in self.statue_projectiles:
                if isinstance(p, dict) and "radius" not in p:
                    p["radius"] = 6
        except Exception:
            pass

    def handle_collisions(self) -> None:
        """Handle all collision detection"""

        # Build or update spatial grid for enemies (reused if present)
        try:
            from src.utils.spatial_grid import SpatialGrid

            enemies_iter = self._enemies_iter()
            if not hasattr(self, "spatial_grid") or self.spatial_grid is None:
                # Use configurable cell size
                cell_size = getattr(self, "spatial_grid_cell_size", 120)
                self.spatial_grid = SpatialGrid(cell_size=cell_size, width=self.width, height=self.height)
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
                # Debug logging removed
                pass
            except Exception:
                pass
            primary_target = None
            # Normalize projectile fields for dict/object compatibility
            effect = projectile.get("effect") if isinstance(projectile, dict) else getattr(projectile, "effect", None)
            slow_duration = projectile.get("slow_duration", 120) if isinstance(projectile, dict) else getattr(projectile, "slow_duration", 120)
            slow_factor = projectile.get("slow_factor", 0.5) if isinstance(projectile, dict) else getattr(projectile, "slow_factor", 0.5)
            burn_duration = projectile.get("burn_duration", 180) if isinstance(projectile, dict) else getattr(projectile, "burn_duration", 180)
            burn_dps = projectile.get("burn_damage_per_second", 4.0) if isinstance(projectile, dict) else getattr(projectile, "burn_damage_per_second", 4.0)
            # Flag to indicate we've processed this projectile via the spatial-grid branch
            processed_projectile = False
            # Ensure we always have an iterable for hit enemies
            hit_enemies = []

            # If we have a spatial grid and projectile exposes position, use it
            if getattr(self, "spatial_grid", None) is not None and hasattr(projectile, "x"):
                try:
                    px = getattr(projectile, "x", 0)
                    py = getattr(projectile, "y", 0)
                    pr = getattr(projectile, "radius", getattr(projectile, "rect", None) and (projectile.rect.width // 2) or 5)
                    candidates = self.spatial_grid.query_circle(px, py, pr)
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
                        hit_enemies = pygame.sprite.spritecollide(projectile, self.enemies, False)
                    else:
                        hit_enemies = []
                try:
                    px = getattr(projectile, "x", 0)
                    py = getattr(projectile, "y", 0)
                    pr = getattr(projectile, "radius", getattr(projectile, "rect", None) and (projectile.rect.width // 2) or 5)
                    candidates = self.spatial_grid.query_circle(px, py, pr)
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
                        hit_enemies = pygame.sprite.spritecollide(projectile, self.enemies, False)
                    else:
                        hit_enemies = []
            # For skull bombs, also check collision with bosses
            if getattr(projectile, "weapon_type", None) == "skull_bomb":
                if hasattr(self, 'bosses') and self.bosses:
                    if hasattr(self.bosses, "sprites") and hasattr(projectile, "rect"):
                        boss_hits = pygame.sprite.spritecollide(projectile, self.bosses, False)
                        hit_enemies.extend(boss_hits)
                    elif hasattr(projectile, "x"):  # Check distance-based collision with bosses
                        px = getattr(projectile, "x", 0)
                        py = getattr(projectile, "y", 0)
                        pr = getattr(projectile, "radius", 5)
                        for boss in self.bosses:
                            if hasattr(boss, 'x') and hasattr(boss, 'y'):
                                bx, by = boss.x, boss.y
                                br = getattr(boss, "radius", 20)
                                dx = bx - px
                                dy = by - py
                                if dx * dx + dy * dy <= (pr + br) * (pr + br):
                                    hit_enemies.append(boss)

            # Prefer the nearest hit candidate to be processed as primary (avoid multiple targets in same frame)
            try:
                if len(hit_enemies) > 1:
                    px = getattr(projectile, 'x', 0)
                    py = getattr(projectile, 'y', 0)
                    hit_enemies.sort(key=lambda e: (self._enemy_pos(e)[0] - px) ** 2 + (self._enemy_pos(e)[1] - py) ** 2)
                    hit_enemies = [hit_enemies[0]]
                try:
                    # Debug: hit candidates filtered
                    pass
                except Exception:
                    pass
            except Exception:
                pass

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
                    if isinstance(projectile, dict):
                        hit_ids = projectile.setdefault("_hit_ids", set())
                    else:
                        if not hasattr(projectile, "_hit_ids"):
                            projectile._hit_ids = set()
                        hit_ids = projectile._hit_ids
                    if id(enemy) in hit_ids:
                        # Already processed this enemy for this projectile
                        continue
                except Exception:
                    hit_ids = None

                # Special handling for soul drain
                if getattr(projectile, "weapon_type", None) == "Soul Drain":

                    # Apply instant damage on contact
                    if hasattr(enemy, "take_damage"):
                        enemy.take_damage(2)
                        # spawn centralized floating text
                        try:
                            ex, ey = self._enemy_pos(enemy)
                            self.spawn_floating_text("2", ex, ey - self._enemy_radius(enemy) - 8)
                        except Exception:
                            pass
                    else:
                        # dict enemy
                        enemy["health"] = enemy.get("health", 0) - 2
                        try:
                            ex, ey = self._enemy_pos(enemy)
                            self.spawn_floating_text("2", ex, ey - enemy.get("radius", 12) - 8)
                        except Exception:
                            pass

                    # Apply drain effect instead of instant damage
                    if not hasattr(enemy, "drain_timer") or getattr(enemy, "drain_timer", 0) <= 0:
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
                    num_particles = random.randint(12, 18)  # More particles for denser effect
                    for _ in range(num_particles):
                        # More varied angle distribution - sometimes clustered, sometimes spread
                        angle_variation = random.uniform(0, 2 * math.pi)
                        if random.random() < 0.3:  # 30% chance of clustering
                            angle_variation += random.uniform(-0.5, 0.5)  # Small cluster
                        angle = angle_variation
                        
                        # More extreme speed distribution - some fast, some slow
                        speed = random.choice([
                            random.uniform(30, 80),    # Slow particles
                            random.uniform(80, 150),   # Medium particles  
                            random.uniform(150, 250),  # Fast particles
                        ])
                        
                        vx = math.cos(angle) * speed
                        vy = math.sin(angle) * speed
                        
                        # More varied starting positions
                        offset_x = random.uniform(-8, 8)
                        offset_y = random.uniform(-8, 8)
                        
                        try:
                            # More varied life and size
                            life = random.randint(10, 40)  # Wider range
                            size = random.randint(1, 6)    # Smaller to larger
                            p = BurnParticle(px + offset_x, py + offset_y, 
                                           vx, vy, life=life, size=size)
                            self.skull_bomb_particles.append(p)
                        except Exception:
                            pass
                    
                    # Create explosion area effect
                    self.skull_bomb_explosions.append({
                        "x": px,
                        "y": py,
                        "radius": explosion_radius,
                        "max_radius": explosion_radius,
                        "timer": 15,  # Duration in frames
                        "max_timer": 15
                    })
                    
                    # Damage all enemies within explosion radius
                    all_targets = []
                    # Add regular enemies
                    all_targets.extend(self.enemies)
                    # Add bosses
                    if hasattr(self, 'bosses') and self.bosses:
                        if hasattr(self.bosses, 'sprites'):
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
                                enemy.take_damage(projectile.damage)
                                try:
                                    ex, ey = self._enemy_pos(enemy)
                                    self.spawn_floating_text(str(projectile.damage), ex, ey - self._enemy_radius(enemy) - 8)
                                except Exception:
                                    pass
                            except Exception:
                                if isinstance(enemy, dict):
                                    enemy["health"] = max(0, enemy.get("health", 0) - projectile.damage)
                                    try:
                                        ex, ey = self._enemy_pos(enemy)
                                        self.spawn_floating_text(str(projectile.damage), ex, ey - enemy.get("radius", 12) - 8)
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
                        enemy.take_damage(projectile.damage)
                        try:
                            ex, ey = self._enemy_pos(enemy)
                            self.spawn_floating_text(str(projectile.damage), ex, ey - self._enemy_radius(enemy) - 8)
                        except Exception:
                            pass

                        # Storm-statue projectiles should be removed on first contact (apply chain immediately)
                        if getattr(projectile, "appearance", None) == "storm_statue":
                            # Apply chain lightning to nearby enemies (primary already hit)
                            try:
                                chain = getattr(projectile, "chain_targets", 0)
                                if chain and chain > 1 and not getattr(projectile, "_chain_applied", False):
                                    chain_points = [(self._enemy_pos(enemy)[0], self._enemy_pos(enemy)[1])]
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
                                    if len(chain_points) > 1:
                                        self.game_state.chain_lightning_effects.append({"points": chain_points, "timer": 8})
                                    try:
                                        projectile._chain_applied = True
                                    except Exception:
                                        try:
                                            projectile["_chain_applied"] = True
                                        except Exception:
                                            pass
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
                            enemy["health"] = max(0, enemy.get("health", 0) - projectile.damage)
                            try:
                                ex, ey = self._enemy_pos(enemy)
                                self.spawn_floating_text(str(projectile.damage), ex, ey - enemy.get("radius", 12) - 8)
                            except Exception:
                                pass

                            # Storm-statue dict-style projectiles should be removed on first contact (apply chain immediately)
                            if isinstance(projectile, dict) and projectile.get("appearance") == "storm_statue":
                                try:
                                    chain = projectile.get("chain_targets", 0)
                                    if chain and chain > 1 and not projectile.get("_chain_applied", False):
                                        chain_points = [(enemy.get("x", 0), enemy.get("y", 0))]
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
                                        for targ_dist, targ in others[:to_chain]:
                                            targ["health"] -= projectile.get("damage", 0) * 2
                                            tx, ty = self._enemy_pos(targ)
                                            chain_points.append((tx, ty))
                                        if len(chain_points) > 1:
                                            self.game_state.chain_lightning_effects.append({"points": chain_points, "timer": 8})
                                        projectile["_chain_applied"] = True
                                except Exception:
                                    pass
                                try:
                                    self.projectiles.remove(projectile)
                                except Exception:
                                    pass

                # Record this hit so projectile won't hit the same enemy again
                try:
                    if hit_ids is None:
                        if isinstance(projectile, dict):
                            hit_ids = projectile.setdefault("_hit_ids", set())
                        else:
                            hit_ids = getattr(projectile, "_hit_ids", set())
                    hit_ids.add(id(enemy))
                except Exception:
                    pass

                # Apply slow effect if projectile has it (Ice towers)
                if effect == "slow":
                    if not hasattr(enemy, "slow_timer") or getattr(enemy, "slow_timer", 0) <= 0:
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
                            ice_parts.append({
                                "x": enemy["x"],
                                "y": enemy["y"],
                                "vx": vx,
                                "vy": vy,
                                "life": 20,
                                "size": 2,
                            })
                    else:
                        for _ in range(10):  # More ice shards for better visibility
                            vx = random.uniform(-60, 60)
                            vy = random.uniform(-40, 20)  # Some go up, some down
                            p = IceParticle(enemy.x, enemy.y, vx, vy, life=25, size=random.randint(1, 3))
                            enemy.ice_particles.append(p)

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
                        else:
                            if not hasattr(enemy, "burn_timer") or getattr(enemy, "burn_timer", 0) <= 0:
                                enemy.burn_timer = burn_duration
                                enemy.burn_damage_per_second = burn_dps
                                # Counter for per-second ticks
                                enemy.burn_tick_timer = getattr(self, "fps", 60)
                    except Exception:
                        pass

                # Handle projectile piercing / kill (applies to all projectile types)
                if isinstance(projectile, dict):
                    p_pierce_all = projectile.get("pierce_all", False)
                    p_pierce_count = projectile.get("pierce_count", 0)
                else:
                    p_pierce_all = getattr(projectile, "pierce_all", False)
                    p_pierce_count = getattr(projectile, "pierce_count", 0)

                if p_pierce_all:
                    pass  # Spear pierces through everything
                elif p_pierce_count > 0:
                    # decrement remaining pierces and remove if exhausted
                    if isinstance(projectile, dict):
                        p_pierce_count -= 1
                        projectile["pierce_count"] = p_pierce_count
                    else:
                        projectile.pierce_count -= 1
                        p_pierce_count = projectile.pierce_count

                    if p_pierce_count <= 0:
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
                            self.score += int(
                                enemy.get("max_health", 10) * 18 * self.difficulty_multiplier
                            )
                            type_xp = {
                                "weak": 10,
                                "normal": 16,
                                "strong": 25,
                                "giant": 50,
                                "angel": 22,
                            }
                            base_xp = type_xp.get(enemy.get("type"), 12)
                            self.player_xp += base_xp
                            if self.player_xp >= self.xp_to_next_level:
                                self.trigger_level_up()
                            try:
                                self.enemies.remove(enemy)
                            except Exception:
                                pass
                        break

                    # Death handling for object-based enemies
                    if getattr(enemy, "health", None) is not None:
                        if enemy.health <= 0:
                            self.score += int(
                                enemy.max_health * 18 * self.difficulty_multiplier
                            )
                            # Give XP on kill (per-type table, flat values)
                            type_xp: Dict[str, int] = {
                                "weak": 10,
                                "normal": 16,
                                "strong": 25,
                                "giant": 50,
                                "angel": 22,
                            }
                            base_xp: int = type_xp.get(enemy.enemy_type, 12)  # fallback XP
                            self.player_xp += base_xp
                            if self.player_xp >= self.xp_to_next_level:
                                self.trigger_level_up()
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
                    if chain and chain > 1 and not getattr(projectile, "_chain_applied", False):
                        others = []
                        # Gather other enemy candidates within chain range
                        max_chain_distance = 300  # Maximum distance for chain lightning (pixels)
                        for other in self.enemies.sprites():
                            if other is primary_target:
                                continue
                            if getattr(other, "health", 0) <= 0:
                                continue
                            ox, oy = self._enemy_pos(other)
                            exx, eyy = self._enemy_pos(primary_target)
                            dist = math.hypot(ox - exx, oy - eyy)
                            if dist <= max_chain_distance:  # Only consider enemies within range
                                others.append((dist, other))
                        others.sort(key=lambda t: t[0])
                        to_chain = min(len(others), chain - 1)

                        # Debug logging for chain targets
                        try:
                            LOG.debug("Storm chain: primary=%s, chain=%s, candidates=%s", primary_target, chain, [o[1] for o in others])
                        except Exception:
                            pass
                        
                        # Store chain lightning effect for visual
                        chain_points = [(self._enemy_pos(primary_target)[0], self._enemy_pos(primary_target)[1])]
                        
                        for _, targ in others[:to_chain]:
                            # Apply damage to chained targets (prefer take_damage)
                            damaged = False
                            try:
                                before_h = getattr(targ, 'health', None)
                                try:
                                    # Chain: apply damage to secondary target
                                    pass
                                except Exception:
                                    pass
                                targ.take_damage(projectile.damage * 2)
                                damaged = True
                                after_h = getattr(targ, 'health', None)
                                try:
                                    # Chain: damage applied
                                    pass
                                except Exception:
                                    pass
                            except Exception:
                                try:
                                    before_h = getattr(targ, 'health', None)
                                    try:
                                        # Chain: apply damage to secondary target
                                        pass
                                    except Exception:
                                        pass
                                    targ.health -= projectile.damage * 2
                                    damaged = True
                                    after_h = getattr(targ, 'health', None)
                                    try:
                                        # Chain: damage applied
                                        pass
                                    except Exception:
                                        pass
                                except Exception:
                                    pass

                            # Record that this projectile hit the chained target so it won't be hit again
                            try:
                                if isinstance(projectile, dict):
                                    projectile.setdefault("_hit_ids", set()).add(id(targ))
                                else:
                                    if not hasattr(projectile, "_hit_ids"):
                                        projectile._hit_ids = set()
                                    projectile._hit_ids.add(id(targ))
                            except Exception:
                                pass

                            # Debug log if damage wasn't applied
                            try:
                                if not damaged:
                                    LOG.debug("Storm chain: failed to damage target %s", targ)
                            except Exception:
                                pass

                            # Add to chain points for visual effect
                            tx, ty = self._enemy_pos(targ)
                            chain_points.append((tx, ty))
                            
                            # death handling for chained-target sprites
                            if getattr(targ, "health", 0) <= 0:
                                self.score += int(
                                    targ.max_health * 18 * self.difficulty_multiplier
                                )
                                type_xp = {
                                    "weak": 10,
                                    "normal": 16,
                                    "strong": 25,
                                    "giant": 50,
                                    "angel": 22,
                                }
                                base_xp = type_xp.get(targ.enemy_type, 12)
                                self.player_xp += base_xp
                                if self.player_xp >= self.xp_to_next_level:
                                    self.trigger_level_up()
                                try:
                                    targ.kill()
                                except Exception:
                                    try:
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
                            self.game_state.chain_lightning_effects.append({
                                "points": chain_points,
                                "timer": 8  # Show for 8 frames
                            })
                        # Mark chain applied so we don't duplicate
                        try:
                            projectile._chain_applied = True
                        except Exception:
                            try:
                                projectile["_chain_applied"] = True
                            except Exception:
                                pass
            if processed_projectile:
                continue
            else:
                # Enemies stored as a simple iterable (dicts or object instances)
                # Collect precise overlap candidates first and prefer the nearest one
                candidates = []
                try:
                    proj_px = getattr(projectile, "x", projectile.get("x", 0) if isinstance(projectile, dict) else 0)
                    proj_py = getattr(projectile, "y", projectile.get("y", 0) if isinstance(projectile, dict) else 0)
                    proj_pr = getattr(projectile, "radius", projectile.get("radius", 0) if isinstance(projectile, dict) else 0)
                except Exception:
                    proj_px = proj_py = proj_pr = 0

                for enemy in list(self.enemies):
                    ex, ey = self._enemy_pos(enemy)
                    er = self._enemy_radius(enemy)
                    dx = ex - proj_px
                    dy = ey - proj_py
                    # precise circle overlap check
                    if dx * dx + dy * dy <= (er + proj_pr) * (er + proj_pr):
                        candidates.append((dx * dx + dy * dy, enemy))

                if len(candidates) > 1:
                    candidates.sort(key=lambda t: t[0])
                    hit_enemies = [candidates[0][1]]
                else:
                    hit_enemies = [c[1] for c in candidates]

                # Process only the nearest overlapping enemy (if any)
                for enemy in hit_enemies:
                    # Support dict-shaped projectiles (tests/backwards-compat) as well as objects
                    if isinstance(projectile, dict):
                        px = projectile.get("x", 0)
                        py = projectile.get("y", 0)
                        pr = projectile.get("radius", 0)
                        p_damage = projectile.get("damage", 0)
                        p_pierce_all = projectile.get("pierce_all", False)
                        p_pierce_count = projectile.get("pierce_count", 0)
                    else:
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
                        if isinstance(projectile, dict):
                            hit_ids = projectile.setdefault("_hit_ids", set())
                        else:
                            if not hasattr(projectile, "_hit_ids"):
                                projectile._hit_ids = set()
                            hit_ids = projectile._hit_ids
                        if id(enemy) in hit_ids:
                            continue
                    except Exception:
                        hit_ids = None
                    if isinstance(enemy, dict):
                            # Dict-based enemy
                            enemy["health"] -= p_damage

                            # Record this hit so projectile won't hit the same enemy again
                            try:
                                if hit_ids is None:
                                    if isinstance(projectile, dict):
                                        hit_ids = projectile.setdefault("_hit_ids", set())
                                    else:
                                        hit_ids = getattr(projectile, "_hit_ids", set())
                                hit_ids.add(id(enemy))

                            except Exception:
                                pass

                            # Apply slow for dict-based enemies
                            if effect == "slow":


                                enemy.setdefault("speed", 100)
                                enemy["slow_timer"] = slow_duration
                                enemy["slow_factor"] = slow_factor
                                enemy["speed"] = enemy["speed"] * enemy["slow_factor"]

                                # Add ice explosion particles
                                ice_parts = enemy.setdefault("ice_particles", [])
                                ex = enemy.get("x", 0)
                                ey = enemy.get("y", 0)
                                for _ in range(10):  # More ice shards for better visibility
                                    vx = random.uniform(-60, 60)
                                    vy = random.uniform(-40, 20)  # Some go up, some down
                                    ice_parts.append({
                                        "x": ex,
                                        "y": ey,
                                        "vx": vx,
                                        "vy": vy,
                                        "life": 25,
                                        "size": random.randint(1, 3),  # Vary size
                                    })

                            # Apply burn for dict-based enemies
                            if effect == "burn":
                                enemy.setdefault("burn_timer", 0)
                                # Only apply if not already burning
                                if enemy.get("burn_timer", 0) <= 0:
                                    enemy["burn_timer"] = burn_duration
                                    enemy["burn_damage_per_second"] = burn_dps
                                    enemy["burn_tick_counter"] = self.fps

                            # Handle projectile piercing / kill (support dict or object projectiles)
                            if isinstance(projectile, dict):
                                p_pierce_all = projectile.get("pierce_all", False)
                                p_pierce_count = projectile.get("pierce_count", 0)
                            else:
                                p_pierce_all = getattr(projectile, "pierce_all", False)
                                p_pierce_count = getattr(projectile, "pierce_count", 0)

                            if p_pierce_all:
                                pass
                            elif p_pierce_count > 0:
                                p_pierce_count -= 1
                                if isinstance(projectile, dict):
                                    projectile["pierce_count"] = p_pierce_count
                                else:
                                    projectile.pierce_count = p_pierce_count
                                if p_pierce_count <= 0:
                                    if isinstance(projectile, dict):
                                        try:
                                            self.projectiles.remove(projectile)
                                        except Exception:
                                            pass
                                    else:
                                        projectile.kill()
                            else:
                                if isinstance(projectile, dict):
                                    try:
                                        self.projectiles.remove(projectile)
                                    except Exception:
                                        pass
                                else:
                                    projectile.kill()

                            # Death handling for dict enemies
                            if enemy["health"] <= 0:
                                self.score += int(
                                    enemy.get("max_health", 10)
                                    * 18
                                    * self.difficulty_multiplier
                                )
                                type_xp = {
                                    "weak": 10,
                                    "normal": 16,
                                    "strong": 25,
                                    "giant": 50,
                                    "angel": 22,
                                }
                                base_xp = type_xp.get(enemy.get("type"), 12)
                                self.player_xp += base_xp
                                if self.player_xp >= self.xp_to_next_level:
                                    self.trigger_level_up()
                                try:
                                    self.enemies.remove(enemy)
                                except ValueError:
                                    pass

                            # Chain hits: storm projectiles can hit additional distinct enemies
                            if isinstance(projectile, dict):
                                chain = projectile.get("chain_targets", 0)
                            else:
                                chain = getattr(projectile, "chain_targets", 0)
                            if chain and chain > 1 and not getattr(projectile, "_chain_applied", False):
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
                                    targ["health"] -= p_damage * 2
                                    try:
                                        # dict chain: after damage
                                        pass
                                    except Exception:
                                        pass
                                    # Record this hit to prevent further hits from the same projectile
                                    try:
                                        if isinstance(projectile, dict):
                                            projectile.setdefault("_hit_ids", set()).add(id(targ))
                                        else:
                                            if not hasattr(projectile, "_hit_ids"):
                                                projectile._hit_ids = set()
                                            projectile._hit_ids.add(id(targ))
                                    except Exception:
                                        pass
                                    tx, ty = self._enemy_pos(targ)
                                    chain_points.append((tx, ty))
                                    if targ["health"] <= 0:
                                        self.score += int(targ.get("max_health", 10) * 18 * self.difficulty_multiplier)
                                        base_xp = 12
                                        self.player_xp += base_xp
                                        if self.player_xp >= self.xp_to_next_level:
                                            self.trigger_level_up()
                                        try:
                                            self.enemies.remove(targ)
                                        except Exception:
                                            pass
                                if len(chain_points) > 1:
                                    self.game_state.chain_lightning_effects.append({"points": chain_points, "timer": 8})
                                    try:
                                        projectile._chain_applied = True
                                    except Exception:
                                        try:
                                            projectile["_chain_applied"] = True
                                        except Exception:
                                            pass
                                    processed_projectile = True

                    else:
                        # Object-based enemy (sprite/instance)
                            try:
                                enemy.take_damage(p_damage)

                                # Remove storm projectiles on contact (apply chain immediately)
                                if getattr(projectile, "appearance", None) == "storm_statue":
                                    try:
                                        chain = getattr(projectile, "chain_targets", 0)
                                        if chain and chain > 1 and not getattr(projectile, "_chain_applied", False):
                                            chain_points = [(self._enemy_pos(enemy)[0], self._enemy_pos(enemy)[1])]
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
                                                    targ.take_damage(p_damage * 2)
                                                except Exception:
                                                    try:
                                                        targ.health -= p_damage * 2
                                                    except Exception:
                                                        pass
                                                tx, ty = self._enemy_pos(targ)
                                                chain_points.append((tx, ty))
                                            if len(chain_points) > 1:
                                                self.game_state.chain_lightning_effects.append({"points": chain_points, "timer": 8})
                                            try:
                                                projectile._chain_applied = True
                                            except Exception:
                                                try:
                                                    projectile["_chain_applied"] = True
                                                except Exception:
                                                    pass
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
                                    enemy.health -= p_damage
                                except Exception:
                                    pass

                            # Record this hit so projectile won't hit the same enemy again
                            try:
                                if hit_ids is None:
                                    if isinstance(projectile, dict):
                                        hit_ids = projectile.setdefault("_hit_ids", set())
                                    else:
                                        hit_ids = getattr(projectile, "_hit_ids", set())
                                hit_ids.add(id(enemy))
                            except Exception:
                                pass

                            # Apply slow effect if projectile has it (Ice towers)
                            if effect == "slow":
                                if not hasattr(enemy, "slow_timer") or getattr(enemy, "slow_timer", 0) <= 0:
                                    enemy.slow_timer = slow_duration
                                    enemy.slow_factor = slow_factor
                                    if not hasattr(enemy, "original_speed"):
                                        enemy.original_speed = enemy.speed
                                    enemy.speed = enemy.speed * enemy.slow_factor

                            # Apply burn effect (Fire towers)
                            if effect == "burn":
                                if not hasattr(enemy, "burn_timer") or getattr(enemy, "burn_timer", 0) <= 0:
                                    enemy.burn_timer = burn_duration
                                    enemy.burn_damage_per_second = burn_dps
                                    # Counter for per-second ticks
                                    enemy.burn_tick_timer = getattr(self, "fps", 60)

                            # Handle projectile piercing / kill (support dict or object projectiles)
                            if p_pierce_all:
                                pass
                            elif p_pierce_count > 0:
                                p_pierce_count -= 1
                                if isinstance(projectile, dict):
                                    projectile["pierce_count"] = p_pierce_count
                                else:
                                    projectile.pierce_count = p_pierce_count
                                if p_pierce_count <= 0:
                                    if isinstance(projectile, dict):
                                        try:
                                            self.projectiles.remove(projectile)
                                        except Exception:
                                            pass
                                    else:
                                        projectile.kill()
                            else:
                                if isinstance(projectile, dict):
                                    try:
                                        self.projectiles.remove(projectile)
                                    except Exception:
                                        pass
                                else:
                                    projectile.kill()

                            # Death handling for object enemies
                            if getattr(enemy, "health", 0) <= 0:
                                self.score += int(
                                    enemy.max_health * 18 * self.difficulty_multiplier
                                )
                                type_xp: Dict[str, int] = {
                                    "weak": 10,
                                    "normal": 16,
                                    "strong": 25,
                                    "giant": 50,
                                    "angel": 22,
                                }
                                base_xp: int = type_xp.get(enemy.enemy_type, 12)  # fallback XP
                                self.player_xp += base_xp
                                if self.player_xp >= self.xp_to_next_level:
                                    self.trigger_level_up()
                                enemy.kill()  # Remove dead enemy

                            # Chain hits: storm projectiles can hit additional distinct enemies
                            if isinstance(projectile, dict):
                                chain = projectile.get("chain_targets", 0)
                            else:
                                chain = getattr(projectile, "chain_targets", 0)
                            if chain and chain > 1 and not getattr(projectile, "_chain_applied", False):
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
                                chain_points = [(self._enemy_pos(enemy)[0], self._enemy_pos(enemy)[1])]

                                for i in range(to_chain):
                                    targ = others[i][1]
                                    if isinstance(targ, dict):
                                        targ["health"] -= p_damage * 2  # Increased damage for secondary targets
                                        if targ["health"] <= 0:
                                            self.score += int(
                                                targ.get("max_health", 10) * 18 * self.difficulty_multiplier
                                            )
                                            type_xp = {
                                                "weak": 10,
                                                "normal": 16,
                                                "strong": 25,
                                                "giant": 50,
                                                "angel": 22,
                                            }
                                            base_xp = type_xp.get(targ.get("type"), 12)
                                            self.player_xp += base_xp
                                            if self.player_xp >= self.xp_to_next_level:
                                                self.trigger_level_up()
                                            try:
                                                self.enemies.remove(targ)
                                            except Exception:
                                                pass
                                    else:
                                        try:
                                            targ.take_damage(p_damage * 2)  # Increased damage for secondary targets
                                        except Exception:
                                            try:
                                                targ.health -= p_damage * 2  # Increased damage for secondary targets
                                            except Exception:
                                                pass
                                        if getattr(targ, "health", 0) <= 0:
                                            self.score += int(
                                                targ.max_health * 18 * self.difficulty_multiplier
                                            )
                                            type_xp: Dict[str, int] = {
                                                "weak": 10,
                                                "normal": 16,
                                                "strong": 25,
                                                "giant": 50,
                                                "angel": 22,
                                            }
                                            base_xp: int = type_xp.get(targ.enemy_type, 12)
                                            self.player_xp += base_xp
                                            if self.player_xp >= self.xp_to_next_level:
                                                self.trigger_level_up()
                                            targ.kill()

                                    # add visual point for this chained target
                                    tx, ty = self._enemy_pos(targ)
                                    chain_points.append((tx, ty))

                                # append visual effect when we actually chained at least once
                                if len(chain_points) > 1:
                                    self.game_state.chain_lightning_effects.append({"points": chain_points, "timer": 8})
                                try:
                                    projectile._chain_applied = True
                                except Exception:
                                    try:
                                        projectile["_chain_applied"] = True
                                    except Exception:
                                        pass
                                processed_projectile = True
                    break

            # Projectiles hit bosses (only for sprite projectiles)
            hit_bosses: List[Any] = []
            if hasattr(projectile, "rect"):
                hit_bosses = pygame.sprite.spritecollide(projectile, self.bosses, False)
            for boss in hit_bosses:
                if boss.enemy_type == "boss_final" and self.selected_stage == "prologo":
                    if self.prologo_final_boss_immortal:
                        continue  # Invulnerable
                    else:
                        boss.take_damage(projectile.damage)
                        if boss.health <= boss.max_health * 0.1:
                            self.prologo_final_boss_immortal = True
                            boss.health = boss.max_health * 0.1
                else:
                    boss.take_damage(projectile.damage)

                # Handle projectile piercing for bosses too
                # NOTE: Spears should not pierce bosses — treat spear as single-hit for bosses
                if getattr(projectile, "pierce_all", False) and getattr(projectile, "weapon_type", None) != "spear":
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
                    self.score += int(boss.max_health * 25)
                    # Give XP for boss kill (per-type table, flat values)
                    boss_xp_map: Dict[str, int] = {"medium": 80, "big": 150, "final": 400}
                    boss_base_xp: int = boss_xp_map.get(
                        boss.enemy_type.replace("boss_", ""), 100
                    )
                    self.player_xp += boss_base_xp
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
                    max_chain_distance = 300  # Maximum distance for chain lightning (pixels)
                    
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
                    chain_points = [(self._enemy_pos(primary_boss)[0], self._enemy_pos(primary_boss)[1])]
                    
                    for i in range(to_chain):
                        targ = others[i][1]
                        targ.take_damage(projectile.damage * 2)  # Increased damage for secondary targets
                        
                        # Add to chain points for visual effect
                        tx, ty = self._enemy_pos(targ)
                        chain_points.append((tx, ty))
                        
                        # death handling for chained targets
                        if targ.health <= 0:
                            if hasattr(targ, 'enemy_type') and targ.enemy_type.startswith('boss_'):
                                # Boss death handling
                                self.score += int(targ.max_health * 25)
                                boss_xp_map: Dict[str, int] = {"medium": 80, "big": 150, "final": 400}
                                boss_base_xp: int = boss_xp_map.get(
                                    targ.enemy_type.replace("boss_", ""), 100
                                )
                                self.player_xp += boss_base_xp
                                if self.player_xp >= self.xp_to_next_level:
                                    self.trigger_level_up()
                                targ.kill()
                            else:
                                # Regular enemy death handling
                                self.score += int(
                                    targ.max_health * 18 * self.difficulty_multiplier
                                )
                                type_xp = {
                                    "weak": 10,
                                    "normal": 16,
                                    "strong": 25,
                                    "giant": 50,
                                    "angel": 22,
                                }
                                base_xp = type_xp.get(targ.enemy_type, 12)
                                self.player_xp += base_xp
                                if self.player_xp >= self.xp_to_next_level:
                                    self.trigger_level_up()
                                targ.kill()
                    
                    # Add chain lightning effect to game state
                    if len(chain_points) > 1:
                        self.game_state.chain_lightning_effects.append({
                            "points": chain_points,
                            "timer": 8  # Show for 8 frames
                        })
                        # Mark chain applied so we don't duplicate
                        try:
                            projectile._chain_applied = True
                        except Exception:
                            try:
                                projectile["_chain_applied"] = True
                            except Exception:
                                pass
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
                    if not hasattr(self.player, "slow_timer") or getattr(self.player, "slow_timer", 0) <= 0:
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
                            p = BurnParticle(enemy.x + random.uniform(-8, 8), enemy.y - 8 + random.uniform(-4, 4), vx, vy, life=random.randint(18, 44), size=random.randint(3, 5))
                            try:
                                enemy.burn_particles.append(p)
                            except Exception:
                                pass
                        # Player particles - same stronger effect
                        if not hasattr(self.player, "burn_particles"):
                            self.player.burn_particles = []
                        for _ in range(random.randint(3, 6)):
                            vx = random.uniform(-30, 30)
                            vy = random.uniform(15, 40)
                            p = BurnParticle(self.player.x + random.uniform(-16, 16), self.player.y - 8 + random.uniform(-4, 4), vx, vy, life=random.randint(18, 44), size=random.randint(3, 5))
                            self.player.burn_particles.append(p)
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
                        enemy.get("damage", 5) / self.fps
                    ) * self.damage_reduction_multiplier
                    self.player.take_damage(actual_damage)
                    contact_damage_to_enemy = 2.0 / self.fps
                    if isinstance(enemy, dict):
                        enemy["health"] -= contact_damage_to_enemy
                        if enemy["health"] <= 0:
                            try:
                                self.enemies.remove(enemy)
                            except Exception:
                                pass
                    else:
                        enemy.take_damage(contact_damage_to_enemy, show_floating=False)
                    if self.frame_count % 10 == 0:
                        # Shorter, weaker shake for contact
                        self.shake_timer = 6
                        self.shake_intensity = max(self.shake_intensity, 6)

                        # Add burn particles to dict enemy (visual only)
                        try:
                            parts = enemy.setdefault("burn_particles", [])
                            ex = enemy.get("x", 0)
                            ey = enemy.get("y", 0)
                            for _ in range(random.randint(3, 6)):
                                parts.append({
                                    "x": ex + random.uniform(-8, 8),
                                    "y": ey - 8 + random.uniform(-4, 4),
                                    "vx": random.uniform(-30, 30),
                                    "vy": random.uniform(15, 40),
                                    "life": random.randint(18, 44),
                                    "size": random.randint(3, 5),
                                })
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
                                p = _BP(self.player.x + random.uniform(-12, 12), self.player.y - 8 + random.uniform(-2, 2), vx, vy, life=random.randint(12, 30), size=random.randint(2, 4))
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
                        self.spawn_floating_text(str(int(damage)), ex, ey - self._enemy_radius(enemy) - 8)
                    except Exception:
                        pass
                    self.player.health = min(self.player.max_health, self.player.health + heal)
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

        # Also handle dict-based drain timers (legacy dict enemies)
        if not hasattr(self.enemies, "update"):
            for enemy in list(self.enemies):
                if isinstance(enemy, dict) and enemy.get("drain_timer", 0) > 0:
                    enemy["drain_timer"] -= 1
                    if enemy["drain_timer"] % 60 == 0:
                        damage = enemy.get("drain_damage", 1)
                        heal = enemy.get("drain_heal", 1)
                        enemy["health"] = max(0, enemy.get("health", 0) - damage)
                        try:
                            ex, ey = self._enemy_pos(enemy)
                            self.spawn_floating_text(str(int(damage)), ex, ey - enemy.get("radius", 12) - 8)
                        except Exception:
                            pass
                        self.player.health = min(self.player.max_health, self.player.health + heal)
                    if enemy["drain_timer"] <= 0:
                        for k in ("drain_timer", "drain_damage", "drain_heal", "drain_source"):
                            try:
                                del enemy[k]
                            except Exception:
                                pass

        # Update spine timers
        for enemy in self.enemies:
            if hasattr(enemy, "spine_timer") and enemy.spine_timer > 0:
                enemy.spine_timer -= 1
                if enemy.spine_timer <= 0:
                    enemy.spine_from = None

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
                gs.weapon_choices = list(self.weapon_choices) if hasattr(self, "weapon_choices") else []
                gs.upgrade_choices = list(self.upgrade_choices) if hasattr(self, "upgrade_choices") else []
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
                max_level: int = getattr(game, "max_weapon_level", WEAPON_DEFS.get(weapon_id, {}).get("max_level", 6))
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
                    upgrade_desc: str = f"Upgrade {weapon_name} to level {current_level + 1}"
                    weapon_upgrades.append({
                        "id": f"{weapon_id}_upgrade",
                        "name": upgrade_name,
                        "description": upgrade_desc,
                        "apply": lambda w=weapon_id: game.apply_weapon(f"{w}_upgrade"),
                    })
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
                {"id": "shotgun", "name": "Hellgun", "description": "Fires multiple pellets in a spread pattern"},
                {"id": "orbital", "name": "Orbitals", "description": "Summon orbiting sentinels that auto-fire"},
                {"id": "spear", "name": "Spear", "description": "Pierces through multiple enemies"},
                {"id": "beast", "name": "The number of the beast", "description": "Unleash demonic power with devastating attacks"},
                {"id": "Soul Drain", "name": "Soul Drain", "description": "Fires homing soul projectiles that drain life from enemies and heal the player"},
            ]
            choices: List[Dict[str, str]] = random.sample(initial_weapons, min(3, len(initial_weapons)))
            return [{"id": c["id"], "name": c["name"], "description": c["description"]} for c in choices]

    def generate_weapon_choices(self):
        """Generate weapon choices"""

        # Use centralized weapon definitions
        all_weapons: List[Dict[str, str]] = get_weapon_definitions()
        all_weapon_ids = [w["id"] for w in all_weapons]

        # At player level 6 we must *always* propose 3 new weapons (no upgrades)
        if getattr(self, "player_level", None) == 6:
            unowned = [w for w in all_weapon_ids if w not in self.player_weapons]
            choices: List[Dict[str, str]] = []
            if unowned:
                # If fewer than 3 unowned weapons, sample with replacement to reach 3
                if len(unowned) >= 3:
                    selected = random.sample(unowned, 3)
                else:
                    selected = [random.choice(unowned) for _ in range(3)]
                for weapon in selected:
                    choices.append(
                        {
                            "id": f"acquire_{weapon}",
                            "name": WEAPON_DEFS[weapon]["name"],
                            "description": WEAPON_DEFS[weapon]["description"],
                        }
                    )
            else:
                # No unowned weapons: fallback to picking (with replacement) from all weapons
                selected = [random.choice(all_weapon_ids) for _ in range(3)]
                for weapon in selected:
                    choices.append(
                        {
                            "id": f"acquire_{weapon}",
                            "name": WEAPON_DEFS.get(weapon, {}).get('name', weapon),
                            "description": WEAPON_DEFS.get(weapon, {}).get('description', ''),
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
        available_weapons: List[Dict[str, str]] = [
            w for w in all_weapons if w["id"] not in self.player_weapons
        ]

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
            max_level: int = getattr(self, "max_weapon_level", WEAPON_DEFS.get(weapon_id, {}).get("max_level", 6))  # Default max level

            if current_level < max_level:
                weapon_name: str = WEAPON_DEFS.get(weapon_id, {}).get("name", weapon_id.title())
                upgrade_name: str = f"{weapon_name} Lv.{current_level + 1}"
                upgrade_desc: str = get_weapon_upgrade_description(weapon_id, current_level + 1)

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
                    self.orbital_count = get_orbital_count(self.weapon_levels["orbital"])
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
        if not (getattr(self, 'is_initial_tower_choice', False) or getattr(self, 'awaiting_tower_choice', False)):
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
            {"id": "fire", "name": "Fire Tower", "description": "Burn nearby enemies"},
            {"id": "storm", "name": "Storm Tower", "description": "Strike lightning at enemies"},
            {"id": "ice", "name": "Ice Tower", "description": "Slow enemies with frost"},
        ]

    def _wall_x_at(self, side: str, y: float) -> float:
        """Return wall x coordinate for given side ('left' or 'right') nearest to provided y."""
        points = self.left_wall_points if side == "left" else self.right_wall_points
        if not points:
            return 320.0 if side == "left" else 960.0
        # Find nearest y sample
        nearest = min(points, key=lambda p: abs(p[1] - y))
        return nearest[0]

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
        self.left_tower = Tower(left_x, desired_y, fire_rate=self.statue_fire_rate, tower_type=tower_type)
        self.right_tower = Tower(right_x, desired_y, fire_rate=self.statue_fire_rate, tower_type=tower_type)
        # Ensure visibility after player actively chose towers
        self.left_tower.visible = True
        self.right_tower.visible = True

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
        if getattr(self, "enemy_manager", None) is not None:
            self.enemy_manager.enemy_spawn_timer -= 1
            if self.enemy_manager.enemy_spawn_timer <= 0:
                self.spawn_enemy()
                if self.selected_stage == "prologo":
                    self.enemy_manager.enemy_spawn_timer = int(self.enemy_manager.enemy_spawn_rate * 1.5)
                else:
                    self.enemy_manager.enemy_spawn_timer = self.enemy_manager.enemy_spawn_rate
        else:
            self.enemy_spawn_timer -= 1
            if self.enemy_spawn_timer <= 0:
                self.spawn_enemy()
                if self.selected_stage == "prologo":
                    self.enemy_spawn_timer = int(self.enemy_spawn_rate * 1.5)
                else:
                    self.enemy_spawn_timer = self.enemy_spawn_rate

        # Periodic big enemy spawn (delegate to EnemyManager when present)
        if getattr(self, "enemy_manager", None) is not None:
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
            if getattr(self, "enemy_manager", None) is not None:
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
            if getattr(self, "enemy_manager", None) is not None:
                try:
                    self.enemy_manager.wave_boss_spawned = False
                except Exception:
                    self.wave_boss_spawned = False
            else:
                self.wave_boss_spawned = False

            # Reset prologo final boss flags if any (proxy to manager when available)
            # Skip reset for prologo to prevent multiple spawns
            if self.selected_stage != "prologo":
                if getattr(self, "enemy_manager", None) is not None:
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
            if getattr(self, "enemy_manager", None) is not None:
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
                if getattr(self, "enemy_manager", None) is not None:
                    self.enemy_manager.enemy_spawn_rate = self.enemy_spawn_rate
            else:
                self.enemy_spawn_rate = max(
                    self.spawn_min_rate,
                    int(self.base_spawn_rate - self.wave * self.spawn_ramp_slope_post),
                )
                if getattr(self, "enemy_manager", None) is not None:
                    self.enemy_manager.enemy_spawn_rate = self.enemy_spawn_rate

            self.difficulty_multiplier = 1.0 + (self.wave * 0.12)

        # Spawn boss at 28 seconds (delegate to manager when available)
        if getattr(self, "enemy_manager", None) is not None:
            try:
                self.enemy_manager.update_wave_boss(self.wave_time)
            except Exception:
                # Fallback to legacy behavior
                if not self.wave_boss_spawned and self.wave_time >= 28:
                    if not (
                        self.selected_stage == "prologo" and self.prologo_final_boss_spawned
                    ):
                        if self.wave % 3 == 0 and self.wave > 0:
                            self.spawn_boss("big")
                        else:
                            self.spawn_boss("mid")
                    self.wave_boss_spawned = True
        else:
            if not self.wave_boss_spawned and self.wave_time >= 28:
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
            if getattr(self, "enemy_manager", None) is not None:
                if not self.enemy_manager.big_spawned_this_wave:
                    self.spawn_big_enemy()
                    self.enemy_manager.big_spawned_this_wave = True
            else:
                if not self.big_spawned_this_wave:
                    self.spawn_big_enemy()
                    self.big_spawned_this_wave = True

        # Ensure wave boss spawning is handled by manager when available
        if getattr(self, "enemy_manager", None) is not None:
            # manager.update_wave_boss already called earlier; nothing else required here
            pass

    def update_prologo_events(self) -> None:
        """Handle special Prologo events (managed by EnemyManager when present)"""
        if getattr(self, "enemy_manager", None) is not None:
            try:
                self.enemy_manager.update_prologo_events()
                return
            except Exception:
                # Fallback to legacy behavior below
                pass

        # Final boss at 2:55 (175 seconds) - delegate to manager when available
        if getattr(self, "enemy_manager", None) is not None:
            try:
                self.enemy_manager.update_prologo_events()
            except Exception:
                # fallback to legacy behavior
                if (
                    self.selected_stage == "prologo"
                    and not self.prologo_final_boss_spawned
                    and self.time_elapsed >= 175
                ):
                    logger.info("[PROLOGO] Spawning final boss at time %s", self.time_elapsed)
                    self.spawn_boss("final")
                    self.prologo_final_boss_spawned = True
        else:
            if (
                self.selected_stage == "prologo"
                and not self.prologo_final_boss_spawned
                and self.time_elapsed >= 175
            ):
                logger.info("[PROLOGO] Spawning final boss at time %s", self.time_elapsed)
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
                    logger.info("[PROLOGO] Final boss reached full health — triggering lightning strike")
                    self.prologo_lightning_strike = True
                    self.generate_lightning()
                    logger.debug(
                        "[PROLOGO] Lightning points generated: %s",
                        len(self.lightning_points) if hasattr(self, "lightning_points") else None,
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
            font_large = pygame.font.Font(None, 64)
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
            prompt = get_text("Press ESC to return to menu", font_medium, (255, 255, 153)).copy()
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
        # Spawn from top of screen
        x: int = random.randint(0, self.width)
        # Keep spawn within walls
        x = self.clamp_to_walls(x)
        y = -20

        # Choose enemy type based on wave and random chance
        rand: float = random.random()
        # Choose health and speed based on type
        health: float = 0.0
        if self.wave >= 5 and rand < 0.05:  # 5% chance for giant after wave 5
            enemy_type = "giant"
            health = 160 * self.difficulty_multiplier  # Doubled from 80
            # Base non-boss giant speed (from balance)
            speed = ENEMY_BASE_SPEEDS.get('giant', 45)
        elif self.wave >= 3 and rand < 0.15:  # 15% chance for strong after wave 3
            enemy_type = "strong"
            health = 70 * self.difficulty_multiplier  # Doubled from 35
            # Strong enemies (from balance)
            speed = ENEMY_BASE_SPEEDS.get('strong', 60)
        elif rand < 0.3:  # 30% chance for normal
            enemy_type = "normal"
            health = 50 * self.difficulty_multiplier  # Doubled from 25
            # Normal enemies (from balance)
            speed = ENEMY_BASE_SPEEDS.get('normal', 75)
        elif rand < 0.5:  # 20% chance for angel
            enemy_type = "angel"
            health = 40 * self.difficulty_multiplier  # Doubled from 20
            # Angel speed (from balance)
            speed = ENEMY_BASE_SPEEDS.get('angel', 60)
        else:  # 25% chance for weak
            enemy_type = "weak"
            health = 30 * self.difficulty_multiplier  # Doubled from 15
            # Weak enemies (from balance)
            speed = ENEMY_BASE_SPEEDS.get('weak', 35)

        # Use EnemyManager when available
        if getattr(self, "enemy_manager", None) is not None:
            try:
                self.enemy_manager.spawn(x, y, enemy_type, health, speed)
            except Exception:
                enemy: Enemy = Enemy(x, y, enemy_type, health, speed)
                if hasattr(self.enemies, "add"):
                    self.enemies.add(enemy)
                else:
                    self.enemies.append(enemy)
        else:
            enemy: Enemy = Enemy(x, y, enemy_type, health, speed)
            if hasattr(self.enemies, "add"):
                self.enemies.add(enemy)
            else:
                self.enemies.append(enemy)

    def spawn_enemy_projectiles(self) -> None:
        """Have some enemies shoot projectiles at the player"""
        # Only some enemies shoot (angels and bosses)
        shooting_enemies = []
        for enemy in self.enemies:
            if enemy.enemy_type in ["angel"]:
                shooting_enemies.append(enemy)
        for boss in self.bosses:
            if boss.enemy_type in ["boss_medium", "boss_big", "boss_final"]:
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
        if getattr(self, "enemy_manager", None) is not None:
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
            x = random.randint(0, self.width)
            # Keep top spawn within walls
            x = self.clamp_to_walls(x)
            y = -30

        enemy_type = "giant"
        health: float = 100 * self.difficulty_multiplier
        # Base non-boss giant speed (from balance)
        speed = ENEMY_BASE_SPEEDS.get('giant', 45)
        enemy: Enemy = Enemy(x, y, enemy_type, health, speed)
        if hasattr(self.enemies, "add"):
            self.enemies.add(enemy)
        else:
            self.enemies.append(enemy)

    def spawn_big_enemy(self) -> None:
        """Spawn a big enemy (giant). Delegates to EnemyManager if available."""
        if getattr(self, "enemy_manager", None) is not None:
            try:
                self.enemy_manager.spawn_giant_enemy()
                return
            except Exception:
                pass

        x: int = random.randint(0, self.width)
        # Keep spawn within walls
        x = self.clamp_to_walls(x)
        y = -30

        enemy_type = "giant"
        health: float = 100 * self.difficulty_multiplier
        # Base non-boss giant speed (spawn fallback)
        speed = ENEMY_BASE_SPEEDS.get('giant', 45)
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
                    x: int = random.randint(100, self.width - 100)
                    # Clamp random top spawn inside walls
                    x = self.clamp_to_walls(x)
                    y = 50
            if count is None:
                count: int = self.reinforcement_count

            # If this is an "extra" reinforcement (e.g., mid-boss doubled call), reduce enemies by 1/3
            # to make the extra wave smaller and less overwhelming. This is a silent adjustment.
            if count > self.reinforcement_count:
                count: int = max(1, int(round(count * 2.0 / 3.0)))

            # Choose types biased to normal/angel
            weights: List[float] = [0.3, 0.4, 0.2, 0.3]  # Bias toward normals and angels
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
                    speed = ENEMY_BASE_SPEEDS.get('weak', 35)
                elif etype == "normal":
                    enemy_type = "normal"
                    health = int(25 * self.difficulty_multiplier * 1.1)
                    speed = ENEMY_BASE_SPEEDS.get('normal', 75)
                elif etype == "strong":
                    enemy_type = "strong"
                    health = int(45 * self.difficulty_multiplier * 1.1)
                    speed = ENEMY_BASE_SPEEDS.get('strong', 60)
                else:  # angel
                    enemy_type = "angel"
                    health = int(30 * self.difficulty_multiplier * 1.1)
                    speed = ENEMY_BASE_SPEEDS.get('angel', 60)

                enemy: Enemy = Enemy(rx, ry, enemy_type, health, speed)
                self.enemies.add(enemy)
        except Exception as e:
            logger.exception("Error spawning reinforcements: %s", e)
            import traceback

            traceback.print_exc()

    def spawn_boss(self, boss_type) -> None:
        """Spawn a boss of the specified type (delegates to EnemyManager)."""
        if getattr(self, "enemy_manager", None) is not None:
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
            speed = ENEMY_BASE_SPEEDS.get('boss_final', 40)
        elif boss_type == "big":
            enemy_type = "boss_big"
            health = 600 * self.difficulty_multiplier
            speed = ENEMY_BASE_SPEEDS.get('boss_big', 40)
        else:  # mid
            enemy_type = "boss_medium"
            health = 300 * self.difficulty_multiplier
            speed = ENEMY_BASE_SPEEDS.get('boss_medium', 45)

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
