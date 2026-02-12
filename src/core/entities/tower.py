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
        self.x = x
        self.y = y
        self.fire_rate = fire_rate
        self.projectile_speed = projectile_speed
        self.inaccuracy = inaccuracy
        self.damage = damage
        self.radius = radius
        self.tower_type = tower_type

    def fire_at_closest(self, enemies: Iterable[Any]) -> Optional[object]:
        """Return a projectile dict, or a list of projectile dicts, or None if no enemies."""
        enemies_list = list(enemies) if enemies is not None else []
        if not enemies_list:
            return None

        # Dispatch based on tower type
        if self.tower_type == "fire":
            return self._fire_single(enemies_list)
        elif self.tower_type == "storm":
            return self._fire_storm(enemies_list)
        elif self.tower_type == "ice":
            return self._fire_ice(enemies_list)
        else:
            return self._fire_single(enemies_list)

    def _fire_single(self, enemies_list: List[Any]) -> Optional[Projectile]:
        closest = min(
            enemies_list,
            key=lambda e: math.hypot(_pos(e)[0] - self.x, _pos(e)[1] - self.y),
        )
        cx, cy = _pos(closest)
        dx = cx - self.x
        dy = cy - self.y
        dist = math.hypot(dx, dy)
        if dist <= 0:
            return None

        angle = math.atan2(dy, dx) + random.uniform(-self.inaccuracy, self.inaccuracy)
        vel_x = math.cos(angle) * self.projectile_speed
        vel_y = math.sin(angle) * self.projectile_speed
        # Make Fire tower projectiles visually distinctive
        # Reduce fire projectile size but keep distinctive visuals
        new_radius = max(self.radius, 6)
        proj = Projectile(self.x, self.y, vel_x, vel_y, damage=self.damage, radius=new_radius, is_enemy_projectile=False, appearance="fire_statue")
        # Tag as statue projectile
        proj.source = "statue"

        # Fire towers apply burn (damage over time)
        proj.effect = "burn"
        proj.burn_duration = getattr(self, "burn_duration", 180)  # frames
        proj.burn_damage_per_second = getattr(self, "burn_damage_per_second", 4.0)
        return proj

    def _fire_storm(self, enemies_list: List[Any]) -> Optional[Projectile]:
        # Storm now fires a single aimed projectile (dark-blue appearance)
        closest = min(
            enemies_list,
            key=lambda e: math.hypot(_pos(e)[0] - self.x, _pos(e)[1] - self.y),
        )
        cx, cy = _pos(closest)
        dx = cx - self.x
        dy = cy - self.y
        dist = math.hypot(dx, dy)
        if dist <= 0:
            return None

        angle = math.atan2(dy, dx) + random.uniform(-self.inaccuracy, self.inaccuracy)
        vel_x = math.cos(angle) * self.projectile_speed
        vel_y = math.sin(angle) * self.projectile_speed
        p = Projectile(self.x, self.y, vel_x, vel_y, damage=max(1, int(self.damage * 0.9)), radius=self.radius, is_enemy_projectile=False, appearance="storm_statue")
        p.source = "statue"
        # Storm statue projectiles chain-hit up to 3 different enemies
        p.chain_targets = getattr(self, "chain_targets", 3)
        return p

    def _fire_ice(self, enemies_list: List[Any]) -> Optional[Projectile]:
        # Fire a single projectile that applies a slow effect on hit
        closest = min(
            enemies_list,
            key=lambda e: math.hypot(_pos(e)[0] - self.x, _pos(e)[1] - self.y),
        )
        cx, cy = _pos(closest)
        dx = cx - self.x
        dy = cy - self.y
        dist = math.hypot(dx, dy)
        if dist <= 0:
            return None

        angle = math.atan2(dy, dx) + random.uniform(-self.inaccuracy, self.inaccuracy)
        vel_x = math.cos(angle) * self.projectile_speed
        vel_y = math.sin(angle) * self.projectile_speed
        p = Projectile(self.x, self.y, vel_x, vel_y, damage=self.damage, radius=self.radius, is_enemy_projectile=False)
        p.source = "statue"
        p.appearance = "ice_statue"
        # Add slow effect metadata used by collision handling
        p.effect = "slow"
        p.slow_duration = 120
        p.slow_factor = 0.5
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
    def apply_homing(projectiles: List[Any], enemies: Iterable[Any], projectile_speed: float = 320.0) -> None:
        """Apply homing to projectiles.

        Accepts either dict-like projectiles or Projectile instances. Mutates velocities in-place.
        """
        enemies_list = list(enemies) if enemies is not None else []
        if not enemies_list:
            return

        for proj in list(projectiles):
            # Support dicts or objects
            if isinstance(proj, dict):
                px = proj.get("x", 0)
                py = proj.get("y", 0)
                get_vx = lambda p: p.get("vel_x", 0)
                get_vy = lambda p: p.get("vel_y", 0)
                set_v = lambda p, vx, vy: (p.__setitem__("vel_x", vx), p.__setitem__("vel_y", vy))
            else:
                px = getattr(proj, "x", 0)
                py = getattr(proj, "y", 0)
                get_vx = lambda p: getattr(p, "vel_x", 0)
                get_vy = lambda p: getattr(p, "vel_y", 0)
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
                        homing_strength = 0.1
                        new_vx = get_vx(proj) * (1 - homing_strength) + target_vel_x * homing_strength
                        new_vy = get_vy(proj) * (1 - homing_strength) + target_vel_y * homing_strength
                        set_v(proj, new_vx, new_vy)
                else:
                    homing_strength = 0.8
                    new_vx = get_vx(proj) * (1 - homing_strength) + target_vel_x * homing_strength
                    new_vy = get_vy(proj) * (1 - homing_strength) + target_vel_y * homing_strength
                    set_v(proj, new_vx, new_vy)
