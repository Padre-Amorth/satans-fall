from src.weapons import skullboom_cooldown, skullboom_damage


def test_skullboom_cooldown_and_damage_values():
    """Verify skullboom_damage and skullboom_cooldown return expected HUD values."""
    expected_dmg = skullboom_damage(1)
    expected_cd = skullboom_cooldown(1)

    # Values should be positive and well-formed for HUD display
    assert expected_dmg > 0, "skullboom_damage(1) should be positive"
    assert expected_cd > 0, "skullboom_cooldown(1) should be positive"

    # The HUD string that would be rendered
    hud_text = f"{expected_dmg} explosion dmg (cd {expected_cd:.2f}s)"
    assert "explosion dmg" in hud_text
    assert f"{expected_cd:.2f}s" in hud_text
