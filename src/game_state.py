import random
import logging
from typing import Any

logger: logging.Logger = logging.getLogger(__name__)

class GameStateManager:
    def __init__(self, game) -> None:
        self.game: Any = game

        # Wave management
        self.wave = 0
        self.wave_time = 0
        self.wave_duration = 30  # 30 seconds per wave
        self.wave_boss_spawned = False
        self.big_spawned_this_wave = False

        # Level and XP management
        self.player_level = 1
        self.player_xp = 0
        self.xp_to_next_level = 100

        # Score and difficulty
        self.score = 0
        self.difficulty_multiplier = 1.0

        # Weapon system
        self.player_weapons = []
        self.weapon_levels = {}
        self.max_weapon_level = 6

        # Upgrade system
        self.upgrade_levels: dict[str, int] = {
            "damage": 0,
            "max_health": 0,
            "armor": 0,
            "speed": 0,
            "cooldown": 0,
        }

        # Selection screens
        self.awaiting_weapon_choice = False
        self.awaiting_upgrade = False
        self.weapon_choice_index = 0
        self.upgrade_choice_index = 0
        self.pause_menu_index = 0

        # Weapon and upgrade choices
        self.weapon_choices = []
        self.upgrade_choices = []

        # Stage management
        self.selected_stage = "limbo"  # Default stage

        # Messages
        self.center_messages = []

        # Special effects
        self.selected_stage = "limbo"  # Default stage
        self.prologo_final_boss_spawned = False
        self.prologo_final_boss_defeated = False
        self.prologo_final_boss_immortal = False
        self.prologo_lightning_timer = 0
        self.prologo_lightning_strike = False
        self.lightning_points = []
        self.showing_prologo_end = False

        # Game state
        self.paused = False
        self.time_elapsed = 0

    def update(self) -> None:
        """Update game state logic"""
        if not self.paused:
            self.time_elapsed += 1 / self.game.fps

            # Update wave progression
            self.update_wave_progression()

            # Check for level ups
            self.check_level_up()

            # Check for weapon/upgrade selections
            self.check_for_selections()

    def update_wave_progression(self) -> None:
        """Handle wave timing and progression"""
        # Update wave time
        self.wave_time = self.time_elapsed % self.wave_duration

        # Check for wave completion
        if (
            self.game.frame_count % int(self.wave_duration * self.game.fps) == 0
            and self.game.frame_count > 0
        ):
            self.advance_wave()

        # Update difficulty multiplier
        self.difficulty_multiplier: float = 1.0 + (self.wave * 0.12)

    def advance_wave(self) -> None:
        """Advance to the next wave"""
        self.wave += 1

        # Reset wave-specific flags
        self.wave_boss_spawned = False
        self.big_spawned_this_wave = False

        # Ramp spawn rate: gentler early, steeper after configured ramp wave
        if self.wave < 3:  # spawn_ramp_start_wave
            self.game.enemy_manager.enemy_spawn_rate = max(
                30, int(72 - self.wave * 3)
            )  # base_spawn_rate - wave * slope_pre
        else:
            self.game.enemy_manager.enemy_spawn_rate = max(
                30, int(72 - self.wave * 6)
            )  # base_spawn_rate - wave * slope_post

        # Show wave message
        self.add_center_message(
            f"Wave {self.wave}", 120, "#ffff00", ("Arial", 24, "bold")
        )

    def check_level_up(self) -> None:
        """Check if player should level up"""
        if self.player_xp >= self.xp_to_next_level:
            self.level_up()

    def level_up(self) -> None:
        """Handle player level up"""
        self.player_xp -= self.xp_to_next_level
        self.player_level += 1

        # Calculate new XP requirement
        self.xp_to_next_level = int(100 * (1.2 ** (self.player_level - 1)))

        # Show level up message
        self.add_center_message(
            f"Level {self.player_level}!", 120, "#ffd700", ("Arial", 20, "bold")
        )

        # Check if weapon or upgrade selection should be shown
        if self.player_level % 3 == 0:
            self.show_weapon_choice()
        else:
            self.show_upgrade_choice()

    def check_for_selections(self) -> None:
        """Check if selections should be shown"""
        # Weapon choice every 3 levels
        if (
            self.player_level % 3 == 0
            and not self.awaiting_weapon_choice
            and not self.awaiting_upgrade
        ):
            if (self.player_level >= 3 and len(self.player_weapons) < 2) or (
                self.player_level >= 6 and len(self.player_weapons) < 3
            ):
                self.show_weapon_choice()

        # Upgrade choice for other levels
        elif not self.awaiting_weapon_choice and not self.awaiting_upgrade:
            if self.player_level > 1 and self.player_level % 3 != 0:
                self.show_upgrade_choice()

    def show_weapon_choice(self) -> None:
        """Show weapon selection screen"""
        self.awaiting_weapon_choice = True
        self.weapon_choices = self.generate_weapon_choices()
        self.weapon_choice_index = 0

    def show_upgrade_choice(self) -> None:
        """Show upgrade selection screen"""
        self.awaiting_upgrade = True
        self.upgrade_choices = self.generate_upgrade_choices()
        self.upgrade_choice_index = 0

    def select_weapon(self, index) -> None:
        """Apply selected weapon choice"""
        if 0 <= index < len(self.weapon_choices):
            weapon = self.weapon_choices[index]
            weapon_id = weapon["id"]

            if weapon_id.startswith("acquire_"):
                # Acquire new weapon
                actual_weapon = weapon_id.replace("acquire_", "")
                if actual_weapon not in self.player_weapons:
                    self.player_weapons.append(actual_weapon)
                    self.weapon_levels[actual_weapon] = 1
                    self.add_center_message(
                        f"Acquired {weapon['name']}!",
                        120,
                        "#00ff00",
                        ("Arial", 16, "bold"),
                    )

                    # Special handling for orbital acquisition
                    if actual_weapon == "orbital":
                        self.game.orbital_count = 3
                        self.game.create_orbitals()
            else:
                # Upgrade existing weapon
                weapon_name = weapon_id.replace("_upgrade", "")
                if weapon_name in self.weapon_levels:
                    self.weapon_levels[weapon_name] += 1
                    self.add_center_message(
                        f"{weapon['name']} upgraded!",
                        120,
                        "#00ff00",
                        ("Arial", 16, "bold"),
                    )

                    # Special handling for orbital upgrades
                    if weapon_name == "orbital":
                        self.game.orbital_count = (
                            self.weapon_levels["orbital"] // 2 + 3
                        )  # 3 orbitals at level 1, +1 every 2 levels
                        self.game.create_orbitals()

            # Reset selection state
            self.awaiting_weapon_choice = False
            self.weapon_choices = []

    def select_upgrade(self, index) -> None:
        """Apply selected upgrade"""
        if 0 <= index < len(self.upgrade_choices):
            upgrade = self.upgrade_choices[index]
            upgrade_id = upgrade["id"]

            # Apply the upgrade
            if "apply" in upgrade:
                try:
                    upgrade["apply"]()
                except Exception as e:
                    logger.exception("Upgrade apply error: %s", e)

            # Update upgrade levels
            if upgrade_id in self.upgrade_levels:
                self.upgrade_levels[upgrade_id] += 1

            # Show upgrade message
            self.add_center_message(
                f"{upgrade['name']} acquired!", 120, "#00ff00", ("Arial", 16, "bold")
            )

            # Reset selection state
            self.awaiting_upgrade = False
            self.upgrade_choices = []

    def generate_weapon_choices(self):
        """Generate weapon choices for selection"""
        choices = []

        # Offer weapon acquisitions if player has fewer than 3 weapons
        available_weapons: list[str] = ["shotgun", "orbital", "spear", "beast"]
        unowned_weapons: list[str] = [w for w in available_weapons if w not in self.player_weapons]

        if len(self.player_weapons) < 3 and unowned_weapons:
            weapon: str = random.choice(unowned_weapons)
            weapon_names: dict[str, str] = {
                "shotgun": "Hellgun",
                "orbital": "Orbitals",
                "spear": "Spear",
                "beast": "The number of the beast",
            }
            weapon_descs: dict[str, str] = {
                "shotgun": "Powerful close-range spread weapon",
                "orbital": "Orbiting projectiles around you",
                "spear": "Piercing projectile with chain lightning",
                "beast": "Normal weapon with damage bonuses",
            }
            choices.append(
                {
                    "id": f"acquire_{weapon}",
                    "name": f"Acquire {weapon_names[weapon]}",
                    "description": weapon_descs[weapon],
                }
            )

        # Offer weapon upgrades for owned weapons
        for weapon in self.player_weapons:
            if self.weapon_levels.get(weapon, 0) < self.max_weapon_level:
                weapon_names: dict[str, str] = {
                    "shotgun": "Hellgun",
                    "orbital": "Orbitals",
                    "spear": "Spear",
                    "beast": "The number of the beast",
                }
                choices.append(
                    {
                        "id": f"{weapon}_upgrade",
                        "name": f"{weapon_names[weapon]} Upgrade",
                        "description": f"Upgrade {weapon_names[weapon]} to level {self.weapon_levels[weapon] + 1}",
                    }
                )

        # Ensure we have at least 3 choices
        while len(choices) < 3:
            if choices:
                choices.append(random.choice(choices))
            else:
                # Fallback to a generic damage upgrade
                choices.append(
                    {
                        "id": "damage",
                        "name": "Damage +10%",
                        "description": "Increase damage by 10%",
                    }
                )

        return choices[:3]

    def generate_upgrade_choices(self):
        """Generate upgrade choices"""
        choices = []

        # Stat upgrades
        stat_upgrades = [
            {
                "id": "damage",
                "name": "Damage +15%",
                "description": "Increase damage dealt",
                "apply": lambda: self.apply_damage_upgrade(),
            },
            {
                "id": "max_health",
                "name": "Health +20",
                "description": "Increase maximum health",
                "apply": lambda: self.apply_health_upgrade(),
            },
            {
                "id": "speed",
                "name": "Speed +10%",
                "description": "Move faster",
                "apply": lambda: self.apply_speed_upgrade(),
            },
        ]

        # Add levels to stat upgrades
        for upgrade in stat_upgrades:
            upgrade["level"] = self.upgrade_levels.get(upgrade["id"], 0)
            choices.append(upgrade)

        # Weapon upgrades for owned weapons
        for weapon in self.player_weapons:
            if self.weapon_levels.get(weapon, 0) < self.max_weapon_level:
                weapon_names: dict[str, str] = {
                    "shotgun": "Hellgun",
                    "orbital": "Orbitals",
                    "spear": "Spear",
                }
                choices.append(
                    {
                        "id": f"{weapon}_upgrade",
                        "name": f"{weapon_names[weapon]} Upgrade",
                        "description": f"Upgrade {weapon_names[weapon]}",
                        "apply": lambda w=weapon: self.apply_weapon_upgrade(w),
                        "level": self.weapon_levels.get(weapon, 0),
                    }
                )

        # Randomly select 3 unique choices
        if len(choices) <= 3:
            return choices
        else:
            return random.sample(choices, 3)

    def apply_damage_upgrade(self) -> None:
        """Apply damage upgrade"""
        # This would modify the game's damage multiplier
        pass

    def apply_health_upgrade(self) -> None:
        """Apply health upgrade"""
        # This would increase max health
        pass

    def apply_speed_upgrade(self) -> None:
        """Apply speed upgrade"""
        # This would increase movement speed
        pass

    def apply_weapon_upgrade(self, weapon) -> None:
        """Apply weapon-specific upgrade"""
        if weapon in self.weapon_levels:
            self.weapon_levels[weapon] += 1

    def add_center_message(self, text, frames, color, font) -> None:
        """Add a centered message to display"""
        self.center_messages.append(
            {"text": text, "frames": frames, "color": color, "font": font}
        )

    def update_center_messages(self) -> None:
        """Update center messages (called by UI manager)"""
        for m in self.center_messages[:]:
            m["frames"] -= 1
            if m["frames"] <= 0:
                self.center_messages.remove(m)

    def toggle_pause(self) -> None:
        """Toggle pause state"""
        self.paused: bool = not self.paused

    def add_score(self, points) -> None:
        """Add points to score"""
        self.score += points

    def add_xp(self, xp_amount) -> None:
        """Add XP to player"""
        self.player_xp += xp_amount
