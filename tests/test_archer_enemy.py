import pygame
from unittest.mock import patch

from src.game import Game
from src.entities.enemy import Enemy
from src.game_constants import ARCHER_VERTICAL_LIMIT, ARCHER_PROJECTILE_DAMAGE, ARCHER_PROJECTILE_RADIUS


def test_archer_initial_stats():
    pygame.init()
    g = Game(debug=True)
    # spawn via spawn_system to bypass Game wrapper (which doesn't accept forced_type)
    g.spawn_system.spawn_enemy(forced_type="archer")
    archer = next((e for e in g.enemies if getattr(e, "enemy_type", None) == "archer"), None)
    assert archer is not None, "Archer should have spawned with forced_type"
    # base normal health is 50, doubled by archer rule
    expected_hp = int(50 * g.difficulty_multiplier * 2 * 1.2)  # applies global 1.2 boost as well
    assert archer.max_health == expected_hp
    assert archer.health == expected_hp
    # speed should be pulled from balance
    from src.balance import ENEMY_BASE_SPEEDS
    assert abs(archer.speed - ENEMY_BASE_SPEEDS.get("archer", 40)) < 0.001


def test_archer_stays_top_and_moves_randomly():
    pygame.init()
    g = Game(debug=True)
    # create enemy starting below limit to verify repositioning
    a = Enemy(100, ARCHER_VERTICAL_LIMIT + 50, enemy_type="archer", health=100, speed=40)
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
    # force cooldown minimal to trigger shooting on update
    a.shoot_cooldown = 1
    # first update should fire a single arrow
    a.update(g.player, g)
    assert len(g.enemy_projectiles) == 1
    # next cycle should fire burst of three
    a.shoot_cooldown = 1
    a.update(g.player, g)
    assert len(g.enemy_projectiles) == 4  # 1 previous + 3 new
    # verify alternating flag toggled
    assert a.archer_fire_single_next is True
    # check that projectiles have expected damage/radius
    for proj in list(g.enemy_projectiles)[1:]:
        assert proj.damage == ARCHER_PROJECTILE_DAMAGE
        assert proj.radius == ARCHER_PROJECTILE_RADIUS
