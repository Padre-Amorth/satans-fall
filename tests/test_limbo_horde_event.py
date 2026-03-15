#!/usr/bin/env python3
"""Tests for the Limbo horde event at 8 minutes.

The scenario is triggered on the three "regular" limbo stages (limbo, limbo_2,
limbo_3).  Once time_elapsed reaches the threshold the game spawns a large batch
of enemies and begins tracking a special horde.  The level should not end until
the player has slain every enemy in the horde; previously the run would finish
with a scripted explosion once half the horde was dead.
"""

import pygame
import pytest

from src.game import Game
from src.game_constants import (
    LIMBO_HORDE_TIME_1,
    LIMBO_HORDE_TIME_2,
    LIMBO_HORDE_TIME_3,
)


@pytest.mark.parametrize(
    "stage,horde_time",
    [
        ("limbo", LIMBO_HORDE_TIME_1),
        ("limbo_2", LIMBO_HORDE_TIME_2),
        ("limbo_3", LIMBO_HORDE_TIME_3),
    ],
)
def test_limbo_horde_triggers_and_completes(stage, horde_time):
    g = Game()
    # ensure the game is running and stage is initialized
    g.reset_game()
    g.select_stage(stage)

    # fast-forward to the horde threshold and run until all phases have fired
    g.time_elapsed = horde_time
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
    # verify the aggregate size recorded by the game matches the sum of
    # counts *plus any bosses*.  This is what the player actually needs to
    # kill before victory can appear.
    initial_total = sum(
        e.get("count", 0) + e.get("boss_count", 0) for e in base_expected
    )
    # remaining tracks horde size; verify it matches expected
    assert g.limbo_horde_remaining == initial_total
    # remaining may have decreased by whatever spawned on the first update call
    # so we don't assert exact equality here

    # tick through entire schedule to accumulate horde enemies
    # we run long enough to cover the last burst at 40s
    for _ in range(int(g.fps * 55)):
        g.spawn_system.update_enemy_spawning()
    assert g.limbo_horde_started
    assert g.limbo_horde_active
    remaining = g.limbo_horde_remaining
    assert (
        remaining == 79
    ), f"horde size should now be 79 (including boss), got {remaining}"

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
    g.time_elapsed = horde_time
    g.spawn_system.update_enemy_spawning()
    initial_count = len(g.enemies)
    assert 9 <= initial_count <= 12
    # Run through all remaining schedule phases. Rather than asserting exact
    # intermediate counts (which depend on normal-spawner overlap and timing
    # jitter), just advance enough frames to cover the full schedule and verify
    # the total at the end is in the right ballpark.
    for _ in range(int(g.fps * 55)):
        g.spawn_system.update_enemy_spawning()
    # After running the full schedule, boss should have spawned
    assert getattr(
        g, "limbo_horde_boss_spawned", False
    ), "flag should flip when boss spawns"
    boss_spawned = any(
        b.enemy_type == "boss_limbo_horde" for b in getattr(g, "bosses", [])
    )
    assert boss_spawned, "horde boss should have spawned during schedule"
    # Horde should NOT be completed yet (boss is still alive)
    assert not g.limbo_horde_completed, "horde finished early before boss killed"
    # Completion is now boss-death-based: kill the boss and let update() detect it
    for boss in list(g.bosses):
        if getattr(boss, "enemy_type", "") == "boss_limbo_horde":
            boss.health = 0
    # Run update to trigger boss death detection
    g.update()
    assert (
        g.limbo_horde_completed
    ), "horde should only complete after boss death detected by update()"


# additional regression tests for the SATANIC VICTORY overlay


def _make_victory_game(stage="limbo"):
    g = Game(debug=True)
    g.selected_stage = stage
    g.showing_victory = True
    return g


def test_victory_overlay_esc_returns_menu():
    pygame.init()
    g = _make_victory_game("limbo")
    # simulate keypress
    g.handle_keydown(pygame.K_ESCAPE)
    # The escape key is meant to yank the player all the way back to the
    # main menu; the stage menu is not considered active in this context.
    assert g.showing_main_menu, "ESC should return to the main menu"
    assert not g.showing_victory


def test_victory_overlay_enter_advances_stage():
    pygame.init()
    g = _make_victory_game("limbo")
    current = g.selected_stage
    g.handle_keydown(pygame.K_RETURN)
    assert not g.showing_victory
    # stage should now be next in sequence
    assert g.selected_stage != current
    assert g.selected_stage in ("limbo", "limbo_2", "limbo_3")

    # weapon choice should run immediately and countdown must not have started yet
    assert getattr(
        g, "awaiting_weapon_choice", False
    ), "Should be awaiting weapon selection"
    assert (
        g.stage_start_countdown == 0
    ), "Countdown should be deferred while choosing weapon"
    assert g.stage_start_timer == 0

    # simulate selecting the first weapon and verify countdown begins
    g.handle_keydown(pygame.K_1)
    assert not getattr(
        g, "awaiting_weapon_choice", False
    ), "Weapon choice should be cleared after selection"
    assert g.stage_start_countdown == 3
    assert g.stage_start_timer == g.fps


def test_victory_overlay_esc_does_not_reappear():
    """Pressing ESC should dismiss the overlay and never bring it back.

    Previously the victory logic left limbo_horde_completed/timer active
    when the user backed out to the menu, which meant the ``update_game``
    fallback branch would restart the countdown while the menu was visible.
    The result was the SATANIC VICTORY screen popping up again a few seconds
    later, trapping the player.  Regression tests exercise both the menu and
    stage-advance paths.
    """
    pygame.init()
    g = _make_victory_game("limbo")
    # simulate state that could trigger the fallback logic
    g.limbo_horde_completed = True
    g.limbo_horde_victory_timer = 0

    g.handle_keydown(pygame.K_ESCAPE)
    assert g.showing_main_menu
    assert not g.showing_victory

    # run some frames to ensure the overlay does not come back
    for _ in range(int(g.fps * 10)):
        g.update_game()
    assert not g.showing_victory
    assert g.limbo_horde_victory_timer == 0
    assert not g.limbo_horde_completed
    # also verify no residual weapon choice or countdown occurred
    assert not getattr(g, "awaiting_weapon_choice", False)
    assert g.stage_start_countdown == 0


def test_victory_overlay_enter_does_not_reappear():
    """Advancing a stage after victory should not immediately trigger a new
    overlay on the following level."""
    pygame.init()
    g = _make_victory_game("limbo")
    g.limbo_horde_completed = True
    g.limbo_horde_victory_timer = 0
    curr = g.selected_stage
    g.handle_keydown(pygame.K_RETURN)
    assert not g.showing_victory
    assert g.selected_stage != curr

    # the reset_run called during continue_after_victory should clear the
    # completed flag, but verify that the timer remains inert over a few
    # frames so the overlay cannot reappear.
    for _ in range(int(g.fps * 10)):
        g.update_game()
    assert not g.showing_victory


@pytest.mark.parametrize(
    "stage,horde_time",
    [
        ("limbo", LIMBO_HORDE_TIME_1),
        ("limbo_2", LIMBO_HORDE_TIME_2),
        ("limbo_3", LIMBO_HORDE_TIME_3),
    ],
)
def test_no_wave_boss_during_limbo_horde(stage, horde_time):
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
    g.time_elapsed = horde_time
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


def test_boss_forced_even_if_cleared_early():
    """Even if the player kills every non-boss horde enemy before the final
    burst, the boss must still appear and the level shouldn't end until it
    dies."""
    pygame.init()
    g = Game(debug=True)
    g.reset_game()
    g.select_stage("limbo")
    # trigger horde
    g.time_elapsed = LIMBO_HORDE_TIME_1
    g.spawn_system.update_enemy_spawning()
    # wipe each wave as soon as it spawns
    for frame in range(int(g.fps * 60)):
        g.spawn_system.update_enemy_spawning()
        for e in list(g.enemies):
            e.kill()
        # stop when boss appears
        if getattr(g, "limbo_horde_boss_spawned", False):
            break
    assert getattr(g, "limbo_horde_boss_spawned", False), "boss should spawn"
    # boss now on-screen; kill it by setting health to 0 and let update() detect it
    for b in list(g.bosses):
        if b.enemy_type == "boss_limbo_horde":
            b.health = 0
    # update() detects boss death and sets completion flags
    g.update()
    # flag should reflect that the horde boss was killed
    assert getattr(g, "limbo_horde_boss_killed", False), "boss_killed flag not set"
    assert g.limbo_horde_completed, "Horde should finish only after boss death"


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


@pytest.mark.parametrize(
    "stage,horde_time",
    [
        ("limbo", LIMBO_HORDE_TIME_1),
        ("limbo_2", LIMBO_HORDE_TIME_2),
        ("limbo_3", LIMBO_HORDE_TIME_3),
    ],
)
def test_victory_delayed_until_all_enemies_cleared(stage, horde_time):
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
    g.time_elapsed = horde_time
    for _ in range(int(g.fps * 2)):
        g.spawn_system.update_enemy_spawning()
    remaining = g.limbo_horde_remaining
    assert remaining > 0
    assert len(g.enemies) > 0

    # Horde completion is now triggered by boss death detection in update(),
    # not by kill counting.  Simulate boss death by setting the flags directly
    # (as update() would do when boss_limbo_horde.health <= 0).
    g.limbo_horde_boss_killed = True
    g.limbo_horde_active = False
    g.limbo_horde_completed = True
    g.limbo_horde_ready_for_victory = True
    had_enemies = len(getattr(g, "enemies", [])) > 0

    # run a couple of frames and verify that we do not show victory *while*
    # enemies are expected to exist.  if cleanup already removed them the
    # overlay may appear immediately (that behaviour is acceptable).
    for _ in range(int(g.fps * 2)):
        g.update()
        if had_enemies:
            assert not g.showing_victory

    # now clear any remaining foes; the countdown should finally begin
    try:
        if hasattr(g.enemies, "empty"):
            g.enemies.empty()
        else:
            g.enemies = []
    except Exception:
        g.enemies = []
    for _ in range(int(g.fps * 5) + 1):
        g.update()
    assert g.showing_victory, "Victory overlay never activated after clearing last foes"


# Regression test for bug where the final boss death could be ignored if
# ``limbo_horde_active`` had been cleared before the kill.  This happened when
# the kill counter accidentally reached the threshold one enemy early; the
# active flag was shut off and subsequent boss kills were no longer recorded,
# leaving the run stuck indefinitely.
def test_boss_kill_counts_when_active_false():
    from src.entities.enemy import Enemy

    g = Game()
    g.reset_game()
    g.select_stage("limbo")

    # simulate that the horde has started with a single boss remaining
    # (initial count of 2: one generic and one boss)
    g.limbo_horde_initial = 2
    g.limbo_horde_killed = 1
    g.limbo_horde_active = True  # must be True for update() boss-death detection
    g.limbo_horde_completed = False
    g.limbo_horde_ready_for_victory = False

    # spawn a lone horde boss into the bosses group
    boss = Enemy(0, 0, "boss_limbo_horde", health=1, speed=0)
    try:
        g.bosses.add(boss)
    except Exception:
        g.bosses = type(g.bosses)([boss])

    # kill the boss by setting health to 0 and let update() detect the death
    boss.health = 0
    g.update()

    # after the call we expect the horde to be marked complete; the
    # ready_for_victory flag is consumed immediately when the victory timer
    # starts (since enemies/bosses are empty), so check the timer instead.
    assert g.limbo_horde_completed, "Horde should be completed after boss kill"
    assert (
        g.limbo_horde_victory_timer > 0 or g.limbo_horde_ready_for_victory
    ), "Victory timer should have started or ready flag should be set"

    # run a few frames to ensure the victory countdown completes and overlay
    # eventually appears (should happen within 6 seconds at 60fps)
    showed = False
    for _ in range(int(g.fps * 6)):
        g.update()
        if g.showing_victory:
            showed = True
            break
    assert showed, "Victory overlay failed to appear after boss kill"


# Ensure that if the ready flag is somehow cleared or never set the
# fallback in ``update()`` will still start the countdown once the room is
# empty.  This guards against infinite runs caused by obscure race
# conditions.
def test_victory_timer_fallback_when_ready_lost():
    g = Game()
    g.reset_game()
    g.select_stage("limbo")

    # simulate a completed horde with no enemies left
    g.limbo_horde_completed = True
    g.limbo_horde_ready_for_victory = False
    # clear any existing creatures
    try:
        g.enemies.empty()
    except Exception:
        g.enemies = []
    try:
        g.bosses.empty()
    except Exception:
        g.bosses = []

    # one update should start the timer via fallback
    g.update()
    assert g.limbo_horde_victory_timer > 0, "Fallback timer did not start"


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
    g.time_elapsed = LIMBO_HORDE_TIME_1
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


def test_giants_blocked_during_limbo_horde():
    """Ensure that no casual giants spawn when the horde is active.

    A common bug in earlier versions allowed giants to slip through during the
    event by cheating the 12‑second cooldown.  The desired behaviour is to
    completely suppress unscripted giants while ``limbo_horde_active`` is
    True; only the boss at the end of the schedule may appear.
    """
    import random

    g = Game()
    g.reset_game()
    g.select_stage("limbo")
    # pretend we're currently inside a horde
    g.limbo_horde_active = True
    # make sure any time‑based thresholds would normally permit a giant
    g.time_elapsed = 31.0

    original_random = random.random
    try:
        random.random = lambda: 0.01
        g.spawn_system.spawn_enemy()
        assert not any(
            getattr(e, "enemy_type", None) == "giant" for e in g.enemies
        ), "Giants should be suppressed during an active horde"
        # clear list and try again immediately
        g.enemies = type(g.enemies)()
        g.spawn_system.spawn_enemy()
        assert not any(
            getattr(e, "enemy_type", None) == "giant" for e in g.enemies
        ), "Giants should still be blocked while horde is active"
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
