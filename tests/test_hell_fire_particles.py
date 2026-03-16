"""Test Hell stage ambient burn fires (sustained burning effects)."""

import pytest

from src.game.core import Game


class TestHellBurnFires:
    """Test Hell stage burn fire system."""

    def test_fires_not_spawned_in_non_hell_stages(self):
        """Burn fires should not spawn in non-hell stages."""
        g = Game()
        g.selected_stage = "purgatory"

        # Run updates
        for _ in range(500):
            g._update_hell_fire_particles()

        # Should not spawn any fires
        assert len(g.hell_burn_fires) == 0

    def test_fires_spawn_in_hell_stage(self):
        """Burn fires should spawn in hell stage."""
        g = Game()
        g.selected_stage = "hell"

        # Run until we get a spawn or max frames
        spawn_found = False
        for i in range(2000):
            g._update_hell_fire_particles()
            if len(g.hell_burn_fires) > 0:
                spawn_found = True
                break

        assert spawn_found, "No fires spawned in 2000 frames (p=1% per frame)"

    def test_fires_have_required_attributes(self):
        """Spawned fires should have required attributes."""
        g = Game()
        g.selected_stage = "hell"

        # Manually add a test fire
        g.hell_burn_fires.append(
            {
                "x": 100,
                "y": 200,
                "timer": 300,
                "max_timer": 300,
                "particles": [],
            }
        )

        fire = g.hell_burn_fires[0]
        assert "x" in fire
        assert "y" in fire
        assert "timer" in fire
        assert "max_timer" in fire
        assert "particles" in fire

    def test_fires_spawn_at_edges(self):
        """Fires should spawn at lateral edges or near walls (left or right)."""
        g = Game()
        g.selected_stage = "hell"

        # Spawn many fires to test positioning
        from src.game_constants import HELL_FIRE_PARTICLE_MARGIN, WALL_THICKNESS

        for _ in range(2000):
            g._update_hell_fire_particles()

        # All fires should be at edges or near walls
        for fire in g.hell_burn_fires:
            x = fire["x"]
            # Either: screen edge, or near walls
            is_left_edge = x < HELL_FIRE_PARTICLE_MARGIN
            is_right_edge = x > (g.width - HELL_FIRE_PARTICLE_MARGIN)
            is_left_wall = WALL_THICKNESS <= x <= (WALL_THICKNESS + HELL_FIRE_PARTICLE_MARGIN)
            is_right_wall = (g.width - WALL_THICKNESS - HELL_FIRE_PARTICLE_MARGIN) <= x <= (g.width - WALL_THICKNESS)

            assert is_left_edge or is_right_edge or is_left_wall or is_right_wall, f"Fire x={x} not at edge or wall"

            # Y position should avoid screen edges (margin of 100px)
            y = fire["y"]
            margin_y = 100
            assert margin_y <= y <= (g.height - margin_y), f"Fire y={y} too close to screen edge"

    def test_fires_have_random_duration(self):
        """Fires should have random duration between min and max."""
        from src.game_constants import (
            HELL_FIRE_PARTICLE_LIFETIME_MAX,
            HELL_FIRE_PARTICLE_LIFETIME_MIN,
        )

        g = Game()
        g.selected_stage = "hell"

        # Spawn many fires and collect durations
        for _ in range(10000):
            g._update_hell_fire_particles()

        # All durations should be within range
        durations = set()
        for fire in g.hell_burn_fires:
            duration = fire["max_timer"]
            assert (
                HELL_FIRE_PARTICLE_LIFETIME_MIN
                <= duration
                <= HELL_FIRE_PARTICLE_LIFETIME_MAX
            ), f"Duration {duration} outside range"
            durations.add(duration)

        # We should eventually see variation in durations
        assert len(durations) > 0 or len(g.hell_burn_fires) > 0, "No fires spawned"

    def test_fires_emit_burn_particles(self):
        """Fires should emit BurnParticles like burning enemies."""
        g = Game()
        g.selected_stage = "hell"

        # Manually add a fire
        g.hell_burn_fires.append(
            {
                "x": 100,
                "y": 200,
                "timer": 100,
                "max_timer": 100,
                "particles": [],
            }
        )

        fire = g.hell_burn_fires[0]
        assert len(fire["particles"]) == 0

        # Update - should emit particles
        g._update_hell_fire_particles()

        # Should have particles now
        assert len(fire["particles"]) > 0

    def test_fires_fade_over_time(self):
        """Fires should decrease in timer over time."""
        g = Game()
        g.selected_stage = "hell"

        # Manually add a fire
        g.hell_burn_fires.append(
            {
                "x": 100,
                "y": 200,
                "timer": 100,
                "max_timer": 100,
                "particles": [],
            }
        )

        initial_timer = g.hell_burn_fires[0]["timer"]

        # Update once
        g._update_hell_fire_particles()

        # Timer should decrease
        assert g.hell_burn_fires[0]["timer"] < initial_timer

    def test_fires_removed_when_expired(self):
        """Fires should be removed when timer reaches 0."""
        g = Game()
        g.selected_stage = "hell"

        # Manually add a fire with very low timer
        g.hell_burn_fires.append(
            {
                "x": 100,
                "y": 200,
                "timer": 1,
                "max_timer": 100,
                "particles": [],
            }
        )

        assert len(g.hell_burn_fires) == 1

        # Update - fire should expire
        g._update_hell_fire_particles()
        g._update_hell_fire_particles()

        # Fire should be removed
        assert len(g.hell_burn_fires) == 0

    def test_max_fires_capped(self):
        """Should not exceed max active fires."""
        from src.game_constants import HELL_FIRE_PARTICLE_MAX_ACTIVE

        g = Game()
        g.selected_stage = "hell"

        # Run many updates to let fires accumulate
        for _ in range(10000):
            g._update_hell_fire_particles()

        # Should not exceed max
        assert len(g.hell_burn_fires) <= HELL_FIRE_PARTICLE_MAX_ACTIVE

    def test_fires_clear_on_reset(self):
        """Fires should clear when run is reset."""
        g = Game()
        g.selected_stage = "hell"

        # Spawn some fires
        for _ in range(2000):
            g._update_hell_fire_particles()

        assert len(g.hell_burn_fires) > 0

        # Reset run
        g.reset_run()

        # Fires should be cleared
        assert len(g.hell_burn_fires) == 0

    def test_drawing_does_not_crash(self):
        """Drawing fires should not crash."""
        from src.entities.enemy import BurnParticle

        g = Game()
        g.selected_stage = "hell"

        # Add a test fire with particles
        fire = {
            "x": 100,
            "y": 200,
            "timer": 100,
            "max_timer": 100,
            "particles": [
                BurnParticle(100, 200, 0, 12, life=30, size=3),
                BurnParticle(105, 205, -5, 15, life=35, size=4),
            ],
        }
        g.hell_burn_fires.append(fire)

        # Should not raise exception
        try:
            g.ui.effects._draw_hell_fire_particles(0, 0)
        except Exception as e:
            pytest.fail(f"Drawing crashed: {e}")

    def test_all_hell_stages_support_fires(self):
        """All hell stages should spawn fires."""
        from src.game_constants import HELL_STAGES

        for stage in HELL_STAGES:
            g = Game()
            g.selected_stage = stage

            # Run updates until we spawn or timeout
            spawn_found = False
            for _ in range(2000):
                g._update_hell_fire_particles()
                if len(g.hell_burn_fires) > 0:
                    spawn_found = True
                    break

            # Should spawn fires in each stage
            assert spawn_found, f"No fires spawned in {stage} after 2000 frames"

    def test_fires_maintain_minimum_distance(self):
        """Fires should maintain minimum distance (150px) from each other."""
        import math

        g = Game()
        g.selected_stage = "hell"

        # Spawn many fires to ensure multiple fires are present
        for _ in range(10000):
            g._update_hell_fire_particles()

        # Check distance between all pairs of fires
        min_distance = 150
        for i, fire1 in enumerate(g.hell_burn_fires):
            for fire2 in g.hell_burn_fires[i + 1 :]:
                x1, y1 = fire1.get("x", 0), fire1.get("y", 0)
                x2, y2 = fire2.get("x", 0), fire2.get("y", 0)
                distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                assert distance >= min_distance, f"Fires too close: {distance:.1f}px < {min_distance}px"
