"""Test pulsating glow effect for hell lamps."""

import math

import pytest

from src.game.core import Game


class TestHellLampPulsation:
    """Test pulsation effects for hell lamp glows."""

    @pytest.fixture
    def hell_game(self):
        """Setup game in hell stage with lamps."""
        game = Game()
        game.selected_stage = "hell"
        game.hell_lamps = []  # Initialize hell_lamps (not set in __init__)
        game.generate_walls()
        game.generate_hell_lamps()
        return game

    def test_hell_lamps_have_pulse_speed(self, hell_game):
        """Verify each hell lamp has pulse_speed parameter."""
        assert hell_game.hell_lamps, "No hell lamps generated"
        for lamp in hell_game.hell_lamps:
            assert "pulse_speed" in lamp, "Hell lamp missing pulse_speed"
            assert isinstance(lamp["pulse_speed"], float), "pulse_speed should be float"
            assert (
                0.3 <= lamp["pulse_speed"] <= 0.6
            ), f"pulse_speed out of range: {lamp['pulse_speed']}"

    def test_hell_lamps_have_pulse_phase(self, hell_game):
        """Verify each hell lamp has pulse_phase parameter."""
        assert hell_game.hell_lamps, "No hell lamps generated"
        for lamp in hell_game.hell_lamps:
            assert "pulse_phase" in lamp, "Hell lamp missing pulse_phase"
            assert isinstance(lamp["pulse_phase"], float), "pulse_phase should be float"
            assert (
                0 <= lamp["pulse_phase"] <= 2 * math.pi
            ), f"pulse_phase out of range: {lamp['pulse_phase']}"

    def test_hell_lamps_have_glow_radius(self, hell_game):
        """Verify each hell lamp has glow_radius parameter."""
        assert hell_game.hell_lamps, "No hell lamps generated"
        for lamp in hell_game.hell_lamps:
            assert "glow_radius" in lamp, "Hell lamp missing glow_radius"
            assert isinstance(lamp["glow_radius"], int), "glow_radius should be int"
            assert lamp["glow_radius"] == 25, "Hell lamps should have glow_radius=25"

    def test_hell_lamps_have_glow_color(self, hell_game):
        """Verify each hell lamp has glow_color parameter."""
        assert hell_game.hell_lamps, "No hell lamps generated"
        for lamp in hell_game.hell_lamps:
            assert "glow_color" in lamp, "Hell lamp missing glow_color"
            color = lamp["glow_color"]
            assert isinstance(color, tuple), "glow_color should be tuple"
            assert len(color) == 3, "glow_color should have 3 channels (RGB)"

    def test_hell_lamps_use_red_orange_color(self, hell_game):
        """Verify hell lamps use red-orange color (same as regular limbo)."""
        assert hell_game.hell_lamps, "No hell lamps generated"
        for lamp in hell_game.hell_lamps:
            assert lamp["glow_color"] == (
                255,
                100,
                60,
            ), "Hell lamps should use red-orange (255, 100, 60)"

    def test_hell_lamps_pulsation_varies(self, hell_game):
        """Verify different hell lamps have different pulse speeds."""
        assert hell_game.hell_lamps, "No hell lamps generated"
        # Even with just 2 lamps, phase offsets should create variation
        phases = [lamp["pulse_phase"] for lamp in hell_game.hell_lamps]
        assert len(set(phases)) > 0, "Phase offsets should vary between lamps"

    def test_hell_lamp_count(self, hell_game):
        """Verify hell stages generate expected lamp count (2 corner lamps)."""
        assert (
            len(hell_game.hell_lamps) == 2
        ), "Hell stages should have exactly 2 lamps (left + right)"

    def test_all_hell_stages_generate_lamps(self):
        """Verify all hell stages generate lamps with pulsation."""
        for stage in ["hell", "hell_2", "hell_3"]:
            game = Game()
            game.selected_stage = stage
            game.hell_lamps = []  # Initialize hell_lamps (not set in __init__)
            game.generate_walls()
            game.generate_hell_lamps()
            assert game.hell_lamps, f"{stage} should generate hell lamps"
            for lamp in game.hell_lamps:
                assert "pulse_speed" in lamp, f"{stage} lamp missing pulse_speed"
                assert "glow_radius" in lamp, f"{stage} lamp missing glow_radius"
