from src.weapons import shotgun_pellet_damage


def test_shotgun_pellet_damage_scaling_with_base_30():
    base = 30
    # Expected linear mapping Lv1..Lv7 -> 20..30 (Lv7 = FINAL FORM)
    expected = {1: 20, 2: 21, 3: 23, 4: 25, 5: 26, 6: 28, 7: 30}
    for lvl, dmg in expected.items():
        assert shotgun_pellet_damage(lvl, base) == dmg, f"Lv{lvl} should be {dmg}"


def test_shotgun_pellet_damage_scales_with_player_damage():
    # If player damage doubles, pellet damage should scale proportionally
    base = 60
    expected = {1: 40, 6: 56, 7: 60}
    for lvl, dmg in expected.items():
        assert (
            shotgun_pellet_damage(lvl, base) == dmg
        ), f"Scaled Lv{lvl} should be {dmg}"


def test_shotgun_pellet_level_zero_fallback():
    # Level 0 should fallback to legacy multiplier behavior (approx base * 0.55)
    assert shotgun_pellet_damage(0, 30) == int(30 * 0.55)
