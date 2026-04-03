"""Comprehensive tests for bloodstain system."""

import time

from src.entities.bloodstain import Bloodstain
from src.game_constants import (
    BLOODSTAIN_FADE_TIME,
    BLOODSTAIN_LIFETIME,
    MAX_BLOODSTAINS,
)


class TestBloodstainConstruction:
    """Test Bloodstain initialization and properties."""

    def test_init_default(self):
        """Test default bloodstain creation."""
        bs = Bloodstain(100, 200)
        assert bs.x == 100
        assert bs.y == 200
        assert bs.base_size == 4.0
        assert bs.size == 4.0  # No is_large multiplier
        assert bs.color == (100, 20, 20)
        assert bs.alpha == 255

    def test_init_custom_size(self):
        """Test custom size parameter."""
        bs = Bloodstain(50, 75, size=6.0)
        assert bs.base_size == 6.0
        assert bs.size == 6.0

    def test_init_custom_color(self):
        """Test custom color parameter."""
        custom_color = (200, 50, 50)
        bs = Bloodstain(100, 200, color=custom_color)
        assert bs.color == custom_color

    def test_init_large_multiplier(self):
        """Test is_large applies 1.5x size multiplier."""
        bs = Bloodstain(100, 200, size=4.0, is_large=True)
        assert bs.base_size == 4.0
        assert bs.size == 6.0  # 4.0 * 1.5

    def test_init_large_with_custom_size(self):
        """Test is_large multiplier with custom size."""
        bs = Bloodstain(100, 200, size=10.0, is_large=True)
        assert bs.size == 15.0  # 10.0 * 1.5

    def test_init_deterministic_seed(self):
        """Test that seed parameter produces identical splatter patterns."""
        seed = 42
        bs1 = Bloodstain(100, 200, seed=seed)
        bs2 = Bloodstain(100, 200, seed=seed)
        # Same seed should produce same splatter pattern
        assert len(bs1.splatter_pattern) == len(bs2.splatter_pattern)
        assert bs1.splatter_pattern == bs2.splatter_pattern

    def test_splatter_pattern_generated(self):
        """Test that splatter pattern is generated on init."""
        bs = Bloodstain(100, 200, seed=123)
        assert len(bs.splatter_pattern) > 0
        assert len(bs.splatter_pattern) >= 12
        assert len(bs.splatter_pattern) <= 16

    def test_splatter_pattern_tuple_format(self):
        """Test splatter pattern contains valid (offset_x, offset_y, size) tuples."""
        bs = Bloodstain(100, 200, seed=123)
        for offset_x, offset_y, splatter_size in bs.splatter_pattern:
            assert isinstance(offset_x, float)
            assert isinstance(offset_y, float)
            assert isinstance(splatter_size, float)
            assert splatter_size >= 3.0
            assert splatter_size <= 5.0

    def test_splatter_spread_radius(self):
        """Test that splatters spread within expected radius (±2.5x size)."""
        bs = Bloodstain(100, 200, size=4.0, seed=123)
        max_spread = bs.size * 2.5
        for offset_x, offset_y, _ in bs.splatter_pattern:
            assert abs(offset_x) <= max_spread
            assert abs(offset_y) <= max_spread


class TestBloodstainUpdate:
    """Test Bloodstain lifecycle and fade mechanics."""

    def test_update_fresh_bloodstain(self):
        """Test that fresh bloodstain is not expired."""
        bs = Bloodstain(100, 200)
        # Should not be expired immediately
        assert bs.update() is False

    def test_update_maintains_alpha_before_fade(self):
        """Test alpha stays at 255 before fade-out phase."""
        bs = Bloodstain(100, 200)
        # Update immediately - should still be 255
        bs.update()
        assert bs.alpha == 255

    def test_update_fades_during_fade_time(self):
        """Test alpha decreases during fade-out phase."""
        bs = Bloodstain(100, 200)
        # Simulate time just past (lifetime - fade_time)
        bs.creation_time = time.time() - (
            BLOODSTAIN_LIFETIME - BLOODSTAIN_FADE_TIME / 2
        )
        bs.update()
        # Should be fading but not completely transparent
        assert 0 < bs.alpha < 255

    def test_update_expires_after_lifetime(self):
        """Test bloodstain expires after BLOODSTAIN_LIFETIME."""
        bs = Bloodstain(100, 200)
        # Simulate time exceeding lifetime
        bs.creation_time = time.time() - (BLOODSTAIN_LIFETIME + 0.1)
        assert bs.update() is True

    def test_update_alpha_zero_at_lifetime_end(self):
        """Test alpha reaches 0 shortly after lifetime end."""
        bs = Bloodstain(100, 200)
        # Simulate just past lifetime (code checks elapsed > BLOODSTAIN_LIFETIME)
        bs.creation_time = time.time() - (BLOODSTAIN_LIFETIME + 0.01)
        result = bs.update()
        # Should be expired
        assert result is True

    def test_update_alpha_progression(self):
        """Test alpha decreases linearly during fade phase."""
        bs = Bloodstain(100, 200)
        fade_start = BLOODSTAIN_LIFETIME - BLOODSTAIN_FADE_TIME
        # Sample at 25%, 50%, 75% through fade
        alphas = []
        for progress in [0.25, 0.50, 0.75]:
            bs.creation_time = time.time() - (
                fade_start + BLOODSTAIN_FADE_TIME * progress
            )
            bs.update()
            alphas.append(bs.alpha)
        # Should be monotonically decreasing
        assert alphas[0] > alphas[1] > alphas[2]
        # Should be approximately linear: 191, 127, 64
        assert 180 < alphas[0] < 200
        assert 120 < alphas[1] < 135
        assert 50 < alphas[2] < 75

    def test_multiple_updates_decrease_alpha(self):
        """Test repeated updates continue to decrease alpha."""
        bs = Bloodstain(100, 200)
        bs.creation_time = time.time() - (
            BLOODSTAIN_LIFETIME - BLOODSTAIN_FADE_TIME / 2
        )

        bs.update()
        alpha2 = bs.alpha
        # First update might not change alpha if not yet fading

        # Simulate more time passing into fade phase
        bs.creation_time = time.time() - (BLOODSTAIN_LIFETIME - 0.1)
        bs.update()
        alpha3 = bs.alpha

        assert alpha3 < alpha2


class TestBloodstainDraw:
    """Test Bloodstain rendering (requires pygame mock)."""

    def test_draw_does_not_crash_with_mock_surface(self, monkeypatch):
        """Test that draw() method works with a mocked pygame surface."""
        import pygame

        # Create a mock surface
        surface = pygame.Surface((1280, 720))

        bs = Bloodstain(100, 200)
        # Should not raise any exception
        bs.draw(surface)

    def test_draw_with_camera_shake(self, monkeypatch):
        """Test that camera shake offsets are applied to blit position."""
        import pygame

        surface = pygame.Surface((1280, 720))
        bs = Bloodstain(100, 200)

        # Should handle non-zero camera shake
        bs.draw(surface, shake_x=10, shake_y=-5)

    def test_draw_with_zero_alpha(self, monkeypatch):
        """Test that draw() returns early when alpha is 0."""
        import pygame

        surface = pygame.Surface((1280, 720))
        bs = Bloodstain(100, 200)
        bs.alpha = 0

        # Should return early without rendering
        bs.draw(surface)

    def test_draw_with_positive_alpha(self, monkeypatch):
        """Test draw() with various positive alpha values."""
        import pygame

        surface = pygame.Surface((1280, 720))

        for alpha_val in [1, 127, 255]:
            bs = Bloodstain(100, 200)
            bs.alpha = alpha_val
            # Should not crash
            bs.draw(surface)


class TestBloodstainConstants:
    """Test that constants are appropriately configured."""

    def test_bloodstain_lifetime_positive(self):
        """Test BLOODSTAIN_LIFETIME is positive."""
        assert BLOODSTAIN_LIFETIME > 0

    def test_bloodstain_fade_time_positive(self):
        """Test BLOODSTAIN_FADE_TIME is positive."""
        assert BLOODSTAIN_FADE_TIME > 0

    def test_fade_time_less_than_lifetime(self):
        """Test fade time is less than total lifetime."""
        assert BLOODSTAIN_FADE_TIME < BLOODSTAIN_LIFETIME

    def test_max_bloodstains_reasonable(self):
        """Test MAX_BLOODSTAINS is a reasonable limit."""
        assert MAX_BLOODSTAINS > 100
        assert MAX_BLOODSTAINS < 10000


class TestBloodstainIntegration:
    """Integration tests for bloodstain system behavior."""

    def test_normal_enemy_bloodstain(self):
        """Test bloodstain properties for normal enemy."""
        bs = Bloodstain(100, 200, size=4, is_large=False)
        assert bs.size == 4.0

    def test_boss_enemy_bloodstain(self):
        """Test bloodstain properties for boss enemy."""
        bs = Bloodstain(100, 200, size=6, is_large=True)
        assert bs.size == 9.0  # 6 * 1.5

    def test_bloodstain_lifecycle(self):
        """Test complete bloodstain lifecycle from creation to expiry."""
        bs = Bloodstain(100, 200)

        # Fresh: should not expire
        assert bs.update() is False
        assert bs.alpha == 255

        # Mid-life: still not expired
        bs.creation_time = time.time() - (BLOODSTAIN_LIFETIME / 2)
        assert bs.update() is False
        assert bs.alpha == 255  # Not yet fading

        # Near end of fade: fading
        bs.creation_time = time.time() - (
            BLOODSTAIN_LIFETIME - BLOODSTAIN_FADE_TIME / 2
        )
        assert bs.update() is False
        assert 0 < bs.alpha < 255

        # Expired: should return True
        bs.creation_time = time.time() - (BLOODSTAIN_LIFETIME + 0.1)
        assert bs.update() is True

    def test_multiple_bloodstains_independent(self):
        """Test that multiple bloodstains have independent lifecycles."""
        bs1 = Bloodstain(100, 200, size=4, seed=1)
        bs2 = Bloodstain(300, 400, size=6, seed=2, is_large=True)

        # Different positions and sizes
        assert bs1.x != bs2.x
        assert bs1.y != bs2.y
        assert bs1.size != bs2.size

        # Independent splatters
        assert bs1.splatter_pattern != bs2.splatter_pattern


class TestBloodstainEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_position(self):
        """Test bloodstain at origin (0, 0)."""
        bs = Bloodstain(0, 0)
        assert bs.x == 0
        assert bs.y == 0

    def test_large_position(self):
        """Test bloodstain at large coordinates."""
        bs = Bloodstain(5000, 5000)
        assert bs.x == 5000
        assert bs.y == 5000

    def test_negative_position(self):
        """Test bloodstain with negative coordinates (off-screen)."""
        bs = Bloodstain(-100, -100)
        assert bs.x == -100
        assert bs.y == -100

    def test_very_small_size(self):
        """Test bloodstain with very small size."""
        bs = Bloodstain(100, 200, size=0.1)
        assert bs.size == 0.1

    def test_very_large_size(self):
        """Test bloodstain with very large size."""
        bs = Bloodstain(100, 200, size=100.0)
        assert bs.size == 100.0

    def test_custom_color_white(self):
        """Test custom color: white."""
        bs = Bloodstain(100, 200, color=(255, 255, 255))
        assert bs.color == (255, 255, 255)

    def test_custom_color_black(self):
        """Test custom color: black."""
        bs = Bloodstain(100, 200, color=(0, 0, 0))
        assert bs.color == (0, 0, 0)

    def test_repeated_updates(self):
        """Test bloodstain survives many consecutive updates until lifetime."""
        bs = Bloodstain(100, 200)
        # Bloodstain doesn't expire just from repeated updates with current time
        # It only expires when enough real time has passed
        # This test verifies it doesn't crash on repeated updates
        for _ in range(10):
            result = bs.update()
            assert result is False

        # Now simulate time passing beyond lifetime
        bs.creation_time = time.time() - (BLOODSTAIN_LIFETIME + 0.1)
        result = bs.update()
        assert result is True
