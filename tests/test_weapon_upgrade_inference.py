from src.weapons import get_weapon_upgrade_description


def test_inferred_descriptions_for_common_weapons():
    # Ensure inference returns non-generic descriptions for underscored keys
    d1 = get_weapon_upgrade_description("flies", 2)
    assert not d1.startswith("Upgrade to level"), f"Bad fallback: {d1}"
    assert "projectile" in d1 or "projectiles" in d1

    d2 = get_weapon_upgrade_description("orbital", 2)
    assert not d2.startswith("Upgrade to level")
    assert "orbital" in d2 or "orbitals" in d2

    d3 = get_weapon_upgrade_description("shotgun", 4)
    assert not d3.startswith("Upgrade to level")
    assert "pellet" in d3

    d4 = get_weapon_upgrade_description("spear", 3)
    assert not d4.startswith("Upgrade to level")
    assert "damage" in d4
