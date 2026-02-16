from src.weapons import WEAPON_DEFS, get_weapon_upgrade_description


def test_all_weapons_have_explicit_upgrade_descriptions():
    """Ensure every weapon has explicit upgrade descriptions for every level up to max_level
    and that get_weapon_upgrade_description returns the exact configured description.
    """
    missing = []
    mismatches = []
    for wid, wdef in WEAPON_DEFS.items():
        max_level = wdef.get("max_level", 6)
        upgrades = wdef.get("upgrade_descriptions", {})
        for lvl in range(1, max_level + 1):
            if lvl not in upgrades:
                missing.append((wid, lvl))
            else:
                expected = upgrades[lvl]
                got = get_weapon_upgrade_description(wid, lvl)
                if got != expected:
                    mismatches.append((wid, lvl, expected, got))

    assert not missing, f"Missing upgrade descriptions for: {missing}"
    assert not mismatches, f"Descriptions mismatch for: {mismatches}"
