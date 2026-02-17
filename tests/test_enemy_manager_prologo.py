import pygame

from src.game import Game


def test_prologo_final_boss_spawn_and_lightning():
    pygame.init()
    g = Game(debug=True)
    em = g.enemy_manager
    assert em is not None

    # Simulate reaching the final boss time
    g.selected_stage = "prologo"
    g.time_elapsed = 235

    # Trigger prologo events
    g.update_prologo_events()

    # Manager should have spawned final boss
    assert em.prologo_final_boss_spawned is True

    # Ensure no additional wave bosses spawn after final boss - only non-boss enemies
    # (simulate end-of-wave boss time; manager should ignore wave-boss spawns for prologo)
    em.update_wave_boss(38)
    assert all(getattr(b, "enemy_type", "").startswith("boss_final") for b in g.bosses)
    finals = [b for b in g.bosses if getattr(b, "enemy_type", "") == "boss_final"]
    assert len(finals) >= 1

    # Test regen->lightning sequence: set final boss to be immortal and near-full health
    boss = finals[0]
    em.prologo_final_boss_immortal = True
    boss.health = boss.max_health - 1
    em.prologo_lightning_strike = False

    # Trigger update; should regen and immediately trigger lightning
    em.update_prologo_events()

    assert em.prologo_lightning_strike is True
    # Player should be knocked out (health 0) by lightning trigger
    assert getattr(g.player, "health", None) == 0
    assert hasattr(g, "lightning_points")


def test_prologo_final_boss_becomes_immortal_instead_of_dying():
    """Final boss should enter immortal/regeneration at 10% HP instead of dying

    Regression: area/explosion damage or other sources were killing the boss
    because the immortal-transition logic was not centralized. Ensure any call
    to take_damage triggers the transition and clamps HP to 10%.
    """
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "prologo"
    em = g.enemy_manager

    # Spawn final boss and ensure it's present
    boss = em.spawn_boss("final")
    assert boss is not None
    assert boss.enemy_type == "boss_final"
    assert boss in g.bosses

    # Put boss just above the threshold and apply a large hit
    boss.health = boss.max_health * 0.12
    # Apply a damage that would normally kill it; take_damage should clamp + set immortal
    boss.take_damage(boss.max_health)

    # Boss must have transitioned to immortal phase and be clamped to 10%
    assert g.prologo_final_boss_immortal is True
    assert int(boss.health) == int(boss.max_health * 0.1)
    # Boss should still be alive in boss group (not killed)
    assert boss in g.bosses
    # The defeated flag must not be set
    assert g.prologo_final_boss_defeated is False


def test_prologo_enemy_spawns_vary_after_draw():
    """Ensure Prologo spawns are not fixed by UI drawing (no global RNG reseed).

    Regression test for bug where `ui.draw()` reseeded the global RNG each
    frame causing identical enemy types/positions in Prologo.
    """
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "prologo"
    # Ensure walls are present for Prologo positioning
    g.generate_walls()

    xs = set()
    types = set()

    for _ in range(8):
        # simulate a frame draw (used to reseed RNG in the buggy implementation)
        try:
            g.draw()
        except Exception:
            # headless drawing may fail in some CI environments; ignore
            pass

        # spawn one enemy and record its x / type
        g.spawn_enemy()
        enemies = g._enemies_iter()
        assert enemies, "no enemies spawned"
        e = enemies[-1]
        xs.add(int(getattr(e, "x", 0)))
        types.add(getattr(e, "enemy_type", None))

        # cleanup last spawn so loop remains isolated
        try:
            if hasattr(g.enemies, "remove"):
                g.enemies.remove(e)
            else:
                g.enemies.pop()
        except Exception:
            pass

    # Expect some variation across spawns (very high probability)
    assert len(xs) > 1 or len(types) > 1
