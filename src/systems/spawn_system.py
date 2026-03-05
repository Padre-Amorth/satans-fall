"""Spawn and wave management system."""

from __future__ import annotations

import logging
import math
import random
from typing import TYPE_CHECKING, Any, Dict, List

from src.balance import ENEMY_BASE_SPEEDS
from src.entities.enemy import Enemy
from src.game_constants import (
    LIMBO_FINAL_ACCEL_START_TIME,
    LIMBO_FINAL_HALT_BEFORE_BOSS,
    LIMBO_HORDE_TIME,
    LIMBO_HORDE_TIME_1,
    LIMBO_HORDE_TIME_2,
    LIMBO_HORDE_TIME_3,
    PURGATORY_HORDE_TIME_1,
    PURGATORY_HORDE_TIME_2,
    PURGATORY_HORDE_TIME_3,
)
from src.projectile import Projectile

if TYPE_CHECKING:
    from src.game import Game

logger = logging.getLogger(__name__)


class SpawnSystem:
    """Handles enemy spawning, wave progression, and prologo events."""

    def __init__(self, game: "Game") -> None:
        self.game = game
        # track rare crusader spawns per wave (starts at zero)
        self.crusader_spawned_this_wave: int = 0
        # track total spawns in this wave to force crusader after ~30 spawns
        self.spawns_since_last_crusader: int = 0
        # remember when the last "big" enemy (giant/custode) was created
        # so we can enforce a minimum 12‑second cooldown between spawns during
        # normal play.  Using ``game.time_elapsed`` makes it global across
        # waves; the value is reset to ``-inf`` so the first spawn is always
        # allowed.  The cooldown is waived when a limbo horde is active.
        self.last_giant_spawn_time: float = -float("inf")
        # One-time pentagram flag for the current run
        self.pentagram_spawned: bool = False

    def _can_spawn_giant(self) -> bool:
        """Return ``True`` if a giant (or similar big enemy) may spawn now.

        A 12‑second cooldown is enforced by comparing the current global
        ``game.time_elapsed`` to ``last_giant_spawn_time``.  During an active
        limbo horde or after horde completion, casual giant spawns are blocked.
        """
        # Block casual giant spawns during active horde (only script-controlled spawns allowed)
        if getattr(self.game, "limbo_horde_active", False):
            return False
        if getattr(self.game, "purgatory_horde_active", False):
            return False
        # Block giant spawns after horde completion (waiting for victory)
        if getattr(self.game, "limbo_horde_completed", False):
            return False
        if getattr(self.game, "purgatory_horde_completed", False):
            return False
        if getattr(self.game, "showing_victory", False):
            return False
        return (self.game.time_elapsed - self.last_giant_spawn_time) >= 12.0

    def update_enemy_spawning(self) -> None:
        """Handle enemy spawning logic (delegates timing to EnemyManager when present)."""
        if getattr(self.game, "debug", False):
            logger.debug(
                "[spawn_system] update_enemy_spawning called stage=%s",
                self.game.selected_stage,
            )
        # halt spawning just before the Limbo Final boss arrives (based on total time)
        if (
            self.game.selected_stage == "limbo_final"
            and self.game.time_elapsed >= 180.0 - LIMBO_FINAL_HALT_BEFORE_BOSS
        ):
            # do nothing; stop spawning entirely
            return

        # check for the regular limbo horde trigger (not final)
        if self.game.selected_stage in ("limbo", "limbo_2", "limbo_3") and not getattr(
            self.game, "limbo_horde_started", False
        ):
            # Determine horde spawn time based on stage
            horde_time_threshold = {
                "limbo": LIMBO_HORDE_TIME_1,
                "limbo_2": LIMBO_HORDE_TIME_2,
                "limbo_3": LIMBO_HORDE_TIME_3,
            }.get(self.game.selected_stage, LIMBO_HORDE_TIME)

            # add noisy logging only in debug mode (useful for ff scripts)
            if getattr(self.game, "debug", False):
                logger.debug(
                    "[horde-check] stage=%s time_elapsed=%.3f started=%s threshold=%.1f",
                    self.game.selected_stage,
                    self.game.time_elapsed,
                    getattr(self.game, "limbo_horde_started", False),
                    horde_time_threshold,
                )
            if self.game.time_elapsed >= horde_time_threshold:
                if getattr(self.game, "debug", False):
                    logger.debug(
                        "[spawn_system] triggering horde at time %s (stage %s)",
                        self.game.time_elapsed,
                        self.game.selected_stage,
                    )
                self._start_limbo_horde()

        # check for the purgatory horde trigger (no boss, no buff)
        if self.game.selected_stage in (
            "purgatory",
            "purgatory_2",
            "purgatory_3",
        ) and not getattr(self.game, "purgatory_horde_started", False):
            # Determine horde spawn time based on stage
            horde_time_threshold = {
                "purgatory": PURGATORY_HORDE_TIME_1,
                "purgatory_2": PURGATORY_HORDE_TIME_2,
                "purgatory_3": PURGATORY_HORDE_TIME_3,
            }.get(self.game.selected_stage, PURGATORY_HORDE_TIME_1)

            # add debug logging
            if getattr(self.game, "debug", False):
                logger.debug(
                    "[horde-check] stage=%s time_elapsed=%.3f started=%s threshold=%.1f",
                    self.game.selected_stage,
                    self.game.time_elapsed,
                    getattr(self.game, "purgatory_horde_started", False),
                    horde_time_threshold,
                )
            if self.game.time_elapsed >= horde_time_threshold:
                if getattr(self.game, "debug", False):
                    logger.debug(
                        "[spawn_system] triggering purgatory horde at time %s (stage %s)",
                        self.game.time_elapsed,
                        self.game.selected_stage,
                    )
                self._start_purgatory_horde()

        # Pentagram: spawn one-shot at t >= 60s
        if (
            not self.pentagram_spawned
            and getattr(self.game, "time_elapsed", 0.0) >= 60.0
            and not getattr(self.game, "limbo_horde_completed", False)
            and not getattr(self.game, "showing_victory", False)
            and not getattr(self.game, "showing_game_over", False)
        ):
            self._spawn_pentagram()

        # Use manager timers if manager exists
        # block any further spawning once the horde has been completed,
        # the limbo-final boss has been killed, or a victory/defeat overlay is showing
        if (
            getattr(self.game, "limbo_horde_completed", False)
            or getattr(self.game, "purgatory_horde_completed", False)
            or getattr(self.game, "showing_victory", False)
            or getattr(self.game, "limbo_final_victory_timer", 0) > 0
            or getattr(self.game, "purgatory_horde_victory_timer", 0) > 0
        ):
            return

        if self.game.enemy_manager is not None:
            # accelerate spawn pace after the accel-start time by
            # ticking the timer an extra frame each update
            self.game.enemy_manager.enemy_spawn_timer -= 1
            if (
                self.game.selected_stage == "limbo_final"
                and self.game.wave_time >= LIMBO_FINAL_ACCEL_START_TIME
            ):
                self.game.enemy_manager.enemy_spawn_timer -= 1

            # also handle limbo horde phased spawning if active
            if self.game.limbo_horde_active and self.game.limbo_horde_schedule:
                # increment elapsed frames
                self.game.limbo_horde_elapsed += 1
                # process any phases whose trigger time has arrived
                while (
                    self.game.limbo_horde_phase_index
                    < len(self.game.limbo_horde_schedule)
                    and self.game.limbo_horde_elapsed
                    >= self.game.limbo_horde_schedule[
                        self.game.limbo_horde_phase_index
                    ]["time"]
                ):
                    phase = self.game.limbo_horde_schedule[
                        self.game.limbo_horde_phase_index
                    ]
                    self._spawn_horde_batch(phase)
                    # scripted events may accompany phases
                    if phase.get("growth"):
                        self._trigger_satan_growth()
                    self.game.limbo_horde_phase_index += 1

            # also handle purgatory horde phased spawning if active
            if self.game.purgatory_horde_active and self.game.purgatory_horde_schedule:
                # increment elapsed frames
                self.game.purgatory_horde_elapsed += 1
                # process any phases whose trigger time has arrived
                while (
                    self.game.purgatory_horde_phase_index
                    < len(self.game.purgatory_horde_schedule)
                    and self.game.purgatory_horde_elapsed
                    >= self.game.purgatory_horde_schedule[
                        self.game.purgatory_horde_phase_index
                    ]["time"]
                ):
                    phase = self.game.purgatory_horde_schedule[
                        self.game.purgatory_horde_phase_index
                    ]
                    self._spawn_horde_batch(phase)
                    # no scripted events for purgatory (no growth buff)
                    self.game.purgatory_horde_phase_index += 1

            # During an active horde, normal wave spawning is suspended so
            # that the only arrivals come from our controlled timer.  The
            # wave will be finished artificially when the explosion triggers
            # so there's no need to ever resume this.
            if (
                not self.game.limbo_horde_active
                and not self.game.purgatory_horde_active
                and self.game.enemy_manager.enemy_spawn_timer <= 0
            ):
                self.spawn_enemy()
                # compute base next rate
                next_rate = self.game.enemy_manager.enemy_spawn_rate
                if self.game.selected_stage == "prologo":
                    next_rate = int(next_rate * 1.5)
                # apply extra acceleration in limbo_final after threshold
                if (
                    self.game.selected_stage == "limbo_final"
                    and self.game.wave_time >= LIMBO_FINAL_ACCEL_START_TIME
                ):
                    # subtract a little more each spawn (half‑frame per sec)
                    extra = int(
                        (self.game.wave_time - LIMBO_FINAL_ACCEL_START_TIME) * 0.5
                    )
                    next_rate = max(self.game.spawn_min_rate, next_rate - extra)
                self.game.enemy_manager.enemy_spawn_timer = next_rate
        else:
            self.game.enemy_spawn_timer -= 1
            if (
                self.game.selected_stage == "limbo_final"
                and self.game.wave_time >= LIMBO_FINAL_ACCEL_START_TIME
            ):
                self.game.enemy_spawn_timer -= 1

            # limbo horde handling without enemy_manager uses the same phased logic
            if self.game.limbo_horde_active and self.game.limbo_horde_schedule:
                self.game.limbo_horde_elapsed += 1
                while (
                    self.game.limbo_horde_phase_index
                    < len(self.game.limbo_horde_schedule)
                    and self.game.limbo_horde_elapsed
                    >= self.game.limbo_horde_schedule[
                        self.game.limbo_horde_phase_index
                    ]["time"]
                ):
                    phase = self.game.limbo_horde_schedule[
                        self.game.limbo_horde_phase_index
                    ]
                    self._spawn_horde_batch(phase)
                    if phase.get("growth"):
                        self._trigger_satan_growth()
                    self.game.limbo_horde_phase_index += 1

            # purgatory horde handling without enemy_manager
            if self.game.purgatory_horde_active and self.game.purgatory_horde_schedule:
                self.game.purgatory_horde_elapsed += 1
                while (
                    self.game.purgatory_horde_phase_index
                    < len(self.game.purgatory_horde_schedule)
                    and self.game.purgatory_horde_elapsed
                    >= self.game.purgatory_horde_schedule[
                        self.game.purgatory_horde_phase_index
                    ]["time"]
                ):
                    phase = self.game.purgatory_horde_schedule[
                        self.game.purgatory_horde_phase_index
                    ]
                    self._spawn_horde_batch(phase)
                    # no scripted events for purgatory
                    self.game.purgatory_horde_phase_index += 1

            if (
                not self.game.limbo_horde_active
                and not self.game.purgatory_horde_active
                and self.game.enemy_spawn_timer <= 0
            ):
                print("[DEBUG] normal wave spawn triggered (no manager)")
                self.spawn_enemy()
                next_rate = self.game.enemy_spawn_rate
                if self.game.selected_stage == "prologo":
                    next_rate = int(next_rate * 1.5)
                if (
                    self.game.selected_stage == "limbo_final"
                    and self.game.wave_time >= LIMBO_FINAL_ACCEL_START_TIME
                ):
                    extra = int(
                        (self.game.wave_time - LIMBO_FINAL_ACCEL_START_TIME) * 0.5
                    )
                    next_rate = max(self.game.spawn_min_rate, next_rate - extra)
                self.game.enemy_spawn_timer = next_rate

        # Periodic big enemy spawn (delegate to EnemyManager when present)
        # IMPORTANT: Don't spawn giants during victory screen OR horde completion
        if not (
            getattr(self.game, "limbo_horde_completed", False)
            or getattr(self.game, "showing_victory", False)
        ):
            if self.game.enemy_manager is not None:
                try:
                    self.game.enemy_manager.update_big_enemy_timer()
                except Exception:
                    # Fallback to legacy behavior
                    self.game.big_enemy_timer -= 1
                    if (
                        self.game.big_enemy_timer <= 0
                        and not self.game.big_spawned_this_wave
                    ):
                        self.spawn_big_enemy()
                        self.game.big_spawned_this_wave = True
                        if self.game.wave >= 6:
                            self.game.big_enemy_timer = (
                                self.game.big_enemy_fast_interval
                            )
                        else:
                            self.game.big_enemy_timer = 12 * self.game.fps

                # Also allow EnemyManager to occasionally spawn non-boss inquisitors in Purgatory
                try:
                    self.game.enemy_manager.update_inquisitor_spawns()
                except Exception:
                    pass
            else:
                self.game.big_enemy_timer -= 1
                if (
                    self.game.big_enemy_timer <= 0
                    and not self.game.big_spawned_this_wave
                ):
                    self.spawn_big_enemy()
                    self.game.big_spawned_this_wave = True
                    if self.game.wave >= 6:
                        self.game.big_enemy_timer = self.game.big_enemy_fast_interval
                    else:
                        self.game.big_enemy_timer = 12 * self.game.fps

        # handle satan growth animation if active
        # (buffs are applied instantly; we no longer change the player's size)
        if getattr(self.game, "satan_growth_active", False):
            self.game.satan_growth_elapsed += 1
            # apply a light screen shake each frame while the scripted event
            # remains active.  once the elapsed time exceeds the duration we
            # simply clear the flag; no scaling adjustments are performed.
            self.game.shake_timer = 1
            self.game.shake_intensity = 2
            duration = self.game.satan_growth_duration or (5 * self.game.fps)
            if self.game.satan_growth_elapsed >= duration:
                self.game.satan_growth_active = False

        # Spawn acceleration
        self.game.spawn_accel_timer -= 1
        if self.game.spawn_accel_timer <= 0:
            # Update both game and manager rates to keep them in sync
            new_rate = max(
                self.game.spawn_min_rate, int(self.game.enemy_spawn_rate * 0.99)
            )
            self.game.enemy_spawn_rate = new_rate
            if self.game.enemy_manager is not None:
                self.game.enemy_manager.enemy_spawn_rate = new_rate
            self.game.spawn_accel_timer = 20 * self.game.fps

    def update_wave_progression(self) -> None:
        """Handle wave progression and boss spawning"""
        # Block ALL wave progression once the limbo horde has been completed or
        # the victory screen is showing.  Without this, new waves keep starting
        # which spawn wave bosses and reset big_spawned_this_wave, allowing
        # giants to appear and preventing the "enemies empty" victory condition.
        if getattr(self.game, "limbo_horde_completed", False) or getattr(
            self.game, "showing_victory", False
        ):
            return

        # Wave progression based on elapsed seconds or on explicit frame boundary
        frames_per_wave = int(self.game.wave_duration * self.game.fps)
        frame_boundary_hit: bool = (
            frames_per_wave > 0
            and self.game.frame_count % frames_per_wave == 0
            and self.game.frame_count != 0
        )

        # If Limbo Final boss has already shown up, do not advance waves; the
        # encounter ends the stage and we shouldn't spawn further inquisitors or
        # increment the wave counter.
        if self.game.selected_stage == "limbo_final" and getattr(
            self.game.enemy_manager, "limbo_final_boss_spawned", False
        ):
            return

        if self.game.wave_time >= self.game.wave_duration or frame_boundary_hit:
            self.game.wave += 1
            self.game.wave_time = 0
            # Reset wave boss flag (proxy to manager when available)
            if self.game.enemy_manager is not None:
                try:
                    self.game.enemy_manager.wave_boss_spawned = False
                except Exception:
                    self.game.wave_boss_spawned = False
            else:
                self.game.wave_boss_spawned = False

            # reset crusader counter and spawn tracking for new wave
            self.crusader_spawned_this_wave = 0
            self.spawns_since_last_crusader = 0

            # Reset prologo final boss flags if any (proxy to manager when available)
            # Skip reset for prologo to prevent multiple spawns
            if self.game.selected_stage != "prologo":
                if self.game.enemy_manager is not None:
                    try:
                        self.game.enemy_manager.prologo_final_boss_spawned = False
                        self.game.enemy_manager.prologo_final_boss_defeated = False
                        self.game.enemy_manager.prologo_final_boss_immortal = False
                        self.game.enemy_manager.prologo_lightning_timer = 0
                        self.game.enemy_manager.prologo_lightning_strike = False
                    except Exception:
                        self.game.prologo_final_boss_spawned = False
                        self.game.prologo_final_boss_defeated = False
                        self.game.prologo_final_boss_immortal = False
                        self.game.prologo_lightning_timer = 0
                        self.game.prologo_lightning_strike = False
                else:
                    self.game.prologo_final_boss_spawned = False
                    self.game.prologo_final_boss_defeated = False
                    self.game.prologo_final_boss_immortal = False
                    self.game.prologo_lightning_timer = 0
                    self.game.prologo_lightning_strike = False
            # if the limbo horde has already completed (explosion happened),
            # clear the started/active flags so subsequent wave increments don't
            # mistakenly think the event is still pending. this avoids reset
            # immediately after the event fires while the wave_time bump from
            # trigger_limbo_horde_explosion may roll the wave counter.
            try:
                if getattr(self.game, "limbo_horde_completed", False):
                    self.game.limbo_horde_started = False
                    self.game.limbo_horde_active = False
                    # Reset giant spawn cooldown when horde ends so the 12-second rule applies again
                    self.last_giant_spawn_time = self.game.time_elapsed
            except Exception:
                pass
            # Keep big spawn flag in manager if available
            if self.game.enemy_manager is not None:
                try:
                    self.game.enemy_manager.big_spawned_this_wave = False
                except Exception:
                    self.game.big_spawned_this_wave = False
            else:
                self.game.big_spawned_this_wave = False

            # Adjust spawn rate based on wave
            if self.game.wave < self.game.spawn_ramp_start_wave:
                rate = max(
                    self.game.spawn_min_rate,
                    int(
                        self.game.base_spawn_rate
                        - self.game.wave * self.game.spawn_ramp_slope_pre
                    ),
                )
            else:
                rate = max(
                    self.game.spawn_min_rate,
                    int(
                        self.game.base_spawn_rate
                        - self.game.wave * self.game.spawn_ramp_slope_post
                    ),
                )
            # apply limbo penalty
            if getattr(self.game, "selected_stage", None) in (
                "limbo",
                "limbo_2",
                "limbo_3",
            ):
                from src.balance import LIMBO_SPAWN_RATE_PENALTY

                rate += LIMBO_SPAWN_RATE_PENALTY
            self.game.enemy_spawn_rate = rate
            if self.game.enemy_manager is not None:
                self.game.enemy_manager.enemy_spawn_rate = rate

            # difficulty grows linearly each wave (defined in balance)
            per_wave = self.game.get_difficulty_multiplier_per_wave()
            self.game.difficulty_multiplier = 1.0 + (self.game.wave * per_wave)

        # Spawn boss at 38 seconds (delegate to manager when available).
        # During the special limbo horde event we control every spawn via the
        # schedule and only the horde logic should produce bosses.  The regular
        # wave boss would otherwise trigger independently (usually at the 38s
        # mark) which results in two big bosses appearing in quick succession –
        # one from the horde and one from the wave timer.  To avoid that we
        # suppress normal wave-boss logic while the horde is active on the
        # three limbo stages.
        suppress_wave_boss = self.game.selected_stage in (
            "limbo",
            "limbo_2",
            "limbo_3",
        ) and getattr(self.game, "limbo_horde_active", False)

        if not suppress_wave_boss:
            if self.game.enemy_manager is not None:
                try:
                    self.game.enemy_manager.update_wave_boss(self.game.wave_time)
                except Exception:
                    # Fallback to legacy behavior
                    if not self.game.wave_boss_spawned and self.game.wave_time >= 38:
                        if not (
                            self.game.selected_stage == "prologo"
                            and self.game.prologo_final_boss_spawned
                        ):
                            # new rule: limbo stages never get the "big" wave boss
                            if getattr(self.game, "is_limbo_stage", lambda: False)():
                                self.spawn_boss("inquisitor")
                            elif self.game.wave % 3 == 0 and self.game.wave > 0:
                                self.spawn_boss("big")
                            else:
                                self.spawn_boss("mid")
                        self.game.wave_boss_spawned = True
            else:
                if not self.game.wave_boss_spawned and self.game.wave_time >= 38:
                    if not (
                        self.game.selected_stage == "prologo"
                        and self.game.prologo_final_boss_spawned
                    ):
                        if getattr(self.game, "is_limbo_stage", lambda: False)():
                            self.spawn_boss("inquisitor")
                        elif self.game.wave % 3 == 0 and self.game.wave > 0:
                            self.spawn_boss("big")
                        else:
                            self.spawn_boss("mid")
                    self.game.wave_boss_spawned = True

        # Ensure giant spawns at 12 seconds if not already spawned.
        # however, limbo variants should not produce giants until the player has
        # been in the stage for at least 30 seconds (global time_elapsed).
        # additionally we enforce the 12‑second cooldown even for this
        # periodic call; if the cooldown prevents a spawn we simply leave
        # ``big_spawned_this_wave`` false so the check can try again later.
        # ALSO: don't spawn during victory screen or horde completion
        if self.game.wave_time >= 12:
            if not (
                self.game.selected_stage in ("limbo", "limbo_2", "limbo_3")
                and getattr(self.game, "time_elapsed", 0.0) < 30.0
            ):
                if not (
                    getattr(self.game, "limbo_horde_completed", False)
                    or getattr(self.game, "showing_victory", False)
                ):
                    if self.game.enemy_manager is not None:
                        if (
                            not self.game.enemy_manager.big_spawned_this_wave
                            and self._can_spawn_giant()
                        ):
                            self.spawn_big_enemy()
                            self.game.enemy_manager.big_spawned_this_wave = True
                    else:
                        if not self.game.big_spawned_this_wave:
                            self.spawn_big_enemy()
                            self.game.big_spawned_this_wave = True

        # Ensure wave boss spawning is handled by manager when available
        if self.game.enemy_manager is not None:
            # manager.update_wave_boss already called earlier; nothing else required here
            pass

    def update_prologo_events(self) -> None:
        """Handle special Prologo events (managed by EnemyManager when present)"""
        if self.game.enemy_manager is not None:
            try:
                self.game.enemy_manager.update_prologo_events()
                return
            except Exception:
                # Fallback to legacy behavior below
                pass

        # Final boss at 3:55 (235 seconds) - delegate to manager when available
        if self.game.enemy_manager is not None:
            try:
                self.game.enemy_manager.update_prologo_events()
            except Exception:
                # fallback to legacy behavior
                if (
                    self.game.selected_stage == "prologo"
                    and not self.game.prologo_final_boss_spawned
                    and self.game.time_elapsed >= 235
                ):
                    logger.info(
                        "[PROLOGO] Spawning final boss at time %s",
                        self.game.time_elapsed,
                    )
                    self.spawn_boss("final")
                    self.game.prologo_final_boss_spawned = True
                # also handle limbo_final in legacy fallback
                if (
                    self.game.selected_stage == "limbo_final"
                    and not getattr(self.game, "limbo_final_boss_spawned", False)
                    and self.game.time_elapsed >= 180
                ):
                    logger.info(
                        "[LIMBO_FINAL] spawning limbo boss at time %s",
                        self.game.time_elapsed,
                    )
                    self.spawn_boss("limbo")
                    try:
                        self.game.limbo_final_boss_spawned = True
                    except Exception:
                        setattr(self.game, "limbo_final_boss_spawned", True)
        else:
            if (
                self.game.selected_stage == "prologo"
                and not self.game.prologo_final_boss_spawned
                and self.game.time_elapsed >= 235
            ):
                logger.info(
                    "[PROLOGO] Spawning final boss at time %s", self.game.time_elapsed
                )
                self.spawn_boss("final")
                self.game.prologo_final_boss_spawned = True
                if (
                    self.game.selected_stage == "limbo_final"
                    and not getattr(self.game, "limbo_final_boss_spawned", False)
                    and self.game.time_elapsed >= 180
                ):
                    logger.info(
                        "[LIMBO_FINAL] spawning limbo boss at time %s",
                        self.game.time_elapsed,
                    )
                    self.spawn_boss("limbo")
                    try:
                        self.game.limbo_final_boss_spawned = True
                    except Exception:
                        setattr(self.game, "limbo_final_boss_spawned", True)

        # Lightning strike when immortal boss reaches full health
        if self.game.selected_stage == "prologo" and self.game.prologo_lightning_strike:
            self.game.prologo_lightning_timer += 1
            if (
                self.game.prologo_lightning_timer
                >= self.game.prologo_lightning_duration_frames
            ):
                self.game.prologo_defeat()

        # Boss regeneration when immortal
        for boss in self.game.bosses:
            if (
                boss.enemy_type == "boss_final"
                and self.game.prologo_final_boss_immortal
                and boss.health < boss.max_health
            ):
                boss.health = min(boss.health + 3.0, boss.max_health)
                if (
                    boss.health >= boss.max_health
                    and not self.game.prologo_lightning_strike
                ):
                    logger.info(
                        "[PROLOGO] Final boss reached full health — triggering lightning strike"
                    )
                    self.game.prologo_lightning_strike = True
                    self.generate_lightning()
                    logger.debug(
                        "[PROLOGO] Lightning points generated: %s",
                        (
                            len(self.game.lightning_points)
                            if hasattr(self.game, "lightning_points")
                            else None
                        ),
                    )
                    self.game.player.health = 0

    def generate_lightning(self) -> None:
        """Generate lightning bolt path"""
        try:
            # Use player's current x as bolt origin, ensure numeric
            bolt_x = int(getattr(self.game.player, "x", self.game.width // 2))
            player_y = int(getattr(self.game.player, "y", self.game.height))
            segments = 10
            pts = []
            pts.append((bolt_x, 0))
            prev_x: int = bolt_x

            for i in range(segments):
                next_y = int((i + 1) * (player_y / segments))
                # Random step but clamp to screen bounds
                next_x = int(prev_x + random.randint(-25, 25))
                next_x = max(0, min(self.game.width, next_x))
                next_y = max(0, min(self.game.height, next_y))
                pts.append((next_x, next_y))
                prev_x = next_x

            pts.append((bolt_x, player_y))
            # Final assign
            self.game.lightning_points = pts
        except Exception as e:
            logger.exception("Exception while generating lightning: %s", e)
            import traceback

            traceback.print_exc()
            self.game.lightning_points = []

    def _start_limbo_horde(self) -> None:
        """Begin the limbo horde event as a series of timed bursts.

        The horde now arrives in five high‑level phases:
          * 10 enemies immediately
          * 15 more after 5 seconds
          * 15 more after another 5 seconds (10s total)
          * 30 more after an additional 8 seconds (18s total)
          * final 30 enemies beginning much earlier (roughly 10‑12s); this
            portion is broken into random sub‑bursts spread over a 5–7‑second
            window.  The timing distribution is deterministic for test
            reproducibility.  Only the very last sub‑burst includes a single
            big boss, and every sub‑burst skews heavily toward giants/
            inquisitors.

        Previously the behaviour used a fixed-rate spawn over 10 seconds.
        """
        self.game.limbo_horde_started = True
        self.game.limbo_horde_active = True
        # boss has not appeared yet
        try:
            self.game.limbo_horde_boss_spawned = False
        except Exception:
            pass
        # build schedule: times are offsets from the moment the horde starts
        f = self.game.fps
        # fixed phases as per design; mark the fourth phase with a growth
        # script trigger so we can buff the player afterwards.
        # base phases remain unchanged
        schedule = [
            {"time": 0, "count": 10},
            {"time": 5 * f, "count": 15},
            {"time": 10 * f, "count": 15},
        ]
        # revised fourth phase broken into four small bursts. first burst
        # triggers the growth event. composition remains heavy on giants,
        # shielded and light on inquisitors.
        heavy_composition = {
            "special": True,
            "giant_ratio": 0.6,
            "shielded_ratio": 0.3,
            "inquisitor_ratio": 0.1,
        }
        schedule.extend(
            [
                {"time": 20 * f, "count": 5, "growth": True, **heavy_composition},
                {"time": 25 * f, "count": 5, **heavy_composition},
                {"time": 28 * f, "count": 5, **heavy_composition},
                {"time": 33 * f, "count": 5, **heavy_composition},
            ]
        )
        # special 5th phase entries with explicit composition
        schedule.append(
            {
                "time": 38 * f,
                "count": 8,
                "special": True,
                "custom": {"shielded": 5, "normal": 3},
            }
        )
        schedule.append(
            {
                "time": 48 * f,
                "count": 10,  # 9 regular + 1 boss
                "special": True,
                "custom": {"giant": 3, "shielded": 3, "normal": 3},
                "boss_count": 1,
            }
        )
        # compute total including any bosses; the original implementation
        # forgot to count ``boss_count`` entries, which meant the event could
        # prematurely mark itself complete before the final boss ever spawned.
        total = 0
        for entry in schedule:
            total += entry.get("count", 0) + entry.get("boss_count", 0)
        self.game.limbo_horde_schedule = schedule
        self.game.limbo_horde_initial = total
        self.game.limbo_horde_killed = 0
        self.game.limbo_horde_remaining = total
        self.game.limbo_horde_phase_index = 0
        self.game.limbo_horde_timer = 0
        self.game.limbo_horde_elapsed = 0
        # broadcast warning
        try:
            self.game.show_centered_message("HORDE SWARMS!", 2000, (255, 100, 0))
        except Exception:
            pass

    def _trigger_satan_growth(self) -> None:
        """Activate the scripted player buff after the fourth horde phase.

        The player receives permanent stat buffs: max health is doubled and
        fire rate is increased by 50%.  A brief screen shake plays while the
        scripted event is active.  The size no longer changes during this
        sequence.  This method can be called multiple times but only the first
        invocation has effect.
        """
        if getattr(self.game, "satan_growth_active", False):
            return
        # mark state
        self.game.satan_growth_active = True
        self.game.satan_growth_elapsed = 0
        self.game.satan_growth_duration = 5 * self.game.fps
        # apply buffs immediately (health double, fire rate +50%)
        try:
            self.game.player.max_health *= 2
            self.game.player.health *= 2
            self.game.player.fire_rate_multiplier *= 1.5
        except Exception:
            pass
        # remember that the aura should now persist until the stage ends
        try:
            self.game.satan_growth_persistent = True
        except Exception:
            pass

    def _start_purgatory_horde(self) -> None:
        """Begin the purgatory horde event as a series of timed bursts.

        Similar to limbo horde but without a final boss and without player buff.
        The horde arrives in six phases with 100 total enemies (no boss):
          * 10 enemies immediately
          * 15 more after 5 seconds
          * 15 more after another 5 seconds (10s total)
          * 20 more in four 5-enemy bursts from 20-33 seconds (heavy composition)
          * 13 shielded/normal after 38 seconds
          * 10 enemies at 48 seconds, then final 17 at 55 seconds (7s later).
            These final two phases are heavy on giants/shielded.
        """
        self.game.purgatory_horde_started = True
        self.game.purgatory_horde_active = True
        # build schedule: times are offsets from the moment the horde starts
        f = self.game.fps
        # base phases remain unchanged
        schedule = [
            {"time": 0, "count": 10},
            {"time": 5 * f, "count": 15},
            {"time": 10 * f, "count": 15},
        ]
        # revised fourth phase broken into four small bursts with heavy composition
        heavy_composition = {
            "special": True,
            "giant_ratio": 0.6,
            "shielded_ratio": 0.3,
            "inquisitor_ratio": 0.1,
        }
        schedule.extend(
            [
                {"time": 20 * f, "count": 5, **heavy_composition},
                {"time": 25 * f, "count": 5, **heavy_composition},
                {"time": 28 * f, "count": 5, **heavy_composition},
                {"time": 33 * f, "count": 5, **heavy_composition},
            ]
        )
        # special 5th phase entries with explicit composition (no boss)
        # 5a - shielded focus (add 2 crusaders at midpoint)
        schedule.append(
            {
                "time": 38 * f,
                "count": 13,
                "special": True,
                "custom": {"shielded": 8, "normal": 3, "crusader": 2},
            }
        )
        # 5b - first assault with archers
        schedule.append(
            {
                "time": 48 * f,
                "count": 12,
                "special": True,
                "custom": {"giant": 3, "shielded": 3, "archer": 2, "normal": 4},
            }
        )
        # 5c - final assault (7 seconds later, add 2 crusaders at end)
        schedule.append(
            {
                "time": 55 * f,
                "count": 15,
                "special": True,
                "custom": {"giant": 5, "shielded": 3, "normal": 5, "crusader": 2},
            }
        )
        # compute total (no bosses in purgatory horde)
        total = 0
        for entry in schedule:
            total += entry.get("count", 0)
        self.game.purgatory_horde_schedule = schedule
        self.game.purgatory_horde_initial = total
        self.game.purgatory_horde_killed = 0
        self.game.purgatory_horde_remaining = total
        self.game.purgatory_horde_phase_index = 0
        self.game.purgatory_horde_timer = 0
        self.game.purgatory_horde_elapsed = 0
        # broadcast warning
        try:
            self.game.show_centered_message("HORDE APPROACHES!", 2000, (180, 120, 200))
        except Exception:
            pass

    def spawn_enemy(self, forced_type: str | None = None) -> None:
        # Spawn from top of screen (pick X uniformly between the walls)
        x = self.game.random_x_between_walls()
        # apply a small random horizontal jitter so consecutive spawns don't
        # land perfectly on top of each other; this is especially helpful
        # during the scripted horde where many enemies of the same type
        # spawn in quick succession. clamp back into the wall boundaries.
        try:
            jitter = random.randint(-20, 20)
            x = self.game.clamp_to_walls(x + jitter)
        except Exception:
            pass
        # also give a little vertical offset to avoid perfect stacking when
        # multiple creatures spawn in the same frame; keep them just off-screen
        y = -20
        try:
            y += random.randint(0, 5)
        except Exception:
            pass

        # if caller specified a forced type we bypass the random selection logic
        health: float = 0.0
        if forced_type is not None:
            enemy_type = forced_type
            if enemy_type == "giant":
                # base giant health reduced to 120 (previously 160)
                health = 120 * self.game.difficulty_multiplier
                speed = ENEMY_BASE_SPEEDS.get("giant", 45)
                # record spawn time so even forced giants (e.g. during horde)
                # influence the cooldown window afterwards
                try:
                    self.last_giant_spawn_time = self.game.time_elapsed
                except Exception:
                    pass
            elif enemy_type == "crusader":
                health = 200 * self.game.difficulty_multiplier
                speed = ENEMY_BASE_SPEEDS.get("crusader", 30)
                stage = getattr(self.game, "selected_stage", "") or ""
                if stage.startswith("purgatory") or stage.startswith("hell"):
                    self.crusader_spawned_this_wave += 1
            elif enemy_type == "inquisitor":
                # inquisitor is just a normal enemy with a special appearance
                enemy_type = "normal"
                health = 50 * self.game.difficulty_multiplier
                speed = ENEMY_BASE_SPEEDS.get("normal", 75)
            elif enemy_type == "shielded":
                # treat as a normal enemy but with shielded type
                health = 50 * self.game.difficulty_multiplier
                speed = ENEMY_BASE_SPEEDS.get("normal", 75)
            elif enemy_type == "winged":
                # fast flying zig-zag enemy
                health = 30 * self.game.difficulty_multiplier
                speed = ENEMY_BASE_SPEEDS.get("winged", 120)
            elif enemy_type == "archer":
                # slow archer unit
                # start with normal enemy HP; the Enemy ctor will double it
                health = 50 * self.game.difficulty_multiplier
                speed = ENEMY_BASE_SPEEDS.get("archer", 40)
            else:
                # fallback to default normal values
                health = 50 * self.game.difficulty_multiplier
                speed = ENEMY_BASE_SPEEDS.get("normal", 75)
        else:
            # Choose enemy type based on wave and random chance
            rand: float = random.random()
            # Choose health and speed based on type
            # Determine rare spawn chances (crusader is rarer than a giant)
            crusader_chance = 0.015  # 1.5% base chance
            # Determine giant spawn chance, with limbo-specific rules
            giant_chance = 0.05
            if self.game.selected_stage in ("limbo", "limbo_2", "limbo_3"):
                # no crusaders in limbo
                crusader_chance = 0.0
                # no giants in the first 30 seconds of limbo
                if getattr(self.game, "time_elapsed", 0.0) < 30.0:
                    giant_chance = 0.0
                else:
                    # after 30s, giants are rarer than usual
                    giant_chance = 0.025
            # check crusader first since its probability is included within giant
            # rolls; we want a tiny chance of a crusader even when a giant might
            # have spawned.
            # Determine whether stage allows crusaders (purgatory onward)
            stage = getattr(self.game, "selected_stage", "") or ""
            # allow any stage string containing purgatory or hell (covers
            # numbered variants like "purgatory1"/"purgatory_1" used in debug
            # runs).  limbo stages must not spawn crusaders.
            allowed = "purgatory" in stage or "hell" in stage

            # Track spawns to force crusader after ~30 spawns if quota not met
            # This ensures at least 2 crusaders per wave in purgatory/hell
            force_crusader = (
                self.spawns_since_last_crusader >= 30
                and allowed
                and self.game.wave > 1
                and self.crusader_spawned_this_wave < 2
            )
            self.spawns_since_last_crusader += 1

            # no crusaders allowed in wave 1
            if (
                (rand < crusader_chance or force_crusader)
                and allowed
                and self.game.wave > 1
                and self.crusader_spawned_this_wave < 5
            ):
                enemy_type = "crusader"
                health = 200 * self.game.difficulty_multiplier
                speed = ENEMY_BASE_SPEEDS.get("crusader", 30)
                # NOTE: counter increment is delayed until after successful spawn
            # prefer giant only if the cooldown allows it (or we're in a
            # limbo horde).  falling into the other branches when the timer
            # blocks gives the normal/strong/etc. behaviour, which is what we
            # want when giants are temporarily prohibited.
            elif rand < giant_chance and self._can_spawn_giant():
                enemy_type = "giant"
                health = 120 * self.game.difficulty_multiplier  # reduced from 160
                # Base non-boss giant speed (from balance)
                speed = ENEMY_BASE_SPEEDS.get("giant", 45)
                # record spawn time so subsequent rolls honor the cooldown
                try:
                    self.last_giant_spawn_time = self.game.time_elapsed
                except Exception:
                    pass
            else:
                # compute dynamic spawn probabilities that shift with wave count:
                wave = getattr(self.game, "wave", 0)
                # base values
                base_strong = 0.10 if wave < 3 else 0.15
                base_normal = 0.30
                base_angel = 0.20
                base_winged = 0.10 if wave >= 3 else 0.0
                # adjustments per wave
                strong_chance = max(
                    base_strong - wave * 0.005, 0.05
                )  # more rare over time
                normal_chance = min(
                    base_normal + wave * 0.005, 0.50
                )  # increases with wave
                angel_chance = max(
                    base_angel - wave * 0.005, 0.05
                )  # decreases with wave
                winged_chance = base_winged
                if wave >= 3:
                    winged_chance = min(base_winged + (wave - 2) * 0.01, 0.30)
                # archer chance is always half of normal chance, but only from wave 3 onward in prologo
                stage = getattr(self.game, "selected_stage", "") or ""
                if stage == "prologo" and wave < 3:
                    archer_chance = 0.0
                else:
                    archer_chance = normal_chance * 0.5
                # ensure total doesn't exceed 1.0 by scaling if necessary
                total = (
                    strong_chance
                    + normal_chance
                    + angel_chance
                    + winged_chance
                    + archer_chance
                )
                if total > 1.0:
                    factor = 1.0 / total
                    strong_chance *= factor
                    normal_chance *= factor
                    angel_chance *= factor
                    winged_chance *= factor
                    archer_chance *= factor
                # now pick based on cumulative thresholds
                cumulative = strong_chance
                if rand < cumulative:
                    enemy_type = "strong"
                    health = 70 * self.game.difficulty_multiplier
                    speed = ENEMY_BASE_SPEEDS.get("strong", 60)
                else:
                    cumulative += normal_chance
                    if rand < cumulative:
                        enemy_type = "normal"
                        health = 50 * self.game.difficulty_multiplier  # Doubled from 25
                        speed = ENEMY_BASE_SPEEDS.get("normal", 75)
                    else:
                        cumulative += angel_chance
                        if rand < cumulative:
                            enemy_type = "angel"
                            health = (
                                40 * self.game.difficulty_multiplier
                            )  # Doubled from 20
                            speed = ENEMY_BASE_SPEEDS.get("angel", 60)
                        else:
                            cumulative += winged_chance
                            if rand < cumulative:
                                enemy_type = "winged"
                                health = 30 * self.game.difficulty_multiplier
                                speed = ENEMY_BASE_SPEEDS.get("winged", 120)
                            else:
                                cumulative += archer_chance
                                if rand < cumulative:
                                    enemy_type = "archer"
                                    # start with normal health; constructor will double it
                                    health = 50 * self.game.difficulty_multiplier
                                    speed = ENEMY_BASE_SPEEDS.get("archer", 40)
                                else:
                                    enemy_type = "weak"
                                    # base HP increased from 30 → 45 as per tuning request
                                    health = 45 * self.game.difficulty_multiplier
                                    speed = ENEMY_BASE_SPEEDS.get("weak", 35)

        # mage override: only after purgatory starts and once timer expires (~15s)
        if (getattr(self.game, "selected_stage", None) or "").startswith(
            ("purgatory", "hell")
        ):
            if not hasattr(self.game, "mage_last_spawn_frame"):
                # just initialize; no chance to convert on this spawn
                self.game.mage_last_spawn_frame = getattr(self.game, "frame_count", 0)
            else:
                elapsed = (
                    getattr(self.game, "frame_count", 0)
                    - self.game.mage_last_spawn_frame
                )
                if elapsed >= getattr(self.game, "fps", 60) * 15:
                    # don't allow more than two mage enemies at once
                    mage_count = 0
                    for e in getattr(self.game, "enemies", []):
                        if getattr(e, "enemy_type", None) == "mage":
                            mage_count += 1
                    if mage_count < 2:
                        try:
                            if random.random() < 0.5:
                                enemy_type = "mage"
                                health = 60 * self.game.difficulty_multiplier
                                speed = ENEMY_BASE_SPEEDS.get("mage", 50)
                                # only reset timer when a mage actually spawned
                                self.game.mage_last_spawn_frame = getattr(
                                    self.game, "frame_count", 0
                                )
                        except Exception:
                            pass
                    else:
                        # if already two mages, do nothing; wait until one is gone
                        pass

        # Check archer count limit (max 2 at once)
        if enemy_type == "archer":
            archer_count = 0
            for e in getattr(self.game, "enemies", []):
                if getattr(e, "enemy_type", None) == "archer":
                    archer_count += 1
            if archer_count >= 2:
                # already 2 archers, convert to normal enemy instead
                enemy_type = "normal"
                health = 50 * self.game.difficulty_multiplier
                speed = ENEMY_BASE_SPEEDS.get("normal", 75)

        # convert some strong enemies into shielded variants for non-prologo stages
        if enemy_type == "strong" and (
            getattr(self.game, "selected_stage", None) or ""
        ) not in ("", "prologo"):
            # probability of turning into shielded grows with wave number
            # start at roughly 50% and approach 90% over time
            try:
                wave = getattr(self.game, "wave", 0)
                shield_prob = min(0.50 + wave * 0.02, 0.90)
                if random.random() < shield_prob:
                    enemy_type = "shielded"
            except Exception:
                pass
        # Use EnemyManager when available (global slowdown handled there)
        enemy_created_successfully = False
        if self.game.enemy_manager is not None:
            try:
                enemy = self.game.enemy_manager.spawn(x, y, enemy_type, health, speed)
                enemy_created_successfully = True
            except Exception:
                enemy = Enemy(x, y, enemy_type, health, speed)
                if hasattr(self.game.enemies, "add"):
                    self.game.enemies.add(enemy)
                else:
                    self.game.enemies.append(enemy)
                enemy_created_successfully = True
        else:
            enemy = Enemy(x, y, enemy_type, health, speed)
            if hasattr(self.game.enemies, "add"):
                self.game.enemies.add(enemy)
            else:
                self.game.enemies.append(enemy)
            enemy_created_successfully = True

        # if caller provided additional appearance override (e.g. inquisitor)
        if forced_type == "inquisitor":
            try:
                enemy.appearance = "inquisitor"
            except Exception:
                pass

        # Increment crusader counter AFTER successful spawn
        if (
            enemy_created_successfully
            and enemy_type == "crusader"
            and forced_type is None
        ):
            # This was a randomly selected or forced crusader during normal wave
            self.crusader_spawned_this_wave += 1
            self.spawns_since_last_crusader = 0

    def _spawn_horde_batch(self, phase: dict) -> None:
        """Internal helper invoked when a horde phase is reached.

        ``phase`` contains at least ``time`` and ``count``; if ``special`` is
        True the remaining enemies should skew toward giants/inquisitors and
        conclude with three big bosses.
        """
        count = phase.get("count", 0)
        if not phase.get("special", False):
            for _ in range(count):
                self.spawn_enemy()
        else:
            # custom composition entries take precedence
            if phase.get("custom"):
                custom = phase["custom"]
                for etype, num in custom.items():
                    for _ in range(num):
                        if etype == "giant":
                            self.spawn_enemy(forced_type="giant")
                        elif etype == "shielded":
                            self.spawn_enemy(forced_type="shielded")
                        elif etype == "inquisitor":
                            self.spawn_enemy(forced_type="inquisitor")
                        elif etype == "crusader":
                            self.spawn_enemy(forced_type="crusader")
                        elif etype == "archer":
                            self.spawn_enemy(forced_type="archer")
                        else:
                            # treat remaining as normal
                            self.spawn_enemy()
                # spawn any bosses specified separately.  we mirror the logic
                # used in the non-custom path so that limbo stages get the
                # specialised boss type instead of the generic wave boss.
                stage = getattr(self.game, "selected_stage", "") or ""
                for _ in range(phase.get("boss_count", 0)):
                    try:
                        if stage.startswith("limbo"):
                            self.game.spawn_boss("limbo_horde")
                            try:
                                self.game.limbo_horde_boss_spawned = True
                            except Exception:
                                pass
                        else:
                            self.game.spawn_boss("big")
                    except Exception:
                        print("[DEBUG] boss spawn failed, fallback giant")
                        self.spawn_enemy(forced_type="giant")
                return
            # Determine how many bosses this phase should include; default 0
            boss_count = phase.get("boss_count", 0)
            normal_count = max(0, count - boss_count)
            # composition ratios may be overridden per phase; fall back to
            # original 70/30 giant/inquisitor split when unspecified.
            giant_ratio = phase.get("giant_ratio", 0.7)
            shielded_ratio = phase.get("shielded_ratio", 0.0)
            _inquisitor_ratio = phase.get(
                "inquisitor_ratio", max(0.0, 1.0 - giant_ratio - shielded_ratio)
            )
            # compute actual counts; ensure sum equals normal_count by rolling
            # any rounding remainder into giants.
            giant_count = int(normal_count * giant_ratio)
            shielded_count = int(normal_count * shielded_ratio)
            inquisitor_count = normal_count - giant_count - shielded_count
            # spawn giants first
            for _ in range(giant_count):
                self.spawn_enemy(forced_type="giant")
            # spawn shielded variants next
            for _ in range(shielded_count):
                # force a shielded spawn; spawn_enemy handles this type
                self.spawn_enemy(forced_type="shielded")
            # then inquisitors
            for _ in range(inquisitor_count):
                self.spawn_enemy(forced_type="inquisitor")
            # finally, add the configured number of big bosses (or a
            # specialised Limbo boss during the limbo horde).  The default
            # behaviour used to spawn ``boss_big`` here which meant the horde
            # shared the same entity and asset as the ordinary wave boss.  To
            # satisfy the requirement of a separate, importable sprite we
            # switch to ``boss_limbo`` in limbo stages so the horde finale can
            # have its own distinct appearance and logic.
            stage = getattr(self.game, "selected_stage", "") or ""
            for _ in range(boss_count):
                try:
                    if stage.startswith("limbo"):
                        # spawn a specialised horde boss type so it can have a
                        # unique asset separate from the final-stage boss.
                        self.game.spawn_boss("limbo_horde")
                        try:
                            self.game.limbo_horde_boss_spawned = True
                        except Exception:
                            pass
                    else:
                        self.game.spawn_boss("big")
                except Exception:
                    print("[DEBUG] boss spawn failed, fallback giant")
                    self.spawn_enemy(forced_type="giant")

    def spawn_enemy_projectiles(self) -> None:
        """Have some enemies shoot projectiles at the player"""
        # Only some enemies shoot (angels, inquisitor-normal, and bosses)
        shooting_enemies = []
        for enemy in self.game.enemies:
            if enemy.enemy_type in ["angel"] or (
                enemy.enemy_type == "normal"
                and getattr(enemy, "appearance", None) == "inquisitor"
            ):
                shooting_enemies.append(enemy)
        for boss in self.game.bosses:
            if boss.enemy_type in [
                "boss_medium",
                "boss_big",
                "boss_final",
                "boss_inquisitor",
                "boss_limbo",
                "boss_limbo_horde",
            ]:
                shooting_enemies.append(boss)

        # Limit to 2-3 shooters at a time
        shooting_enemies = shooting_enemies[:3]

        for enemy in shooting_enemies:
            # Calculate direction to player
            dx = self.game.player.x - enemy.x
            dy = self.game.player.y - enemy.y
            distance: float = math.sqrt(dx * dx + dy * dy)

            if distance > 0:
                # Normalize direction
                dx /= distance
                dy /= distance

                # Create projectile
                speed = 200
                projectile: Projectile = Projectile(
                    enemy.x,
                    enemy.y,
                    dx * speed,
                    dy * speed,
                    damage=8,
                    radius=4,
                    is_enemy_projectile=True,
                )
                self.game.enemy_projectiles.add(projectile)

    def spawn_giant_enemy(self) -> None:
        """Spawn a giant enemy at random edge (delegates to EnemyManager)."""
        if self.game.enemy_manager is not None:
            try:
                self.game.enemy_manager.spawn_giant_enemy()
                return
            except Exception:
                pass

        # Fallback to original behavior
        side: str = random.choice(["left", "right", "top"])

        if side == "left":
            x = -30
            y = random.randint(0, self.game.height)
        elif side == "right":
            x = self.game.width + 30
            y = random.randint(0, self.game.height)
        else:  # top
            x = self.game.random_x_between_walls()
            y = -30

        # Choose type based on current stage: Hell replaces giants with custodes
        stage = getattr(self.game, "selected_stage", "") or ""
        if stage.startswith("hell"):
            enemy_type = "custode"
        else:
            enemy_type = "giant"
        health: float = 100 * self.game.difficulty_multiplier
        # Base non-boss giant (and custode) speed (from balance)
        speed = ENEMY_BASE_SPEEDS.get("giant", 45)
        enemy: Enemy = Enemy(x, y, enemy_type, health, speed)
        if hasattr(self.game.enemies, "add"):
            self.game.enemies.add(enemy)
        else:
            self.game.enemies.append(enemy)

    def spawn_crusader_enemy(self) -> None:
        """Spawn a crusader enemy at random edge (delegates to EnemyManager).

        This is a very rare, tanky variant of the giant.
        """
        if self.game.enemy_manager is not None:
            try:
                self.game.enemy_manager.spawn_crusader_enemy()
                return
            except Exception:
                pass

        # Fallback behaviour mirrors spawn_giant_enemy but always uses crusader type
        side: str = random.choice(["left", "right", "top"])

        if side == "left":
            x = -30
            y = random.randint(0, self.game.height)
        elif side == "right":
            x = self.game.width + 30
            y = random.randint(0, self.game.height)
        else:  # top
            x = self.game.random_x_between_walls()
            y = -30

        enemy_type = "crusader"
        health: float = 200 * self.game.difficulty_multiplier
        speed = ENEMY_BASE_SPEEDS.get("crusader", 30)
        # count explicit spawns toward the wave cap if stage allows
        stage = getattr(self.game, "selected_stage", "") or ""
        if (
            stage.startswith("purgatory")
            or stage.startswith("hell")
            or stage.startswith("limbo")
        ):
            self.crusader_spawned_this_wave += 1
        enemy: Enemy = Enemy(x, y, enemy_type, health, speed)
        if hasattr(self.game.enemies, "add"):
            self.game.enemies.add(enemy)
        else:
            self.game.enemies.append(enemy)

    def spawn_big_enemy(self) -> None:
        """Spawn a big enemy (giant or custode).

        Delegates to ``EnemyManager`` when present.  The 12‑second giant
        cooldown is also respected here; callers that rely on the automatic
        wave‑time guarantee should continue to work, because the calling code
        checks ``_can_spawn_giant`` before invoking this method.  This method
        still updates ``last_giant_spawn_time`` if a creature is actually
        created so that other spawn paths remain aware of the timing.
        """
        if self.game.enemy_manager is not None:
            try:
                self.game.enemy_manager.spawn_giant_enemy()
                return
            except Exception:
                pass

        # bail out if the cooldown currently forbids another big spawn
        if not self._can_spawn_giant():
            return

        x = self.game.random_x_between_walls()
        y = -30

        # choose type based on stage like spawn_giant_enemy
        stage = getattr(self.game, "selected_stage", "") or ""
        if stage.startswith("hell"):
            enemy_type = "custode"
        else:
            enemy_type = "giant"
        health: float = 100 * self.game.difficulty_multiplier
        # Base non-boss giant/custode speed (spawn fallback)
        speed = ENEMY_BASE_SPEEDS.get("giant", 45)
        enemy: Enemy = Enemy(x, y, enemy_type, health, speed)
        if hasattr(self.game.enemies, "add"):
            self.game.enemies.add(enemy)
        else:
            self.game.enemies.append(enemy)
        # record spawn time so further attempts respect the cooldown
        try:
            self.last_giant_spawn_time = self.game.time_elapsed
        except Exception:
            pass

    def _spawn_pentagram(self) -> None:
        """Spawn the one-time pentagram tank enemy that traverses the stage horizontally."""
        self.pentagram_spawned = True
        # Choose entry side randomly
        direction: int = random.choice([-1, 1])
        half_w = 40  # half of final width (70 + 10 from global growth) / 2
        if direction == 1:
            # Enter from left, move right
            x = float(-half_w - 10)
        else:
            # Enter from right, move left
            x = float(self.game.width + half_w + 10)
        # Random vertical spawn position: 100px higher than mid-screen, still randomized
        y = float(random.randint(100, 400))
        # Pentagram: 500 base health (will get 1500 shield added in __init__)
        health = 500.0 * getattr(self.game, "difficulty_multiplier", 1.0)
        speed = ENEMY_BASE_SPEEDS.get("pentagram", 50.0)
        # Create the pentagram enemy
        enemy = Enemy(x, y, "pentagram", health, speed)
        # Override direction after construction for correct visuals/movement
        enemy.direction = direction
        # Add to game's enemy group
        if hasattr(self.game.enemies, "add"):
            self.game.enemies.add(enemy)
        else:
            self.game.enemies.append(enemy)

    def spawn_reinforcements(self, x=None, y=None, count=None):
        """Spawn a short-lived cluster of reinforcements near (x,y) or at a random building.
        If x,y are None the spawn will originate from a random building at the top.
        `count` overrides the default reinforcement_count."""
        try:
            if x is None or y is None:
                if self.game.buildings:  # If there are buildings (prologo)
                    building: Dict[str, Any] = random.choice(self.game.buildings)
                    x = building["x"] + random.randint(-20, 20)
                    # Clamp building-based spawn inside walls
                    x = self.game.clamp_to_walls(x)
                    y = building["y"]
                else:  # No buildings (limbo), spawn at random top position
                    x = self.game.random_x_between_walls(margin=100)
                    y = 50
            if count is None:
                count: int = self.game.reinforcement_count

            # If this is an "extra" reinforcement (e.g., mid-boss doubled call), reduce enemies by 1/3
            # to make the extra wave smaller and less overwhelming. This is a silent adjustment.
            if count > self.game.reinforcement_count:
                count: int = max(1, int(round(count * 2.0 / 3.0)))

            # Choose types biased to normal/angel
            # include mage with a modest weight so reinforcements can sometimes
            # bring a support caster, but only once we've unlocked purgatory+.
            if (getattr(self.game, "selected_stage", None) or "").startswith(
                ("purgatory", "hell")
            ):
                if getattr(self.game, "wave", 0) >= 3:
                    weights: List[float] = [
                        0.20,  # weak
                        0.30,  # normal
                        0.15,  # strong
                        0.20,  # angel
                        0.10,  # winged
                        0.05,  # mage
                    ]
                    types = ["weak", "normal", "strong", "angel", "winged", "mage"]
                else:
                    # early waves: no winged, keep heavy normal/weak
                    weights = [0.25, 0.35, 0.20, 0.25, 0.05]
                    types = ["weak", "normal", "strong", "angel", "mage"]
            else:
                if getattr(self.game, "wave", 0) >= 3:
                    weights = [0.25, 0.35, 0.20, 0.25, 0.10]
                    types = ["weak", "normal", "strong", "angel", "winged"]
                else:
                    weights = [0.3, 0.4, 0.2, 0.3]
                    types = ["weak", "normal", "strong", "angel"]
            for i in range(count):
                etype: str = random.choices(types, weights=weights)[0]

                # Scatter reinforced enemies in a broader area to avoid clustering
                angle: float = random.uniform(0, 2 * math.pi)
                r: int = random.randint(40, 160)
                rx = int(x + math.cos(angle) * r)
                ry = int(y + math.sin(angle) * r)

                # Clamp positions into the playable area
                rx: int = max(30, min(self.game.width - 30, rx))
                # Also clamp to walls so reinforcements don't appear outside bounds
                rx = self.game.clamp_to_walls(rx)
                # Keep regular enemies generally in the upper area when spawning from top
                if etype != "angel":
                    ry: int = max(40, min(self.game.height - 120, ry))
                else:
                    # Angels always spawn from the top band
                    rx: int = max(50, min(self.game.width - 50, rx))
                    ry = 50

                if etype == "weak":
                    enemy_type = "weak"
                    health = int(15 * self.game.difficulty_multiplier * 1.1)
                    speed = ENEMY_BASE_SPEEDS.get("weak", 35)
                elif etype == "normal":
                    enemy_type = "normal"
                    health = int(25 * self.game.difficulty_multiplier * 1.1)
                    speed = ENEMY_BASE_SPEEDS.get("normal", 75)
                elif etype == "strong":
                    enemy_type = "strong"
                    health = int(45 * self.game.difficulty_multiplier * 1.1)
                    speed = ENEMY_BASE_SPEEDS.get("strong", 60)
                elif etype == "mage":
                    enemy_type = "mage"
                    health = int(60 * self.game.difficulty_multiplier * 1.1)
                    speed = ENEMY_BASE_SPEEDS.get("mage", 50)
                else:  # angel
                    enemy_type = "angel"
                    health = int(30 * self.game.difficulty_multiplier * 1.1)
                    speed = ENEMY_BASE_SPEEDS.get("angel", 60)

                enemy: Enemy = Enemy(rx, ry, enemy_type, health, speed)
                self.game.enemies.add(enemy)
        except Exception as e:
            logger.exception("Error spawning reinforcements: %s", e)
            import traceback

            traceback.print_exc()

    def spawn_boss(self, boss_type) -> None:
        """Spawn a boss of the specified type (delegates to EnemyManager).

        The ``EnemyManager`` knows how to handle an expanded set of types
        (``"limbo"`` in particular for the unique Limbo horde boss), so the
        system simply forwards the call whenever an enemy manager is present.
        If no manager exists we fall back on the legacy behaviour and only
        support a small subset of types.  ``boss_type == "limbo"`` is treated
        analogously to ``"big"`` but uses the special ``boss_limbo`` enemy
        class so that it can carry its own sprite/behaviour independently of
        the standard wave boss.
        """
        if self.game.enemy_manager is not None:
            try:
                self.game.enemy_manager.spawn_boss(boss_type)
                return
            except Exception:
                pass

        # Legacy fallback – only a limited set of types was ever supported
        # here.  ``limbo`` used to spawn the final Limbo boss, so we leave it
        # alone; the horde-specific variant is called ``limbo_horde`` and maps
        # to a distinct enemy type so that an independent asset may be used.
        x: int = self.game.width // 2
        y = -50

        # Decide health and speed per boss type
        health: float = 0.0
        if boss_type == "final":
            enemy_type = "boss_final"
            health = 1000 * self.game.difficulty_multiplier
            speed = ENEMY_BASE_SPEEDS.get("boss_final", 40)
        elif boss_type == "big":
            enemy_type = "boss_big"
            health = 600 * self.game.difficulty_multiplier
            speed = ENEMY_BASE_SPEEDS.get("boss_big", 40)
        elif boss_type == "inquisitor":
            # explicit support so legacy path can spawn inquisitor bosses too
            enemy_type = "boss_inquisitor"
            health = 950 * self.game.difficulty_multiplier
            speed = ENEMY_BASE_SPEEDS.get("boss_inquisitor", 40)
        elif boss_type == "limbo":
            # Final Limbo boss (standard encounter)
            enemy_type = "boss_limbo"
            health = 800 * self.game.difficulty_multiplier
            speed = ENEMY_BASE_SPEEDS.get("boss_limbo", 40)
        elif boss_type == "limbo_horde":
            # Horde-ending boss uses its own type/asset
            enemy_type = "boss_limbo_horde"
            health = 500 * self.game.difficulty_multiplier
            speed = ENEMY_BASE_SPEEDS.get("boss_limbo_horde", 40)
        else:  # mid
            enemy_type = "boss_medium"
            health = 300 * self.game.difficulty_multiplier
            speed = ENEMY_BASE_SPEEDS.get("boss_medium", 45)

        boss: Enemy = Enemy(x, y, enemy_type, health, speed)
        self.game.bosses.add(boss)
