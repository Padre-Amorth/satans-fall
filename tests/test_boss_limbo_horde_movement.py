from src.balance import ENEMY_BASE_SPEEDS
from src.entities.enemy import Enemy
import math


class DummyGame:
    def __init__(self, width=800, height=600):
        self.width = width
        self.height = height
        # minimal projectile container used by boss shooting logic
        class _DummyGroup:
            def add(self, *args, **kwargs):
                pass
        self.enemy_projectiles = _DummyGroup()

    def clamp_to_walls(self, x):
        # simple horizontal clamping consistent with game logic
        return max(0, min(self.width, x))


def test_boss_limbo_horde_speed_entry():
    """The balance table should contain a faster speed for the horde boss."""
    assert "boss_limbo_horde" in ENEMY_BASE_SPEEDS
    assert ENEMY_BASE_SPEEDS["boss_limbo_horde"] > ENEMY_BASE_SPEEDS.get(
        "boss_final", 0
    )


def test_boss_limbo_horde_moves_to_upper_half_and_bounces():
    g = DummyGame()
    boss = Enemy(
        100,
        -50,
        enemy_type="boss_limbo_horde",
        health=500,
        speed=ENEMY_BASE_SPEEDS["boss_limbo_horde"],
    )

    # use a simple dummy player so shooting code never crashes
    class DummyPlayer:
        x = g.width // 2
        y = g.height // 2

    player = DummyPlayer()

    # first update should still descend
    boss.update(player=player, game=g)
    assert boss.y > -50, "Boss should descend from offscreen on first update"

    # run until boss has completed its entrance and acquired a velocity vector
    for _ in range(1000):
        boss.update(player=player, game=g)
    assert boss.y <= g.height / 2
    assert hasattr(boss, "horde_vx"), "Boss should have velocity after entrance"

    # record initial horizontal velocity and position
    init_vx = boss.horde_vx
    start_x = boss.x
    start_y = boss.y

    # ensure the speed was doubled correctly (angle 30°)
    # new behaviour: speed is boosted by factor 3 (previously 2)
    expected_vx = ENEMY_BASE_SPEEDS["boss_limbo_horde"] * 3.0 * math.cos(math.radians(30))
    assert math.isclose(abs(init_vx), expected_vx, rel_tol=1e-2), "Horizontal speed should match boosted factor-3 value"

    # simulate for a while and ensure there are no sudden teleports
    prev_x, prev_y = boss.x, boss.y
    for _ in range(500):
        boss.update(player=player, game=g)
        dx = abs(boss.x - prev_x)
        dy = abs(boss.y - prev_y)
        assert dx < 50 and dy < 50, "Movement should be smooth without big jumps"
        # boss should always remain within the central horizontal zone
        center = g.width / 2
        assert center - 400 <= boss.x <= center + 400
        assert boss.horde_y_min <= boss.y <= boss.horde_y_max
        prev_x, prev_y = boss.x, boss.y

    # continue check boundaries while waiting for a bounce reversal
    for _ in range(5000):
        boss.update(player=player, game=g)
        center = g.width / 2
        assert center - 400 <= boss.x <= center + 400
        assert boss.horde_y_min <= boss.y <= boss.horde_y_max
        if boss.horde_vx != init_vx:
            reversed_once = True
            break

    # continue updating until we either see a reversal or hit a generous cap
    reversed_once = False
    for _ in range(5000):
        boss.update(player=player, game=g)
        if boss.horde_vx != init_vx:
            reversed_once = True
            break
    assert reversed_once, "Boss should reverse direction when it hits a wall"

    # final position should still be in upper half
    assert boss.y <= g.height / 2
    assert g.height * 0.25 * 0.5 <= boss.y <= g.height / 2
    # and horizontally confined to the centre 800‑pixel band
    center = g.width / 2
    assert center - 400 <= boss.x <= center + 400


def test_boss_limbo_horde_never_chases_player():
    g = DummyGame()
    # start boss above the screen similar to actual spawn
    boss = Enemy(
        50,
        -50,
        enemy_type="boss_limbo_horde",
        health=100,
        speed=ENEMY_BASE_SPEEDS["boss_limbo_horde"],
    )

    # place player far right bottom
    class DummyPlayer:
        x = g.width
        y = g.height

    player = DummyPlayer()
    # run a few updates and ensure boss x doesn't move steadily toward the player
    for _ in range(20):
        boss.update(player=player, game=g)
    # after updates the boss should still be comfortably away from the right edge
    assert (
        boss.x < g.width - 50
    ), "Boss should not drift all the way to the player's x position"
