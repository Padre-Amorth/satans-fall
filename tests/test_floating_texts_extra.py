from src.entities.enemy import Enemy
from src.game import Game


def test_enemy_drain_spawns_text():
    g = Game(debug=True)
    # Prepare game for update loop
    g.selected_stage = "prologo"
    g.showing_stage_menu = False

    e = Enemy(100, 100)
    g.enemies.add(e)
    e.drain_timer = 61
    e.drain_damage = 5
    e.drain_heal = 1

    # No floating texts initially
    assert len(g.floating_texts) == 0

    # One update should bring timer to 60 and trigger tick
    g.update()
    assert len(g.floating_texts) >= 1


def test_dict_burn_spawns_text():
    g = Game(debug=True)
    g.selected_stage = "prologo"
    g.showing_stage_menu = False

    from src.entities.enemy import Enemy

    enemy_obj = Enemy(120, 80, enemy_type="normal", health=20)
    enemy_obj.health = 20
    enemy_obj.burn_timer = 10
    enemy_obj.burn_damage_per_second = 3
    enemy_obj.burn_tick_timer = 1
    enemy_obj.radius = 10
    g.enemies = [enemy_obj]

    assert len(g.floating_texts) == 0
    g.update()
    # burn tick should spawn floating text
    assert len(g.floating_texts) >= 1
