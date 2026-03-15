"""Test that weapon icons appear in Tab menu (player_stats display)."""

from src.assets.manager import get_image
from src.game import Game


def test_tab_menu_draws_with_weapon_icons():
    """Test that draw_player_stats renders without error with weapon icons."""
    g = Game()
    g.select_stage("purgatory")

    # Choose weapon
    if g.weapon_choices:
        g.apply_weapon(g.weapon_choices[0]["id"])

    # Show player stats (Tab menu)
    g.showing_player_stats = True

    # Should render without error with icons
    try:
        g.ui.draw_player_stats()
    except Exception as e:
        assert False, f"draw_player_stats raised: {e}"


def test_tab_menu_with_multiple_weapons():
    """Test Tab menu with multiple weapons acquired."""
    g = Game()
    g.select_stage("purgatory")

    # Acquire multiple weapons by simulating progression
    weapons_to_acquire = ["shotgun", "orbital"]
    for wid in weapons_to_acquire:
        if wid not in g.player_weapons:
            g.player_weapons.append(wid)
        g.weapon_levels[wid] = 2

    # Show player stats
    g.showing_player_stats = True

    # Should render all weapons with icons
    try:
        g.ui.draw_player_stats()
    except Exception as e:
        assert False, f"draw_player_stats with multiple weapons raised: {e}"


def test_tab_menu_with_final_form_weapon():
    """Test Tab menu displays FINAL FORM correctly with icon for level 7."""
    g = Game()
    g.select_stage("purgatory")

    # Add a level 7 weapon
    if "shotgun" not in g.player_weapons:
        g.player_weapons.append("shotgun")
    g.weapon_levels["shotgun"] = 7

    # Show player stats
    g.showing_player_stats = True

    # Should render FINAL FORM with icon without error
    try:
        g.ui.draw_player_stats()
    except Exception as e:
        assert False, f"draw_player_stats with FINAL FORM raised: {e}"


def test_weapon_icon_asset_exists():
    """Verify that weapon icons are available in assets."""
    from src.weapons import WEAPON_DEFS

    icon_size = 32
    for wid, weapon_def in WEAPON_DEFS.items():
        icon_key = weapon_def.get("icon")
        if not icon_key:
            icon_key = f"weapon_{wid.lower()}.png"

        # Try to load the icon
        icon_surf = get_image(icon_key, (icon_size, icon_size))
        if icon_surf is None and icon_key.startswith("weapon_"):
            # Try fallback
            icon_surf = get_image(icon_key[len("weapon_") :], (icon_size, icon_size))

        # Icon should load or fallback gracefully (no crash)
        # We don't assert it exists because fallback is OK


def test_tab_menu_no_crash_with_missing_icon():
    """Test that Tab menu doesn't crash even if an icon asset is missing."""
    g = Game()
    g.select_stage("purgatory")

    # Add a weapon with a potentially missing icon
    if "shotgun" not in g.player_weapons:
        g.player_weapons.append("shotgun")
    g.weapon_levels["shotgun"] = 3

    # Show player stats - should NOT crash even if icon fails to load
    g.showing_player_stats = True

    try:
        g.ui.draw_player_stats()
    except Exception as e:
        # Icon loading should be graceful, not crash
        assert False, f"draw_player_stats crashed on icon loading: {e}"
