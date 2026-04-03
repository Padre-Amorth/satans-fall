"""Tower special-ability system — energy, fire, blizzard, and Voltaic Mayhem state/logic."""

from __future__ import annotations

import logging
import math
import random
from typing import TYPE_CHECKING, Dict, List

from src.game_constants import HELL_STAGES, LIMBO_STAGES, PURGATORY_STAGES

if TYPE_CHECKING:
    from src.game import Game

LOG = logging.getLogger(__name__)


class TowerSpecialSystem:
    """Owns all special-ability state and implements fire / blizzard / Voltaic Mayhem logic.

    Designed as a Service-Locator system: receives and holds a reference to the
    Game instance so it can read enemies, game_state, permanent_stats, etc.
    without duplicating that data.

    Constructor signature:
        TowerSpecialSystem(game: Game) -> None

    All public methods mirror the existing Game methods they replace so that
    backward-compatible delegates are one-liners.
    """

    def __init__(self, game: "Game") -> None:
        self.game = game

        # --- Energy bar ---
        self.tower_energy: int = 0
        self.tower_energy_max: int = 100
        self.tower_energy_per_hit: int = 5

        # --- Fire special (fire tier-7) ---
        self.fire_special_charges: int = 0
        self.fire_special_timer: int = 0
        self.fire_special_index: int = 0
        self.pending_fire_clicks: List[dict] = []
        self.fire_smoke: List[dict] = []

        # --- Input state for beam ---
        self.right_mouse_held: bool = False

        # --- Voltaic Mayhem (storm tier-7) ---
        self.voltaic_active: bool = False
        self.voltaic_time_left: int = 0
        self.voltaic_x: float = 0.0
        self.voltaic_y: float = 0.0
        self._voltaic_accum: Dict[int, int] = {}

        # copy constants for convenience (mirrors what _init_game_state did)
        try:
            from src.game_constants import (
                VOLTAIC_MAYHEM_IMPACT_RADIUS,
                VOLTAIC_MAYHEM_MAX_DURATION,
                VOLTAIC_MAYHEM_SPEED,
                VOLTAIC_MAYHEM_VIOLET_CHANCE,
                VOLTAIC_MAYHEM_VIOLET_COLOR,
            )

            self.VOLTAIC_MAYHEM_MAX_DURATION = VOLTAIC_MAYHEM_MAX_DURATION
            self.VOLTAIC_MAYHEM_IMPACT_RADIUS = VOLTAIC_MAYHEM_IMPACT_RADIUS
            self.VOLTAIC_MAYHEM_SPEED = VOLTAIC_MAYHEM_SPEED
            # chance and colour for occasional violet beams
            self.VOLTAIC_MAYHEM_VIOLET_CHANCE = VOLTAIC_MAYHEM_VIOLET_CHANCE
            self.VOLTAIC_MAYHEM_VIOLET_COLOR = VOLTAIC_MAYHEM_VIOLET_COLOR
        except (ImportError, AttributeError, NameError):
            self.VOLTAIC_MAYHEM_MAX_DURATION = 0
            self.VOLTAIC_MAYHEM_IMPACT_RADIUS = 0
            self.VOLTAIC_MAYHEM_SPEED = 0
            self.VOLTAIC_MAYHEM_VIOLET_CHANCE = 0
            self.VOLTAIC_MAYHEM_VIOLET_COLOR = (150, 200, 255)

    def special_unlocked(self) -> bool:
        """Return True if any placed tower has its last‑skill slot active.

        The unlock is governed by permanent_stats like ``fire_7`` / ``storm_7`` /
        ``ice_7``.  If neither tower exists or the appropriate stat is zero, the
        special ability is considered unavailable.
        """
        # prologo never has towers/specials
        if getattr(self.game, "selected_stage", None) == "prologo":
            return False
        try:
            stats = getattr(self.game, "permanent_stats", {})
            for t in (
                getattr(self.game, "left_tower", None),
                getattr(self.game, "right_tower", None),
            ):
                if t is None:
                    continue
                tp = getattr(t, "tower_type", None)
                if not tp:
                    continue
                if stats.get(f"{tp}_7", 0):
                    return True
        except (AttributeError, KeyError, TypeError):
            pass
        return False

    def charge_tower_energy(self, amount: int | None = None) -> None:
        """Increase tower energy by *amount* (or ``tower_energy_per_hit``).

        Energy is clamped to ``tower_energy_max``.  ``amount`` may be negative to
        subtract energy.  Charging only occurs when the special is unlocked.
        """
        # guard against charging when unlock missing
        if not self.special_unlocked():
            return
        if amount is None:
            amount = self.tower_energy_per_hit
        try:
            cur = self.tower_energy
            mx = self.tower_energy_max
            new_val = cur + amount
            if mx is not None and mx >= 0:
                new_val = max(0, min(mx, new_val))
            self.tower_energy = new_val
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def is_tower_special_ready(self) -> bool:
        """Return True when the energy bar is full and the special is unlocked."""
        try:
            if not self.special_unlocked():
                return False
            return self.tower_energy >= self.tower_energy_max
        except (AttributeError, TypeError, ValueError, KeyError):
            return False

    def _dist_point_to_segment(
        self, px: float, py: float, x1: float, y1: float, x2: float, y2: float
    ) -> float:
        """Return shortest distance from point (px,py) to line segment (x1,y1)-(x2,y2)."""
        # based on projection formula
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)
        t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return math.hypot(px - proj_x, py - proj_y)

    def activate_tower_special(self) -> bool:
        """Attempt to consume the full energy bar.

        Clears ``tower_energy`` to zero if there was enough and returns True;
        otherwise does nothing and returns False.  Routes to appropriate special
        based on which tower types are actually placed.
        """
        if self.is_tower_special_ready():
            try:
                self.tower_energy = 0
            except (AttributeError, TypeError):
                pass

            # Collect tower types that are both placed AND have their special unlocked
            placed_types = set()
            for t in (
                getattr(self.game, "left_tower", None),
                getattr(self.game, "right_tower", None),
            ):
                if t is None:
                    continue
                tp = getattr(t, "tower_type", None)
                if tp and self.game.permanent_stats.get(f"{tp}_7", 0):
                    placed_types.add(tp)

            # Activate fire special first (if unlocked) since it's time-limited
            if "fire" in placed_types:
                try:
                    from src.game_constants import (
                        FIRE_SPECIAL_CHARGES,
                        FIRE_SPECIAL_DURATION,
                    )
                except (ImportError, ModuleNotFoundError):
                    FIRE_SPECIAL_CHARGES = 0
                    FIRE_SPECIAL_DURATION = 0
                # grant full charges and schedule the first explosion after the
                # configured click delay.  charges are still consumed immediately
                # so the window countdown starts with one shot already pending.
                self.fire_special_charges = FIRE_SPECIAL_CHARGES
                self.fire_special_timer = FIRE_SPECIAL_DURATION
                try:
                    from src.game_constants import FIRE_SPECIAL_CLICK_DELAY

                    delay = FIRE_SPECIAL_CLICK_DELAY
                except (ImportError, ModuleNotFoundError):
                    delay = 0
                try:
                    self.pending_fire_clicks.append(
                        {
                            "timer": delay,
                            "x": getattr(self.game, "mouse_x", 0),
                            "y": getattr(self.game, "mouse_y", 0),
                        }
                    )
                except (AttributeError, TypeError):
                    pass
                try:
                    self.fire_special_charges = max(0, self.fire_special_charges - 1)
                except (AttributeError, TypeError):
                    pass
            # Activate Blizzard if ice tower is placed with ice_7 unlocked
            if "ice" in placed_types:
                try:
                    from src.game_constants import (
                        BLIZZARD_MAX_DURATION,
                        BLIZZARD_RADIUS,
                        BLIZZARD_SLOW_FACTOR,
                    )
                except (AttributeError, TypeError, ValueError, KeyError):
                    BLIZZARD_RADIUS = 0
                    BLIZZARD_MAX_DURATION = 0
                    BLIZZARD_SLOW_FACTOR = 1.0
                if not hasattr(self.game, "blizzard_puddles"):
                    self.game.blizzard_puddles = []
                self.game.blizzard_puddles.append(
                    {
                        "x": getattr(self.game, "mouse_x", 0),
                        "y": getattr(self.game, "mouse_y", 0),
                        "radius": BLIZZARD_RADIUS,
                        "timer": BLIZZARD_MAX_DURATION,
                        # Blizzard puddles should behave like ice puddles with respect to
                        # slowing, so include a slow factor constant so the collision
                        # system doesn't blow up when iterating over them.
                        "slow_factor": BLIZZARD_SLOW_FACTOR,
                        "blizzard": True,
                    }
                )

            # Activate Voltaic Mayhem if storm tower is placed with storm_7 unlocked
            if "storm" in placed_types:
                # start the beam; it will run while right mouse held or until time runs out
                try:
                    LOG.info("voltaic branch activated")
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
                self.voltaic_active = True
                # initialize the movable endpoint at the current mouse position so
                # the beam doesn't jump from (0,0)
                self.voltaic_x = getattr(self.game, "mouse_x", 0)
                self.voltaic_y = getattr(self.game, "mouse_y", 0)
                # fall back to constant if attribute missing
                dur = getattr(self, "VOLTAIC_MAYHEM_MAX_DURATION", None)
                if dur is None:
                    try:
                        from src.game_constants import VOLTAIC_MAYHEM_MAX_DURATION

                        dur = VOLTAIC_MAYHEM_MAX_DURATION
                    except (AttributeError, TypeError, ValueError, KeyError):
                        dur = 0
                self.voltaic_time_left = dur

            return True
        return False

    def _spawn_fire_special(self, x: float, y: float) -> None:
        """Spawn one fire-special explosion at the given coordinates.

        Damages/ignites nearby targets and shows a cycling word.  The floating
        text should appear at the explosion itself regardless of whether any
        enemies are hit.  (Previous logic only spawned words when enemies were
        damaged, which made tests and the UI inconsistent.)
        """
        try:
            from src.game_constants import (
                FIRE_SPECIAL_DAMAGE,
                FIRE_SPECIAL_EXPLOSION_COLOR,
                FIRE_SPECIAL_RADIUS,
                FIRE_SPECIAL_WORDS,
            )
        except (AttributeError, TypeError, ValueError, KeyError):
            FIRE_SPECIAL_RADIUS = 0
            FIRE_SPECIAL_DAMAGE = 0
            FIRE_SPECIAL_WORDS = []
            FIRE_SPECIAL_EXPLOSION_COLOR = (200, 100, 40)

        # display word at explosion location first; this happens even if there
        # are no nearby enemies.  Use extended life so the word lingers at least
        # two seconds as requested by design.  add tiny random offset to avoid
        # duplicate-removal logic erasing earlier words.
        try:
            if FIRE_SPECIAL_WORDS:
                word = FIRE_SPECIAL_WORDS[
                    self.fire_special_index % len(FIRE_SPECIAL_WORDS)
                ]
            else:
                word = ""
            word = word.upper()
            ox = x + random.uniform(-3, 3)
            oy = y + random.uniform(-3, 3)
            # make the text noticeably larger and ensure it floats like damage
            self.game.spawn_floating_text(
                word,
                ox,
                oy,
                color=(150, 0, 0),
                outline_color=(0, 0, 0),
                life=getattr(
                    __import__(
                        "src.game_constants", fromlist=["FIRE_SPECIAL_TEXT_LIFE"]
                    ),
                    "FIRE_SPECIAL_TEXT_LIFE",
                    0,
                ),
                font_size=40,
                vy=-1.2,
            )
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        # normal enemies
        try:
            for enemy in (
                list(self.game.enemies) if getattr(self.game, "enemies", None) else []
            ):
                ex, ey = self.game._enemy_pos(enemy)
                dx = ex - x
                dy = ey - y
                if dx * dx + dy * dy <= FIRE_SPECIAL_RADIUS * FIRE_SPECIAL_RADIUS:
                    _etype = getattr(enemy, "enemy_type", "")
                    _shp = getattr(enemy, "shield_hp", 0)
                    _shield_active = _shp > 0 and _etype in (
                        "pentagram_fire",
                        "pentagram_storm",
                        "pentagram_ice",
                    )
                    try:
                        if (
                            _etype in ("pentagram_storm", "pentagram_ice")
                            and _shield_active
                        ):
                            pass  # fire special does not penetrate storm/ice elemental shields
                        elif _etype == "pentagram_fire" and _shield_active:
                            # fire special dissolves fire pentagram's shield
                            absorbed = min(_shp, FIRE_SPECIAL_DAMAGE)
                            enemy.shield_hp -= absorbed
                            remainder = FIRE_SPECIAL_DAMAGE - absorbed
                            if remainder > 0:
                                enemy.health = max(0, enemy.health - remainder)
                        else:
                            enemy.health = max(0, enemy.health - FIRE_SPECIAL_DAMAGE)
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass
                    try:
                        if not _shield_active and getattr(enemy, "burn_timer", 0) <= 0:
                            enemy.burn_timer = 120
                            enemy.burn_damage_per_second = 4.0
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        # bosses
        try:
            if hasattr(self.game, "bosses") and self.game.bosses:
                items = (
                    self.game.bosses.sprites()
                    if hasattr(self.game.bosses, "sprites")
                    else list(self.game.bosses)
                )
                for boss in items:
                    bx, by = self.game._enemy_pos(boss)
                    dx = bx - x
                    dy = by - y
                    if dx * dx + dy * dy <= FIRE_SPECIAL_RADIUS * FIRE_SPECIAL_RADIUS:
                        try:
                            boss.health = max(0, boss.health - FIRE_SPECIAL_DAMAGE)
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                        try:
                            if getattr(boss, "burn_timer", 0) <= 0:
                                boss.burn_timer = 120
                                boss.burn_damage_per_second = 4.0
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                        try:
                            word = (
                                FIRE_SPECIAL_WORDS[
                                    self.fire_special_index % len(FIRE_SPECIAL_WORDS)
                                ]
                                if FIRE_SPECIAL_WORDS
                                else ""
                            )
                            self.game.spawn_floating_text(
                                word,
                                bx,
                                by - self.game._enemy_radius(boss) - 8,
                                color=(150, 0, 0),
                                outline_color=(0, 0, 0),
                                life=getattr(
                                    __import__(
                                        "src.game_constants",
                                        fromlist=["FIRE_SPECIAL_TEXT_LIFE"],
                                    ),
                                    "FIRE_SPECIAL_TEXT_LIFE",
                                    0,
                                ),
                                font_size=40,
                                vy=-1.2,
                            )
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        # add visual effect entry (longer duration via constant)
        try:
            from src.game_constants import FIRE_SPECIAL_VISUAL_DURATION

            vis = FIRE_SPECIAL_VISUAL_DURATION
        except (AttributeError, TypeError, ValueError, KeyError):
            vis = 8
        try:
            # include color so downstream draw code can use a nicer default and
            # tests can inspect it directly
            self.game.game_state.fire_explosions.append(
                {
                    "x": x,
                    "y": y,
                    "radius": FIRE_SPECIAL_RADIUS,
                    "timer": vis,
                    "max_timer": vis,
                    "color": FIRE_SPECIAL_EXPLOSION_COLOR,
                }
            )
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        # emit some smoke particles around the explosion
        try:
            for i in range(random.randint(10, 14)):
                self.fire_smoke.append(
                    {
                        "x": x + random.uniform(-12, 12),
                        "y": y + random.uniform(-12, 12),
                        "life": random.randint(25, 45),
                        "size": random.uniform(4, 10),
                    }
                )
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        try:
            self.fire_special_index = (self.fire_special_index + 1) % (
                len(FIRE_SPECIAL_WORDS) or 1
            )
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def _update_fire_smoke(self) -> None:
        """Advance smoke particles emitted by fire special explosions."""
        if not getattr(self, "fire_smoke", None):
            return
        alive = []
        for p in list(self.fire_smoke):
            try:
                p["y"] -= 1.0  # drift upward faster
                p["life"] -= 1
                if p["life"] > 0:
                    alive.append(p)
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
        self.fire_smoke = alive

    def update_voltaic_mayhem(self) -> None:
        """Update state for the storm special (Voltaic Mayhem).

        Beams originate from each placed storm tower and stretch to the current
        mouse position.  They damage any enemy whose hitbox comes within a
        small radius of the line segment.  The ability is activated by a
        right-click and will remain active until the timer expires **or** the
        player clicks the right button again to cancel.  It no longer depends on
        the button being held down.
        """
        # If the special is not currently active we can clear any stored
        # accumulators and bail early.  This ensures lingering entries don't
        # persist between activations.
        if not getattr(self, "voltaic_active", False):
            self._voltaic_accum.clear()
            self._voltaic_frame_counter = 0
            return

        # frame counter for damage timing: deal 2 damage every 3 frames (40 DPS at 60 FPS)
        if not hasattr(self, "_voltaic_frame_counter"):
            self._voltaic_frame_counter = 0

        # decrement timer and disable when expired; deactivate when the
        # counter hits zero so that the effect ends immediately on the frame
        # it expires rather than waiting for the next update call.
        self.voltaic_time_left -= 1
        if self.voltaic_time_left <= 0:
            self.voltaic_active = False
            self._voltaic_accum.clear()
            return

        # compute desired endpoint (mouse) and move current endpoint toward it
        mx = getattr(self.game, "mouse_x", 0)
        my = getattr(self.game, "mouse_y", 0)
        # ensure we have endpoint coords in case activation failed to set them
        hx = getattr(self, "voltaic_x", mx)
        hy = getattr(self, "voltaic_y", my)
        # move endpoint toward mouse using configured speed (pixels/sec)
        try:
            speed = getattr(self, "VOLTAIC_MAYHEM_SPEED", 0) / float(self.game.fps or 1)
        except (AttributeError, TypeError, ValueError, KeyError):
            speed = 0
        # vector from current to target
        dx = mx - hx
        dy = my - hy
        dist = math.hypot(dx, dy)
        if dist <= speed or dist == 0:
            hx, hy = mx, my
        else:
            frac = speed / dist
            hx += dx * frac
            hy += dy * frac
        self.voltaic_x, self.voltaic_y = hx, hy

        # damage radius: use enemy radius plus small margin
        from src import game_constants

        for idx, tower in enumerate(
            (
                getattr(self.game, "left_tower", None),
                getattr(self.game, "right_tower", None),
            ),
        ):
            if tower is None or getattr(tower, "tower_type", None) != "storm":
                continue
            tx, ty = getattr(tower, "x", 0), getattr(tower, "y", 0)
            # apply same offset as statue projectiles so voltaic beams start
            # from the actual shot origin rather than the tower centre.  use the
            # shared helper from weapon_system so both systems stay in sync.
            try:
                from src.systems.weapon_system import statue_projectile_offsets

                stage_x, stage_y = statue_projectile_offsets(self.game)
            except (AttributeError, TypeError, ValueError, KeyError):
                # fallback to constants (shouldn't happen)
                stage = getattr(self.game, "selected_stage", "") or ""
                if stage in LIMBO_STAGES:
                    stage_x = game_constants.STATUE_PROJECTILE_OFFSET_X_LIMBO
                elif stage in PURGATORY_STAGES:
                    stage_x = game_constants.STATUE_PROJECTILE_OFFSET_X_PURGATORY
                elif stage in HELL_STAGES:
                    stage_x = game_constants.STATUE_PROJECTILE_OFFSET_X_HELL
                else:
                    stage_x = 0
                stage_y = game_constants.STATUE_PROJECTILE_OFFSET_Y
            # left tower shoots to right; right tower to left
            if idx == 0:  # left
                tx += stage_x
            else:
                tx -= stage_x
            ty += stage_y

            # visual feedback: append chain lightning effect from tower to current endpoint
            try:
                # beams occasionally get a more violetty hue for variety
                beam_effect: dict = {"points": [(tx, ty), (hx, hy)], "timer": 4}
                try:
                    import random

                    if random.random() < getattr(
                        self, "VOLTAIC_MAYHEM_VIOLET_CHANCE", 0
                    ):
                        beam_effect["color"] = getattr(
                            self, "VOLTAIC_MAYHEM_VIOLET_COLOR", (150, 200, 255)
                        )
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
                self.game.game_state.chain_lightning_effects.append(beam_effect)
                # impact circle at endpoint
                self.game.game_state.chain_lightning_effects.append(
                    {
                        "points": [(hx, hy)],
                        # explosion should linger a bit longer so player sees it
                        "timer": 16,
                        "explosion": True,
                        "radius": getattr(self, "VOLTAIC_MAYHEM_IMPACT_RADIUS", 50),
                        # brighter cyan for better contrast
                        "color": (150, 240, 255),
                    }
                )
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
            # damage regular enemies and any bosses along segment
            candidates = []
            try:
                candidates.extend(list(getattr(self.game, "enemies", [])))
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
            try:
                # bosses may be Group or list
                if hasattr(getattr(self.game, "bosses", None), "sprites"):
                    candidates.extend(self.game.bosses.sprites())
                elif getattr(self.game, "bosses", None) is not None:
                    candidates.extend(list(self.game.bosses))
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

            for enemy in candidates:
                try:
                    ex, ey = self.game._enemy_pos(enemy)
                except (AttributeError, TypeError, ValueError, KeyError):
                    continue
                er = self.game._enemy_radius(enemy)
                # calculate distance against the current beam endpoint
                dist = self._dist_point_to_segment(ex, ey, tx, ty, hx, hy)
                if dist <= er + 3:  # small tolerance
                    try:
                        # silent damage; we'll show aggregated text separately
                        _vetype = getattr(enemy, "enemy_type", "")
                        _vshield = getattr(enemy, "shield_hp", 0) > 0
                        _voltaic_blocked = _vshield and _vetype in (
                            "pentagram_fire",
                            "pentagram_ice",
                        )
                        if not _voltaic_blocked:
                            # deal 2 damage every 3 frames (40 DPS at 60 FPS)
                            if self._voltaic_frame_counter % 3 == 0:
                                enemy.take_damage(2, show_floating=False)
                            else:
                                enemy.take_damage(1, show_floating=False)
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass
                    # accumulate damage for throttled display
                    try:
                        eid = id(enemy)
                        # add 2 damage every 3 frames, 1 damage on other frames (40 DPS average)
                        damage_this_frame = 2 if self._voltaic_frame_counter % 3 == 0 else 1
                        total = self._voltaic_accum.get(eid, 0) + damage_this_frame
                        self._voltaic_accum[eid] = total
                        if total >= 30:
                            # show a bundled "30" above the enemy
                            try:
                                self.game.spawn_floating_text("30", ex, ey - 8)
                            except (AttributeError, TypeError, ValueError, KeyError):
                                pass
                            self._voltaic_accum[eid] = total - 30
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass
                    # drop the entry if the enemy died to avoid leaks
                    try:
                        if getattr(enemy, "health", 1) <= 0:
                            self._voltaic_accum.pop(eid, None)
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass

        # increment frame counter for damage timing
        self._voltaic_frame_counter += 1

    def use_fire_charge(self) -> bool:
        """Consume one fire-special charge if any remain in the active window.

        Returns True if a shot was queued, False otherwise.
        """
        if self.fire_special_charges <= 0 or self.fire_special_timer <= 0:
            return False
        try:
            from src.game_constants import FIRE_SPECIAL_CLICK_DELAY

            delay = FIRE_SPECIAL_CLICK_DELAY
        except (AttributeError, TypeError, ValueError, KeyError):
            delay = 0
        self.pending_fire_clicks.append(
            {
                "timer": delay,
                "x": getattr(self.game, "mouse_x", 0),
                "y": getattr(self.game, "mouse_y", 0),
            }
        )
        self.fire_special_charges = max(0, self.fire_special_charges - 1)
        return True

    def update(self) -> None:
        """Per-frame update: smoke, pending shots, fire timer, Voltaic Mayhem beam."""
        self._update_fire_smoke()

        # process delayed-fire shots
        if self.pending_fire_clicks:
            for p in list(self.pending_fire_clicks):
                try:
                    p["timer"] -= 1
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
                if p.get("timer", 0) <= 0:
                    try:
                        self._spawn_fire_special(p.get("x", 0), p.get("y", 0))
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass
                    try:
                        self.pending_fire_clicks.remove(p)
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass

        # handle fire-special timer; expire remaining charges after duration
        if self.fire_special_timer > 0:
            self.fire_special_timer -= 1
            if self.fire_special_timer <= 0:
                self.fire_special_charges = 0
                try:
                    self.fire_special_index = 0
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

        # update fire-explosion visuals
        if hasattr(self.game, "game_state"):
            new_fx = []
            for fx in getattr(self.game.game_state, "fire_explosions", []):
                if fx.get("timer", 0) > 0:
                    new_fx.append(fx)
            self.game.game_state.fire_explosions = new_fx
            for fx in self.game.game_state.fire_explosions:
                try:
                    fx["timer"] -= 1
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

        self.update_voltaic_mayhem()

    def reset(self) -> None:
        """Clear all run-specific special-ability state."""
        self.tower_energy = 0
        self.fire_special_charges = 0
        self.fire_special_timer = 0
        self.fire_special_index = 0
        self.pending_fire_clicks.clear()
        self.fire_smoke.clear()
        self.voltaic_active = False
        self.voltaic_time_left = 0
        self._voltaic_accum.clear()
