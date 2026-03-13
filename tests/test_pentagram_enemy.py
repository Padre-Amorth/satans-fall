"""Tests for the pentagram enemy type and elemental variants."""

from src.game import Game

_ELEMENTAL_TYPES = ("pentagram_fire", "pentagram_storm", "pentagram_ice")
_ALL_PENTAGRAM_TYPES = ("pentagram",) + _ELEMENTAL_TYPES


def test_pentagram_spawns_at_60_seconds():
    """Verify pentagram does NOT spawn before 60s, but DOES spawn at/after 60s."""
    g = Game(debug=True)
    g.selected_stage = "prologo"
    g.showing_main_menu = False
    g.time_elapsed = 59.9
    g.update_game()

    # Should not exist yet
    types_before = [getattr(e, "enemy_type", None) for e in g.enemies]
    assert not any(
        t in _ALL_PENTAGRAM_TYPES for t in types_before
    ), "Pentagram should not spawn before 60s"

    # Move time forward to 60.1 seconds
    g.time_elapsed = 60.1
    g.update_game()

    # Should exist now
    types_after = [getattr(e, "enemy_type", None) for e in g.enemies]
    assert any(
        t in _ALL_PENTAGRAM_TYPES for t in types_after
    ), "Pentagram should spawn at t >= 60s"


def test_pentagram_spawns_once_per_run():
    """Verify pentagram spawns only once per run."""
    g = Game(debug=True)
    g.selected_stage = "limbo"
    g.showing_main_menu = False
    g.time_elapsed = 60.1

    # Force multiple update calls
    for _ in range(5):
        g.update_game()

    # Count all pentagram variants
    pentagrams = [
        e for e in g.enemies if getattr(e, "enemy_type", None) in _ALL_PENTAGRAM_TYPES
    ]
    assert len(pentagrams) == 1, f"Expected 1 pentagram, found {len(pentagrams)}"


def test_pentagram_horizontal_movement():
    """Verify pentagram moves horizontally (x changes, y oscillates)."""
    from src.entities.enemy import Enemy

    e = Enemy(100.0, 250.0, "pentagram", 300.0, 50.0)
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
    """Verify pentagram has exactly 300 body HP + 1500 shield HP."""
    from src.entities.enemy import Enemy

    e = Enemy(100.0, 300.0, "pentagram", 300.0, 50.0)
    assert e.max_health == 300, f"Expected max_health=300, got {e.max_health}"
    assert e.health == 300, f"Expected health=300, got {e.health}"
    assert e.shield_hp == 1500, f"Expected shield_hp=1500, got {e.shield_hp}"
    assert (
        e.shield_max_hp == 1500
    ), f"Expected shield_max_hp=1500, got {e.shield_max_hp}"


def test_elemental_pentagram_has_correct_health():
    """Verify elemental variants have 300 body HP + 500 elemental shield HP."""
    from src.entities.enemy import Enemy

    for etype in _ELEMENTAL_TYPES:
        e = Enemy(100.0, 300.0, etype, 300.0, 50.0)
        assert (
            e.max_health == 300
        ), f"{etype}: Expected max_health=300, got {e.max_health}"
        assert e.health == 300, f"{etype}: Expected health=300, got {e.health}"
        assert e.shield_hp == 500, f"{etype}: Expected shield_hp=500, got {e.shield_hp}"
        assert (
            e.shield_max_hp == 500
        ), f"{etype}: Expected shield_max_hp=500, got {e.shield_max_hp}"


def test_elemental_pentagram_stage_mapping():
    """Verify each purgatory stage spawns the correct elemental variant."""
    _EXPECTED = {
        "purgatory": "pentagram_fire",
        "purgatory_2": "pentagram_storm",
        "purgatory_3": "pentagram_ice",
    }
    for stage, expected_type in _EXPECTED.items():
        g = Game(debug=True)
        g.selected_stage = stage
        g.showing_main_menu = False
        g.time_elapsed = 60.1
        g.update_game()
        types = [getattr(e, "enemy_type", None) for e in g.enemies]
        assert (
            expected_type in types
        ), f"Stage '{stage}' should spawn '{expected_type}', got {types}"


def test_pentagram_exits_screen_when_off_bounds():
    """Verify pentagram self-removes (health=0) when fully off-screen."""
    from src.entities.enemy import Enemy

    e = Enemy(-50.0, 300.0, "pentagram", 300.0, 50.0)
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
    """Verify all pentagram variants have 0 damage."""
    from src.entities.enemy import Enemy

    for etype in _ALL_PENTAGRAM_TYPES:
        e = Enemy(100.0, 300.0, etype, 300.0, 50.0)
        assert e.damage == 0, f"{etype} damage should be 0, got {e.damage}"


def test_pentagram_reset_on_new_run():
    """Verify pentagram flag resets when starting a new run."""
    g = Game(debug=True)
    g.selected_stage = "purgatory"
    g.showing_main_menu = False
    g.time_elapsed = 60.1

    # First run: spawn pentagram_fire (purgatory stage)
    g.update_game()
    pentagrams_1 = [
        e for e in g.enemies if getattr(e, "enemy_type", None) in _ALL_PENTAGRAM_TYPES
    ]
    assert len(pentagrams_1) == 1, "Should spawn 1 pentagram variant in first run"
    assert (
        getattr(pentagrams_1[0], "enemy_type", None) == "pentagram_fire"
    ), "purgatory should spawn pentagram_fire"

    # Verify the flag is True
    assert g.spawn_system.pentagram_spawned is True, "Flag should be True after spawn"

    # Reset the run
    g.reset_game()
    g.selected_stage = "purgatory"
    g.showing_main_menu = False

    # Verify the flag is reset to False
    assert (
        g.spawn_system.pentagram_spawned is False
    ), "Flag should be False after reset_game()"

    # Move time to 60s again
    g.time_elapsed = 60.1
    g.update_game()
    pentagrams_2 = [
        e for e in g.enemies if getattr(e, "enemy_type", None) in _ALL_PENTAGRAM_TYPES
    ]
    assert len(pentagrams_2) == 1, "Should spawn 1 pentagram variant after reset"
