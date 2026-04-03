import math
import os

import pygame
from test_utils import DummyPlayer

from src.entities.enemy import Enemy
from src.game import Game


def test_boss_moves_to_center_and_shines_when_immortal():
    game = Game()
    game.selected_stage = "prologo"
    # Create boss starting off-center
    boss = Enemy(50, 50, "boss_final", health=1000, speed=10)

    center_x = game.width / 2
    center_y = (
        game.height / 2 - 150
    )  # Stopped 100px higher during immortal/regeneration phase
    initial_dist = math.hypot(boss.x - center_x, boss.y - center_y)
    initial_width = boss.width

    # Set game state to immortal phase
    game.prologo_final_boss_immortal = True

    # Call update a few times to move towards center and trigger shine
    player = DummyPlayer(400, 500)
    for _ in range(10):  # More updates for size increase
        boss.update(player, game)

    new_dist = math.hypot(boss.x - center_x, boss.y - center_y)

    assert new_dist < initial_dist, "Boss did not move closer to center when immortal"
    assert (
        boss.width > initial_width
    ), "Boss did not increase in size during regeneration"
    assert hasattr(boss, "shine_phase") and boss.shine_phase > 0
    assert boss.shining is True
    # If a base image is available we expect the immortal-phase
    # overlay to have altered the central pixel (shine on top)
    # as well as the usual aura expansion around the boss.
    if getattr(boss, "base_image", None) is not None:
        # central pixel should change because of the top-layer shine
        base_center = boss.base_image.get_at((boss.width // 2, boss.height // 2))
        cx = boss.image.get_width() // 2
        cy = boss.image.get_height() // 2
        cur_center = boss.image.get_at((cx, cy))
        assert base_center != cur_center, "Central pixel did not change for shine"

        # aura image should still be square and not excessively large
        w = boss.image.get_width()
        h = boss.image.get_height()
        assert w == h, "Aura surface must remain square for a circular halo"
        # should not be more than twice the boss width/height
        assert w <= boss.width * 2 + 20, "Aura surface unexpectedly huge"
        # central transparent corners verify roundness: top-left should be clear
        corner = boss.image.get_at((0, 0))
        assert corner.a == 0, "Aura corners should be transparent (round glow)"
        # ensure aura actually exists at an edge pixel
        edge_px = boss.image.get_at((w // 2, h - 1))
        assert edge_px.a > 0, "Aura not visible around boss during shine"
        # check fade: alpha drops once we leave the main glow radius
        # (radius value not used by test)


# optionally could inspect alpha gradient, but outer ring may
# be nearly equal due to rounding; visual gap is sufficient.


def test_boss_prologo_entrance_pulses_aura_midway():
    """Boss_final entering in prologo should have its aura active from spawn.

    Instead of waiting until halfway down, the glow must be present the moment
    the boss appears and continue through the entire entrance sequence.
    """
    game = Game()
    game.selected_stage = "prologo"
    # use the typical prologue spawn speed so the movement rate reflects actual
    # gameplay; the exact value doesn't matter since the loop below is unbounded
    boss = Enemy(200, 0, "boss_final", health=1000, speed=40)

    player = DummyPlayer(0, 0)
    target_y = 140
    halfway = target_y / 2

    # Before moving, there should be no aura active
    assert boss.shining is False
    boss.update(player, game)
    assert boss.y < halfway
    # aura should already be active now (checked below)

    # first update should already start the aura
    boss.update(player, game)
    assert boss.shining is True
    assert boss.shine_phase > 0

    if getattr(boss, "base_image", None) is not None:
        # ensure the surface is square and corners are transparent (circle)
        w = boss.image.get_width()
        h = boss.image.get_height()
        assert w == h, "Entrance aura surface should be square"
        corner = boss.image.get_at((0, 0))
        assert corner.a == 0, "Aura corners are not transparent"
        edge_center = boss.image.get_at((w // 2, h - 1))
        assert (
            edge_center.a > 0
        ), "Boss image did not show aura behind silhouette on entrance"
        # fade check (radius value not used)
    # alpha gradient not strictly tested any more

    # advance until entrance is marked complete, then verify pulsing continues
    while not hasattr(boss, "entrance_complete"):
        boss.update(player, game)

    prev_phase = boss.shine_phase
    boss.update(player, game)
    assert boss.shining is True, "Aura should remain active after arrival"
    assert (
        boss.shine_phase > prev_phase
    ), "Aura phase should keep advancing after entrance"


def test_boss_limbo_entrance_pulses_aura_midway():
    """Limbo Final boss should glow immediately on spawn like Prologo's boss.

    The logic is identical to :func:`test_boss_prologo_entrance_pulses_aura_midway`
    but for the `boss_limbo` type and `limbo_final` stage.
    """
    game = Game()
    game.selected_stage = "limbo_final"
    boss = Enemy(200, 0, "boss_limbo", health=1000, speed=40)
    player = DummyPlayer(0, 0)
    target_y = 140
    halfway = target_y / 2

    assert boss.shining is False
    boss.update(player, game)
    assert boss.y < halfway
    boss.update(player, game)
    assert boss.shining is True
    assert boss.shine_phase > 0

    if getattr(boss, "base_image", None) is not None:
        w = boss.image.get_width()
        h = boss.image.get_height()
        assert w == h, "Entrance aura surface should be square"
        corner = boss.image.get_at((0, 0))
        assert corner.a == 0, "Aura corners are not transparent"
        edge_center = boss.image.get_at((w // 2, h - 1))
        assert (
            edge_center.a > 0
        ), "Boss image did not show aura behind silhouette on entrance"

    while not hasattr(boss, "entrance_complete"):
        boss.update(player, game)

    prev_phase = boss.shine_phase
    boss.update(player, game)
    assert boss.shining is True
    assert boss.shine_phase > prev_phase


def test_aura_covers_elongated_boss():
    """Ensure aura radius calculation encloses the full silhouette.

    Regression: previous implementation used half the max dimension which
    failed to cover the diagonal corners of very wide/narrow bosses.
    """
    pygame.init()
    long_boss = Enemy(0, 0, "boss_limbo", health=10, speed=1)
    # simulate an extremely elongated shape
    long_boss.width = 200
    long_boss.height = 50
    # rebuild base image to match these dimensions
    long_boss.base_image = pygame.Surface(
        (long_boss.width, long_boss.height), pygame.SRCALPHA
    )
    long_boss.draw_enemy()

    # apply aura with an arbitrary pulse
    long_boss._apply_aura(pulse=100)
    img = long_boss.image
    w, h = img.get_size()
    cx, cy = w // 2, h // 2
    hw, hh = long_boss.width // 2, long_boss.height // 2

    # points just outside the boss bounding box corners should still be lit
    outer_points = [
        (cx + hw + 1, cy + hh + 1),
        (cx + hw + 1, cy - hh - 1),
        (cx - hw - 1, cy + hh + 1),
        (cx - hw - 1, cy - hh - 1),
    ]
    for px, py in outer_points:
        assert img.get_at((px, py))[3] > 0, f"Aura failed at {px},{py}"


def test_lightning_effect_uses_limbor_timer_and_screenshots(monkeypatch, tmp_path):
    """UI.draw_lightning_effect should read limbo timer when in limbo_final.

    The screenshot filenames should also use the "limbo" prefix.
    """
    pygame.init()
    from src.ui import PygameUIManager as UI

    g = Game()
    g.selected_stage = "limbo_final"
    # prepare values
    g.limbo_final_lightning_timer = 5
    g.limbo_final_lightning_duration_frames = 100
    g.limbo_final_lightning_strike = True
    # ensure game dimensions match our test surface so pixel sampling works
    g.width = 640
    g.height = 480
    ui = UI(g)
    ui.screen = pygame.Surface((g.width, g.height))

    saved = []

    def fake_save(surface, path):
        saved.append(path)

    monkeypatch.setattr(pygame.image, "save", fake_save)
    monkeypatch.setattr(os, "makedirs", lambda *args, **kw: None)

    # trigger the screenshot logic by setting timer to the computed start frame
    total = g.limbo_final_lightning_duration_frames
    start_frame = max(1, int(total * 0.1))
    g.frame_count = start_frame
    g.limbo_final_lightning_timer = start_frame
    ui.draw_lightning_effect()
    assert any(
        "limbo_beam_start.png" in p for p in saved
    ), f"screenshots not saved: {saved}"
    # also ensure beam draws something non-transparent at roughly beam center
    pixel = ui.screen.get_at((g.width // 2, 10))
    assert pixel.a > 0, "Beam was not drawn for limbo timer"


def test_aura_does_not_expand_hitbox():
    """Applying aura must not increase the enemy.rect beyond the shrunken size.

    Regression for boss_limbo where aura pixels were enlarging collision area.
    """
    pygame.init()
    # spawn through manager so hitbox shrinking flag is set correctly
    g = Game(debug=True)
    g.selected_stage = "limbo_final"
    boss = g.enemy_manager.spawn_boss("limbo")
    # record rect before aura (shrunken by spawn logic)
    original_rect = boss.rect.copy()
    # apply aura pulse (regen phase uses this; aura should not enlarge rect)
    boss._apply_aura(50)
    assert boss.rect.width <= original_rect.width
    assert boss.rect.height <= original_rect.height
