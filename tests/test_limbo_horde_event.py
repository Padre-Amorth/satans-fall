#!/usr/bin/env python3
"""Tests for the Limbo horde event at 8 minutes.

The scenario is triggered on the three "regular" limbo stages (limbo, limbo_2,
limbo_3).  Once time_elapsed reaches the threshold the game spawns a large batch
of enemies and begins tracking a special horde.  The level should not end until
the player has slain every enemy in the horde; previously the run would finish
with a scripted explosion once half the horde was dead.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pygame
import pytest

from src.game import Game
from src.game_constants import LIMBO_HORDE_TIME


@pytest.mark.parametrize("stage", ["limbo", "limbo_2", "limbo_3"])
def test_limbo_horde_triggers_and_completes(stage):
    g = Game()
    # ensure the game is running and stage is initialized
    g.reset_game()
    g.select_stage(stage)

    # fast-forward to the horde threshold and run until all phases have fired
    g.time_elapsed = LIMBO_HORDE_TIME
    # trigger spawn system to build schedule
    g.spawn_system.update_enemy_spawning()
    # once started the schedule should match our expected offsets and counts
    f = g.fps
    # schedule should reflect the revised phase structure described in
    # documentation: three initial bursts followed by four smaller waves,
    # then two final bursts including a boss in the last one.
    base_expected = [
        {"time": 0, "count": 10},
        {"time": 5 * f, "count": 15},
        {"time": 10 * f, "count": 15},
        {"time": 20 * f, "count": 5, "growth": True},
        {"time": 25 * f, "count": 5},
        {"time": 28 * f, "count": 5},
        {"time": 33 * f, "count": 5},
        {"time": 38 * f, "count": 8},
        {"time": 48 * f, "count": 10, "boss_count": 1},
    ]
    # only compare the core fields; additional tuning keys may be present
    actual_trimmed = []
    for entry in g.limbo_horde_schedule:
        trimmed = {
            k: entry[k] for k in entry if k in ("time", "count", "growth", "boss_count")
        }
        actual_trimmed.append(trimmed)
    assert actual_trimmed == base_expected
    # verify the aggregate size recorded by the game matches the sum of counts
    initial_total = sum(e["count"] for e in base_expected)
    assert g.limbo_horde_initial == initial_total
    # remaining may have decreased by whatever spawned on the first update call
    # so we don't assert exact equality here

    # tick through entire schedule to accumulate horde enemies
    # we run long enough to cover the last burst at 40s
    for _ in range(int(g.fps * 55)):
        g.spawn_system.update_enemy_spawning()
    assert g.limbo_horde_started
    assert g.limbo_horde_active
    initial = g.limbo_horde_initial
    assert initial == 78, f"horde size should now be 78, got {initial}"

    # the final burst should have produced the Limbo‑horde boss entity
    bosses = [b for b in getattr(g, "bosses", [])]
    assert bosses, "No bosses spawned during the horde completion"
    assert any(
        b.enemy_type == "boss_limbo_horde" for b in bosses
    ), "Expected a boss_limbo_horde to spawn during final horde burst"

    # now re-create the game state and run through the schedule again so we
    # can verify the intermediate enemy counts without the earlier 78 sprites
    # cluttering the group.
    g = Game()
    g.reset_game()
    g.select_stage(stage)
    g.time_elapsed = LIMBO_HORDE_TIME
    g.spawn_system.update_enemy_spawning()
    assert len(g.enemies) == 10
    for _ in range(int(g.fps * 5)):
        g.spawn_system.update_enemy_spawning()
    assert len(g.enemies) == 25
    for _ in range(int(g.fps * 5)):
        g.spawn_system.update_enemy_spawning()
    assert len(g.enemies) == 40
    # advance to the 20‑second burst (adds 5)
    for _ in range(int(g.fps * 10)):
        g.spawn_system.update_enemy_spawning()
    assert 44 <= len(g.enemies) <= 47, f"expected ~45 enemies, got {len(g.enemies)}"
    # 25s burst
    for _ in range(int(g.fps * 5)):
        g.spawn_system.update_enemy_spawning()
    assert 49 <= len(g.enemies) <= 52
    # 28s burst
    for _ in range(int(g.fps * 3)):
        g.spawn_system.update_enemy_spawning()
    assert 54 <= len(g.enemies) <= 57
    # 33s burst
    for _ in range(int(g.fps * 5)):
        g.spawn_system.update_enemy_spawning()
    assert 59 <= len(g.enemies) <= 62
    # 38s special composition: expect 8 total
    for _ in range(int(g.fps * 5)):
        g.spawn_system.update_enemy_spawning()
    assert (
        67 <= len(g.enemies) <= 69
    ), f"expected ~68 enemies after 38s, got {len(g.enemies)}"
    # 48s final burst
    for _ in range(int(g.fps * 10)):
        g.spawn_system.update_enemy_spawning()
    assert (
        77 <= len(g.enemies) <= 79
    ), f"expected ~78 enemies after 48s, got {len(g.enemies)}"
    # step through until horde exhausted
    while g.limbo_horde_remaining > 0:
        g.spawn_system.update_enemy_spawning()
    all_ids = {id(e) for e in g.enemies}
    all_ids |= {id(b) for b in getattr(g, "bosses", [])}
    total_spawned = len(all_ids)
    # allow a few deviations around the new total of 78
    assert (
        75 <= total_spawned <= 82
    ), f"expected ~78 total creatures, got {total_spawned}"


@pytest.mark.parametrize("stage", ["limbo", "limbo_2", "limbo_3"])
def test_no_wave_boss_during_limbo_horde(stage):
    """Wave boss logic must be suppressed once a regular limbo horde is active.

    Without this guard the timer-based wave boss will fire around the 38s
    mark while the horde schedule also emits its own boss.  Players would
    therefore see two big bosses during the horde endpoint, which is not
    intended.  We simulate the condition by keeping ``wave_time`` at or above
    the threshold while advancing the horde; only a single boss should appear.
    """
    pygame.init()
    g = Game(debug=True)
    g.select_stage(stage)
    # trigger the horde schedule
    g.time_elapsed = LIMBO_HORDE_TIME
    g.spawn_system.update_enemy_spawning()

    # make sure wave boss could spawn if unchecked
    g.wave_time = 38.0
    g.wave_boss_spawned = False

    # record existing boss IDs so we can identify the one spawned during the
    # horde; there should normally be none, but this keeps the assertion
    # precise even if some other code added a boss prematurely.
    before_ids = {id(b) for b in getattr(g, "bosses", [])}

    # step through enough frames to reach the final horde burst (45s)
    boss_before = len(getattr(g, "bosses", []))
    for _ in range(int(g.fps * 50)):
        # update wave progression each frame so the normal boss-check runs
        g.update_wave_progression()
        g.spawn_system.update_enemy_spawning()
    boss_after = len(getattr(g, "bosses", []))

    # should only have gained a single boss from the horde schedule
    assert boss_after - boss_before == 1, "Only one boss should spawn during the horde"
    # and the wave boss flag should remain false
    assert not g.wave_boss_spawned

    # determine exactly which boss objects are new
    new_bosses = [b for b in getattr(g, "bosses", []) if id(b) not in before_ids]
    assert len(new_bosses) == 1, "Expected exactly one new boss object"
    boss = new_bosses[0]
    assert (
        boss.enemy_type == "boss_limbo_horde"
    ), f"Limbo horde should produce a boss_limbo_horde, got {boss.enemy_type}"
    # ensure we didn't accidentally spawn any boss_big at all
    assert not any(
        b.enemy_type == "boss_big" for b in getattr(g, "bosses", [])
    ), "No boss_big should ever appear during the Limbo horde"


def test_periodic_giant_from_wave_time():
    """The automatic giant spawn at 12s should also be blocked for the first
    30s of Limbo stages.  After 30s it may fire once per wave as normal.
    """
    g = Game()
    g.reset_game()
    g.select_stage("limbo")
    g.wave = 1
    # simulate time less than 30s but wave_time past 12s
    g.time_elapsed = 20.0
    g.wave_time = 15.0
    # ensure no giants yet
    g.update_wave_progression()
    assert not any(getattr(e, "enemy_type", None) == "giant" for e in g.enemies)
    # now advance global time past 30 and try again
    g.enemies = type(g.enemies)()
    g.time_elapsed = 31.0
    g.wave_time = 20.0
    g.big_spawned_this_wave = False
    try:
        g.enemy_manager.big_spawned_this_wave = False
    except Exception:
        pass
    g.update_wave_progression()
    assert any(
        getattr(e, "enemy_type", None) == "giant" for e in g.enemies
    ), "Giant should spawn after 30s when wave_time>=12"


def test_random_giant_spawn_cooldown():
    """Randomly chosen giants should respect a 12‑second cooldown outside
    of limbo hordes.  Early returns should convert into other enemy types.
    """
    import random

    g = Game()
    g.reset_game()
    g.select_stage("purgatory")
    g.wave = 1

    original_random = random.random
    try:
        # always return a value that would normally produce a giant
        random.random = lambda: 0.01

        # first attempt should succeed
        g.time_elapsed = 0.0
        g.spawn_system.spawn_enemy()
        assert any(getattr(e, "enemy_type", None) == "giant" for e in g.enemies)

        # a few seconds later but still within cooldown: no new giant
        g.enemies = type(g.enemies)()
        g.time_elapsed = 5.0
        g.spawn_system.spawn_enemy()
        assert not any(getattr(e, "enemy_type", None) == "giant" for e in g.enemies)

        # after 12 seconds have passed the giant may spawn again
        g.enemies = type(g.enemies)()
        g.time_elapsed = 13.0
        g.spawn_system.spawn_enemy()
        assert any(getattr(e, "enemy_type", None) == "giant" for e in g.enemies)
    finally:
        random.random = original_random


def test_wave_time_spawn_respects_cooldown():
    """The wave-time giant guarantee should not bypass the 12‑second rule.
    If a giant spawned only a few seconds earlier, the automatic spawn should
    wait until the cooldown expires."""
    g = Game()
    g.reset_game()
    g.select_stage("purgatory")
    g.wave = 1

    # manually perform a random giant spawn
    import random

    orig = random.random
    try:
        random.random = lambda: 0.01
        g.spawn_system.spawn_enemy()
    finally:
        random.random = orig

    # wave time reaches 12 shortly after but cooldown should block
    g.wave_time = 12.0
    g.time_elapsed = 5.0
    g.update_wave_progression()
    assert sum(1 for e in g.enemies if getattr(e, "enemy_type", None) == "giant") == 1

    # still within wave, after cooldown expires
    g.wave_time += 8.0
    g.time_elapsed += 8.0
    g.update_wave_progression()
    assert sum(1 for e in g.enemies if getattr(e, "enemy_type", None) == "giant") == 2


def test_victory_timer_starts_after_room_empty():
    """A 5‑second countdown should begin only once all enemies have vanished.

    We manually set the ready flag and manipulate the enemy list to ensure the
    timer does not start prematurely, then verify the overlay appears exactly
    after the specified delay.
    """
    from src.entities.enemy import Enemy

    g = Game()
    g.reset_game()
    g.select_stage("limbo")

    # mark ready before any enemies exist
    g.limbo_horde_ready_for_victory = True
    # with no enemies the timer should start immediately on update
    g.update()
    # update() decrements the value once, so expect between fps*5-1 and fps*5
    assert 0 < g.limbo_horde_victory_timer <= int(g.fps * 5)
    # clear flag now to avoid re-triggering
    g.limbo_horde_ready_for_victory = False

    # spawn a dummy enemy and set the flag again
    e = Enemy(0, 0)
    try:
        g.enemies.add(e)
    except Exception:
        g.enemies = [e]
    # clear any leftover timer from previous check
    g.limbo_horde_victory_timer = 0
    g.limbo_horde_ready_for_victory = True
    g.update()
    # timer should not start while enemies remain
    assert g.limbo_horde_victory_timer == 0

    # remove the enemy, timer should begin on the next update
    try:
        g.enemies.empty()
    except Exception:
        g.enemies = []
    g.update()
    # account for one decrement from the update call
    assert 0 < g.limbo_horde_victory_timer <= int(g.fps * 5)
    t = g.limbo_horde_victory_timer

    # run until just before expiration; victory should not show
    for _ in range(t - 1):
        g.update()
        assert not g.showing_victory
    g.update()
    assert g.showing_victory


@pytest.mark.parametrize("stage", ["limbo", "limbo_2", "limbo_3"])
def test_victory_delayed_until_all_enemies_cleared(stage):
    """The win countdown is deferred until the room is empty.

    To reproduce the original bug we manually bump the kill counter past the
    expected horde size by "killing" an unrelated enemy.  If there are still
    live horde foes on-screen the victory timer must not start until those
    enemies have also been cleared.
    """
    from src.entities.enemy import Enemy

    g = Game()
    g.reset_game()
    g.select_stage(stage)

    # trigger the horde and let some actual sprites spawn so the group is
    # non-empty. we don't care about the exact number, just that there are
    # enemies we won't remove until later.
    g.time_elapsed = LIMBO_HORDE_TIME
    for _ in range(int(g.fps * 2)):
        g.spawn_system.update_enemy_spawning()
    initial = g.limbo_horde_initial
    assert initial > 0
    assert len(g.enemies) > 0

    # pretend the player has killed all but one of the horde, then kill a
    # stray creature to push the count over the threshold.  the real horde
    # enemies remain alive in ``g.enemies``.
    g.limbo_horde_killed = initial - 1
    stray = Enemy(0, 0)
    g.enemies.add(stray)
    g.record_enemy_kill()  # bump kill count to ``initial``
    g.enemies.remove(stray)

    # the completion flags should have been flipped, and the deferred flag
    # should still be set because the room isn't empty yet.
    assert g.limbo_horde_completed
    assert g.limbo_horde_ready_for_victory
    assert len(g.enemies) > 0

    # run a couple of frames and verify that the overlay does *not* start
    # while enemies remain.
    for _ in range(int(g.fps * 2)):
        g.update()
        assert not g.showing_victory

    # now clear the remaining foes; the countdown should finally begin
    g.enemies.empty()
    for _ in range(int(g.fps * 5) + 1):
        g.update()
    assert g.showing_victory, "Victory overlay never activated after clearing last foes"


def test_satan_growth_scripted():
    """After the fourth horde burst the player should scale and gain buffs.

    Growth should begin immediately once the 18s phase spawns, continue for
    five seconds, and persist thereafter (health doubled, fire rate +50%).
    """
    from src.balance import DEFAULT_FIRE_RATE_MULTIPLIER

    g = Game()
    g.reset_game()
    g.select_stage("limbo")

    # record base health before anything happens
    base_health = g.player.max_health
    # trigger the horde
    g.time_elapsed = LIMBO_HORDE_TIME
    # run until the phase index moves past the fourth entry
    while g.limbo_horde_phase_index < 4:
        g.spawn_system.update_enemy_spawning()
    # growth should now be active and buffs applied
    assert g.satan_growth_active
    assert g.player.max_health == base_health * 2
    assert g.player.health == g.player.max_health
    assert g.player.fire_rate_multiplier >= DEFAULT_FIRE_RATE_MULTIPLIER * 1.5
    # screen shake should be triggered during growth
    assert g.shake_timer > 0
    assert g.shake_intensity >= 1

    # run a few frames to let the duration elapse.  the growth flag
    # should clear after the configured period (shake continues while active),
    # but the persistent flag and aura should remain.
    duration = g.satan_growth_duration
    for _ in range(duration + 2):
        g.spawn_system.update_enemy_spawning()
    assert not g.satan_growth_active
    assert g.satan_growth_persistent
    # player's size should remain unchanged
    assert g.player.width == g.player.original_width
    assert g.player.height == g.player.original_height


def test_satan_growth_aura_effect():
    """During the scripted growth, Satan should be surrounded by a red pulse aura.

    We trigger the growth state directly, advance a few frames so the pulse
    formula has nonzero value, render the game objects onto an offscreen
    surface, and then inspect a pixel just outside the player's silhouette.
    The pixel should have nonzero alpha and be predominantly red.
    """
    import math

    import pygame

    pygame.init()
    g = Game()
    g.reset_game()
    g.select_stage("limbo")
    # prepare a drawing surface for the UI manager
    g.ui.screen = pygame.Surface((g.width, g.height), pygame.SRCALPHA)

    # activate growth and advance a few frames
    g.spawn_system._trigger_satan_growth()
    assert g.satan_growth_active
    for _ in range(5):
        g.spawn_system.update_enemy_spawning()
    assert g.satan_growth_active

    # perform drawing
    g.ui.draw_game_objects()

    # aura should still exist even after growth_active may have cleared
    assert g.satan_growth_persistent

    # compute a point just outside the player's bounds where the aura should be
    cx = g.player.rect.centerx
    cy = g.player.rect.centery
    w = g.player.width
    h = g.player.height
    base_radius = int(math.hypot(w, h) / 2)
    glow_radius = base_radius + 1
    outer_padding = 20
    aura_radius = glow_radius + outer_padding
    # pick a pixel near the bottom edge of the aura
    xpix = int(cx)
    ypix = int(cy + aura_radius - 1)
    color = g.ui.screen.get_at((xpix, ypix))
    assert color.a > 0, "Aura pixel should not be fully transparent"
    # red component should dominate (pure red aura)
    assert color.r >= color.g and color.r >= color.b


def test_giant_spawn_limits_in_limbo():
    """Giants shouldn't appear in the first 30s of limbo and become rarer after."""
    import random

    g = Game()
    g.reset_game()
    g.select_stage("limbo")
    g.wave = 5  # enable giant eligibility

    # patch random to return a value that would normally spawn a giant
    original_random = random.random
    try:
        random.random = lambda: 0.01
        # before 30s, no giant should ever spawn
        g.time_elapsed = 10.0
        for _ in range(10):
            g.spawn_system.spawn_enemy()
        assert all(
            getattr(e, "enemy_type", None) != "giant" for e in g.enemies
        ), "No giants allowed early"
        # after 30s, with low-chance threshold 0.025, the same random value should spawn one
        g.enemies = type(g.enemies)()
        g.time_elapsed = 31.0
        g.spawn_system.spawn_enemy()
        assert any(
            getattr(e, "enemy_type", None) == "giant" for e in g.enemies
        ), "Giant should spawn after 30s"
    finally:
        random.random = original_random


def test_cooldown_ignored_during_limbo_horde():
    """During an active limbo horde the giant cooldown is waived so multiple
    giants can appear in rapid succession."""
    import random

    g = Game()
    g.reset_game()
    g.select_stage("limbo")
    # pretend we're currently inside a horde
    g.limbo_horde_active = True
    # make sure the usual limbo-30s restriction is not masking what we're
    # trying to test; pretend we've been in the level long enough for giants
    # to be allowed normally.
    g.time_elapsed = 31.0

    original_random = random.random
    try:
        random.random = lambda: 0.01
        g.spawn_system.spawn_enemy()
        assert any(getattr(e, "enemy_type", None) == "giant" for e in g.enemies)
        # clear list and try again immediately
        g.enemies = type(g.enemies)()
        g.spawn_system.spawn_enemy()
        assert any(
            getattr(e, "enemy_type", None) == "giant" for e in g.enemies
        ), "Horde should override the spawn cooldown"
    finally:
        random.random = original_random


def test_speed_reduced_in_limbo_and_prologo():
    """Ensure enemies spawn with 20% slower speed in limbo/prologa stages."""
    from src.balance import ENEMY_BASE_SPEEDS

    # create fresh game for each stage to avoid container conflicts
    for stage in ("prologo", "limbo"):
        g = Game()
        g.reset_game()
        g.select_stage(stage)
        # spawn a single enemy (random type) and check its speed reduction
        # no need to clear g.enemies; it's empty after reset
        g.wave = 5
        # force a stable random so we know what type we get
        import random

        random.random = lambda: 0.25  # ensures "normal" type (<0.3 & >=0.15)
        g.spawn_system.spawn_enemy()
        speeds = [
            (getattr(e, "speed", None), getattr(e, "enemy_type", None))
            for e in g.enemies
        ]
        assert speeds, "enemy should have spawned"
        speed, etype = speeds[0]
        base = ENEMY_BASE_SPEEDS.get(etype or "normal", 75)
        assert abs(speed - base * 0.8) < 1e-3, f"{etype} speed should be 0.8x"
        # restore random
        random.random = __import__("random").random
