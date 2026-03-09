import logging
import random
from typing import Any

from src.balance import (
    BASE_SPAWN_RATE,
    SPAWN_MIN_RATE,
    SPAWN_RAMP_SLOPE_POST,
    SPAWN_RAMP_SLOPE_PRE,
    SPAWN_RAMP_START_WAVE,
    XP_BASE,
    XP_GROWTH,
)
from src.game_constants import HELL_STAGES
from src.weapons import (
    WEAPON_DEFS,
    get_orbital_count,
    get_weapon_definitions,
    get_weapon_upgrade_description,
)

logger: logging.Logger = logging.getLogger(__name__)


class GameStateManager:
    def __init__(self, game) -> None:
        self.game: Any = game

        # Wave management
        self.wave = 0
        self.wave_time = 0
        from src.game_constants import (
            DEFAULT_WAVE_DURATION,
        )

        # duration of each wave in seconds; pulled from constants for
        # consistency so tuning only needs to change one value.
        self.wave_duration = DEFAULT_WAVE_DURATION
        self.wave_boss_spawned = False
        self.big_spawned_this_wave = False

        # Level and XP management
        self.player_level = 1
        self.player_xp = 0
        self.xp_to_next_level = XP_BASE

        # Score and difficulty
        self.score: int = 0
        self.difficulty_multiplier: float = 1.0

        # Weapon system
        self.player_weapons: list[str] = []
        self.weapon_levels: dict[str, int] = {}
        self.max_weapon_level: int = 6

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
        self.awaiting_tower_choice = False
        self.awaiting_upgrade = False
        self.weapon_choice_index = 0
        self.tower_choice_index = 0
        self.upgrade_choice_index = 0
        self.pause_menu_index = 0

        # Weapon, tower and upgrade choices
        self.weapon_choices: list[dict[str, Any]] = []
        self.tower_choices: list[dict[str, Any]] = []
        self.upgrade_choices: list[dict[str, Any]] = []

        # Stage management
        self.selected_stage: str = "limbo"  # Default stage

        # Messages
        self.center_messages: list[dict[str, Any]] = []

        # Special effects
        self.selected_stage = "limbo"  # Default stage
        self.prologo_final_boss_spawned: bool = False
        self.prologo_final_boss_defeated: bool = False
        self.prologo_final_boss_immortal: bool = False
        self.prologo_lightning_timer: int = 0
        self.prologo_lightning_strike: bool = False
        self.lightning_points: list[tuple[int, int]] = []
        self.chain_lightning_effects: list[dict] = (
            []
        )  # List of chain effects with timer and points
        # fire special explosion effects (orange circles)
        self.fire_explosions: list[dict] = []
        self.showing_prologo_end: bool = False

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

        # Update difficulty multiplier using stage‑aware slope helper
        per_wave = self.game.get_difficulty_multiplier_per_wave()
        self.difficulty_multiplier = 1.0 + (self.wave * per_wave)

    def advance_wave(self) -> None:
        """Advance to the next wave"""
        self.wave += 1

        # Reset wave-specific flags
        self.wave_boss_spawned = False
        self.big_spawned_this_wave = False

        # Ramp spawn rate: gentler early, steeper after configured ramp wave
        if self.wave < SPAWN_RAMP_START_WAVE:  # spawn_ramp_start_wave
            rate = max(
                SPAWN_MIN_RATE, int(BASE_SPAWN_RATE - self.wave * SPAWN_RAMP_SLOPE_PRE)
            )  # base_spawn_rate - wave * slope_pre
        else:
            rate = max(
                SPAWN_MIN_RATE, int(BASE_SPAWN_RATE - self.wave * SPAWN_RAMP_SLOPE_POST)
            )  # base_spawn_rate - wave * slope_post
        # apply limbo penalty after computing base rate
        if getattr(self.game, "selected_stage", None) in (
            "limbo",
            "limbo_2",
            "limbo_3",
        ):
            from src.balance import LIMBO_SPAWN_RATE_PENALTY

            rate += LIMBO_SPAWN_RATE_PENALTY
        self.game.enemy_manager.enemy_spawn_rate = rate

        # Show wave message
        self.add_center_message(
            f"Wave {self.wave}", 120, "#dcb414", ("Arial", 24, "bold")
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
        self.xp_to_next_level = int(XP_BASE * (XP_GROWTH ** (self.player_level - 1)))

        # Show level up message
        self.add_center_message(
            f"Level {self.player_level}!", 120, "#dcb414", ("Arial", 20, "bold")
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
                        self.game.orbital_count = get_orbital_count(
                            self.weapon_levels.get("orbital", 1)
                        )
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
        all_weapon_ids = list(WEAPON_DEFS.keys())
        unowned_weapons: list[str] = [
            w for w in all_weapon_ids if w not in self.player_weapons
        ]

        # At player level 6 we must propose 3 new weapons only (no upgrades)
        if getattr(self, "player_level", None) == 6:
            import random

            if unowned_weapons:
                if len(unowned_weapons) >= 3:
                    selected = random.sample(unowned_weapons, 3)
                else:
                    selected = [random.choice(unowned_weapons) for _ in range(3)]
                for weapon in selected:
                    choices.append(
                        {
                            "id": f"acquire_{weapon}",
                            "name": WEAPON_DEFS[weapon]["name"],
                            "description": WEAPON_DEFS[weapon]["description"],
                        }
                    )
            else:
                # No unowned weapons: fallback to sampling any weapons
                selected = [random.choice(all_weapon_ids) for _ in range(3)]
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
            # Attach icon info for any acquired weapons (level-6 special case)
            for c in choices:
                wid = None
                cid = c.get("id", "")
                if cid.startswith("acquire_"):
                    wid = cid.split("acquire_")[-1]
                elif cid.endswith("_upgrade"):
                    wid = cid[: -len("_upgrade")]
                if wid:
                    # use definition icon or default pattern
                    icon = WEAPON_DEFS.get(wid, {}).get("icon")
                    if not icon:
                        icon = f"weapon_{wid.lower()}.png"
                    c["icon"] = icon

        # Offer weapon upgrades for owned weapons
        for weapon in self.player_weapons:
            if self.weapon_levels.get(weapon, 0) < self.max_weapon_level:
                display_name = WEAPON_DEFS.get(weapon, {}).get(
                    "name", weapon.replace("_", " ").title()
                )
                next_level = self.weapon_levels.get(weapon, 0) + 1
                description = get_weapon_upgrade_description(weapon, next_level)
                choices.append(
                    {
                        "id": f"{weapon}_upgrade",
                        "name": f"{display_name} Upgrade",
                        "description": description,
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

        # Final pass: ensure icon metadata accompanies each choice
        for c in choices:
            wid = None
            cid = c.get("id", "")
            if cid.startswith("acquire_"):
                wid = cid.split("acquire_")[-1]
            elif cid.endswith("_upgrade"):
                wid = cid[: -len("_upgrade")]
            if wid:
                c["icon"] = WEAPON_DEFS.get(wid, {}).get("icon")

        return choices[:3]

    def generate_initial_weapon_choices(self):
        """Generate initial weapon choices for stages like Limbo.

        Filter out weapons whose `available_from` requirement is not met by the
        current `selected_stage` (e.g. Purgatory-only weapons are excluded from
        Prologo/Limbo initial choices).
        """
        import random

        # Start from full definitions, then filter by availability for this stage
        defs = get_weapon_definitions()
        filtered: list[dict] = []
        for w in defs:
            wid = w.get("id")
            wdef = WEAPON_DEFS.get(wid, {})

            # Check meta-level requirement first
            required_ml = wdef.get("required_meta_level")
            if required_ml:
                current_ml = self.game.global_progress.get("meta_level", 1)
                if current_ml < required_ml:
                    continue

            available_from = wdef.get("available_from")
            if available_from:
                af = str(available_from).lower()
                if af == "purgatory":
                    # only allow in purgatory / HELL stages
                    if not (
                        self.selected_stage
                        and str(self.selected_stage).startswith(("purgatory", "hell"))
                    ):
                        continue
                elif af == "limbo":
                    # allow in limbo and purgatory but not in prologo
                    if not (
                        self.selected_stage and str(self.selected_stage) != "prologo"
                    ):
                        continue
                elif af == "hell":
                    # only allow in HELL stages (not purgatory)
                    if not (
                        self.selected_stage and str(self.selected_stage) in HELL_STAGES
                    ):
                        continue
            filtered.append(w)

        if not filtered:
            filtered = defs

        choices = random.sample(filtered, min(3, len(filtered)))
        # Include icon key just like the regular weapon choice generator does.
        return [
            {
                "id": c["id"],
                "name": c["name"],
                "description": c["description"],
                "icon": WEAPON_DEFS.get(c["id"], {}).get("icon"),
            }
            for c in choices
        ]

    def show_initial_weapon_choice(self) -> None:
        """Enable initial weapon selection screen and populate choices."""
        self.awaiting_weapon_choice = True
        self.weapon_choices = self.generate_initial_weapon_choices()
        self.weapon_choice_index = 0

    def generate_initial_tower_choices(self) -> list[dict[str, Any]]:
        """Return the three tower choices for Purgatory: Fire, Storm, Ice.

        Descriptions include the current base damage and a short note about the
        secondary effect so players see the actual numbers in the selection UI.
        """
        return [
            {
                "id": "fire",
                "name": "Fire Tower",
                "description": "Burn enemies.",
            },
            {
                "id": "storm",
                "name": "Storm Tower",
                "description": "Chain lightning damage.",
            },
            {
                "id": "ice",
                "name": "Ice Tower",
                "description": "Slow enemies.",
            },
        ]

    def show_initial_tower_choice(self) -> None:
        """Enable initial tower selection screen and populate choices."""
        self.awaiting_tower_choice = True
        self.tower_choices = self.generate_initial_tower_choices()
        self.tower_choice_index = 0

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
        weapon_names: dict[str, str] = {
            "shotgun": "Hellgun",
            "orbital": "Orbitals",
            "spear": "Spear",
            "Flies": "Flies",
            "beast": "The number of the beast",
        }
        for weapon in self.player_weapons:
            if self.weapon_levels.get(weapon, 0) < self.max_weapon_level:
                display_name = weapon_names.get(
                    weapon, weapon.replace("_", " ").title()
                )
                current_level = self.weapon_levels.get(weapon, 0)
                next_level = current_level + 1
                description = self.get_weapon_upgrade_description(weapon, next_level)
                choices.append(
                    {
                        "id": f"{weapon}_upgrade",
                        "name": f"{display_name} Upgrade",
                        "description": description,
                        "apply": lambda w=weapon: self.apply_weapon_upgrade(w),
                        "level": current_level,
                    }
                )

        # Randomly select 3 unique choices
        if len(choices) <= 3:
            return choices
        else:
            return random.sample(choices, 3)

    def get_weapon_upgrade_description(self, weapon, level):
        """Delegate to centralized weapon descriptions."""
        return get_weapon_upgrade_description(weapon, level)

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

    # --- Backwards-compatible aliases for legacy Game field names ---
    @property
    def selected_weapon_index(self):
        return getattr(self, "weapon_choice_index", 0)

    @selected_weapon_index.setter
    def selected_weapon_index(self, v):
        self.weapon_choice_index = v

    @property
    def selected_upgrade_index(self):
        return getattr(self, "upgrade_choice_index", 0)

    @selected_upgrade_index.setter
    def selected_upgrade_index(self, v):
        self.upgrade_choice_index = v

    def toggle_pause(self) -> None:
        """Toggle pause state"""
        self.paused = not self.paused

    def add_score(self, points) -> None:
        """Add points to score via the main Game implementation.

        Delegating ensures that meta-XP awards are not bypassed when code
        interacts with the game state directly.
        """
        try:
            # prefer using Game.add_score so that all side effects (meta XP)
            # are handled in one place
            if hasattr(self, "game") and getattr(self.game, "add_score", None):
                self.game.add_score(points)
                # mirror the value in this state
                self.score = getattr(self.game, "score", self.score)
                return
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        # fallback to previous behavior (multiplier ignored)
        try:
            amt = int(points)
            self.score += amt
            try:
                if (
                    hasattr(self, "game")
                    and getattr(self.game, "score", None) is not None
                ):
                    self.game.score += amt
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def add_xp(self, xp_amount) -> None:
        """Add XP to player"""
        self.player_xp += xp_amount
