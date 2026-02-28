"""
Module handling tower/statue behavior for Limbo stage.
Provides Tower and TowerManager classes to encapsulate firing and homing logic.
"""

from __future__ import annotations

import math
import random
from typing import Any, Iterable, List, Optional, Tuple

from src.projectile import Projectile


def _pos(e: Any) -> Tuple[float, float]:
    if isinstance(e, dict):
        return e.get("x", 0), e.get("y", 0)
    return getattr(e, "x", 0), getattr(e, "y", 0)


class Tower:
    def __init__(
        self,
        x: float,
        y: float,
        fire_rate: int = 85,
        projectile_speed: float = 320.0,
        inaccuracy: float = 0.5,
        damage: int = 10,
        radius: int = 6,
        tower_type: str = "fire",
    ) -> None:
        # Ice statues/towers have higher base damage than other types unless
        # an explicit damage value is provided by the caller.
        if tower_type == "ice" and damage == 10:
            damage = 15

        self.x = x
        self.y = y
        self.fire_rate = fire_rate
        self.projectile_speed = projectile_speed
        self.inaccuracy = inaccuracy
        self.damage = damage
        self.radius = radius
        self.tower_type = tower_type
        # Preserve base stats for external code that reads these (game.py expects them)
        self._base_damage: int = damage
        self._base_fire_rate: int = fire_rate
        self.visible: bool = True

    def fire_at_closest(
        self,
        enemies: Iterable[Any],
        origin_x: float | None = None,
        origin_y: float | None = None,
    ) -> Optional[object]:
        """Return a projectile (or list/dict) aimed at the nearest enemy.

        ``enemies`` may be any iterable of objects with ``x``/``y`` attributes or
        dicts containing those keys.  ``origin_x``/``origin_y`` allow the caller
        to override the firing point used for both projectile position and
        directional calculations; by default the tower's own ``x``/``y`` are used.
        This is primarily useful for the limbo statues where visual art places
        the firing nozzle away from the tower centre.  When offsets are supplied
        the created projectile's velocity vector is recalculated so it still
        travels toward the chosen target.
        """
        enemies_list = list(enemies) if enemies is not None else []
        if not enemies_list:
            return None

        # choose base coordinates for aim and spawn
        ox = self.x if origin_x is None else origin_x
        oy = self.y if origin_y is None else origin_y

        # Dispatch based on tower type
        if self.tower_type == "fire":
            return self._fire_single(enemies_list, ox, oy)
        elif self.tower_type == "storm":
            return self._fire_storm(enemies_list, ox, oy)
        elif self.tower_type == "ice":
            return self._fire_ice(enemies_list, ox, oy)
        else:
            return self._fire_single(enemies_list, ox, oy)

    def _fire_single(
        self, enemies_list: List[Any], ox: float, oy: float
    ) -> Optional[Projectile]:
        closest = min(
            enemies_list,
            key=lambda e: math.hypot(_pos(e)[0] - ox, _pos(e)[1] - oy),
        )
        cx, cy = _pos(closest)
        dx = cx - ox
        dy = cy - oy
        dist = math.hypot(dx, dy)
        if dist <= 0:
            return None

        # calculate angle; remove random spread when target is a boss
        inacc = self.inaccuracy
        try:
            et = getattr(closest, "enemy_type", "")
            if isinstance(et, str) and "boss" in et:
                inacc = 0.0
        except Exception:
            pass
        angle = math.atan2(dy, dx) + random.uniform(-inacc, inacc)
        vel_x = math.cos(angle) * self.projectile_speed
        vel_y = math.sin(angle) * self.projectile_speed
        # Make Fire tower projectiles visually distinctive
        # Reduce fire projectile size but keep distinctive visuals
        new_radius = max(self.radius, 6)
        proj = Projectile(
            ox,
            oy,
            vel_x,
            vel_y,
            damage=self.damage,
            radius=new_radius,
            is_enemy_projectile=False,
            appearance="fire_statue",
        )
        # Tag as statue projectile
        proj.source = "statue"
        # record originating tower type for later special move logic
        proj.tower_type = self.tower_type

        # Fire towers apply burn (damage over time)
        proj.effect = "burn"
        proj.burn_duration = getattr(self, "burn_duration", 180)  # frames
        # Scale burn DPS proportionally to tower damage relative to its base damage so
        # permanent +% damage applied to towers also affects DOT from Burn.
        base_burn = getattr(self, "burn_damage_per_second", 4.0)
        base_damage = getattr(self, "_base_damage", self.damage)
        try:
            scale = (self.damage / base_damage) if base_damage else 1.0
        except Exception:
            scale = 1.0
        proj.burn_damage_per_second = base_burn * scale
        return proj

    def _fire_storm(
        self, enemies_list: List[Any], ox: float, oy: float
    ) -> Optional[Projectile]:
        # Storm now fires a single aimed projectile (dark-blue appearance)
        closest = min(
            enemies_list,
            key=lambda e: math.hypot(_pos(e)[0] - ox, _pos(e)[1] - oy),
        )
        cx, cy = _pos(closest)
        dx = cx - ox
        dy = cy - oy
        dist = math.hypot(dx, dy)
        if dist <= 0:
            return None

        # remove spread for bosses
        inacc = self.inaccuracy
        try:
            et = getattr(closest, "enemy_type", "")
            if isinstance(et, str) and "boss" in et:
                inacc = 0.0
        except Exception:
            pass
        angle = math.atan2(dy, dx) + random.uniform(-inacc, inacc)
        vel_x = math.cos(angle) * self.projectile_speed
        vel_y = math.sin(angle) * self.projectile_speed
        p = Projectile(
            ox,
            oy,
            vel_x,
            vel_y,
            damage=max(1, int(self.damage * 0.9)),
            radius=self.radius,
            is_enemy_projectile=False,
            appearance="storm_statue",
        )
        p.source = "statue"
        # record type
        p.tower_type = self.tower_type
        # Storm statue projectiles chain-hit up to 3 different enemies
        p.chain_targets = getattr(self, "chain_targets", 3)
        return p

    def _fire_ice(
        self, enemies_list: List[Any], ox: float, oy: float
    ) -> Optional[Projectile]:
        # Fire a single projectile that applies a slow effect on hit
        closest = min(
            enemies_list,
            key=lambda e: math.hypot(_pos(e)[0] - ox, _pos(e)[1] - oy),
        )
        cx, cy = _pos(closest)
        dx = cx - ox
        dy = cy - oy
        dist = math.hypot(dx, dy)
        if dist <= 0:
            return None

        # no spread if aiming at boss
        inacc = self.inaccuracy
        try:
            et = getattr(closest, "enemy_type", "")
            if isinstance(et, str) and "boss" in et:
                inacc = 0.0
        except Exception:
            pass
        angle = math.atan2(dy, dx) + random.uniform(-inacc, inacc)
        vel_x = math.cos(angle) * self.projectile_speed
        vel_y = math.sin(angle) * self.projectile_speed
        p = Projectile(
            ox,
            oy,
            vel_x,
            vel_y,
            damage=self.damage,
            radius=self.radius,
            is_enemy_projectile=False,
        )
        p.source = "statue"
        p.appearance = "ice_statue"
        # record originating tower type, useful for future specials
        p.tower_type = self.tower_type
        # Add slow effect metadata used by collision handling
        p.effect = "slow"
        p.slow_duration = 120
        p.slow_factor = 0.5
        # Add area damage effect if tower has explosion_radius (from ICE1 upgrade)
        if hasattr(self, "explosion_radius"):
            p.explosion_radius = self.explosion_radius
        return p


# Backwards-compatible aliases
class FireTower(Tower):
    def __init__(self, x, y, **kwargs):
        super().__init__(x, y, tower_type="fire", **kwargs)


class StormTower(Tower):
    def __init__(self, x, y, **kwargs):
        super().__init__(x, y, tower_type="storm", **kwargs)


class IceTower(Tower):
    def __init__(self, x, y, **kwargs):
        super().__init__(x, y, tower_type="ice", **kwargs)


class TowerManager:
    @staticmethod
    def apply_homing(
        projectiles: List[Any], enemies: Iterable[Any], projectile_speed: float = 320.0
    ) -> None:
        """Apply homing to Projectile instances (object-style only).

        Mutates velocities in-place.
        """
        enemies_list = list(enemies) if enemies is not None else []
        if not enemies_list:
            return

        for proj in list(projectiles):
            # Expect object-like projectiles with x/vel_x/vel_y attributes
            px = getattr(proj, "x", 0)
            py = getattr(proj, "y", 0)

            def get_vx(p):
                return getattr(p, "vel_x", 0)

            def get_vy(p):
                return getattr(p, "vel_y", 0)

            def set_v(p, vx, vy):
                p.vel_x = vx
                p.vel_y = vy

            closest_enemy = min(
                enemies_list,
                key=lambda e: math.hypot(_pos(e)[0] - px, _pos(e)[1] - py),
            )
            cx, cy = _pos(closest_enemy)
            dx = cx - px
            dy = cy - py
            dist = math.hypot(dx, dy)

            if dist > 0:
                target_vel_x = (dx / dist) * projectile_speed
                target_vel_y = (dy / dist) * projectile_speed

                current_speed = math.hypot(get_vx(proj), get_vy(proj))
                if current_speed > 0:
                    current_angle = math.atan2(get_vy(proj), get_vx(proj))
                    target_angle = math.atan2(target_vel_y, target_vel_x)
                    angle_diff = abs(target_angle - current_angle)
                    angle_diff = min(angle_diff, 2 * math.pi - angle_diff)
                    angle_diff_degrees = math.degrees(angle_diff)

                    if angle_diff_degrees <= 90:
                        # Reduce homing for ICE3 projectiles that have already hit their first enemy
                        homing_strength = 0.1
                        if (
                            hasattr(proj, "appearance")
                            and getattr(proj, "appearance", "") == "ice_statue"
                            and getattr(proj, "has_hit_first_enemy", False)
                        ):
                            homing_strength = 0.02  # Much weaker homing after first hit
                        new_vx = (
                            get_vx(proj) * (1 - homing_strength)
                            + target_vel_x * homing_strength
                        )
                        new_vy = (
                            get_vy(proj) * (1 - homing_strength)
                            + target_vel_y * homing_strength
                        )
                        set_v(proj, new_vx, new_vy)
                else:
                    homing_strength = 0.8
                    # Reduce homing for ICE3 projectiles that have already hit their first enemy
                    if (
                        hasattr(proj, "appearance")
                        and getattr(proj, "appearance", "") == "ice_statue"
                        and getattr(proj, "has_hit_first_enemy", False)
                    ):
                        homing_strength = 0.1  # Much weaker homing after first hit
                    new_vx = (
                        get_vx(proj) * (1 - homing_strength)
                        + target_vel_x * homing_strength
                    )
                    new_vy = (
                        get_vy(proj) * (1 - homing_strength)
                        + target_vel_y * homing_strength
                    )
                    set_v(proj, new_vx, new_vy)
