import math
import os
import random
import logging
from typing import Any, Literal

from src.weapons import WEAPON_DEFS
from src.game_constants import WALL_THICKNESS

logger: logging.Logger = logging.getLogger(__name__)

class UIManager:
    def __init__(self, game) -> None:
        self.game: Any = game
        self.canvas = game.canvas
        self.width = game.width
        self.height = game.height

    def draw_ui(self) -> None:
        """Draw all UI elements (HUD, messages, special effects)"""
        # Draw basic HUD
        self.draw_hud()

        # Draw weapon HUD
        self.draw_weapon_hud()

        # Draw special effects
        self.draw_special_effects()

        # Draw selection screens
        if self.game.game_state.awaiting_weapon_choice:
            self.draw_weapon_selection()
        elif self.game.game_state.awaiting_upgrade:
            self.draw_upgrade_selection()
        elif self.game.game_state.paused:
            self.draw_pause_menu()

    def draw_hud(self) -> None:
        """Draw the main HUD elements"""
        # Score
        self.canvas.create_text(
            10,
            10,
            text=f"Score: {int(self.game.game_state.score)}",
            fill="#ffff00",
            font=("Arial", 14),
            anchor="nw",
        )

        # Wave
        self.canvas.create_text(
            10,
            40,
            text=f"Wave: {self.game.game_state.wave}",
            fill="#ff6464",
            font=("Arial", 14),
            anchor="nw",
        )

        # Timer
        minutes = int(self.game.game_state.time_elapsed // 60)
        seconds = int(self.game.game_state.time_elapsed % 60)
        self.canvas.create_text(
            10,
            70,
            text=f"Time: {minutes}:{seconds:02d}",
            fill="#64c8ff",
            font=("Arial", 14),
            anchor="nw",
        )

        # Health
        self.canvas.create_text(
            self.width - 10,
            10,
            text=f"Health: {int(self.game.player.health)}/{int(self.game.player.max_health)}",
            fill="#c86464",
            font=("Arial", 14),
            anchor="ne",
        )

        # Level
        self.canvas.create_text(
            self.width - 10,
            40,
            text=f"Level {self.game.game_state.player_level}",
            fill="#ffd700",
            font=("Arial", 18, "bold"),
            anchor="ne",
        )

        # XP Bar
        self.draw_xp_bar()

        # Center messages
        self.draw_center_messages()

    def draw_xp_bar(self) -> None:
        """Draw the XP progress bar"""
        xp_bar_width = 200
        xp_bar_height = 20
        xp_bar_x = self.width - 210
        xp_bar_y = 65

        # Background
        self.canvas.create_rectangle(
            xp_bar_x,
            xp_bar_y,
            xp_bar_x + xp_bar_width,
            xp_bar_y + xp_bar_height,
            fill="#323232",
            outline="#969696",
            width=2,
        )

        # XP fill
        xp_ratio: float = min(
            1.0, self.game.game_state.player_xp / self.game.game_state.xp_to_next_level
        )
        self.canvas.create_rectangle(
            xp_bar_x,
            xp_bar_y,
            xp_bar_x + xp_bar_width * xp_ratio,
            xp_bar_y + xp_bar_height,
            fill="#64c8ff",
            outline="",
        )

        # XP text
        self.canvas.create_text(
            xp_bar_x + xp_bar_width // 2,
            xp_bar_y + xp_bar_height // 2,
            text=f"{int(self.game.game_state.player_xp)}/{int(self.game.game_state.xp_to_next_level)}",
            fill="#ffffff",
            font=("Arial", 10, "bold"),
        )

    def draw_weapon_hud(self) -> None:
        """Draw the weapon information HUD"""
        hud_x = self.width - 10
        hud_y = 65 + 20 + 12  # After XP bar
        box_w = 170

        # Extra weapons
        if getattr(self.game.game_state, "player_weapons", None):
            # Use centralized weapon names
            name_map: dict[str, str] = {wid: d["name"] for wid, d in WEAPON_DEFS.items()}
            for i, wid in enumerate(self.game.game_state.player_weapons):
                lvl = self.game.game_state.weapon_levels.get(wid, 0)
                display_name: str | None = name_map.get(wid, wid.capitalize())
                display_text: str = f"{display_name} Lv{lvl}"
                y: int = hud_y + i * 18
                # Background box
                self.canvas.create_rectangle(
                    hud_x - box_w,
                    y - 10,
                    hud_x,
                    y + 6,
                    fill="#161616",
                    outline="#444444",
                )
                self.canvas.create_text(
                    hud_x - box_w // 2,
                    y - 3,
                    text=display_text,
                    fill="#c8c8c8",
                    font=("Arial", 10, "bold"),
                )
                # MAX indicator
                if lvl >= getattr(self.game.game_state, "max_weapon_level", 6):
                    self.canvas.create_text(
                        hud_x - 12,
                        y - 3,
                        text="MAX",
                        fill="#ffd700",
                        font=("Arial", 8, "bold"),
                    )

    def draw_center_messages(self) -> None:
        """Draw centered messages with shadows"""
        if getattr(self.game.game_state, "center_messages", None):
            for m in self.game.game_state.center_messages[:]:
                # Shadow for readability
                try:
                    self.canvas.create_text(
                        self.width // 2 + 2,
                        self.height // 2 - 78,
                        text=m["text"],
                        fill="black",
                        font=m["font"],
                    )
                    self.canvas.create_text(
                        self.width // 2,
                        self.height // 2 - 80,
                        text=m["text"],
                        fill=m["color"],
                        font=m["font"],
                    )
                except Exception:
                    pass
                m["frames"] -= 1
                if m["frames"] <= 0:
                    self.game.game_state.center_messages.remove(m)

    def draw_special_effects(self) -> None:
        """Draw special UI effects like lightning and spine effects"""
        # Divine lightning effect
        if (
            self.game.game_state.selected_stage == "prologo"
            and self.game.game_state.prologo_lightning_strike
        ):
            self.draw_lightning_effect()

        # Spine effect (thorns)
        self.draw_spine_effect()

    def draw_lightning_effect(self) -> None:
        """Draw the divine lightning strike effect"""
        # Full screen white flash with pulsing
        flash_alpha: float = abs(math.sin(self.game.frame_count * 0.3))
        if flash_alpha > 0.3:
            self.canvas.create_rectangle(
                0, 0, self.width, self.height, fill="#ffffff", stipple="gray25"
            )

        # Falling light beam from above (replaces bolt)
        t: Any | int = getattr(self.game.game_state, "prologo_lightning_timer", 0)
        pts: Any | None = getattr(self.game.game_state, "lightning_points", None)
        if pts and len(pts) > 0:
            end_x, end_y = pts[-1]
        else:
            end_x = int(getattr(self.game.player, "x", self.width // 2))
            end_y = int(getattr(self.game.player, "y", self.height - 80))
        # Beam fall progress (fast initial fall)
        fall_frames = 30
        progress: float = min(1.0, t / float(fall_frames))
        beam_y = int(end_y * progress)
        # Beam widths scale with progress
        outer_w = int(max(30, 180 * (0.2 + 0.8 * progress)))
        core_w = int(max(6, 40 * progress))
        # Outer glow rectangle (top -> current beam_y)
        self.canvas.create_rectangle(
            end_x - outer_w // 2,
            0,
            end_x + outer_w // 2,
            beam_y,
            fill="#fff8e6",
            outline="",
        )
        # Inner core
        self.canvas.create_rectangle(
            end_x - core_w // 2,
            0,
            end_x + core_w // 2,
            beam_y,
            fill="#ffffe0",
            outline="",
        )
        # Thin bright center line
        self.canvas.create_line(
            end_x,
            0,
            end_x,
            beam_y,
            fill="#fff8b0",
            width=3,
        )
        # Impact explosion (pulsing)
        max_radius = 160
        duration = float(getattr(self.game, "prologo_lightning_duration_frames", 180))
        radius = int(min(max_radius, (t / duration) * max_radius + 8))
        pulse: float = (math.sin(self.game.frame_count * 0.25) + 1) * 0.5
        self.canvas.create_oval(
            end_x - int(radius * 1.1),
            end_y - int(radius * 1.1),
            end_x + int(radius * 1.1),
            end_y + int(radius * 1.1),
            fill="#fff0d8",
            outline="",
        )
        self.canvas.create_oval(
            end_x - int(radius * 0.6 + pulse * 8),
            end_y - int(radius * 0.6 + pulse * 8),
            end_x + int(radius * 0.6 + pulse * 8),
            end_y + int(radius * 0.6 + pulse * 8),
            fill="#ffffe0",
            outline="",
        )

    def draw_spine_effect(self) -> None:
        """Draw the spine/thorns effect on enemies"""
        for enemy in self.game.enemy_manager.enemies:
            if enemy.get("spine_timer", 0) > 0 and "spine_from" in enemy:
                try:
                    ex, ey = enemy["x"], enemy["y"]
                    spine_from = enemy["spine_from"]
                    if (
                        isinstance(spine_from, (list, tuple))
                        and len(spine_from) == 2
                        and all(isinstance(v, (int, float)) for v in spine_from)
                    ):
                        px, py = spine_from
                        # Draw light effect: a few glowing circles between player and enemy
                        for t in [0.25, 0.5, 0.75]:
                            lx = px + (ex - px) * t
                            ly = py + (ey - py) * t
                            r: float = 18 + 6 * random.random()
                            color: str = (
                                "#ffffcc"
                                if self.game.frame_count % 2 == 0
                                else "#fffbe0"
                            )
                            self.canvas.create_oval(
                                lx - r,
                                ly - r,
                                lx + r,
                                ly + r,
                                fill=color,
                                outline="#fff700",
                                width=2,
                            )
                        # Small flash at enemy
                        self.canvas.create_oval(
                            ex - 12,
                            ey - 12,
                            ex + 12,
                            ey + 12,
                            fill="#fffbe0",
                            outline="#fff700",
                            width=3,
                        )
                except Exception as e:
                    print(f"[SPINE EFFECT ERROR] {e}")
                enemy["spine_timer"] -= 1
                if enemy["spine_timer"] <= 0:
                    enemy.pop("spine_from", None)

    def draw_weapon_selection(self) -> None:
        """Draw the weapon selection screen"""
        # Semi-transparent overlay
        self.canvas.create_rectangle(
            0, 0, self.width, self.height, fill="#000000", stipple="gray50"
        )

        # Title
        self.canvas.create_text(
            self.width // 2,
            100,
            text="CHOOSE YOUR WEAPON",
            fill="#ffd700",
            font=("Arial", 24, "bold"),
        )

        # Weapon options
        weapon_options: list[tuple[str, str]] = [
            ("Hellgun", "Powerful close-range spread weapon"),
            ("Orbitals", "Orbiting projectiles around you"),
            ("Spear", "Piercing projectile with chain lightning"),
        ]

        start_y = 200
        spacing = 80

        for i, (name, desc) in enumerate(weapon_options):
            y: int = start_y + i * spacing
            color: str = (
                "#ffffff"
                if i != self.game.game_state.selected_weapon_index
                else "#ffff00"
            )

            # Weapon name
            self.canvas.create_text(
                self.width // 2, y, text=name, fill=color, font=("Arial", 18, "bold")
            )

            # Description
            self.canvas.create_text(
                self.width // 2, y + 25, text=desc, fill="#cccccc", font=("Arial", 12)
            )

            # Selection indicator
            if i == self.game.game_state.selected_weapon_index:
                self.canvas.create_text(
                    self.width // 2 - 150,
                    y,
                    text=">",
                    fill="#ffff00",
                    font=("Arial", 20, "bold"),
                )
                self.canvas.create_text(
                    self.width // 2 + 150,
                    y,
                    text="<",
                    fill="#ffff00",
                    font=("Arial", 20, "bold"),
                )

        # Instructions
        self.canvas.create_text(
            self.width // 2,
            self.height - 100,
            text="Use UP/DOWN to select, ENTER to confirm",
            fill="#888888",
            font=("Arial", 14),
        )

    def draw_upgrade_selection(self) -> None:
        """Draw the upgrade selection screen"""
        # Semi-transparent overlay
        self.canvas.create_rectangle(
            0, 0, self.width, self.height, fill="#000000", stipple="gray50"
        )

        # Title
        self.canvas.create_text(
            self.width // 2,
            100,
            text="CHOOSE YOUR UPGRADE",
            fill="#ffd700",
            font=("Arial", 24, "bold"),
        )

        # Upgrade options
        upgrade_options: list[tuple[str, str]] = [
            ("Health +20", "Increase maximum health"),
            ("Speed +10%", "Move faster"),
            ("Damage +15%", "Deal more damage"),
        ]

        start_y = 200
        spacing = 80

        for i, (name, desc) in enumerate(upgrade_options):
            y: int = start_y + i * spacing
            color: str = (
                "#ffffff"
                if i != self.game.game_state.selected_upgrade_index
                else "#ffff00"
            )

            # Upgrade name
            self.canvas.create_text(
                self.width // 2, y, text=name, fill=color, font=("Arial", 18, "bold")
            )

            # Description
            self.canvas.create_text(
                self.width // 2, y + 25, text=desc, fill="#cccccc", font=("Arial", 12)
            )

            # Selection indicator
            if i == self.game.game_state.selected_upgrade_index:
                self.canvas.create_text(
                    self.width // 2 - 150,
                    y,
                    text=">",
                    fill="#ffff00",
                    font=("Arial", 20, "bold"),
                )
                self.canvas.create_text(
                    self.width // 2 + 150,
                    y,
                    text="<",
                    fill="#ffff00",
                    font=("Arial", 20, "bold"),
                )

        # Instructions
        self.canvas.create_text(
            self.width // 2,
            self.height - 100,
            text="Use UP/DOWN to select, ENTER to confirm",
            fill="#888888",
            font=("Arial", 14),
        )

    def draw_pause_menu(self) -> None:
        """Draw the pause menu"""
        # Semi-transparent overlay
        self.canvas.create_rectangle(
            0, 0, self.width, self.height, fill="#000000", stipple="gray75"
        )

        # Title
        self.canvas.create_text(
            self.width // 2,
            150,
            text="PAUSED",
            fill="#ffffff",
            font=("Arial", 32, "bold"),
        )

        # Menu options
        menu_options: list[str] = ["Resume", "Restart", "Quit"]
        start_y = 250
        spacing = 60

        for i, option in enumerate(menu_options):
            y: int = start_y + i * spacing
            color: str = (
                "#ffffff" if i != self.game.game_state.pause_menu_index else "#ffff00"
            )

            self.canvas.create_text(
                self.width // 2, y, text=option, fill=color, font=("Arial", 20, "bold")
            )

            # Selection indicator
            if i == self.game.game_state.pause_menu_index:
                self.canvas.create_text(
                    self.width // 2 - 120,
                    y,
                    text=">",
                    fill="#ffff00",
                    font=("Arial", 24, "bold"),
                )
                self.canvas.create_text(
                    self.width // 2 + 120,
                    y,
                    text="<",
                    fill="#ffff00",
                    font=("Arial", 24, "bold"),
                )

        # Stats display
        stats_y: int = start_y + len(menu_options) * spacing + 50
        self.canvas.create_text(
            self.width // 2,
            stats_y,
            text="GAME STATISTICS",
            fill="#ffd700",
            font=("Arial", 18, "bold"),
        )

        stats_y += 40
        self.canvas.create_text(
            self.width // 2,
            stats_y,
            text=f"Score: {int(self.game.game_state.score)}",
            fill="#ffff00",
            font=("Arial", 14),
        )
        stats_y += 25
        self.canvas.create_text(
            self.width // 2,
            stats_y,
            text=f"Wave: {self.game.game_state.wave}",
            fill="#ff6464",
            font=("Arial", 14),
        )
        stats_y += 25
        minutes = int(self.game.game_state.time_elapsed // 60)
        seconds = int(self.game.game_state.time_elapsed % 60)
        self.canvas.create_text(
            self.width // 2,
            stats_y,
            text=f"Time: {minutes}:{seconds:02d}",
            fill="#64c8ff",
            font=("Arial", 14),
        )
        stats_y += 25
        self.canvas.create_text(
            self.width // 2,
            stats_y,
            text=f"Level: {self.game.game_state.player_level}",
            fill="#ffd700",
            font=("Arial", 14),
        )

        # Instructions
        self.canvas.create_text(
            self.width // 2,
            self.height - 80,
            text="Use UP/DOWN to select, ENTER to confirm",
            fill="#888888",
            font=("Arial", 14),
        )


class PygameUIManager:
    """A Pygame-specific UI manager which encapsulates all drawing logic previously inside Game."""

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

        # Fill inside battlefield with dark green
        if (
            self.game.selected_stage == "prologo"
            and self.game.left_wall_points
            and self.game.right_wall_points
        ):
            inside_points = (
                self.game.left_wall_points + self.game.right_wall_points[::-1]
            )
            pygame.draw.polygon(
                self.screen,
                (0, 50, 0),
                [(p[0] + shake_x, p[1] + shake_y) for p in inside_points],
            )

        # Fill inside battlefield with dark orange for limbo
        elif (
            self.game.is_limbo_stage()
            and self.game.left_wall_points
            and self.game.right_wall_points
        ):
            inside_points = (
                self.game.left_wall_points + self.game.right_wall_points[::-1]
            )
            pygame.draw.polygon(
                self.screen,
                (100, 50, 0),
                [(p[0] + shake_x, p[1] + shake_y) for p in inside_points],
            )

        # Fill inside battlefield with dark gray for purgatory variants
        elif (
            getattr(self.game, "selected_stage", None)
            and str(self.game.selected_stage).startswith("purgatory")
            and self.game.left_wall_points
            and self.game.right_wall_points
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
                [(p[0] + shake_x, p[1] + shake_y) for p in inside_points],
            )

        # Draw walls
        wall_color = settings["wall_color"]
        wall_thickness = WALL_THICKNESS
        # Left wall
        if self.game.left_wall_points:
            left_wall_exterior = [
                (point[0] - wall_thickness, point[1])
                for point in self.game.left_wall_points
            ]
            left_wall_all = self.game.left_wall_points + left_wall_exterior[::-1]
            pygame.draw.polygon(
                self.screen,
                wall_color,
                [(p[0] + shake_x, p[1] + shake_y) for p in left_wall_all],
            )
        # Right wall
        if self.game.right_wall_points:
            right_wall_exterior = [
                (point[0] + wall_thickness, point[1])
                for point in self.game.right_wall_points
            ]
            right_wall_all = self.game.right_wall_points + right_wall_exterior[::-1]
            pygame.draw.polygon(
                self.screen,
                wall_color,
                [(p[0] + shake_x, p[1] + shake_y) for p in right_wall_all],
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

            labels: List[str] = ["LIMBO 1", "LIMBO 2", "LIMBO 3"]
            for i, label in enumerate(labels):
                rect = pygame.Rect(start_x, start_y + i * spacing, option_w, option_h)
                hovered: bool = rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
                bg: tuple[int, int, int] = (137, 78, 36) if hovered else (107, 58, 26)
                pygame.draw.rect(self.screen, bg, rect)
                pygame.draw.rect(self.screen, (255, 255, 255), rect, 2)
                text: pygame.Surface = font_medium.render(label, True, (255, 255, 255))
                self.screen.blit(
                    text,
                    (
                        self.width // 2 - text.get_width() // 2 + shake_x,
                        start_y + i * spacing + (option_h - text.get_height()) // 2 + shake_y,
                    ),
                )

            back_rect = pygame.Rect(self.width // 2 - 60, start_y + len(labels) * spacing + 10, 120, 36)
            back_hover: bool = back_rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
            back_color: tuple[int, int, int] = (80, 80, 80) if back_hover else (60, 60, 60)
            pygame.draw.rect(self.screen, back_color, back_rect)
            pygame.draw.rect(self.screen, (255, 255, 255), back_rect, 2)
            back_text: pygame.Surface = font_small.render("BACK", True, (255, 255, 255))
            self.screen.blit(
                back_text,
                (self.width // 2 - back_text.get_width() // 2 + shake_x, start_y + len(labels) * spacing + 14 + shake_y),
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

            labels: List[str] = ["PURGATORY 1", "PURGATORY 2", "PURGATORY 3"]
            for i, label in enumerate(labels):
                rect = pygame.Rect(start_x, start_y + i * spacing, option_w, option_h)
                hovered: bool = rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
                bg: tuple[int, int, int] = (137, 78, 136) if hovered else (107, 58, 106)
                pygame.draw.rect(self.screen, bg, rect)
                pygame.draw.rect(self.screen, (255, 255, 255), rect, 2)
                text: pygame.Surface = font_medium.render(label, True, (255, 255, 255))
                self.screen.blit(
                    text,
                    (
                        self.width // 2 - text.get_width() // 2 + shake_x,
                        start_y + i * spacing + (option_h - text.get_height()) // 2 + shake_y,
                    ),
                )

            back_rect = pygame.Rect(self.width // 2 - 60, start_y + len(labels) * spacing + 10, 120, 36)
            back_hover: bool = back_rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
            back_color: tuple[int, int, int] = (80, 80, 80) if back_hover else (60, 60, 60)
            pygame.draw.rect(self.screen, back_color, back_rect)
            pygame.draw.rect(self.screen, (255, 255, 255), back_rect, 2)
            back_text: pygame.Surface = font_small.render("BACK", True, (255, 255, 255))
            self.screen.blit(
                back_text,
                (self.width // 2 - back_text.get_width() // 2 + shake_x, start_y + len(labels) * spacing + 14 + shake_y),
            )

            try:
                self.game._last_drawn_menu = "purgatory"
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
        prologo_rect = pygame.Rect(self.width // 2 - 100, self.height // 2 - 50, 200, 40)
        prologo_hovered: bool = prologo_rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
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
        limbo_hovered: bool = limbo_rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
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

        # Purgatory main button (opens second menu)
        purgatory_rect = pygame.Rect(self.width // 2 - 100, self.height // 2 + 70, 200, 40)
        purgatory_hovered: bool = purgatory_rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
        purgatory_color: tuple[Literal[137], Literal[78], Literal[136]] | tuple[Literal[107], Literal[58], Literal[106]] = (137, 78, 136) if purgatory_hovered else (107, 58, 106)
        pygame.draw.rect(self.screen, purgatory_color, purgatory_rect)
        pygame.draw.rect(self.screen, (255, 255, 255), purgatory_rect, 2)
        purgatory_text: pygame.Surface = font_medium.render("PURGATORY", True, (255, 255, 255))
        self.screen.blit(
            purgatory_text,
            (
                self.width // 2 - purgatory_text.get_width() // 2 + shake_x,
                self.height // 2 + 80 + shake_y,
            ),
        )

        # Upgrades button moved to bottom of screen to avoid overlap and be more accessible
        upgrades_rect = pygame.Rect(self.width // 2 - 125, max(20, self.height - 80), 250, 35)
        upgrades_hovered: bool = upgrades_rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
        upgrades_bg_color: tuple[Literal[94], Literal[36], Literal[94]] | tuple[Literal[74], Literal[26], Literal[74]] = (
            (94, 36, 94) if upgrades_hovered else (74, 26, 74)
        )  # Lighter purple when hovered
        upgrades_border_color: tuple[Literal[255], Literal[224], Literal[20]] | tuple[Literal[255], Literal[204], Literal[0]] = (
            (255, 224, 20) if upgrades_hovered else (255, 204, 0)
        )  # Brighter gold when hovered
        pygame.draw.rect(self.screen, upgrades_bg_color, upgrades_rect)
        pygame.draw.rect(self.screen, upgrades_border_color, upgrades_rect, 2)
        upgrades_text: pygame.Surface = font_small.render("PERMANENT UPGRADES", True, upgrades_border_color)
        self.screen.blit(
            upgrades_text,
            (self.width // 2 - upgrades_text.get_width() // 2 + shake_x, upgrades_rect.y + (upgrades_rect.height - upgrades_text.get_height()) // 2 + shake_y),
        )

        try:
            self.game._last_drawn_menu = "stage_main"
        except Exception:
            pass

    def draw_permanent_upgrades(self, shake_x=0, shake_y=0) -> None:
        """Draw the permanent upgrades menu (migrated from Game).

        Uses direct pygame fonts to avoid text_cache dependencies during menu overlay draws.
        """
        pygame = self.pygame
        if not self.screen or not pygame:
            return
        font_large = pygame.font.Font(None, 36)
        font_medium = pygame.font.Font(None, 24)
        font_small = pygame.font.Font(None, 18)

        # Title and layout
        left_x: int = self.width // 2 - 420
        title: pygame.Surface = font_large.render("PERMANENT UPGRADES", True, (255, 255, 0))
        self.screen.blit(title, (self.width // 2 - title.get_width() // 2 + shake_x, 40 + shake_y))

        stat_configs = [
            {"name": "POWER", "key": "power", "color": (255, 68, 68), "y": 140},
            {"name": "VIGOR", "key": "vigor", "color": (255, 204, 0), "y": 185},
            {"name": "ADRENALINE", "key": "adrenaline", "color": (170, 68, 255), "y": 230},
            {"name": "STRUCTURE", "key": "structure", "color": (139, 105, 20), "y": 275},
        ]

        for stat in stat_configs:
            name_text = font_medium.render(stat["name"], True, stat["color"])
            self.screen.blit(name_text, (left_x + shake_x, stat["y"] + shake_y))

            value = self.game.permanent_stats.get(stat["key"], 0)
            val_text = font_small.render(f"Level: {value}", True, (255, 255, 255))
            self.screen.blit(val_text, (left_x + 200 + shake_x, stat["y"] + shake_y))

            bar_x = left_x + 120
            bar_y = stat["y"] + 15
            bar_width = 200
            bar_height = 12
            pygame.draw.rect(self.screen, (26, 26, 26), (bar_x + shake_x, bar_y + shake_y, bar_width, bar_height))
            pygame.draw.rect(self.screen, (68, 68, 68), (bar_x + shake_x, bar_y + shake_y, bar_width, bar_height), 1)
            if value > 0:
                fill_width = min(bar_width, (value / 10) * bar_width)
                pygame.draw.rect(self.screen, stat["color"], (bar_x + shake_x, bar_y + shake_y, fill_width, bar_height))

        # Separator & Classic Upgrades section (migrated from legacy Game impl)
        separator_y = 320
        classic_text: pygame.Surface = font_medium.render("CLASSIC UPGRADES", True, (136, 136, 136))
        self.screen.blit(
            classic_text,
            (left_x + shake_x, separator_y + 30 + shake_y),
        )

        # Placeholder boxes for classic upgrades (2 rows of 5)
        box_width = 80
        box_height = 60
        box_spacing = 100
        start_x: int = left_x + box_spacing // 2 - 40

        box_y1: int = separator_y + 60
        for i in range(5):
            box_x = start_x + (i * box_spacing)
            pygame.draw.rect(self.screen, (26, 26, 26), (box_x - box_width // 2 + shake_x, box_y1 + shake_y, box_width, box_height))
            pygame.draw.rect(self.screen, (51, 51, 51), (box_x - box_width // 2 + shake_x, box_y1 + shake_y, box_width, box_height), 1)

        box_y2: int = box_y1 + box_height + 20
        for i in range(5):
            box_x = start_x + (i * box_spacing)
            pygame.draw.rect(self.screen, (26, 26, 26), (box_x - box_width // 2 + shake_x, box_y2 + shake_y, box_width, box_height))
            pygame.draw.rect(self.screen, (51, 51, 51), (box_x - box_width // 2 + shake_x, box_y2 + shake_y, box_width, box_height), 1)

        # Skill trees (FIRE, STORM, ICE) on the right side
        tree_types = [("FIRE", "fire", (255, 68, 68)), ("STORM", "storm", (170, 68, 255)), ("ICE", "ice", (100, 200, 255))]
        tree_box_w = 50
        tree_box_h = 36
        tree_v_spacing = 46
        tree_col_spacing = 120
        tree_base_x: int = left_x + 680
        tree_top_y: int = separator_y - 150

        for col, (label, key_prefix, color) in enumerate(tree_types):
            col_x = tree_base_x + col * tree_col_spacing
            lbl_surf: pygame.Surface = font_small.render(label, True, color)
            self.screen.blit(lbl_surf, (col_x - lbl_surf.get_width() // 2 + shake_x, tree_top_y - 28 + shake_y))

            # Draw simple 3x2 boxes layout similar to legacy view
            inner_col_offset = tree_box_w // 2 + 1
            left_col_x = col_x - inner_col_offset
            right_col_x = col_x + inner_col_offset
            for row in range(3):
                y = tree_top_y + row * tree_v_spacing
                left_rect = (left_col_x - tree_box_w // 2 + shake_x, y + shake_y, tree_box_w, tree_box_h)
                right_rect = (right_col_x - tree_box_w // 2 + shake_x, y + shake_y, tree_box_w, tree_box_h)
                left_bg = color if bool(self.game.permanent_stats.get(f"{key_prefix}_{row+1}", 0)) else (26, 26, 26)
                right_bg = color if bool(self.game.permanent_stats.get(f"{key_prefix}_{4+row}", 0)) else (26, 26, 26)
                left_border = tuple(min(255, c + 20) for c in color) if left_bg != (26, 26, 26) else (51, 51, 51)
                right_border = tuple(min(255, c + 20) for c in color) if right_bg != (26, 26, 26) else (51, 51, 51)
                pygame.draw.rect(self.screen, left_bg, left_rect)
                pygame.draw.rect(self.screen, left_border, left_rect, 1)
                pygame.draw.rect(self.screen, right_bg, right_rect)
                pygame.draw.rect(self.screen, right_border, right_rect, 1)

        # Instructions
        instructions = font_medium.render("Left click to upgrade | Right click to downgrade | ESC to return", True, (200, 200, 200))
        self.screen.blit(instructions, (left_x + shake_x, self.height - 50 + shake_y))

        try:
            self.game._last_drawn_menu = "permanent_upgrades"
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

        title: pygame.Surface = get_text("PAUSED", font_large, (255, 255, 255))
        self.screen.blit(title, (self.width // 2 - title.get_width() // 2 + shake_x, self.height // 2 - 100 + shake_y))

        options = ["Resume", "Restart", "Quit to Menu"]
        option_height = 40
        for i, option in enumerate(options):
            y_pos = self.height // 2 - 20 + i * option_height
            text_width = len(option) * 14
            option_rect = pygame.Rect(self.width // 2 - text_width // 2, y_pos, text_width, option_height)
            is_hovered = option_rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
            if is_hovered:
                self.game.pause_menu_option = i
            is_selected = i == self.game.pause_menu_option
            color = (255, 255, 0) if is_selected else ((200, 200, 0) if is_hovered else (255, 255, 255))
            text = font_medium.render(option, True, color)
            self.screen.blit(text, (self.width // 2 - text.get_width() // 2 + shake_x, y_pos + shake_y))

        try:
            self.game._last_drawn_menu = "pause"
        except Exception:
            pass

    def draw_player_stats(self, shake_x=0, shake_y=0) -> None:
        """Draw the player stats panel (migrated from Game)."""
        pygame = self.pygame
        if not self.screen or not pygame:
            return
        from src.assets.text_cache import get_font, get_text
        font_huge = get_font(48)
        font_medium = get_font(32)
        font_small = get_font(20)

        title = get_text("PLAYER STATS", font_huge, (255, 215, 0))
        self.screen.blit(title, (self.width // 2 - title.get_width() // 2 + shake_x, 60 + shake_y))

        mid_col_x = self.width // 2 - 200
        w_y = 140
        self.screen.blit(get_text("Weapons", font_medium, (255, 215, 0)), (mid_col_x, w_y - 30))
        for i, (name, lvl) in enumerate([(n, self.game.weapon_levels.get(n, 0)) for n in self.game.player_weapons]):
            txt = get_text(f"{name} Lv{lvl}", font_small, (220, 220, 220))
            self.screen.blit(txt, (mid_col_x, w_y + i * 26))

        right_col_x = self.width // 2 + 60
        u_y = 140
        self.screen.blit(get_text("Upgrades", font_medium, (255, 215, 0)), (right_col_x, u_y - 30))
        for i, (k, v) in enumerate(self.game.upgrade_levels.items()):
            txt = get_text(f"{k}: {v}", font_small, (220, 220, 220))
            self.screen.blit(txt, (right_col_x, u_y + i * 26))

        ps_y = 340
        self.screen.blit(get_text("Permanent Stats", font_medium, (255, 215, 0)), (right_col_x, ps_y - 30))
        for i, (k, v) in enumerate(self.game.permanent_stats.items()):
            txt = get_text(f"{k}: {v}", font_small, (220, 220, 220))
            self.screen.blit(txt, (right_col_x, ps_y + i * 26))

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

            # Slimmer demonic statue on top with pitchfork
            statue_base_y: int = y - 10

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
        sig = (sig_left, sig_right, self.width, self.height)
        if getattr(self, "_fog_cache_signature", None) == sig and getattr(self, "_fog_cache", None):
            return  # Cache still valid

        # Build cache
        pygame = self.pygame
        wall_thickness = 40
        num_layers = 5
        base_r, base_g, base_b = 60, 60, 60

        cache: list[pygame.Surface] = []

        for i in range(num_layers):
            opacity: float = (num_layers - i) / num_layers
            layer_offset: int = 250 * (i + 1) // num_layers
            r = int(base_r * (1 - opacity * 0.6))
            g = int(base_g * (1 - opacity * 0.6))
            b = int(base_b * (1 - opacity * 0.6))
            color: tuple[int, int, int] = (r, g, b)

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
                cache.append(fog_surface)
            else:
                cache.append(None)

        self._fog_cache = cache
        self._fog_cache_signature = sig

    def draw_fog(self, shake_x=0, shake_y=0) -> None:
        if not self.game.is_limbo_stage():
            return
        if not self.screen:
            return
        if not self.game.left_wall_points or not self.game.right_wall_points:
            return

        # Ensure cache is built and up-to-date
        try:
            self._build_fog_cache()
        except Exception:
            # If caching fails, fall back to original drawing
            self._fog_cache = None
            self._fog_cache_signature = None

        pygame = self.pygame
        wall_thickness = 40
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
        wall_thickness = 40
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
                self.screen.blit(fog_surface, (0, 0))

    def draw_game_objects(self, shake_x=0, shake_y=0) -> None:
        if not self.screen:
            return
        pygame = self.pygame
        # Draw enemies
        for enemy in self.game.enemies:
            if isinstance(enemy, dict):
                # Dict-based enemies (tests/back-compat) - draw simple circle
                ex = int(enemy.get("x", 0) + shake_x)
                ey = int(enemy.get("y", 0) + shake_y)
                er = int(enemy.get("radius", 12))
                pygame.draw.circle(self.screen, (200, 50, 50), (ex, ey), er)

                # Draw burn status for dict-based enemies
                try:
                    if enemy.get("burn_timer", 0) > 0:
                        # Spawn and update simple burn particles for dict enemies (visual only)
                        flame_y = ey - er - 8
                        try:
                            parts = enemy.setdefault("burn_particles", [])
                            # spawn 2-4 particles (increased visibility)
                            for _ in range(random.randint(2, 4)):
                                parts.append({
                                    "x": ex + random.uniform(-er/2, er/2),
                                    "y": flame_y + random.uniform(-4, 4),
                                    "vx": random.uniform(-30, 30),
                                    "vy": random.uniform(15, 40),
                                    "life": random.randint(18, 44),
                                    "size": random.randint(3, 5),
                                })
                            # update and draw
                            for p in list(parts):
                                p["x"] += p["vx"] / 60
                                p["y"] -= p["vy"] / 60
                                p["vy"] = max(0, p["vy"] - 0.6)
                                p["life"] -= 1
                                # draw particle with alpha based on life
                                try:
                                    surf = pygame.Surface((p["size"] * 2 + 2, p["size"] * 2 + 2), pygame.SRCALPHA)
                                    alpha = max(60, int(255 * (p["life"] / 44)))
                                    pygame.draw.circle(surf, (255, 140, 0, alpha), (p["size"] + 1, p["size"] + 1), p["size"])
                                    self.screen.blit(surf, (int(p["x"] - p["size"]), int(p["y"] - p["size"])) )
                                except Exception:
                                    pass
                                if p["life"] <= 0:
                                    try:
                                        parts.remove(p)
                                    except Exception:
                                        pass
                        except Exception:
                            pass

                        # Draw ice particles for dict enemies
                        try:
                            ice_parts = enemy.get("ice_particles", [])
                            for p in list(ice_parts):
                                p["x"] += p["vx"] / 60
                                p["y"] += p["vy"] / 60
                                p["vy"] += 0.1
                                p["life"] -= 1
                                # draw particle with alpha based on life
                                try:
                                    surf = pygame.Surface((p["size"] * 2 + 2, p["size"] * 2 + 2), pygame.SRCALPHA)
                                    alpha = max(50, int(255 * (p["life"] / 25)))
                                    pygame.draw.circle(surf, (200, 240, 255, alpha), (p["size"] + 1, p["size"] + 1), p["size"])
                                    self.screen.blit(surf, (int(p["x"] - p["size"]), int(p["y"] - p["size"])) )
                                except Exception:
                                    pass
                                if p["life"] <= 0:
                                    try:
                                        ice_parts.remove(p)
                                    except Exception:
                                        pass
                        except Exception:
                            pass

                except Exception:
                    pass
            else:
                enemy.draw(self.screen, shake_x, shake_y)

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
                        surf = pygame.Surface((p.size * 2 + 2, p.size * 2 + 2), pygame.SRCALPHA)
                        alpha = max(60, int(255 * (p.life / 44)))
                        pygame.draw.circle(surf, (255, 140, 0, alpha), (p.size + 1, p.size + 1), p.size)
                        self.screen.blit(surf, (int(p.x + shake_x - p.size), int(p.y + shake_y - p.size)))
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

    def draw_special_effects(self, shake_x=0, shake_y=0) -> None:
        if self.game.selected_stage == "prologo" and self.game.prologo_lightning_strike:
            self.draw_lightning_effect(shake_x, shake_y)
        self.draw_chain_lightning_effects(shake_x, shake_y)
        self.draw_spine_effect(shake_x, shake_y)

    def draw_lightning_effect(self, shake_x=0, shake_y=0):
        pygame = self.pygame
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
            outer_color: tuple[Literal[255], Literal[240], Literal[200], int] = (255, 240, 200, int(150 * (0.5 + progress * 0.5)))
            core_color: tuple[Literal[255], Literal[255], Literal[200], int] = (255, 255, 200, int(220 * (0.3 + progress * 0.7)))
            center_color: tuple[Literal[255], Literal[255], Literal[180], int] = (255, 255, 180, int(255 * progress))
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
                alpha = min(180, int(180 * (timer / 8.0)))  # Max 180 alpha, fade to 0
                
                # Draw jagged lines between consecutive points
                for i in range(len(points) - 1):
                    start_x, start_y = points[i]
                    end_x, end_y = points[i + 1]
                    
                    # Create jagged lightning path
                    lightning_points = self._generate_lightning_path(
                        start_x + shake_x, start_y + shake_y,
                        end_x + shake_x, end_y + shake_y,
                        segments=6, max_offset=8
                    )
                    
                    # Draw the jagged line segments
                    color = (150, 200, 255, alpha)
                    for j in range(len(lightning_points) - 1):
                        pygame.draw.line(
                            self.screen,
                            color,
                            lightning_points[j],
                            lightning_points[j + 1],
                            2
                        )
        except Exception:
            logger.exception("draw_chain_lightning_effects failed")

    def _generate_lightning_path(self, start_x, start_y, end_x, end_y, segments=6, max_offset=8):
        """Generate a jagged lightning path between two points"""
        import math
        import random
        
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
                            color: tuple[Literal[255], Literal[255], Literal[204]] | tuple[Literal[255], Literal[254], Literal[224]] = (
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
            return None
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
        health_text = get_text(f"{int(self.game.player.health)}/{int(self.game.player.max_health)}", small_font, (255, 255, 255))
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
        xp_text = get_text(f"{int(self.game.player_xp)}/{int(self.game.xp_to_next_level)}", small_font, (255, 255, 255))
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
            name_map: Dict[str, str] = {
                "shotgun": "Hellgun",
                "orbital": "Orbitals",
                "spear": "Spear",
                "beast": "The number of the beast",
                "Soul Drain": "Soul Drain",
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

                weapon_text: pygame.Surface = small_font.render(display_text, True, (200, 200, 200))
                self.screen.blit(
                    weapon_text,
                    (
                        hud_x - box_w // 2 - weapon_text.get_width() // 2 + shake_x,
                        y - 8 + shake_y,
                    ),
                )

                # If at max level, add MAX indicator
                if lvl >= getattr(self.game, "max_weapon_level", 6):
                    max_text: pygame.Surface = small_font.render("MAX", True, (255, 215, 0))
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
            except Exception as e:
                logger.exception("Error drawing center message: %s", e)
                # Remove the problematic message
                if msg in self.game.center_messages:
                    self.game.center_messages.remove(msg)
