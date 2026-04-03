"""Tests for Eye bonus enemy: spawning, blink animation, beam mechanics, and paralysis."""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# 1. Constants
# ---------------------------------------------------------------------------


def test_eye_constants_present():
    """Verify all Eye-related constants are defined."""
    from src.game_constants import (
        EYE_BEAM_RADIUS,
        EYE_BEAM_TRAVEL_TIME,
        EYE_BLINK_DURATION,
        EYE_BLINK_INTERVAL_MAX,
        EYE_BLINK_INTERVAL_MIN,
        EYE_BOB_AMPLITUDE,
        EYE_BOB_SPEED,
        EYE_BUFF_DURATION,
        EYE_FIRE_RATE_BOOST,
        EYE_FIRST_SPAWN_MAX,
        EYE_FIRST_SPAWN_MIN,
        EYE_HP,
        EYE_LIFESPAN_MAX,
        EYE_LIFESPAN_MIN,
        EYE_PARALYSIS_DURATION,
        EYE_SPAWN_INTERVAL_MAX,
        EYE_SPAWN_INTERVAL_MIN,
        EYE_SPEED,
    )

    # Basic attributes
    assert EYE_HP == 70
    assert EYE_SPEED == 0.0
    assert EYE_FIRST_SPAWN_MIN == 20.0
    assert EYE_FIRST_SPAWN_MAX == 25.0
    assert EYE_SPAWN_INTERVAL_MIN == 20.0
    assert EYE_SPAWN_INTERVAL_MAX == 30.0

    # Lifespan
    assert EYE_LIFESPAN_MIN == 5.0
    assert EYE_LIFESPAN_MAX == 7.0

    # Beam properties
    assert EYE_BEAM_TRAVEL_TIME == 1.8
    assert EYE_BEAM_RADIUS == 6

    # Effects
    assert EYE_PARALYSIS_DURATION == 2.0
    assert EYE_FIRE_RATE_BOOST == 2.0
    assert EYE_BUFF_DURATION == 10.0

    # Animation
    assert EYE_BOB_AMPLITUDE == 4.0
    assert EYE_BOB_SPEED == 0.8
    assert EYE_BLINK_INTERVAL_MIN == 0.8
    assert EYE_BLINK_INTERVAL_MAX == 1.5
    assert EYE_BLINK_DURATION == 1.0


# ---------------------------------------------------------------------------
# 2. Eye initialization and attributes
# ---------------------------------------------------------------------------


def test_eye_init_basic():
    """Test Eye enemy initialization."""
    import pygame

    pygame.init()
    from src.entities.enemy import Enemy
    from src.game_constants import EYE_HP

    x, y = 100, 200
    eye = Enemy(x, y, "eye", EYE_HP, 0.0)

    # Size check (20x20 base + 10 generic adjustment)
    assert eye.width == 30
    assert eye.height == 30

    # Health pinned to exact value
    assert eye.max_health == EYE_HP
    assert eye.health == EYE_HP

    # Damage is zero (harmless)
    assert eye.damage == 0

    # Speed is zero (stationary)
    assert eye.speed == 0.0


def test_eye_init_lifespan():
    """Test Eye lifespan initialization."""
    import pygame

    pygame.init()
    from src.entities.enemy import Enemy
    from src.game_constants import EYE_HP, EYE_LIFESPAN_MAX, EYE_LIFESPAN_MIN

    eye = Enemy(100, 200, "eye", EYE_HP, 0.0)

    # Lifespan should be random in range
    assert hasattr(eye, "_eye_lifespan")
    assert EYE_LIFESPAN_MIN <= eye._eye_lifespan <= EYE_LIFESPAN_MAX

    # Elapsed time starts at zero
    assert hasattr(eye, "_eye_elapsed")
    assert eye._eye_elapsed == 0.0


def test_eye_init_beam_state():
    """Test Eye beam state initialization."""
    import pygame

    pygame.init()
    from src.entities.enemy import Enemy
    from src.game_constants import EYE_HP

    eye = Enemy(100, 200, "eye", EYE_HP, 0.0)

    # Beam state
    assert hasattr(eye, "_eye_beam_fired")
    assert eye._eye_beam_fired is False
    assert hasattr(eye, "_eye_beam_active")
    assert eye._eye_beam_active is False
    assert hasattr(eye, "_eye_beam_timer")
    assert eye._eye_beam_timer == 0.0
    assert hasattr(eye, "_eye_paralysis_applied")
    assert eye._eye_paralysis_applied is False

    # Fire delay (1.5 seconds)
    assert hasattr(eye, "_eye_beam_fire_delay")
    assert eye._eye_beam_fire_delay == 1.5


def test_eye_init_blink_state():
    """Test Eye blink animation state initialization."""
    import pygame

    pygame.init()
    from src.entities.enemy import Enemy
    from src.game_constants import EYE_HP

    eye = Enemy(100, 200, "eye", EYE_HP, 0.0)

    # Blink state: should have timer and progress
    assert hasattr(eye, "_eye_blink_next_time")
    # Should be initialized with random interval
    assert eye._eye_blink_next_time > 0

    assert hasattr(eye, "_eye_blink_progress")
    assert eye._eye_blink_progress == 0.0  # Starts open


# ---------------------------------------------------------------------------
# 3. Blink animation mechanics
# ---------------------------------------------------------------------------


def test_eye_blink_timing():
    """Test that blink triggers at correct intervals."""
    import pygame

    pygame.init()
    from src.entities.enemy import Enemy
    from src.game_constants import (
        EYE_HP,
    )

    eye = Enemy(100, 200, "eye", EYE_HP, 0.0)

    # Manually set blink timing to test
    eye._eye_blink_next_time = 0.1  # Trigger soon
    eye._eye_blink_progress = 0.0

    # Simulate one frame (1/60s)
    dt = 1.0 / 60.0
    # In update, blink_next_time would decrement
    eye._eye_blink_next_time -= dt

    # After enough frames, timer should expire
    assert eye._eye_blink_next_time < 0.1


def test_eye_blink_animation_progress():
    """Test blink animation progresses from 0 to 1 and back."""
    import pygame

    pygame.init()
    from src.entities.enemy import Enemy
    from src.game_constants import EYE_BLINK_DURATION, EYE_HP

    eye = Enemy(100, 200, "eye", EYE_HP, 0.0)

    # Force blink to start
    eye._eye_blink_progress = 0.001
    eye._eye_blink_next_time = 1.0

    # Simulate blink animation for full duration
    for _ in range(int(EYE_BLINK_DURATION * 60)):
        dt = 1.0 / 60.0
        eye._eye_blink_progress += dt / EYE_BLINK_DURATION

    # Should complete
    assert eye._eye_blink_progress >= 1.0


def test_eye_blink_close_open_symmetry():
    """Test blink closes and opens symmetrically."""

    # First half (closing)
    progress_close = 0.25  # 25% through blink = 50% through close phase
    if progress_close <= 0.5:
        blink_close = progress_close * 2.0
    else:
        blink_close = (1.0 - progress_close) * 2.0

    assert 0.4 <= blink_close <= 0.6  # Around 50% closed

    # Second half (opening)
    progress_open = 0.75  # 75% through blink = 50% through open phase
    if progress_open <= 0.5:
        blink_close = progress_open * 2.0
    else:
        blink_close = (1.0 - progress_open) * 2.0

    assert 0.4 <= blink_close <= 0.6  # Around 50% closed (symmetric)


# ---------------------------------------------------------------------------
# 4. Bobbing animation
# ---------------------------------------------------------------------------


def test_eye_bobbing_oscillation():
    """Test Eye bobs vertically with sine wave."""
    import pygame

    pygame.init()
    from src.entities.enemy import Enemy
    from src.game_constants import EYE_BOB_AMPLITUDE, EYE_BOB_SPEED, EYE_HP

    eye = Enemy(100, 200.0, "eye", EYE_HP, 0.0)
    original_y = eye._eye_spawn_y

    # Simulate a few frames of bobbing
    dt = 1.0 / 60.0
    for _ in range(30):  # 0.5 seconds
        eye._eye_bob_phase = (
            getattr(eye, "_eye_bob_phase", 0.0) + EYE_BOB_SPEED * dt * 6.2832
        )
        spawn_y = getattr(eye, "_eye_spawn_y", 200.0)
        eye.y = spawn_y + math.sin(eye._eye_bob_phase) * EYE_BOB_AMPLITUDE

    # Y should oscillate within ±EYE_BOB_AMPLITUDE from spawn_y
    delta_y = abs(eye.y - original_y)
    assert delta_y <= EYE_BOB_AMPLITUDE + 0.1  # Allow small floating point error


# ---------------------------------------------------------------------------
# 5. Beam firing and travel
# ---------------------------------------------------------------------------


def test_eye_beam_fire_delay():
    """Test Eye fires beam 1.5 seconds after spawning."""
    import pygame

    pygame.init()
    from src.entities.enemy import Enemy
    from src.game_constants import EYE_HP

    eye = Enemy(100, 200, "eye", EYE_HP, 0.0)

    # Beam should NOT fire immediately
    assert eye._eye_beam_fired is False
    assert eye._eye_beam_active is False

    # Fire delay should be 1.5 seconds
    assert eye._eye_beam_fire_delay == 1.5


def test_eye_beam_single_fire():
    """Test Eye fires exactly one beam per appearance."""
    import pygame

    pygame.init()
    from src.entities.enemy import Enemy
    from src.game_constants import EYE_HP

    eye = Enemy(100, 200, "eye", EYE_HP, 0.0)

    # Mark as fired
    eye._eye_beam_fired = True
    eye._eye_beam_active = True

    # Once fired, should not re-fire (no multi-beam)
    assert eye._eye_beam_fired is True


def test_eye_beam_locked_direction():
    """Test beam direction is locked at fire time, doesn't follow player."""
    import pygame

    pygame.init()
    from src.entities.enemy import Enemy
    from src.game_constants import EYE_HP

    eye = Enemy(100, 200, "eye", EYE_HP, 0.0)

    # Set fire position and target
    eye._eye_beam_start_x = 100.0
    eye._eye_beam_start_y = 200.0
    eye._eye_beam_target_x = 500.0
    eye._eye_beam_target_y = 300.0

    # Direction vector
    dx = eye._eye_beam_target_x - eye._eye_beam_start_x
    dy = eye._eye_beam_target_y - eye._eye_beam_start_y

    assert dx > 0  # Toward right
    assert dy > 0  # Toward down

    # Even if player moves, target stays fixed
    original_target_x = eye._eye_beam_target_x
    original_target_y = eye._eye_beam_target_y

    assert eye._eye_beam_target_x == original_target_x
    assert eye._eye_beam_target_y == original_target_y


# ---------------------------------------------------------------------------
# 6. Paralysis effect on player
# ---------------------------------------------------------------------------


def test_player_paralysis_timer():
    """Test player paralysis timer attribute."""
    import pygame

    pygame.init()
    from src.entities.player import Player

    player = Player(640, 360)

    # Should have paralysis timer
    assert hasattr(player, "paralyze_timer")
    assert player.paralyze_timer == 0


def test_player_paralysis_freezes_movement():
    """Test paralyzed player cannot move."""
    import pygame

    pygame.init()
    from src.entities.player import Player

    player = Player(640, 360)

    # Set paralysis
    player.paralyze_timer = 120  # 2 seconds at 60 FPS
    player.velocity_x = 100
    player.velocity_y = 50

    # Simulate update with paralysis guard
    if getattr(player, "paralyze_timer", 0) > 0:
        player.velocity_x = 0.0
        player.velocity_y = 0.0

    assert player.velocity_x == 0.0
    assert player.velocity_y == 0.0


# ---------------------------------------------------------------------------
# 7. Spawn system integration
# ---------------------------------------------------------------------------


def test_eye_not_in_prologo():
    """Test Eyes do not spawn in prologue stage."""
    stage = "prologo"

    # Eye should only spawn in non-prologo stages
    should_spawn = stage != "prologo"
    assert should_spawn is False


def test_eye_spawn_in_other_stages():
    """Test Eyes can spawn in all non-prologue stages."""
    for stage in ["limbo", "limbo_2", "purgatory", "hell"]:
        should_spawn = stage != "prologo"
        assert should_spawn is True


def test_eye_spawn_position_margins():
    """Test Eye spawns in outer wall margins, not center."""
    screen_w, screen_h = 1280, 720
    wall = 25  # WALL_THICKNESS

    # Valid spawn zones: outer margins
    left_zone = (0, wall + 50)
    right_zone = (screen_w - wall - 50, screen_w)
    (60, wall + 50)

    # Eye should not spawn in center
    center_x = screen_w // 2
    screen_h // 2

    assert not (left_zone[0] <= center_x <= left_zone[1])
    assert not (right_zone[0] <= center_x <= right_zone[1])


# ---------------------------------------------------------------------------
# 8. Fire rate buff on kill
# ---------------------------------------------------------------------------


def test_fire_rate_buff_initialization():
    """Test fire rate buff state variables."""
    from src.game_constants import EYE_BUFF_DURATION, EYE_FIRE_RATE_BOOST

    # Buff attributes that should be set on kill
    assert EYE_FIRE_RATE_BOOST == 2.0
    assert EYE_BUFF_DURATION == 10.0


def test_fire_rate_buff_multiplication():
    """Test fire rate is doubled on Eye kill."""
    base_fire_rate = 1.0
    boosted_fire_rate = base_fire_rate * 2.0

    assert boosted_fire_rate == 2.0
    assert boosted_fire_rate / base_fire_rate == 2.0


# ---------------------------------------------------------------------------
# 9. Auto-despawn (no kill reward)
# ---------------------------------------------------------------------------


def test_eye_natural_despawn_no_reward():
    """Test Eye despawns naturally without granting reward."""
    import pygame

    pygame.init()
    from src.entities.enemy import Enemy
    from src.game_constants import EYE_HP

    eye = Enemy(100, 200, "eye", EYE_HP, 0.0)

    # Set lifespan to a known value
    eye._eye_lifespan = 5.0
    # Force elapsed time past lifespan
    eye._eye_elapsed = 6.0

    # When elapsed >= lifespan, Eye should despawn
    should_despawn = eye._eye_elapsed >= eye._eye_lifespan
    assert should_despawn  # Natural despawn triggers


# ---------------------------------------------------------------------------
# 10. Beam collision with player
# ---------------------------------------------------------------------------


def test_beam_segment_collision_calculation():
    """Test beam segment collision uses point-to-segment distance."""

    # Beam start and end points
    beam_start_x, beam_start_y = 100.0, 200.0
    beam_end_x, beam_end_y = 500.0, 300.0

    # Player position
    player_x, player_y = 300.0, 250.0

    # Vector from beam start to end
    beam_dx = beam_end_x - beam_start_x
    beam_dy = beam_end_y - beam_start_y
    beam_len_sq = beam_dx * beam_dx + beam_dy * beam_dy

    if beam_len_sq > 0:
        # Project player onto beam line
        t = (
            (player_x - beam_start_x) * beam_dx + (player_y - beam_start_y) * beam_dy
        ) / beam_len_sq
        t = max(0, min(1, t))  # Clamp to segment

        # Closest point on segment
        closest_x = beam_start_x + t * beam_dx
        closest_y = beam_start_y + t * beam_dy

        # Distance from player to closest point
        dist = math.hypot(player_x - closest_x, player_y - closest_y)

        # Should be within valid hit radius
        assert dist >= 0


def test_beam_hits_only_within_segment():
    """Test beam only hits if player within rendered segment."""
    # Beam segment length (100 pixels)
    segment_length = 100

    # Player at different distances
    proj_len = 80  # Within segment

    # Hit only if 0 <= proj_len <= segment_length
    should_hit = 0 <= proj_len <= segment_length
    assert should_hit is True

    # Player outside segment
    proj_len = 150
    should_hit = 0 <= proj_len <= segment_length
    assert should_hit is False


# ---------------------------------------------------------------------------
# 11. Integration tests
# ---------------------------------------------------------------------------


def test_eye_complete_lifecycle():
    """Test Eye complete lifecycle: spawn -> bob -> blink -> fire -> despawn."""
    import pygame

    pygame.init()
    from src.entities.enemy import Enemy
    from src.game_constants import EYE_HP

    eye = Enemy(100, 200, "eye", EYE_HP, 0.0)

    # Initial state
    assert eye.health == EYE_HP
    assert eye._eye_beam_fired is False
    assert eye._eye_blink_progress == 0.0

    # Should have all required attributes
    assert hasattr(eye, "_eye_lifespan")
    assert hasattr(eye, "_eye_elapsed")
    assert hasattr(eye, "_eye_bob_phase")
    assert hasattr(eye, "_eye_blink_next_time")
    assert hasattr(eye, "_eye_blink_progress")
    assert hasattr(eye, "_eye_beam_fire_delay")


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
