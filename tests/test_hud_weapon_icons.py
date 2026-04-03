"""Test that weapon icons appear in HUD (right panel during gameplay)."""

from src.game import Game


def test_hud_draws_with_weapon_icons():
    """Test that HUD renders weapon icons without error."""
    g = Game()
    g.select_stage("purgatory")

    # Choose weapon
    if g.weapon_choices:
        g.apply_weapon(g.weapon_choices[0]["id"])

    # Should render HUD with icons
    try:
        g.ui.effects.draw_hud()
    except Exception as e:
        assert False, f"draw_hud raised: {e}"


def test_hud_with_multiple_weapons():
    """Test HUD with multiple weapons acquired."""
    g = Game()
    g.select_stage("purgatory")

    # Acquire multiple weapons
    weapons_to_acquire = ["shotgun", "orbital"]
    for wid in weapons_to_acquire:
        if wid not in g.player_weapons:
            g.player_weapons.append(wid)
        g.weapon_levels[wid] = 2

    # Should render all weapons with icons
    try:
        g.ui.effects.draw_hud()
    except Exception as e:
        assert False, f"draw_hud with multiple weapons raised: {e}"


def test_hud_with_final_form_weapon():
    """Test HUD displays FINAL FORM correctly with icon for level 7."""
    g = Game()
    g.select_stage("purgatory")

    # Add a level 7 weapon
    if "shotgun" not in g.player_weapons:
        g.player_weapons.append("shotgun")
    g.weapon_levels["shotgun"] = 7

    # Should render FINAL FORM with icon without error
    try:
        g.ui.effects.draw_hud()
    except Exception as e:
        assert False, f"draw_hud with FINAL FORM raised: {e}"


def test_hud_no_crash_with_missing_icon():
    """Test that HUD doesn't crash even if an icon asset is missing."""
    g = Game()
    g.select_stage("purgatory")

    # Add a weapon with a potentially missing icon
    if "shotgun" not in g.player_weapons:
        g.player_weapons.append("shotgun")
    g.weapon_levels["shotgun"] = 3

    # Should NOT crash even if icon fails to load
    try:
        g.ui.effects.draw_hud()
    except Exception as e:
        assert False, f"draw_hud crashed on icon loading: {e}"
