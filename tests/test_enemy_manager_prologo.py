import math

import pygame
import pytest

from src.entities.enemy import Enemy
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


def test_limbo_final_boss_spawns_at_three_minutes():
    pygame.init()
    g = Game(debug=True)
    em = g.enemy_manager
    g.selected_stage = "limbo_final"
    # simulate running update loop until boss time
    # start just before and step forward
    for t in (179, 180, 181):
        g.time_elapsed = t
        g.update_enemy_spawning()
        g.update_wave_progression()
        # update_prologo_events is now called automatically in Game.update(); replicate here
        g.update_prologo_events()
    assert em.limbo_final_boss_spawned is True
    assert any(b.enemy_type == "boss_limbo" for b in g.bosses)
    # repeating should not spawn extra
    pre = len(g.bosses)
    g.update_prologo_events()
    assert len(g.bosses) == pre


def test_limbo_final_boss_becomes_immortal_and_triggers_lightning():
    pygame.init()
    g = Game(debug=True)
    em = g.enemy_manager

    # spawn limbo_final boss manually
    g.selected_stage = "limbo_final"
    boss = em.spawn_boss("limbo")
    assert boss.enemy_type == "boss_limbo"
    # apply damage to push into immortality
    boss.health = boss.max_health * 0.12
    boss.take_damage(boss.max_health)
    assert g.limbo_final_boss_immortal is True
    assert int(boss.health) == int(boss.max_health * 0.1)

    # now simulate regen and lightning
    em.limbo_final_lightning_strike = False
    boss.health = boss.max_health - 1
    em.update_prologo_events()
    assert em.limbo_final_lightning_strike is True


def test_towers_fire_at_limbo_boss():
    """Statue/projectile weapons should target the Limbo boss when present."""
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "limbo_final"
    # place a boss and an enemy to ensure towers prefer closest
    boss = g.enemy_manager.spawn_boss("limbo")
    boss.x = 400
    boss.y = 100
    enemy = Enemy(0, 0, "normal", health=10, speed=1)
    g.enemies = [enemy]
    # setup towers
    from src.core.entities.tower import Tower

    # eliminate randomness for this validation
    g.left_tower = Tower(400, 400, inaccuracy=0.0)
    g.right_tower = Tower(800, 400, inaccuracy=0.0)
    # tick weapon system once
    ws = g.weapon_system
    g.statue_cooldown = 1
    ws.update_statue_weapons()

    # projectiles should include a missile heading toward boss coordinates
    # and the velocity vector should point from the offset origin to the boss
    found = False
    for p in g.projectiles:
        px = getattr(p, "x", 0)
        py = getattr(p, "y", 0)
        vx = getattr(p, "vel_x", getattr(p, "vx", 0))
        vy = getattr(p, "vel_y", getattr(p, "vy", 0))
        # expect starting near tower y=400
        if py >= 390:
            # ensure projectile was spawned at offset origin
            if hasattr(p, "_statue_offset"):
                offx, offy = p._statue_offset
                # origin should equal tower pos + offset
                exp_x = g.left_tower.x + offx if px < 500 else g.right_tower.x + offx
                exp_y = g.left_tower.y + offy
                assert px == pytest.approx(exp_x)
                assert py == pytest.approx(exp_y)
            # verify direction alignment with boss position
            dx = boss.x - px
            dy = boss.y - py
            if dx == 0 and dy == 0:
                found = True
                break
            proj_angle = math.atan2(vy, vx)
            target_angle = math.atan2(dy, dx)
            # compute smallest circular difference
            diff = abs(
                ((proj_angle - target_angle + math.pi) % (2 * math.pi)) - math.pi
            )
            if diff < 0.1:
                found = True
                break
    assert found, "No tower projectile spawned against boss in correct direction"


def test_voltaic_beams_start_at_statue_offsets():
    """Voltaic Mayhem beam origins should equal statue projectile start points.

    We configure left/right storm towers in each relevant stage and fire once.
    The chain_lightning_effects list should contain a beam beginning at the
    offset-adjusted coordinates identical to those produced by the statue logic.
    """
    pygame.init()
    from src.core.entities.tower import Tower
    from src.systems.weapon_system import statue_projectile_offsets

    for stage, offset_attr in [
        ("limbo", "STATUE_PROJECTILE_OFFSET_X_LIMBO"),
        ("limbo_2", "STATUE_PROJECTILE_OFFSET_X_LIMBO"),
        ("limbo_3", "STATUE_PROJECTILE_OFFSET_X_LIMBO"),
        ("limbo_final", "STATUE_PROJECTILE_OFFSET_X_LIMBO"),
        ("purgatory", "STATUE_PROJECTILE_OFFSET_X_PURGATORY"),
        ("hell", "STATUE_PROJECTILE_OFFSET_X_HELL"),
        ("prologo", None),
    ]:
        g = Game(debug=True)
        g.selected_stage = stage
        # place two storm towers at known coords
        g.left_tower = Tower(100, 200, tower_type="storm")
        g.right_tower = Tower(500, 200, tower_type="storm")
        # activate Voltaic Mayhem with at least two frames of duration so we don't
        # expire before the first update (see update_voltaic_mayhem logic)
        g.voltaic_active = True
        g.voltaic_time_left = 2
        # record expected origins using the shared helper; this ensures the test
        # mirrors production logic exactly and will catch drift if the helper
        # ever changes.
        stage_x, stage_y = statue_projectile_offsets(g)
        # limbo_final offset is computed in helper (now should be 35)
        left_origin = (100 + stage_x, 200 + stage_y)
        right_origin = (500 - stage_x, 200 + stage_y)
        # run update once
        g.tower_special.update_voltaic_mayhem()
        beams = g.game_state.chain_lightning_effects
        assert beams, f"No Voltaic Mayhem beam produced for stage {stage}"
        origs = [
            b["points"][0] for b in beams if "points" in b and len(b["points"]) > 0
        ]
        assert (
            left_origin in origs or right_origin in origs
        ), f"Beam origins {origs} didn't include expected offsets for {stage}"


def test_statue_projectile_offsets_helper():
    """The shared helper should agree with the constants for each stage."""
    from src import game_constants
    from src.systems.weapon_system import statue_projectile_offsets

    g = Game(debug=True)
    for stage, attr in [
        ("limbo", "STATUE_PROJECTILE_OFFSET_X_LIMBO"),
        ("limbo_2", "STATUE_PROJECTILE_OFFSET_X_LIMBO"),
        ("limbo_3", "STATUE_PROJECTILE_OFFSET_X_LIMBO"),
        ("limbo_final", "STATUE_PROJECTILE_OFFSET_X_LIMBO"),
        ("purgatory", "STATUE_PROJECTILE_OFFSET_X_PURGATORY"),
        ("hell", "STATUE_PROJECTILE_OFFSET_X_HELL"),
        ("prologo", None),
    ]:
        g.selected_stage = stage
        x, y = statue_projectile_offsets(g)
        # limbo_final should subtract 20 from the limbo constant
        if stage == "limbo_final":
            expected_x = getattr(game_constants, attr) - 35
        else:
            expected_x = getattr(game_constants, attr) if attr else 0
        expected_y = game_constants.STATUE_PROJECTILE_OFFSET_Y
        assert (x, y) == (
            expected_x,
            expected_y,
        ), f"helper returned {(x,y)} for {stage}"


def test_limbo_lightning_does_not_trigger_game_over():
    """Player death from the Limbo boss lightning shouldn’t immediately game over.

    The game_over flag is only set when the lightning timer completes and
    limbo_final_defeat is called.
    """
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "limbo_final"
    em = g.enemy_manager

    # simulate boss regen and full health lightning
    boss = em.spawn_boss("limbo")
    boss.health = boss.max_health * 0.5
    # trigger immortal and then regen until full
    g.limbo_final_boss_immortal = True
    for _ in range(1000):
        boss.health = min(boss.max_health, boss.health + 3.0)
        if boss.health >= boss.max_health:
            break
    assert boss.health >= boss.max_health

    # resetting flags to emulate the moment just before strike
    em.limbo_final_lightning_strike = False
    # now do the strike
    em.limbo_final_lightning_strike = True
    g.player.health = 0

    # Immediately after strike we should NOT be in game over
    assert not getattr(g, "showing_game_over", False)
    # advance timer to completion, which normally fires limbo_final_defeat
    g.limbo_final_lightning_timer = g.limbo_final_lightning_duration_frames
    em.update_prologo_events()
    # defeat screen should now be active (not game over)
    assert getattr(g, "showing_prologo_end", False)
    assert not getattr(g, "showing_game_over", False)


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
