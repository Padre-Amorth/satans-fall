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

    # Place an Enemy instance in play area
    from src.entities.enemy import Enemy

    e = Enemy(g.width // 2, 100, enemy_type="normal", health=10)
    try:
        g.enemies.empty()
        g.enemies.add(e)
    except Exception:
        g.enemies = [e]

    # Prepare statue cooldown to fire immediately
    g.statue_cooldown = 1
    g.statue_next_left = True

    # Call update_statue_weapons directly
    g.update_statue_weapons()

    # Expect at least one projectile with source 'statue' in game.projectiles
    try:
        proj_list = list(g.projectiles)
    except Exception:
        proj_list = g.projectiles
    assert any(
        getattr(p, "source", None) == "statue" for p in proj_list
    ), "Expected at least one statue projectile in purgatory"
