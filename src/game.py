import logging
import math
import os
import random
from typing import Any, Dict, List, Literal, Self

import pygame
from pygame.key import ScancodeWrapper

from src.entities.enemy import Enemy
from src.entities.player import Player
from src.projectile import Projectile
from src.ui import PygameUIManager

logger: logging.Logger = logging.getLogger(__name__) 


class Game:
    def __init__(
        self,
        fast_forward_prologo: bool = False,
        fast_forward_prologo_force_lightning: bool = False,
        debug: bool = False,
    ) -> None:
        pygame.init()
        pygame.mixer.init()

        # Debug fast-forward flags (set by CLI/tests)
        self.fast_forward_prologo: bool = fast_forward_prologo
        self.fast_forward_prologo_force_lightning: bool = fast_forward_prologo_force_lightning
        self.fast_forward_applied = False

        # Debug flag to control debug output
        self.debug: bool = debug

        self.width = 1280
        self.height = 720
        self.screen: pygame.Surface = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Satan's Roguelite - Vampire Survivors Style")
        self.clock = pygame.time.Clock()
        self.running = True
        self.fps = 60

        # Game state
        self.player: Player[int, int] = Player(self.width // 2, self.height - 80)
        self.enemies: Any = pygame.sprite.Group()
        self.projectiles: Any = pygame.sprite.Group()
        self.enemy_projectiles: Any = pygame.sprite.Group()
        self.bosses: Any = pygame.sprite.Group()

        # Stage system
        self.selected_stage = None
        self.stage_settings = {
            "prologo": {
                "bg_color": (0, 0, 0),
                "floor_color": (0, 50, 0),
                "wall_color": (150, 150, 150),
                "building_color": (139, 69, 69),
            },
            "limbo": {
                "bg_color": (0, 0, 0),
                "floor_color": (100, 50, 0),
                "wall_color": (42, 18, 8),
                "building_color": None,  # No buildings in limbo
            },
            "limbo_2": {
                "bg_color": (0, 0, 0),
                "floor_color": (100, 50, 0),
                "wall_color": (42, 18, 8),
                "building_color": None,
            },
            "limbo_3": {
                "bg_color": (0, 0, 0),
                "floor_color": (100, 50, 0),
                "wall_color": (42, 18, 8),
                "building_color": None,
            },
        }

        # Game variables
        self.wave = 0
        self.wave_time = 0
        self.wave_duration = 30  # seconds
        self.enemy_spawn_timer = 0
        self.base_spawn_rate = 72  # base frames between spawns
        self.enemy_spawn_rate = 72  # frames between spawns

        # Wave ramp settings
        self.spawn_ramp_start_wave = 3
        self.spawn_ramp_slope_pre = 3
        self.spawn_ramp_slope_post = 6
        self.spawn_min_rate = 30

        # Spawn acceleration
        self.spawn_accel_timer: int = 20 * self.fps
        self.time_elapsed = 0

        # Giant enemy spawning
        self.big_enemy_timer: int = 12 * self.fps
        self.big_enemy_fast_interval: int = 9 * self.fps
        self.big_spawned_this_wave = False

        # Reinforcements
        self.reinforcement_delay_ms = 2000
        self.reinforcement_count = 8

        self.score = 0
        self.difficulty_multiplier = 1.0
        self.player_damage = 15

        # XP and Level system
        self.player_xp = 0
        self.player_level = 1
        self.xp_to_next_level = 100
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
        self.max_extra_weapons = 2
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
        self.permanent_stats: Dict[str, int] = {
            "power": 0,  # Red - affects damage
            "vigor": 0,  # Yellow - affects max health
            "adrenaline": 0,  # Purple - affects fire rate/speed
            "structure": 0,  # Brown - affects armor/defense
        }

        # Frame counter for animations
        self.frame_count = 0

        # Player animation
        self.player_anim_frame = 0
        self.player_anim_timer = 0
        self.player_anim_speed = 30  # frames between animation changes (slower)
        self.player_is_moving = False

        # Boss system
        self.wave_boss_spawned = False

        # Prologo special events
        self.prologo_final_boss_spawned = False
        self.prologo_final_boss_defeated = False
        self.prologo_final_boss_immortal = False
        self.prologo_lightning_timer = 0
        # Duration (frames) between lightning strike start and showing ending screen.
        # Default was 180 (3s); add 2 more seconds as requested (2 * fps)
        self.prologo_lightning_duration_frames: int = 180 + 2 * self.fps
        self.prologo_lightning_strike = False
        self.lightning_points: List[tuple] = []

        # Weapon system
        self.max_extra_weapons = 2
        self.max_weapon_level = 6
        self.orbital_count = 3

        # Burst fire system
        self.burst_count = 0
        self.burst_max = 3
        self.burst_cooldown = 0
        self.burst_fire_rate = 6
        self.burst_pause = 30

        # Weapon cooldowns
        self.spear_cooldown_timer = 0
        self.shotgun_cooldown_timer = 0

        # Upgrade system
        self.awaiting_upgrade = False
        self.selected_upgrade_index = 0
        self.upgrade_levels: Dict[str, int] = {
            "damage": 0,
            "fire_rate": 0,
            "max_health": 0,
            "projectile_size": 0,
            "armor": 0,
        }

        # Weapon selection
        self.awaiting_weapon_choice = False
        self.selected_weapon_index = 0

        # Permanent upgrades (meta-progression)
        self.permanent_stats: Dict[str, int] = {"power": 0, "vigor": 0, "adrenaline": 0, "structure": 0}

        # Screen effects
        self.shake_timer = 0
        self.shake_intensity = 5

        # Menu state
        self.showing_stage_menu = True
        self.showing_permanent_upgrades = False
        self.showing_prologo_end = False
        self.paused = False
        # Game over state
        self.showing_game_over = False
        # Fade animation for game over overlay
        self.game_over_alpha = 0  # 0..255
        # Duration in ms for fade-in (approx). Adjust for desired speed.
        self.game_over_fade_duration_ms = 900
        # Computed per-frame fade speed based on duration
        frames_for_fade: int = max(
            1, int((self.game_over_fade_duration_ms / 1000.0) * self.fps)
        )
        self.game_over_fade_speed: int = max(1, int(255 / frames_for_fade))

        # Stage start countdown
        self.stage_start_countdown = 0  # 0 = not counting, >0 = counting down
        self.stage_start_timer = 0

        # Pause menu
        self.pause_menu_option = 0  # 0=Resume, 1=Restart, 2=Quit to Menu

        # Wall collision data
        self.left_wall_points: List[tuple] = []
        self.right_wall_points: List[tuple] = []
        self.generate_walls()

        # Buildings (set per stage)
        self.buildings: List[Dict[str, Any]] = []

        # Limbo features
        self.dead_trees: List[Dict[str, Any]] = []
        self.statue_projectiles: List[Dict[str, Any]] = []
        self.statue_cooldown_left = 0
        self.statue_cooldown_right = 0
        self.statue_fire_rate = 220

        # Center messages
        self.center_messages: List[Dict[str, Any]] = []

        # Menu state (submenu for Limbo)
        self.showing_limbo_menu = False

        # Load assets
        self.load_assets()

        # Initialize Pygame UI manager (handles drawing)
        self.ui: PygameUIManager[Self] = PygameUIManager(self)

        # Initialize orbitals
        self.orbitals: List[Dict[str, Any]] = []

        # Mouse tracking
        self.mouse_x: int = self.width // 2
        self.mouse_y: int = self.height // 2

    @property
    def game_state(self) -> Self:
        """Return self for UI compatibility"""
        return self

    def load_assets(self) -> None:
        """Load game assets"""
        self.assets = {}
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

        assets_dir: str = os.path.join(os.path.dirname(__file__), "..", "assets")
        for asset in asset_files:
            path: str = os.path.join(assets_dir, asset)
            try:
                if os.path.exists(path):
                    self.assets[asset] = pygame.image.load(path).convert_alpha()
                else:
                    self.assets[asset] = None
                    logger.warning("Asset %s not found at %s", asset, path)
            except Exception as e:
                self.assets[asset] = None
                logger.exception("Error loading asset %s: %s", asset, e)

    def generate_walls(self) -> None:
        """Generate irregular wall points for collision detection"""

        self.left_wall_points = []
        self.right_wall_points = []

        for y in range(0, self.height + 1, 20):
            progress: float = y / self.height
            if self.is_limbo_stage():
                width_at_y: float = 680 - (progress * 280)
            else:
                width_at_y: float = 560 - (progress * 240)

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

        wall_thickness = 25
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
            shake_x = 0
            shake_y = 0
            if self.shake_timer > 0:
                shake_x: int = random.randint(-self.shake_intensity, self.shake_intensity)
                shake_y: int = random.randint(-self.shake_intensity, self.shake_intensity)

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

    def draw_ui(self, shake_x=0, shake_y=0) -> None:
        """Delegate UI drawing work to the Pygame UI manager where appropriate."""
        # Draw stage start countdown (kept here to avoid changing menu ordering)
        if self.stage_start_countdown > 0:
            font_large: pygame.Font = pygame.font.SysFont("chiller", 72)
            countdown_text: pygame.Surface = font_large.render(
                str(self.stage_start_countdown), True, (255, 255, 0)
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
        elif self.showing_prologo_end:
            self.draw_prologo_end(shake_x, shake_y)
        elif self.awaiting_weapon_choice:
            self.draw_weapon_selection(shake_x, shake_y)
        elif self.awaiting_upgrade:
            self.draw_upgrade_selection(shake_x, shake_y)
        elif self.paused:
            self.draw_pause_menu(shake_x, shake_y)

    def draw_hud(self, shake_x=0, shake_y=0) -> None:
        """Draw the HUD elements"""
        font = pygame.font.Font(None, 24)
        small_font = pygame.font.Font(None, 18)

        # Score
        score_text: pygame.Surface = font.render(f"Score: {int(self.score)}", True, (255, 255, 0))
        self.screen.blit(score_text, (10 + shake_x, 10 + shake_y))

        # Wave
        wave_text: pygame.Surface = font.render(f"Wave: {self.wave}", True, (255, 100, 100))
        self.screen.blit(wave_text, (10 + shake_x, 40 + shake_y))

        # Time
        minutes = int(self.time_elapsed // 60)
        seconds = int(self.time_elapsed % 60)
        time_text: pygame.Surface = font.render(f"Time: {minutes}:{seconds:02d}", True, (100, 200, 255))
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
        health_ratio: float = self.player.health / self.player.max_health
        # Health color: dark green for healthy, yellow/red for mid/low
        health_color: tuple[Literal[20], Literal[80], Literal[20]] | tuple[Literal[255], Literal[255], Literal[0]] | tuple[Literal[255], Literal[0], Literal[0]] = (
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
        health_text: pygame.Surface = small_font.render(
            f"{int(self.player.health)}/{int(self.player.max_health)}",
            True,
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
        xp_ratio: float = self.player_xp / self.xp_to_next_level
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
        xp_text: pygame.Surface = small_font.render(
            f"{int(self.player_xp)}/{int(self.xp_to_next_level)}", True, (255, 255, 255)
        )
        self.screen.blit(
            xp_text,
            (
                bar_x + bar_width // 2 - xp_text.get_width() // 2 + shake_x,
                xp_bar_y + bar_height // 2 - xp_text.get_height() // 2 + shake_y,
            ),
        )

        # Level
        level_text: pygame.Surface = font.render(f"Level {self.player_level}", True, (255, 215, 0))
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
        if hasattr(self, "player_weapons") and self.player_weapons:
            name_map: Dict[str, str] = {
                "shotgun": "Shotgun",
                "orbital": "Orbitals",
                "spear": "Spear",
                "beast": "The number of the beast",
            }
            for i, wid in enumerate(self.player_weapons):
                lvl: int = self.weapon_levels.get(wid, 0)
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

                weapon_text: pygame.Surface = small_font.render(display_text, True, (200, 200, 200))
                self.screen.blit(
                    weapon_text,
                    (
                        hud_x - box_w // 2 - weapon_text.get_width() // 2 + shake_x,
                        y - 8 + shake_y,
                    ),
                )

                # If at max level, add MAX indicator
                if lvl >= getattr(self, "max_weapon_level", 6):
                    max_text: pygame.Surface = small_font.render("MAX", True, (255, 215, 0))
                    self.screen.blit(
                        max_text,
                        (
                            hud_x - 12 - max_text.get_width() // 2 + shake_x,
                            y - 8 + shake_y,
                        ),
                    )

        # Draw center messages
        self.draw_center_messages(shake_x, shake_y)

    def draw_center_messages(self, shake_x=0, shake_y=0) -> None:
        """Draw any active centered messages"""
        for msg in self.center_messages:
            try:
                font = pygame.font.Font(None, msg.get("font_size", 36))
                # Shadow for readability
                shadow_text: pygame.Surface = font.render(msg["text"], True, (0, 0, 0))
                self.screen.blit(
                    shadow_text,
                    (
                        self.width // 2 - shadow_text.get_width() // 2 + 2 + shake_x,
                        self.height // 2 - 40 + 2 + shake_y,
                    ),
                )
                # Main text
                main_text: pygame.Surface = font.render(msg["text"], True, msg["color"])
                self.screen.blit(
                    main_text,
                    (
                        self.width // 2 - main_text.get_width() // 2 + shake_x,
                        self.height // 2 - 40 + shake_y,
                    ),
                )
            except Exception as e:
                logger.exception("Error drawing center message: %s", e)
                # Remove the problematic message
                if msg in self.center_messages:
                    self.center_messages.remove(msg)

    def draw_stage_menu(self, shake_x=0, shake_y=0) -> None:
        """Draw the stage selection menu"""
        font_large = pygame.font.Font(None, 48)
        font_medium = pygame.font.Font(None, 32)
        font_small = pygame.font.Font(None, 20)

        # If we're showing the Limbo submenu as a separate menu, draw it and return
        if self.showing_limbo_menu:
            # Limbo menu title
            title: pygame.Surface = font_large.render("LIMBO", True, (255, 215, 0))
            self.screen.blit(
                title,
                (
                    self.width // 2 - title.get_width() // 2 + shake_x,
                    self.height // 2 - 120 + shake_y,
                ),
            )

            # Limbo options (simple, separated menu)
            option_w = 320
            option_h = 48
            start_x: int = self.width // 2 - option_w // 2
            start_y: int = self.height // 2 - 40
            spacing = 60

            # note: menu layout is custom Pygame UI (no Tkinter)

            labels: List[str] = ["LIMBO", "LIMBO 2", "LIMBO 3"]
            for i, label in enumerate(labels):
                rect = pygame.Rect(start_x, start_y + i * spacing, option_w, option_h)
                hovered: bool = rect.collidepoint(self.mouse_x, self.mouse_y)
                bg: tuple[Literal[137], Literal[78], Literal[36]] | tuple[Literal[107], Literal[58], Literal[26]] = (137, 78, 36) if hovered else (107, 58, 26)
                pygame.draw.rect(self.screen, bg, rect)
                pygame.draw.rect(self.screen, (255, 255, 255), rect, 2)
                text: pygame.Surface = font_medium.render(label, True, (255, 255, 255))
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

            # Back button
            back_rect = pygame.Rect(
                self.width // 2 - 60, start_y + len(labels) * spacing + 10, 120, 36
            )
            back_hover: bool = back_rect.collidepoint(self.mouse_x, self.mouse_y)
            back_color: tuple[Literal[80], Literal[80], Literal[80]] | tuple[Literal[60], Literal[60], Literal[60]] = (80, 80, 80) if back_hover else (60, 60, 60)
            pygame.draw.rect(self.screen, back_color, back_rect)
            pygame.draw.rect(self.screen, (255, 255, 255), back_rect, 2)
            back_text: pygame.Surface = font_small.render("BACK", True, (255, 255, 255))
            self.screen.blit(
                back_text,
                (
                    self.width // 2 - back_text.get_width() // 2 + shake_x,
                    start_y + len(labels) * spacing + 14 + shake_y,
                ),
            )

            # Return early so main menu doesn't draw beneath it
            return

        # Title
        title: pygame.Surface = font_large.render("SATANS FALL", True, (255, 100, 100))
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
        prologo_hovered: bool = prologo_rect.collidepoint(self.mouse_x, self.mouse_y)
        prologo_color: tuple[Literal[189], Literal[89], Literal[89]] | tuple[Literal[139], Literal[69], Literal[69]] = (
            (189, 89, 89) if prologo_hovered else (139, 69, 69)
        )  # Lighter red when hovered
        pygame.draw.rect(self.screen, prologo_color, prologo_rect)
        pygame.draw.rect(self.screen, (255, 255, 255), prologo_rect, 2)  # White border
        prologo_text: pygame.Surface = font_medium.render("PROLOGUE", True, (255, 255, 255))
        self.screen.blit(
            prologo_text,
            (
                self.width // 2 - prologo_text.get_width() // 2 + shake_x,
                self.height // 2 - 40 + shake_y,
            ),
        )

        # Limbo main button (opens second menu)
        limbo_rect = pygame.Rect(self.width // 2 - 100, self.height // 2 + 10, 200, 40)
        limbo_hovered: bool = limbo_rect.collidepoint(self.mouse_x, self.mouse_y)
        limbo_color: tuple[Literal[137], Literal[78], Literal[36]] | tuple[Literal[107], Literal[58], Literal[26]] = (137, 78, 36) if limbo_hovered else (107, 58, 26)
        pygame.draw.rect(self.screen, limbo_color, limbo_rect)
        pygame.draw.rect(self.screen, (255, 255, 255), limbo_rect, 2)
        limbo_text: pygame.Surface = font_medium.render("LIMBO", True, (255, 255, 255))
        self.screen.blit(
            limbo_text,
            (
                self.width // 2 - limbo_text.get_width() // 2 + shake_x,
                self.height // 2 + 20 + shake_y,
            ),
        )

        # Permanent Upgrades button
        upgrades_rect = pygame.Rect(
            self.width // 2 - 125, self.height // 2 + 70, 250, 35
        )
        upgrades_hovered: bool = upgrades_rect.collidepoint(self.mouse_x, self.mouse_y)
        upgrades_bg_color: tuple[Literal[94], Literal[36], Literal[94]] | tuple[Literal[74], Literal[26], Literal[74]] = (
            (94, 36, 94) if upgrades_hovered else (74, 26, 74)
        )  # Lighter purple when hovered
        upgrades_border_color: tuple[Literal[255], Literal[224], Literal[20]] | tuple[Literal[255], Literal[204], Literal[0]] = (
            (255, 224, 20) if upgrades_hovered else (255, 204, 0)
        )  # Brighter gold when hovered
        pygame.draw.rect(self.screen, upgrades_bg_color, upgrades_rect)
        pygame.draw.rect(self.screen, upgrades_border_color, upgrades_rect, 2)
        upgrades_text: pygame.Surface = font_small.render(
            "PERMANENT UPGRADES", True, upgrades_border_color
        )
        self.screen.blit(
            upgrades_text,
            (
                self.width // 2 - upgrades_text.get_width() // 2 + shake_x,
                self.height // 2 + 80 + shake_y,
            ),
        )

    def draw_permanent_upgrades(self, shake_x=0, shake_y=0) -> None:
        """Draw the permanent upgrades menu"""
        font_large = pygame.font.Font(None, 36)
        font_medium = pygame.font.Font(None, 24)
        font_small = pygame.font.Font(None, 18)

        # Title
        title: pygame.Surface = font_large.render("PERMANENT UPGRADES", True, (255, 255, 0))
        self.screen.blit(
            title, (self.width // 2 - title.get_width() // 2 + shake_x, 50 + shake_y)
        )

        # Subtitle
        subtitle: pygame.Surface = font_small.render(
            "Upgrade your demonic powers", True, (136, 136, 136)
        )
        self.screen.blit(
            subtitle,
            (self.width // 2 - subtitle.get_width() // 2 + shake_x, 85 + shake_y),
        )

        # Stats display
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

        for stat in stat_configs:
            # Check hover for stat name
            name_rect = pygame.Rect(self.width // 2 - 100, stat["y"], 100, 30)
            is_hovered: bool = name_rect.collidepoint(self.mouse_x, self.mouse_y)

            # Stat name (brighter if hovered and can upgrade)
            name_color = stat["color"]
            if is_hovered and self.permanent_stats[stat["key"]] < 10:
                # Brighten the color when hovered
                name_color: tuple[int, ...] = tuple(min(255, c + 50) for c in stat["color"])
            elif self.permanent_stats[stat["key"]] >= 10:
                # Gray out if maxed
                name_color = (100, 100, 100)

            name_text: pygame.Surface = font_medium.render(stat["name"], True, name_color)
            self.screen.blit(
                name_text, (self.width // 2 - 100 + shake_x, stat["y"] + shake_y)
            )

            # Stat value
            value: int = self.permanent_stats[stat["key"]]
            value_text: pygame.Surface = font_small.render(f"Level: {value}", True, (255, 255, 255))
            self.screen.blit(
                value_text, (self.width // 2 + 50 + shake_x, stat["y"] + shake_y)
            )

            # MAX indicator if at max level
            if value >= 10:
                max_text: pygame.Surface = font_small.render("MAX", True, (255, 215, 0))
                self.screen.blit(
                    max_text, (self.width // 2 + 120 + shake_x, stat["y"] + shake_y)
                )

            # Bar background
            bar_x: int = self.width // 2 - 100
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
            (self.width // 2 - 300 + shake_x, separator_y + shake_y),
            (self.width // 2 + 300 + shake_x, separator_y + shake_y),
            2,
        )

        # Classic Upgrades section
        classic_text: pygame.Surface = font_medium.render("CLASSIC UPGRADES", True, (136, 136, 136))
        self.screen.blit(
            classic_text,
            (
                self.width // 2 - classic_text.get_width() // 2 + shake_x,
                separator_y + 30 + shake_y,
            ),
        )

        # Placeholder boxes for future upgrades (2 rows of 5)
        box_width = 90
        box_height = 70
        box_spacing = 110
        start_x: int = self.width // 2 - (5 * box_spacing) // 2 + box_spacing // 2

        # First row
        box_y1: int = separator_y + 60
        for i in range(5):
            box_x: int = start_x + (i * box_spacing)
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
            box_x: int = start_x + (i * box_spacing)
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

        # Instructions
        instructions: pygame.Surface = font_medium.render(
            "Left click to upgrade | Right click to downgrade | ESC to return",
            True,
            (200, 200, 200),
        )
        self.screen.blit(
            instructions,
            (
                self.width // 2 - instructions.get_width() // 2 + shake_x,
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
        """Draw the pause menu"""
        font_large = pygame.font.Font(None, 36)
        font_medium = pygame.font.Font(None, 28)

        # Semi-transparent overlay
        overlay = pygame.Surface((self.width, self.height))
        overlay.set_alpha(128)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        # Title
        title: pygame.Surface = font_large.render("PAUSED", True, (255, 255, 255))
        self.screen.blit(
            title,
            (
                self.width // 2 - title.get_width() // 2 + shake_x,
                self.height // 2 - 100 + shake_y,
            ),
        )

        # Options
        options: List[str] = ["Resume", "Restart", "Quit to Menu"]
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
                self.pause_menu_option: int = i

            # Color based on selection or hover
            is_selected: bool = i == self.pause_menu_option
            if is_selected or is_hovered:
                color: tuple[Literal[255], Literal[255], Literal[0]] | tuple[Literal[200], Literal[200], Literal[0]] = (255, 255, 0) if is_selected else (200, 200, 0)
            else:
                color = (255, 255, 255)

            text: pygame.Surface = font_medium.render(option, True, color)
            self.screen.blit(
                text,
                (self.width // 2 - text.get_width() // 2 + shake_x, y_pos + shake_y),
            )

    def draw_weapon_selection(self, shake_x=0, shake_y=0) -> None:
        """Draw weapon selection screen"""
        font_large = pygame.font.Font(None, 36)
        font_medium = pygame.font.Font(None, 24)
        font_small = pygame.font.Font(None, 18)

        # Semi-transparent overlay
        overlay = pygame.Surface((self.width, self.height))
        overlay.set_alpha(80)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        # Title
        title: pygame.Surface = font_large.render("CHOOSE YOUR WEAPON", True, (255, 255, 0))
        self.screen.blit(
            title, (self.width // 2 - title.get_width() // 2 + shake_x, 100 + shake_y)
        )

        # Weapon options in boxes
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

        for i, weapon in enumerate(self.weapon_choices):
            y_pos: int = start_y + i * (box_height + spacing)

            # Check if mouse is hovering over this weapon
            mouse_rect = pygame.Rect(x_pos, y_pos, box_width, box_height)
            is_hovered: bool = mouse_rect.collidepoint(self.mouse_x, self.mouse_y)

            # Update selected index if hovered
            if is_hovered:
                self.selected_weapon_index: int = i

            # Draw box background - highlight if selected or hovered
            is_selected: bool = i == self.selected_weapon_index
            if is_selected or is_hovered:
                box_color: tuple[Literal[100], Literal[100], Literal[100]] | tuple[Literal[75], Literal[75], Literal[75]] = (100, 100, 100) if is_selected else (75, 75, 75)
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
            name_text: pygame.Surface = font_medium.render(weapon["name"], True, (255, 255, 0))
            self.screen.blit(name_text, (x_pos + 20 + shake_x, y_pos + 10 + shake_y))

            # Weapon description
            desc_text: pygame.Surface = font_small.render(weapon["description"], True, (200, 200, 200))
            self.screen.blit(desc_text, (x_pos + 20 + shake_x, y_pos + 40 + shake_y))

        # Instructions
        instructions: pygame.Surface = font_medium.render(
            "Click weapon or press 1-3 to select, or use mouse wheel",
            True,
            (200, 200, 200),
        )
        self.screen.blit(
            instructions,
            (
                self.width // 2 - instructions.get_width() // 2 + shake_x,
                self.height - 100 + shake_y,
            ),
        )

    def draw_upgrade_selection(self, shake_x=0, shake_y=0) -> None:
        """Draw upgrade selection screen"""
        font_large = pygame.font.Font(None, 36)
        font_medium = pygame.font.Font(None, 24)
        font_small = pygame.font.Font(None, 18)

        # Semi-transparent overlay
        overlay = pygame.Surface((self.width, self.height))
        overlay.set_alpha(128)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        # Title
        title: pygame.Surface = font_large.render("LEVEL UP - CHOOSE UPGRADE", True, (255, 255, 0))
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
                self.selected_upgrade_index: int = i

            # Draw box background - highlight if selected or hovered
            is_selected: bool = i == self.selected_upgrade_index
            if is_selected or is_hovered:
                box_color: tuple[Literal[100], Literal[100], Literal[100]] | tuple[Literal[75], Literal[75], Literal[75]] = (100, 100, 100) if is_selected else (75, 75, 75)
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
            name_text: pygame.Surface = font_medium.render(upgrade["name"], True, (255, 255, 0))
            self.screen.blit(name_text, (x_pos + 20 + shake_x, y_pos + 10 + shake_y))

            # Upgrade description
            desc_text: pygame.Surface = font_small.render(upgrade["description"], True, (200, 200, 200))
            self.screen.blit(desc_text, (x_pos + 20 + shake_x, y_pos + 40 + shake_y))

        # Instructions
        instructions: pygame.Surface = font_medium.render(
            "Click upgrade or press 1-3 to select, or use mouse wheel",
            True,
            (200, 200, 200),
        )
        self.screen.blit(
            instructions,
            (
                self.width // 2 - instructions.get_width() // 2 + shake_x,
                self.height - 100 + shake_y,
            ),
        )

    def handle_events(self) -> None:
        for event in pygame.event.get():
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

    def handle_keydown(self, key):
        if self.showing_stage_menu:
            if key == pygame.K_p:
                self.select_stage("prologo")
            elif key == pygame.K_l:
                # Open the Limbo second menu (keyboard shortcut)
                self.showing_limbo_menu = True
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
        elif self.showing_game_over:
            # When the game-over overlay is active:
            # Enter/Space restarts the current stage, ESC returns to the main menu.
            if key == pygame.K_RETURN or key == pygame.K_SPACE:
                logger.info("Restart requested via Enter/Space from game over screen")
                if self.selected_stage:
                    self.showing_game_over = False
                    self.paused = False
                    self.game_over_alpha = 0
                    self.select_stage(self.selected_stage)
                else:
                    self.show_stage_menu()
            elif key == pygame.K_ESCAPE:
                logger.info("Escape pressed on game over screen; returning to menu")
                self.show_stage_menu()
        elif self.awaiting_weapon_choice:
            if key == pygame.K_1 and len(self.weapon_choices) > 0:
                self.apply_weapon(self.weapon_choices[0]["id"])
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
            elif key == pygame.K_DOWN:
                self.selected_weapon_index: int = min(
                    max(0, len(self.weapon_choices) - 1), self.selected_weapon_index + 1
                )
            elif key == pygame.K_RETURN or key == pygame.K_SPACE:
                self.apply_weapon(self.weapon_choices[self.selected_weapon_index]["id"])
            elif key == pygame.K_ESCAPE and not self.is_initial_weapon_choice:
                # Cancel weapon selection and resume game (only for non-initial choices)
                self.awaiting_weapon_choice = False
                self.paused = False
        elif self.awaiting_upgrade:
            if key == pygame.K_1 and len(self.upgrade_choices) > 0:
                self.apply_upgrade(self.upgrade_choices[0])
            elif key == pygame.K_2 and len(self.upgrade_choices) > 1:
                self.apply_upgrade(self.upgrade_choices[1])
            elif key == pygame.K_3 and len(self.upgrade_choices) > 2:
                self.apply_upgrade(self.upgrade_choices[2])
            elif key == pygame.K_UP:
                self.selected_upgrade_index: int = max(0, self.selected_upgrade_index - 1)
            elif key == pygame.K_DOWN:
                self.selected_upgrade_index: int = min(
                    max(0, len(self.upgrade_choices) - 1),
                    self.selected_upgrade_index + 1,
                )
            elif key == pygame.K_RETURN or key == pygame.K_SPACE:
                self.apply_upgrade(self.upgrade_choices[self.selected_upgrade_index])
            elif key == pygame.K_ESCAPE:
                # Cancel upgrade selection and resume game
                self.awaiting_upgrade = False
                self.paused = False
        elif self.paused:
            if key == pygame.K_UP or key == pygame.K_w:
                self.pause_menu_option: int = max(0, self.pause_menu_option - 1)
            elif key == pygame.K_DOWN or key == pygame.K_s:
                self.pause_menu_option: int = min(2, self.pause_menu_option + 1)
            elif key == pygame.K_RETURN or key == pygame.K_SPACE:
                self.execute_pause_option()
        else:
            if key == pygame.K_ESCAPE:
                self.toggle_pause()

    def handle_mouse_click(self, pos, button=1):
        """Handle mouse clicks in menus"""
        # Handle mouse wheel buttons for navigation
        if button == 4:  # Wheel up
            if self.awaiting_weapon_choice and self.weapon_choices:
                self.selected_weapon_index: int = max(0, self.selected_weapon_index - 1)
                return
            elif self.awaiting_upgrade and self.upgrade_choices:
                self.selected_upgrade_index: int = max(0, self.selected_upgrade_index - 1)
                return
        elif button == 5:  # Wheel down
            if self.awaiting_weapon_choice and self.weapon_choices:
                self.selected_weapon_index: int = min(
                    len(self.weapon_choices) - 1, self.selected_weapon_index + 1
                )
                return
            elif self.awaiting_upgrade and self.upgrade_choices:
                self.selected_upgrade_index: int = min(
                    len(self.upgrade_choices) - 1, self.selected_upgrade_index + 1
                )
                return
        if self.showing_stage_menu:
            # Check stage selection buttons
            prologo_rect = pygame.Rect(
                self.width // 2 - 100, self.height // 2 - 50, 200, 40
            )
            limbo_rect = pygame.Rect(
                self.width // 2 - 100, self.height // 2 + 10, 200, 40
            )
            upgrades_rect = pygame.Rect(
                self.width // 2 - 125, self.height // 2 + 70, 250, 35
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
                    self.select_stage("limbo")
                elif limbo2_rect.collidepoint(pos):
                    self.select_stage("limbo_2")
                elif limbo3_rect.collidepoint(pos):
                    self.select_stage("limbo_3")
                elif back_rect.collidepoint(pos):
                    self.showing_limbo_menu = False
            else:
                if prologo_rect.collidepoint(pos):
                    self.select_stage("prologo")
                elif limbo_rect.collidepoint(pos):
                    # Open the limbo submenu (second menu)
                    self.showing_limbo_menu = True
                elif upgrades_rect.collidepoint(pos):
                    self.show_permanent_upgrades()
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

            for stat in stat_configs:
                # Check if click is on the stat name area
                name_rect = pygame.Rect(self.width // 2 - 100, stat["y"], 100, 30)
                if name_rect.collidepoint(pos):
                    if (
                        button == 1 and self.permanent_stats[stat["key"]] < 10
                    ):  # Left click to upgrade
                        self.permanent_stats[stat["key"]] += 1
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
                        self.show_centered_message(
                            f"{stat['name']} downgraded to level {self.permanent_stats[stat['key']]}!",
                            120,
                            stat["color"],
                            24,
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
            # Pause menu options
            options_y_start: int = self.height // 2 - 20
            option_height = 40
            for i in range(3):
                option_y: int = options_y_start + i * option_height
                # Check if click is within a reasonable area around the text
                if (
                    option_y - 20 <= pos[1] <= option_y + 20
                    and self.width // 2 - 150 <= pos[0] <= self.width // 2 + 150
                ):
                    self.pause_menu_option: int = i
                    self.execute_pause_option()
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
                {"x": 520, "y": 80},
                {"x": 640, "y": 60},
                {"x": 760, "y": 80},
            ]
        else:  # limbo
            self.buildings = []  # No buildings in limbo

        # Generate stage-specific features
        if str(stage).startswith("limbo"):
            self.generate_dead_trees()
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
            # For Limbo, show initial weapon choice before countdown
            self.is_initial_weapon_choice = True
            self.awaiting_weapon_choice = True
            self.weapon_choices = self.generate_initial_weapon_choices()
            self.selected_weapon_index = 0
            # Do not start countdown yet

        # Start 3-second countdown before gameplay begins (unless initial weapon choice)
        if not self.is_initial_weapon_choice:
            self.stage_start_countdown = 3  # 3 seconds
            self.stage_start_timer: int = self.fps  # 1 second in frames
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

        # Reset multipliers (apply permanent upgrades)
        self.damage_multiplier = 1.0
        self.fire_rate_multiplier = 1.0
        self.projectile_size_multiplier = 1.0
        self.damage_reduction_multiplier: float = 1.0 - (
            self.permanent_stats["structure"] * 0.05
        )

        # Reset game state
        self.enemies.empty()
        self.projectiles.empty()
        self.enemy_projectiles.empty()
        self.bosses.empty()

        self.wave = 0
        self.wave_time = 0
        self.enemy_spawn_timer = 0
        self.enemy_spawn_rate: int = self.base_spawn_rate
        self.spawn_accel_timer: int = 20 * self.fps
        self.time_elapsed = 0
        self.big_enemy_timer: int = 12 * self.fps
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
        self.statue_projectiles = []
        self.statue_cooldown_left = 0
        self.statue_cooldown_right = 0
        self.is_initial_weapon_choice = False

        # Reset player stats (keep permanent upgrades)
        self.player.xp = 0
        self.player.level = 1
        self.player.xp_to_next_level = 100
        self.player.damage_multiplier = 1.0 + (self.permanent_stats["power"] * 0.1)
        self.player.fire_rate_multiplier = 1.0 + (
            self.permanent_stats["adrenaline"] * 0.1
        )
        self.player.projectile_size_multiplier = 1.0
        self.player.damage_reduction_multiplier = 1.0 - (
            self.permanent_stats["structure"] * 0.05
        )
        self.player.max_health = 100 + (self.permanent_stats["vigor"] * 10)
        self.player.health = self.player.max_health

        # Reset game level/XP tracking
        self.player_level = 1
        self.player_xp = 0
        self.xp_to_next_level = 100
        self.score = 0
        self.difficulty_multiplier = 1.0

        self.upgrade_levels: Dict[str, int] = {
            "damage": 0,
            "fire_rate": 0,
            "max_health": 0,
            "projectile_size": 0,
            "armor": 0,
        }

        self.paused = False
        self.awaiting_upgrade = False
        self.awaiting_weapon_choice = False

    def reset_game(self) -> None:
        """Reset everything including permanent upgrades"""
        self.reset_run()
        self.selected_stage = None
        self.permanent_stats: Dict[str, int] = {"power": 0, "vigor": 0, "adrenaline": 0, "structure": 0}
        self.showing_stage_menu = True

    def toggle_pause(self) -> None:
        """Toggle pause state"""
        if not self.awaiting_upgrade and not self.showing_prologo_end:
            self.paused: bool = not self.paused
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
        elif self.pause_menu_option == 1:  # Restart Run
            self.reset_run()
        elif self.pause_menu_option == 2:  # Quit to Menu
            self.reset_game()

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
                    self.stage_start_timer: int = self.fps  # Reset for next second
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
        self.awaiting_weapon_choice: bool = self.game_state.awaiting_weapon_choice
        self.weapon_choices = self.game_state.weapon_choices
        self.awaiting_upgrade: bool = self.game_state.awaiting_upgrade
        self.upgrade_choices = self.game_state.upgrade_choices
        self.selected_weapon_index: int = self.game_state.selected_weapon_index
        self.selected_upgrade_index: int = self.game_state.selected_upgrade_index

        if self.paused or self.awaiting_upgrade or self.awaiting_weapon_choice:
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

        # Check for level up
        if self.player_xp >= self.xp_to_next_level:
            self.trigger_level_up()

        # Auto-attack system
        self.update_weapon_firing()

        # Update game objects
        self.projectiles.update()
        self.enemy_projectiles.update()

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

        # Update enemy spawning
        self.update_enemy_spawning()

        # Update wave progression
        self.update_wave_progression()

        # Update prologo events
        if self.selected_stage == "prologo":
            self.update_prologo_events()

        # Handle collisions
        self.handle_collisions()

        # Update statue weapons (Limbo)
        if self.is_limbo_stage():
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
                    self.player_anim_frame: int = (self.player_anim_frame + 1) % 8
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
                effective_burst_fire_rate: int = max(
                    1, int(self.burst_fire_rate / self.fire_rate_multiplier)
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
                        self.burst_cooldown: int = effective_burst_pause
                        self.burst_count = 0

        # Special weapons
        if "shotgun" in self.player_weapons and self.shotgun_cooldown_timer <= 0:
            self.fire_shotgun(aim_vel_x, aim_vel_y)
            slevel: int = self.weapon_levels.get("shotgun", 0)
            reductions: int = slevel // 2
            base_cd = 1.5
            cd_sec: float = max(0.4, base_cd - reductions * 0.15)
            self.shotgun_cooldown_timer = int(cd_sec * self.fps)

        if "spear" in self.player_weapons and self.spear_cooldown_timer <= 0:
            self.fire_spear(aim_vel_x, aim_vel_y)
            slevel: int = self.weapon_levels.get("spear", 0)
            base_cd = 0.6
            red: float = 0.06 * slevel
            cd: float = max(0.15, base_cd - red)
            self.spear_cooldown_timer = int(cd * self.fps)

        # Update weapon cooldowns
        if self.shotgun_cooldown_timer > 0:
            self.shotgun_cooldown_timer -= 1
        if self.spear_cooldown_timer > 0:
            self.spear_cooldown_timer -= 1

    def fire_basic_weapon(self, aim_x, aim_y) -> None:
        """Fire basic projectile"""
        base_damage = int(self.player_damage * self.damage_multiplier)

        # Apply beast weapon damage bonus (+5% per level)
        beast_level: int = self.weapon_levels.get("beast", 0)
        if beast_level > 0:
            base_damage = int(base_damage * (1 + beast_level * 0.05))

        base_radius = int(8 * self.projectile_size_multiplier)

        projectile: Projectile[int, Any, Any, Any] = Projectile(
            self.player.x,
            self.player.y,
            aim_x,
            aim_y,
            damage=base_damage,
            radius=base_radius,
        )
        self.projectiles.add(projectile)

    def fire_shotgun(self, aim_x, aim_y) -> None:
        """Fire shotgun pellets"""
        slevel: int = self.weapon_levels.get("shotgun", 0)
        pellets: int = 4 + (slevel // 2)
        spread_deg = 12
        angle: float = math.atan2(aim_y, aim_x)

        for p in range(pellets):
            if pellets > 1:
                a: float = angle + math.radians(
                    -spread_deg / 2 + p * (spread_deg / (pellets - 1))
                )
            else:
                a: float = angle
            vx: float = math.cos(a) * 500
            vy: float = math.sin(a) * 500

            base_damage = int(self.player_damage * self.damage_multiplier * 0.55)
            base_radius = int(5 * self.projectile_size_multiplier * 0.9)

            pellet: Projectile[int, Any, float, float] = Projectile(
                self.player.x,
                self.player.y,
                vx,
                vy,
                damage=base_damage,
                radius=base_radius,
                weapon_type="shotgun",
            )
            self.projectiles.add(pellet)

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

        spear: Projectile[int, Any, int, int] = Projectile(
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

    def update_orbitals(self) -> None:
        """Update orbital sentinels"""
        for orb in self.orbitals:
            orb["angle"] += 0.06
            ox = self.player.x + math.cos(orb["angle"]) * orb["dist"]
            oy = self.player.y + math.sin(orb["angle"]) * orb["dist"]
            orb["x"] = ox
            orb["y"] = oy
            orb["cooldown"] -= 1

            if orb["cooldown"] <= 0:
                # Auto-aim at closest enemy or mouse
                if self.enemies:
                    target = min(
                        self.enemies.sprites(),
                        key=lambda e: math.hypot(e.x - ox, e.y - oy),
                    )
                    dx = target.x - ox
                    dy = target.y - oy
                else:
                    dx = self.mouse_x - ox
                    dy = self.mouse_y - oy

                dist: float = math.hypot(dx, dy)
                if dist > 0:
                    speed = 420
                    vel_x = (dx / dist) * speed
                    vel_y = (dy / dist) * speed
                else:
                    vel_x = 0
                    vel_y = -420

                projectile: Projectile[Any, Any, Any | int, Any | int] = Projectile(
                    ox,
                    oy,
                    vel_x,
                    vel_y,
                    damage=int(8 * self.damage_multiplier),
                    radius=int(4 * self.projectile_size_multiplier),
                    source="orbital",
                )
                self.projectiles.add(projectile)

                min_cd, max_cd = self._orbital_cooldown_range()
                orb["cooldown"] = random.randint(min_cd, max_cd)

    def _orbital_cooldown_range(self) -> tuple[int, int]:
        """Return cooldown range for orbitals based on level"""
        olevel: int = self.weapon_levels.get("orbital", 0)
        reductions: int = olevel // 2
        base_min = 40
        base_max = 100
        min_cd: int = max(10, base_min - reductions * 6)
        max_cd: int = max(min_cd + 5, base_max - reductions * 12)
        return int(min_cd), int(max_cd)

    def create_orbitals(self) -> None:
        """Initialize orbital sentinels around player"""
        import math
        import random

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

        # Left statue
        self.statue_cooldown_left -= 1
        if self.statue_cooldown_left <= 0:
            enemies_list = _enemy_iter()
            if enemies_list:
                statue_x, statue_y = 320, 530
                closest_enemy = min(
                    enemies_list,
                    key=lambda e: math.hypot(
                        _pos(e)[0] - statue_x, _pos(e)[1] - statue_y
                    ),
                )
                cx, cy = _pos(closest_enemy)
                dx = cx - statue_x
                dy = cy - statue_y
                dist: float = math.hypot(dx, dy)
                if dist > 0:
                    speed = 320
                    # Add inaccuracy to aiming
                    angle: float = math.atan2(dy, dx) + random.uniform(-0.5, 0.5)
                    self.statue_projectiles.append(
                        {
                            "x": statue_x,
                            "y": statue_y,
                            "vel_x": math.cos(angle) * speed,
                            "vel_y": math.sin(angle) * speed,
                            "radius": 6,
                            "damage": 5,
                        }
                    )
                    self.statue_cooldown_left: int = self.statue_fire_rate

        # Right statue
        self.statue_cooldown_right -= 1
        if self.statue_cooldown_right <= 0:
            enemies_list = _enemy_iter()
            if enemies_list:
                statue_x, statue_y = 960, 530
                closest_enemy = min(
                    enemies_list,
                    key=lambda e: math.hypot(
                        _pos(e)[0] - statue_x, _pos(e)[1] - statue_y
                    ),
                )
                cx, cy = _pos(closest_enemy)
                dx = cx - statue_x
                dy = cy - statue_y
                dist: float = math.hypot(dx, dy)
                if dist > 0:
                    speed = 320
                    # Add inaccuracy to aiming
                    angle: float = math.atan2(dy, dx) + random.uniform(-0.5, 0.5)
                    self.statue_projectiles.append(
                        {
                            "x": statue_x,
                            "y": statue_y,
                            "vel_x": math.cos(angle) * speed,
                            "vel_y": math.sin(angle) * speed,
                            "radius": 6,
                            "damage": 5,
                        }
                    )
                    self.statue_cooldown_right: int = self.statue_fire_rate

        # Update statue projectiles with homing
        for proj in self.statue_projectiles[:]:
            enemies_list = _enemy_iter()
            if enemies_list:
                closest_enemy = min(
                    enemies_list,
                    key=lambda e: math.hypot(
                        _pos(e)[0] - proj["x"], _pos(e)[1] - proj["y"]
                    ),
                )
                cx, cy = _pos(closest_enemy)
                dx = cx - proj["x"]
                dy = cy - proj["y"]
                dist: float = math.hypot(dx, dy)

                if dist > 0:
                    target_vel_x = (dx / dist) * 320
                    target_vel_y = (dy / dist) * 320

                    # Calculate angle difference between current velocity and target direction
                    current_speed: float = math.hypot(proj["vel_x"], proj["vel_y"])
                    if current_speed > 0:
                        current_angle: float = math.atan2(proj["vel_y"], proj["vel_x"])
                        target_angle: float = math.atan2(target_vel_y, target_vel_x)
                        angle_diff: float = abs(target_angle - current_angle)
                        # Normalize angle difference to 0-180 degrees
                        angle_diff: float = min(angle_diff, 2 * math.pi - angle_diff)
                        angle_diff_degrees: float = math.degrees(angle_diff)

                        # Only apply homing if angle difference is <= 90 degrees
                        if angle_diff_degrees <= 90:
                            homing_strength = 0.1
                            proj["vel_x"] = (
                                proj["vel_x"] * (1 - homing_strength)
                                + target_vel_x * homing_strength
                            )
                            proj["vel_y"] = (
                                proj["vel_y"] * (1 - homing_strength)
                                + target_vel_y * homing_strength
                            )
                        # If angle difference > 90°, don't apply homing - let projectile miss
                    else:
                        # If projectile is not moving, apply full correction
                        homing_strength = 0.8
                        proj["vel_x"] = (
                            proj["vel_x"] * (1 - homing_strength)
                            + target_vel_x * homing_strength
                        )
                        proj["vel_y"] = (
                            proj["vel_y"] * (1 - homing_strength)
                            + target_vel_y * homing_strength
                        )

            proj["x"] += proj["vel_x"] / self.fps
            proj["y"] += proj["vel_y"] / self.fps

    def handle_collisions(self) -> None:
        """Handle all collision detection"""

        # Projectiles hit enemies
        for projectile in list(self.projectiles):
            # Support both Group (pygame) and list-of-dicts used in tests
            if hasattr(self.enemies, "sprites"):
                hit_enemies: List[Any] = pygame.sprite.spritecollide(
                    projectile, self.enemies, False
                )
                for enemy in hit_enemies:
                    enemy.take_damage(projectile.damage)
                    if projectile.pierce_all:
                        pass  # Spear pierces through everything
                    elif projectile.pierce_count > 0:
                        projectile.pierce_count -= 1
                        if projectile.pierce_count <= 0:
                            projectile.kill()
                    else:
                        projectile.kill()
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
            else:
                # Enemies stored as simple dicts
                for enemy in list(self.enemies):
                    dx = enemy.get("x", 0) - projectile.x
                    dy = enemy.get("y", 0) - projectile.y
                    r = enemy.get("radius", 12) + getattr(projectile, "radius", 0)
                    if dx * dx + dy * dy <= r * r:
                        # Hit
                        enemy["health"] -= projectile.damage
                        if projectile.pierce_all:
                            pass
                        elif getattr(projectile, "pierce_count", 0) > 0:
                            projectile.pierce_count -= 1
                            if projectile.pierce_count <= 0:
                                projectile.kill()
                        else:
                            projectile.kill()
                        if enemy["health"] <= 0:
                            self.score += int(
                                enemy.get("max_health", 10)
                                * 18
                                * self.difficulty_multiplier
                            )
                            type_xp: Dict[str, int] = {
                                "weak": 10,
                                "normal": 16,
                                "strong": 25,
                                "giant": 50,
                                "angel": 22,
                            }
                            base_xp: int = type_xp.get(enemy.get("type"), 12)
                            self.player_xp += base_xp
                            if self.player_xp >= self.xp_to_next_level:
                                self.trigger_level_up()
                            try:
                                self.enemies.remove(enemy)
                            except ValueError:
                                pass
                        break

            # Projectiles hit bosses
            hit_bosses: List[Any] = pygame.sprite.spritecollide(projectile, self.bosses, False)
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
                if projectile.pierce_all:
                    pass  # Spear pierces through everything
                elif projectile.pierce_count > 0:
                    projectile.pierce_count -= 1
                    if projectile.pierce_count <= 0:
                        projectile.kill()
                else:
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

        # Statue projectiles hit enemies
        for proj in self.statue_projectiles[:]:
            enemies_list = self._enemies_iter()
            if not enemies_list:
                continue
            closest_enemy = min(
                enemies_list,
                key=lambda e: math.hypot(
                    self._enemy_pos(e)[0] - proj["x"], self._enemy_pos(e)[1] - proj["y"]
                ),
            )
            cx, cy = self._enemy_pos(closest_enemy)
            r = self._enemy_radius(closest_enemy)
            dist: float = math.hypot(cx - proj["x"], cy - proj["y"])
            if dist < r + proj["radius"]:
                # Apply damage
                if isinstance(closest_enemy, dict):
                    closest_enemy["health"] -= proj["damage"]
                    if closest_enemy["health"] <= 0:
                        try:
                            self.enemies.remove(closest_enemy)
                        except Exception:
                            pass
                else:
                    closest_enemy.take_damage(proj["damage"])
                try:
                    self.statue_projectiles.remove(proj)
                except ValueError:
                    pass

        # Enemy projectiles hit player
        hit_projectiles: List[Any] = pygame.sprite.spritecollide(
            self.player, self.enemy_projectiles, False
        )
        for projectile in hit_projectiles:
            actual_damage = projectile.damage * self.damage_reduction_multiplier
            self.player.take_damage(actual_damage)
            self.shake_timer = 8
            projectile.kill()

        # Enemies hit player
        if hasattr(self.enemies, "sprites"):
            hit_enemies: List[Any] = pygame.sprite.spritecollide(self.player, self.enemies, False)
            for enemy in hit_enemies:
                actual_damage = (
                    enemy.damage / self.fps
                ) * self.damage_reduction_multiplier
                self.player.take_damage(actual_damage)
                contact_damage_to_enemy: float = 2.0 / self.fps
                enemy.take_damage(contact_damage_to_enemy)
                if self.time_elapsed % 10 == 0:
                    self.shake_timer = 6

                # Armor spine effect
                if self.upgrade_levels.get("armor", 0) > 0:
                    reflect_ratio: float = min(0.3 * self.upgrade_levels["armor"], 0.9)
                    reflected = actual_damage * reflect_ratio
                    enemy.take_damage(reflected)
                    # Visual effect: draw red spikes from player to enemy
                    if enemy.get("spine_timer", 0) <= 0:
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
                    contact_damage_to_enemy: float = 2.0 / self.fps
                    if isinstance(enemy, dict):
                        enemy["health"] -= contact_damage_to_enemy
                        if enemy["health"] <= 0:
                            try:
                                self.enemies.remove(enemy)
                            except Exception:
                                pass
                    else:
                        enemy.take_damage(contact_damage_to_enemy)
                    if self.time_elapsed % 10 == 0:
                        self.shake_timer = 6

                    # Armor spine effect (best-effort for dicts)
                    if self.upgrade_levels.get("armor", 0) > 0:
                        reflect_ratio: float = min(0.3 * self.upgrade_levels["armor"], 0.9)
                        reflected = actual_damage * reflect_ratio
                        if not isinstance(enemy, dict):
                            enemy.take_damage(reflected)
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
        hit_bosses: List[Any] = pygame.sprite.spritecollide(self.player, self.bosses, False)
        for boss in hit_bosses:
            contact_damage = (boss.damage / self.fps) * self.damage_reduction_multiplier
            self.player.take_damage(contact_damage)
            if self.time_elapsed % 10 == 0:
                self.shake_timer = 6

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
                    dist: float = math.hypot(ex - ox, ey - oy)
                    if dist < enemy.radius + 6:  # orbital radius is 6
                        enemy.take_damage(1.0 / self.fps)  # slight damage per frame
                for boss in self.bosses:
                    dist: float = math.hypot(boss.x - ox, boss.y - oy)
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
        # XP curve: 100 * (1.2 ^ (level - 1))
        self.xp_to_next_level = int(100 * (1.2 ** (self.player_level - 1)))

        # Levels 3 and 6: weapon choices if player has room for more weapons
        if (
            self.player_level in [3, 6]
            and len(self.player_weapons) < self.max_extra_weapons
        ):
            self.awaiting_upgrade = False
            self.awaiting_weapon_choice = True
            self.weapon_choices = self.generate_weapon_choices()

            # From level 6 onwards, also include weapon upgrades in weapon choices
            if self.player_level >= 6:
                weapon_upgrades = self.generate_weapon_upgrade_choices()
                if weapon_upgrades:
                    # Add weapon upgrades to the weapon choices
                    self.weapon_choices.extend(weapon_upgrades)
                    # Re-shuffle to mix weapons and upgrades
                    import random

                    random.shuffle(self.weapon_choices)
                    # Limit to exactly 3 choices if we have more
                    self.weapon_choices = self.weapon_choices[:3]

            self.selected_weapon_index = 0
            self.paused = True
        elif self.player_level in [3, 6]:
            # If player already has max weapons, show upgrades instead
            self.awaiting_weapon_choice = False
            self.awaiting_upgrade = True
            self.upgrade_choices = self.generate_upgrade_choices()
            self.selected_upgrade_index = 0
            self.paused = True
        else:
            # Levels 1, 2, 4, 5, 7+: normal upgrades + base weapon upgrade + weapon upgrades when available
            self.awaiting_weapon_choice = False
            self.awaiting_upgrade = True
            self.upgrade_choices = self.generate_upgrade_choices()
            self.selected_upgrade_index = 0
            self.paused = True

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
            # Return empty list for now - weapon upgrades can be added later
            return []

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
            import random

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

        # Randomly select 3 different upgrades, guaranteeing at least 1 weapon upgrade if available
        choices = []
        used_ids = set()

        # Guarantee at least one weapon upgrade when available
        weapon_upgrade_options = [u for u in processed_upgrades if "upgrade" in u["id"]]
        if weapon_upgrade_options:
            forced = random.choice(weapon_upgrade_options)
            choices.append(forced)
            used_ids.add(forced["id"])

        # Fill remaining slots with random upgrades
        remaining_upgrades = [u for u in processed_upgrades if u["id"] not in used_ids]
        while len(choices) < 3 and remaining_upgrades:
            upgrade = random.choice(remaining_upgrades)
            choices.append(upgrade)
            remaining_upgrades.remove(upgrade)

        return choices

    def generate_initial_weapon_choices(self):
        """Generate initial weapon choices for Limbo"""
        initial_weapons: List[Dict[str, str]] = [
            {
                "id": "shotgun",
                "name": "Shotgun",
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
        ]

        # Convert to the format expected
        initial_weapons = [
            {
                "id": weapon["id"],
                "name": weapon["name"],
                "description": weapon["description"],
                "apply": lambda w=weapon["id"]: self.apply_weapon(w),
            }
            for weapon in initial_weapons
        ]

        import random

        return random.sample(initial_weapons, min(3, len(initial_weapons)))

    def generate_weapon_choices(self):
        """Generate weapon choices"""

        # Define weapon definitions inline
        def get_weapon_definitions() -> List[Dict[str, str]]:
            return [
                {
                    "id": "shotgun",
                    "name": "Shotgun",
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
            ]

        all_weapons: List[Dict[str, str]] = get_weapon_definitions()

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
        available_weapons = [
            w for w in all_weapons if w["id"] not in self.player_weapons
        ]

        # If player already has max weapons, don't offer new weapons
        if len(self.player_weapons) >= self.max_extra_weapons:
            available_weapons = []

        # If no new weapons available, return empty list
        if not available_weapons:
            return []

        # Return up to 3 weapon choices
        import random

        return random.sample(available_weapons, min(3, len(available_weapons)))

    def generate_weapon_upgrade_choices(self):
        """Generate weapon upgrade choices for owned weapons"""
        weapon_upgrades = []

        # Generate upgrades for each owned weapon
        for weapon_id in self.player_weapons:
            current_level: int = self.weapon_levels.get(weapon_id, 1)
            max_level: Any | int = getattr(self, "max_weapon_level", 5)  # Default max level

            if current_level < max_level:
                weapon_names: Dict[str, str] = {
                    "shotgun": "Hellgun",
                    "orbital": "Orbitals",
                    "spear": "Spear",
                    "beast": "The number of the beast",
                }

                weapon_name: str = weapon_names.get(weapon_id, weapon_id.title())
                upgrade_name: str = f"{weapon_name} Lv.{current_level + 1}"
                upgrade_desc: str = f"Upgrade {weapon_name} to level {current_level + 1}"

                weapon_upgrades.append(
                    {
                        "id": f"{weapon_id}_upgrade",
                        "name": upgrade_name,
                        "description": upgrade_desc,
                        "weapon_id": weapon_id,
                    }
                )

        # Return up to 2 weapon upgrade choices
        import random

        return random.sample(weapon_upgrades, min(2, len(weapon_upgrades)))

    def apply_weapon(self, weapon_id) -> None:
        """Apply a weapon or weapon upgrade"""
        # Check if this is a weapon upgrade
        if weapon_id.endswith("_upgrade"):
            base_weapon_id = weapon_id.replace("_upgrade", "")
            if base_weapon_id in self.player_weapons:
                # Upgrade existing weapon
                current_level: int = self.weapon_levels.get(base_weapon_id, 1)
                self.weapon_levels[base_weapon_id] = current_level + 1

                # Special handling for orbital upgrades
                if base_weapon_id == "orbital":
                    self.orbital_count: int = self.weapon_levels["orbital"] // 2 + 3
                    self.create_orbitals()

                print(
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

        # Resume the game
        self.awaiting_weapon_choice = False
        self.paused = False

        # If this was initial weapon choice for Limbo, start the countdown
        if self.is_initial_weapon_choice:
            self.is_initial_weapon_choice = False
            self.stage_start_countdown = 3  # 3 seconds
            self.stage_start_timer: int = self.fps  # 1 second in frames

    def update_enemy_spawning(self) -> None:
        """Handle enemy spawning logic"""
        self.enemy_spawn_timer -= 1
        if self.enemy_spawn_timer <= 0:
            self.spawn_enemy()
            if self.selected_stage == "prologo":
                self.enemy_spawn_timer = int(self.enemy_spawn_rate * 1.5)
            else:
                self.enemy_spawn_timer: int = self.enemy_spawn_rate

        # Periodic big enemy spawn
        self.big_enemy_timer -= 1
        if self.big_enemy_timer <= 0 and not self.big_spawned_this_wave:
            self.spawn_big_enemy()
            self.big_spawned_this_wave = True
            if self.wave >= 6:
                self.big_enemy_timer: int = self.big_enemy_fast_interval
            else:
                self.big_enemy_timer: int = 12 * self.fps

        # Spawn acceleration
        self.spawn_accel_timer -= 1
        if self.spawn_accel_timer <= 0:
            self.enemy_spawn_rate: int = max(
                self.spawn_min_rate, int(self.enemy_spawn_rate * 0.99)
            )
            self.spawn_accel_timer: int = 20 * self.fps

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
            self.wave_boss_spawned = False
            self.big_spawned_this_wave = False

            # Adjust spawn rate based on wave
            if self.wave < self.spawn_ramp_start_wave:
                self.enemy_spawn_rate: int = max(
                    self.spawn_min_rate,
                    int(self.base_spawn_rate - self.wave * self.spawn_ramp_slope_pre),
                )
            else:
                self.enemy_spawn_rate: int = max(
                    self.spawn_min_rate,
                    int(self.base_spawn_rate - self.wave * self.spawn_ramp_slope_post),
                )

            self.difficulty_multiplier: float = 1.0 + (self.wave * 0.12)

        # Spawn boss at 28 seconds
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
        if self.wave_time >= 12 and not self.big_spawned_this_wave:
            self.spawn_big_enemy()
            self.big_spawned_this_wave = True

    def update_prologo_events(self) -> None:
        """Handle special Prologo events"""
        # Final boss at 2:55 (175 seconds)
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
                    print(
                        "[PROLOGO] Final boss reached full health — triggering lightning strike"
                    )
                    self.prologo_lightning_strike = True
                    self.generate_lightning()
                    print(
                        "[PROLOGO] Lightning points generated:",
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
                next_x: int = max(0, min(self.width, next_x))
                next_y: int = max(0, min(self.height, next_y))
                pts.append((next_x, next_y))
                prev_x: int = next_x

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
        self.game_over_alpha: int = min(255, self.game_over_fade_speed)

        # Stop any screen shake immediately so the overlay is stable
        self.shake_timer = 0

        # Do not schedule an automatic return to menu; require explicit key press
        logger.info("Game over triggered; showing game over screen (awaiting keypress)")

    def update_game_over(self) -> None:
        """Progress the game-over fade animation."""
        try:
            if self.game_over_alpha < 255:
                self.game_over_alpha: int = min(
                    255, self.game_over_alpha + self.game_over_fade_speed
                )
        except Exception as e:
            logger.exception("Error in update_game_over: %s", e)

    def draw_game_over(self, shake_x=0, shake_y=0) -> None:
        """Draw the persistent game over screen overlay with fade."""
        try:
            # Overlay surface with per-pixel alpha to allow fade-in effect
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((40, 20, 45, int(self.game_over_alpha)))
            self.screen.blit(overlay, (0, 0))

            # Title (fade text by setting per-surface alpha)
            font_large = pygame.font.Font(None, 64)
            # Dark red for the FALL title for stronger contrast
            title_surf: pygame.Surface = font_large.render("FALL", True, (139, 0, 0))
            title_surf.set_alpha(int(self.game_over_alpha))
            self.screen.blit(
                title_surf,
                (
                    self.width // 2 - title_surf.get_width() // 2 + shake_x,
                    200 + shake_y,
                ),
            )

            # Stats
            font_medium = pygame.font.Font(None, 24)
            stats: List[str] = [
                f"Final Score: {int(self.score)}",
                f"Wave: {self.wave}",
                f"Level: {self.player.level}",
            ]

            for i, stat in enumerate(stats):
                text_surf: pygame.Surface = font_medium.render(stat, True, (255, 255, 255))
                text_surf.set_alpha(int(self.game_over_alpha))
                self.screen.blit(
                    text_surf,
                    (
                        self.width // 2 - text_surf.get_width() // 2 + shake_x,
                        320 + i * 40 + shake_y,
                    ),
                )

            # Prompt
            # Main prompt: Enter to restart, ESC to return to menu
            # Moved down for more spacing and changed to light yellow
            prompt: pygame.Surface = font_medium.render(
                "Press ENTER to restart, ESC to return to menu", True, (255, 255, 153)
            )
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
        text: pygame.Surface = font_large.render("THE FALL", True, (139, 0, 0))
        self.screen.blit(text, (self.width // 2 - text.get_width() // 2, 150))

        # Description
        font_medium = pygame.font.Font(None, 18)
        text: pygame.Surface = font_medium.render(
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
            text: pygame.Surface = font_medium.render(stat, True, (255, 255, 255))
            self.screen.blit(
                text, (self.width // 2 - text.get_width() // 2, 300 + i * 40)
            )

        # Continue prompt
        text: pygame.Surface = font_medium.render(
            "Press ENTER to continue to Limbo", True, (100, 200, 255)
        )
        self.screen.blit(text, (self.width // 2 - text.get_width() // 2, 500))

        text: pygame.Surface = font_medium.render("or ESC to return to menu", True, (150, 150, 150))
        self.screen.blit(text, (self.width // 2 - text.get_width() // 2, 540))

    def spawn_enemy(self) -> None:
        # Spawn from top of screen
        x: int = random.randint(0, self.width)
        y = -20

        # Choose enemy type based on wave and random chance
        rand: float = random.random()
        if self.wave >= 5 and rand < 0.05:  # 5% chance for giant after wave 5
            enemy_type = "giant"
            health: float = 80 * self.difficulty_multiplier
            speed = 70
        elif self.wave >= 3 and rand < 0.15:  # 15% chance for strong after wave 3
            enemy_type = "strong"
            health: float = 35 * self.difficulty_multiplier
            speed = 90
        elif rand < 0.3:  # 30% chance for normal
            enemy_type = "normal"
            health: float = 25 * self.difficulty_multiplier
            speed = 100
        elif rand < 0.5:  # 20% chance for angel
            enemy_type = "angel"
            health: float = 20 * self.difficulty_multiplier
            speed = 120
        else:  # 25% chance for weak
            enemy_type = "weak"
            health: float = 15 * self.difficulty_multiplier
            speed = 110

        enemy: Enemy[int, int] = Enemy(x, y, enemy_type, health, speed)
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
        """Spawn a giant enemy at random edge"""
        side: str = random.choice(["left", "right", "top"])

        if side == "left":
            x = -30
            y: int = random.randint(0, self.height)
        elif side == "right":
            x: int = self.width + 30
            y: int = random.randint(0, self.height)
        else:  # top
            x: int = random.randint(0, self.width)
            y = -30

        enemy_type = "giant"
        health: float = 100 * self.difficulty_multiplier
        speed = 60
        enemy: Enemy[int, int] = Enemy(x, y, enemy_type, health, speed)
        if hasattr(self.enemies, "add"):
            self.enemies.add(enemy)
        else:
            self.enemies.append(enemy)

    def spawn_big_enemy(self) -> None:
        """Spawn a big enemy (giant)"""
        x: int = random.randint(0, self.width)
        y = -30

        enemy_type = "giant"
        health: float = 100 * self.difficulty_multiplier
        speed = 60
        enemy: Enemy[int, int] = Enemy(x, y, enemy_type, health, speed)
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
                    y = building["y"]
                else:  # No buildings (limbo), spawn at random top position
                    x: int = random.randint(100, self.width - 100)
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
                    speed = 75
                elif etype == "normal":
                    enemy_type = "normal"
                    health = int(25 * self.difficulty_multiplier * 1.1)
                    speed = 50
                elif etype == "strong":
                    enemy_type = "strong"
                    health = int(45 * self.difficulty_multiplier * 1.1)
                    speed = 38
                else:  # angel
                    enemy_type = "angel"
                    health = int(30 * self.difficulty_multiplier * 1.1)
                    speed = 70

                enemy: Enemy[int, int] = Enemy(rx, ry, enemy_type, health, speed)
                self.enemies.add(enemy)
        except Exception as e:
            logger.exception("Error spawning reinforcements: %s", e)
            import traceback

            traceback.print_exc()

    def spawn_boss(self, boss_type) -> None:
        """Spawn a boss of the specified type"""
        # Spawn boss at top center
        x: int = self.width // 2
        y = -50

        if boss_type == "final":
            enemy_type = "boss_final"
            health: float = 1000 * self.difficulty_multiplier
            speed = 18
        elif boss_type == "big":
            enemy_type = "boss_big"
            health: float = 600 * self.difficulty_multiplier
            speed = 16
        else:  # mid
            enemy_type = "boss_medium"
            health: float = 300 * self.difficulty_multiplier
            speed = 60

        boss: Enemy[int, int] = Enemy(x, y, enemy_type, health, speed)
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
            upgrade: Dict[str, Any] = self.upgrade_choices[upgrade]

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
