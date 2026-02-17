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

    # prepare an Enemy instance (object-style)
    from src.entities.enemy import Enemy

    e = Enemy(320, 520, enemy_type="normal", health=30)
    e.health = 30
    e.max_health = 30
    e.speed = 75
    e.radius = 12
    e.damage = 5
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
        proj.x = e.x
        proj.y = e.y
        proj.rect.center = (int(e.x), int(e.y))
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

    # check enemy received the expected status
    if expected_effect == "burn":
        assert getattr(e, "burn_timer", 0) > 0
        assert getattr(e, "burn_damage_per_second", 0) > 0
    elif expected_effect == "slow":
        assert getattr(e, "slow_timer", 0) > 0
        assert getattr(e, "slow_factor", 1.0) != 1.0

    # Now test boss was affected by the same projectile as well
    # Use a fresh projectile placed directly on the boss to ensure boss receives the effect
    from src.projectile import Projectile

    proj2 = Projectile(
        int(getattr(boss, "x", 0)),
        int(getattr(boss, "y", 0)),
        0,
        0,
        damage=getattr(proj, "damage", 0),
        radius=6,
    )
    proj2.effect = getattr(proj, "effect", None)
    proj2.slow_duration = getattr(proj, "slow_duration", 120)
    proj2.slow_factor = getattr(proj, "slow_factor", 0.5)
    try:
        if proj2 not in g.projectiles:
            g.projectiles.add(proj2)
    except Exception:
        if proj2 not in g.projectiles:
            g.projectiles.append(proj2)

    g.handle_collisions()

    if expected_effect == "burn":
        assert getattr(boss, "burn_timer", 0) > 0
        assert getattr(boss, "burn_damage_per_second", 0) > 0
    elif expected_effect == "slow":
        assert getattr(boss, "slow_timer", 0) > 0
        assert getattr(boss, "slow_factor", 1.0) != 1.0
