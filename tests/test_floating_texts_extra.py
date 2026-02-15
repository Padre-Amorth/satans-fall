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

    enemy = {
        "x": 120,
        "y": 80,
        "health": 20,
        "burn_timer": 10,
        "burn_damage_per_second": 3,
        "burn_tick_counter": 1,
        "radius": 10,
    }
    # Use a list for dict-style enemies (matches legacy tests)
    g.enemies = [enemy]

    assert len(g.floating_texts) == 0
    g.update()
    # burn tick should spawn floating text
    assert len(g.floating_texts) >= 1
