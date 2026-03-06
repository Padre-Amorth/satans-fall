"""Upgrade and progression system for weapons and permanent stats."""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Any, Dict, List

from src.balance import PLAYER_BASE_HEALTH, XP_BASE, XP_GROWTH
from src.core.entities.tower import Tower
from src.game_constants import WALL_THICKNESS
from src.weapons import (
    WEAPON_DEFS,
    get_orbital_count,
    get_weapon_definitions,
    get_weapon_upgrade_description,
)

if TYPE_CHECKING:
    from src.game import Game

logger = logging.getLogger(__name__)


class UpgradeSystem:
    """Handles weapon upgrades, permanent stats, and level-up progression."""

    def __init__(self, game: "Game") -> None:
        self.game = game

    def trigger_level_up(self) -> None:
        """Pause game and show upgrade choices"""
        self.game.player_xp -= self.game.xp_to_next_level
        self.game.player_level += 1
        self.game.xp_to_next_level = int(
            XP_BASE * (XP_GROWTH ** (self.game.player_level - 1))
        )

        if self.game.player_level in [3, 6]:
            self.game.awaiting_upgrade = False
            self.game.awaiting_weapon_choice = True
            self.game.weapon_choices = self.generate_weapon_choices()

            if not self.game.weapon_choices:
                self.game.awaiting_weapon_choice = False
                self.game.awaiting_upgrade = True
                self.game.upgrade_choices = self.generate_upgrade_choices()
                self.game.selected_upgrade_index = 0
            else:
                self.game.selected_weapon_index = 0

            self.game.paused = True
        else:
            self.game.awaiting_weapon_choice = False
            self.game.awaiting_upgrade = True
            self.game.upgrade_choices = self.generate_upgrade_choices()
            self.game.selected_upgrade_index = 0
            self.game.paused = True

        try:
            gs: Any | None = getattr(self.game, "game_state", None)
            if gs is not None:
                gs.player_xp = self.game.player_xp
                gs.player_level = self.game.player_level
                gs.xp_to_next_level = self.game.xp_to_next_level
                gs.awaiting_weapon_choice = self.game.awaiting_weapon_choice
                gs.awaiting_upgrade = self.game.awaiting_upgrade
                gs.weapon_choices = (
                    list(self.game.weapon_choices)
                    if hasattr(self.game, "weapon_choices")
                    else []
                )
                gs.upgrade_choices = (
                    list(self.game.upgrade_choices)
                    if hasattr(self.game, "upgrade_choices")
                    else []
                )
                gs.weapon_choice_index = getattr(self.game, "selected_weapon_index", 0)
                gs.upgrade_choice_index = getattr(
                    self.game, "selected_upgrade_index", 0
                )
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def generate_upgrade_choices(self):
        """Generate 3 random upgrade choices of different types"""
        g = self.game

        def get_upgrade_patterns():
            patterns = [
                {
                    "id": "damage",
                    "name": "Damage +10%",
                    "description": "Increase damage by 10%",
                    "apply": lambda g=g: setattr(
                        g, "player_damage", int(g.player_damage * 1.1)
                    ),
                },
                {
                    "id": "fire_rate",
                    "name": "Fire Rate +10%",
                    "description": "Increase fire rate by 10%",
                    "apply": lambda g=g: setattr(
                        g, "fire_rate_multiplier", g.fire_rate_multiplier * 1.1
                    ),
                },
                {
                    "id": "max_health",
                    "name": "Max Health +20",
                    "description": "Increase maximum health by 20",
                    "apply": lambda g=g: (
                        setattr(g.player, "max_health", g.player.max_health + 20),
                        setattr(g.player, "health", g.player.health + 20),
                    ),
                },
                {
                    "id": "projectile_size",
                    "name": "Projectile Size +10%",
                    "description": "Increase projectile size by 10%",
                    "apply": lambda g=g: setattr(
                        g,
                        "projectile_size_multiplier",
                        g.projectile_size_multiplier * 1.1,
                    ),
                },
                {
                    "id": "movement_speed",
                    "name": "Movement Speed +5%",
                    "description": "Increase movement speed by 5%",
                    "apply": lambda g=g: (
                        setattr(g.player, "speed", g.player.speed * 1.05),
                        setattr(g.player, "base_speed", g.player.base_speed * 1.05),
                    ),
                },
                {
                    "id": "health_regen",
                    "name": "Health Regen +1 HP/5s",
                    "description": "Passive health regeneration of 1 HP every 5 seconds",
                    "apply": lambda g=g: (
                        setattr(
                            g.player,
                            "regen_per_5s",
                            getattr(g.player, "regen_per_5s", 0.0) + 1.0,
                        ),
                        setattr(
                            g.player, "regen_timer", getattr(g.player, "regen_timer", 0)
                        ),
                    ),
                },
                {
                    "id": "xp",
                    "name": "XP +10%",
                    "description": "Increase XP gain by 10%",
                    "apply": lambda g=g: setattr(
                        g, "xp_multiplier", getattr(g, "xp_multiplier", 1.0) * 1.1
                    ),
                },
                {
                    "id": "tower_fire_rate",
                    "name": "Tower Fire Rate +10%",
                    "description": "Increase the firing speed of towers by 10%",
                    "apply": lambda g=g: (
                        (
                            setattr(
                                g,
                                "tower_fire_rate_multiplier",
                                {
                                    k: (
                                        getattr(
                                            g, "tower_fire_rate_multiplier", {}
                                        ).get(k, 1.0)
                                        * 1.1
                                    )
                                    for k in ("fire", "storm", "ice")
                                },
                            )
                        ),
                        [
                            setattr(
                                t,
                                "fire_rate",
                                max(
                                    1,
                                    int(
                                        round(
                                            getattr(t, "_base_fire_rate", t.fire_rate)
                                            / getattr(
                                                g, "tower_fire_rate_multiplier", {}
                                            ).get(getattr(t, "tower_type", "fire"), 1.0)
                                        )
                                    ),
                                ),
                            )
                            for t in (
                                getattr(g, "left_tower", None),
                                getattr(g, "right_tower", None),
                            )
                            if t is not None
                        ],
                    ),
                },
                {
                    "id": "armor",
                    "name": "Armor +5%",
                    "description": "Reduce damage taken by 5%",
                    "apply": lambda g=g: setattr(
                        g,
                        "damage_reduction_multiplier",
                        g.damage_reduction_multiplier * 0.95,
                    ),
                },
                {
                    "id": "shield",
                    "name": "SHIELD",
                    "description": "Reduce shield cooldown by 2 seconds (max lvl 5)",
                    "apply": lambda g=g: setattr(
                        g.player,
                        "shield_upgrade_level",
                        getattr(g.player, "shield_upgrade_level", 0) + 1,
                    ),
                },
                {
                    "id": "kill_explosion",
                    "name": "BOOM!",
                    "description": "Every 10 kills: explosion (+50 dmg, +50px range per upgrade)",
                    "apply": lambda g=g: (
                        setattr(g.player, "kill_explosion_enabled", True),
                        setattr(
                            g.player,
                            "kill_explosion_upgrades",
                            getattr(g.player, "kill_explosion_upgrades", 0) + 1,
                        ),
                    ),
                },
            ]

            # Filter out shield upgrade if already at max level (5) OR not available in this stage
            try:
                shield_level = getattr(g.player, "shield_upgrade_level", 0)
                if shield_level >= 5:
                    patterns = [p for p in patterns if p.get("id") != "shield"]
                else:
                    # Shield only available from Limbo onwards
                    stage = getattr(g, "selected_stage", None)
                    if stage == "prologo":
                        patterns = [p for p in patterns if p.get("id") != "shield"]
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

            try:
                stage = getattr(g, "selected_stage", None)
                # Projectile Size only available in Hell
                if not (stage and str(stage).startswith("hell")):
                    patterns = [p for p in patterns if p.get("id") != "projectile_size"]
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

            try:
                stage = getattr(g, "selected_stage", None)
                if not (
                    stage
                    and (
                        str(stage).startswith("purgatory")
                        or str(stage).startswith("hell")
                    )
                ):
                    patterns = [p for p in patterns if p.get("id") != "tower_fire_rate"]
                    patterns = [p for p in patterns if p.get("id") != "kill_explosion"]
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

            try:
                if random.random() > 0.33:
                    patterns = [p for p in patterns if p.get("id") != "xp"]
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

            return patterns

        def get_weapon_upgrade_patterns(game):
            weapon_upgrades = []
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
                        "skullboom": "SkullBoom",
                        "beast": "The number of the beast",
                    }
                    weapon_name: str = weapon_names.get(weapon_id, weapon_id.title())
                    upgrade_name: str = f"{weapon_name} Lv.{current_level + 1}"
                    upgrade_desc: str = get_weapon_upgrade_description(
                        weapon_id, current_level + 1
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

        upgrade_groups = {}
        for upgrade in all_upgrades:
            upgrade_id = upgrade["id"]
            if upgrade_id not in upgrade_groups:
                upgrade_groups[upgrade_id] = []
            upgrade_groups[upgrade_id].append(upgrade)

        processed_upgrades = []
        for upgrade_id, upgrades in upgrade_groups.items():
            selected_upgrade = random.choice(upgrades)
            processed_upgrades.append(
                {
                    "id": selected_upgrade["id"],
                    "name": selected_upgrade["name"],
                    "description": selected_upgrade["description"],
                    "apply": lambda u=selected_upgrade: u["apply"](),
                }
            )

        weapon_upgrades = get_weapon_upgrade_patterns(g)
        if weapon_upgrades:
            for upgrade in weapon_upgrades:
                processed_upgrades.append(
                    {
                        "id": upgrade["id"],
                        "name": upgrade["name"],
                        "description": upgrade["description"],
                        "apply": upgrade["apply"],
                    }
                )

        max_choices = 3

        choices = random.sample(
            processed_upgrades, min(max_choices, len(processed_upgrades))
        )

        return choices

    def reroll_upgrade_choices(self) -> bool:
        """Consume one reroll (if available) and replace the current upgrade choices."""
        if not getattr(self.game, "awaiting_upgrade", False):
            return False
        if getattr(self.game, "upgrade_rerolls_remaining", 0) <= 0:
            return False

        old_ids = [c.get("id") for c in self.game.upgrade_choices]
        attempts = 0
        while attempts < 8:
            new_choices = self.generate_upgrade_choices()
            new_ids = [c.get("id") for c in new_choices]
            if set(new_ids) != set(old_ids):
                self.game.upgrade_choices = new_choices
                self.game.upgrade_rerolls_remaining = max(
                    0, self.game.upgrade_rerolls_remaining - 1
                )
                try:
                    self.game.game_state.upgrade_choices = list(
                        self.game.upgrade_choices
                    )
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
                return True
            attempts += 1
        self.game.upgrade_rerolls_remaining = max(
            0, self.game.upgrade_rerolls_remaining - 1
        )
        return False

    def generate_initial_weapon_choices(self):
        """Delegate to GameStateManager for initial weapon choices."""
        try:
            return self.game.game_state.generate_initial_weapon_choices()
        except (AttributeError, TypeError, ValueError, KeyError):
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
                    "id": "Flies",
                    "name": "Flies",
                    "description": "Fires homing fly projectiles that heal the player",
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
        all_weapons: List[Dict[str, str]] = get_weapon_definitions()
        all_weapon_ids = [w["id"] for w in all_weapons]

        if getattr(self.game, "player_level", None) == 6:
            unowned = [w for w in all_weapon_ids if w not in self.game.player_weapons]

            def _is_available_for_stage(wid: str) -> bool:
                wdef = WEAPON_DEFS.get(wid, {})
                available_from = wdef.get("available_from")
                if not available_from:
                    return True
                af = str(available_from).lower()
                if af == "purgatory":
                    return bool(
                        self.game.selected_stage
                        and str(self.game.selected_stage).startswith(
                            ("purgatory", "hell")
                        )
                    )
                if af == "limbo":
                    return bool(
                        self.game.selected_stage
                        and str(self.game.selected_stage) != "prologo"
                    )
                if af == "hell":
                    return bool(
                        self.game.selected_stage
                        and str(self.game.selected_stage).startswith("hell")
                    )
                return True

            filtered_unowned = [w for w in unowned if _is_available_for_stage(w)]

            choices: List[Dict[str, str]] = []
            if filtered_unowned:
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
            # ensure icons propagate even for the early level-6 branch
            for c in choices:
                wid = None
                cid = c.get("id", "")
                if cid.startswith("acquire_"):
                    wid = cid.split("acquire_")[-1]
                elif cid.endswith("_upgrade"):
                    wid = cid[: -len("_upgrade")]
                if wid:
                    icon = WEAPON_DEFS.get(wid, {}).get("icon")
                    if not icon:
                        icon = f"weapon_{wid.lower()}.png"
                    c["icon"] = icon
            return choices[:3]

        all_weapons = [
            {
                "id": weapon["id"],
                "name": weapon["name"],
                "description": weapon["description"],
                "apply": lambda w=weapon["id"]: self.game.apply_weapon(w),
            }
            for weapon in all_weapons
        ]

        available_weapons: List[Dict[str, str]] = []
        for w in all_weapons:
            wid = w["id"]
            if wid in self.game.player_weapons:
                continue
            wdef = WEAPON_DEFS.get(wid, {})
            available_from = wdef.get("available_from")
            if available_from:
                af = str(available_from).lower()
                if af == "purgatory":
                    if not (
                        self.game.selected_stage
                        and str(self.game.selected_stage).startswith(
                            ("purgatory", "hell")
                        )
                    ):
                        continue
                if af == "limbo":
                    if not (
                        self.game.selected_stage
                        and str(self.game.selected_stage) != "prologo"
                    ):
                        continue
                if af == "hell":
                    if not (
                        self.game.selected_stage
                        and str(self.game.selected_stage).startswith("hell")
                    ):
                        continue
            available_weapons.append(w)

        if len(self.game.player_weapons) >= self.game.max_extra_weapons:
            available_weapons = []

        if not available_weapons:
            return []

        result = random.sample(available_weapons, min(3, len(available_weapons)))
        # attach icon info for returned entries (fallback if necessary)
        for c in result:
            wid = c.get("id")
            if wid:
                icon = WEAPON_DEFS.get(wid, {}).get("icon")
                if not icon:
                    icon = f"weapon_{wid.lower()}.png"
                c["icon"] = icon
        return result
        return result

    def generate_weapon_upgrade_choices(self):
        """Generate weapon upgrade choices for owned weapons"""
        weapon_upgrades = []

        for weapon_id in self.game.player_weapons:
            current_level: int = self.game.weapon_levels.get(weapon_id, 0)
            max_level: int = getattr(
                self.game,
                "max_weapon_level",
                WEAPON_DEFS.get(weapon_id, {}).get("max_level", 6),
            )

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

        return random.sample(weapon_upgrades, min(2, len(weapon_upgrades)))

    def apply_weapon(self, weapon_id) -> None:
        """Apply a weapon or weapon upgrade"""
        if isinstance(weapon_id, str) and weapon_id.startswith("acquire_"):
            weapon_id = weapon_id.replace("acquire_", "")

        if weapon_id.endswith("_upgrade"):
            base_weapon_id = weapon_id.replace("_upgrade", "")
            if base_weapon_id in self.game.player_weapons:
                current_level: int = self.game.weapon_levels.get(base_weapon_id, 0)
                self.game.weapon_levels[base_weapon_id] = current_level + 1

                if base_weapon_id == "orbital":
                    self.game.orbital_count = get_orbital_count(
                        self.game.weapon_levels["orbital"]
                    )
                    self.game.create_orbitals()

                logger.info(
                    f"Upgraded {base_weapon_id} to level {self.game.weapon_levels[base_weapon_id]}"
                )
        elif (
            weapon_id not in self.game.player_weapons
            and len(self.game.player_weapons) < self.game.max_extra_weapons
        ):
            self.game.player_weapons.append(weapon_id)
            self.game.weapon_levels[weapon_id] = 1
            self.game.game_state.player_weapons = self.game.player_weapons.copy()
            self.game.game_state.weapon_levels = self.game.weapon_levels.copy()
            if weapon_id == "orbital":
                self.game.orbital_count = 3
                self.game.create_orbitals()

        self.game.awaiting_weapon_choice = False
        if not (
            getattr(self.game, "is_initial_tower_choice", False)
            or getattr(self.game, "awaiting_tower_choice", False)
        ):
            self.game.paused = False
        try:
            self.game.game_state.awaiting_weapon_choice = False
            self.game.game_state.weapon_choices = []
            self.game.game_state.weapon_choice_index = 0
            self.game.game_state.player_weapons = self.game.player_weapons.copy()
            self.game.game_state.weapon_levels = self.game.weapon_levels.copy()
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        if self.game.is_initial_weapon_choice:
            self.game.is_initial_weapon_choice = False
            if self.game.is_initial_tower_choice:
                try:
                    self.game.game_state.show_initial_tower_choice()
                    self.game.awaiting_tower_choice = (
                        self.game.game_state.awaiting_tower_choice
                    )
                    self.game.tower_choices = list(self.game.game_state.tower_choices)
                    self.game.selected_tower_index = (
                        self.game.game_state.tower_choice_index
                    )
                except (AttributeError, TypeError, ValueError, KeyError):
                    self.game.awaiting_tower_choice = True
                    self.game.tower_choices = self.generate_initial_tower_choices()
                    self.game.selected_tower_index = 0
            else:
                try:
                    self.game.tower_energy = 0
                except (AttributeError, TypeError, ValueError, KeyError):
                    setattr(self.game, "tower_energy", 0)
                self.game.stage_start_countdown = 3
                self.game.stage_start_timer = self.game.fps

    def generate_initial_tower_choices(self) -> list[dict[str, Any]]:
        """Fallback generator for tower choices (mirrors GameStateManager)."""
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

    def _wall_x_at(self, side: str, y: float) -> float:
        """Return wall x coordinate for given side ('left' or 'right') nearest to provided y."""
        points = (
            self.game.left_wall_points
            if side == "left"
            else self.game.right_wall_points
        )
        if not points:
            return 320.0 if side == "left" else 960.0
        nearest = min(points, key=lambda p: abs(p[1] - y))
        return float(nearest[0])

    def apply_tower(self, tower_id: str) -> None:
        """Apply the selected tower type for Purgatory and place towers at the bottom outside walls."""
        tower_type = tower_id

        desired_y = 600
        left_wall_x = self._wall_x_at("left", desired_y)
        right_wall_x = self._wall_x_at("right", desired_y)
        margin = 30
        left_x = left_wall_x - WALL_THICKNESS - margin
        right_x = right_wall_x + WALL_THICKNESS + margin

        left_x = max(20, left_x)
        right_x = min(self.game.width - 20, right_x)

        self.game.left_tower = Tower(
            left_x,
            desired_y,
            fire_rate=self.game.statue_fire_rate,
            tower_type=tower_type,
        )
        self.game.left_tower._base_damage = self.game.left_tower.damage
        self.game.left_tower._base_fire_rate = self.game.left_tower.fire_rate
        self.game.right_tower = Tower(
            right_x,
            desired_y,
            fire_rate=self.game.statue_fire_rate,
            tower_type=tower_type,
        )
        self.game.right_tower._base_damage = self.game.right_tower.damage
        self.game.right_tower._base_fire_rate = self.game.right_tower.fire_rate
        self.game.left_tower.visible = True
        self.game.right_tower.visible = True
        try:
            self.game.apply_permanent_stats()
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        self.game.awaiting_tower_choice = False
        if not getattr(self.game, "is_initial_weapon_choice", False):
            self.game.paused = False
        try:
            self.game.game_state.awaiting_tower_choice = False
            self.game.game_state.tower_choices = []
            self.game.game_state.tower_choice_index = 0
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        if self.game.is_initial_tower_choice:
            self.game.is_initial_tower_choice = False
            if not self.game.is_initial_weapon_choice:
                try:
                    self.game.tower_energy = 0
                except (AttributeError, TypeError, ValueError, KeyError):
                    setattr(self.game, "tower_energy", 0)
                self.game.stage_start_countdown = 3
                self.game.stage_start_timer = self.game.fps

    def apply_permanent_stats(self) -> None:
        """Apply permanent stat effects to both game-level and player-level multipliers."""
        self.game.damage_multiplier = 1.0 + (
            self.game.permanent_stats.get("power", 0) * 0.05
        )
        self.game.fire_rate_multiplier = 1.0 + (
            self.game.permanent_stats.get("adrenaline", 0) * 0.05
        )
        self.game.projectile_size_multiplier = 1.0 + (
            self.game.permanent_stats.get("projectile_size", 0) * 0.0
        )
        self.game.damage_reduction_multiplier = 1.0 - (
            self.game.permanent_stats.get("structure", 0) * 0.02
            + self.game.permanent_stats.get("blasphemy_3", 0) * 0.10
        )
        self.game.xp_multiplier = (
            1.0
            + (self.game.permanent_stats.get("structure", 0) * 0.03)
            + (self.game.permanent_stats.get("blasphemy_4", 0) * 0.10)
        )

        try:
            self.game.player.damage_multiplier = self.game.damage_multiplier
            self.game.player.fire_rate_multiplier = self.game.fire_rate_multiplier
            self.game.player.projectile_size_multiplier = (
                self.game.projectile_size_multiplier
            )
            self.game.player.damage_reduction_multiplier = (
                self.game.damage_reduction_multiplier
            )
            speed_multiplier = 1.0 + (
                self.game.permanent_stats.get("blasphemy_7", 0) * 0.10
            )
            base_speed = getattr(
                self.game.player,
                "base_speed",
                getattr(self.game.player, "speed", 220.0),
            )
            self.game.player.speed = base_speed * speed_multiplier
            if hasattr(self.game.player, "original_speed"):
                self.game.player.original_speed = base_speed * speed_multiplier
            try:
                self.game.player.max_health = (
                    PLAYER_BASE_HEALTH
                    + (self.game.permanent_stats.get("vigor", 0) * 10)
                    + (self.game.permanent_stats.get("blasphemy_1", 0) * 15)
                )
                if getattr(self.game.player, "health", 0) > self.game.player.max_health:
                    self.game.player.health = self.game.player.max_health
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        for prefix in ("fire", "storm", "ice"):
            self._enforce_center_requirement(prefix)

        self.game.tower_damage_multiplier = {"fire": 1.0, "storm": 1.0, "ice": 1.0}
        self.game.tower_fire_rate_multiplier = {"fire": 1.0, "storm": 1.0, "ice": 1.0}
        blasphemy8_mult = 1.0 + (self.game.permanent_stats.get("blasphemy_8", 0) * 0.20)
        try:
            from src.balance import STATUE_FIRE_RATE

            self.game.statue_fire_rate = max(
                1, int(round(STATUE_FIRE_RATE / blasphemy8_mult))
            )
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        storm_left_count = (
            2 * self.game.permanent_stats.get("storm_1", 0)
            + 0 * self.game.permanent_stats.get("storm_2", 0)
            + 2 * self.game.permanent_stats.get("storm_3", 0)
        )

        for prefix in ("fire", "storm", "ice"):
            right_count = sum(
                self.game.permanent_stats.get(f"{prefix}_{i}", 0) for i in (4, 5, 6)
            )
            # damage multiplier per right-column slot:
            # * fire: +10% (crit handled separately)
            # * ice: +20%
            # * storm: no damage bonus any more
            if prefix == "ice":
                dmg_mult = 1.0 + (right_count * 0.20)
            elif prefix == "storm":
                dmg_mult = 1.0
            else:
                dmg_mult = 1.0 + (right_count * 0.10)
            # fire rate multiplier: storm and ice benefit; fire no longer gets fire-rate
            if prefix == "storm":
                fr_mult = 1.0 + (right_count * 0.20)
            elif prefix == "ice":
                fr_mult = 1.0 + (right_count * 0.10)
            else:
                fr_mult = 1.0
            fr_mult = fr_mult * blasphemy8_mult
            self.game.tower_damage_multiplier[prefix] = dmg_mult
            self.game.tower_fire_rate_multiplier[prefix] = fr_mult

            for t in (
                getattr(self.game, "left_tower", None),
                getattr(self.game, "right_tower", None),
            ):
                if t is None:
                    continue
                if getattr(t, "tower_type", None) != prefix:
                    continue
                if not hasattr(t, "_base_damage"):
                    t._base_damage = t.damage
                if not hasattr(t, "_base_fire_rate"):
                    t._base_fire_rate = t.fire_rate
                if prefix == "storm" and not hasattr(t, "_base_chain_targets"):
                    t._base_chain_targets = getattr(t, "chain_targets", 3)
                t.damage = int(round(t._base_damage * dmg_mult))
                t.fire_rate = max(1, int(round(t._base_fire_rate / fr_mult)))

                if prefix == "storm":
                    extra_chain = storm_left_count
                    t.chain_targets = getattr(t, "_base_chain_targets", 3) + extra_chain

                if prefix == "ice" and self.game.permanent_stats.get("ice_1", 0):
                    t.explosion_radius = 60
                    if self.game.permanent_stats.get("ice_2", 0):
                        t.explosion_radius = int(60 * 1.5)

    def _enforce_center_requirement(self, key_prefix: str) -> None:
        """Ensure the center tier (7) is only active when a full column of 3 exists."""
        center_key = f"{key_prefix}_7"
        left_full = all(
            self.game.permanent_stats.get(f"{key_prefix}_{i + 1}", 0) for i in range(3)
        )
        right_full = all(
            self.game.permanent_stats.get(f"{key_prefix}_{4 + i}", 0) for i in range(3)
        )
        if self.game.permanent_stats.get(center_key, 0) and not (
            left_full or right_full
        ):
            self.game.permanent_stats[center_key] = 0
            logger.info(
                "Clearing center tier %s because no column is fully active", center_key
            )

    def permanent_stat_effect_text(self, key: str, level: int) -> str:
        """Return a human-friendly description of the per-level and total effect for a permanent stat."""
        if key == "power":
            per = 5.0
            total = per * level
            return f"+{per:.0f}% dmg/level ({total:.0f}% total)"
        if key == "vigor":
            per = 10
            total = per * level
            # Regeneration scales with level: 0.5 HP per 5s per level
            regen_per_level = 0.5
            regen_total = regen_per_level * level
            regen_str = (
                f"{regen_total:.1f}" if regen_total % 1 else f"{int(regen_total)}"
            )
            return (
                f"+{per:d} HP/level ({total:d} HP total)\n"
                f"Heal {regen_per_level} HP every 5s/level ({regen_str} HP/5s)"
            )
        if key == "adrenaline":
            per = 5.0
            total = per * level
            crit_per = 2.0
            crit_total = crit_per * level
            return (
                f"+{per:.0f}% fire rate/level ({total:.0f}% total); "
                f"+{crit_per:.0f}% crit chance/level ({crit_total:.0f}% total)"
            )
        if key == "structure":
            per = 2.0
            total = per * level
            xp_total_pct = int(round(3.0 * level))
            return f"-{per:.0f}% dmg taken/level ({total:.0f}% total); +3% XP/level (+{xp_total_pct}% XP total)"
        if key.startswith("blasphemy"):
            if key == "blasphemy_1":
                per = 15
                total = per * level
                return f"+{per:d} HP/level ({total:d} HP total)"
            if key == "blasphemy_2":
                # now gives 0.5 HP every 2s per level
                per = 0.5
                total = per * level
                regen_str = f"{total:.1f}" if total % 1 else f"{int(total)}"
                # add 'Heal' prefix to make regeneration explicit
                return f"Heal {per:g} HP every 2s/level ({regen_str} HP every 2s)"
            if key == "blasphemy_3":
                per = 10.0
                total = per * level
                return f"-{per:.0f}% dmg taken/level ({total:.0f}% total)"
            if key == "blasphemy_4":
                per = 10.0
                total = per * level
                return f"+{per:.0f}% XP/level ({total:.0f}% total)"
            if key == "blasphemy_5":
                return "Blink: teleport in moving direction (spacebar); 5s cooldown"
            if key == "blasphemy_6":
                per = 10.0
                total = per * level
                return f"Critical hits: +50% damage; +{per:.0f}% crit chance/level ({int(total)}% total)"
            if key == "blasphemy_7":
                per = 10.0
                total = per * level
                return f"+{per:.0f}% movement speed/level ({total:.0f}% total)"
            if key == "blasphemy_8":
                per = 20.0
                total = per * level
                return f"+{per:.0f}% tower fire rate/level ({total:.0f}% total)"
            if key == "blasphemy_9":
                per = 2
                total = per * level
                return f"Reroll level-up upgrade choices: +{per:d} rerolls/level ({total:d} rerolls per run)"
            if key == "blasphemy_10":
                return "Revive once on death; restore 50% max HP"
            return "No description available"
        return ""

    def _skill_tooltip_lines(self, key_prefix: str, tier: int) -> list:
        """Return list of text lines to show in a tooltip for a given skill tree tier."""
        lines: list[str] = []

        if tier in (4, 5, 6):
            if key_prefix == "storm":
                lines.append("+10% crit chance, +20% fire rate")
            elif key_prefix == "ice":
                lines.append("+20% dmg, +10% fire rate")
            else:  # fire
                lines.append("+10% dmg, +10% crit chance")
        elif tier == 7:
            # center-tier upgrades now have proper names
            if key_prefix == "fire":
                lines.append("AR.MAGA.EDDON")
                lines.append("Right-click fires up to 4 burning orbs ")
            elif key_prefix == "storm":
                lines.append("Voltaic Mayhem")
                lines.append("Controllable stream of electric chaos")
                lines.append(
                    "Endpoint moves toward cursor at limited speed (≈200px/sec)"
                )
            elif key_prefix == "ice":
                lines.append("Blizzard")
        else:
            if key_prefix == "fire" and tier == 1:
                lines.append("Burn spreads to nearby enemies on death (chains up to 2)")
            elif key_prefix == "fire" and tier == 2:
                lines.append("Burn duration ×2; burn DPS ×2")
            elif key_prefix == "fire" and tier == 3:
                lines.append("+25% damage to burning enemies")
            elif key_prefix == "storm" and tier in (1, 2, 3):
                if tier == 1:
                    lines.append("Chain lightning +2 targets")
                elif tier == 2:
                    lines.append("Chain-kills trigger lightning explosion")
                else:
                    lines.append("Chain lightning +2 targets")
            elif key_prefix == "ice" and tier == 1:
                lines.append("Projectiles deal area damage and create slowing puddles")
            elif key_prefix == "ice" and tier == 2:
                lines.append("+50% puddle area and area damage radius")
            elif key_prefix == "ice" and tier == 3:
                lines.append("Projectiles pierce through enemies")

        return lines

    def _player_stats_display_items(self):
        """Return (key, value) pairs to display in the player stats sheet."""
        import re

        def is_excluded(k: str) -> bool:
            if any(tok in k for tok in ("tower", "statue")):
                return True
            if re.match(r"^(fire|storm|ice)(?:_|$)", k):
                return True
            return False

        return [
            (k, v) for k, v in self.game.permanent_stats.items() if not is_excluded(k)
        ]

    def show_upgrades(self) -> None:
        """Show level up upgrade selection"""
        self.game.awaiting_upgrade = True
        self.game.paused = True
        self.game.upgrade_choices = self.generate_upgrade_choices()
        self.game.selected_upgrade_index = 0

    def apply_upgrade(self, upgrade) -> None:
        """Apply the selected upgrade"""
        if isinstance(upgrade, int):
            upgrade = self.game.upgrade_choices[upgrade]

        try:
            upgrade["apply"]()
        except Exception as e:
            logger.exception(
                "Error applying upgrade %s: %s", upgrade.get("name", "unknown"), e
            )

        upgrade_id = upgrade["id"]
        if upgrade_id not in self.game.upgrade_levels:
            self.game.upgrade_levels[upgrade_id] = 0
        self.game.upgrade_levels[upgrade_id] += 1

        # Track shield upgrade level for cooldown calculation
        if upgrade_id == "shield":
            self.game.player.shield_upgrade_level = self.game.upgrade_levels[upgrade_id]
            # Enable shield on first upgrade (shield_charges was 0 before)
            if self.game.player.shield_charges == 0:
                self.game.player.shield_charges = 1

        self.game.awaiting_upgrade = False
        self.game.paused = False
        try:
            self.game.game_state.awaiting_upgrade = False
            self.game.game_state.upgrade_choices = []
            self.game.game_state.upgrade_choice_index = 0
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
