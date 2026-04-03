"""Test pulsating glow effect for prologo torches."""

import math

import pytest

from src.game.core import Game


class TestPrologoTorchPulsation:
    """Test pulsation effects for prologo torch glows."""

    @pytest.fixture
    def prologo_game(self):
        """Setup game in prologo stage with torches."""
        game = Game()
        game.selected_stage = "prologo"
        game.generate_walls()
        game.generate_prologo_torches()
        return game

    def test_prologo_torches_generated(self, prologo_game):
        """Verify torches are generated for prologo stage."""
        assert prologo_game.prologo_torches, "No torches generated for prologo"
        assert len(prologo_game.prologo_torches) > 0, "Expected at least one torch"

    def test_prologo_torches_have_pulse_speed(self, prologo_game):
        """Verify each torch has pulse_speed parameter."""
        assert prologo_game.prologo_torches, "No torches generated"
        for torch in prologo_game.prologo_torches:
            assert "pulse_speed" in torch, "Torch missing pulse_speed"
            assert isinstance(
                torch["pulse_speed"], float
            ), "pulse_speed should be float"
            assert (
                0.3 <= torch["pulse_speed"] <= 0.6
            ), f"pulse_speed out of range: {torch['pulse_speed']}"

    def test_prologo_torches_have_pulse_phase(self, prologo_game):
        """Verify each torch has pulse_phase parameter."""
        assert prologo_game.prologo_torches, "No torches generated"
        for torch in prologo_game.prologo_torches:
            assert "pulse_phase" in torch, "Torch missing pulse_phase"
            assert isinstance(
                torch["pulse_phase"], float
            ), "pulse_phase should be float"
            assert (
                0 <= torch["pulse_phase"] <= 2 * 3.14159
            ), f"pulse_phase out of range: {torch['pulse_phase']}"

    def test_prologo_torches_have_glow_radius(self, prologo_game):
        """Verify each torch has glow_radius parameter."""
        assert prologo_game.prologo_torches, "No torches generated"
        for torch in prologo_game.prologo_torches:
            assert "glow_radius" in torch, "Torch missing glow_radius"
            assert isinstance(torch["glow_radius"], int), "glow_radius should be int"
            assert (
                torch["glow_radius"] == 18
            ), "Prologo torches should have glow_radius=18"

    def test_prologo_torches_have_glow_color(self, prologo_game):
        """Verify each torch has glow_color parameter."""
        assert prologo_game.prologo_torches, "No torches generated"
        for torch in prologo_game.prologo_torches:
            assert "glow_color" in torch, "Torch missing glow_color"
            color = torch["glow_color"]
            assert isinstance(color, tuple), "glow_color should be tuple"
            assert len(color) == 3, "glow_color should have 3 channels (RGB)"

    def test_prologo_torches_use_red_orange_color(self, prologo_game):
        """Verify prologo torches use red-orange color."""
        assert prologo_game.prologo_torches, "No torches generated"
        for torch in prologo_game.prologo_torches:
            assert torch["glow_color"] == (
                255,
                100,
                60,
            ), "Prologo torches should use red-orange (255, 100, 60)"

    def test_prologo_torches_have_positions(self, prologo_game):
        """Verify each torch has x and y coordinates."""
        assert prologo_game.prologo_torches, "No torches generated"
        for torch in prologo_game.prologo_torches:
            assert "x" in torch, "Torch missing x coordinate"
            assert "y" in torch, "Torch missing y coordinate"
            assert isinstance(torch["x"], (int, float)), "x should be numeric"
            assert isinstance(torch["y"], (int, float)), "y should be numeric"

    def test_prologo_torches_have_sides(self, prologo_game):
        """Verify each torch has side designation (left/right)."""
        assert prologo_game.prologo_torches, "No torches generated"
        for torch in prologo_game.prologo_torches:
            assert "side" in torch, "Torch missing side designation"
            assert torch["side"] in ["left", "right"], f"Invalid side: {torch['side']}"

    def test_prologo_torch_count(self, prologo_game):
        """Verify prologo generates expected torch count (6 total: 3 positions × 2 sides)."""
        assert (
            len(prologo_game.prologo_torches) == 6
        ), "Prologo should have exactly 6 torches (3 positions × 2 sides)"

    def test_pulse_calculation_range(self):
        """Verify pulse value calculation stays within valid range for prologo."""
        min_pulse = 0.55
        for t in [0, 0.25, 0.5, 1.0, 2.0, 5.0]:
            pulse_speed = 0.4
            pulse_phase = 0.5
            pulse_value = min_pulse + (1.0 - min_pulse) * (
                0.5 + 0.5 * math.sin(2 * math.pi * pulse_speed * t + pulse_phase)
            )
            assert (
                min_pulse <= pulse_value <= 1.0
            ), f"Prologo torch pulse {pulse_value} out of range at t={t}"

    def test_glow_color_consistency(self, prologo_game):
        """Verify all torches use consistent glow color."""
        assert prologo_game.prologo_torches, "No torches generated"
        glow_colors = [torch["glow_color"] for torch in prologo_game.prologo_torches]
        assert (
            len(set(glow_colors)) == 1
        ), "Expected all torches to have same glow color"
        assert glow_colors[0] == (
            255,
            100,
            60,
        ), "Glow color should be red-orange (255, 100, 60)"
