from src.weapons import beast_damage


def test_beast_damage_levels_for_base_30():
    base = 30
    # Expected (linear interpolation 22 -> 45): 22,26,31,35,40,45
    expected = {1: 22, 2: 26, 3: 31, 4: 35, 5: 40, 6: 45}
    for lvl, dmg in expected.items():
        assert beast_damage(lvl, base) == dmg, f"Lv{lvl} should be {dmg} dmg"


def test_beast_damage_level_zero_returns_base():
    assert beast_damage(0, 30) == 30
