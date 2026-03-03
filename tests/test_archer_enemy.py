import pygame

from src.entities.enemy import Enemy
from src.game import Game
from src.game_constants import (
    ARCHER_PROJECTILE_RADIUS,
    ARCHER_VERTICAL_LIMIT,
)


def test_archer_initial_stats():
    pygame.init()
    g = Game(debug=True)
    # spawn via spawn_system to bypass Game wrapper (which doesn't accept forced_type)
    g.spawn_system.spawn_enemy(forced_type="archer")
    archer = next(
        (e for e in g.enemies if getattr(e, "enemy_type", None) == "archer"), None
    )
    assert archer is not None, "Archer should have spawned with forced_type"
    # base normal health is 50, doubled by archer rule
    expected_hp = int(
        50 * g.difficulty_multiplier * 2 * 1.2
    )  # applies global 1.2 boost as well
    assert archer.max_health == expected_hp
    assert archer.health == expected_hp
    # speed should be pulled from balance
    from src.balance import ENEMY_BASE_SPEEDS

    assert abs(archer.speed - ENEMY_BASE_SPEEDS.get("archer", 40)) < 0.001


def test_archer_stays_top_and_moves_randomly():
    pygame.init()
    g = Game(debug=True)
    # create enemy starting below limit to verify repositioning
    a = Enemy(
        100, ARCHER_VERTICAL_LIMIT + 50, enemy_type="archer", health=100, speed=40
    )
    # add to game for clamp function
    try:
        g.enemies.add(a)
    except Exception:
        g.enemies.append(a)
    # perform several updates, ensure y never exceeds limit and x changes
    initial_x = a.x
    for _ in range(30):
        a.update(g.player, g)
        assert a.y <= ARCHER_VERTICAL_LIMIT
    assert a.x != initial_x, "Archer should jitter horizontally"


def test_archer_shooting_sequence():
    pygame.init()
    g = Game(debug=True)
    # make a standalone archer
    a = Enemy(200, 50, enemy_type="archer", health=100, speed=40)
    # Exit entry phase (archer starts entering from top, need to skip entry)
    a.archer_entering = False
    # force cooldown minimal to trigger shooting on update
    a.shoot_cooldown = 1
    # first update should fire single arrow #1
    a.update(g.player, g)
    assert len(g.enemy_projectiles) == 1
    assert a.archer_fire_count == 1  # moved to second single
    # second update should fire single arrow #2
    a.shoot_cooldown = 1
    a.update(g.player, g)
    assert len(g.enemy_projectiles) == 2  # 1 previous + 1 new
    assert a.archer_fire_count == 2  # ready for burst
    # third update should prepare burst (fire_count==2, burst_arrow==0->1)
    a.shoot_cooldown = 1
    a.update(g.player, g)
    assert len(g.enemy_projectiles) == 2  # no projectile fired yet, just setup
    assert a.archer_burst_arrow == 1  # prepared first burst arrow
    # fourth update should fire first burst arrow
    a.shoot_cooldown = 1
    a.update(g.player, g)
    assert len(g.enemy_projectiles) == 3  # 2 previous + 1 burst arrow
    assert a.archer_burst_arrow == 2
    # fifth update should fire second burst arrow
    a.shoot_cooldown = 1
    a.update(g.player, g)
    assert len(g.enemy_projectiles) == 4  # 3 previous + 1 burst arrow
    assert a.archer_burst_arrow == 3
    # sixth update should fire third burst arrow and reset cycle
    a.shoot_cooldown = 1
    a.update(g.player, g)
    assert len(g.enemy_projectiles) == 5  # 4 previous + 1 burst arrow
    assert a.archer_fire_count == 0  # cycle reset
    assert a.archer_burst_arrow == 0
    # check that projectiles have expected damage/radius (damage defaults to 10 if not in game constants)
    for proj in list(g.enemy_projectiles):
        assert proj.damage >= 10
        assert proj.radius == ARCHER_PROJECTILE_RADIUS
