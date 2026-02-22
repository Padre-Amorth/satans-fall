import pygame

from src.game import Game


def test_custode_splits_at_half_health():
    pygame.init()
    g = Game(debug=True)

    # ensure non-Hell spawns still create a giant
    g.selected_stage = "purgatory"
    g.spawn_giant_enemy()
    giants = [e for e in g.enemies if getattr(e, "enemy_type", "") == "giant"]
    assert giants, "non-Hell spawn_giant_enemy should produce a giant"
    # clear and prepare for hell test
    # use fresh container rather than clear() (Group.clear needs surfaces)
    g.enemies = pygame.sprite.Group()

    g.selected_stage = "hell"  # ensure custode spawn
    # force a big spawn
    g.spawn_giant_enemy()
    custodes = [e for e in g.enemies if getattr(e, "enemy_type", "") == "custode"]
    assert custodes, "custode should be spawned on hell stage"

    c = custodes[0]
    original_width = c.width
    original_height = c.height
    initial_max = c.max_health
    # deal damage to push it below half
    c.take_damage(initial_max // 2 + 1)
    # simulate a game update so splitting logic runs
    try:
        c.update(g.player, g)
    except Exception:
        pass

    # after splitting we should have exactly two custodes in the game
    all_custodes = [e for e in g.enemies if getattr(e, "enemy_type", "") == "custode"]
    assert (
        len(all_custodes) == 2
    ), f"expected 2 custodes after split, found {len(all_custodes)}"
    # original object should no longer be present
    assert (
        c not in all_custodes and c.health <= 0
    ), "original custode did not vanish on split"
    # both halves should share roughly equal max health (half of original)
    all_custodes.sort(key=lambda e: e.x)
    left, right = all_custodes
    # both halves should have equal max health and be strictly less than original
    assert left.max_health == right.max_health
    assert left.max_health < initial_max
    # ensure they're reasonably separated horizontally; require at least
    # the same distance used during spawning (parent width/2 or 30 px)
    expected_sep = max(30, original_width // 2)
    assert (
        abs(left.x - right.x) >= expected_sep
    ), "custode pieces are too close together"
    # both children still have less HP than the initial maximum
    for e in all_custodes:
        assert e.health < initial_max

    # both halves should move significantly faster than the parent
    # (2× multiplier used during spawn) and record that doubled speed as
    # their original_speed so downstream systems don’t throttle them back
    base_speed = getattr(c, "original_speed", c.speed)
    for e in all_custodes:
        assert (
            abs(e.speed - base_speed * 2.0) < 0.001
        ), f"custode piece speed {e.speed} != expected {base_speed * 2.0}"
        assert getattr(e, "original_speed", 0) == base_speed * 2.0

    # halves should have an initial push direction and timer set
    for e in all_custodes:
        assert hasattr(e, "_custode_push_dir")
        assert getattr(e, "_custode_push_timer", 0) > 0

    # simulate a frame and ensure push timer decreases and they move apart
    before_sep = abs(left.x - right.x)
    for e in all_custodes:
        try:
            e.update(g.player, g)
        except Exception:
            pass
    after_sep = abs(left.x - right.x)
    assert after_sep >= before_sep, "halves did not move further apart after update"

    # both pieces should be roughly half the original dimensions
    assert left.width <= original_width // 2 and left.height <= original_height // 2
    assert right.width <= original_width // 2 and right.height <= original_height // 2
