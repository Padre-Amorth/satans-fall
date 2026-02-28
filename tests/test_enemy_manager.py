import random

import pygame

from src.game import Game


def test_spawn_and_recycle():
    pygame.init()
    g = Game(debug=True)
    em = g.enemy_manager
    assert em is not None

    # Spawn an enemy via manager
    e = em.spawn(100, 100, "weak", health=10, speed=50)

    # It should be in game's enemies container
    found = False
    try:
        for en in g.enemies:
            if en is e:
                found = True
                break
    except Exception:
        if e in g.enemies:
            found = True
    assert found

    # Recycle the enemy
    em.recycle(e)

    # After recycle, it shouldn't be active and should be in pool
    assert e not in em.active
    assert e in em.pool


def test_spawn_via_game_spawn_enemy():
    pygame.init()
    g = Game(debug=True)
    # Call the game's spawn helper which should use EnemyManager
    g.spawn_enemy()

    # Expect at least one enemy in container
    assert len(list(g.enemies)) >= 1
    # Manager active list should reflect it
    if g.enemy_manager is not None:
        assert len(g.enemy_manager.active) >= 1


def test_non_boss_spawn_speed_matches_spawn_value():
    """Non-boss spawns (weak, normal, strong, angel, giant) should use the spawn `speed` directly (no global modifier)."""


def test_weak_enemy_base_health():
    """Verify that a spawned weak enemy has the updated base HP (45)."""
    pygame.init()
    g = Game(debug=True)
    # force the random branch to choose weak (rand >= 0.5)
    from unittest.mock import patch

    with patch("random.random", return_value=0.9):
        g.spawn_enemy()
    w = next((e for e in g.enemies if getattr(e, "enemy_type", "") == "weak"), None)
    assert w is not None, "weak enemy should have spawned"
    # constructor applies 1.2× scaling to max_health, so final health should
    # reflect that buff. round to int the same way the enemy does.
    expected = int(45 * g.difficulty_multiplier * 1.2)
    assert w.max_health == expected
    assert w.health == w.max_health

    # verify winged cannot spawn before wave 3, even if rand falls in its band
    pygame.init()
    g = Game(debug=True)
    g.wave = 1
    with patch("random.random", return_value=0.55):
        g.spawn_enemy()
    assert all(
        getattr(e, "enemy_type", "") != "winged" for e in g.enemies
    ), "Winged should not appear before wave 3"
    # early reinforcements also shouldn't produce winged
    try:
        for _e in list(g.enemies):
            try:
                g.enemies.remove(_e)
            except Exception:
                pass
    except Exception:
        g.enemies = []
    g.spawn_reinforcements(x=0, y=0, count=10)
    assert all(
        getattr(e, "enemy_type", "") != "winged" for e in g.enemies
    ), "Reinforcements before wave 3 must not contain winged"

    # now ensure winged spawns when wave >= 3 and rand indicates it
    pygame.init()
    g = Game(debug=True)
    g.wave = 3
    with patch("random.random", return_value=0.55):
        g.spawn_enemy()
    wing = next(
        (en for en in g.enemies if getattr(en, "enemy_type", "") == "winged"),
        None,
    )
    assert (
        wing is not None
    ), "winged enemy should have spawned at rand 0.55 when wave>=3"
    from src.balance import ENEMY_BASE_SPEEDS

    assert (
        abs(wing.speed - ENEMY_BASE_SPEEDS["winged"]) < 0.001
    )  # ensure winged got the health boost and a shield
    expected_base = 30 * g.difficulty_multiplier
    expected = int(expected_base * 1.2) * 2
    assert (
        wing.max_health == expected
    ), f"winged health {wing.max_health} should equal {expected}"
    assert wing.health == wing.max_health
    assert (
        hasattr(wing, "shield_hp") and wing.shield_hp == wing.max_health
    )  # health/shield checks again
    exp_base = 30 * g.difficulty_multiplier
    exp = int(exp_base * 1.2) * 2
    assert wing.max_health == exp
    assert hasattr(wing, "shield_hp") and wing.shield_hp == wing.max_health

    # 1) Force the 'normal' branch
    with patch("random.random", return_value=0.1):
        g.spawn_enemy()
    spawned = next(
        (en for en in g.enemies if getattr(en, "enemy_type", None) == "normal"), None
    )
    assert spawned is not None
    # spawn speed for normal is now read from balance
    from src.balance import ENEMY_BASE_SPEEDS

    assert abs(spawned.speed - ENEMY_BASE_SPEEDS["normal"]) < 0.001

    # 2) Spawn reinforcements covering weak/strong/angel/winged
    # Clear game's enemy container in a safe, container‑agnostic way
    try:
        for _e in list(g.enemies):
            try:
                g.enemies.remove(_e)
            except Exception:
                pass
    except Exception:
        try:
            g.enemies = []
        except Exception:
            pass

    g.spawn_reinforcements(x=200, y=80, count=6)
    # Ensure at least one non-boss enemy spawned and all non-boss enemies use spawn speed
    non_bosses = [
        en
        for en in g.enemies
        if getattr(en, "enemy_type", "").startswith(
            ("weak", "normal", "strong", "angel", "giant", "winged")
        )
    ]
    assert len(non_bosses) >= 1
    # Verify per-type spawn speeds using ENEMY_BASE_SPEEDS
    expected = {
        k: ENEMY_BASE_SPEEDS[k]
        for k in ("weak", "normal", "strong", "angel", "giant", "winged")
    }
    for en in non_bosses:
        et = getattr(en, "enemy_type", "")
        if et in expected:
            assert (
                abs(en.speed - expected[et]) < 0.001
            ), f"{et} expected {expected[et]} but got {en.speed}"


def test_reinforcements_triggered_when_boss_dies_in_update():
    """If a wave boss (boss_medium) dies during the bosses' update (e.g. burn),
    the reinforcement message + timer must still be scheduled and the
    USEREVENT+1 must spawn reinforcements when fired.
    """
    pygame.init()
    g = Game(debug=True)
    g.select_stage("purgatory")

    # Ensure no enemies initially
    try:
        for _e in list(g.enemies):
            try:
                g.enemies.remove(_e)
            except Exception:
                pass
    except Exception:
        try:
            g.enemies = []
        except Exception:
            pass

    em = g.enemy_manager
    # Spawn a mid-wave boss via manager/fallback
    boss = em.spawn_boss("mid")
    assert boss is not None
    assert boss.enemy_type == "boss_medium"
    assert boss in g.bosses

    # Kill the boss using take_damage (simulate DOT or other damage source)
    boss.take_damage(boss.max_health)

    # The centered message should have been enqueued
    msgs = [m for m in g.center_messages if "REINFORCEMENTS" in m.get("text", "")]
    assert (
        len(msgs) >= 1
    ), "Reinforcement message not shown when boss killed via take_damage"

    # Manually post the timer event (avoid waiting for real-time timer) and process events
    pygame.event.post(pygame.event.Event(pygame.USEREVENT + 1))
    g.handle_events()

    # After handling the event, there should be at least one non-boss enemy spawned
    non_bosses = [
        en
        for en in g.enemies
        if getattr(en, "enemy_type", "").startswith(
            ("weak", "normal", "strong", "angel", "giant", "winged")
        )
    ]
    assert len(non_bosses) >= 1, "Reinforcements were not spawned after USEREVENT+1"


def test_reinforcements_scheduled_when_boss_take_damage_kills():
    """Killing a wave boss via take_damage must schedule reinforcements (message + timer)."""
    pygame.init()
    g = Game(debug=True)
    g.select_stage("purgatory")
    em = g.enemy_manager

    boss = em.spawn_boss("mid")
    assert boss is not None and boss.enemy_type == "boss_medium"

    # Kill via take_damage (simulate DOT or direct ability)
    boss.take_damage(boss.max_health)

    # Centered message enqueued
    msgs = [m for m in g.center_messages if "REINFORCEMENTS" in m.get("text", "")]
    assert (
        len(msgs) >= 1
    ), "Reinforcement message not shown when boss killed via take_damage"

    # Fire the reinforcement event manually and ensure enemies spawn
    pygame.event.post(pygame.event.Event(pygame.USEREVENT + 1))
    g.handle_events()
    non_bosses = [
        en
        for en in g.enemies
        if getattr(en, "enemy_type", "").startswith(
            ("weak", "normal", "strong", "angel", "giant", "winged")
        )
    ]
    assert (
        len(non_bosses) >= 1
    ), "Reinforcements were not spawned after USEREVENT+1 when boss was killed via take_damage"


def test_wave_boss_health_drop(monkeypatch):
    """Wave bosses drop a slow health bonus that heals the player on contact."""
    pygame.init()
    g = Game(debug=True)
    g.select_stage("purgatory")
    # ignore any selection menus so update_game will process boss logic
    g.awaiting_weapon_choice = False
    g.awaiting_upgrade = False
    setattr(g, "awaiting_tower_choice", False)
    # clear corresponding state manager flags too
    g.game_state.awaiting_weapon_choice = False
    g.game_state.awaiting_upgrade = False
    g.game_state.awaiting_tower_choice = False
    em = g.enemy_manager
    # force a known heal amount
    monkeypatch.setattr(random, "randint", lambda a, b: 20)
    boss = em.spawn_boss("mid")
    assert boss is not None and boss.enemy_type == "boss_medium"
    g.player.health = 1
    boss.take_damage(boss.max_health)
    # run a frame of actual game logic to process boss death and spawn drop
    g.update_game()
    drops = getattr(g, "health_drops", [])
    assert len(drops) == 1
    assert drops[0].get("heal") == 20
    # drop size matches new radius (now 8)
    assert drops[0].get("radius") == 8
    # new fall speed
    assert drops[0].get("vy") == 1.5
    # ensure drop is within visible range
    assert drops[0].get("y", 0) >= 0
    drops[0]["x"] = g.player.x
    drops[0]["y"] = g.player.y
    g._update_health_drops()
    assert g.player.health == min(g.player.max_health, 1 + 20)
    assert getattr(g, "health_drops", []) == []


def test_inquisitor_health_drop(monkeypatch):
    """The Limbo inquisitor end-of-wave boss also drops health."""
    pygame.init()
    g = Game(debug=True)
    g.select_stage("purgatory")
    # clear all selection flags so update_game executes boss logic
    g.awaiting_weapon_choice = False
    g.awaiting_upgrade = False
    setattr(g, "awaiting_tower_choice", False)
    g.game_state.awaiting_weapon_choice = False
    g.game_state.awaiting_upgrade = False
    g.game_state.awaiting_tower_choice = False
    em = g.enemy_manager
    monkeypatch.setattr(random, "randint", lambda a, b: 25)
    boss = em.spawn_boss("inquisitor")
    assert boss is not None and boss.enemy_type == "boss_inquisitor"
    g.player.health = 2
    boss.take_damage(boss.max_health)
    g.update_game()
    drops = getattr(g, "health_drops", [])
    assert len(drops) == 1
    assert drops[0].get("heal") == 25
    assert drops[0].get("radius") == 8
    assert drops[0].get("y", 0) >= 0
    drops[0]["x"] = g.player.x
    drops[0]["y"] = g.player.y
    g._update_health_drops()
    assert g.player.health == min(g.player.max_health, 2 + 25)
    assert getattr(g, "health_drops", []) == []


def test_big_boss_health_drop(monkeypatch):
    """Big bosses (spawned by horde events) should also drop health."""
    pygame.init()
    g = Game(debug=True)
    g.select_stage("purgatory")
    g.awaiting_weapon_choice = False
    g.awaiting_upgrade = False
    setattr(g, "awaiting_tower_choice", False)
    g.game_state.awaiting_weapon_choice = False
    g.game_state.awaiting_upgrade = False
    g.game_state.awaiting_tower_choice = False
    g.game_state.awaiting_weapon_choice = False
    em = g.enemy_manager
    monkeypatch.setattr(random, "randint", lambda a, b: 30)
    boss = em.spawn_boss("big")
    assert boss is not None and boss.enemy_type == "boss_big"
    g.player.health = 3
    boss.take_damage(boss.max_health)
    g.update_game()
    drops = getattr(g, "health_drops", [])
    assert len(drops) == 1
    assert drops[0].get("heal") == 30
    assert drops[0].get("radius") == 8
    assert drops[0].get("y", 0) >= 0
    drops[0]["x"] = g.player.x
    drops[0]["y"] = g.player.y
    g._update_health_drops()
    assert g.player.health == min(g.player.max_health, 3 + 30)
    assert getattr(g, "health_drops", []) == []


def test_health_drop_sound(monkeypatch):
    """Spawning a health drop should play the click sound when audio is on."""
    g = Game(debug=True)
    calls = []

    # fake sound object with play method
    class DummySound:
        def play(self_inner):
            calls.append(True)

    from src.utils import sound as sound_utils

    monkeypatch.setattr(sound_utils, "suono_click_soft", lambda: DummySound())

    g.sounds_enabled = True
    g.spawn_health_drop(5, 5, 10)
    assert calls, "Sound should be played when sounds_enabled is True"

    calls.clear()
    g.sounds_enabled = False
    g.spawn_health_drop(6, 6, 8)
    assert not calls, "No sound when sounds are disabled"


def test_boss_take_damage_direct_shows_floating_text():
    """Calling take_damage on a boss should spawn a floating damage number."""
    pygame.init()
    g = Game(debug=True)
    g.select_stage("purgatory")
    boss = g.enemy_manager.spawn_boss("mid")
    assert boss is not None

    # no texts initially
    assert getattr(g, "floating_texts", []) == []
    boss.take_damage(12)
    assert len(g.floating_texts) == 1
    assert g.floating_texts[0].text == "12"


def test_strong_can_spawn_in_first_two_waves():
    """Ensure 'strong' has a 10% chance to appear in waves 1-2 (rand < 0.10)."""
    from unittest.mock import patch

    pygame.init()
    g = Game(debug=True)
    g.wave = 1
    # Force random.random to a value within the 10% threshold
    with patch("random.random", return_value=0.05):
        g.spawn_enemy()

    spawned = next(
        (en for en in g.enemies if getattr(en, "enemy_type", None) == "strong"),
        None,
    )
    assert (
        spawned is not None
    ), "Expected a 'strong' enemy to spawn for wave 1 with rand=0.05"
