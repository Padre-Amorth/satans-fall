"""ProjectileManager with simple object pooling.

Responsibilities:
- Provide spawn API for creating projectiles (reusing instances when possible)
- Register existing projectiles so they are managed (when game code creates them directly)
- Recycle dead projectiles back to pools
- Provide update and draw helpers if needed
"""

from __future__ import annotations

import logging
from typing import List, Optional

from src.projectile import FliesProjectile, Projectile

logger = logging.getLogger(__name__)


class ProjectileManager:
    def __init__(self, game, initial_pool: int = 200) -> None:
        self.game = game
        # Simple pools for Projectile and FliesProjectile
        self.pool: List[Projectile] = []
        self.pool_flies: List[FliesProjectile] = []
        for _ in range(initial_pool):
            try:
                self.pool.append(Projectile(0, 0, 0, 0))
            except Exception:
                # In case pygame surfaces can't be created in headless env, ignore
                break
        self.active: List[Projectile] = []

    def spawn(
        self,
        x: float,
        y: float,
        vel_x: float,
        vel_y: float,
        damage: int = 15,
        radius: int = 5,
        is_enemy_projectile: bool = False,
        weapon_type: Optional[str] = None,
        source: Optional[str] = None,
        appearance: Optional[str] = None,
    ) -> Projectile:
        cls = FliesProjectile if weapon_type == "Flies" else Projectile
        if cls is Projectile:
            if self.pool:
                p = self.pool.pop()
                p.reset(
                    x,
                    y,
                    vel_x,
                    vel_y,
                    damage=damage,
                    radius=radius,
                    is_enemy_projectile=is_enemy_projectile,
                    weapon_type=weapon_type,
                    source=source,
                    appearance=appearance,
                )
            else:
                p = Projectile(
                    x,
                    y,
                    vel_x,
                    vel_y,
                    damage=damage,
                    radius=radius,
                    is_enemy_projectile=is_enemy_projectile,
                    weapon_type=weapon_type,
                    source=source,
                    appearance=appearance,
                )
        else:
            if self.pool_flies:
                p = self.pool_flies.pop()
                p.reset(
                    x,
                    y,
                    vel_x,
                    vel_y,
                    damage=damage,
                    radius=radius,
                    is_enemy_projectile=is_enemy_projectile,
                    weapon_type=weapon_type,
                    source=source,
                    appearance=appearance,
                )
            else:
                p = FliesProjectile(x, y, vel_x, vel_y, damage=damage)
                # FliesProjectile constructor sets needed fields
        # Attach manager reference
        p.manager = self

        # Add to game's projectiles container (Group or list)
        try:
            self.game.projectiles.add(p)
        except Exception:
            try:
                self.game.projectiles.append(p)
            except Exception:
                pass

        # Track active
        self.active.append(p)
        return p

    def register(self, p: Projectile) -> None:
        """Register an externally created projectile (set manager and track it)."""
        p.manager = self
        # Basic invariant: projectile should expose transient tracking fields
        try:
            assert hasattr(p, "_hit_ids"), "Registered projectile must have _hit_ids"
            assert hasattr(
                p, "_chain_applied"
            ), "Registered projectile must have _chain_applied"
        except AssertionError:
            logger.exception(
                "Projectile missing required transient attributes during register"
            )
        if p not in self.active:
            self.active.append(p)

    def recycle(self, p: Projectile) -> None:
        """Recycle a projectile instance back into the appropriate pool."""
        # Remove from active list if present
        try:
            if p in self.active:
                self.active.remove(p)
        except Exception:
            pass

        # Remove from game containers (if present)
        try:
            if hasattr(self.game.projectiles, "remove"):
                self.game.projectiles.remove(p)
        except Exception:
            try:
                # If list
                self.game.projectiles.remove(p)
            except Exception:
                pass

        # Clean up attributes and return to pool
        try:
            p.manager = None
            # Zero velocities and hide off-screen
            p.x = -9999
            p.y = -9999
            p.vel_x = 0
            p.vel_y = 0
            # Reset common attributes
            p.damage = 0
            p.pierce_all = False
            p.pierce_count = 0
            # Clear transient/stateful fields that must not persist across reuse
            try:
                p._hit_ids = set()
            except Exception:
                pass
            try:
                p._chain_applied = False
            except Exception:
                pass
        except Exception:
            pass

        # Sanity checks: pooled projectile must have transient state cleared
        try:
            assert (
                getattr(p, "_hit_ids", set()) == set()
            ), "Recycled projectile must have empty _hit_ids"
            assert (
                getattr(p, "_chain_applied", False) is False
            ), "Recycled projectile must have _chain_applied=False"
            assert p.manager is None, "Recycled projectile.manager must be None"
        except AssertionError:
            logger.exception("ProjectileManager.recycle invariant failed")
            # continue silently in production; assertions help catch regressions during development

        # Put into correct pool
        if isinstance(p, FliesProjectile):
            self.pool_flies.append(p)
        else:
            self.pool.append(p)

    def cleanup(self) -> None:
        """Optional periodic maintenance: prune pools if needed (not used yet)."""
        pass


__all__ = ["ProjectileManager"]
