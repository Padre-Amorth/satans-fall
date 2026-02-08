import math
import random


class UIManager:
    def __init__(self, game):
        self.game = game
        self.canvas = game.canvas
        self.width = game.width
        self.height = game.height

    def draw_ui(self):
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

    def draw_hud(self):
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

    def draw_xp_bar(self):
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
        xp_ratio = min(
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

    def draw_weapon_hud(self):
        """Draw the weapon information HUD"""
        hud_x = self.width - 10
        hud_y = 65 + 20 + 12  # After XP bar
        box_w = 170

        # Extra weapons
        if getattr(self.game.game_state, "player_weapons", None):
            name_map = {
                "shotgun": "Hellgun",
                "orbital": "Orbitals",
                "spear": "Spear",
                "beast": "The number of the beast",
            }
            for i, wid in enumerate(self.game.game_state.player_weapons):
                lvl = self.game.game_state.weapon_levels.get(wid, 0)
                display_name = name_map.get(wid, wid.capitalize())
                display_text = f"{display_name} Lv{lvl}"
                y = hud_y + i * 18
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

    def draw_center_messages(self):
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

    def draw_special_effects(self):
        """Draw special UI effects like lightning and spine effects"""
        # Divine lightning effect
        if (
            self.game.game_state.selected_stage == "prologo"
            and self.game.game_state.prologo_lightning_strike
        ):
            self.draw_lightning_effect()

        # Spine effect (thorns)
        self.draw_spine_effect()

    def draw_lightning_effect(self):
        """Draw the divine lightning strike effect"""
        # Full screen white flash with pulsing
        flash_alpha = abs(math.sin(self.game.frame_count * 0.3))
        if flash_alpha > 0.3:
            self.canvas.create_rectangle(
                0, 0, self.width, self.height, fill="#ffffff", stipple="gray25"
            )

        # Lightning bolt from saved points
        if (
            hasattr(self.game.game_state, "lightning_points")
            and self.game.game_state.lightning_points
        ):
            # Outer glow (blue-white)
            for i in range(len(self.game.game_state.lightning_points) - 1):
                x1, y1 = self.game.game_state.lightning_points[i]
                x2, y2 = self.game.game_state.lightning_points[i + 1]
                self.canvas.create_line(x1, y1, x2, y2, fill="#64c8ff", width=20)
            # Middle layer (bright white)
            for i in range(len(self.game.game_state.lightning_points) - 1):
                x1, y1 = self.game.game_state.lightning_points[i]
                x2, y2 = self.game.game_state.lightning_points[i + 1]
                self.canvas.create_line(x1, y1, x2, y2, fill="#ffffff", width=12)
            # Inner core (electric yellow)
            for i in range(len(self.game.game_state.lightning_points) - 1):
                x1, y1 = self.game.game_state.lightning_points[i]
                x2, y2 = self.game.game_state.lightning_points[i + 1]
                self.canvas.create_line(x1, y1, x2, y2, fill="#ffff00", width=6)
            # Add some branching lightning effects
            if len(self.game.game_state.lightning_points) > 3:
                mid_point = self.game.game_state.lightning_points[
                    len(self.game.game_state.lightning_points) // 2
                ]
                branch_x = mid_point[0] + 40
                branch_y = mid_point[1] + 30
                self.canvas.create_line(
                    mid_point[0],
                    mid_point[1],
                    branch_x,
                    branch_y,
                    fill="#ffffff",
                    width=8,
                )
                self.canvas.create_line(
                    mid_point[0],
                    mid_point[1],
                    branch_x,
                    branch_y,
                    fill="#ffff00",
                    width=4,
                )

    def draw_spine_effect(self):
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
                            r = 18 + 6 * random.random()
                            color = (
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

    def draw_weapon_selection(self):
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
        weapon_options = [
            ("Shotgun", "Powerful close-range spread weapon"),
            ("Orbitals", "Orbiting projectiles around you"),
            ("Spear", "Piercing projectile with chain lightning"),
        ]

        start_y = 200
        spacing = 80

        for i, (name, desc) in enumerate(weapon_options):
            y = start_y + i * spacing
            color = (
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

    def draw_upgrade_selection(self):
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
        upgrade_options = [
            ("Health +20", "Increase maximum health"),
            ("Speed +10%", "Move faster"),
            ("Damage +15%", "Deal more damage"),
        ]

        start_y = 200
        spacing = 80

        for i, (name, desc) in enumerate(upgrade_options):
            y = start_y + i * spacing
            color = (
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

    def draw_pause_menu(self):
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
        menu_options = ["Resume", "Restart", "Quit"]
        start_y = 250
        spacing = 60

        for i, option in enumerate(menu_options):
            y = start_y + i * spacing
            color = (
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
        stats_y = start_y + len(menu_options) * spacing + 50
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

    def __init__(self, game):
        # Defer importing pygame to runtime (helps tests without SDL)
        try:
            import pygame

            self.pygame = pygame
        except Exception:
            self.pygame = None
        self.game = game
        self.screen = getattr(game, "screen", None)
        self.width = getattr(game, "width", 0)
        self.height = getattr(game, "height", 0)

    def draw_game_world(self, shake_x=0, shake_y=0):
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

        # Draw walls
        wall_color = settings["wall_color"]
        wall_thickness = 25
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

    def draw_dead_trees(self, shake_x=0, shake_y=0):
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

    def draw_pedestals(self, shake_x=0, shake_y=0):
        """Draw tall pedestals with demonic statues for Limbo stage"""
        if not self.game.is_limbo_stage():
            if getattr(self.game, "debug", False):
                print("[DEBUG] draw_pedestals: not in limbo")
            return
        pygame = self.pygame
        if getattr(self.game, "debug", False):
            print("[DEBUG] draw_pedestals: drawing pedestals")
        # Two pedestals at the sides of the play area
        pedestals = [
            {"x": 320, "y": 620},  # Left pedestal
            {"x": 960, "y": 620},  # Right pedestal
        ]

        for pedestal in pedestals:
            x = pedestal["x"] + shake_x
            y = pedestal["y"] + shake_y

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
            statue_base_y = y - 10

            # Statue body (slimmer triangular/demonic shape - dark red)
            body_points = [
                (x, statue_base_y - 60),  # Neck point (head connects here)
                (x - 12, statue_base_y - 40),  # Left shoulder (narrower)
                (x - 15, statue_base_y),  # Left base (narrower)
                (x + 15, statue_base_y),  # Right base (narrower)
                (x + 12, statue_base_y - 40),  # Right shoulder (narrower)
            ]
            pygame.draw.polygon(self.screen, (58, 10, 10), body_points)
            pygame.draw.polygon(self.screen, (26, 0, 0), body_points, 2)

            # Head (larger and round)
            head_y = statue_base_y - 70
            head_radius = 15
            pygame.draw.circle(self.screen, (58, 10, 10), (x, head_y), head_radius)
            pygame.draw.circle(self.screen, (26, 0, 0), (x, head_y), head_radius, 2)

            # Larger horns (from head)
            pygame.draw.line(
                self.screen,
                (138, 32, 32),
                (x - 10, head_y - 10),
                (x - 20, head_y - 30),
                4,
            )
            pygame.draw.line(
                self.screen,
                (138, 32, 32),
                (x + 10, head_y - 10),
                (x + 20, head_y - 30),
                4,
            )

            # Glowing eyes (on head)
            pygame.draw.circle(self.screen, (255, 48, 48), (x - 7, head_y), 3)
            pygame.draw.circle(self.screen, (255, 48, 48), (x + 7, head_y), 3)

            # Subtle glow ring around head for visibility
            pygame.draw.circle(
                self.screen, (200, 150, 60), (x, head_y), head_radius + 4, 2
            )

            # Pitchfork in hand
            # Handle (long pole)
            fork_x = x + 20  # Held to the right side
            fork_top_y = statue_base_y - 100
            fork_bottom_y = statue_base_y - 20
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
            left_wing_points = [
                (x - 12, statue_base_y - 40),
                (x - 30, statue_base_y - 45),
                (x - 25, statue_base_y - 30),
            ]
            pygame.draw.polygon(self.screen, (74, 16, 16), left_wing_points)
            pygame.draw.polygon(self.screen, (42, 0, 0), left_wing_points, 1)

            # Right wing (smaller to not interfere with pitchfork)
            right_wing_points = [
                (x + 12, statue_base_y - 40),
                (x + 28, statue_base_y - 45),
                (x + 23, statue_base_y - 30),
            ]
            pygame.draw.polygon(self.screen, (74, 16, 16), right_wing_points)
            pygame.draw.polygon(self.screen, (42, 0, 0), right_wing_points, 1)

    def draw_fog(self, shake_x=0, shake_y=0):
        if not self.game.is_limbo_stage():
            return
        if not self.game.left_wall_points or not self.game.right_wall_points:
            return
        pygame = self.pygame
        wall_thickness = 40
        num_layers = 5
        base_r, base_g, base_b = 60, 60, 60
        for i in range(num_layers):
            opacity = (num_layers - i) / num_layers
            layer_offset = 250 * (i + 1) // num_layers
            r = int(base_r * (1 - opacity * 0.6))
            g = int(base_g * (1 - opacity * 0.6))
            b = int(base_b * (1 - opacity * 0.6))
            color = (r, g, b)
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

    def draw_game_objects(self, shake_x=0, shake_y=0):
        pygame = self.pygame
        # Draw enemies
        for enemy in self.game.enemies:
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

        # Draw statue projectiles (Limbo only)
        for proj in self.game.statue_projectiles:
            # Red outer ring
            pygame.draw.circle(
                self.screen,
                (255, 0, 0),
                (int(proj["x"] + shake_x), int(proj["y"] + shake_y)),
                proj["radius"],
            )
            # Yellow core
            pygame.draw.circle(
                self.screen,
                (255, 255, 0),
                (int(proj["x"] + shake_x), int(proj["y"] + shake_y)),
                proj["radius"] // 2,
            )

        # Draw player
        self.game.player.draw(
            self.screen,
            shake_x,
            shake_y,
            self.game.player_anim_frame,
            self.game.player_is_moving,
        )

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

    def draw_special_effects(self, shake_x=0, shake_y=0):
        pygame = self.pygame
        if self.game.selected_stage == "prologo" and self.game.prologo_lightning_strike:
            self.draw_lightning_effect(shake_x, shake_y)
        self.draw_spine_effect(shake_x, shake_y)

    def draw_lightning_effect(self, shake_x=0, shake_y=0):
        pygame = self.pygame
        try:
            player_x = getattr(self.game.player, "x", self.width // 2)
            player_y = getattr(self.game.player, "y", self.height - 80)
            beam_width = 8
            beam_x = player_x
            pulse_intensity = abs(math.sin(self.game.frame_count * 0.2)) * 0.5 + 0.5
            pygame.draw.line(
                self.screen,
                (255, 255, 200),
                (beam_x + shake_x, 0 + shake_y),
                (beam_x + shake_x, player_y + shake_y),
                beam_width + 12,
            )
        except Exception:
            pass

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
                            r = 18 + 6 * random.random()
                            color = (
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
        """Draw the HUD by delegating to Game's existing HUD implementation."""
        # If the Game still has the original draw_hud implementation, reuse it to
        # avoid duplicating large amounts of drawing code.
        if hasattr(self.game, "draw_hud"):
            return self.game.draw_hud(shake_x, shake_y)
        # Otherwise, do nothing safely
        return None
