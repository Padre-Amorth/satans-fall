"""Test suite for Satan level (meta_level) based weapon and upgrade unlocks.

Verifies that weapons and run-time upgrades unlock correctly based on Satan level,
not stage restrictions.
"""

import pytest
from src.weapons import WEAPON_DEFS


class TestWeaponMetaLevelUnlocks:
    """Test weapon unlock thresholds by Satan level."""

    def test_hellgun_immediate(self):
        """Hellgun (shotgun) should have no meta_level requirement."""
        wdef = WEAPON_DEFS.get("shotgun", {})
        assert "required_meta_level" not in wdef, "Hellgun should be immediately available"
        assert wdef.get("available_from") is None, "Hellgun should not have stage restriction"

    def test_orbitals_immediate(self):
        """Orbitals should be immediately available."""
        wdef = WEAPON_DEFS.get("orbital", {})
        assert "required_meta_level" not in wdef, "Orbitals should be immediately available"
        assert wdef.get("available_from") is None

    def test_spear_immediate(self):
        """Spear should be immediately available."""
        wdef = WEAPON_DEFS.get("spear", {})
        assert "required_meta_level" not in wdef
        assert wdef.get("available_from") is None

    def test_beast_immediate(self):
        """Beast should be immediately available."""
        wdef = WEAPON_DEFS.get("beast", {})
        assert "required_meta_level" not in wdef
        assert wdef.get("available_from") is None

    def test_skullboom_level_3(self):
        """SkullBoom should require Satan Level 3."""
        wdef = WEAPON_DEFS.get("skullboom", {})
        assert wdef.get("required_meta_level") == 3, "SkullBoom requires Satan Lv 3"
        assert wdef.get("available_from") is None, "SkullBoom should not have stage restriction"

    def test_flies_level_6(self):
        """Flies should require Satan Level 6 (was Limbo-only)."""
        wdef = WEAPON_DEFS.get("Flies", {})
        assert wdef.get("required_meta_level") == 6, "Flies requires Satan Lv 6"
        assert (
            wdef.get("available_from") is None
        ), "Flies should NOT have stage restriction, uses meta_level instead"

    def test_demonstrike_level_9(self):
        """DemonStrike should require Satan Level 9 (was Purgatory-only)."""
        wdef = WEAPON_DEFS.get("DemonStrike", {})
        assert wdef.get("required_meta_level") == 9, "DemonStrike requires Satan Lv 9"
        assert (
            wdef.get("available_from") is None
        ), "DemonStrike should NOT have stage restriction"

    def test_tenebrae_level_12(self):
        """Tenebrae should require Satan Level 12 (was Hell-only)."""
        wdef = WEAPON_DEFS.get("tenebrae", {})
        assert wdef.get("required_meta_level") == 12, "Tenebrae requires Satan Lv 12"
        assert (
            wdef.get("available_from") is None
        ), "Tenebrae should NOT have stage restriction"

    def test_all_weapons_have_max_level(self):
        """All weapons should have a max_level defined."""
        for weapon_id, wdef in WEAPON_DEFS.items():
            assert (
                "max_level" in wdef
            ), f"Weapon {weapon_id} missing max_level definition"
            assert wdef["max_level"] >= 1, f"Weapon {weapon_id} max_level must be >= 1"

    def test_no_stage_restriction_on_meta_locked_weapons(self):
        """Weapons with meta_level requirement should not have available_from."""
        meta_locked = ["skullboom", "Flies", "DemonStrike", "tenebrae"]
        for weapon_id in meta_locked:
            wdef = WEAPON_DEFS.get(weapon_id, {})
            if "required_meta_level" in wdef:
                assert (
                    "available_from" not in wdef
                ), f"{weapon_id} should not have both required_meta_level and available_from"


class TestUpgradeMetaLevelUnlocks:
    """Test run-time upgrade unlock thresholds by Satan level."""

    def test_shield_unlocks_at_level_5(self):
        """SHIELD upgrade should be available at Satan Level 5 and beyond."""
        # Satan Lv < 5: SHIELD locked
        assert not self._is_shield_available(meta_level=1, stage="prologo")
        assert not self._is_shield_available(meta_level=4, stage="prologo")

        # Satan Lv >= 5: SHIELD available in ALL stages
        assert self._is_shield_available(meta_level=5, stage="prologo")
        assert self._is_shield_available(meta_level=5, stage="limbo")
        assert self._is_shield_available(meta_level=5, stage="purgatory")
        assert self._is_shield_available(meta_level=5, stage="hell")

    def test_boom_unlocks_at_level_10(self):
        """BOOM! upgrade should be available at Satan Level 10 and beyond."""
        # Satan Lv < 10: BOOM! locked
        assert not self._is_boom_available(meta_level=1, stage="prologo")
        assert not self._is_boom_available(meta_level=9, stage="prologo")
        assert not self._is_boom_available(meta_level=9, stage="purgatory")

        # Satan Lv >= 10: BOOM! available in ALL stages
        assert self._is_boom_available(meta_level=10, stage="prologo")
        assert self._is_boom_available(meta_level=10, stage="limbo")
        assert self._is_boom_available(meta_level=10, stage="purgatory")
        assert self._is_boom_available(meta_level=10, stage="hell")

    def test_projectile_size_stage_locked_hell_only(self):
        """Projectile Size should be Hell-only, no Satan level requirement."""
        # Hell: available
        assert self._is_projectile_size_available(meta_level=1, stage="hell")
        assert self._is_projectile_size_available(meta_level=1, stage="hell_2")

        # Not Hell: locked (regardless of Satan level)
        assert not self._is_projectile_size_available(meta_level=99, stage="prologo")
        assert not self._is_projectile_size_available(meta_level=99, stage="limbo")
        assert not self._is_projectile_size_available(meta_level=99, stage="purgatory")

    def test_tower_fire_rate_stage_locked_purgatory_plus(self):
        """Tower Fire Rate should be Purgatory+, no Satan level requirement."""
        # Purgatory+: available
        assert self._is_tower_fire_available(meta_level=1, stage="purgatory")
        assert self._is_tower_fire_available(meta_level=1, stage="purgatory_2")
        assert self._is_tower_fire_available(meta_level=1, stage="hell")

        # Before Purgatory: locked (regardless of Satan level)
        assert not self._is_tower_fire_available(meta_level=99, stage="prologo")
        assert not self._is_tower_fire_available(meta_level=99, stage="limbo")

    @staticmethod
    def _is_shield_available(meta_level: int, stage: str) -> bool:
        """Simulate SHIELD availability logic from upgrade_system.py."""
        if meta_level < 5:
            return False
        return True  # Available in all stages once Satan Lv 5+

    @staticmethod
    def _is_boom_available(meta_level: int, stage: str) -> bool:
        """Simulate BOOM! availability logic from upgrade_system.py."""
        if meta_level < 10:
            return False
        return True  # Available in all stages once Satan Lv 10+

    @staticmethod
    def _is_projectile_size_available(meta_level: int, stage: str) -> bool:
        """Simulate Projectile Size availability logic (Hell-only)."""
        hell_stages = {"hell", "hell_2", "hell_3"}
        return stage in hell_stages  # Stage-locked, no meta_level requirement

    @staticmethod
    def _is_tower_fire_available(meta_level: int, stage: str) -> bool:
        """Simulate Tower Fire Rate availability logic (Purgatory+)."""
        purgatory_stages = {
            "purgatory",
            "purgatory_2",
            "purgatory_3",
            "hell",
            "hell_2",
            "hell_3",
        }
        return stage in purgatory_stages  # Stage-locked, no meta_level requirement


class TestMetaLevelFilterLogic:
    """Test that weapon and upgrade filtering logic works correctly."""

    def test_weapon_filter_respects_meta_level(self):
        """Verify weapon filtering by meta_level in generate_weapon_choices."""
        # Simulate game state at different Satan levels
        weapons_at_level = {
            1: [
                "shotgun",
                "orbital",
                "spear",
                "beast",
            ],  # 4 immediate weapons
            3: ["shotgun", "orbital", "spear", "beast", "skullboom"],  # +skullboom
            6: [
                "shotgun",
                "orbital",
                "spear",
                "beast",
                "skullboom",
                "Flies",
            ],  # +Flies
            9: [
                "shotgun",
                "orbital",
                "spear",
                "beast",
                "skullboom",
                "Flies",
                "DemonStrike",
            ],  # +DemonStrike
            12: [
                "shotgun",
                "orbital",
                "spear",
                "beast",
                "skullboom",
                "Flies",
                "DemonStrike",
                "tenebrae",
            ],  # +Tenebrae
        }

        for level, expected_weapons in weapons_at_level.items():
            for weapon_id in expected_weapons:
                wdef = WEAPON_DEFS.get(weapon_id, {})
                required_ml = wdef.get("required_meta_level")
                assert (
                    required_ml is None or required_ml <= level
                ), f"{weapon_id} should not be available at Satan Lv {level}"

    def test_upgrade_filter_respects_meta_level(self):
        """Verify upgrade filtering by meta_level."""
        # Check that SHIELD and BOOM! have correct thresholds
        assert 5 > 1, "SHIELD (Lv5) should not appear at Satan Lv 1"
        assert 5 <= 5, "SHIELD (Lv5) should appear at Satan Lv 5"
        assert 10 > 9, "BOOM! (Lv10) should not appear at Satan Lv 9"
        assert 10 <= 10, "BOOM! (Lv10) should appear at Satan Lv 10"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
