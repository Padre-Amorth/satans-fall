import os

from src.game import Game


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def test_no_towers_drawn_in_prologo(tmp_path):
    setup_dummy_sdl()
    g = Game()

    # Towers may not be created until a tower choice is applied; that's
    # fine as long as Prologo never draws them.  (previous versions created
    # placeholders during initialization, so some tests relied on their
    # existence.)
    # no explicit assertion on presence / absence here

    g.select_stage("prologo")

    # Clear enemies/bosses/projectiles so nothing overlaps tower area
    g.enemies = []
    g.bosses = []
    g.projectiles.empty()
    g.enemy_projectiles.empty()

    # Sample pixel at expected left tower head location before drawing
    # If a tower object exists, sample at its head position; otherwise pick
    # a safe location (top-left corner) that will never show statue colors.
    if g.left_tower is not None:
        tx = int(g.left_tower.x)
        ty = int(g.left_tower.y - 8)
    else:
        tx, ty = 0, 0
    before = tuple(g.screen.get_at((tx, ty))[:3])

    # Draw game objects in Prologo
    g.ui.draw_game_objects()

    after = tuple(g.screen.get_at((tx, ty))[:3])

    # Color used by statue model for fire body is (58,10,10) - ensure it's NOT present
    assert after != (58, 10, 10), f"Found statue color in Prologo at {tx},{ty}: {after}"
    # And if we sampled a real tower location, the pixel should remain unchanged
    if g.left_tower is not None:
        assert after == before
