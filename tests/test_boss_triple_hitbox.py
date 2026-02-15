from types import SimpleNamespace

from test_utils import DummyGroup, DummyPlayer

from src.entities.enemy import Enemy


def test_boss_triple_shot_hitbox_smaller():
    boss = Enemy(200, 200, enemy_type="boss_big", health=500)
    boss.pattern_timer = 10
    boss.big_shot_cooldown = 0

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

    # Ensure we have at least three projectiles
    assert len(game.enemy_projectiles) >= 3

    # Check the radius of the triple shot projectiles - they should be the smaller value
    for p in game.enemy_projectiles[:3]:
        assert hasattr(p, "radius")
        assert p.radius <= 8
