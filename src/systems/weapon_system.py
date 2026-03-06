"""Weapon system for handling all weapon firing and projectile creation."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING, Any

from src.projectile import FliesProjectile, Projectile
from src.weapons import (
    DemonStrike_cooldown,
    beast_damage,
    flies_cd,
    flies_damage_heal_mult,
    flies_projectile_count,
    orbital_cooldown_range,
    shotgun_cooldown,
    shotgun_pellet_damage,
    shotgun_pellets,
    skullboom_cooldown,
    skullboom_damage,
    skullboom_explosion_radius,
    tenebrae_cooldown,
)

if TYPE_CHECKING:
    from src.game import Game

from src.core.entities.tower import TowerManager
from src.weapons import WEAPON_DEFS


def statue_projectile_offsets(game: "Game") -> tuple[float, float]:
    """Return (x,y) offsets applied to statue/tower projectiles for selected stage.

    Horizontal offset is the distance from the tower center to the point where
    projectiles are spawned; it is positive for towers on the left side and should
    be negated for the right side.  Vertical offset is always applied downward.
    Every piece of code that needs to know where projectiles originate (statue
    weapons, storm‑tier special beam origins, etc.) must use this helper so they
    stay in sync as stage artwork changes.
    """
    from src import game_constants

    stage = getattr(game, "selected_stage", "") or ""
    if stage in LIMBO_STAGES:
        # Limbo Final projectiles originate further from centre than
        # regular Limbo statues.  Total outward shift is currently 35px,
        # so subtract that amount from the limbo constant (50) giving 15px.
        stage_x = game_constants.STATUE_PROJECTILE_OFFSET_X_LIMBO
        if stage == "limbo_final":
            stage_x -= 35
    elif stage in PURGATORY_STAGES:
        stage_x = game_constants.STATUE_PROJECTILE_OFFSET_X_PURGATORY
    elif stage in HELL_STAGES:
        stage_x = game_constants.STATUE_PROJECTILE_OFFSET_X_HELL
    else:
        stage_x = 0
    stage_y = game_constants.STATUE_PROJECTILE_OFFSET_Y
    return stage_x, stage_y


class WeaponSystem:
    """Handles weapon firing, projectile creation, and orbital updates."""

    def __init__(self, game: "Game") -> None:
        self.game = game

    def update_weapon_firing(self) -> None:
        """Handle automatic weapon firing"""
        if self.game.selected_stage == "prologo" and self.game.prologo_lightning_strike:
            return  # No firing during lightning

        # Calculate aim direction
        dx: int | Any = self.game.mouse_x - self.game.player.x
        dy = self.game.mouse_y - self.game.player.y
        dist: float = math.hypot(dx, dy)
        if dist > 0:
            aim_vel_x: float | Any = (dx / dist) * 500
            aim_vel_y = (dy / dist) * 500
        else:
            aim_vel_x = 0
            aim_vel_y = -500

        # Base weapon firing (burst system) - only if player has beast
        if "beast" in self.game.player_weapons:
            if self.game.burst_cooldown > 0:
                self.game.burst_cooldown -= 1
            else:
                beast_level = self.game.weapon_levels.get("beast", 0)
                beast_rate_multiplier = 1 + beast_level * 0.05
                effective_burst_fire_rate: int = max(
                    1,
                    int(
                        self.game.burst_fire_rate
                        / (self.game.fire_rate_multiplier * beast_rate_multiplier)
                    ),
                )
                effective_burst_max: int = self.game.burst_max
                effective_burst_pause: int = max(6, self.game.burst_pause)

                if (
                    self.game.time_elapsed % (effective_burst_fire_rate / self.game.fps)
                    < 1 / self.game.fps
                ):
                    if self.game.burst_count < effective_burst_max:
                        self.fire_basic_weapon(aim_vel_x, aim_vel_y)
                        self.game.burst_count += 1
                    else:
                        self.game.burst_cooldown = effective_burst_pause
                        self.game.burst_count = 0

        # Special weapons
        if (
            "shotgun" in self.game.player_weapons
            and self.game.hellgun_cooldown_timer <= 0
        ):
            self.fire_hellgun(aim_vel_x, aim_vel_y)
            slevel = self.game.weapon_levels.get("shotgun", 0)
            cd_shot: float = shotgun_cooldown(slevel)
            self.game.hellgun_cooldown_timer = int(cd_shot * self.game.fps)

        if "spear" in self.game.player_weapons and self.game.spear_cooldown_timer <= 0:
            self.fire_spear(aim_vel_x, aim_vel_y)
            slevel = self.game.weapon_levels.get("spear", 0)
            cd: float = DemonStrike_cooldown(slevel)
            self.game.spear_cooldown_timer = int(cd * self.game.fps)

        # Tenebrae weapon: piercing beam that decays per enemy hit
        if (
            "tenebrae" in self.game.player_weapons
            and getattr(self.game, "tenebrae_cooldown_timer", 0) <= 0
        ):
            self.fire_tenebrae(aim_vel_x, aim_vel_y)
            dlevel = self.game.weapon_levels.get("tenebrae", 0)
            cd_d: float = tenebrae_cooldown(dlevel)
            self.game.tenebrae_cooldown_timer = int(cd_d * self.game.fps)

        # DemonStrike: vertical-only rolling ball, pierces and slows
        if (
            "DemonStrike" in self.game.player_weapons
            and getattr(self.game, "DemonStrike_cooldown_timer", 0) <= 0
        ):
            self.fire_demon_strike(aim_vel_x, aim_vel_y)
            ds_level = self.game.weapon_levels.get("DemonStrike", 0)
            cd_ds: float = DemonStrike_cooldown(ds_level)
            self.game.DemonStrike_cooldown_timer = int(cd_ds * self.game.fps)

        if "Flies" in self.game.player_weapons and self.game.flies_cooldown_timer <= 0:
            self.fire_flies(aim_vel_x, aim_vel_y)
            slevel = self.game.weapon_levels.get("Flies", 0)
            cd_sec: float = flies_cd(slevel)
            self.game.flies_cooldown_timer = int(cd_sec * self.game.fps)

        # Update weapon cooldowns
        if self.game.hellgun_cooldown_timer > 0:
            self.game.hellgun_cooldown_timer -= 1
        if self.game.spear_cooldown_timer > 0:
            self.game.spear_cooldown_timer -= 1
        if getattr(self.game, "DemonStrike_cooldown_timer", 0) > 0:
            self.game.DemonStrike_cooldown_timer -= 1
        if self.game.flies_cooldown_timer > 0:
            self.game.flies_cooldown_timer -= 1
        if getattr(self.game, "tenebrae_cooldown_timer", 0) > 0:
            self.game.tenebrae_cooldown_timer -= 1

    def fire_basic_weapon(self, aim_x, aim_y) -> None:
        """Fire basic projectile"""
        base_damage = int(self.game.player_damage * self.game.damage_multiplier)

        # Apply beast weapon damage bonus (+5% per level)
        beast_level: int = self.game.weapon_levels.get("beast", 0)
        if beast_level > 0:
            try:
                # Use centralized helper to compute beast-adjusted damage
                base_damage = beast_damage(beast_level, base_damage)
            except (AttributeError, TypeError, ValueError, KeyError):
                # Fallback to old percentage behaviour if helper missing
                base_damage = int(base_damage * (1 + beast_level * 0.05))

        base_radius = int(8 * self.game.projectile_size_multiplier)

        # If player has the 'beast' weapon, make basic projectiles visibly larger
        # Fixed increase: +25% radius for beast projectiles (all levels)
        if self.game.weapon_levels.get("beast", 0) > 0:
            base_radius = max(1, int(base_radius * 1.25))

        projectile: Projectile = Projectile(
            self.game.player.x,
            self.game.player.y,
            aim_x,
            aim_y,
            damage=base_damage,
            radius=base_radius,
            appearance="beast" if beast_level > 0 else None,
            weapon_type="beast" if beast_level > 0 else None,
        )
        self.game.projectiles.add(projectile)
        mgr = self.game.projectile_manager
        if mgr is not None:
            try:
                mgr.register(projectile)
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

    def fire_hellgun(self, aim_x, aim_y) -> None:
        """Fire hellgun pellets"""
        slevel: int = self.game.weapon_levels.get("shotgun", 0)
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
            base_player = int(self.game.player_damage * self.game.damage_multiplier)
            base_damage = shotgun_pellet_damage(slevel, base_player)
            base_radius = int(5 * self.game.projectile_size_multiplier * 1.0)
            # Increase pellet collision/visual radius by +2 px as requested
            base_radius = max(1, base_radius + 2)

            pellet: Projectile = Projectile(
                self.game.player.x,
                self.game.player.y,
                vx,
                vy,
                damage=base_damage,
                radius=base_radius,
                weapon_type="shotgun",
            )
            self.game.projectiles.add(pellet)
            mgr = self.game.projectile_manager
            if mgr is not None:
                try:
                    mgr.register(pellet)
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

    def fire_spear(self, aim_x, aim_y) -> None:
        """Fire piercing spear"""
        slevel: int = self.game.weapon_levels.get("spear", 0)
        spear_damage: int = max(
            2,
            int(
                self.game.player_damage * self.game.damage_multiplier * 0.5 + slevel * 2
            ),
        )
        speed_factor: float = 800 / 500.0
        vx = int(aim_x * speed_factor)
        vy = int(aim_y * speed_factor)
        # base diameter adjusted: original 5 -> 10, then reduced by 3 to 7
        # radius = max(4, int(base * multiplier * 1.1))
        spear_radius: int = max(4, int(7 * self.game.projectile_size_multiplier * 1.1))

        spear: Projectile = Projectile(
            self.game.player.x,
            self.game.player.y,
            vx,
            vy,
            damage=spear_damage,
            radius=spear_radius,
            weapon_type="spear",
            appearance="spear",  # allow external asset override
        )
        spear.pierce_all = True
        self.game.projectiles.add(spear)
        mgr = self.game.projectile_manager
        if mgr is not None:
            try:
                mgr.register(spear)
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

    def fire_demon_strike(self, aim_x, aim_y) -> None:
        """Fire DemonStrike: vertical-only rolling ball that pierces and slows enemies.

        Behavior:
        - Velocity constrained to perfectly vertical direction (vx = 0).
        - Pierces every enemy hit (pierce_all = True) and deals one instance of damage per enemy (same damage formula as spear).
        - Applies slow effect (50% speed) for 2 seconds on hit.
        """
        dlevel: int = self.game.weapon_levels.get("DemonStrike", 0)
        # Damage scaling: keep player-damage component, add +10 damage per weapon level
        dmg: int = max(
            2,
            int(self.game.player_damage * self.game.damage_multiplier * 0.5)
            + dlevel * 10,
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
                round((base_diam * self.game.projectile_size_multiplier) / 2.0)
            )
        else:
            base_r_calc = int(
                WEAPON_DEFS.get("DemonStrike", {}).get("base_radius", 9)
                * self.game.projectile_size_multiplier
            )
        per_level_inc = WEAPON_DEFS.get("DemonStrike", {}).get(
            "radius_increase_per_level", 0
        )
        radius: int = max(7, base_r_calc + dlevel * per_level_inc)

        ball = Projectile(
            self.game.player.x,
            self.game.player.y,
            vx,
            vy,
            damage=dmg,
            radius=radius,
            weapon_type="DemonStrike",
        )
        ball.pierce_all = True
        # Slow metadata handled by collision system
        ball.effect = "slow"
        ball.slow_duration = int(2 * getattr(self.game, "fps", 60))
        ball.slow_factor = 0.5

        self.game.projectiles.add(ball)
        mgr = self.game.projectile_manager
        if mgr is not None:
            try:
                mgr.register(ball)
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

    def fire_flies(self, aim_x, aim_y) -> None:
        """Fire homing Flies projectiles"""
        slevel: int = self.game.weapon_levels.get("Flies", 0)
        # Use centralized helper to determine projectile count (base is now 2)
        num_projectiles = flies_projectile_count(slevel)
        # damage/heal multipliers are computed by helper function in weapons.py
        damage_mult, heal_mult = flies_damage_heal_mult(slevel)

        # Read base_heal from weapon defs so changes propagate consistently
        base_heal = WEAPON_DEFS.get("Flies", {}).get("base_heal", 2)

        for i in range(num_projectiles):
            # Spread slightly
            angle_offset = (i - (num_projectiles - 1) / 2) * 0.3
            # Initial velocity reduced to make projectiles at least half as fast
            vx = (aim_x * math.cos(angle_offset) - aim_y * math.sin(angle_offset)) * 0.5
            vy = (aim_x * math.sin(angle_offset) + aim_y * math.cos(angle_offset)) * 0.5

            flies_proj = FliesProjectile(
                self.game.player.x,
                self.game.player.y,
                vx,
                vy,
                damage=int(
                    WEAPON_DEFS.get("Flies", {}).get("base_damage", 10) * damage_mult
                ),
                heal_amount=int(base_heal * heal_mult),
                level=slevel,
            )
            self.game.projectiles.add(flies_proj)
            mgr = self.game.projectile_manager
            if mgr is not None:
                try:
                    mgr.register(flies_proj)
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

    def fire_skullboom(self, aim_x, aim_y) -> None:
        """Fire explosive SkullBoom"""
        slevel: int = self.game.weapon_levels.get("skullboom", 0)
        damage = skullboom_damage(slevel)
        explosion_radius = skullboom_explosion_radius(slevel)

        # Create skull projectile
        # Slightly slower than basic projectiles (≈26% slower than 500 px/s)
        vx = aim_x * 370
        vy = aim_y * 370

        skull: Projectile = Projectile(
            self.game.player.x,
            self.game.player.y,
            vx,
            vy,
            damage=damage,
            radius=11,  # Medium skull (30% smaller than doubled size)
            weapon_type="skullboom",
        )
        # Store explosion radius in projectile for later use
        skull.explosion_radius = explosion_radius

        self.game.projectiles.add(skull)
        mgr = self.game.projectile_manager
        if mgr is not None:
            try:
                mgr.register(skull)
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

    def fire_tenebrae(self, aim_x, aim_y) -> None:
        """Fire Tenebrae projectile: piercing beam that loses power per enemy.

        Creates a piercing projectile that tracks how many enemies it's hit so
        that collision handling can compute decayed damage.  Uses centralized
        helpers for damage and cooldown.  Projectile moves relatively slowly
        (speed defined in WEAPON_DEFS) and retains base player damage for
        scaling.
        """
        dlevel: int = self.game.weapon_levels.get("tenebrae", 0)
        base_player = int(self.game.player_damage * self.game.damage_multiplier)
        speed = WEAPON_DEFS.get("tenebrae", {}).get("speed", 400)

        vx = aim_x * (speed / 500.0)
        vy = aim_y * (speed / 500.0)

        beam: Projectile = Projectile(
            self.game.player.x,
            self.game.player.y,
            vx,
            vy,
            damage=0,  # actual damage computed on hit
            radius=12,  # slightly larger to accommodate wide arc (bumped +2px)
            weapon_type="tenebrae",
            appearance="tenebrae",  # allow external asset or special drawing
        )
        beam.pierce_all = True
        beam.level = dlevel
        beam.base_player_damage = base_player
        beam.targets_hit = 0

        self.game.projectiles.add(beam)
        mgr = self.game.projectile_manager
        if mgr is not None:
            try:
                mgr.register(beam)
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

    def _orbital_cooldown_range(self) -> tuple[int, int]:
        """Return cooldown range for orbitals based on level (delegates to weapons helper)"""
        olevel: int = self.game.weapon_levels.get("orbital", 0)
        return orbital_cooldown_range(olevel)

    def create_orbitals(self) -> None:
        """Initialize orbital sentinels around player"""

        self.game.orbitals = []
        min_cd, max_cd = self._orbital_cooldown_range()
        for i in range(self.game.orbital_count):
            self.game.orbitals.append(
                {
                    "angle": 2 * math.pi * i / max(1, self.game.orbital_count),
                    "dist": 70,
                    "cooldown": random.randint(min_cd, max_cd),
                    "x": self.game.player.x,
                    "y": self.game.player.y,
                }
            )

    def update_orbitals(self) -> None:
        """Update orbital sentinels and handle orbital firing."""

        # Ensure orbitals exist and match desired count
        if (
            not getattr(self.game, "orbitals", None)
            or len(self.game.orbitals) != self.game.orbital_count
        ):
            self.create_orbitals()

        spin_base = 0.06
        spin = spin_base + 0.003 * self.game.weapon_levels.get("orbital", 0)

        for orb in self.game.orbitals:
            orb["angle"] = orb.get("angle", 0) + spin
            orb["x"] = self.game.player.x + math.cos(orb["angle"]) * orb.get("dist", 70)
            orb["y"] = self.game.player.y + math.sin(orb["angle"]) * orb.get("dist", 70)
            orb["cooldown"] = orb.get("cooldown", 0) - 1

            if orb["cooldown"] <= 0:
                ox = orb.get("x", self.game.player.x)
                oy = orb.get("y", self.game.player.y)

                # Select nearest target among enemies and bosses if present
                targets = []
                # Enemies (supports Group or list/dict)
                if hasattr(self.game.enemies, "sprites"):
                    targets.extend(self.game.enemies.sprites())
                else:
                    try:
                        targets.extend(list(self.game.enemies))
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass

                # Bosses (may be stored separately)
                if hasattr(self.game.bosses, "sprites"):
                    targets.extend(self.game.bosses.sprites())
                else:
                    try:
                        targets.extend(list(self.game.bosses))
                    except (AttributeError, TypeError, ValueError, KeyError):
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
                    dx = self.game.mouse_x - ox
                    dy = self.game.mouse_y - oy

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
                        * self.game.damage_multiplier
                        * (
                            1.0
                            + (self.game.weapon_levels.get("orbital", 0) >= 3) * 0.1
                            + (self.game.weapon_levels.get("orbital", 0) >= 5) * 0.1
                        )
                    ),
                    radius=int(4 * self.game.projectile_size_multiplier),
                    source="orbital",
                )
                self.game.projectiles.add(projectile)
                mgr = self.game.projectile_manager
                if mgr is not None:
                    try:
                        mgr.register(projectile)
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass

                min_cd, max_cd = self._orbital_cooldown_range()
                orb["cooldown"] = random.randint(min_cd, max_cd)

    def update_skullboom(self) -> None:
        """Update SkullBoom auto-fire"""

        if self.game.skullboom_cooldown_timer > 0:
            self.game.skullboom_cooldown_timer -= 1
            return

        # Always aim at mouse position
        dx = self.game.mouse_x - self.game.player.x
        dy = self.game.mouse_y - self.game.player.y

        dist = math.hypot(dx, dy)
        if dist > 0:
            # Normalize direction
            dx /= dist
            dy /= dist
        else:
            dx, dy = 1, 0  # Default right

        # Fire SkullBoom
        self.fire_skullboom(dx, dy)

        # Set cooldown
        slevel = self.game.weapon_levels.get("skullboom", 0)
        cd: float = skullboom_cooldown(slevel)
        self.game.skullboom_cooldown_timer = int(cd * self.game.fps)

    def update_statue_weapons(self) -> None:
        """Update Limbo statue weapons"""

        # Helper to get iterable of enemies (supports Group or plain list/dicts)
        def _enemy_iter():
            if hasattr(self.game.enemies, "sprites"):
                return self.game.enemies.sprites()
            try:
                return list(self.game.enemies)
            except (AttributeError, TypeError, ValueError, KeyError):
                return []

        def _pos(e):
            if isinstance(e, dict):
                return e.get("x", 0), e.get("y", 0)
            return getattr(e, "x", 0), getattr(e, "y", 0)

        # Don't fire any statue projectiles while the player is choosing a
        # tower in limbo_final; the towers are invisible and spawning shots
        # before choice looks wrong.
        if getattr(self.game, "selected_stage", "").startswith(
            "limbo_final"
        ) and getattr(self.game, "awaiting_tower_choice", False):
            return
        # Statues alternate firing: single cooldown drives both sides and toggles the next side
        self.game.statue_cooldown -= 1
        if self.game.statue_cooldown <= 0:
            enemies_list = _enemy_iter()
            # include bosses if any (Limbo boss should be targetable)
            if hasattr(self.game, "bosses"):
                try:
                    boss_list = (
                        self.game.bosses.sprites()
                        if hasattr(self.game.bosses, "sprites")
                        else list(self.game.bosses)
                    )
                    enemies_list.extend(boss_list)
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
            if enemies_list:
                # Determine offset values for current stage
                stage_x, stage_y = statue_projectile_offsets(self.game)

                # Choose side based on flag (default to left)
                firing_left = getattr(self.game, "statue_next_left", True)
                origin_shift = stage_x if firing_left else -stage_x
                tower = self.game.left_tower if firing_left else self.game.right_tower
                proj = None
                if tower is not None:
                    origin_x = getattr(tower, "x", 0) + origin_shift
                    origin_y = getattr(tower, "y", 0) + stage_y
                    proj = tower.fire_at_closest(
                        enemies_list,
                        origin_x=origin_x,
                        origin_y=origin_y,
                    )
                if proj:
                    # record offset for diagnostics/tests
                    try:
                        proj._statue_offset = (origin_shift, stage_y)
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass

                    def _store(p):
                        try:
                            self.game.projectiles.add(p)
                            if getattr(
                                self.game, "projectile_manager", None
                            ) is not None and not isinstance(p, dict):
                                try:
                                    mgr = self.game.projectile_manager
                                    if mgr is not None:
                                        mgr.register(p)
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                        except (AttributeError, TypeError, ValueError, KeyError):
                            self.game.projectiles.append(p)

                    # Support both single Projectile and list of Projectiles
                    if isinstance(proj, list):
                        for p in proj:
                            _store(p)
                            try:
                                sp = type("StatueProj", (), {})()
                                sp.x = getattr(p, "x", 0)
                                sp.y = getattr(p, "y", 0)
                                sp.vx = getattr(p, "vel_x", getattr(p, "vx", 0))
                                sp.vy = getattr(p, "vel_y", getattr(p, "vy", 0))
                                sp.radius = getattr(p, "radius", 6)
                                sp.source = getattr(p, "source", "statue")
                                sp.appearance = getattr(p, "appearance", None)
                                self.game.statue_projectiles.append(sp)
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass
                    else:
                        _store(proj)
                        try:
                            sp = type("StatueProj", (), {})()
                            sp.x = getattr(proj, "x", 0)
                            sp.y = getattr(proj, "y", 0)
                            sp.vx = getattr(proj, "vel_x", getattr(proj, "vx", 0))
                            sp.vy = getattr(proj, "vel_y", getattr(proj, "vy", 0))
                            sp.radius = getattr(proj, "radius", 6)
                            sp.source = getattr(proj, "source", "statue")
                            sp.appearance = getattr(proj, "appearance", None)
                            self.game.statue_projectiles.append(sp)
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                    # Reset cooldown and flip next side
                    self.game.statue_cooldown = self.game.statue_fire_rate
                    self.game.statue_next_left = not getattr(
                        self.game, "statue_next_left", True
                    )

        # Update statue projectiles with homing (delegated to TowerManager)
        enemies_list = _enemy_iter()
        # include bosses so homing tracks them too
        if hasattr(self.game, "bosses"):
            try:
                boss_list = (
                    self.game.bosses.sprites()
                    if hasattr(self.game.bosses, "sprites")
                    else list(self.game.bosses)
                )
                enemies_list.extend(boss_list)
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
        # Collect statue projectiles from the main projectile pool
        statue_projs = []
        try:
            # pygame Group iterable
            for p in self.game.projectiles:
                if getattr(p, "source", None) == "statue":
                    statue_projs.append(p)
        except (AttributeError, TypeError, ValueError, KeyError):
            for p in self.game.projectiles:
                if getattr(p, "source", None) == "statue":
                    statue_projs.append(p)

        TowerManager.apply_homing(statue_projs, enemies_list)
