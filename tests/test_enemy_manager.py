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
    from unittest.mock import patch

    pygame.init()
    g = Game(debug=True)

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

    # 2) Spawn reinforcements covering weak/strong/angel
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
            ("weak", "normal", "strong", "angel", "giant")
        )
    ]
    assert len(non_bosses) >= 1
    # Verify per-type spawn speeds using ENEMY_BASE_SPEEDS
    expected = {
        k: ENEMY_BASE_SPEEDS[k] for k in ("weak", "normal", "strong", "angel", "giant")
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
            ("weak", "normal", "strong", "angel", "giant")
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
            ("weak", "normal", "strong", "angel", "giant")
        )
    ]
    assert (
        len(non_bosses) >= 1
    ), "Reinforcements were not spawned after USEREVENT+1 when boss was killed via take_damage"


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
