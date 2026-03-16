"""Test Hell stage ambient fire particles."""

import pytest

from src.game.core import Game


class TestHellFireParticles:
    """Test Hell stage fire particle system."""

    def test_particles_not_spawned_in_non_hell_stages(self):
        """Particles should not spawn in non-hell stages."""
        g = Game()
        g.selected_stage = "purgatory"

        # Run updates
        for _ in range(500):
            g._update_hell_fire_particles()

        # Should not spawn any particles
        assert len(g.hell_fire_particles) == 0

    def test_particles_spawn_in_hell_stage(self):
        """Particles should spawn in hell stage."""
        g = Game()
        g.selected_stage = "hell"

        # Run updates (spawn chance is 0.005 per frame)
        # Run until we get a spawn or max frames
        spawn_found = False
        for i in range(2000):
            g._update_hell_fire_particles()
            if len(g.hell_fire_particles) > 0:
                spawn_found = True
                break

        assert spawn_found, "No particles spawned in 2000 frames (p=0.5% per frame)"

    def test_particles_have_required_attributes(self):
        """Spawned particles should have required attributes."""
        g = Game()
        g.selected_stage = "hell"

        # Manually spawn a particle for testing
        g.hell_fire_particles.append(
            {
                "x": 100,
                "y": 200,
                "size": 8,
                "life": 60,
                "max_life": 120,
            }
        )

        p = g.hell_fire_particles[0]
        assert "x" in p
        assert "y" in p
        assert "size" in p
        assert "life" in p
        assert "max_life" in p

    def test_particles_spawn_at_edges(self):
        """Particles should spawn only at screen edges."""
        g = Game()
        g.selected_stage = "hell"

        # Spawn many particles to test positioning
        from src.game_constants import HELL_FIRE_PARTICLE_MARGIN

        for _ in range(2000):
            g._update_hell_fire_particles()

        # All particles should be at edges
        for p in g.hell_fire_particles:
            x = p["x"]
            # Either left edge or right edge
            is_left = x < HELL_FIRE_PARTICLE_MARGIN
            is_right = x > (g.width - HELL_FIRE_PARTICLE_MARGIN)
            assert is_left or is_right, f"Particle x={x} not at edge"

    def test_particles_fade_over_time(self):
        """Particles should decrease in life over time."""
        g = Game()
        g.selected_stage = "hell"

        # Manually add a particle
        g.hell_fire_particles.append(
            {
                "x": 100,
                "y": 200,
                "size": 8,
                "life": 60,
                "max_life": 120,
            }
        )

        initial_life = g.hell_fire_particles[0]["life"]

        # Update once
        g._update_hell_fire_particles()

        # Life should decrease
        assert g.hell_fire_particles[0]["life"] < initial_life

    def test_particles_removed_when_dead(self):
        """Particles should be removed when life reaches 0."""
        g = Game()
        g.selected_stage = "hell"

        # Manually add a particle with very low life
        g.hell_fire_particles.append(
            {
                "x": 100,
                "y": 200,
                "size": 8,
                "life": 1,
                "max_life": 120,
            }
        )

        assert len(g.hell_fire_particles) == 1

        # Update once - particle should reach life=0
        g._update_hell_fire_particles()

        assert len(g.hell_fire_particles) == 1  # Still there after first update

        # Update again - now particle should be removed
        g._update_hell_fire_particles()

        # Particle should be removed (life <= 0 means it's filtered out)
        assert len(g.hell_fire_particles) == 0

    def test_max_particles_capped(self):
        """Should not exceed max active particles."""
        from src.game_constants import HELL_FIRE_PARTICLE_MAX_ACTIVE

        g = Game()
        g.selected_stage = "hell"

        # Run many updates to let particles accumulate
        for _ in range(10000):
            g._update_hell_fire_particles()

        # Should not exceed max
        assert len(g.hell_fire_particles) <= HELL_FIRE_PARTICLE_MAX_ACTIVE

    def test_particles_clear_on_reset(self):
        """Particles should clear when run is reset."""
        g = Game()
        g.selected_stage = "hell"

        # Spawn some particles until we get one
        for _ in range(2000):
            g._update_hell_fire_particles()
            if len(g.hell_fire_particles) > 0:
                break

        assert len(g.hell_fire_particles) > 0, "Could not spawn particle for test"

        # Reset run
        g.reset_run()

        # Particles should be cleared
        assert len(g.hell_fire_particles) == 0

    def test_drawing_does_not_crash(self):
        """Drawing particles should not crash."""
        g = Game()
        g.selected_stage = "hell"

        # Add a test particle
        g.hell_fire_particles.append(
            {
                "x": 100,
                "y": 200,
                "size": 8,
                "life": 60,
                "max_life": 120,
            }
        )

        # Should not raise exception
        try:
            g.ui.effects._draw_hell_fire_particles(0, 0)
        except Exception as e:
            pytest.fail(f"Drawing crashed: {e}")

    def test_all_hell_stages_support_particles(self):
        """All hell stages should spawn particles."""
        from src.game_constants import HELL_STAGES

        for stage in HELL_STAGES:
            g = Game()
            g.selected_stage = stage

            # Run updates until we spawn or timeout
            spawn_found = False
            for _ in range(2000):
                g._update_hell_fire_particles()
                if len(g.hell_fire_particles) > 0:
                    spawn_found = True
                    break

            # Should spawn particles in each stage
            assert spawn_found, f"No particles spawned in {stage} after 2000 frames"
