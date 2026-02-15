import math
from types import SimpleNamespace

from test_utils import DummyGroup, DummyPlayer

from src.entities.enemy import Enemy


def test_boss_big_triple_shot_has_wide_spread():
    boss = Enemy(100, 100, enemy_type="boss_big", health=500)
    # Ensure pattern_timer is positive so we hit the big_shot branch
    boss.pattern_timer = 10
    boss.big_shot_cooldown = 0

    # Place player to the right so base_angle is ~0 radians
    player = DummyPlayer(boss.x + 200, boss.y)

    game = SimpleNamespace(
        enemy_projectiles=DummyGroup(),
        selected_stage=None,
        prologo_final_boss_immortal=False,
        width=800,
        height=600,
        fps=60,
    )

    boss.update(player, game)

    # Expect at least three projectiles from the triple spread
    assert len(game.enemy_projectiles) >= 3

    # Get the three projectiles (order preserved)
    p1, p2, p3 = game.enemy_projectiles[:3]

    # Compute angles in degrees
    a1 = math.degrees(math.atan2(p1.vel_y, p1.vel_x))
    _ = math.degrees(math.atan2(p2.vel_y, p2.vel_x))
    a3 = math.degrees(math.atan2(p3.vel_y, p3.vel_x))

    # Outer angles should be notably separated (we expect ~30° between outer projectiles)
    outer_sep = abs(a3 - a1)
    assert outer_sep > 25
