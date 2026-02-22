from unittest.mock import patch

import pygame

from src.entities.enemy import Enemy
from src.game import Game


def test_mage_spawned_only_in_purgatory_after_timer():
    """Mage should appear only when stage is purgatory/hell and ~15s have passed."""
    pygame.init()
    g = Game(debug=True)
    # ensure we are in an eligible stage and simulate elapsed time
    g.selected_stage = "purgatory"
    g.frame_count = g.fps * 20  # past 15 second threshold
    # simulate that the last mage spawn was much earlier
    g.mage_last_spawn_frame = g.frame_count - (g.fps * 20)
    # force random.roll to hit the 50% check
    with patch("random.random", return_value=0.1):
        g.spawn_enemy()

    types = [getattr(e, "enemy_type", None) for e in g.enemies]
    assert "mage" in types, "Expected a mage spawn under purgatory after timer"
    # mage spawned should carry a shield
    mage = next(e for e in g.enemies if getattr(e, "enemy_type", "") == "mage")
    assert hasattr(mage, "shield_hp") and mage.shield_hp == mage.max_health


def test_mage_not_spawn_early_stage_or_before_timer():
    """Mage must not appear in early stages or before timer expires."""
    pygame.init()
    g = Game(debug=True)
    # scenario 1: wrong stage
    g.selected_stage = "limbo"
    with patch("random.random", return_value=0.1):
        g.spawn_enemy()
    types = [getattr(e, "enemy_type", None) for e in g.enemies]
    assert "mage" not in types, "Mage should not spawn before purgatory"

    # scenario 2: correct stage but timer not elapsed
    g = Game(debug=True)
    g.selected_stage = "purgatory"
    g.frame_count = g.fps * 5  # only 5 seconds passed
    with patch("random.random", return_value=0.1):
        g.spawn_enemy()
    types = [getattr(e, "enemy_type", None) for e in g.enemies]
    assert "mage" not in types, "Mage should not spawn before 15s have elapsed"


def test_mage_spawn_limited_to_two():
    """If two mages are already on screen, a spawn attempt shouldn't add a third.
    The mage timer should also remain unchanged when blocked.
    """
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "purgatory"
    g.frame_count = g.fps * 20
    # simulate timer ready to spawn another mage
    g.mage_last_spawn_frame = g.frame_count - (g.fps * 20)

    # pre-populate two mage enemies
    m1 = Enemy(10, 10, "mage", health=20, speed=30)
    m2 = Enemy(20, 20, "mage", health=20, speed=30)
    try:
        g.enemies.add(m1)
        g.enemies.add(m2)
    except Exception:
        g.enemies = [m1, m2]

    before_timer = g.mage_last_spawn_frame
    with patch("random.random", return_value=0.1):
        g.spawn_enemy()
    types = [getattr(e, "enemy_type", None) for e in g.enemies]
    assert (
        types.count("mage") == 2
    ), "No third mage should have spawned when two are already present"
    # timer should not have been reset because spawn was blocked
    assert g.mage_last_spawn_frame == before_timer

    # if one of the mages is removed, spawning should be allowed again
    try:
        g.enemies.remove(m1)
    except Exception:
        g.enemies = [e for e in g.enemies if e is not m1]
    # advance frame count so timer is still ripe
    g.frame_count += g.fps * 1
    with patch("random.random", return_value=0.1):
        g.spawn_enemy()
    types = [getattr(e, "enemy_type", None) for e in g.enemies]
    assert (
        types.count("mage") == 2
    ), "After removing one mage, spawn should replenish to two"
    # timer should now have been reset since spawn succeeded
    assert g.mage_last_spawn_frame != before_timer


def test_mage_gives_shield_to_another_enemy():
    """The mage should periodically give a shield equal to its max health to a random ally."""
    pygame.init()
    g = Game(debug=True)
    # create one mage and one normal enemy
    mage = Enemy(100, 100, "mage", health=50, speed=50)
    other = Enemy(200, 200, "normal", health=30, speed=50)
    # put them in the game's enemy group so mage.update can see them
    try:
        g.enemies.add(mage)
        g.enemies.add(other)
    except Exception:
        g.enemies = [mage, other]

    # force timer to trigger immediately
    mage.shield_timer = 1

    # patch random.choice so we know which target is picked
    with patch("random.choice", return_value=other):
        mage.update(g.player, g)

    assert getattr(other, "shield_hp", 0) == mage.max_health
    # target should have received a beam effect recorded
    assert hasattr(other, "shield_beam") and other.shield_beam.get("remaining", 0) > 0
    # shield_particles should be generated
    assert getattr(other, "shield_particles", [])
    initial_particles = len(other.shield_particles)
    assert initial_particles > 0, "Expected some shield particles spawned"
    # advancing one frame should update particles (life decreases)
    other.update(g.player, g)
    assert len(other.shield_particles) <= initial_particles
    # after casting the timer should have been reset to somewhere between
    # 5 and 10 seconds (randomised)
    min_expected = g.fps * 5
    max_expected = g.fps * 10
    assert (
        min_expected <= mage.shield_timer <= max_expected
    ), f"Timer should be between {min_expected} and {max_expected} frames"


def test_beam_drawn_and_consumed_on_shield(grayscale=False):
    """Ensure beam countdown works and originates from correct points."""
    pygame.init()
    g = Game(debug=True)
    mage = Enemy(50, 50, "mage", health=40, speed=60)
    other = Enemy(150, 150, "normal", health=30, speed=50)
    try:
        g.enemies.add(mage)
        g.enemies.add(other)
    except Exception:
        g.enemies = [mage, other]
    # manually assign a beam lasting 2 frames
    other.shield_beam = {"remaining": 2, "source": mage}

    # patch pygame.draw.lines to capture drawn coords
    drawn = {}

    def fake_lines(screen, color, closed, points, width):
        drawn["points"] = points

    pygame.draw.lines = fake_lines

    surf = pygame.Surface((300, 300))
    other.rect = pygame.Rect(
        other.x - other.width / 2, other.y - other.height / 2, other.width, other.height
    )
    # draw once, beam remaining should decrement
    other.draw(surf)
    assert other.shield_beam["remaining"] == 1
    # verify captured start/end roughly equal mage and other centres
    pts = drawn.get("points", [])
    assert pts, "Beam should have been drawn"
    assert abs(pts[0][0] - mage.x) <= 6 and abs(pts[0][1] - mage.y) <= 6
    assert abs(pts[-1][0] - other.x) <= 6 and abs(pts[-1][1] - other.y) <= 6
    # midpoint should not lie exactly on straight line connecting endpoints
    if len(pts) >= 3:
        sx, sy = pts[0]
        mx, my = pts[1]
        ex, ey = pts[-1]
        # compute distance from mid to line
        if ex != sx:
            slope = (ey - sy) / (ex - sx)
            expected_my = sy + slope * (mx - sx)
        else:
            expected_my = sy
        assert abs(my - expected_my) > 0.5, "Beam midpoint should jitter off-line"

    # drawing again should consume final frame; attribute may be removed
    other.draw(surf)
    assert (
        not hasattr(other, "shield_beam") or other.shield_beam.get("remaining", 0) == 0
    )
    # further draws leave nothing or zero
    other.draw(surf)
    assert not hasattr(other, "shield_beam")


def test_mage_vertical_drift_into_rear_area():
    """Mage should quickly enter the rear quarter and not stick at top."""
    pygame.init()
    g = Game(debug=True)
    mage = Enemy(100, g.height - 20, "mage", health=40, speed=60)
    try:
        g.enemies.add(mage)
    except Exception:
        g.enemies = [mage]
    # first update: should move up by ~= speed/60 pixels
    before = mage.y
    mage.update(g.player, g)
    assert mage.y < before - (mage.speed / 70), "Mage needs to ascend at normal speed"

    # if mage started very high it should descend
    mage.y = 0
    mage.update(g.player, g)
    assert mage.y > 0, "Mage should descend when above rear zone"

    # after several frames inside rear band it should not freeze: gather y changes
    mage.y = max(30, g.height // 4)
    ys = []
    for _ in range(10):
        mage.update(g.player, g)
        ys.append(mage.y)
    assert any(
        abs(ys[i] - ys[i + 1]) > 0.1 for i in range(len(ys) - 1)
    ), "Mage must oscillate vertically when in rear"


def test_mage_stays_in_background_and_ignores_player():
    """Mage should not chase the player; it stays toward the rear area."""
    pygame.init()
    g = Game(debug=True)
    mage = Enemy(50, 50, "mage", health=40, speed=60)
    try:
        g.enemies.add(mage)
    except Exception:
        g.enemies = [mage]

    # place player far away
    g.player.x = 500
    g.player.y = 500

    # record original position
    ox, oy = mage.x, mage.y
    mage.update(g.player, g)
    # ensure mage didn't move significantly toward player
    dx = g.player.x - mage.x
    dy = g.player.y - mage.y
    # new distance should be roughly same or larger (not chasing)
    od = ((g.player.x - ox) ** 2 + (g.player.y - oy) ** 2) ** 0.5
    nd = (dx**2 + dy**2) ** 0.5
    # allow a pixel or two of jitter; mage should not meaningfully chase player
    assert nd >= od - 2.0, "Mage moved closer to player; it should stay in rear."


def test_reinforcements_can_spawn_mage():
    """Reinforce logic should be able to produce mage enemies when stage allows."""
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "purgatory"
    from unittest.mock import patch

    with patch("random.choices", return_value=["mage"]):
        g.spawn_reinforcements(x=10, y=10, count=2)

    assert any(
        getattr(e, "enemy_type", "") == "mage" for e in g.enemies
    ), "Expected at least one mage from reinforcements"


def test_reinforcements_no_mage_before_purgatory():
    """Reinforcements should not include mage options before purgatory."""
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "limbo"
    from unittest.mock import patch

    def fake_choices(types, weights):
        # mage must not be among generated choices
        assert "mage" not in types, "Mage should not be selectable before purgatory"
        return [types[0]]

    with patch("random.choices", fake_choices):
        g.spawn_reinforcements(x=10, y=10, count=2)

    assert not any(
        getattr(e, "enemy_type", "") == "mage" for e in g.enemies
    ), "Mage should not appear before purgatory"
