"""Test pulsating glow effect for limbo lamps."""

import math

import pytest

from src.game.core import Game


class TestLampPulsation:
    """Test pulsation effects for limbo lamp glows."""

    @pytest.fixture
    def limbo_game(self):
        """Setup game in limbo stage with lamps."""
        game = Game()
        game.selected_stage = "limbo"
        game.generate_walls()
        game.generate_limbo_lamps()
        return game

    @pytest.fixture
    def limbo_final_game(self):
        """Setup game in limbo_final stage with lamps."""
        game = Game()
        game.selected_stage = "limbo_final"
        game.generate_walls()
        game.generate_limbo_lamps()
        return game

    def test_lamps_have_pulse_speed(self, limbo_game):
        """Verify each lamp has pulse_speed parameter."""
        assert limbo_game.limbo_lamps, "No lamps generated"
        for lamp in limbo_game.limbo_lamps:
            assert "pulse_speed" in lamp, "Lamp missing pulse_speed"
            assert isinstance(lamp["pulse_speed"], float), "pulse_speed should be float"
            assert (
                0.3 <= lamp["pulse_speed"] <= 0.6
            ), f"pulse_speed out of range: {lamp['pulse_speed']}"

    def test_lamps_have_pulse_phase(self, limbo_game):
        """Verify each lamp has pulse_phase parameter."""
        assert limbo_game.limbo_lamps, "No lamps generated"
        for lamp in limbo_game.limbo_lamps:
            assert "pulse_phase" in lamp, "Lamp missing pulse_phase"
            assert isinstance(lamp["pulse_phase"], float), "pulse_phase should be float"
            assert (
                0 <= lamp["pulse_phase"] <= 2 * math.pi
            ), f"pulse_phase out of range: {lamp['pulse_phase']}"

    def test_lamps_have_glow_radius(self, limbo_game):
        """Verify each lamp has glow_radius parameter."""
        assert limbo_game.limbo_lamps, "No lamps generated"
        for lamp in limbo_game.limbo_lamps:
            assert "glow_radius" in lamp, "Lamp missing glow_radius"
            assert isinstance(lamp["glow_radius"], int), "glow_radius should be int"
            assert lamp["glow_radius"] > 0, "glow_radius should be positive"

    def test_lamps_have_glow_color(self, limbo_game):
        """Verify each lamp has glow_color parameter."""
        assert limbo_game.limbo_lamps, "No lamps generated"
        for lamp in limbo_game.limbo_lamps:
            assert "glow_color" in lamp, "Lamp missing glow_color"
            color = lamp["glow_color"]
            assert isinstance(color, tuple), "glow_color should be tuple"
            assert len(color) == 3, "glow_color should have 3 channels (RGB)"
            for channel in color:
                assert 0 <= channel <= 255, f"Color channel out of range: {channel}"

    def test_pulsation_values_vary(self, limbo_game):
        """Verify that different lamps have different pulse speeds (randomized)."""
        assert limbo_game.limbo_lamps, "No lamps generated"
        pulse_speeds = [lamp["pulse_speed"] for lamp in limbo_game.limbo_lamps]
        # With random generation, not all should be identical
        assert (
            len(set(pulse_speeds)) > 1
        ), "All lamps have same pulse_speed (expected variation)"

    def test_phase_offset_creates_stagger(self, limbo_game):
        """Verify phase offsets create staggered pulsation."""
        assert limbo_game.limbo_lamps, "No lamps generated"
        phases = [lamp["pulse_phase"] for lamp in limbo_game.limbo_lamps]
        # Phase should vary (creates visual stagger)
        assert len(set(phases)) > 1, "All lamps have same phase (expected variation)"

    def test_pulsation_limbo_final(self, limbo_final_game):
        """Verify limbo_final lamps also have pulsation parameters."""
        assert limbo_final_game.limbo_lamps, "No lamps generated for limbo_final"
        for lamp in limbo_final_game.limbo_lamps:
            assert "pulse_speed" in lamp, "limbo_final lamp missing pulse_speed"
            assert "pulse_phase" in lamp, "limbo_final lamp missing pulse_phase"
            assert "glow_radius" in lamp, "limbo_final lamp missing glow_radius"
            assert "glow_color" in lamp, "limbo_final lamp missing glow_color"

    def test_pulse_calculation_range(self):
        """Verify pulse value calculation stays within valid range."""
        # Regular limbo stages (0.70 to 1.0)
        for t in [0, 0.25, 0.5, 1.0, 2.0, 5.0]:
            pulse_speed = 0.5
            pulse_phase = 0.5
            pulse_value = 0.70 + 0.30 * (
                0.5 + 0.5 * math.sin(2 * math.pi * pulse_speed * t + pulse_phase)
            )
            assert (
                0.70 <= pulse_value <= 1.0
            ), f"Regular limbo pulse {pulse_value} out of range at t={t}"

        # limbo_final (0.70 to 1.0)
        for t in [0, 0.25, 0.5, 1.0, 2.0, 5.0]:
            pulse_speed = 0.5
            pulse_phase = 0.5
            pulse_value = 0.70 + 0.30 * (
                0.5 + 0.5 * math.sin(2 * math.pi * pulse_speed * t + pulse_phase)
            )
            assert (
                0.70 <= pulse_value <= 1.0
            ), f"limbo_final pulse {pulse_value} out of range at t={t}"

    def test_glow_color_consistency(self, limbo_game):
        """Verify all lamps use consistent glow color."""
        assert limbo_game.limbo_lamps, "No lamps generated"
        glow_colors = [lamp["glow_color"] for lamp in limbo_game.limbo_lamps]
        # All should be same red-orange color
        assert len(set(glow_colors)) == 1, "Expected all lamps to have same glow color"
        assert glow_colors[0] == (
            255,
            100,
            60,
        ), "Glow color should be red-orange (255, 100, 60)"
