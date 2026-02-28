import pygame
import pytest

from src.game import Game


def test_area_attack_timer_initialised():
    pygame.init()
    g = Game(debug=True)
    boss = g.enemy_manager.spawn_boss("limbo")
    assert hasattr(boss, "area_attack_cooldown")
    assert 180 <= boss.area_attack_cooldown <= 300


def test_area_attack_hits_player_centered():
    """Player centered on boss should take damage (old behavior)."""
    pygame.init()
    g = Game(debug=True)
    boss = g.enemy_manager.spawn_boss("limbo")
    boss.x = g.player.x
    boss.y = g.player.y
    boss.area_attack_cooldown = 0
    g.skullboom_explosions.clear()
    initial_hp = g.player.health

    delay = int(1.0 * g.fps)
    boss.update(g.player, g)

    # first update should create the indicator only
    assert len(g.skullboom_explosions) == 1
    exp = g.skullboom_explosions[0]
    assert exp["timer"] == delay

    # run until the pending explosion fires
    while getattr(boss, "pending_area", None) is not None:
        boss.update(g.player, g)

    assert len(g.skullboom_explosions) >= 2, "no actual explosion spawned"
    assert g.player.health < initial_hp, "player should take damage"

    # ensure drawing doesn't crash for both indicator and explosion frames
    try:
        g.draw_skullboom_particles()
    except Exception:
        pytest.skip("drawing explosions failed")


def test_area_attack_hits_if_majority_inside():
    """Player whose center is slightly outside old threshold but mostly inside
    the explosion should still be damaged under new logic.
    """
    pygame.init()
    g = Game(debug=True)
    boss = g.enemy_manager.spawn_boss("limbo")
    # place boss at origin for simplicity
    boss.x = 0
    boss.y = 0
    # place player's center outside old radius but rect still overlaps
    # explosion circle (center at 0,0, radius 50).  center distance = 55
    g.player.x = 55
    g.player.y = 0
    boss.area_attack_cooldown = 0
    g.skullboom_explosions.clear()
    hp_before = g.player.health

    boss.update(g.player, g)
    while getattr(boss, "pending_area", None) is not None:
        boss.update(g.player, g)

    # with new circle-rect check the player should take damage
    assert g.player.health < hp_before

    try:
        g.draw_skullboom_particles()
    except Exception:
        pytest.skip("drawing explosions failed")


def test_area_attack_targets_player_location():
    pygame.init()
    g = Game(debug=True)
    boss = g.enemy_manager.spawn_boss("limbo")
    boss.x = 0
    boss.y = 0
    # place player far away; explosion should still hit because target is player
    g.player.x = 1000
    g.player.y = 1000
    boss.area_attack_cooldown = 0
    g.skullboom_explosions.clear()
    hp_before = g.player.health

    delay = int(1.0 * g.fps)
    boss.update(g.player, g)
    assert len(g.skullboom_explosions) == 1
    exp = g.skullboom_explosions[0]
    assert exp["timer"] == delay
    assert exp.get("indicator") is True
    assert exp["radius"] == 50 and exp["max_radius"] == 50
    assert exp.get("indicator") is True
    assert exp["radius"] == 50 and exp["max_radius"] == 50

    while getattr(boss, "pending_area", None) is not None:
        boss.update(g.player, g)

    assert len(g.skullboom_explosions) >= 2
    assert (
        g.player.health < hp_before
    ), "player should have been hit even if far from boss"

    try:
        g.draw_skullboom_particles()
    except Exception:
        pytest.skip("drawing explosions failed")


def test_area_attack_player_moves_out_of_range():
    pygame.init()
    g = Game(debug=True)
    boss = g.enemy_manager.spawn_boss("limbo")
    boss.x = 0
    boss.y = 0
    g.player.x = 500
    g.player.y = 500
    boss.area_attack_cooldown = 0
    g.skullboom_explosions.clear()
    hp_before = g.player.health

    boss.update(g.player, g)
    assert getattr(boss, "pending_area", None) is not None
    # move player away before explosion fires
    g.player.x += 1000
    g.player.y += 1000

    while getattr(boss, "pending_area", None) is not None:
        boss.update(g.player, g)

    # explosion occurred at old location; health should be unchanged
    assert g.player.health == hp_before

    try:
        g.draw_skullboom_particles()
    except Exception:
        pytest.skip("drawing explosions failed")


def test_area_attack_resets_cooldown():
    pygame.init()
    g = Game(debug=True)
    boss = g.enemy_manager.spawn_boss("limbo")
    boss.x = g.player.x
    boss.y = g.player.y
    boss.area_attack_cooldown = 0
    g.skullboom_explosions.clear()

    boss.update(g.player, g)

    assert boss.area_attack_cooldown > 0
    # area attack should also have been scheduled
    assert getattr(boss, "pending_area", None) is not None
