"""Tests for the pentagram enemy type."""

from src.game import Game


def test_pentagram_spawns_at_60_seconds():
    """Verify pentagram does NOT spawn before 60s, but DOES spawn at/after 60s."""
    g = Game(debug=True)
    g.selected_stage = "prologo"
    g.showing_main_menu = False
    g.time_elapsed = 59.9
    g.update_game()

    # Should not exist yet
    types_before = [getattr(e, "enemy_type", None) for e in g.enemies]
    assert "pentagram" not in types_before, "Pentagram should not spawn before 60s"

    # Move time forward to 60.1 seconds
    g.time_elapsed = 60.1
    g.update_game()

    # Should exist now
    types_after = [getattr(e, "enemy_type", None) for e in g.enemies]
    assert "pentagram" in types_after, "Pentagram should spawn at t >= 60s"


def test_pentagram_spawns_once_per_run():
    """Verify pentagram spawns only once per run."""
    g = Game(debug=True)
    g.selected_stage = "limbo"
    g.showing_main_menu = False
    g.time_elapsed = 60.1

    # Force multiple update calls
    for _ in range(5):
        g.update_game()

    # Count pentagrams
    pentagrams = [e for e in g.enemies if getattr(e, "enemy_type", None) == "pentagram"]
    assert len(pentagrams) == 1, f"Expected 1 pentagram, found {len(pentagrams)}"


def test_pentagram_horizontal_movement():
    """Verify pentagram moves horizontally (x changes, y oscillates)."""
    from src.entities.enemy import Enemy

    e = Enemy(100.0, 250.0, "pentagram", 500.0, 50.0)
    e.direction = 1  # moving right

    # Simulate 60 frames
    class FakeGame:
        width = 1280

    x_positions = [e.x]
    for _ in range(60):
        e.update(None, FakeGame())
        x_positions.append(e.x)

    # X should increase monotonically (direction=1)
    for i in range(1, len(x_positions)):
        assert (
            x_positions[i] > x_positions[i - 1]
        ), "X should increase when moving right"

    # Check that movement is roughly 50px/s * 60 frames / 60fps = 50px
    x_delta = x_positions[-1] - x_positions[0]
    assert 49 < x_delta < 51, f"X movement should be ~50px, got {x_delta}"


def test_pentagram_has_correct_health():
    """Verify pentagram has exactly 500 body HP + 1500 shield HP."""
    from src.entities.enemy import Enemy

    e = Enemy(100.0, 300.0, "pentagram", 500.0, 50.0)
    assert e.max_health == 500, f"Expected max_health=500, got {e.max_health}"
    assert e.health == 500, f"Expected health=500, got {e.health}"
    assert e.shield_hp == 1500, f"Expected shield_hp=1500, got {e.shield_hp}"
    assert (
        e.shield_max_hp == 1500
    ), f"Expected shield_max_hp=1500, got {e.shield_max_hp}"


def test_pentagram_exits_screen_when_off_bounds():
    """Verify pentagram self-removes (health=0) when fully off-screen."""
    from src.entities.enemy import Enemy

    e = Enemy(-50.0, 300.0, "pentagram", 500.0, 50.0)
    e.direction = 1  # moving right

    # Simulate enough frames to cross 1280px: 1280 / (50px/s / 60fps) = 1536 frames
    class FakeGame:
        width = 1280

    for _ in range(2000):  # well over 1536
        e.update(None, FakeGame())
        if e.health <= 0:
            break

    assert (
        e.health <= 0
    ), "Pentagram should be removed (health <= 0) when exiting right side"


def test_pentagram_does_not_attack():
    """Verify pentagram has 0 damage."""
    from src.entities.enemy import Enemy

    e = Enemy(100.0, 300.0, "pentagram", 500.0, 50.0)
    assert e.damage == 0, f"Pentagram damage should be 0, got {e.damage}"


def test_pentagram_reset_on_new_run():
    """Verify pentagram flag resets when starting a new run."""
    g = Game(debug=True)
    g.selected_stage = "purgatory"
    g.showing_main_menu = False
    g.time_elapsed = 60.1

    # First run: spawn pentagram
    g.update_game()
    pentagrams_1 = [
        e for e in g.enemies if getattr(e, "enemy_type", None) == "pentagram"
    ]
    assert len(pentagrams_1) == 1, "Should spawn 1 pentagram in first run"

    # Verify the flag is True
    assert g.spawn_system.pentagram_spawned is True, "Flag should be True after spawn"

    # Reset the run (resets time_elapsed to 0, clears enemies, resets flag)
    g.reset_game()
    g.selected_stage = "purgatory"  # re-select stage after reset
    g.showing_main_menu = False

    # Verify the flag is reset to False
    assert (
        g.spawn_system.pentagram_spawned is False
    ), "Flag should be False after reset_game()"

    # Move time to 60s again
    g.time_elapsed = 60.1
    g.update_game()
    pentagrams_2 = [
        e for e in g.enemies if getattr(e, "enemy_type", None) == "pentagram"
    ]
    assert len(pentagrams_2) == 1, "Should spawn 1 pentagram after reset"
