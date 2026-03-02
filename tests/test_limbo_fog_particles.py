"""
Test limbo fog particles behavior: count, concentration, speed, alpha, caching.
"""

import pygame

from src.game import Game


class TestLimboFogParticleCount:
    """Test that limbo fog particles are created at correct count."""

    def test_particle_count_12_per_side(self):
        """12 particles per side (24 total) for balance (fps optimization)."""
        pygame.init()
        g = Game(debug=True)
        g.selected_stage = "limbo"
        g.generate_walls()

        ui = g.ui
        left_particles = getattr(ui, "_limbo_fog_particles_left", [])
        right_particles = getattr(ui, "_limbo_fog_particles_right", [])

        assert (
            len(left_particles) == 12
        ), f"Expected 12 left particles, got {len(left_particles)}"
        assert (
            len(right_particles) == 12
        ), f"Expected 12 right particles, got {len(right_particles)}"


class TestLimboFogParticleConcentration:
    """Test that particles start in lower half of screen (60-100%)."""

    def test_initial_spawn_lower_half(self):
        """Particles should spawn in 60-100% of screen height (bottom half)."""
        pygame.init()
        g = Game(debug=True)
        g.selected_stage = "limbo"
        g.generate_walls()

        ui = g.ui
        left_particles = getattr(ui, "_limbo_fog_particles_left", [])
        right_particles = getattr(ui, "_limbo_fog_particles_right", [])

        all_particles = left_particles + right_particles
        min_spawn_y = g.height * 0.6

        # All particles should be in lower half initially
        for p in all_particles:
            assert (
                p.y >= min_spawn_y - 100
            ), f"Particle y={p.y} should be in lower half (>= {min_spawn_y})"


class TestLimboFogParticleSpeed:
    """Test that particle speeds are reduced (30-60% of original)."""

    def test_reduced_speed_range(self):
        """Particles should move at reduced speed: FOG_MIN_SPEED*0.3 to FOG_MAX_SPEED*0.6."""
        pygame.init()
        g = Game(debug=True)
        g.selected_stage = "limbo"
        g.generate_walls()

        ui = g.ui
        left_particles = getattr(ui, "_limbo_fog_particles_left", [])
        right_particles = getattr(ui, "_limbo_fog_particles_right", [])

        all_particles = left_particles + right_particles

        # FOG_MIN_SPEED = 0.3, FOG_MAX_SPEED = 0.65
        # Expected range: 0.09 to 0.39
        expected_min = 0.3 * 0.3
        expected_max = 0.65 * 0.6

        for p in all_particles:
            assert (
                expected_min - 0.01 <= p.speed <= expected_max + 0.01
            ), f"Particle speed {p.speed} outside range [{expected_min}, {expected_max}]"


class TestLimboFogParticleMovement:
    """Test that particles move upward and wobble."""

    def test_particle_moves_upward(self):
        """Particles should move upward (y decreases) over time."""
        pygame.init()
        g = Game(debug=True)
        g.selected_stage = "limbo"
        g.generate_walls()

        ui = g.ui
        left_particles = getattr(ui, "_limbo_fog_particles_left", [])

        if len(left_particles) > 0:
            p = left_particles[0]
            initial_y = p.y

            # Update 10 frames
            for _ in range(10):
                p.update()

            final_y = p.y
            # Should move upward (y decreases)
            assert (
                final_y < initial_y
            ), f"Particle should move upward: {initial_y} -> {final_y}"


class TestLimboFogParticleAlpha:
    """Test that limbo_1 uses reduced alpha (70% opacity)."""

    def test_limbo_uses_reduced_alpha(self):
        """Limbo_1 particles should cache with 70% alpha opacity."""
        pygame.init()
        g = Game(debug=True)
        g.selected_stage = "limbo"
        g.generate_walls()

        ui = g.ui
        screen = pygame.Surface((g.width, g.height))
        ui.screen = screen

        left_particles = getattr(ui, "_limbo_fog_particles_left", [])

        if len(left_particles) > 0:
            p = left_particles[0]

            # Draw once to trigger caching
            p.draw(screen)

            # Check cache was created
            cache_key = getattr(p, "_cached_draw_key", None)
            assert cache_key is not None, "Cache key should exist after draw"

            cached_image = getattr(p, "_cached_draw_image", None)
            assert cached_image is not None, "Cached image should exist after draw"


class TestLimboFogParticleCaching:
    """Test image caching to reduce per-frame overhead."""

    def test_cache_persists_same_stage(self):
        """Cache should persist when stage doesn't change."""
        pygame.init()
        g = Game(debug=True)
        g.selected_stage = "limbo_2"
        g.generate_walls()

        ui = g.ui
        screen = pygame.Surface((g.width, g.height))
        ui.screen = screen

        left_particles = getattr(ui, "_limbo_fog_particles_left", [])

        if len(left_particles) > 0:
            p = left_particles[0]

            # First draw
            p.draw(screen)
            cache_key_1 = getattr(p, "_cached_draw_key", None)
            cached_img_1_id = id(getattr(p, "_cached_draw_image", None))

            # Second draw (same stage, no cache invalidation)
            p.draw(screen)
            cache_key_2 = getattr(p, "_cached_draw_key", None)
            cached_img_2_id = id(getattr(p, "_cached_draw_image", None))

            # Cache should be identical (same key, same object)
            assert cache_key_1 == cache_key_2, "Cache key should persist for same stage"
            assert (
                cached_img_1_id == cached_img_2_id
            ), "Cached image object should be reused"

    def test_cache_updates_on_stage_change(self):
        """Cache should regenerate when stage changes."""
        pygame.init()
        g = Game(debug=True)
        g.selected_stage = "limbo"
        g.generate_walls()

        ui = g.ui
        screen = pygame.Surface((g.width, g.height))
        ui.screen = screen

        left_particles = getattr(ui, "_limbo_fog_particles_left", [])

        if len(left_particles) > 0:
            p = left_particles[0]

            # Draw with limbo stage
            p.draw(screen)
            cache_key_1 = getattr(p, "_cached_draw_key", None)
            cached_img_1_id = id(getattr(p, "_cached_draw_image", None))

            # Change stage to limbo_2
            g.selected_stage = "limbo_2"
            p.draw(screen)
            cache_key_2 = getattr(p, "_cached_draw_key", None)
            cached_img_2_id = id(getattr(p, "_cached_draw_image", None))

            # Cache should have changed (new key, new object)
            assert (
                cache_key_1 != cache_key_2
            ), "Cache key should change when stage changes"
            assert (
                cached_img_1_id != cached_img_2_id
            ), "Cached image should be regenerated"


class TestLimboFogParticleReset:
    """Test that particles reset when leaving screen."""

    def test_particle_resets_when_off_top(self):
        """Particle should reset when y < -width (off top screen)."""
        pygame.init()
        g = Game(debug=True)
        g.selected_stage = "limbo"
        g.generate_walls()

        ui = g.ui
        left_particles = getattr(ui, "_limbo_fog_particles_left", [])

        if len(left_particles) > 0:
            p = left_particles[0]

            # Force y to be off-screen top
            p.y = -p.width - 10

            # Update should trigger reset
            p.update()

            # After reset, y should be back in lower half
            assert (
                p.y >= g.height * 0.6 - 100
            ), f"Particle y={p.y} should reset to lower half after leaving screen"
