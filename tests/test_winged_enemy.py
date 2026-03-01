import pygame

from src.balance import ENEMY_BASE_SPEEDS
from src.entities.enemy import Enemy
from src.game import Game


def test_winged_zigzag_and_fast_movement():
    """Winged enemies should oscillate horizontally and descend quickly."""
    pygame.init()
    g = Game(debug=True)
    # create a winged enemy heading downward from top
    w = Enemy(100, 0, "winged", health=30, speed=ENEMY_BASE_SPEEDS.get("winged", 120))

    dxs = []
    # simulate a few frames and record horizontal deltas
    for _ in range(20):
        old_x = w.x
        old_y = w.y
        w.update(g.player, g)
        dxs.append(w.x - old_x)
        # ensure the enemy moved downward at least once
        assert w.y > old_y

    # there should be both positive and negative horizontal changes
    assert any(d > 0 for d in dxs), "Winged enemy never moved right"
    assert any(d < 0 for d in dxs), "Winged enemy never moved left"

    # vertical speed should be greater than a normal enemy's default
    normal_speed = ENEMY_BASE_SPEEDS.get("normal", 75)
    # approximate expectation: winged moves at least 1.3× normal per frame
    assert (w.y / len(dxs)) >= (normal_speed / 60) * 1.3


def test_winged_wave_restriction():
    """Verify that winged enemies only spawn from wave 3 onward."""
    pygame.init()
    from unittest.mock import patch

    # wave 1 should never produce a winged on random roll
    g = Game(debug=True)
    g.wave = 1
    with patch("random.random", return_value=0.55):
        g.spawn_enemy()
    assert not any(getattr(e, "enemy_type", "") == "winged" for e in g.enemies)

    # reinforcements also should avoid winged early
    try:
        for e in list(g.enemies):
            try:
                g.enemies.remove(e)
            except Exception:
                pass
    except Exception:
        g.enemies = []
    g.spawn_reinforcements(x=0, y=0, count=20)
    assert not any(getattr(e, "enemy_type", "") == "winged" for e in g.enemies)

    # wave 3 should allow winged spawn
    g = Game(debug=True)
    g.wave = 3
    with patch("random.random", return_value=0.55):
        g.spawn_enemy()
    wing = next(
        (e for e in g.enemies if getattr(e, "enemy_type", "") == "winged"), None
    )
    assert wing is not None
    # health/shield checks
    expected_base = 30 * g.difficulty_multiplier
    expected = int(expected_base * 1.2) * 2
    assert wing.max_health == expected
    assert hasattr(wing, "shield_hp") and wing.shield_hp == wing.max_health


def test_winged_explodes_on_player_contact():
    """A winged enemy should detonate when it touches the player.

    The explosion should create a brief visual effect and deal a flat damage
    value specified by the constants in :mod:`src.game_constants`.
    """
    import pygame
    from src.game import Game
    from src.entities.enemy import Enemy
    from src.game_constants import (
        WINGED_CONTACT_DAMAGE,
        WINGED_EXPLOSION_RADIUS,
        WINGED_EXPLOSION_DURATION,
    )

    pygame.init()
    g = Game(debug=True)

    # ensure clean state
    try:
        g.enemies.empty()
    except Exception:
        g.enemies = []
    g.game_state.fire_explosions.clear()

    # place enemy exactly on top of player to force immediate contact
    w = Enemy(g.player.x, g.player.y, enemy_type="winged", health=5)
    try:
        g.enemies.add(w)
    except Exception:
        g.enemies.append(w)

    before_hp = g.player.health
    # trigger collision handling once
    g.handle_collisions()

    assert g.player.health == before_hp - WINGED_CONTACT_DAMAGE
    assert len(g.game_state.fire_explosions) == 1
    exp = g.game_state.fire_explosions[0]
    assert exp["radius"] == WINGED_EXPLOSION_RADIUS
    assert exp["timer"] == WINGED_EXPLOSION_DURATION
    # enemy should have been removed from the active list
    assert not any(getattr(e, "enemy_type", "") == "winged" for e in g.enemies)
