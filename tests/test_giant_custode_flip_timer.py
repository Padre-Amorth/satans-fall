import pygame

from src.entities.enemy import Enemy
from src.game import Game


def test_giant_flip_timer_initialization():
    """Verify that Giant enemies initialize with flip timer."""
    pygame.init()

    # Create a Giant enemy
    giant = Enemy(100, 100, "giant")
    assert hasattr(giant, "_flip_timer"), "Giant should have _flip_timer"
    assert hasattr(giant, "_should_flip"), "Giant should have _should_flip"
    assert giant._flip_timer == 0, "Initial _flip_timer should be 0"
    assert giant._should_flip is False, "Initial _should_flip should be False"


def test_custode_flip_timer_initialization():
    """Verify that Custode enemies initialize with flip timer."""
    pygame.init()

    # Create a Custode enemy
    custode = Enemy(100, 100, "custode")
    assert hasattr(custode, "_flip_timer"), "Custode should have _flip_timer"
    assert hasattr(custode, "_should_flip"), "Custode should have _should_flip"
    assert custode._flip_timer == 0, "Initial _flip_timer should be 0"
    assert custode._should_flip is False, "Initial _should_flip should be False"


def test_flip_timer_advances_each_frame():
    """Verify that _flip_timer increments each frame."""
    pygame.init()
    g = Game(debug=True)

    giant = Enemy(100, 100, "giant")
    initial_timer = giant._flip_timer

    # Simulate 10 frames of updates
    for _ in range(10):
        giant.update(g.player, g)

    assert (
        giant._flip_timer == initial_timer + 10
    ), "Timer should advance by 10 after 10 updates"


def test_flip_toggles_at_48_frames():
    """Verify that _should_flip toggles every 48 frames (0.8 seconds)."""
    pygame.init()
    g = Game(debug=True)

    giant = Enemy(100, 100, "giant")
    initial_flip = giant._should_flip

    # Simulate 47 frames - should NOT flip yet
    for _ in range(47):
        giant.update(g.player, g)

    assert giant._should_flip == initial_flip, "Should not flip before 48 frames"
    assert giant._flip_timer == 47, "Timer should be at 47"

    # One more frame to reach 48
    giant.update(g.player, g)

    assert giant._should_flip != initial_flip, "Should flip at exactly 48 frames"
    assert giant._flip_timer == 0, "Timer should reset to 0 after flip"

    # Continue to verify the cycle repeats
    for _ in range(48):
        giant.update(g.player, g)

    assert (
        giant._should_flip == initial_flip
    ), "Should flip back after another 48 frames"


def test_flip_timer_persists_during_movement():
    """Verify that flip timer persists and advances during movement."""
    pygame.init()
    g = Game(debug=True)

    giant = Enemy(100, 100, "giant")

    # Advance the timer to 30
    for _ in range(30):
        giant.update(g.player, g)

    assert giant._flip_timer == 30, "Timer should be at 30"
    assert giant._should_flip is False, "Should not have flipped yet"

    # Move the giant and continue updating
    giant.x += 10
    giant.y += 5

    # Update 18 more times (30 + 18 = 48, the flip threshold)
    for _ in range(18):
        giant.update(g.player, g)

    assert giant._flip_timer == 0, "Timer should reset after flip at 48 frames"
    assert giant._should_flip is True, "Should flip after reaching 48 frames"


def test_custode_flip_independent_of_facing():
    """Verify that Custode flip is independent of _facing_right."""
    pygame.init()
    g = Game(debug=True)

    custode = Enemy(100, 100, "custode")

    # Set _facing_right to True and advance 48 frames
    custode._facing_right = True
    for _ in range(48):
        custode.update(g.player, g)

    assert custode._should_flip is True, "Should flip after 48 frames"

    # Change facing direction
    custode._facing_right = False

    # The flip state should not be affected by _facing_right change
    should_flip_before_update = custode._should_flip
    custode.update(g.player, g)
    assert (
        custode._should_flip == should_flip_before_update
    ), "Flip should not change based on _facing_right"
