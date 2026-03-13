"""Collision detection system extracted from Game."""

from __future__ import annotations

import logging
import math
import random
from typing import TYPE_CHECKING, Any, Dict, List

import pygame

from src.balance import ENEMY_SCORE_PER_HEALTH
from src.entities.enemy import BurnParticle, IceParticle
from src.weapons import tenebrae_damage

if TYPE_CHECKING:
    from src.game import Game

LOG = logging.getLogger(__name__)


class CollisionSystem:
    """Handles all collision detection and resolution.

    Operates on game state via a reference to the Game instance.
    """

    def __init__(self, game: "Game") -> None:
        self.game = game

    # helper to avoid repeating slow logic in multiple branches
    def _apply_slow_effect(
        self,
        enemy: Any,
        slow_duration: float,
        slow_factor: float,
        extend: bool = False,
    ) -> None:
        """Apply or extend a slow effect to an enemy.

        Supports both object-style enemies (attributes) and dictionary-style
        entries.  When ``extend`` is False the slow is only applied if the
        target is not currently slowed.  When ``extend`` is True the duration
        will be maximised and the factor minimised (used by ICE3/area-damage
        code paths).
        """
        try:
            if isinstance(enemy, dict):
                cur_timer = float(enemy.get("slow_timer", 0))
                cur_factor = float(enemy.get("slow_factor", 1.0))
                if extend:
                    # combine durations/factors but still update speed
                    new_timer = max(cur_timer, slow_duration)
                    new_factor = min(cur_factor, slow_factor)
                else:
                    if cur_timer > 0:
                        return
                    new_timer = slow_duration
                    new_factor = slow_factor
                enemy["slow_timer"] = new_timer
                enemy["slow_factor"] = new_factor
                if "original_speed" not in enemy:
                    enemy["original_speed"] = enemy.get("speed", 0)
                # always update speed based on the new factor
                enemy["speed"] = enemy.get("original_speed", 0) * new_factor
            else:
                # object-style
                cur_timer = getattr(enemy, "slow_timer", 0)
                cur_factor = getattr(enemy, "slow_factor", 1.0)
                if extend:
                    # combine durations/factors but still update speed
                    new_timer = max(cur_timer, slow_duration)
                    new_factor = min(cur_factor, slow_factor)
                    enemy.slow_timer = new_timer
                    enemy.slow_factor = new_factor
                else:
                    if cur_timer > 0:
                        return
                    enemy.slow_timer = slow_duration
                    enemy.slow_factor = slow_factor
                if not hasattr(enemy, "original_speed"):
                    enemy.original_speed = getattr(enemy, "speed", 0)
                # update speed regardless of whether we extended or applied
                enemy.speed = enemy.original_speed * getattr(enemy, "slow_factor", 1.0)
        except (AttributeError, TypeError, ValueError, KeyError):
            # swallow errors so collision handling remains robust
            pass

    def _maybe_charge_tower(self, projectile: Any, hits: int = 1) -> None:
        """Increment tower energy for statue projectile hits.

        ``hits`` allows batching multiple charges (e.g. storm chains).
        """
        try:
            if getattr(projectile, "source", None) != "statue":
                return
            # ensure unlock exists for this tower type
            tp = getattr(projectile, "tower_type", None)
            if tp is None:
                return
            if not self.game.permanent_stats.get(f"{tp}_7", 0):
                return
            amt = getattr(self.game, "tower_energy_per_hit", 0) * hits
            try:
                self.game.charge_tower_energy(amt)
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def _projectile_radius(self, proj: Any) -> int:
        """Return radius for a projectile object.

        - Handles Projectile instances and objects with a `rect`.
        """
        r = getattr(proj, "radius", None)
        if r is not None:
            try:
                return int(r)
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
        rect = getattr(proj, "rect", None)
        if rect is not None:
            try:
                return int(rect.width // 2)
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
        return 5

    def _get_projectile_metadata(self, projectile: Any) -> Dict[str, Any]:
        """Normalize commonly used projectile metadata into a dict for tests.

        Returns: { effect, slow_duration, slow_factor, burn_duration, burn_dps }
        """
        g = self.game
        effect = getattr(projectile, "effect", None)
        slow_duration = getattr(projectile, "slow_duration", 120)
        slow_factor = getattr(projectile, "slow_factor", 0.5)
        burn_duration = getattr(projectile, "burn_duration", 180)
        burn_dps = getattr(projectile, "burn_damage_per_second", 4.0)
        # Permanent upgrade interaction (fire_2) - double burn effects
        if getattr(g, "permanent_stats", None) and g.permanent_stats.get("fire_2", 0):
            try:
                burn_duration = int(burn_duration * 2)
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
            try:
                burn_dps = burn_dps * 2
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
        return {
            "effect": effect,
            "slow_duration": slow_duration,
            "slow_factor": slow_factor,
            "burn_duration": burn_duration,
            "burn_dps": burn_dps,
        }

    def _get_hit_enemies_for_projectile(self, projectile: Any) -> list[Any]:
        """Return enemies hit by projectile (supports dict/list and Group).

        - Uses spatial_grid when available; otherwise falls back to pygame.sprite
          collision or manual list scanning.
        """
        g = self.game
        hit_enemies: list[Any] = []
        try:
            px = float(getattr(projectile, "x", 0))
            py = float(getattr(projectile, "y", 0))
            # keep rect in sync for pygame.sprite collisions
            try:
                if hasattr(projectile, "rect"):
                    projectile.rect.center = (int(px), int(py))
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
            pr = self._projectile_radius(projectile)
            sg = getattr(g, "spatial_grid", None)
            if sg is not None:
                candidates = sg.query_circle(px, py, pr)
            else:
                candidates = []
            for enemy in candidates:
                ex, ey = g._enemy_pos(enemy)
                er = g._enemy_radius(enemy)
                dx = ex - px
                dy = ey - py
                if dx * dx + dy * dy <= (pr + er) * (pr + er):
                    hit_enemies.append(enemy)
            if not hit_enemies:
                # Try pygame Group collision when possible
                if hasattr(g.enemies, "sprites") and hasattr(projectile, "rect"):
                    hit_enemies = pygame.sprite.spritecollide(
                        projectile, g.enemies, False
                    )
                else:
                    try:
                        for enemy in g.enemies:
                            ex, ey = g._enemy_pos(enemy)
                            er = g._enemy_radius(enemy)
                            dx = ex - px
                            dy = ey - py
                            if dx * dx + dy * dy <= (pr + er) * (pr + er):
                                hit_enemies.append(enemy)
                    except (AttributeError, TypeError, ValueError):
                        hit_enemies = []
        except (AttributeError, TypeError, KeyError):
            hit_enemies = []
        return hit_enemies

    def _build_spatial_grid(self) -> None:
        """Create or rebuild the SpatialGrid used by collision queries (test helper)."""
        g = self.game
        try:
            from src.utils.spatial_grid import SpatialGrid

            enemies_iter = g._enemies_iter()
            if not hasattr(g, "spatial_grid") or g.spatial_grid is None:
                cell_size = getattr(g, "spatial_grid_cell_size", 120)
                g.spatial_grid = SpatialGrid(
                    cell_size=cell_size, width=g.width, height=g.height
                )
            try:
                g.spatial_grid.build(enemies_iter)
            except (AttributeError, TypeError, ValueError, KeyError):
                g.spatial_grid = None
        except (AttributeError, TypeError, ValueError, KeyError):
            g.spatial_grid = None

    def _remove_offscreen_projectiles(self) -> None:
        """Remove projectiles that left the screen (Group or list).

        Kept simple for tests: remove sprites whose y is offscreen and filter lists.
        """
        g = self.game
        projs = getattr(g, "projectiles", [])
        # Group-based
        if hasattr(projs, "sprites"):
            for p in list(projs):
                try:
                    if getattr(p, "y", None) is not None and p.y < 0:
                        p.kill()
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
        else:
            projs = [
                p
                for p in list(projs)
                if not (getattr(p, "y", None) is not None and p.y < 0)
            ]
            g.projectiles = projs

    def _apply_ice_puddles(self):
        """Apply slowing effect from active ice puddles to nearby enemies (test helper)."""
        g = self.game
        try:
            for puddle in getattr(g, "ice_puddles", []) or []:
                if puddle.get("timer", 0) <= 0:
                    continue
                px = float(puddle.get("x", 0))
                py = float(puddle.get("y", 0))
                pr = float(puddle.get("radius", 0))
                slow_factor = float(puddle.get("slow_factor", 0.5))
                for enemy in g._enemies_iter():
                    try:
                        ex, ey = g._enemy_pos(enemy)
                        if (ex - px) ** 2 + (ey - py) ** 2 <= pr * pr:
                            if not hasattr(enemy, "original_speed"):
                                enemy.original_speed = getattr(enemy, "speed", 0)
                            enemy.speed = enemy.original_speed * slow_factor
                            enemy.slow_factor = slow_factor
                    except (AttributeError, TypeError, ValueError, KeyError):
                        # ignore per-enemy errors when applying puddle slow
                        pass
                # Bosses
                try:
                    if hasattr(g, "bosses") and g.bosses:
                        bosses = (
                            g.bosses.sprites()
                            if hasattr(g.bosses, "sprites")
                            else list(g.bosses)
                        )
                        for boss in bosses:
                            bx, by = g._enemy_pos(boss)
                            if (bx - px) ** 2 + (by - py) ** 2 <= pr * pr:
                                if not hasattr(boss, "original_speed"):
                                    boss.original_speed = getattr(boss, "speed", 0)
                                boss.speed = boss.original_speed * slow_factor
                                boss.slow_factor = slow_factor
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def _propagate_burn(self, source_enemy):
        """Propagate a burn from source_enemy to nearby enemies.

        - Uses propagation parameters set on the source (radius, dps, duration).
        - Applies burn to nearby enemies but does NOT schedule further propagation
          (prevents infinite chaining).
        - Handles both dict-based and sprite-based enemies.
        """
        g = self.game
        # Support both dict-based and sprite/object-based enemies as the source.
        try:
            if isinstance(source_enemy, dict):
                radius = float(source_enemy.get("burn_propagate_radius", 0))
                dps = float(source_enemy.get("burn_propagate_dps", 0))
                duration = int(source_enemy.get("burn_propagate_duration", 0))
                source_hops = int(source_enemy.get("burn_propagate_hops", 0))
            else:
                radius = float(getattr(source_enemy, "burn_propagate_radius", 0))
                dps = float(getattr(source_enemy, "burn_propagate_dps", 0))
                duration = int(getattr(source_enemy, "burn_propagate_duration", 0))
                source_hops = int(getattr(source_enemy, "burn_propagate_hops", 0))
        except (AttributeError, TypeError, ValueError, KeyError):
            return

        if radius <= 0 or dps <= 0 or duration <= 0:
            return

        # Find nearby enemies and apply burn to them (excluding the source)
        for other in g._enemies_iter():
            # Skip the source itself
            if other is source_enemy:
                continue

            ox, oy = g._enemy_pos(other)
            sx, sy = g._enemy_pos(source_enemy)
            dist_sq = (ox - sx) ** 2 + (oy - sy) ** 2
            if dist_sq <= radius * radius:
                # Apply burn to dict-based enemies
                if isinstance(other, dict):
                    # only apply if not already burning
                    if other.get("burn_timer", 0) <= 0:
                        other["burn_timer"] = duration
                        other["burn_damage_per_second"] = dps
                        other["burn_tick_counter"] = getattr(g, "fps", 60)
                        # If the source has hops remaining, allow this propagated burn to
                        # further propagate when that enemy dies (chain behavior).
                        if source_hops > 0:
                            new_hops = max(0, source_hops - 1)
                            other["burn_propagate_hops"] = new_hops
                            if new_hops > 0:
                                other["burn_propagate_on_death"] = True
                                other["burn_propagate_radius"] = radius
                                other["burn_propagate_dps"] = dps
                                other["burn_propagate_duration"] = duration
                        # Spawn a small floating text to indicate propagation (best-effort)
                        try:
                            ex, ey = g._enemy_pos(other)
                            g.spawn_floating_text(
                                "burn", ex, ey - other.get("radius", 12) - 8
                            )
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                else:
                    # sprite-based enemy objects
                    if (
                        not hasattr(other, "burn_timer")
                        or getattr(other, "burn_timer", 0) <= 0
                    ):
                        other.burn_timer = duration
                        other.burn_damage_per_second = dps
                        other.burn_tick_timer = getattr(g, "fps", 60)
                        # If the source has hops remaining, allow chaining for sprite enemies too
                        if source_hops > 0:
                            new_hops = max(0, source_hops - 1)
                            try:
                                other.burn_propagate_hops = new_hops
                                if new_hops > 0:
                                    other.burn_propagate_on_death = True
                                    other.burn_propagate_radius = radius
                                    other.burn_propagate_dps = dps
                                    other.burn_propagate_duration = duration
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass
                        try:
                            g.spawn_floating_text(
                                "burn",
                                other.x,
                                other.y - getattr(other, "radius", 12) - 8,
                            )
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                        # Visual: orange chain from source -> target
                        try:
                            sx, sy = g._enemy_pos(source_enemy)
                            ex, ey = g._enemy_pos(other)
                            g.game_state.chain_lightning_effects.append(
                                {
                                    "points": [(sx, sy), (ex, ey)],
                                    "timer": 6,
                                    "color": (255, 140, 0),
                                }
                            )
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
        # Also consider boss sprites separately (they're stored in g.bosses).
        # Bosses are sprite-based; apply the same propagation logic as above.
        if hasattr(g, "bosses") and getattr(g, "bosses", None):
            try:
                boss_list = (
                    g.bosses.sprites()
                    if hasattr(g.bosses, "sprites")
                    else list(g.bosses)
                )
                for other in boss_list:
                    # Skip source if it's the same object/dict
                    if other is source_enemy:
                        continue
                    ox, oy = g._enemy_pos(other)
                    sx, sy = g._enemy_pos(source_enemy)
                    dist_sq = (ox - sx) ** 2 + (oy - sy) ** 2
                    if dist_sq <= radius * radius:
                        # Apply burn to boss sprites (if not already burning)
                        if (
                            not hasattr(other, "burn_timer")
                            or getattr(other, "burn_timer", 0) <= 0
                        ):
                            other.burn_timer = duration
                            other.burn_damage_per_second = dps
                            other.burn_tick_timer = getattr(g, "fps", 60)
                            if source_hops > 0:
                                new_hops = max(0, source_hops - 1)
                                try:
                                    other.burn_propagate_hops = new_hops
                                    if new_hops > 0:
                                        other.burn_propagate_on_death = True
                                        other.burn_propagate_radius = radius
                                        other.burn_propagate_dps = dps
                                        other.burn_propagate_duration = duration
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                            try:
                                g.spawn_floating_text(
                                    "burn",
                                    other.x,
                                    other.y - getattr(other, "radius", 12) - 8,
                                )
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass
                            # Visual: small orange chain effect boss <- source
                            try:
                                g.game_state.chain_lightning_effects.append(
                                    {
                                        "points": [(sx, sy), (ox, oy)],
                                        "timer": 6,
                                        "color": (255, 140, 0),
                                    }
                                )
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

    def _floating_text_style_for_projectile(
        self, projectile, base_color=(255, 255, 255), base_font_size: int = 20
    ) -> tuple:
        """Return (color, font_size) for floating damage text for a projectile hit.

        If the projectile carried a critical hit marker (set by
        _player_damage_vs_burning), return a red color and slightly larger font.
        """
        try:
            is_crit = False
            if isinstance(projectile, dict):
                is_crit = bool(projectile.get("_was_critical", False))
            else:
                is_crit = bool(getattr(projectile, "_was_critical", False))
            if is_crit:
                # Red and slightly larger
                return ((255, 50, 50), max(12, base_font_size + 2))
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        return (base_color, base_font_size)

    @staticmethod
    def _elemental_shield_can_damage(enemy: Any, projectile: Any) -> bool:
        """Return True if projectile is allowed to damage the elemental shield.

        Elemental pentagram variants have shields immune to all damage except
        from the matching tower type.  Once shield_hp reaches 0 the body HP
        is vulnerable to every source.  Non-elemental enemies always return True.

        IMPORTANT: This check MUST be applied consistently in ALL code paths,
        including fallback handlers and exception cases. If this returns False,
        NO damage of any kind should be applied to the enemy.
        """
        etype = getattr(enemy, "enemy_type", "")
        if etype not in ("pentagram_fire", "pentagram_storm", "pentagram_ice"):
            return True
        if getattr(enemy, "shield_hp", 0) <= 0:
            return True  # shield gone — all sources can damage body HP
        tower_type = getattr(projectile, "tower_type", None)
        if etype == "pentagram_fire":
            return tower_type == "fire"
        elif etype == "pentagram_storm":
            return tower_type == "storm"
        elif etype == "pentagram_ice":
            return tower_type == "ice"
        return True

    def _show_immune_text(self, enemy: Any) -> None:
        """Display IMMUNE floating text when elemental shield blocks damage."""
        try:
            g = self.game
            ex, ey = g._enemy_pos(enemy)
            g.floating_texts.append(
                {
                    "text": "IMMUNE",
                    "x": ex,
                    "y": ey - 30,
                    "vx": 0,
                    "vy": -2,
                    "lifetime": 30,
                    "color": (200, 200, 200),
                    "size": 14,
                }
            )
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def _player_damage_vs_burning(self, projectile, enemy, base_damage: int) -> int:
        """Return adjusted damage for player projectiles.

        Applies these per-player-projectile modifiers in priority order:
        1. FIRE tier-3 bonus vs burning enemies (+25% dmg)
        2. BLASPHEMY_6 critical hit (chance = 10% * level, damage = +50%)

        The helper is safe to call for non-player projectiles (it will return
        base_damage unchanged).
        """
        g = self.game
        try:
            # Reset transient crit marker on the projectile so callers can
            # consult it (used by floating-text styling).
            try:
                if isinstance(projectile, dict):
                    projectile["_was_critical"] = False
                else:
                    setattr(projectile, "_was_critical", False)
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

            # Only consider non-enemy projectiles.  Statues are normally
            # excluded, unless they belong to a fire tower with right-column
            # upgrades (those should be allowed to crit).  We start by assuming
            # non-enemy projectiles are valid, then turn off the flag for a
            # statue that doesn't meet the extra condition.
            is_player_proj = not getattr(projectile, "is_enemy_projectile", False)
            if getattr(projectile, "source", None) == "statue":
                # statue projectiles are normally ignored; however, fire and storm
                # towers gain crit chance from their right-column tiers so we need
                # to let those shots pass through the player/crit logic when any
                # such tier is active.
                ttype = getattr(projectile, "tower_type", None)
                if ttype in ("fire", "storm"):
                    right_count = sum(
                        self.game.permanent_stats.get(f"{ttype}_{i}", 0)
                        for i in (4, 5, 6)
                    )
                    if not right_count:
                        is_player_proj = False
                else:
                    is_player_proj = False

            # FIRE tier-3: bonus vs burning enemies (highest priority)
            try:
                if is_player_proj and g.permanent_stats.get("fire_3", 0):
                    if getattr(enemy, "burn_timer", 0) > 0:
                        return int(round(base_damage * 1.25))
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

            # Critical hit mechanic:
            #   * BLASPHEMY_6 grants +50% damage on crit, +10% crit chance per level
            #   * ADRENALINE grants +2% crit chance per level (applies even with no blasphemy)
            try:
                if is_player_proj:
                    base_chance = float(g.permanent_stats.get("blasphemy_6", 0)) * 0.10
                    adrenaline_bonus = (
                        float(g.permanent_stats.get("adrenaline", 0)) * 0.02
                    )
                    # additional crit chance from right-column slots on tower projectiles
                    extra_crit = 0.0
                    ttype = getattr(projectile, "tower_type", None)
                    if ttype == "fire":
                        extra_crit += (
                            sum(
                                g.permanent_stats.get(f"fire_{i}", 0) for i in (4, 5, 6)
                            )
                            * 0.10
                        )
                    elif ttype == "storm":
                        extra_crit += (
                            sum(
                                g.permanent_stats.get(f"storm_{i}", 0)
                                for i in (4, 5, 6)
                            )
                            * 0.10
                        )
                    chance = min(1.0, base_chance + adrenaline_bonus + extra_crit)
                    if chance > 0 and random.random() < chance:
                        try:
                            if isinstance(projectile, dict):
                                projectile["_was_critical"] = True
                            else:
                                setattr(projectile, "_was_critical", True)
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                        return int(round(base_damage * 1.5))
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        return base_damage

    def handle_collisions(self) -> None:
        """Handle all collision detection"""
        g = self.game

        # Build or update spatial grid for enemies (reused if present)
        try:
            from src.utils.spatial_grid import SpatialGrid

            enemies_iter = g._enemies_iter()
            if not hasattr(g, "spatial_grid") or g.spatial_grid is None:
                # Use configurable cell size
                cell_size = getattr(g, "spatial_grid_cell_size", 120)
                g.spatial_grid = SpatialGrid(
                    cell_size=cell_size, width=g.width, height=g.height
                )
            # Build grid from current enemy positions
            try:
                g.spatial_grid.build(enemies_iter)
            except (AttributeError, TypeError, ValueError, KeyError):
                # If building fails, fall back to not using the grid
                g.spatial_grid = None
        except (AttributeError, TypeError, ValueError, KeyError):
            g.spatial_grid = None

        # Projectiles hit enemies
        for projectile in list(g.projectiles):
            try:
                LOG.debug(
                    "handle_collisions: processing projectile id=%s appearance=%s effect=%s rect=%s",
                    id(projectile),
                    getattr(projectile, "appearance", None),
                    getattr(projectile, "effect", None),
                    getattr(projectile, "rect", None),
                )
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
            primary_target = None
            # Projectile metadata (object-only canonical representation)
            effect = getattr(projectile, "effect", None)
            slow_duration = getattr(projectile, "slow_duration", 120)
            slow_factor = getattr(projectile, "slow_factor", 0.5)
            burn_duration = getattr(projectile, "burn_duration", 180)
            burn_dps = getattr(projectile, "burn_damage_per_second", 4.0)
            # FIRE left-column tier 2: double burn duration and burn DPS
            if getattr(g, "permanent_stats", None) and g.permanent_stats.get(
                "fire_2", 0
            ):
                try:
                    burn_duration = int(burn_duration * 2)
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
                try:
                    burn_dps = burn_dps * 2
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
            # Flag to indicate we've processed this projectile via the spatial-grid branch
            processed_projectile = False
            # Ensure we always have an iterable for hit enemies
            hit_enemies: list[Any] = []

            hit_enemies = self._get_hit_enemies_for_projectile(projectile)
            # Cache projectile position for later use (ice puddles, nearest-target, etc.)
            px = getattr(projectile, "x", 0)
            py = getattr(projectile, "y", 0)
            pr = self._projectile_radius(projectile)

            # Hell barrier collision: player projectiles consumed by barriers
            if getattr(g, "barriers", []):
                proj_rect = getattr(projectile, "rect", None)
                hit_barrier = False
                for b in g.barriers:
                    if proj_rect is not None:
                        hit = b["rect"].colliderect(proj_rect)
                    else:
                        cx, cy = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
                        hit = (
                            abs(px - cx) < b["w"] / 2 + pr
                            and abs(py - cy) < b["h"] / 2 + pr
                        )
                    if hit:
                        # Get projectile damage (apply burning bonus if applicable)
                        try:
                            dmg = self._player_damage_vs_burning(
                                projectile, None, getattr(projectile, "damage", 10)
                            )
                        except Exception:
                            dmg = getattr(projectile, "damage", 10)
                        b["hp"] -= dmg
                        try:
                            projectile.kill()
                        except Exception:
                            try:
                                g.projectiles.remove(projectile)
                            except Exception:
                                pass
                        hit_barrier = True
                        break
                if hit_barrier:
                    continue  # skip all enemy-hit logic for this projectile

            # For SkullBooms and ice projectiles, also check collision with bosses
            if getattr(projectile, "weapon_type", None) == "skullboom" or (
                getattr(projectile, "appearance", None) == "ice_statue"
                and hasattr(projectile, "explosion_radius")
            ):
                if hasattr(g, "bosses") and g.bosses:
                    if hasattr(g.bosses, "sprites") and hasattr(projectile, "rect"):
                        boss_hits = pygame.sprite.spritecollide(
                            projectile, g.bosses, False
                        )
                        hit_enemies.extend(boss_hits)
                    elif hasattr(
                        projectile, "x"
                    ):  # Check distance-based collision with bosses
                        px = getattr(projectile, "x", 0)
                        py = getattr(projectile, "y", 0)
                        pr = getattr(projectile, "radius", 5)
                        for boss in g.bosses:
                            if hasattr(boss, "x") and hasattr(boss, "y"):
                                bx, by = boss.x, boss.y
                                br = getattr(boss, "radius", 20)
                                dx = bx - px
                                dy = by - py
                                if dx * dx + dy * dy <= (pr + br) * (pr + br):
                                    hit_enemies.append(boss)

            # Prefer the nearest hit candidate to be processed as primary (avoid multiple targets in same frame)
            try:
                if len(hit_enemies) > 1:
                    # Allow multi-hit for statues / piercing projectiles (ICE3, spear-like behaviour)
                    appearance = getattr(projectile, "appearance", None)
                    # Only treat ice projectiles as multi-hit when ICE3 (piercing) is active;
                    # storm statues still chain by design.
                    is_statue = appearance == "storm_statue" or (
                        appearance == "ice_statue" and g.permanent_stats.get("ice_3", 0)
                    )
                    pierce_attr = (
                        getattr(projectile, "pierce_all", False)
                        or getattr(projectile, "pierce_count", 0) > 0
                    )
                    # If not a special multi-hit projectile, prefer the nearest target only
                    if not (is_statue or pierce_attr):
                        px = getattr(projectile, "x", 0)
                        py = getattr(projectile, "y", 0)
                        # Optimization: use min() instead of sort to find nearest enemy
                        if hit_enemies:
                            nearest = min(
                                hit_enemies,
                                key=lambda e: (
                                    (g._enemy_pos(e)[0] - px) ** 2
                                    + (g._enemy_pos(e)[1] - py) ** 2
                                ),
                            )
                            hit_enemies = [nearest]
                    try:
                        # Debug: hit candidates filtered
                        pass
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

            # ICE projectile: if it hit any enemy, ensure ICE3 first-hit flag is set
            if getattr(projectile, "appearance", None) == "ice_statue" and hit_enemies:
                # If ICE3 is active, mark this projectile as having hit its first enemy
                if g.permanent_stats.get("ice_3", 0) and not hasattr(
                    projectile, "has_hit_first_enemy"
                ):
                    projectile.has_hit_first_enemy = True

            # Special handling for ice projectiles with area damage
            if getattr(projectile, "appearance", None) == "ice_statue" and hit_enemies:
                # Check if ICE3 is active for piercing behavior
                ice3_active = g.permanent_stats.get("ice_3", 0)

                if ice3_active:
                    # ICE3: First hit creates puddle and area damage, then pierces with direct damage + slow
                    has_exploded = getattr(projectile, "has_exploded", False)

                    # Initialize hit tracking if not exists
                    if not hasattr(projectile, "hit_enemy_ids"):
                        projectile.hit_enemy_ids = set()

                    # Apply direct damage + slow to hit enemies (only once per enemy)
                    for enemy in hit_enemies:
                        # Create unique enemy ID
                        enemy_id = id(enemy)

                        # Skip if already hit by this projectile
                        if enemy_id in projectile.hit_enemy_ids:
                            continue

                        # Mark as hit
                        projectile.hit_enemy_ids.add(enemy_id)

                        try:
                            # Apply damage (route through helper so FIRE_3 / BLASPHEMY_6 apply)
                            dmg_to_apply = self._player_damage_vs_burning(
                                projectile, enemy, getattr(projectile, "damage", 0)
                            )
                            if id(enemy) in getattr(projectile, "_hit_ids", set()):
                                pass
                            elif self._elemental_shield_can_damage(enemy, projectile):
                                try:
                                    LOG.debug(
                                        "handle_collisions ICE3-hit: proj_id=%s effect=%s enemy_id=%s pre_hit_ids=%s",
                                        id(projectile),
                                        getattr(projectile, "effect", None),
                                        id(enemy),
                                        getattr(projectile, "_hit_ids", None),
                                    )
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                                enemy.take_damage(dmg_to_apply, show_floating=False)
                                # Apply slow effect (object-style / dict) for ICE3 hits.
                                slow_duration = getattr(
                                    projectile, "slow_duration", 120
                                )
                                slow_factor = getattr(projectile, "slow_factor", 0.5)
                                self._apply_slow_effect(
                                    enemy, slow_duration, slow_factor, extend=True
                                )
                                try:
                                    ex, ey = g._enemy_pos(enemy)
                                    (
                                        final_color,
                                        final_font,
                                    ) = self._floating_text_style_for_projectile(
                                        projectile, (100, 200, 255), 20
                                    )
                                    g.spawn_floating_text(
                                        str(dmg_to_apply),
                                        ex,
                                        ey - g._enemy_radius(enemy) - 8,
                                        color=final_color,
                                        font_size=final_font,
                                    )
                                    try:
                                        if isinstance(projectile, dict):
                                            projectile["_was_critical"] = False
                                        else:
                                            setattr(projectile, "_was_critical", False)
                                    except (
                                        AttributeError,
                                        TypeError,
                                        ValueError,
                                        KeyError,
                                    ):
                                        pass
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                            else:
                                self._show_immune_text(enemy)
                                # ICE3 piercing also counts as tower hits
                                try:
                                    self._maybe_charge_tower(projectile)
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                                try:
                                    LOG.debug(
                                        "handle_collisions ICE3-hit-done: proj_id=%s enemy_id=%s post_hit_ids=%s",
                                        id(projectile),
                                        id(enemy),
                                        getattr(projectile, "_hit_ids", None),
                                    )
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass

                    # Ensure _hit_ids includes hit_enemy_ids so the subsequent explosion
                    # doesn't damage the same enemies again
                    if not hasattr(projectile, "_hit_ids"):
                        projectile._hit_ids = set()
                    projectile._hit_ids.update(
                        getattr(projectile, "hit_enemy_ids", set())
                    )

                    # First hit: create explosion and puddle (only if this projectile has ICE1 / area effect)
                    if not has_exploded and (
                        hasattr(projectile, "explosion_radius")
                        or g.permanent_stats.get("ice_1", 0)
                    ):
                        # Create ice explosion particles
                        num_particles = random.randint(8, 12)
                        for _ in range(num_particles):
                            angle = random.uniform(0, 2 * math.pi)
                            speed = random.uniform(20, 100)
                            vx = math.cos(angle) * speed
                            vy = math.sin(angle) * speed
                            offset_x = random.uniform(-5, 5)
                            offset_y = random.uniform(-5, 5)
                            try:
                                life = random.randint(15, 30)
                                size = random.randint(2, 5)
                                p_ice = IceParticle(
                                    px + offset_x,
                                    py + offset_y,
                                    vx,
                                    vy,
                                    life=life,
                                    size=size,
                                )
                                g.ice_particles.append(p_ice)
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass

                        # Create ice puddle at impact point
                        puddle_radius = 40
                        if g.permanent_stats.get("ice_2", 0):
                            puddle_radius = int(40 * 1.5)  # 60 with ice_2 upgrade
                        g.ice_puddles.append(
                            {
                                "x": px,
                                "y": py,
                                "radius": puddle_radius,  # Puddle radius
                                "timer": 5 * 60,  # 5 seconds at 60 FPS
                                "slow_factor": 0.5,  # 50% speed reduction
                                "slow_duration": 30,  # 0.5 seconds slow when entering puddle
                            }
                        )

                        # Mark projectile so explosion/puddle happen only once
                        try:
                            setattr(projectile, "has_exploded", True)
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass

                        # Damage and slow all enemies within explosion radius
                        explosion_radius = getattr(
                            projectile, "explosion_radius", puddle_radius
                        )
                        all_targets = []
                        all_targets.extend(g.enemies)
                        if hasattr(g, "bosses") and g.bosses:
                            if hasattr(g.bosses, "sprites"):
                                all_targets.extend(g.bosses.sprites())
                            else:
                                all_targets.extend(g.bosses)

                        for enemy in all_targets:
                            ex, ey = g._enemy_pos(enemy)
                            dx = ex - px
                            dy = ey - py
                            dist_sq = dx * dx + dy * dy
                            if dist_sq <= explosion_radius * explosion_radius:
                                try:
                                    # Apply damage (route through helper so FIRE_3 / BLASPHEMY_6 apply)
                                    dmg_to_apply = self._player_damage_vs_burning(
                                        projectile,
                                        enemy,
                                        getattr(projectile, "damage", 0),
                                    )
                                    if id(enemy) in getattr(
                                        projectile, "_hit_ids", set()
                                    ):
                                        pass
                                    elif self._elemental_shield_can_damage(
                                        enemy, projectile
                                    ):
                                        enemy.take_damage(
                                            dmg_to_apply, show_floating=False
                                        )
                                        # charge energy for each successful hit
                                        try:
                                            self._maybe_charge_tower(projectile)
                                        except (
                                            AttributeError,
                                            TypeError,
                                            ValueError,
                                            KeyError,
                                        ):
                                            pass

                                        # Apply slow effect (object or dict) for explosion-area
                                        slow_duration = getattr(
                                            projectile, "slow_duration", 120
                                        )
                                        slow_factor = getattr(
                                            projectile, "slow_factor", 0.5
                                        )
                                        self._apply_slow_effect(
                                            enemy,
                                            slow_duration,
                                            slow_factor,
                                            extend=True,
                                        )

                                        try:
                                            ex, ey = g._enemy_pos(enemy)
                                            (
                                                final_color,
                                                final_font,
                                            ) = self._floating_text_style_for_projectile(
                                                projectile, (100, 200, 255), 20
                                            )
                                            g.spawn_floating_text(
                                                str(dmg_to_apply),
                                                ex,
                                                ey - g._enemy_radius(enemy) - 8,
                                                color=final_color,
                                                font_size=final_font,
                                            )
                                            try:
                                                setattr(
                                                    projectile, "_was_critical", False
                                                )
                                            except (
                                                AttributeError,
                                                TypeError,
                                                ValueError,
                                                KeyError,
                                            ):
                                                pass
                                        except (
                                            AttributeError,
                                            TypeError,
                                            ValueError,
                                            KeyError,
                                        ):
                                            pass
                                    else:
                                        self._show_immune_text(enemy)
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                    # If explosion was not applicable (no ICE1), fall through to normal processing
                    continue  # Skip normal processing
                else:
                    # Create ice explosion particles (visual only)
                    num_particles = random.randint(8, 12)
                    for _ in range(num_particles):
                        angle = random.uniform(0, 2 * math.pi)
                        speed = random.uniform(20, 100)
                        vx = math.cos(angle) * speed
                        vy = math.sin(angle) * speed
                    offset_x = random.uniform(-5, 5)
                    offset_y = random.uniform(-5, 5)
                    try:
                        life = random.randint(15, 30)
                        size = random.randint(2, 5)
                        p_ice_local = IceParticle(
                            px + offset_x, py + offset_y, vx, vy, life=life, size=size
                        )
                        g.ice_particles.append(p_ice_local)
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass

                    # If projectile has ICE1 / explosion_radius, create puddle + area damage
                    if hasattr(projectile, "explosion_radius") or g.permanent_stats.get(
                        "ice_1", 0
                    ):
                        puddle_radius = 40
                        if g.permanent_stats.get("ice_2", 0):
                            puddle_radius = int(40 * 1.5)  # 60 with ice_2 upgrade
                        g.ice_puddles.append(
                            {
                                "x": px,
                                "y": py,
                                "radius": puddle_radius,  # Puddle radius
                                "timer": 5 * 60,  # 5 seconds at 60 FPS
                                "slow_factor": 0.5,  # 50% speed reduction
                                "slow_duration": 30,  # 0.5 seconds slow when entering puddle
                            }
                        )

                        # Damage and slow all enemies within explosion radius
                        explosion_radius = getattr(
                            projectile, "explosion_radius", puddle_radius
                        )
                        all_targets = []
                        all_targets.extend(g.enemies)
                        if hasattr(g, "bosses") and g.bosses:
                            if hasattr(g.bosses, "sprites"):
                                all_targets.extend(g.bosses.sprites())
                            else:
                                all_targets.extend(g.bosses)

                        for enemy in all_targets:
                            ex, ey = g._enemy_pos(enemy)
                            dx = ex - px
                            dy = ey - py
                            dist_sq = dx * dx + dy * dy
                            if dist_sq <= explosion_radius * explosion_radius:
                                try:
                                    dmg_to_apply = self._player_damage_vs_burning(
                                        projectile,
                                        enemy,
                                        getattr(projectile, "damage", 0),
                                    )
                                    if id(enemy) in getattr(
                                        projectile, "_hit_ids", set()
                                    ) or id(enemy) in getattr(
                                        projectile, "hit_enemy_ids", set()
                                    ):
                                        pass
                                    elif self._elemental_shield_can_damage(
                                        enemy, projectile
                                    ):
                                        enemy.take_damage(
                                            dmg_to_apply, show_floating=False
                                        )
                                        # charge energy on each enemy hit by explosion
                                        try:
                                            self._maybe_charge_tower(projectile)
                                        except (
                                            AttributeError,
                                            TypeError,
                                            ValueError,
                                            KeyError,
                                        ):
                                            pass

                                        # Apply slow effect
                                        slow_duration = getattr(
                                            projectile, "slow_duration", 120
                                        )
                                        slow_factor = getattr(
                                            projectile, "slow_factor", 0.5
                                        )
                                        self._apply_slow_effect(
                                            enemy,
                                            slow_duration,
                                            slow_factor,
                                            extend=True,
                                        )
                                        try:
                                            ex, ey = g._enemy_pos(enemy)
                                            (
                                                final_color,
                                                final_font,
                                            ) = self._floating_text_style_for_projectile(
                                                projectile, (100, 200, 255), 20
                                            )
                                            g.spawn_floating_text(
                                                str(dmg_to_apply),
                                                ex,
                                                ey - g._enemy_radius(enemy) - 8,
                                                color=final_color,
                                                font_size=final_font,
                                            )
                                            try:
                                                setattr(
                                                    projectile, "_was_critical", False
                                                )
                                            except (
                                                AttributeError,
                                                TypeError,
                                                ValueError,
                                                KeyError,
                                            ):
                                                pass
                                        except (
                                            AttributeError,
                                            TypeError,
                                            ValueError,
                                            KeyError,
                                        ):
                                            pass
                                    else:
                                        self._show_immune_text(enemy)
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass

                        # Mark projectile exploded so we don't create multiple puddles
                        try:
                            setattr(projectile, "has_exploded", True)
                        except (AttributeError, TypeError, ValueError, KeyError):
                            try:
                                projectile["_has_exploded"] = True
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass

                        # Remove projectile after area effect so ICE1 does NOT pierce
                        try:
                            projectile.kill()
                        except (AttributeError, TypeError, ValueError, KeyError):
                            try:
                                g.projectiles.remove(projectile)
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass

                        processed_projectile = True
                        continue  # Skip normal processing

                    # Otherwise (no ICE1): single-target slow + damage and remove projectile
                    primary = hit_enemies[0]
                    try:
                        dmg_to_apply = self._player_damage_vs_burning(
                            projectile, primary, getattr(projectile, "damage", 0)
                        )
                    except (AttributeError, TypeError, ValueError, KeyError):
                        dmg_to_apply = getattr(projectile, "damage", 0)

                    try:
                        if self._elemental_shield_can_damage(primary, projectile):
                            if hasattr(primary, "take_damage"):
                                primary.take_damage(dmg_to_apply, show_floating=False)
                                try:
                                    self._maybe_charge_tower(projectile)
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                            else:
                                primary["health"] = max(
                                    0, primary.get("health", 0) - dmg_to_apply
                                )

                            # Apply slow to the primary target (use helper to handle dict/object)
                            try:
                                slow_duration = getattr(
                                    projectile, "slow_duration", 120
                                )
                                slow_factor = getattr(projectile, "slow_factor", 0.5)
                                # extend=True because max/min semantics were previously used
                                self._apply_slow_effect(
                                    primary, slow_duration, slow_factor, extend=True
                                )
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass

                            # Floating text
                            try:
                                ex, ey = g._enemy_pos(primary)
                                (
                                    final_color,
                                    final_font,
                                ) = self._floating_text_style_for_projectile(
                                    projectile, (100, 200, 255), 20
                                )
                                g.spawn_floating_text(
                                    str(dmg_to_apply),
                                    ex,
                                    ey - g._enemy_radius(primary) - 8,
                                    color=final_color,
                                    font_size=final_font,
                                )
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass
                        else:
                            self._show_immune_text(primary)
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass

                    # Record hit and remove projectile (single-hit behaviour)
                    if not hasattr(projectile, "_hit_ids"):
                        projectile._hit_ids = set()
                    projectile._hit_ids.add(id(primary))
                    try:
                        projectile.kill()
                    except (AttributeError, TypeError, ValueError, KeyError):
                        try:
                            g.projectiles.remove(projectile)
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                    processed_projectile = True
                    continue  # Skip normal processing

            for enemy in hit_enemies:
                try:
                    # Debug logging removed
                    pass
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
                if primary_target is None:
                    primary_target = enemy
                    try:
                        # Debug logging removed
                        pass
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass

                # Avoid multiple hits on the same enemy by this projectile
                hit_ids = None
                try:
                    # Canonical hit-tracking on Projectile objects (legacy dict paths removed)
                    if not hasattr(projectile, "_hit_ids"):
                        projectile._hit_ids = set()
                    hit_ids = projectile._hit_ids
                    if not hasattr(projectile, "_hit_boss_types"):
                        projectile._hit_boss_types = set()
                    # If this exact enemy was already hit by this projectile, skip
                    if id(enemy) in hit_ids:
                        continue
                    # If this is a boss (or boss part) and we've already hit a boss
                    # of the same logical type with this projectile, skip further hits
                    try:
                        etype = getattr(enemy, "enemy_type", "")
                        if (
                            isinstance(etype, str)
                            and etype.startswith("boss_")
                            and etype in getattr(projectile, "_hit_boss_types", set())
                        ):
                            continue
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass
                except (AttributeError, TypeError, ValueError, KeyError):
                    hit_ids = None

                # Special handling for Flies weapon
                if getattr(projectile, "weapon_type", None) == "Flies":
                    # Apply instant damage on contact — use projectile.damage (and
                    # respect FIRE tier-3 via the centralized helper) rather than a
                    # fixed '2'. Also show the correct damage floating text.
                    try:
                        dmg_to_apply = self._player_damage_vs_burning(
                            projectile, enemy, getattr(projectile, "damage", 0)
                        )
                    except (AttributeError, TypeError, ValueError, KeyError):
                        dmg_to_apply = getattr(projectile, "damage", 0)

                    if hasattr(enemy, "take_damage"):
                        try:
                            if self._elemental_shield_can_damage(enemy, projectile):
                                enemy.take_damage(dmg_to_apply, show_floating=False)
                        except (AttributeError, TypeError, ValueError, KeyError):
                            # Fallback: manually apply damage only if immunity check passed
                            if self._elemental_shield_can_damage(enemy, projectile):
                                try:
                                    enemy.health = max(
                                        0, getattr(enemy, "health", 0) - dmg_to_apply
                                    )
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                # Special handling for Tenebrae weapon: decaying beam
                elif getattr(projectile, "weapon_type", None) == "tenebrae":
                    # compute damage based on how many targets have been hit so far
                    try:
                        lvl = getattr(projectile, "level", 0)
                        base_p = getattr(projectile, "base_player_damage", None)
                        hits = getattr(projectile, "targets_hit", 0)
                        dmg_to_apply = tenebrae_damage(lvl, base_p, hits)
                    except (AttributeError, TypeError, ValueError, KeyError):
                        dmg_to_apply = getattr(projectile, "damage", 0)

                    # increment hit counter for next collision
                    try:
                        projectile.targets_hit = hits + 1
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass

                    if hasattr(enemy, "take_damage"):
                        try:
                            if self._elemental_shield_can_damage(enemy, projectile):
                                enemy.take_damage(dmg_to_apply, show_floating=False)
                            else:
                                self._show_immune_text(enemy)
                        except (AttributeError, TypeError, ValueError, KeyError):
                            # Fallback: manually apply damage only if immunity check passed
                            if self._elemental_shield_can_damage(enemy, projectile):
                                try:
                                    enemy.health = max(
                                        0, getattr(enemy, "health", 0) - dmg_to_apply
                                    )
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                            else:
                                self._show_immune_text(enemy)

                    # Fallback when .take_damage isn't available: adjust attribute
                    if not hasattr(enemy, "take_damage"):
                        try:
                            if self._elemental_shield_can_damage(enemy, projectile):
                                enemy.health = max(
                                    0, getattr(enemy, "health", 0) - int(dmg_to_apply)
                                )
                                try:
                                    ex, ey = g._enemy_pos(enemy)
                                    try:
                                        base = getattr(projectile, "damage", 0)
                                        is_player_proj = (
                                            not getattr(
                                                projectile, "is_enemy_projectile", False
                                            )
                                        ) and (
                                            getattr(projectile, "source", None)
                                            != "statue"
                                        )
                                        color = (
                                            (255, 200, 0)
                                            if (
                                                g.permanent_stats.get("fire_3", 0)
                                                and is_player_proj
                                                and dmg_to_apply > base
                                            )
                                            else (255, 255, 255)
                                        )
                                    except (
                                        AttributeError,
                                        TypeError,
                                        ValueError,
                                        KeyError,
                                    ):
                                        color = (255, 255, 255)
                                    (
                                        final_color,
                                        final_font,
                                    ) = self._floating_text_style_for_projectile(
                                        projectile, color, 20
                                    )
                                    g.spawn_floating_text(
                                        str(int(dmg_to_apply)),
                                        ex,
                                        ey - g._enemy_radius(enemy) - 8,
                                        color=final_color,
                                        font_size=final_font,
                                    )
                                    try:
                                        if isinstance(projectile, dict):
                                            projectile["_was_critical"] = False
                                        else:
                                            setattr(projectile, "_was_critical", False)
                                    except (
                                        AttributeError,
                                        TypeError,
                                        ValueError,
                                        KeyError,
                                    ):
                                        pass
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                            else:
                                self._show_immune_text(enemy)
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                    else:
                        # Only show floating text if damage was applied
                        if self._elemental_shield_can_damage(enemy, projectile):
                            try:
                                ex, ey = g._enemy_pos(enemy)
                                try:
                                    base = getattr(projectile, "damage", 0)
                                    is_player_proj = (
                                        not getattr(
                                            projectile, "is_enemy_projectile", False
                                        )
                                    ) and (
                                        getattr(projectile, "source", None) != "statue"
                                    )
                                    color = (
                                        (255, 200, 0)
                                        if (
                                            g.permanent_stats.get("fire_3", 0)
                                            and is_player_proj
                                            and dmg_to_apply > base
                                        )
                                        else (255, 255, 255)
                                    )
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    color = (255, 255, 255)
                                (
                                    final_color,
                                    final_font,
                                ) = self._floating_text_style_for_projectile(
                                    projectile, color, 20
                                )
                                g.spawn_floating_text(
                                    str(int(dmg_to_apply)),
                                    ex,
                                    ey - g._enemy_radius(enemy) - 8,
                                    color=final_color,
                                    font_size=final_font,
                                )
                                try:
                                    if isinstance(projectile, dict):
                                        projectile["_was_critical"] = False
                                    else:
                                        setattr(projectile, "_was_critical", False)
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass

                    # Apply drain effect (secondary periodic damage/heal) only if shield can be damaged
                    if self._elemental_shield_can_damage(enemy, projectile):
                        if (
                            not hasattr(enemy, "drain_timer")
                            or getattr(enemy, "drain_timer", 0) <= 0
                        ):
                            try:
                                enemy.drain_timer = 4 * 60  # 4 seconds
                                enemy.drain_damage = projectile.damage
                                enemy.drain_heal = projectile.heal_amount
                                enemy.drain_source = projectile  # To track
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass

                    # Record this hit so the same projectile won't process the same enemy again
                    try:
                        if not hasattr(projectile, "_hit_ids"):
                            projectile._hit_ids = set()
                        projectile._hit_ids.add(id(enemy))
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass

                    # Mark as processed so we don't run the later plain-list / fallback
                    # collision branch for the same projectile in this frame.
                    processed_projectile = True

                    # We've handled Flies for this contact — skip the normal damage path
                    continue
                    try:
                        projectile.kill()  # Remove projectile after attaching
                    except (AttributeError, TypeError, ValueError, KeyError):
                        try:
                            g.projectiles.remove(projectile)
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                    break  # Only attach to one enemy
                elif getattr(projectile, "weapon_type", None) == "skullboom":
                    # SkullBoom explodes on contact, damaging all enemies in radius
                    explosion_radius = getattr(projectile, "explosion_radius", 50)
                    px = getattr(projectile, "x", 0)
                    py = getattr(projectile, "y", 0)

                    # Create explosion particles - more irregular and varied
                    num_particles = random.randint(
                        12, 18
                    )  # More particles for denser effect
                    for _ in range(num_particles):
                        # More varied angle distribution - sometimes clustered, sometimes spread
                        angle_variation = random.uniform(0, 2 * math.pi)
                        if random.random() < 0.3:  # 30% chance of clustering
                            angle_variation += random.uniform(
                                -0.5, 0.5
                            )  # Small cluster
                        angle = angle_variation

                        # More extreme speed distribution - some fast, some slow
                        speed = random.choice(
                            [
                                random.uniform(30, 80),  # Slow particles
                                random.uniform(80, 150),  # Medium particles
                                random.uniform(150, 250),  # Fast particles
                            ]
                        )

                        vx = math.cos(angle) * speed
                        vy = math.sin(angle) * speed

                        # More varied starting positions
                        offset_x = random.uniform(-8, 8)
                        offset_y = random.uniform(-8, 8)

                        try:
                            # More varied life and size
                            life = random.randint(10, 40)  # Wider range
                            size = random.randint(1, 6)  # Smaller to larger
                            p_burn = BurnParticle(
                                px + offset_x,
                                py + offset_y,
                                vx,
                                vy,
                                life=life,
                                size=size,
                            )
                            g.skullboom_particles.append(p_burn)
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass

                    # Create explosion area effect
                    g.skullboom_explosions.append(
                        {
                            "x": px,
                            "y": py,
                            "radius": explosion_radius,
                            "max_radius": explosion_radius,
                            "timer": 15,  # Duration in frames
                            "max_timer": 15,
                        }
                    )

                    # Damage all enemies within explosion radius
                    all_targets = []
                    # Add regular enemies
                    all_targets.extend(g.enemies)
                    # Add bosses
                    if hasattr(g, "bosses") and g.bosses:
                        if hasattr(g.bosses, "sprites"):
                            all_targets.extend(g.bosses.sprites())
                        else:
                            all_targets.extend(g.bosses)

                    for enemy in all_targets:
                        ex, ey = g._enemy_pos(enemy)
                        dx = ex - px
                        dy = ey - py
                        dist_sq = dx * dx + dy * dy
                        if dist_sq <= explosion_radius * explosion_radius:
                            try:
                                dmg_to_apply = self._player_damage_vs_burning(
                                    projectile, enemy, getattr(projectile, "damage", 0)
                                )
                                if id(enemy) in getattr(projectile, "_hit_ids", set()):
                                    pass
                                elif self._elemental_shield_can_damage(
                                    enemy, projectile
                                ):
                                    enemy.take_damage(dmg_to_apply, show_floating=False)
                                    try:
                                        ex, ey = g._enemy_pos(enemy)
                                        # Highlight numeric damage yellow if FIRE tier-3 bonus applied
                                        try:
                                            base = getattr(projectile, "damage", 0)
                                            is_player_proj = (
                                                not getattr(
                                                    projectile,
                                                    "is_enemy_projectile",
                                                    False,
                                                )
                                            ) and (
                                                getattr(projectile, "source", None)
                                                != "statue"
                                            )
                                            color = (
                                                (255, 200, 0)
                                                if (
                                                    g.permanent_stats.get("fire_3", 0)
                                                    and is_player_proj
                                                    and dmg_to_apply > base
                                                )
                                                else (255, 255, 255)
                                            )
                                        except (
                                            AttributeError,
                                            TypeError,
                                            ValueError,
                                            KeyError,
                                        ):
                                            color = (255, 255, 255)
                                        (
                                            final_color,
                                            final_font,
                                        ) = self._floating_text_style_for_projectile(
                                            projectile, color, 20
                                        )
                                        g.spawn_floating_text(
                                            str(dmg_to_apply),
                                            ex,
                                            ey - g._enemy_radius(enemy) - 8,
                                            color=final_color,
                                            font_size=final_font,
                                        )
                                        try:
                                            if isinstance(projectile, dict):
                                                projectile["_was_critical"] = False
                                            else:
                                                setattr(
                                                    projectile, "_was_critical", False
                                                )
                                        except (
                                            AttributeError,
                                            TypeError,
                                            ValueError,
                                            KeyError,
                                        ):
                                            pass
                                    except (
                                        AttributeError,
                                        TypeError,
                                        ValueError,
                                        KeyError,
                                    ):
                                        pass
                                else:
                                    self._show_immune_text(enemy)
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass

                    # Remove projectile after explosion
                    try:
                        projectile.kill()
                    except (AttributeError, TypeError, ValueError, KeyError):
                        try:
                            g.projectiles.remove(projectile)
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                    processed_projectile = True
                    break  # Stop processing hits for this projectile
                else:
                    # Normal projectile damage
                    try:
                        try:
                            # Normal hit on target
                            ex, ey = g._enemy_pos(enemy)
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                        # Apply possible FIRE tier-3 player bonus vs burning enemies
                        dmg_to_apply = self._player_damage_vs_burning(
                            projectile, enemy, getattr(projectile, "damage", 0)
                        )
                        # Cross Bearer shield (enemy path — defensive, boss path is primary)
                        _cross_bearer_reflected = False
                        if getattr(enemy, "enemy_type", "") == "cross_bearer":
                            cb_shield = getattr(enemy, "cb_shield_hp", 0)
                            if (
                                not getattr(enemy, "_shield_broken", False)
                                and cb_shield > 0
                            ):
                                enemy.cb_shield_hp = max(
                                    0, cb_shield - int(dmg_to_apply)
                                )
                                enemy._shield_regen_timer = 0
                                if enemy.cb_shield_hp <= 0:
                                    enemy._shield_broken = True
                                    enemy.shake_timer = 12
                                else:
                                    projectile.vel_x = -getattr(projectile, "vel_x", 0)
                                    projectile.vel_y = -getattr(projectile, "vel_y", 0)
                                    projectile.is_enemy_projectile = True
                                    projectile.damage = max(1, int(dmg_to_apply * 0.8))
                                    # Move reflected projectile from player projectiles to enemy projectiles
                                    # so it will damage the player when it hits
                                    try:
                                        if projectile in g.projectiles:
                                            g.projectiles.remove(projectile)
                                        g.enemy_projectiles.add(projectile)
                                    except (
                                        AttributeError,
                                        TypeError,
                                        ValueError,
                                        KeyError,
                                    ):
                                        pass
                                _cross_bearer_reflected = True
                        if not _cross_bearer_reflected:
                            if self._elemental_shield_can_damage(enemy, projectile):
                                enemy.take_damage(dmg_to_apply, show_floating=False)
                                try:
                                    self._maybe_charge_tower(projectile)
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                                try:
                                    ex, ey = g._enemy_pos(enemy)
                                    try:
                                        base = (
                                            projectile.get("damage", 0)
                                            if isinstance(projectile, dict)
                                            else getattr(projectile, "damage", 0)
                                        )
                                        is_player_proj = (
                                            not getattr(
                                                projectile, "is_enemy_projectile", False
                                            )
                                        ) and (
                                            getattr(projectile, "source", None)
                                            != "statue"
                                        )
                                        color = (
                                            (255, 200, 0)
                                            if (
                                                g.permanent_stats.get("fire_3", 0)
                                                and is_player_proj
                                                and dmg_to_apply > base
                                            )
                                            else (255, 255, 255)
                                        )
                                    except (
                                        AttributeError,
                                        TypeError,
                                        ValueError,
                                        KeyError,
                                    ):
                                        color = (255, 255, 255)
                                    try:
                                        ex, ey = g._enemy_pos(enemy)
                                        (
                                            final_color,
                                            final_font,
                                        ) = self._floating_text_style_for_projectile(
                                            projectile, color, 20
                                        )
                                        try:
                                            # display the actual damage applied (including crit bonus)
                                            display_text = str(dmg_to_apply)
                                        except (
                                            AttributeError,
                                            TypeError,
                                            ValueError,
                                            KeyError,
                                        ):
                                            display_text = str(dmg_to_apply)
                                        g.spawn_floating_text(
                                            display_text,
                                            ex,
                                            ey - g._enemy_radius(enemy) - 8,
                                            color=final_color,
                                            font_size=final_font,
                                        )
                                        try:
                                            if isinstance(projectile, dict):
                                                projectile["_was_critical"] = False
                                            else:
                                                setattr(
                                                    projectile, "_was_critical", False
                                                )
                                        except (
                                            AttributeError,
                                            TypeError,
                                            ValueError,
                                            KeyError,
                                        ):
                                            pass
                                    except (
                                        AttributeError,
                                        TypeError,
                                        ValueError,
                                        KeyError,
                                    ):
                                        pass
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                            else:
                                self._show_immune_text(enemy)
                        # Storm-statue projectiles should be removed on first contact (apply chain immediately)
                        if getattr(projectile, "appearance", None) == "storm_statue":
                            # Apply chain lightning to nearby enemies (primary already hit)
                            try:
                                chain = getattr(projectile, "chain_targets", 0)
                                if (
                                    chain
                                    and chain > 1
                                    and not getattr(projectile, "_chain_applied", False)
                                ):
                                    chain_points = [
                                        (
                                            g._enemy_pos(enemy)[0],
                                            g._enemy_pos(enemy)[1],
                                        )
                                    ]
                                    # Gather nearby candidates from sprite group
                                    others = []
                                    max_chain_distance = 300
                                    for other in g.enemies.sprites():
                                        if other is enemy:
                                            continue
                                        if getattr(other, "health", 0) <= 0:
                                            continue
                                        ox, oy = g._enemy_pos(other)
                                        exx, eyy = g._enemy_pos(enemy)
                                        dist = math.hypot(ox - exx, oy - eyy)
                                        if dist <= max_chain_distance:
                                            others.append((dist, other))
                                    others.sort(key=lambda t: t[0])
                                    to_chain = min(len(others), chain - 1)
                                    for _, targ in others[:to_chain]:
                                        try:
                                            # calculate damage through helper so crits/burn
                                            # bonuses apply to chain hits as well
                                            # chain lightning now does 1.5× base damage
                                            dmg_chain = self._player_damage_vs_burning(
                                                projectile,
                                                targ,
                                                projectile.damage * 1.5,
                                            )
                                            if self._elemental_shield_can_damage(
                                                targ, projectile
                                            ):
                                                targ.take_damage(
                                                    dmg_chain, show_floating=False
                                                )
                                                # show damage number using computed value
                                                try:
                                                    ex, ey = g._enemy_pos(targ)
                                                    (
                                                        final_color,
                                                        final_font,
                                                    ) = self._floating_text_style_for_projectile(
                                                        projectile, (255, 255, 255), 20
                                                    )
                                                    g.spawn_floating_text(
                                                        str(int(dmg_chain)),
                                                        ex,
                                                        ey - g._enemy_radius(targ) - 8,
                                                        color=final_color,
                                                        font_size=final_font,
                                                    )
                                                except (
                                                    AttributeError,
                                                    TypeError,
                                                    ValueError,
                                                    KeyError,
                                                ):
                                                    pass
                                            else:
                                                self._show_immune_text(targ)
                                            try:
                                                self._maybe_charge_tower(projectile)
                                            except (
                                                AttributeError,
                                                TypeError,
                                                ValueError,
                                                KeyError,
                                            ):
                                                pass
                                        except (
                                            AttributeError,
                                            TypeError,
                                            ValueError,
                                            KeyError,
                                        ):
                                            try:
                                                targ.health -= projectile.damage * 1.5
                                            except (
                                                AttributeError,
                                                TypeError,
                                                ValueError,
                                                KeyError,
                                            ):
                                                pass
                                            try:
                                                self._maybe_charge_tower(projectile)
                                            except (
                                                AttributeError,
                                                TypeError,
                                                ValueError,
                                                KeyError,
                                            ):
                                                pass
                                        tx, ty = g._enemy_pos(targ)
                                        chain_points.append((tx, ty))

                                        # death handling for chained targets (sprite-based)
                                        if getattr(targ, "health", 0) <= 0:
                                            try:
                                                g.add_score(
                                                    targ.max_health
                                                    * ENEMY_SCORE_PER_HEALTH
                                                    * g.difficulty_multiplier
                                                )
                                            except (
                                                AttributeError,
                                                TypeError,
                                                ValueError,
                                                KeyError,
                                            ):
                                                pass
                                            try:
                                                type_xp_local = {
                                                    "weak": 10,
                                                    "normal": 16,
                                                    "strong": 25,
                                                    "giant": 50,
                                                    "angel": 22,
                                                }
                                                base_xp_local = type_xp_local.get(
                                                    str(
                                                        getattr(targ, "enemy_type", "")
                                                    ),
                                                    12,
                                                )
                                                g.player_xp += int(
                                                    round(
                                                        base_xp_local
                                                        * getattr(
                                                            self, "xp_multiplier", 1.0
                                                        )
                                                    )
                                                )
                                                if g.player_xp >= g.xp_to_next_level:
                                                    g.trigger_level_up()
                                            except (
                                                AttributeError,
                                                TypeError,
                                                ValueError,
                                                KeyError,
                                            ):
                                                pass
                                            try:
                                                if (
                                                    getattr(
                                                        targ,
                                                        "burn_propagate_on_death",
                                                        False,
                                                    )
                                                    or getattr(
                                                        targ, "burn_propagate_hops", 0
                                                    )
                                                    > 0
                                                ):
                                                    try:
                                                        self._propagate_burn(targ)
                                                    except (
                                                        AttributeError,
                                                        TypeError,
                                                        ValueError,
                                                        KeyError,
                                                    ):
                                                        pass
                                            except (
                                                AttributeError,
                                                TypeError,
                                                ValueError,
                                                KeyError,
                                            ):
                                                pass

                                            # storm_2: create lightning explosion on chain-kill
                                            try:
                                                if g.permanent_stats.get("storm_2", 0):
                                                    cx, cy = g._enemy_pos(targ)
                                                    explosion_radius = 120
                                                    explosion_dmg = getattr(
                                                        projectile, "damage", 0
                                                    )
                                                    all_targets = []
                                                    all_targets.extend(
                                                        g.enemies
                                                        if hasattr(g.enemies, "sprites")
                                                        else g.enemies
                                                    )
                                                    if (
                                                        hasattr(g, "bosses")
                                                        and g.bosses
                                                    ):
                                                        if hasattr(g.bosses, "sprites"):
                                                            all_targets.extend(
                                                                g.bosses.sprites()
                                                            )
                                                        else:
                                                            all_targets.extend(g.bosses)
                                                    explosion_points = [(cx, cy)]
                                                    for ex_target in all_targets:
                                                        if ex_target is targ:
                                                            continue
                                                        try:
                                                            ex, ey = g._enemy_pos(
                                                                ex_target
                                                            )
                                                        except (
                                                            AttributeError,
                                                            TypeError,
                                                            ValueError,
                                                            KeyError,
                                                        ):
                                                            continue
                                                        dist = math.hypot(
                                                            ex - cx, ey - cy
                                                        )
                                                        if dist <= explosion_radius:
                                                            try:
                                                                ex_target.take_damage(
                                                                    explosion_dmg
                                                                )
                                                            except (
                                                                AttributeError,
                                                                TypeError,
                                                                ValueError,
                                                                KeyError,
                                                            ):
                                                                if isinstance(
                                                                    ex_target, dict
                                                                ):
                                                                    ex_target[
                                                                        "health"
                                                                    ] = max(
                                                                        0,
                                                                        ex_target.get(
                                                                            "health", 0
                                                                        )
                                                                        - explosion_dmg,
                                                                    )
                                                            explosion_points.append(
                                                                (ex, ey)
                                                            )
                                                    if len(explosion_points) > 1:
                                                        try:
                                                            # richer visual metadata for storm_2 on-kill explosion
                                                            g.game_state.chain_lightning_effects.append(
                                                                {
                                                                    "points": explosion_points,
                                                                    "timer": 16,
                                                                    "color": (
                                                                        120,
                                                                        220,
                                                                        255,
                                                                    ),
                                                                    "explosion": True,
                                                                    "radius": explosion_radius,
                                                                }
                                                            )
                                                        except (
                                                            AttributeError,
                                                            TypeError,
                                                            ValueError,
                                                            KeyError,
                                                        ):
                                                            pass
                                            except (
                                                AttributeError,
                                                TypeError,
                                                ValueError,
                                                KeyError,
                                            ):
                                                pass

                                            try:
                                                try:
                                                    g.record_enemy_kill()
                                                except (
                                                    AttributeError,
                                                    TypeError,
                                                    ValueError,
                                                    KeyError,
                                                ):
                                                    pass
                                                targ.kill()
                                            except (
                                                AttributeError,
                                                TypeError,
                                                ValueError,
                                                KeyError,
                                            ):
                                                try:
                                                    g.enemies.remove(targ)
                                                except (
                                                    AttributeError,
                                                    TypeError,
                                                    ValueError,
                                                    KeyError,
                                                ):
                                                    pass
                                    if len(chain_points) > 1:
                                        g.game_state.chain_lightning_effects.append(
                                            {"points": chain_points, "timer": 8}
                                        )
                                    projectile._chain_applied = True
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass

                            try:
                                projectile.kill()
                            except (AttributeError, TypeError, ValueError, KeyError):
                                try:
                                    g.projectiles.remove(projectile)
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass

                # Record this hit so projectile won't hit the same enemy again
                try:
                    if hit_ids is None:
                        if not hasattr(projectile, "_hit_ids"):
                            projectile._hit_ids = set()
                        hit_ids = projectile._hit_ids
                    hit_ids.add(id(enemy))
                    # For bosses, also remember the boss-type so multi-part bosses
                    # or duplicate boss sub-sprites won't be damaged multiple times
                    try:
                        etype = getattr(enemy, "enemy_type", "")
                        if isinstance(etype, str) and etype.startswith("boss_"):
                            if isinstance(projectile, dict):
                                projectile.setdefault("_hit_boss_types", set()).add(
                                    etype
                                )
                            else:
                                if not hasattr(projectile, "_hit_boss_types"):
                                    projectile._hit_boss_types = set()
                                projectile._hit_boss_types.add(etype)
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

                # Apply slow effect if projectile has it (Ice towers)
                if effect == "slow":
                    if self._elemental_shield_can_damage(enemy, projectile):
                        # helper handles dict/object and guards against reapplication
                        self._apply_slow_effect(enemy, slow_duration, slow_factor)

                        # Add ice explosion particles
                        for _ in range(10):  # More ice shards for better visibility
                            vx = random.uniform(-60, 60)
                            vy = random.uniform(-40, 20)  # Some go up, some down
                            p_ice_enemy = IceParticle(
                                enemy.x,
                                enemy.y,
                                vx,
                                vy,
                                life=25,
                                size=random.randint(1, 3),
                            )
                            enemy.ice_particles.append(p_ice_enemy)
                    else:
                        self._show_immune_text(enemy)

                # Apply burn effect (Fire towers)
                if effect == "burn":
                    if self._elemental_shield_can_damage(enemy, projectile):
                        # Only apply if not already burning
                        try:
                            if (
                                not hasattr(enemy, "burn_timer")
                                or getattr(enemy, "burn_timer", 0) <= 0
                            ):
                                enemy.burn_timer = burn_duration
                                enemy.burn_damage_per_second = burn_dps
                            # Counter for per-second ticks
                            enemy.burn_tick_timer = getattr(g, "fps", 60)
                            # For sprite-based enemies, attach propagation-on-death attrs when applicable
                            try:
                                if g.permanent_stats.get("fire_1", 0):
                                    enemy.burn_propagate_on_death = True
                                    enemy.burn_propagate_radius = 150
                                    enemy.burn_propagate_dps = burn_dps
                                    enemy.burn_propagate_duration = burn_duration
                                    enemy.burn_propagate_hops = 2
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                    else:
                        self._show_immune_text(enemy)

                # Handle projectile piercing / kill (object-style only)
                p_pierce_all = getattr(projectile, "pierce_all", False)
                p_pierce_count = getattr(projectile, "pierce_count", 0)
                # ICE3: Ice projectiles pierce through all enemies
                if getattr(
                    projectile, "appearance", None
                ) == "ice_statue" and g.permanent_stats.get("ice_3", 0):
                    p_pierce_all = True

                if p_pierce_all:
                    pass  # Spear pierces through everything
                elif p_pierce_count > 0:
                    # decrement remaining pierces and remove if exhausted (object-style)
                    projectile.pierce_count = getattr(projectile, "pierce_count", 0) - 1
                    p_pierce_count = projectile.pierce_count

                    if p_pierce_count <= 0:
                        try:
                            projectile.kill()
                        except (AttributeError, TypeError, ValueError, KeyError):
                            try:
                                g.projectiles.remove(projectile)
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                else:
                    # Default: remove / kill projectile after a hit
                    try:
                        if isinstance(projectile, dict):
                            try:
                                g.projectiles.remove(projectile)
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass
                        else:
                            projectile.kill()
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass

                    # Death handling for object-based enemies
                    if getattr(enemy, "health", None) is not None:
                        if enemy.health <= 0:
                            g.add_score(
                                enemy.max_health
                                * ENEMY_SCORE_PER_HEALTH
                                * g.difficulty_multiplier
                            )
                            # Give XP on kill (per-type table, flat values)
                            type_xp_local = {
                                "weak": 10,
                                "normal": 16,
                                "strong": 25,
                                "giant": 50,
                                "angel": 22,
                            }
                            base_xp_local = type_xp_local.get(
                                str(enemy.enemy_type), 12
                            )  # fallback XP
                            g.player_xp += int(
                                round(base_xp_local * getattr(g, "xp_multiplier", 1.0))
                            )
                            if g.player_xp >= g.xp_to_next_level:
                                g.trigger_level_up()
                            # Ensure propagation fires even if killed by a weapon/projectile
                            try:
                                if (
                                    getattr(enemy, "burn_propagate_on_death", False)
                                    or getattr(enemy, "burn_propagate_hops", 0) > 0
                                ):
                                    try:
                                        self._propagate_burn(enemy)
                                    except (
                                        AttributeError,
                                        TypeError,
                                        ValueError,
                                        KeyError,
                                    ):
                                        pass
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass
                            enemy.kill()  # Remove dead enemy
                        break

                try:
                    # Debug logging removed
                    pass
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
                # Chain hits: storm projectiles can hit additional distinct enemies
                if primary_target is not None:
                    try:
                        # Debug logging removed
                        pass
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass
                    chain = getattr(projectile, "chain_targets", 0)
                    if (
                        chain
                        and chain > 1
                        and not getattr(projectile, "_chain_applied", False)
                    ):
                        others = []
                        # Gather other enemy candidates within chain range
                        max_chain_distance = (
                            300  # Maximum distance for chain lightning (pixels)
                        )
                        for other in g.enemies.sprites():
                            if other is primary_target:
                                continue
                            if getattr(other, "health", 0) <= 0:
                                continue
                            ox, oy = g._enemy_pos(other)
                            exx, eyy = g._enemy_pos(primary_target)
                            dist = math.hypot(ox - exx, oy - eyy)
                            if (
                                dist <= max_chain_distance
                            ):  # Only consider enemies within range
                                others.append((dist, other))
                        others.sort(key=lambda t: t[0])
                        to_chain = min(len(others), chain - 1)

                        # Debug logging for chain targets
                        try:
                            LOG.debug(
                                "Storm chain: primary=%s, chain=%s, candidates=%s",
                                primary_target,
                                chain,
                                [o[1] for o in others],
                            )
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass

                        # Store chain lightning effect for visual
                        chain_points = [
                            (
                                g._enemy_pos(primary_target)[0],
                                g._enemy_pos(primary_target)[1],
                            )
                        ]

                        for _, targ in others[:to_chain]:
                            # Apply damage to chained targets (prefer take_damage)
                            damaged = False
                            try:
                                try:
                                    # Chain: apply damage to secondary target
                                    pass
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                                targ.take_damage(
                                    projectile.damage * 1.5, show_floating=False
                                )
                                damaged = True
                                try:
                                    # Chain: damage applied
                                    pass
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                            except (AttributeError, TypeError, ValueError, KeyError):
                                try:
                                    try:
                                        # Chain: apply damage to secondary target
                                        pass
                                    except (
                                        AttributeError,
                                        TypeError,
                                        ValueError,
                                        KeyError,
                                    ):
                                        pass
                                    targ.health -= projectile.damage * 1.5
                                    damaged = True
                                    try:
                                        # Chain: damage applied
                                        pass
                                    except (
                                        AttributeError,
                                        TypeError,
                                        ValueError,
                                        KeyError,
                                    ):
                                        pass
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass

                            # Record that this projectile hit the chained target so it won't be hit again
                            try:
                                if not hasattr(projectile, "_hit_ids"):
                                    projectile._hit_ids = set()
                                projectile._hit_ids.add(id(targ))
                                try:
                                    LOG.debug(
                                        "handle_collisions: projectile id=%s chained-damaged targ id=%s; _hit_ids=%s",
                                        id(projectile),
                                        id(targ),
                                        getattr(projectile, "_hit_ids", None),
                                    )
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass

                            # Debug log if damage wasn't applied
                            try:
                                if not damaged:
                                    LOG.debug(
                                        "Storm chain: failed to damage target %s", targ
                                    )
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass

                            # Add to chain points for visual effect
                            tx, ty = g._enemy_pos(targ)
                            chain_points.append((tx, ty))

                            # death handling for chained-target sprites
                            if getattr(targ, "health", 0) <= 0:
                                g.add_score(
                                    targ.max_health
                                    * ENEMY_SCORE_PER_HEALTH
                                    * g.difficulty_multiplier
                                )
                                type_xp_local = {
                                    "weak": 10,
                                    "normal": 16,
                                    "strong": 25,
                                    "giant": 50,
                                    "angel": 22,
                                }
                                base_xp_local = type_xp_local.get(
                                    str(targ.enemy_type), 12
                                )
                                g.player_xp += int(
                                    round(
                                        base_xp_local * getattr(g, "xp_multiplier", 1.0)
                                    )
                                )
                                if g.player_xp >= g.xp_to_next_level:
                                    g.trigger_level_up()
                                # Propagate burn on death even if killed by a weapon/projectile
                                try:
                                    if (
                                        getattr(targ, "burn_propagate_on_death", False)
                                        or getattr(targ, "burn_propagate_hops", 0) > 0
                                    ):
                                        try:
                                            self._propagate_burn(targ)
                                        except (
                                            AttributeError,
                                            TypeError,
                                            ValueError,
                                            KeyError,
                                        ):
                                            pass
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass

                                # If storm_2 permanent is active, chained-target kills create a
                                # lightning explosion that damages nearby enemies.
                                try:
                                    if g.permanent_stats.get("storm_2", 0):
                                        # Capture center before removing target
                                        try:
                                            cx, cy = g._enemy_pos(targ)
                                        except (
                                            AttributeError,
                                            TypeError,
                                            ValueError,
                                            KeyError,
                                        ):
                                            cx, cy = 0, 0
                                        explosion_radius = 120  # pixels
                                        # Explosion damage scales with the projectile's base damage
                                        try:
                                            explosion_dmg = getattr(
                                                projectile, "damage", 0
                                            )
                                        except (
                                            AttributeError,
                                            TypeError,
                                            ValueError,
                                            KeyError,
                                        ):
                                            explosion_dmg = 0

                                        # Gather targets (enemies + bosses)
                                        all_targets = []
                                        all_targets.extend(
                                            g.enemies
                                            if hasattr(g.enemies, "sprites")
                                            else g.enemies
                                        )
                                        if hasattr(g, "bosses") and g.bosses:
                                            if hasattr(g.bosses, "sprites"):
                                                all_targets.extend(g.bosses.sprites())
                                            else:
                                                all_targets.extend(g.bosses)

                                        explosion_points = [(cx, cy)]
                                        for ex_target in all_targets:
                                            if ex_target is targ:
                                                continue
                                            try:
                                                ex, ey = g._enemy_pos(ex_target)
                                            except (
                                                AttributeError,
                                                TypeError,
                                                ValueError,
                                                KeyError,
                                            ):
                                                continue
                                            dx = ex - cx
                                            dy = ey - cy
                                            distance = math.hypot(dx, dy)
                                            if distance <= explosion_radius:
                                                # Apply damage to nearby enemy
                                                try:
                                                    ex_target.take_damage(
                                                        explosion_dmg,
                                                        show_floating=False,
                                                    )
                                                except (
                                                    AttributeError,
                                                    TypeError,
                                                    ValueError,
                                                    KeyError,
                                                ):
                                                    if isinstance(ex_target, dict):
                                                        ex_target["health"] = max(
                                                            0,
                                                            ex_target.get("health", 0)
                                                            - explosion_dmg,
                                                        )
                                                explosion_points.append((ex, ey))

                                        # Add short chain/lightning visuals from the killed enemy to affected neighbours
                                        if len(explosion_points) > 1:
                                            try:
                                                g.game_state.chain_lightning_effects.append(
                                                    {
                                                        "points": explosion_points,
                                                        "timer": 12,
                                                        "color": (120, 220, 255),
                                                        "explosion": True,
                                                        "radius": explosion_radius,
                                                    }
                                                )
                                            except (
                                                AttributeError,
                                                TypeError,
                                                ValueError,
                                                KeyError,
                                            ):
                                                pass
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass

                                try:
                                    try:
                                        g.record_enemy_kill()
                                    except (
                                        AttributeError,
                                        TypeError,
                                        ValueError,
                                        KeyError,
                                    ):
                                        pass
                                    targ.kill()
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    try:
                                        g.enemies.remove(targ)
                                    except (
                                        AttributeError,
                                        TypeError,
                                        ValueError,
                                        KeyError,
                                    ):
                                        pass

                        # Add chain lightning effect to game state
                        if len(chain_points) > 1:
                            try:
                                # Debug logging removed
                                pass
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass
                            try:
                                # Diagnostic: health snapshot
                                pass
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass
                            g.game_state.chain_lightning_effects.append(
                                {
                                    "points": chain_points,
                                    "timer": 8,  # Show for 8 frames
                                }
                            )
                        # Mark chain applied so we don't duplicate
                        projectile._chain_applied = True
            if processed_projectile:
                continue
            else:
                # Enemies stored as a simple iterable (dicts or object instances)
                # Quick boss check for list-backed enemy collections (ensure projectiles
                # that hit bosses are handled even when enemies are not a Sprite Group)
                try:
                    if (
                        hasattr(projectile, "rect")
                        and hasattr(g, "bosses")
                        and g.bosses
                    ):
                        boss_hits = pygame.sprite.spritecollide(
                            projectile, g.bosses, False
                        )
                        if boss_hits:
                            for boss in boss_hits:
                                _cb_reflected2 = False
                                try:
                                    # Apply direct damage to boss.  Tenebrae projectiles
                                    # compute damage on hit (damage=0) and track
                                    # targets_hit, so replicate that logic here too.
                                    if (
                                        getattr(projectile, "weapon_type", None)
                                        == "tenebrae"
                                    ):
                                        try:
                                            lvl = getattr(projectile, "level", 0)
                                            base_p = getattr(
                                                projectile, "base_player_damage", None
                                            )
                                            hits = getattr(projectile, "targets_hit", 0)
                                            bd_local = tenebrae_damage(
                                                lvl, base_p, hits
                                            )
                                        except (
                                            AttributeError,
                                            TypeError,
                                            ValueError,
                                            KeyError,
                                        ):
                                            bd_local = getattr(projectile, "damage", 0)
                                        # increment hit count so subsequent collisions
                                        # will decay appropriately
                                        try:
                                            projectile.targets_hit = hits + 1
                                        except (
                                            AttributeError,
                                            TypeError,
                                            ValueError,
                                            KeyError,
                                        ):
                                            pass
                                    else:
                                        bd_local = self._player_damage_vs_burning(
                                            projectile,
                                            boss,
                                            getattr(projectile, "damage", 0),
                                        )
                                    # Cross Bearer shield check (fallback path)
                                    if (
                                        getattr(boss, "enemy_type", "")
                                        == "cross_bearer"
                                    ):
                                        cb_shield2 = getattr(boss, "cb_shield_hp", 0)
                                        cb_broken2 = getattr(
                                            boss, "_shield_broken", False
                                        )
                                        if not cb_broken2 and cb_shield2 > 0:
                                            boss.cb_shield_hp = max(
                                                0, cb_shield2 - int(bd_local)
                                            )
                                            boss._shield_regen_timer = 0
                                            if boss.cb_shield_hp <= 0:
                                                boss._shield_broken = True
                                                boss.shake_timer = 12
                                                try:
                                                    g.spawn_floating_text(
                                                        "SHIELD BROKEN",
                                                        int(boss.x),
                                                        int(boss.y) - 30,
                                                        color=(100, 180, 255),
                                                        font_size=18,
                                                    )
                                                except (
                                                    AttributeError,
                                                    TypeError,
                                                    ValueError,
                                                    KeyError,
                                                ):
                                                    pass
                                            else:
                                                pvx2 = getattr(projectile, "vel_x", 0)
                                                pvy2 = getattr(projectile, "vel_y", 0)
                                                projectile.vel_x = -pvx2
                                                projectile.vel_y = -pvy2
                                                projectile.is_enemy_projectile = True
                                                projectile.damage = max(
                                                    1, int(bd_local * 0.8)
                                                )
                                                # Move reflected projectile from player projectiles to enemy projectiles
                                                # so it will damage the player when it hits
                                                try:
                                                    if projectile in g.projectiles:
                                                        g.projectiles.remove(projectile)
                                                    g.enemy_projectiles.add(projectile)
                                                except (
                                                    AttributeError,
                                                    TypeError,
                                                    ValueError,
                                                    KeyError,
                                                ):
                                                    pass
                                                # Show "REFLECTED" only once every 2 seconds (120 frames) to avoid spam
                                                try:
                                                    last_reflect_msg = getattr(
                                                        boss,
                                                        "_last_reflect_msg_time",
                                                        -120,
                                                    )
                                                    current_time = (
                                                        g.time_elapsed * g.fps
                                                    )
                                                    if (
                                                        current_time - last_reflect_msg
                                                        >= 120
                                                    ):
                                                        g.spawn_floating_text(
                                                            "REFLECTED",
                                                            int(boss.x),
                                                            int(boss.y) - 20,
                                                            color=(160, 210, 255),
                                                            font_size=14,
                                                        )
                                                        boss._last_reflect_msg_time = (
                                                            current_time
                                                        )
                                                except (
                                                    AttributeError,
                                                    TypeError,
                                                    ValueError,
                                                    KeyError,
                                                ):
                                                    pass
                                            _cb_reflected2 = True
                                    # boss damage should show numbers; let take_damage use default
                                    if not _cb_reflected2:
                                        boss.take_damage(bd_local)
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass

                                # Apply projectile effects to boss (burn/slow)
                                try:
                                    if getattr(projectile, "effect", None) == "slow":
                                        self._apply_slow_effect(
                                            boss,
                                            getattr(projectile, "slow_duration", 120),
                                            getattr(projectile, "slow_factor", 0.5),
                                        )
                                    elif getattr(projectile, "effect", None) == "burn":
                                        if (
                                            not hasattr(boss, "burn_timer")
                                            or getattr(boss, "burn_timer", 0) <= 0
                                        ):
                                            boss.burn_timer = burn_duration
                                            boss.burn_damage_per_second = burn_dps
                                            boss.burn_tick_timer = getattr(
                                                self, "fps", 60
                                            )
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass

                                # Record that this projectile has hit this boss/type so
                                # it won't hit again on subsequent frames
                                try:
                                    if not hasattr(projectile, "_hit_ids"):
                                        projectile._hit_ids = set()
                                    projectile._hit_ids.add(id(boss))
                                    if not hasattr(projectile, "_hit_boss_types"):
                                        projectile._hit_boss_types = set()
                                    projectile._hit_boss_types.add(
                                        getattr(boss, "enemy_type", "")
                                    )
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass

                                # Reflected projectiles stay alive; others are removed
                                if _cb_reflected2:
                                    pass  # Reflected: keep alive, now travels as enemy projectile
                                else:
                                    try:
                                        projectile.kill()
                                    except (
                                        AttributeError,
                                        TypeError,
                                        ValueError,
                                        KeyError,
                                    ):
                                        try:
                                            g.projectiles.remove(projectile)
                                        except (
                                            AttributeError,
                                            TypeError,
                                            ValueError,
                                            KeyError,
                                        ):
                                            pass
                                # Mark as processed so we don't run the later boss-collision
                                # branch again for the same projectile in this frame.
                                processed_projectile = True
                                continue
                    proj_px = getattr(projectile, "x", 0)
                    proj_py = getattr(projectile, "y", 0)
                    proj_pr = getattr(
                        projectile,
                        "radius",
                        (
                            projectile.get("radius", 0)
                            if isinstance(projectile, dict)
                            else 0
                        ),
                    )
                except (AttributeError, TypeError, ValueError, KeyError):
                    proj_px = proj_py = proj_pr = 0

                # Collect and sort candidates in single pass (optimization: avoid normalization loop)
                candidates = []

                for enemy in g.enemies:
                    try:
                        ex, ey = g._enemy_pos(enemy)
                        er = g._enemy_radius(enemy)
                        dx = ex - proj_px
                        dy = ey - proj_py
                        # precise circle overlap check (using squared distance)
                        d2 = dx * dx + dy * dy
                        thresh = (er + proj_pr) * (er + proj_pr)

                        if d2 <= thresh:
                            candidates.append((d2, enemy))
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass

                # Sort once and hit only nearest enemy (optimization: single-pass sort)
                if candidates:
                    candidates.sort(key=lambda t: t[0])
                    hit_enemies = [candidates[0][1]]
                else:
                    hit_enemies = []

                # Process only the nearest overlapping enemy (if any)
                for enemy in hit_enemies:
                    # Canonical projectile attributes (object-style)
                    px = getattr(projectile, "x", 0)
                    py = getattr(projectile, "y", 0)
                    pr = getattr(projectile, "radius", 0)
                    p_damage = getattr(projectile, "damage", 0)
                    p_pierce_all = getattr(projectile, "pierce_all", False)
                    p_pierce_count = getattr(projectile, "pierce_count", 0)

                    # Hit
                    # Avoid multiple hits on the same enemy by this projectile
                    hit_ids = None
                    try:
                        if not hasattr(projectile, "_hit_ids"):
                            projectile._hit_ids = set()
                        hit_ids = projectile._hit_ids
                        if id(enemy) in hit_ids:
                            continue
                    except (AttributeError, TypeError, ValueError, KeyError):
                        hit_ids = None
                    # object-style enemy (removed dict-compat)
                    dmg_to_apply = self._player_damage_vs_burning(
                        projectile, enemy, p_damage
                    )
                    try:
                        if self._elemental_shield_can_damage(enemy, projectile):
                            enemy.take_damage(dmg_to_apply, show_floating=False)
                    except (AttributeError, TypeError, ValueError, KeyError):
                        # Fallback: manually apply damage only if immunity check passed
                        if self._elemental_shield_can_damage(enemy, projectile):
                            try:
                                enemy.health = max(
                                    0, getattr(enemy, "health", 0) - dmg_to_apply
                                )
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass

                    # Record this hit so projectile won't hit the same enemy again
                    try:
                        if hit_ids is None:
                            if not hasattr(projectile, "_hit_ids"):
                                projectile._hit_ids = set()
                            hit_ids = projectile._hit_ids
                        hit_ids.add(id(enemy))
                        try:
                            LOG.debug(
                                "handle_collisions: projectile id=%s damaged enemy id=%s; _hit_ids=%s",
                                id(projectile),
                                id(enemy),
                                getattr(projectile, "_hit_ids", None),
                            )
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass

                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass

                        # Apply slow (object-style)
                        if effect == "slow":
                            if self._elemental_shield_can_damage(enemy, projectile):
                                if not hasattr(enemy, "original_speed"):
                                    enemy.original_speed = getattr(enemy, "speed", 100)
                                enemy.slow_timer = slow_duration
                                enemy.slow_factor = slow_factor
                                enemy.speed = enemy.original_speed * enemy.slow_factor

                                # Add ice explosion particles (object-style)
                                if not hasattr(enemy, "ice_particles"):
                                    enemy.ice_particles = []
                                ex, ey = g._enemy_pos(enemy)
                                for _ in range(
                                    10
                                ):  # More ice shards for better visibility
                                    vx = random.uniform(-60, 60)
                                    vy = random.uniform(
                                        -40, 20
                                    )  # Some go up, some down
                                    enemy.ice_particles.append(
                                        IceParticle(
                                            ex,
                                            ey,
                                            vx,
                                            vy,
                                            life=25,
                                            size=random.randint(1, 3),
                                        )
                                    )
                            else:
                                self._show_immune_text(enemy)

                        # Apply burn (object-style)
                        if effect == "burn":
                            if self._elemental_shield_can_damage(enemy, projectile):
                                # only apply if enemy not already burning
                                if getattr(enemy, "burn_timer", 0) <= 0:
                                    enemy.burn_timer = burn_duration
                                    enemy.burn_damage_per_second = burn_dps
                                    enemy.burn_tick_counter = g.fps
                            else:
                                self._show_immune_text(enemy)

                        # Handle projectile piercing / kill (object-style)
                        p_pierce_all = getattr(projectile, "pierce_all", False)
                        p_pierce_count = getattr(projectile, "pierce_count", 0)

                        if p_pierce_all:
                            pass
                        elif p_pierce_count > 0:
                            # decrement and persist on projectile object
                            projectile.pierce_count = (
                                getattr(projectile, "pierce_count", 0) - 1
                            )
                            p_pierce_count = projectile.pierce_count
                            if p_pierce_count <= 0:
                                try:
                                    projectile.kill()
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    try:
                                        g.projectiles.remove(projectile)
                                    except (
                                        AttributeError,
                                        TypeError,
                                        ValueError,
                                        KeyError,
                                    ):
                                        pass
                        else:
                            try:
                                projectile.kill()
                            except (AttributeError, TypeError, ValueError, KeyError):
                                try:
                                    g.projectiles.remove(projectile)
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass

                        # Death handling for enemies (object-style)
                        if getattr(enemy, "health", 0) <= 0:
                            g.add_score(
                                enemy.get("max_health", 10)
                                * ENEMY_SCORE_PER_HEALTH
                                * g.difficulty_multiplier
                            )
                            type_xp_local = {
                                "weak": 10,
                                "normal": 16,
                                "strong": 25,
                                "giant": 50,
                                "angel": 22,
                            }
                            base_xp_local = type_xp_local.get(
                                str(enemy.get("type")), 12
                            )
                            g.player_xp += int(
                                round(base_xp_local * getattr(g, "xp_multiplier", 1.0))
                            )
                            if g.player_xp >= g.xp_to_next_level:
                                g.trigger_level_up()
                            # Ensure burn propagation happens on death regardless of damage source
                            try:
                                if (
                                    enemy.get("burn_propagate_on_death", False)
                                    or enemy.get("burn_propagate_hops", 0) > 0
                                ):
                                    try:
                                        self._propagate_burn(enemy)
                                    except (
                                        AttributeError,
                                        TypeError,
                                        ValueError,
                                        KeyError,
                                    ):
                                        pass
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass
                            try:
                                g.enemies.remove(enemy)
                            except ValueError:
                                pass

                        # Chain hits: storm projectiles can hit additional distinct enemies
                        if isinstance(projectile, dict):
                            chain = projectile.get("chain_targets", 0)
                        else:
                            chain = getattr(projectile, "chain_targets", 0)
                        if (
                            chain
                            and chain > 1
                            and not getattr(projectile, "_chain_applied", False)
                        ):
                            # Build a safe snapshot of nearby candidates (exclude the primary)
                            others = []
                            max_chain_distance = 300
                            for other in g.enemies:
                                if other is enemy:
                                    continue
                                if other.get("health", 0) <= 0:
                                    continue
                                dx_o = other.get("x", 0) - enemy.get("x", 0)
                                dy_o = other.get("y", 0) - enemy.get("y", 0)
                                dist = math.hypot(dx_o, dy_o)
                                if dist <= max_chain_distance:
                                    others.append((dist, other))
                            others.sort(key=lambda t: t[0])
                            to_chain = min(len(others), chain - 1)
                            chain_points = [(enemy.get("x", 0), enemy.get("y", 0))]
                            for targ_dist, targ in others[:to_chain]:
                                # Damage the target (secondary)
                                try:
                                    # dict chain: before damage
                                    pass
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                                eff = self._player_damage_vs_burning(
                                    projectile, targ, p_damage
                                )
                                targ["health"] -= eff * 2
                                try:
                                    # dict chain: after damage
                                    pass
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                                # Record this hit to prevent further hits from the same projectile
                                try:
                                    if not hasattr(projectile, "_hit_ids"):
                                        projectile._hit_ids = set()
                                    projectile._hit_ids.add(id(targ))
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                                tx, ty = g._enemy_pos(targ)
                                chain_points.append((tx, ty))
                                if targ["health"] <= 0:
                                    g.add_score(
                                        targ.get("max_health", 10)
                                        * ENEMY_SCORE_PER_HEALTH
                                        * g.difficulty_multiplier
                                    )
                                    base_xp = 12
                                    g.player_xp += int(
                                        round(
                                            base_xp * getattr(g, "xp_multiplier", 1.0)
                                        )
                                    )
                                    if g.player_xp >= g.xp_to_next_level:
                                        g.trigger_level_up()
                                    # Propagate burn on death even if killed by a weapon/projectile
                                    try:
                                        if (
                                            targ.get("burn_propagate_on_death", False)
                                            or targ.get("burn_propagate_hops", 0) > 0
                                        ):
                                            try:
                                                self._propagate_burn(targ)
                                            except (
                                                AttributeError,
                                                TypeError,
                                                ValueError,
                                                KeyError,
                                            ):
                                                pass
                                    except (
                                        AttributeError,
                                        TypeError,
                                        ValueError,
                                        KeyError,
                                    ):
                                        pass
                                    try:
                                        g.enemies.remove(targ)
                                    except (
                                        AttributeError,
                                        TypeError,
                                        ValueError,
                                        KeyError,
                                    ):
                                        pass
                            if len(chain_points) > 1:
                                g.game_state.chain_lightning_effects.append(
                                    {"points": chain_points, "timer": 8}
                                )
                                projectile._chain_applied = True
                                processed_projectile = True

                    else:
                        # Object-based enemy (sprite/instance)
                        try:
                            dmg_to_apply = self._player_damage_vs_burning(
                                projectile, enemy, p_damage
                            )
                            # Skip if this projectile already recorded a hit on this enemy
                            if id(enemy) in getattr(projectile, "_hit_ids", set()):
                                pass
                            elif self._elemental_shield_can_damage(enemy, projectile):
                                enemy.take_damage(dmg_to_apply, show_floating=False)
                                if (
                                    chain
                                    and chain > 1
                                    and not getattr(projectile, "_chain_applied", False)
                                ):
                                    chain_points = [
                                        (
                                            g._enemy_pos(enemy)[0],
                                            g._enemy_pos(enemy)[1],
                                        )
                                    ]
                                    others = []
                                    max_chain_distance = 300
                                    for other in g._enemies_iter():
                                        if other is enemy:
                                            continue
                                        if getattr(other, "health", 0) <= 0:
                                            continue
                                        ox, oy = g._enemy_pos(other)
                                        exx, eyy = g._enemy_pos(enemy)
                                        dist = math.hypot(ox - exx, oy - eyy)
                                        if dist <= max_chain_distance:
                                            others.append((dist, other))
                                    others.sort(key=lambda t: t[0])
                                    to_chain = min(len(others), chain - 1)
                                    for i in range(to_chain):
                                        targ = others[i][1]
                                        try:
                                            eff = self._player_damage_vs_burning(
                                                projectile, targ, p_damage
                                            )
                                            try:
                                                LOG.debug(
                                                    "handle_collisions chain: proj_id=%s targ_id=%s pre_hit_ids=%s",
                                                    id(projectile),
                                                    id(targ),
                                                    getattr(
                                                        projectile, "_hit_ids", None
                                                    ),
                                                )
                                            except (
                                                AttributeError,
                                                TypeError,
                                                ValueError,
                                                KeyError,
                                            ):
                                                pass
                                            try:
                                                targ.take_damage(
                                                    eff * 2, show_floating=False
                                                )
                                                damaged = True
                                            except (
                                                AttributeError,
                                                TypeError,
                                                ValueError,
                                                KeyError,
                                            ):
                                                try:
                                                    targ.health -= eff * 2
                                                    damaged = True
                                                except (
                                                    AttributeError,
                                                    TypeError,
                                                    ValueError,
                                                    KeyError,
                                                ):
                                                    pass
                                            try:
                                                LOG.debug(
                                                    "handle_collisions chain-done: proj_id=%s targ_id=%s post_hit_ids=%s",
                                                    id(projectile),
                                                    id(targ),
                                                    getattr(
                                                        projectile, "_hit_ids", None
                                                    ),
                                                )
                                            except (
                                                AttributeError,
                                                TypeError,
                                                ValueError,
                                                KeyError,
                                            ):
                                                pass
                                        except (
                                            AttributeError,
                                            TypeError,
                                            ValueError,
                                            KeyError,
                                        ):
                                            try:
                                                eff = self._player_damage_vs_burning(
                                                    projectile, targ, p_damage
                                                )
                                                targ.health -= eff * 2
                                            except (
                                                AttributeError,
                                                TypeError,
                                                ValueError,
                                                KeyError,
                                            ):
                                                pass
                                        tx, ty = g._enemy_pos(targ)
                                        chain_points.append((tx, ty))
                                    if len(chain_points) > 1:
                                        g.game_state.chain_lightning_effects.append(
                                            {"points": chain_points, "timer": 8}
                                        )
                                    projectile._chain_applied = True

                                    try:
                                        projectile.kill()
                                    except (
                                        AttributeError,
                                        TypeError,
                                        ValueError,
                                        KeyError,
                                    ):
                                        try:
                                            g.projectiles.remove(projectile)
                                        except (
                                            AttributeError,
                                            TypeError,
                                            ValueError,
                                            KeyError,
                                        ):
                                            pass
                        except (AttributeError, TypeError, ValueError, KeyError):
                            try:
                                enemy.health -= self._player_damage_vs_burning(
                                    projectile, enemy, p_damage
                                )
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass

                        # Record this hit so projectile won't hit the same enemy again
                        try:
                            if hit_ids is None:
                                if not hasattr(projectile, "_hit_ids"):
                                    projectile._hit_ids = set()
                                hit_ids = projectile._hit_ids
                            hit_ids.add(id(enemy))
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass

                        # Apply slow effect if projectile has it (Ice towers)
                        if effect == "slow":
                            if self._elemental_shield_can_damage(enemy, projectile):
                                if (
                                    not hasattr(enemy, "slow_timer")
                                    or getattr(enemy, "slow_timer", 0) <= 0
                                ):
                                    enemy.slow_timer = slow_duration
                                    enemy.slow_factor = slow_factor
                                    if not hasattr(enemy, "original_speed"):
                                        enemy.original_speed = enemy.speed
                                    enemy.speed = enemy.speed * enemy.slow_factor
                            else:
                                self._show_immune_text(enemy)

                        # Apply burn effect (Fire towers)
                        if effect == "burn":
                            if self._elemental_shield_can_damage(enemy, projectile):
                                if (
                                    not hasattr(enemy, "burn_timer")
                                    or getattr(enemy, "burn_timer", 0) <= 0
                                ):
                                    enemy.burn_timer = burn_duration
                                    enemy.burn_damage_per_second = burn_dps
                                    # Counter for per-second ticks
                                    enemy.burn_tick_timer = getattr(g, "fps", 60)
                            else:
                                self._show_immune_text(enemy)

                        # Handle projectile piercing / kill (support dict or object projectiles)
                        if p_pierce_all:
                            pass
                        elif p_pierce_count > 0:
                            # decrement and persist on projectile object (object-only)
                            projectile.pierce_count = (
                                getattr(projectile, "pierce_count", 0) - 1
                            )
                            p_pierce_count = projectile.pierce_count
                            if p_pierce_count <= 0:
                                try:
                                    projectile.kill()
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    try:
                                        g.projectiles.remove(projectile)
                                    except (
                                        AttributeError,
                                        TypeError,
                                        ValueError,
                                        KeyError,
                                    ):
                                        pass
                        else:
                            try:
                                projectile.kill()
                            except (AttributeError, TypeError, ValueError, KeyError):
                                try:
                                    g.projectiles.remove(projectile)
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                            else:
                                projectile.kill()

                        # Death handling for object enemies
                        if getattr(enemy, "health", 0) <= 0:
                            g.add_score(
                                enemy.max_health
                                * ENEMY_SCORE_PER_HEALTH
                                * g.difficulty_multiplier
                            )
                            type_xp_local = {
                                "weak": 10,
                                "normal": 16,
                                "strong": 25,
                                "giant": 50,
                                "angel": 22,
                            }
                            base_xp_local = type_xp_local.get(
                                str(enemy.enemy_type), 12
                            )  # fallback XP
                            g.player_xp += int(
                                round(base_xp_local * getattr(g, "xp_multiplier", 1.0))
                            )
                            if g.player_xp >= g.xp_to_next_level:
                                g.trigger_level_up()
                            # Ensure propagation fires even if enemy was killed by a weapon/projectile
                            try:
                                if (
                                    getattr(enemy, "burn_propagate_on_death", False)
                                    or getattr(enemy, "burn_propagate_hops", 0) > 0
                                ):
                                    try:
                                        # DIAG: log propagation call for sprite-based death
                                        LOG.debug(
                                            "_propagate_burn called from projectile-kill for sprite enemy; burn_propagate_on_death=%s, hops=%s",
                                            getattr(
                                                enemy, "burn_propagate_on_death", False
                                            ),
                                            getattr(enemy, "burn_propagate_hops", 0),
                                        )
                                        self._propagate_burn(enemy)
                                    except (
                                        AttributeError,
                                        TypeError,
                                        ValueError,
                                        KeyError,
                                    ):
                                        pass
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass
                        try:
                            g.record_enemy_kill()
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                        # Chain hits: storm projectiles can hit additional distinct enemies
                        if isinstance(projectile, dict):
                            chain = projectile.get("chain_targets", 0)
                        else:
                            chain = getattr(projectile, "chain_targets", 0)
                        if (
                            chain
                            and chain > 1
                            and not getattr(projectile, "_chain_applied", False)
                        ):
                            others = []
                            # Gather other enemy candidates
                            for other in g._enemies_iter():
                                if other is enemy:
                                    continue
                                if getattr(other, "health", 0) <= 0:
                                    continue
                                ox, oy = g._enemy_pos(other)
                                exx, eyy = g._enemy_pos(enemy)
                                dist = math.hypot(ox - exx, oy - eyy)
                                others.append((dist, other))
                            others.sort(key=lambda t: t[0])
                            to_chain = min(len(others), chain - 1)

                            # Prepare visual chain points (always include primary)
                            chain_points = [
                                (g._enemy_pos(enemy)[0], g._enemy_pos(enemy)[1])
                            ]

                            for i in range(to_chain):
                                targ = others[i][1]
                                if isinstance(targ, dict):
                                    eff = self._player_damage_vs_burning(
                                        projectile, targ, p_damage
                                    )
                                    targ["health"] -= (
                                        eff * 2
                                    )  # Increased damage for secondary targets
                                    if targ["health"] <= 0:
                                        g.add_score(
                                            targ.get("max_health", 10)
                                            * ENEMY_SCORE_PER_HEALTH
                                            * g.difficulty_multiplier
                                        )
                                        type_xp_local = {
                                            "weak": 10,
                                            "normal": 16,
                                            "strong": 25,
                                            "giant": 50,
                                            "angel": 22,
                                        }
                                        base_xp_local = type_xp_local.get(
                                            str(targ.get("type")), 12
                                        )
                                        g.player_xp += int(
                                            round(
                                                base_xp_local
                                                * getattr(g, "xp_multiplier", 1.0)
                                            )
                                        )
                                        if g.player_xp >= g.xp_to_next_level:
                                            g.trigger_level_up()
                                        try:
                                            try:
                                                g.record_enemy_kill()
                                            except (
                                                AttributeError,
                                                TypeError,
                                                ValueError,
                                                KeyError,
                                            ):
                                                pass
                                            g.enemies.remove(targ)
                                        except (
                                            AttributeError,
                                            TypeError,
                                            ValueError,
                                            KeyError,
                                        ):
                                            pass
                                else:
                                    try:
                                        eff = self._player_damage_vs_burning(
                                            projectile, targ, p_damage
                                        )
                                        targ.take_damage(
                                            eff * 2,
                                            show_floating=False,
                                        )  # Increased damage for secondary targets
                                    except (
                                        AttributeError,
                                        TypeError,
                                        ValueError,
                                        KeyError,
                                    ):
                                        try:
                                            eff = self._player_damage_vs_burning(
                                                projectile, targ, p_damage
                                            )
                                            targ.health -= (
                                                eff * 2
                                            )  # Increased damage for secondary targets
                                        except (
                                            AttributeError,
                                            TypeError,
                                            ValueError,
                                            KeyError,
                                        ):
                                            pass
                                    if getattr(targ, "health", 0) <= 0:
                                        g.add_score(
                                            targ.max_health
                                            * ENEMY_SCORE_PER_HEALTH
                                            * g.difficulty_multiplier
                                        )
                                        type_xp_local = {
                                            "weak": 10,
                                            "normal": 16,
                                            "strong": 25,
                                            "giant": 50,
                                            "angel": 22,
                                        }
                                        base_xp_local = type_xp_local.get(
                                            targ.enemy_type, 12
                                        )
                                        g.player_xp += int(
                                            round(
                                                base_xp_local
                                                * getattr(g, "xp_multiplier", 1.0)
                                            )
                                        )
                                        if g.player_xp >= g.xp_to_next_level:
                                            g.trigger_level_up()
                                        try:
                                            g.record_enemy_kill()
                                        except (
                                            AttributeError,
                                            TypeError,
                                            ValueError,
                                            KeyError,
                                        ):
                                            pass
                                        targ.kill()

                                # add visual point for this chained target
                                tx, ty = g._enemy_pos(targ)
                                chain_points.append((tx, ty))

                            # append visual effect when we actually chained at least once
                            if len(chain_points) > 1:
                                g.game_state.chain_lightning_effects.append(
                                    {"points": chain_points, "timer": 8}
                                )
                            projectile._chain_applied = True
                            processed_projectile = True
                    break

            # Projectiles hit bosses (only for sprite projectiles)
            hit_bosses: List[Any] = []
            if hasattr(projectile, "rect"):
                hit_bosses = pygame.sprite.spritecollide(projectile, g.bosses, False)
            # Debug: show projectile -> boss collision detection (debug-level)
            try:
                LOG.debug(
                    "projectile.appearance=%s, projectile.effect=%s, hit_bosses_count=%s",
                    getattr(projectile, "appearance", None),
                    getattr(projectile, "effect", None),
                    len(hit_bosses),
                )
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
            for boss in hit_bosses:
                # Skip if this projectile already hit this exact boss instance
                try:
                    LOG.debug(
                        "handle_collisions: processing boss hit. projectile.effect=%s, effect_var=%s",
                        getattr(projectile, "effect", None),
                        locals().get("effect", None),
                    )
                    if not hasattr(projectile, "_hit_ids"):
                        projectile._hit_ids = set()
                    hit_ids_local = projectile._hit_ids
                    if not hasattr(projectile, "_hit_boss_types"):
                        projectile._hit_boss_types = set()
                    hit_boss_types_local = projectile._hit_boss_types
                    if id(boss) in hit_ids_local or (
                        getattr(boss, "enemy_type", "") in hit_boss_types_local
                    ):
                        continue
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

                if boss.enemy_type == "boss_final" and g.selected_stage == "prologo":
                    if g.prologo_final_boss_immortal:
                        continue  # Invulnerable
                    else:
                        bd = self._player_damage_vs_burning(
                            projectile, boss, getattr(projectile, "damage", 0)
                        )
                        boss.take_damage(bd)
                        self._maybe_charge_tower(projectile)
                        if boss.health <= boss.max_health * 0.1:
                            g.prologo_final_boss_immortal = True
                            boss.health = int(boss.max_health * 0.1)
                elif (
                    boss.enemy_type == "boss_limbo"
                    and g.selected_stage == "limbo_final"
                ):
                    if g.limbo_final_boss_immortal:
                        continue
                    else:
                        bd = self._player_damage_vs_burning(
                            projectile, boss, getattr(projectile, "damage", 0)
                        )
                        boss.take_damage(bd)
                        self._maybe_charge_tower(projectile)
                        if boss.health <= boss.max_health * 0.1:
                            g.limbo_final_boss_immortal = True
                            boss.health = int(boss.max_health * 0.1)
                else:
                    bd = self._player_damage_vs_burning(
                        projectile, boss, getattr(projectile, "damage", 0)
                    )
                    # Cross Bearer: shield absorbs ALL hits while active.
                    # Shield has 100 HP; reflects projectile back until broken.
                    # Once broken, body takes damage normally (5s regen).
                    _cb_reflected = False
                    if getattr(boss, "enemy_type", "") == "cross_bearer":
                        cb_shield = getattr(boss, "cb_shield_hp", 0)
                        cb_broken = getattr(boss, "_shield_broken", False)
                        if not cb_broken and cb_shield > 0:
                            # Shield active: absorb damage and reflect
                            boss.cb_shield_hp = max(0, cb_shield - int(bd))
                            boss._shield_regen_timer = 0
                            if boss.cb_shield_hp <= 0:
                                boss._shield_broken = True
                                boss.shake_timer = 12
                                try:
                                    g.spawn_floating_text(
                                        "SHIELD BROKEN",
                                        int(boss.x),
                                        int(boss.y) - 30,
                                        color=(100, 180, 255),
                                        font_size=18,
                                    )
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                            else:
                                # Reflect projectile back toward player
                                pvx = getattr(projectile, "vel_x", 0)
                                pvy = getattr(projectile, "vel_y", 0)
                                projectile.vel_x = -pvx
                                projectile.vel_y = -pvy
                                projectile.is_enemy_projectile = True
                                projectile.damage = max(1, int(bd * 0.8))
                                # Move reflected projectile from player projectiles to enemy projectiles
                                # so it will damage the player when it hits
                                try:
                                    if projectile in g.projectiles:
                                        g.projectiles.remove(projectile)
                                    g.enemy_projectiles.add(projectile)
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                                # Show "REFLECTED" only once every 2 seconds (120 frames) to avoid spam
                                try:
                                    last_reflect_msg = getattr(
                                        boss, "_last_reflect_msg_time", -120
                                    )
                                    current_time = g.time_elapsed * g.fps
                                    if current_time - last_reflect_msg >= 120:
                                        g.spawn_floating_text(
                                            "REFLECTED",
                                            int(boss.x),
                                            int(boss.y) - 20,
                                            color=(160, 210, 255),
                                            font_size=14,
                                        )
                                        boss._last_reflect_msg_time = current_time
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                            _cb_reflected = True
                    if not _cb_reflected:
                        # boss should show floating damage numbers
                        boss.take_damage(bd)
                    self._maybe_charge_tower(projectile)

                # Ensure projectiles that carry slow/burn also apply to bosses (defensive/duplicate path)
                try:
                    if getattr(projectile, "effect", None) == "slow":
                        if self._elemental_shield_can_damage(boss, projectile):
                            # apply slow metadata directly from projectile as a defensive path
                            try:
                                # use helper to apply slow
                                self._apply_slow_effect(
                                    boss,
                                    getattr(projectile, "slow_duration", 120),
                                    getattr(projectile, "slow_factor", 0.5),
                                )
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass
                        else:
                            self._show_immune_text(boss)
                    if getattr(projectile, "effect", None) == "burn":
                        if self._elemental_shield_can_damage(boss, projectile):
                            # Only apply burn if not already burning
                            if (
                                not hasattr(boss, "burn_timer")
                                or getattr(boss, "burn_timer", 0) <= 0
                            ):
                                boss.burn_timer = burn_duration
                                boss.burn_damage_per_second = burn_dps
                                boss.burn_tick_timer = getattr(g, "fps", 60)
                                # If FIRE tier 1 is active, mark this burn to propagate on death
                                try:
                                    if g.permanent_stats.get("fire_1", 0):
                                        boss.burn_propagate_on_death = True
                                        boss.burn_propagate_radius = 150
                                        boss.burn_propagate_dps = burn_dps
                                        boss.burn_propagate_duration = burn_duration
                                        boss.burn_propagate_hops = 2
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                        else:
                            self._show_immune_text(boss)
                    elif getattr(projectile, "effect", None) == "slow":
                        if self._elemental_shield_can_damage(boss, projectile):
                            # another slow branch, use helper
                            self._apply_slow_effect(boss, slow_duration, slow_factor)
                        else:
                            self._show_immune_text(boss)
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

                # Fallback: ensure slow from projectiles is applied to bosses even if
                # the primary code path above was skipped due to an edge-case.
                try:
                    if (
                        getattr(projectile, "effect", None) == "slow"
                        and getattr(boss, "slow_timer", 0) <= 0
                    ):
                        if self._elemental_shield_can_damage(boss, projectile):
                            self._apply_slow_effect(
                                boss,
                                getattr(projectile, "slow_duration", 120),
                                getattr(projectile, "slow_factor", 0.5),
                            )
                        else:
                            self._show_immune_text(boss)
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
                # Record that this projectile has hit this boss/type so it won't hit again
                try:
                    if not hasattr(projectile, "_hit_ids"):
                        projectile._hit_ids = set()
                    projectile._hit_ids.add(id(boss))
                    if not hasattr(projectile, "_hit_boss_types"):
                        projectile._hit_boss_types = set()
                    projectile._hit_boss_types.add(getattr(boss, "enemy_type", ""))
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

                # Handle projectile piercing for bosses too
                # NOTE: Spears should not pierce bosses — treat spear as single-hit for bosses
                # Reflected projectiles (Cross Bearer shield) are NOT removed — they travel back
                if _cb_reflected:
                    pass  # Reflected: keep alive, now travels as enemy projectile
                elif (
                    getattr(projectile, "pierce_all", False)
                    and getattr(projectile, "weapon_type", None) != "spear"
                ):
                    # Non-spear projectiles that pierce may continue through bosses
                    pass
                elif getattr(projectile, "pierce_count", 0) > 0:
                    projectile.pierce_count -= 1
                    if projectile.pierce_count <= 0:
                        projectile.kill()
                else:
                    # Default: remove projectile after hitting a boss (also covers spear)
                    projectile.kill()

                if boss.health <= 0:
                    # For limbo horde: don't set victory flags here; let the game.update() detect
                    # the dead boss and handle it. This ensures the boss stays in the list long
                    # enough for the detection code to find it.
                    if boss.enemy_type == "boss_limbo_horde":
                        # Show defeat message
                        try:
                            g.show_centered_message(
                                "HORDE DEFEATED!", 2000, (255, 255, 0)
                            )
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                        # Stop spawning more waves
                        try:
                            g.wave_time = g.wave_duration
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                        # Don't call .empty() here; let game.update() handle the cleanup
                        # This ensures the boss death is properly detected
                        if getattr(g, "debug", False):
                            print(
                                "[LIMBO_HORDE] Boss marked dead in collision; game.update() will detect and clean up"
                            )
                    g.add_score(boss.max_health * 25)
                    # Give XP for boss kill (per-type table, flat values)
                    boss_xp_map: Dict[str, int] = {
                        "medium": 80,
                        "big": 150,
                        "final": 400,
                    }
                    boss_base_xp: int = boss_xp_map.get(
                        boss.enemy_type.replace("boss_", ""), 100
                    )
                    g.player_xp += int(
                        round(boss_base_xp * getattr(g, "xp_multiplier", 1.0))
                    )
                    if g.player_xp >= g.xp_to_next_level:
                        g.trigger_level_up()
                    # record boss kill like a normal enemy (awards meta XP)
                    try:
                        g.record_enemy_kill()
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass
                    # give a small amount of meta XP for boss kills so the
                    # external progress bar advances mid-run; use 10% of
                    # boss_base_xp (rounded)
                    try:
                        g.award_meta_xp(int(boss_base_xp * 0.1))
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass
                    # Health drop spawning is handled by DeathSystem
                    # Don't kill boss_limbo_horde here — game.update()
                    # needs it in the bosses group to detect death and
                    # start the victory countdown.
                    if boss.enemy_type != "boss_limbo_horde":
                        boss.kill()
                    _do_reinforce_col = boss.enemy_type == "boss_medium" or (
                        boss.enemy_type == "cross_bearer" and random.random() < 0.5
                    )
                    if _do_reinforce_col:
                        g.show_centered_message(
                            "REINFORCEMENTS INCOMING!", 1800, (255, 204, 0)
                        )
                        # Clear any existing reinforcement timer and schedule new one
                        pygame.time.set_timer(pygame.USEREVENT + 1, 0)
                        pygame.time.set_timer(
                            pygame.USEREVENT + 1, g.reinforcement_delay_ms
                        )
                    elif (
                        boss.enemy_type == "boss_final"
                        and not g.prologo_final_boss_immortal
                    ):
                        g.prologo_final_boss_defeated = True
                break

            # Chain hits for bosses: storm projectiles can hit additional distinct enemies
            if hit_bosses:
                primary_boss = hit_bosses[0]  # First boss hit
                chain = getattr(projectile, "chain_targets", 0)
                if chain and chain > 1:
                    others = []
                    # Gather other enemy candidates within chain range (both enemies and bosses)
                    max_chain_distance = (
                        300  # Maximum distance for chain lightning (pixels)
                    )

                    # Cache primary position once (optimization: avoid redundant lookups)
                    px, py = g._enemy_pos(primary_boss)

                    # Check other bosses
                    for other_boss in g.bosses.sprites():
                        if other_boss is primary_boss:
                            continue
                        if getattr(other_boss, "health", 0) <= 0:
                            continue
                        bx, by = g._enemy_pos(other_boss)
                        dist = math.hypot(bx - px, by - py)
                        if dist <= max_chain_distance:
                            others.append((dist, other_boss))

                    # Check regular enemies
                    for other_enemy in g.enemies.sprites():
                        if getattr(other_enemy, "health", 0) <= 0:
                            continue
                        ex, ey = g._enemy_pos(other_enemy)
                        dist = math.hypot(ex - px, ey - py)
                        if dist <= max_chain_distance:
                            others.append((dist, other_enemy))

                    others.sort(key=lambda t: t[0])
                    to_chain = min(len(others), chain - 1)

                    # Store chain lightning effect for visual (use cached position)
                    chain_points = [(px, py)]

                    for i in range(to_chain):
                        targ = others[i][1]
                        eff = self._player_damage_vs_burning(
                            projectile, targ, getattr(projectile, "damage", 0)
                        )
                        targ.take_damage(
                            eff * 2,
                            show_floating=False,
                        )  # Increased damage for secondary targets

                        # Add to chain points for visual effect (cache target position)
                        tx, ty = g._enemy_pos(targ)
                        chain_points.append((tx, ty))

                        # death handling for chained targets
                        if targ.health <= 0:
                            if hasattr(
                                targ, "enemy_type"
                            ) and targ.enemy_type.startswith("boss_"):
                                # Boss death handling
                                g.add_score(targ.max_health * 25)
                                boss_xp_map = {
                                    "medium": 80,
                                    "big": 150,
                                    "final": 400,
                                }
                                boss_base_xp = boss_xp_map.get(
                                    targ.enemy_type.replace("boss_", ""), 100
                                )
                                g.player_xp += int(
                                    round(
                                        boss_base_xp * getattr(g, "xp_multiplier", 1.0)
                                    )
                                )
                                if g.player_xp >= g.xp_to_next_level:
                                    g.trigger_level_up()
                                targ.kill()
                                try:
                                    g.record_enemy_kill()
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                            else:
                                # Regular enemy death handling
                                g.add_score(
                                    targ.max_health
                                    * ENEMY_SCORE_PER_HEALTH
                                    * g.difficulty_multiplier
                                )
                                type_xp_local = {
                                    "weak": 10,
                                    "normal": 16,
                                    "strong": 25,
                                    "giant": 50,
                                    "angel": 22,
                                }
                                base_xp_local = type_xp_local.get(targ.enemy_type, 12)
                                g.player_xp += int(
                                    round(
                                        base_xp_local * getattr(g, "xp_multiplier", 1.0)
                                    )
                                )
                                if g.player_xp >= g.xp_to_next_level:
                                    g.trigger_level_up()
                                targ.kill()
                                try:
                                    g.record_enemy_kill()
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass

                    # Add chain lightning effect to game state
                    if len(chain_points) > 1:
                        g.game_state.chain_lightning_effects.append(
                            {"points": chain_points, "timer": 8}  # Show for 8 frames
                        )
                        # Mark chain applied so we don't duplicate
                        projectile._chain_applied = True
        hit_projectiles: List[Any] = pygame.sprite.spritecollide(
            g.player, g.enemy_projectiles, False
        )
        for projectile in hit_projectiles:
            actual_damage = projectile.damage * g.damage_reduction_multiplier
            # Skip damage if player is invulnerable during blink
            if not getattr(g, "blasphemy_5_invulnerable", False):
                g.player.take_damage(actual_damage)
            # Apply slow effect to player if projectile carries it (skip if invulnerable)
            if not getattr(g, "blasphemy_5_invulnerable", False):
                try:
                    if getattr(projectile, "effect", None) == "slow":
                        slow_duration = getattr(projectile, "slow_duration", 120)
                        slow_factor = getattr(projectile, "slow_factor", 0.5)
                        if (
                            not hasattr(g.player, "slow_timer")
                            or getattr(g.player, "slow_timer", 0) <= 0
                        ):
                            g.player.slow_timer = slow_duration
                            g.player.slow_factor = slow_factor
                            if not hasattr(g.player, "original_speed"):
                                g.player.original_speed = g.player.speed
                            g.player.speed = g.player.speed * g.player.slow_factor
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

            # Trigger screen & player shake
            g.shake_timer = 8
            g.shake_intensity = max(g.shake_intensity, 8)
            projectile.kill()

        # Enemies hit player
        if hasattr(g.enemies, "sprites"):
            hit_enemies = pygame.sprite.spritecollide(g.player, g.enemies, False)
            for enemy in hit_enemies:
                # winged units explode on player contact
                if getattr(enemy, "enemy_type", "") == "winged":
                    # play small explosion effect and deal flat damage
                    try:
                        from src.game_constants import (
                            WINGED_CONTACT_DAMAGE,
                            WINGED_EXPLOSION_COLOR,
                            WINGED_EXPLOSION_DURATION,
                            WINGED_EXPLOSION_RADIUS,
                        )
                    except (AttributeError, TypeError, ValueError, KeyError):
                        WINGED_EXPLOSION_RADIUS = 30
                        WINGED_EXPLOSION_DURATION = 6
                        WINGED_EXPLOSION_COLOR = (255, 120, 0)
                        WINGED_CONTACT_DAMAGE = 15
                    # Skip damage if player is invulnerable during blink
                    if not getattr(g, "blasphemy_5_invulnerable", False):
                        try:
                            g.player.take_damage(
                                WINGED_CONTACT_DAMAGE, show_floating=False
                            )
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                    try:
                        g.game_state.fire_explosions.append(
                            {
                                "x": enemy.x,
                                "y": enemy.y,
                                "radius": WINGED_EXPLOSION_RADIUS,
                                "timer": WINGED_EXPLOSION_DURATION,
                                "max_timer": WINGED_EXPLOSION_DURATION,
                                "color": WINGED_EXPLOSION_COLOR,
                            }
                        )
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass
                    # remove the enemy immediately
                    try:
                        enemy.kill()
                    except (AttributeError, TypeError, ValueError, KeyError):
                        try:
                            g.enemies.remove(enemy)
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                    # skip the normal contact handling
                    continue

                actual_damage = (enemy.damage / g.fps) * g.damage_reduction_multiplier
                # Skip damage if player is invulnerable during blink transit
                if not getattr(g, "blasphemy_5_invulnerable", False):
                    g.player.take_damage(actual_damage, show_floating=False)

                # contact damage to enemy is now applied as a lump every
                # two seconds rather than continuously.  we track a timer on
                # the enemy instance which counts down each frame while the
                # two hitboxes overlap; when it reaches zero we deal a fixed
                # amount (4 HP) and reset the timer.  leaving contact clears
                # the timer so the next collision starts fresh.
                try:
                    if not hasattr(enemy, "contact_timer"):
                        # start counting once we detect the first frame of
                        # contact.  2s * fps frames.
                        enemy.contact_timer = int(g.fps * 2)
                    else:
                        enemy.contact_timer -= 1
                    if enemy.contact_timer <= 0:
                        _eshield_active = getattr(
                            enemy, "shield_hp", 0
                        ) > 0 and getattr(enemy, "enemy_type", "") in (
                            "pentagram_fire",
                            "pentagram_storm",
                            "pentagram_ice",
                        )
                        if not _eshield_active:
                            enemy.take_damage(4, show_floating=False)
                        enemy.contact_timer = int(g.fps * 2)
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
                if g.frame_count % 10 == 0:
                    # Shorter, weaker shake for contact (burn particles disabled)
                    g.shake_timer = 6
                    g.shake_intensity = max(g.shake_intensity, 6)

                # Armor spine effect (visual removed)
                if g.upgrade_levels.get("armor", 0) > 0:
                    reflect_ratio: float = min(0.3 * g.upgrade_levels["armor"], 0.9)
                    reflected = actual_damage * reflect_ratio
                    _eshield_active2 = getattr(enemy, "shield_hp", 0) > 0 and getattr(
                        enemy, "enemy_type", ""
                    ) in ("pentagram_fire", "pentagram_storm", "pentagram_ice")
                    if not _eshield_active2:
                        enemy.take_damage(reflected, show_floating=False)
        else:
            for enemy in list(g.enemies):
                ex, ey = g._enemy_pos(enemy)
                er = g._enemy_radius(enemy)
                dx = ex - g.player.x
                dy = ey - g.player.y
                if dx * dx + dy * dy <= (er + (g.player.width // 2)) ** 2:
                    # winged explosion behavior for non-sprite enemies
                    if getattr(enemy, "enemy_type", "") == "winged":
                        try:
                            from src.game_constants import (
                                WINGED_CONTACT_DAMAGE,
                                WINGED_EXPLOSION_COLOR,
                                WINGED_EXPLOSION_DURATION,
                                WINGED_EXPLOSION_RADIUS,
                            )
                        except (AttributeError, TypeError, ValueError, KeyError):
                            WINGED_EXPLOSION_RADIUS = 30
                            WINGED_EXPLOSION_DURATION = 6
                            WINGED_EXPLOSION_COLOR = (255, 120, 0)
                            WINGED_CONTACT_DAMAGE = 15
                        try:
                            # Skip damage if player is invulnerable during blink transit
                            if not getattr(g, "blasphemy_5_invulnerable", False):
                                g.player.take_damage(
                                    WINGED_CONTACT_DAMAGE, show_floating=False
                                )
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                        try:
                            g.game_state.fire_explosions.append(
                                {
                                    "x": enemy.x,
                                    "y": enemy.y,
                                    "radius": WINGED_EXPLOSION_RADIUS,
                                    "timer": WINGED_EXPLOSION_DURATION,
                                    "max_timer": WINGED_EXPLOSION_DURATION,
                                    "color": WINGED_EXPLOSION_COLOR,
                                }
                            )
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                        # attempt to remove object-style enemy
                        try:
                            g.enemies.remove(enemy)
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                        continue

                    actual_damage = (
                        getattr(enemy, "damage", 5) / g.fps
                    ) * g.damage_reduction_multiplier
                    # Skip damage if player is invulnerable during blink transit
                    if not getattr(g, "blasphemy_5_invulnerable", False):
                        g.player.take_damage(actual_damage, show_floating=False)

                    try:
                        if not hasattr(enemy, "contact_timer"):
                            enemy.contact_timer = int(g.fps * 2)
                        else:
                            enemy.contact_timer -= 1
                        if enemy.contact_timer <= 0:
                            _eshield_active3 = getattr(
                                enemy, "shield_hp", 0
                            ) > 0 and getattr(enemy, "enemy_type", "") in (
                                "pentagram_fire",
                                "pentagram_storm",
                                "pentagram_ice",
                            )
                            if not _eshield_active3:
                                enemy.take_damage(4, show_floating=False)
                            enemy.contact_timer = int(g.fps * 2)
                    except (AttributeError, TypeError, ValueError, KeyError):
                        # Best-effort fallback: apply tiny constant damage
                        try:
                            enemy.health = max(
                                0, getattr(enemy, "health", 0) - (2.0 / g.fps)
                            )
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                    if g.frame_count % 10 == 0:
                        # Shorter, weaker shake for contact (burn particles disabled)
                        g.shake_timer = 6
                        g.shake_intensity = max(g.shake_intensity, 6)

                    # Armor spine effect (visual removed)
                    if g.upgrade_levels.get("armor", 0) > 0:
                        reflect_ratio = min(0.3 * g.upgrade_levels["armor"], 0.9)
                        reflected = actual_damage * reflect_ratio
                        _eshield_active4 = getattr(
                            enemy, "shield_hp", 0
                        ) > 0 and getattr(enemy, "enemy_type", "") in (
                            "pentagram_fire",
                            "pentagram_storm",
                            "pentagram_ice",
                        )
                        if not _eshield_active4:
                            enemy.take_damage(reflected, show_floating=False)
        # Bosses hit player
        hit_bosses = pygame.sprite.spritecollide(g.player, g.bosses, False)
        for boss in hit_bosses:
            contact_damage = (boss.damage / g.fps) * g.damage_reduction_multiplier
            g.player.take_damage(contact_damage, show_floating=False)
            if g.frame_count % 10 == 0:
                # Boss contact should produce a noticeable shake
                g.shake_timer = 6
                g.shake_intensity = max(g.shake_intensity, 6)

        # Update Flies effects on enemies
        for enemy in list(g.enemies):
            if hasattr(enemy, "drain_timer") and enemy.drain_timer > 0:
                enemy.drain_timer -= 1
                if enemy.drain_timer % 60 == 0:  # Every second
                    damage = getattr(enemy, "drain_damage", 1)
                    heal = getattr(enemy, "drain_heal", 1)
                    _eshield_flies = getattr(enemy, "shield_hp", 0) > 0 and getattr(
                        enemy, "enemy_type", ""
                    ) in ("pentagram_fire", "pentagram_storm", "pentagram_ice")
                    if not _eshield_flies:
                        enemy.take_damage(damage)
                    # spawn centralized floating text for drain tick
                    try:
                        ex, ey = g._enemy_pos(enemy)
                        g.spawn_floating_text(
                            str(int(damage)), ex, ey - g._enemy_radius(enemy) - 8
                        )
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass
                    g.player.health = min(g.player.max_health, g.player.health + heal)
                if enemy.drain_timer <= 0:
                    # Remove drain attributes
                    if hasattr(enemy, "drain_timer"):
                        delattr(enemy, "drain_timer")
                    if hasattr(enemy, "drain_damage"):
                        delattr(enemy, "drain_damage")
                    if hasattr(enemy, "drain_heal"):
                        delattr(enemy, "drain_heal")
                    if hasattr(enemy, "drain_source"):
                        delattr(enemy, "drain_source")

        # If enemies is a plain list, update drain timers for object enemies
        if not hasattr(g.enemies, "update"):
            for enemy in list(g.enemies):
                if getattr(enemy, "drain_timer", 0) > 0:
                    enemy.drain_timer -= 1
                    if enemy.drain_timer % 60 == 0:
                        damage = getattr(enemy, "drain_damage", 1)
                        heal = getattr(enemy, "drain_heal", 1)
                        try:
                            _eshield_flies2 = getattr(
                                enemy, "shield_hp", 0
                            ) > 0 and getattr(enemy, "enemy_type", "") in (
                                "pentagram_fire",
                                "pentagram_storm",
                                "pentagram_ice",
                            )
                            if not _eshield_flies2:
                                enemy.take_damage(damage)
                        except (AttributeError, TypeError, ValueError, KeyError):
                            try:
                                enemy.health = max(
                                    0, getattr(enemy, "health", 0) - damage
                                )
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass
                        try:
                            ex, ey = g._enemy_pos(enemy)
                            g.spawn_floating_text(
                                str(int(damage)), ex, ey - g._enemy_radius(enemy) - 8
                            )
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                        g.player.health = min(
                            g.player.max_health, g.player.health + heal
                        )
                    if enemy.drain_timer <= 0:
                        for attr in (
                            "drain_timer",
                            "drain_damage",
                            "drain_heal",
                            "drain_source",
                        ):
                            if hasattr(enemy, attr):
                                try:
                                    delattr(enemy, attr)
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass

        # Update slow timers for all enemies
        for enemy in g.enemies:
            if hasattr(enemy, "slow_timer") and getattr(enemy, "slow_timer", 0) > 0:
                enemy.slow_timer -= 1
                if enemy.slow_timer <= 0:
                    # Reset slow_factor for enemy objects
                    if hasattr(enemy, "slow_factor"):
                        enemy.slow_factor = 1.0
                    # Reset speed if original_speed was saved
                    if hasattr(enemy, "original_speed"):
                        enemy.speed = getattr(enemy, "original_speed", enemy.speed)
                        delattr(enemy, "original_speed")

        # Update slow timers for bosses
        if hasattr(g, "bosses") and g.bosses:
            for boss in g.bosses:
                if hasattr(boss, "slow_timer") and getattr(boss, "slow_timer", 0) > 0:
                    boss.slow_timer -= 1
                    if boss.slow_timer <= 0:
                        # Reset slow_factor for bosses
                        if hasattr(boss, "slow_factor"):
                            boss.slow_factor = 1.0
                        # Reset speed if original_speed was saved
                        if hasattr(boss, "original_speed"):
                            boss.speed = getattr(boss, "original_speed", boss.speed)
                            if hasattr(boss, "original_speed"):
                                delattr(boss, "original_speed")

        # Orbitals damage enemies on contact (flat 15 per orb per creature)
        if "orbital" in g.player_weapons:
            # Calculate orbital damage based on level (+10% at levels 3 and 5)
            orbital_level = g.weapon_levels.get("orbital", 1)
            orbital_damage = 15
            if orbital_level >= 3:
                orbital_damage = int(orbital_damage * 1.1)  # +10% at level 3+
            if orbital_level >= 5:
                orbital_damage = int(
                    orbital_damage * 1.1
                )  # +10% at level 5+ (stacks: 1.1 * 1.1 = 1.21x)

            for orbital in g.orbitals:
                ox = orbital.get("x", g.player.x)
                oy = orbital.get("y", g.player.y)
                # track which enemies have already been hit by this orbital
                hits: set = orbital.setdefault("hit", set())

                for enemy in g._enemies_iter():
                    ex, ey = g._enemy_pos(enemy)
                    dist = math.hypot(ex - ox, ey - oy)
                    eid = id(enemy)
                    if dist < enemy.radius + 6:  # orbital radius is 6
                        if eid not in hits:
                            # apply a one‑time orbital damage with level bonuses
                            _eshield_orb = getattr(
                                enemy, "shield_hp", 0
                            ) > 0 and getattr(enemy, "enemy_type", "") in (
                                "pentagram_fire",
                                "pentagram_storm",
                                "pentagram_ice",
                            )
                            if not _eshield_orb:
                                enemy.take_damage(orbital_damage)
                            hits.add(eid)
                    else:
                        # enemy has moved away, allow future re-hits
                        if eid in hits:
                            hits.remove(eid)

                for boss in g.bosses:
                    dist = math.hypot(boss.x - ox, boss.y - oy)
                    bid = id(boss)
                    if dist < boss.radius + 6:
                        if bid not in hits:
                            boss.take_damage(orbital_damage)
                            hits.add(bid)
                    else:
                        if bid in hits:
                            hits.remove(bid)

        # Fallback: in case a boss somehow reached zero health without
        # going through the normal boss-hit branch above (e.g. an atypical
        # projectile lacking a ``rect`` or damage applied externally during a
        # test), ensure we still credit the kill and award meta XP.  This also
        # serves as a safety net for any future codepaths that bypass the main
        # boss logic.  We intentionally perform the check _before_ the level-up
        # trigger so the extra XP carries over correctly.
        for boss in list(getattr(g, "bosses", []) or []):
            try:
                if getattr(boss, "health", 0) <= 0 and not getattr(
                    boss, "_death_rewarded", False
                ):
                    boss._death_rewarded = True
                    # record as an enemy kill (increments meta XP by 1)
                    try:
                        g.record_enemy_kill()
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass
                    # also give the small boss XP bonus that the normal branch
                    # would have granted (10% of the base value); keep this
                    # wrapped in a try so we don't crash in odd test objects.
                    try:
                        boss_xp_map: Dict[str, int] = {
                            "medium": 80,
                            "big": 150,
                            "final": 400,
                        }
                        boss_base_xp: int = boss_xp_map.get(
                            boss.enemy_type.replace("boss_", ""), 100
                        )
                        g.award_meta_xp(int(boss_base_xp * 0.1))
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass
                    # Spawn health drop when boss dies
                    # Health drop spawning is handled by DeathSystem
                    # Don't remove boss_limbo_horde here — game.update()
                    # needs it in the group to detect death.
                    if getattr(boss, "enemy_type", "") != "boss_limbo_horde":
                        try:
                            boss.kill()
                        except (AttributeError, TypeError, ValueError, KeyError):
                            try:
                                if hasattr(g.bosses, "remove"):
                                    g.bosses.remove(boss)
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

        # Check for level up
        if g.player_xp >= g.xp_to_next_level:
            g.trigger_level_up()

    def apply_ice_puddle_slowing(self) -> None:
        """Apply ice puddle slowing effects to all enemies and bosses.

        Checks which enemies/bosses are within active ice puddle radii and applies
        the corresponding slow factor to their movement speed.
        """
        g = self.game
        for enemy in g.enemies:
            ex, ey = g._enemy_pos(enemy)
            in_puddle = False
            max_slow_factor = 1.0

            # combine ice and blizzard puddles for processing
            puddles = []
            puddles.extend(getattr(g, "ice_puddles", []) or [])
            puddles.extend(getattr(g, "blizzard_puddles", []) or [])
            # Check all active puddles
            for puddle in puddles:
                px, py = puddle["x"], puddle["y"]
                # compute effective radius for blizzard growth (with multiplier)
                if puddle.get("blizzard"):
                    try:
                        from src.game_constants import (
                            BLIZZARD_GROWTH_MULTIPLIER,
                            BLIZZARD_MAX_DURATION,
                        )
                    except (AttributeError, TypeError, ValueError, KeyError):
                        BLIZZARD_MAX_DURATION = 1
                        BLIZZARD_GROWTH_MULTIPLIER = 1.0
                    growth = 1 - (puddle.get("timer", 0) / BLIZZARD_MAX_DURATION)
                    growth *= BLIZZARD_GROWTH_MULTIPLIER
                    if growth > 1:
                        growth = 1
                    radius = puddle["radius"] * growth
                else:
                    radius = puddle["radius"]
                slow_factor = puddle["slow_factor"]

                dx = ex - px
                dy = ey - py
                dist_sq = dx * dx + dy * dy
                if dist_sq <= radius * radius:
                    in_puddle = True
                    max_slow_factor = min(max_slow_factor, slow_factor)

            # Apply or remove slowing effect
            if in_puddle:
                # Save original speed if not already saved
                if not hasattr(enemy, "original_speed"):
                    enemy.original_speed = getattr(enemy, "speed", 100)
                enemy.speed = enemy.original_speed * max_slow_factor
                enemy.slow_factor = max_slow_factor
            else:
                # Check if enemy has active slow from ice projectile impact (slow_timer-based)
                slow_timer = getattr(enemy, "slow_timer", 0)
                slow_factor_from_impact = getattr(enemy, "slow_factor", 1.0)

                if slow_timer > 0 and slow_factor_from_impact < 1.0:
                    # Preserve slow from direct projectile hit
                    if not hasattr(enemy, "original_speed"):
                        enemy.original_speed = getattr(enemy, "speed", 100)
                    enemy.speed = enemy.original_speed * slow_factor_from_impact
                else:
                    # Restore normal speed (no puddle, no active impact slow)
                    if hasattr(enemy, "original_speed"):
                        enemy.speed = getattr(enemy, "original_speed", enemy.speed)
                        try:
                            del enemy.original_speed
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                    enemy.slow_factor = 1.0

            # Check bosses too
            if hasattr(g, "bosses") and g.bosses:
                for boss in g.bosses:
                    if hasattr(boss, "x") and hasattr(boss, "y"):
                        bx, by = boss.x, boss.y
                        in_puddle = False
                        max_slow_factor = 1.0

                        # Check all active puddles
                        # include both types
                        puddles = []
                        puddles.extend(getattr(g, "ice_puddles", []) or [])
                        puddles.extend(getattr(g, "blizzard_puddles", []) or [])
                        for puddle in puddles:
                            px, py = puddle["x"], puddle["y"]
                            if puddle.get("blizzard"):
                                try:
                                    from src.game_constants import (
                                        BLIZZARD_GROWTH_MULTIPLIER,
                                        BLIZZARD_MAX_DURATION,
                                    )
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    BLIZZARD_MAX_DURATION = 1
                                    BLIZZARD_GROWTH_MULTIPLIER = 1.0
                                growth = 1 - (
                                    puddle.get("timer", 0) / BLIZZARD_MAX_DURATION
                                )
                                growth *= BLIZZARD_GROWTH_MULTIPLIER
                                if growth > 1:
                                    growth = 1
                                radius = puddle["radius"] * growth
                            else:
                                radius = puddle["radius"]
                            slow_factor = puddle["slow_factor"]

                            dx = bx - px
                            dy = by - py
                            dist_sq = dx * dx + dy * dy
                            if dist_sq <= radius * radius:
                                in_puddle = True
                                max_slow_factor = min(max_slow_factor, slow_factor)

                        # Apply or remove slowing effect
                        if in_puddle:
                            # Save original speed if not already saved
                            if not hasattr(boss, "original_speed"):
                                boss.original_speed = getattr(boss, "speed", 100)
                            boss.speed = boss.original_speed * max_slow_factor
                            boss.slow_factor = max_slow_factor
                        else:
                            # Check if boss has active slow from ice projectile impact (slow_timer-based)
                            slow_timer = getattr(boss, "slow_timer", 0)
                            slow_factor_from_impact = getattr(boss, "slow_factor", 1.0)

                            if slow_timer > 0 and slow_factor_from_impact < 1.0:
                                # Preserve slow from direct projectile hit
                                if not hasattr(boss, "original_speed"):
                                    boss.original_speed = getattr(boss, "speed", 100)
                                boss.speed = (
                                    boss.original_speed * slow_factor_from_impact
                                )
                            else:
                                # Restore normal speed (no puddle, no active impact slow)
                                if hasattr(boss, "original_speed"):
                                    boss.speed = getattr(
                                        boss, "original_speed", boss.speed
                                    )
                                    try:
                                        del boss.original_speed
                                    except (
                                        AttributeError,
                                        TypeError,
                                        ValueError,
                                        KeyError,
                                    ):
                                        pass
                                boss.slow_factor = 1.0
