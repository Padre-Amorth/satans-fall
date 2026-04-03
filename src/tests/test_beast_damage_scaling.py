from src.weapons import beast_damage


def test_beast_damage_levels_for_base_30():
    base = 30
    # Expected (linear interpolation 22 -> 50 over 7 levels, Lv7 = FINAL FORM)
    expected = {1: 22, 2: 26, 3: 31, 4: 36, 5: 40, 6: 45, 7: 50}
    for lvl, dmg in expected.items():
        assert beast_damage(lvl, base) == dmg, f"Lv{lvl} should be {dmg} dmg"


def test_beast_damage_level_zero_returns_base():
    assert beast_damage(0, 30) == 30


def test_beast_scales_with_player_damage():
    # If player's base damage is higher than default (30), Beast damage should scale
    # Note: scaling is applied to the remapped (float) damage and then cast to int
    base = 60  # double the default -> expect scaled (and truncated) values
    expected = {1: 44, 2: 53, 3: 62, 4: 72, 5: 81, 6: 90, 7: 100}
    for lvl, dmg in expected.items():
        assert beast_damage(lvl, base) == dmg, f"Scaled Lv{lvl} should be {dmg} dmg"
