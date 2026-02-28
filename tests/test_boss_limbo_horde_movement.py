from src.balance import ENEMY_BASE_SPEEDS
from src.entities.enemy import Enemy


class DummyGame:
    def __init__(self, width=800, height=600):
        self.width = width
        self.height = height

    def clamp_to_walls(self, x):
        # simple horizontal clamping consistent with game logic
        return max(0, min(self.width, x))


def test_boss_limbo_horde_speed_entry():
    """The balance table should contain a faster speed for the horde boss."""
    assert "boss_limbo_horde" in ENEMY_BASE_SPEEDS
    assert ENEMY_BASE_SPEEDS["boss_limbo_horde"] > ENEMY_BASE_SPEEDS.get(
        "boss_final", 0
    )


def test_boss_limbo_horde_moves_to_upper_half_and_oscillates():
    g = DummyGame()
    # mimic spawn offscreen above the playfield
    boss = Enemy(
        100,
        -50,
        enemy_type="boss_limbo_horde",
        health=500,
        speed=ENEMY_BASE_SPEEDS["boss_limbo_horde"],
    )

    # initial update should move the boss downward toward its staging area
    boss.update(player=None, game=g)
    assert boss.y > -50, "Boss should descend from offscreen on first update"

    # run updates until the boss reaches or passes the halfway mark
    for _ in range(1000):
        boss.update(player=None, game=g)
    assert boss.y <= g.height / 2, "Boss should end up in the upper half of the screen"

    # record positions for oscillation checks once entrance is complete
    prev_x = boss.x
    boss.update(player=None, game=g)

    # horizontal position should change due to sine drift
    assert (
        boss.x != prev_x
    ), "Boss should oscillate horizontally after reaching target height"
    # vertical position should remain in upper half
    assert boss.y <= g.height / 2
    # ensure small bobbing keeps it near the target zone
    assert abs(boss.y - (g.height * 0.25)) < g.height * 0.25


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
