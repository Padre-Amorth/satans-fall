from src.weapons import (  # kept identifier for SkullBoom
    skullboom_cooldown,
    skullboom_damage,
)


def test_skullboom_cooldown_lv1_lv6():
    assert abs(skullboom_cooldown(1) - 1.8) < 1e-6
    assert abs(skullboom_cooldown(6) - 1.0) < 1e-6


def test_skullboom_damage_progression():
    # Exact values requested: Lv1 = 30, Lv6 = 50
    expected = {1: 30, 2: 34, 3: 38, 4: 42, 5: 46, 6: 50}
    for lvl, dmg in expected.items():
        assert skullboom_damage(lvl) == dmg, f"Lv{lvl} damage should be {dmg}"
