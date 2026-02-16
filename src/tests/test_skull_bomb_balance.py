from src.weapons import skull_bomb_cooldown, skull_bomb_damage


def test_skull_bomb_cooldown_lv1_lv6():
    assert abs(skull_bomb_cooldown(1) - 1.8) < 1e-6
    assert abs(skull_bomb_cooldown(6) - 1.0) < 1e-6


def test_skull_bomb_damage_progression():
    # Exact values requested: Lv1 = 30, Lv6 = 50
    expected = {1: 30, 2: 34, 3: 38, 4: 42, 5: 46, 6: 50}
    for lvl, dmg in expected.items():
        assert skull_bomb_damage(lvl) == dmg, f"Lv{lvl} damage should be {dmg}"
