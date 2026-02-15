import pygame

from src.entities.enemy import Enemy
from src.game import Game
from src.projectile import Projectile


def test_storm_spatial_grid_collision_object():
    pygame.init()
    g = Game()

    # Three enemies close together (sprite objects)
    e1 = Enemy(400, 100, enemy_type="normal", health=20)
    e2 = Enemy(420, 100, enemy_type="normal", health=20)
    e3 = Enemy(440, 100, enemy_type="normal", health=20)
    try:
        g.enemies.empty()
        g.enemies.add(e1)
        g.enemies.add(e2)
        g.enemies.add(e3)
    except Exception:
        g.enemies = [e1, e2, e3]

    # Ensure spatial grid is built to exercise that branch
    from src.utils.spatial_grid import SpatialGrid

    g.spatial_grid = SpatialGrid(cell_size=120, width=g.width, height=g.height)
    g.spatial_grid.build(g._enemies_iter())

    proj = Projectile(400, 100, 0.0, 0.0, damage=5, radius=6, appearance="storm_statue")
    proj.source = "statue"
    proj.chain_targets = 3

    try:
        g.projectiles.add(proj)
    except Exception:
        g.projectiles = [proj]

    g.handle_collisions()

    # primary target damaged, projectile removed, chain visual applied
    assert e1.health == e1.max_health - 5
    assert proj not in list(g.projectiles)
    assert getattr(proj, "_chain_applied", False) is True
    assert len(getattr(g.game_state, "chain_lightning_effects", [])) >= 1


def test_projectile_reset_clears_state_for_reuse():
    p = Projectile(0, 0, 0, 0, damage=5, radius=6, appearance="storm_statue")
    # Simulate having hit targets / applied chain
    p._hit_ids.add(1)
    p._chain_applied = True

    # Reset for reuse
    p.reset(
        10,
        10,
        1.0,
        1.0,
        damage=3,
        radius=4,
        is_enemy_projectile=False,
        weapon_type=None,
        source="statue",
        appearance="storm_statue",
    )

    # State that must be cleared on reset
    assert p._hit_ids == set()
    assert p._chain_applied is False
    # Values updated correctly
    assert p.x == 10 and p.y == 10
    assert p.damage == 3 and p.radius == 4


def test_storm_dict_projectile_with_spatial_grid_triggers_chain_and_removal():
    pygame.init()
    g = Game()

    # dict-style enemies and dict-style projectile (backwards compat)
    g.enemies = [
        {"x": 400, "y": 100, "health": 20, "max_health": 20, "radius": 12},
        {"x": 420, "y": 100, "health": 20, "max_health": 20, "radius": 12},
    ]

    # Build spatial grid so the spatial branch is taken
    from src.utils.spatial_grid import SpatialGrid

    g.spatial_grid = SpatialGrid(cell_size=120, width=g.width, height=g.height)
    g.spatial_grid.build(g._enemies_iter())

    proj = {
        "x": 400,
        "y": 100,
        "vel_x": 0.0,
        "vel_y": 0.0,
        "damage": 5,
        "radius": 6,
        "source": "statue",
        "appearance": "storm_statue",
        "chain_targets": 2,
    }
    g.projectiles = [proj]

    g.handle_collisions()

    # projectile dict should be removed on contact and chain visual added
    assert proj not in g.projectiles
    assert len(getattr(g.game_state, "chain_lightning_effects", [])) >= 1


def test_storm_left_slot2_chain_kill_triggers_explosion():
    """When `storm_2` permanent is active, enemies killed by chain lightning
    explode and damage nearby enemies."""
    pygame.init()
    g = Game()

    # Three enemies close together (sprite objects)
    e1 = Enemy(400, 100, enemy_type="normal", health=20)
    # e2 is weak so chain damage will kill it
    e2 = Enemy(420, 100, enemy_type="normal", health=5)
    e3 = Enemy(450, 100, enemy_type="normal", health=20)
    try:
        g.enemies.empty()
        g.enemies.add(e1)
        g.enemies.add(e2)
        g.enemies.add(e3)
    except Exception:
        g.enemies = [e1, e2, e3]

    # Activate storm_2 permanent (on-kill explosion)
    g.permanent_stats["storm_1"] = 0
    g.permanent_stats["storm_2"] = 1
    g.permanent_stats["storm_3"] = 0
    g.apply_permanent_stats()

    proj = Projectile(400, 100, 0.0, 0.0, damage=5, radius=6, appearance="storm_statue")
    proj.source = "statue"
    # Only one chained target by design (ensure e3 is only hit by explosion)
    proj.chain_targets = 2

    try:
        g.projectiles.add(proj)
    except Exception:
        g.projectiles = [proj]

    g.handle_collisions()

    # e2 should be killed by the chain damage; e3 should take explosion damage
    assert getattr(e2, "health", 0) <= 0
    assert getattr(e3, "health", 0) < e3.max_health
    # Visual effect for the explosion (lightning) should be present
    assert any(
        any(abs(px - ex) < 5 and abs(py - ey) < 5 for px, py in eff["points"])
        for eff in getattr(g.game_state, "chain_lightning_effects", [])
        for ex, ey in [g._enemy_pos(e2)]
    )
    # Effect should be marked as an explosion for UI to render the flash
    assert any(
        eff.get("explosion")
        for eff in getattr(g.game_state, "chain_lightning_effects", [])
    )


def test_storm_left_slot2_no_explosion_without_permanent():
    """Ensure explosion does NOT occur when `storm_2` is not active."""
    pygame.init()
    g = Game()

    e1 = Enemy(400, 100, enemy_type="normal", health=20)
    e2 = Enemy(420, 100, enemy_type="normal", health=5)
    e3 = Enemy(450, 100, enemy_type="normal", health=20)
    try:
        g.enemies.empty()
        g.enemies.add(e1)
        g.enemies.add(e2)
        g.enemies.add(e3)
    except Exception:
        g.enemies = [e1, e2, e3]

    # Ensure storm_2 not active
    g.permanent_stats["storm_1"] = 0
    g.permanent_stats["storm_2"] = 0
    g.permanent_stats["storm_3"] = 0
    g.apply_permanent_stats()

    proj = Projectile(400, 100, 0.0, 0.0, damage=5, radius=6, appearance="storm_statue")
    proj.source = "statue"
    # Only one chained target by design (ensure e3 is only hit by explosion)
    proj.chain_targets = 2

    try:
        g.projectiles.add(proj)
    except Exception:
        g.projectiles = [proj]

    g.handle_collisions()

    # e2 should be killed, but e3 must remain undamaged
    assert getattr(e2, "health", 0) <= 0
    assert getattr(e3, "health", 0) == e3.max_health
    # No explosion effects must be present when storm_2 is not active
    assert not any(
        eff.get("explosion")
        for eff in getattr(g.game_state, "chain_lightning_effects", [])
    )
