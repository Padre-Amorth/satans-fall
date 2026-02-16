from src.game import Game


def test_purgatory_towers_fire_when_enemies_present():
    g = Game()

    # Select purgatory and pick a tower
    g.select_stage("purgatory")
    # consume weapon choice to move to tower choice
    if g.weapon_choices:
        g.apply_weapon(g.weapon_choices[0]["id"])
    assert g.awaiting_tower_choice
    chosen = g.tower_choices[0]["id"]
    g.apply_tower(chosen)

    # Place a dummy enemy in play area
    g.enemies = [{"x": g.width // 2, "y": 100, "health": 10, "radius": 12}]

    # Prepare statue cooldown to fire immediately
    g.statue_cooldown = 1
    g.statue_next_left = True
    g.statue_projectiles = []

    # Call update_statue_weapons directly
    g.update_statue_weapons()

    assert (
        len(g.statue_projectiles) > 0
    ), "Expected at least one statue projectile in purgatory"
