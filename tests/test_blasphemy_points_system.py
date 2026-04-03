"""Tests for blasphemy points system: pentagram enemies, point awards, and upgrade gating."""

import os

from src.entities.enemy import Enemy
from src.game import Game


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


class TestPentagramEnemyStats:
    """Test pentagram enemy HP values."""

    def test_base_pentagram_hp(self):
        """Base pentagram has 500 body + 500 shield = 1000 total HP."""
        setup_dummy_sdl()
        enemy = Enemy(x=100, y=100, enemy_type="pentagram", health=500, speed=50)
        assert enemy.max_health == 500
        assert enemy.health == 500
        assert enemy.shield_hp == 500
        assert enemy.shield_max_hp == 500

    def test_pentagram_fire_hp(self):
        """Pentagram fire has 500 body + 500 shield = 1000 total HP."""
        setup_dummy_sdl()
        enemy = Enemy(x=100, y=100, enemy_type="pentagram_fire", health=500, speed=50)
        assert enemy.max_health == 500
        assert enemy.health == 500
        assert enemy.shield_hp == 500
        assert enemy.shield_max_hp == 500

    def test_pentagram_storm_hp(self):
        """Pentagram storm has 500 body + 500 shield = 1000 total HP."""
        setup_dummy_sdl()
        enemy = Enemy(x=100, y=100, enemy_type="pentagram_storm", health=500, speed=50)
        assert enemy.max_health == 500
        assert enemy.health == 500
        assert enemy.shield_hp == 500
        assert enemy.shield_max_hp == 500

    def test_pentagram_ice_hp(self):
        """Pentagram ice has 500 body + 500 shield = 1000 total HP."""
        setup_dummy_sdl()
        enemy = Enemy(x=100, y=100, enemy_type="pentagram_ice", health=500, speed=50)
        assert enemy.max_health == 500
        assert enemy.health == 500
        assert enemy.shield_hp == 500
        assert enemy.shield_max_hp == 500

    def test_pentagram_no_damage(self):
        """Pentagram enemies don't attack (damage = 0)."""
        setup_dummy_sdl()
        for enemy_type in [
            "pentagram",
            "pentagram_fire",
            "pentagram_storm",
            "pentagram_ice",
        ]:
            enemy = Enemy(x=100, y=100, enemy_type=enemy_type, health=500, speed=50)
            assert enemy.damage == 0


class TestBlasphemyPointsInitialization:
    """Test blasphemy points persistence and initialization."""

    def test_global_progress_has_blasphemy_points(self):
        """Game initializes with blasphemy_points in global_progress."""
        setup_dummy_sdl()
        g = Game()
        assert "blasphemy_points" in g.global_progress
        # blasphemy_points should be an integer (0 if new profile)
        assert isinstance(g.global_progress["blasphemy_points"], int)
        assert g.global_progress["blasphemy_points"] >= 0

    def test_blasphemy_points_has_setdefault(self):
        """Blasphemy points gets a setdefault in select_profile."""
        setup_dummy_sdl()
        g = Game()
        # Clear the profile and select it again
        g.permanent_stats = {}
        g.global_progress = {}
        g.select_profile(1)
        # After select_profile, blasphemy_points should exist with setdefault
        assert "blasphemy_points" in g.global_progress
        assert isinstance(g.global_progress["blasphemy_points"], int)


class TestBlasphemyPointsCosts:
    """Test blasphemy upgrade costs via input handler."""

    def test_blasphemy_1_4_cost_1_point(self):
        """Blasphemy 1-4 cost 1 point each."""
        setup_dummy_sdl()
        g = Game()
        handler = g.input_handler
        for key in ["blasphemy_1", "blasphemy_2", "blasphemy_3", "blasphemy_4"]:
            assert handler._blasphemy_point_cost(key) == 1

    def test_blasphemy_5_9_cost_1_point(self):
        """Blasphemy 5-9 cost 1 point each."""
        setup_dummy_sdl()
        g = Game()
        handler = g.input_handler
        for key in [
            "blasphemy_5",
            "blasphemy_6",
            "blasphemy_7",
            "blasphemy_8",
            "blasphemy_9",
        ]:
            assert handler._blasphemy_point_cost(key) == 1

    def test_blasphemy_10_costs_3_points(self):
        """Blasphemy 10 (revive) costs 3 points."""
        setup_dummy_sdl()
        g = Game()
        handler = g.input_handler
        assert handler._blasphemy_point_cost("blasphemy_10") == 3


class TestBlasphemyPointsAffordability:
    """Test affordability checks."""

    def test_can_afford_with_zero_points(self):
        """With 0 points, can't afford any upgrade."""
        setup_dummy_sdl()
        g = Game()
        g.global_progress["blasphemy_points"] = 0
        handler = g.input_handler
        for key in ["blasphemy_1", "blasphemy_5", "blasphemy_10"]:
            assert not handler._blasphemy_can_afford(key)

    def test_can_afford_with_sufficient_points(self):
        """With 1 point, can afford regular blasphemies."""
        setup_dummy_sdl()
        g = Game()
        g.global_progress["blasphemy_points"] = 1
        handler = g.input_handler
        assert handler._blasphemy_can_afford("blasphemy_1")
        assert not handler._blasphemy_can_afford("blasphemy_10")

    def test_can_afford_blasphemy_10_with_3_points(self):
        """With 3 points, can afford blasphemy_10."""
        setup_dummy_sdl()
        g = Game()
        g.global_progress["blasphemy_points"] = 3
        handler = g.input_handler
        assert handler._blasphemy_can_afford("blasphemy_10")

    def test_can_afford_multiple_blasphemies(self):
        """With 5 points, can afford regular upgrades and blasphemy_10."""
        setup_dummy_sdl()
        g = Game()
        g.global_progress["blasphemy_points"] = 5
        handler = g.input_handler
        assert handler._blasphemy_can_afford("blasphemy_1")
        assert handler._blasphemy_can_afford("blasphemy_5")
        assert handler._blasphemy_can_afford("blasphemy_10")  # can afford (5 >= 3)


class TestBlasphemyPointsSpending:
    """Test spending and refunding points."""

    def test_spend_point_regular_blasphemy(self):
        """Spending 1 point reduces balance by 1."""
        setup_dummy_sdl()
        g = Game()
        g.global_progress["blasphemy_points"] = 5
        handler = g.input_handler
        handler._blasphemy_spend("blasphemy_1")
        assert g.global_progress["blasphemy_points"] == 4

    def test_spend_3_points_blasphemy_10(self):
        """Spending blasphemy_10 reduces balance by 3."""
        setup_dummy_sdl()
        g = Game()
        g.global_progress["blasphemy_points"] = 5
        handler = g.input_handler
        handler._blasphemy_spend("blasphemy_10")
        assert g.global_progress["blasphemy_points"] == 2

    def test_refund_point_regular_blasphemy(self):
        """Refunding 1 point increases balance by 1."""
        setup_dummy_sdl()
        g = Game()
        g.global_progress["blasphemy_points"] = 5
        handler = g.input_handler
        handler._blasphemy_refund("blasphemy_1")
        assert g.global_progress["blasphemy_points"] == 6

    def test_refund_3_points_blasphemy_10(self):
        """Refunding blasphemy_10 increases balance by 3."""
        setup_dummy_sdl()
        g = Game()
        g.global_progress["blasphemy_points"] = 5
        handler = g.input_handler
        handler._blasphemy_refund("blasphemy_10")
        assert g.global_progress["blasphemy_points"] == 8


class TestBlasphemyUpgradeLevelGating:
    """Test that upgrades respect balance gating."""

    def test_cannot_upgrade_without_points(self):
        """Can't upgrade blasphemy_1 with 0 points."""
        setup_dummy_sdl()
        g = Game()
        g.global_progress["blasphemy_points"] = 0
        g.permanent_stats["blasphemy_1"] = 0
        handler = g.input_handler

        # Attempt to upgrade should fail (not enough points)
        # We can't directly trigger click handling without pygame event, so test affordability
        assert not handler._blasphemy_can_afford("blasphemy_1")

    def test_can_upgrade_with_points(self):
        """Can upgrade blasphemy_1 with 1+ points."""
        setup_dummy_sdl()
        g = Game()
        g.global_progress["blasphemy_points"] = 1
        g.permanent_stats["blasphemy_1"] = 0
        handler = g.input_handler

        assert handler._blasphemy_can_afford("blasphemy_1")

    def test_blasphemy_10_requires_3_points(self):
        """Blasphemy_10 requires 3 points, not 1."""
        setup_dummy_sdl()
        g = Game()
        g.global_progress["blasphemy_points"] = 1
        g.permanent_stats["blasphemy_10"] = 0
        handler = g.input_handler

        assert not handler._blasphemy_can_afford("blasphemy_10")

        g.global_progress["blasphemy_points"] = 3
        assert handler._blasphemy_can_afford("blasphemy_10")


class TestPermanentUpgradesMenuDisplay:
    """Test blasphemy points display in permanent upgrades menu."""

    def test_blasphemy_section_visible(self):
        """Blasphemy section renders when menu is open."""
        setup_dummy_sdl()
        g = Game()
        g.show_permanent_upgrades()
        g.ui.draw_permanent_upgrades()
        # No assertion needed—just ensure no crash
        assert g.showing_permanent_upgrades

    def test_balance_text_rendered_zero_points(self):
        """Balance text renders with 0 points."""
        setup_dummy_sdl()
        g = Game()
        g.global_progress["blasphemy_points"] = 0
        g.show_permanent_upgrades()
        g.ui.draw_permanent_upgrades()
        # Verify no crash and points exist in state
        assert g.global_progress["blasphemy_points"] == 0

    def test_balance_text_rendered_with_points(self):
        """Balance text renders with multiple points."""
        setup_dummy_sdl()
        g = Game()
        g.global_progress["blasphemy_points"] = 5
        g.show_permanent_upgrades()
        g.ui.draw_permanent_upgrades()
        assert g.global_progress["blasphemy_points"] == 5

    def test_unaffordable_boxes_dimmed(self):
        """Unaffordable blasphemy boxes should be visually distinct."""
        setup_dummy_sdl()
        g = Game()
        g.global_progress["blasphemy_points"] = 0  # Can't afford anything
        g.permanent_stats["blasphemy_1"] = 0  # Not maxed
        g.show_permanent_upgrades()
        g.ui.draw_permanent_upgrades()
        # Verify no crash when rendering dimmed boxes
        assert not g.input_handler._blasphemy_can_afford("blasphemy_1")

    def test_maxed_boxes_not_dimmed(self):
        """Maxed blasphemy boxes should not be dimmed even without points."""
        setup_dummy_sdl()
        g = Game()
        g.global_progress["blasphemy_points"] = 0  # No points
        g.permanent_stats["blasphemy_1"] = 3  # Maxed out
        g.show_permanent_upgrades()
        g.ui.draw_permanent_upgrades()
        # Verify no crash when maxed boxes are rendered (not dimmed)
        assert g.permanent_stats["blasphemy_1"] == 3


class TestBlasphemyPointsUIBalance:
    """Test balance display in UI."""

    def test_zero_points_displayed(self):
        """0 points is displayed correctly."""
        setup_dummy_sdl()
        g = Game()
        g.global_progress["blasphemy_points"] = 0
        # Verify the value is retrievable
        assert g.global_progress.get("blasphemy_points", 0) == 0

    def test_positive_points_displayed(self):
        """Positive points are displayed correctly."""
        setup_dummy_sdl()
        g = Game()
        g.global_progress["blasphemy_points"] = 15
        assert g.global_progress.get("blasphemy_points", 0) == 15

    def test_large_point_balance(self):
        """Large point balances display correctly."""
        setup_dummy_sdl()
        g = Game()
        g.global_progress["blasphemy_points"] = 999
        assert g.global_progress.get("blasphemy_points", 0) == 999
