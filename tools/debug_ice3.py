from src.core.entities.tower import Tower
from src.game import Game
from tests.test_tower import DummyEnemy


def run():
    g = Game()
    g.permanent_stats["ice_3"] = 1
    g.permanent_stats["ice_1"] = 1
    g.permanent_stats["ice_2"] = 0
    t = Tower(320, 530, tower_type="ice", projectile_speed=100.0, inaccuracy=0.0)
    g.left_tower = t
    g.apply_permanent_stats()
    e1 = DummyEnemy(400, 530)
    proj = t.fire_at_closest([e1])
    print("proj", proj, "appearance", getattr(proj, "appearance", None))
    g.projectiles.add(proj)
    print("initial projectiles count", len(list(g.projectiles)))
    proj.x, proj.y = 400, 530
    g.enemies.add(e1)
    try:
        g.handle_collisions()
    except Exception as ex:
        print("handle_collisions raised", ex)
        raise
    print("after handle: projectiles count", len(list(g.projectiles)))
    print("projectile still in list?", proj in list(g.projectiles))
    print("ice_puddles count", len(g.ice_puddles))


if __name__ == "__main__":
    run()
