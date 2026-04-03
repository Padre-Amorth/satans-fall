import math
from types import SimpleNamespace

from test_utils import DummyGroup, DummyPlayer

from src.entities.enemy import Enemy


def test_boss_limbo_timers_are_set_on_creation():
    boss = Enemy(0, 0, enemy_type="boss_limbo", health=100)
    # pattern and big shot cooldown should exist (not None); pattern timer
    # should be roughly around three seconds (150–210 frames due to randomness).
    assert boss.pattern_timer is not None
    assert 150 <= boss.pattern_timer <= 210
    assert hasattr(boss, "big_shot_cooldown")
    assert boss.big_shot_cooldown is not None


def test_boss_limbo_triple_shot_appears_with_slow():
    boss = Enemy(100, 100, enemy_type="boss_limbo", health=500)
    # ensure pattern timer won't trigger radial and force big shot
    boss.pattern_timer = 10
    boss.big_shot_cooldown = 0

    # place player to the right so base angle ~0
    player = DummyPlayer(boss.x + 200, boss.y)

    game = SimpleNamespace(
        enemy_projectiles=DummyGroup(),
        selected_stage=None,
        prologo_final_boss_immortal=False,
        limbo_final_boss_immortal=False,
        width=800,
        height=600,
        fps=60,
    )

    boss.update(player, game)

    # triple spread should have injected at least three projectiles
    assert len(game.enemy_projectiles) >= 3

    # verify those projectiles carry the inquisitor slow effect
    found = 0
    for p in game.enemy_projectiles:
        if getattr(p, "effect", None) == "slow":
            found += 1
    assert found >= 3, "expected at least three slow projectiles"

    # check spread angle is similar to inquisitor's (~30° total arc)
    angles = []
    speeds = []
    for p in game.enemy_projectiles[:3]:
        angles.append(math.degrees(math.atan2(p.vel_y, p.vel_x)))
        speeds.append(math.hypot(p.vel_x, p.vel_y))
    angles.sort()
    arc = angles[-1] - angles[0]
    assert 25 <= arc <= 35, f"spread arc {arc:.1f} not in inquisitor range"
    # projectiles should be slightly faster than original 260 value
    assert all(s >= 290 for s in speeds), f"not fast enough: {speeds}"


def test_boss_limbo_single_large_projectile():
    boss = Enemy(100, 100, enemy_type="boss_limbo", health=500)
    # ensure triple shot doesn't fire and force pattern timer activation
    boss.pattern_timer = 0
    boss.big_shot_cooldown = 10

    player = DummyPlayer(boss.x + 200, boss.y)
    game = SimpleNamespace(
        enemy_projectiles=DummyGroup(),
        selected_stage=None,
        prologo_final_boss_immortal=False,
        limbo_final_boss_immortal=False,
        width=800,
        height=600,
        fps=60,
    )

    boss.update(player, game)

    # should have fired exactly one projectile which is larger than normal
    assert len(game.enemy_projectiles) == 1
    proj = game.enemy_projectiles[0]
    assert proj.radius >= 25, "expected big sphere radius"
    assert proj.damage >= 20, "expected heavy damage"
    # projectile should be noticeably faster than previous 280 value
    speed_mag = math.hypot(proj.vel_x, proj.vel_y)
    assert speed_mag >= 320, "projectile not sped up enough"
    # pattern_timer should equal three seconds (± a frame due to integer math)
    assert 170 <= boss.pattern_timer <= 190


def test_boss_limbo_horde_triple_is_green():
    """Horde boss triple shots should appear greenish instead of orange.

    We force a triple-shot event and sample the projectile's centre pixel
    after the sprite is drawn to confirm the hue shift.
    """
    boss = Enemy(100, 100, enemy_type="boss_limbo_horde", health=500)
    boss.big_shot_cooldown = 0
    # no pattern_timer needed since horde boss only shoots via big_shot

    player = DummyPlayer(boss.x + 200, boss.y)
    game = SimpleNamespace(
        enemy_projectiles=DummyGroup(),
        selected_stage=None,
        prologo_final_boss_immortal=False,
        limbo_final_boss_immortal=False,
        width=800,
        height=600,
        fps=60,
    )

    boss.update(player, game)
    assert game.enemy_projectiles, "expected at least one projectile"
    proj = game.enemy_projectiles[0]
    # draw it to ensure colour is baked into image
    proj.draw_projectile()
    w, h = proj.image.get_size()
    cx, cy = w // 2, h // 2
    col = proj.image.get_at((cx, cy))
    # green component should dominate red and blue for a "green" tint
    assert col[1] >= col[0] and col[1] >= col[2], f"not green: {col}"
    # size should reflect larger radius (diameter >= 16)
    assert w >= 16 and h >= 16, f"projectile too small: {w}x{h}"
