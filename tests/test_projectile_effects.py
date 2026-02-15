import pytest

from src.core.entities.tower import Tower
from src.game import Game


@pytest.mark.parametrize(
    "source, expected_effect",
    [
        ("tower_fire", "burn"),
        ("tower_ice", "slow"),
        ("demon_strike", "slow"),
    ],
)
def test_projectile_effects_apply_to_dict_enemy_and_boss(source, expected_effect):
    """Ensure projectiles that carry `burn`/`slow` apply the status to both dict-enemies and bosses."""
    g = Game()
    g.selected_stage = "limbo"

    # prepare a simple dict enemy (test-style)
    e = {
        "x": 320,
        "y": 520,
        "health": 30,
        "max_health": 30,
        "speed": 75,
        "radius": 12,
        "damage": 5,
        "type": "normal",
    }
    g.enemies = [e]

    # spawn a boss (use inquisitor as representative boss)
    boss = g.enemy_manager.spawn_boss("inquisitor")
    assert any(getattr(b, "enemy_type", "") == "boss_inquisitor" for b in g.bosses)

    # create / obtain projectile according to source
    if source == "tower_fire":
        t = Tower(320, 530, tower_type="fire", projectile_speed=100.0, inaccuracy=0.0)
        proj = t.fire_at_closest([e])
        # force known burn values for test determinism
        proj.burn_duration = 6
        proj.burn_damage_per_second = 4
    elif source == "tower_ice":
        t = Tower(320, 530, tower_type="ice", projectile_speed=100.0, inaccuracy=0.0)
        proj = t.fire_at_closest([e])
        proj.slow_duration = 120
        proj.slow_factor = 0.5
    elif source == "demon_strike":
        # fire a DemonStrike via game helper and pick the generated projectile
        g.weapon_levels["DemonStrike"] = 1
        g.fire_demon_strike(0, -500)
        # find newest DemonStrike projectile
        projs = [
            p for p in g.projectiles if getattr(p, "weapon_type", None) == "DemonStrike"
        ]
        assert projs, "DemonStrike projectile not created"
        proj = projs[-1]
    else:
        pytest.skip("unknown source: %s" % source)

    # place projectile on top of dict-enemy so collision is deterministic
    try:
        proj.x = e["x"]
        proj.y = e["y"]
        proj.rect.center = (int(e["x"]), int(e["y"]))
    except Exception:
        pass

    # add projectile to game (if not already added by the source)
    try:
        if proj not in g.projectiles:
            g.projectiles.add(proj)
    except Exception:
        if proj not in g.projectiles:
            g.projectiles.append(proj)

    # run collision handling
    g.handle_collisions()

    # check dict-enemy received the expected status
    if expected_effect == "burn":
        assert e.get("burn_timer", 0) > 0
        assert e.get("burn_damage_per_second", 0) > 0
    elif expected_effect == "slow":
        assert e.get("slow_timer", 0) > 0
        assert e.get("slow_factor", 1.0) != 1.0

    # Now test boss was affected by the same projectile as well
    try:
        proj.rect.center = (int(getattr(boss, "x", 0)), int(getattr(boss, "y", 0)))
    except Exception:
        pass

    # Re-add projectile if necessary (some sources remove on first hit)
    try:
        if proj not in g.projectiles:
            g.projectiles.add(proj)
    except Exception:
        if proj not in g.projectiles:
            g.projectiles.append(proj)

    g.handle_collisions()

    if expected_effect == "burn":
        assert getattr(boss, "burn_timer", 0) > 0
        assert getattr(boss, "burn_damage_per_second", 0) > 0
    elif expected_effect == "slow":
        assert getattr(boss, "slow_timer", 0) > 0
        assert getattr(boss, "slow_factor", 1.0) != 1.0
