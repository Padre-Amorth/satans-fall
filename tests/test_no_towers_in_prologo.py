import os

from src.game import Game


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def test_no_towers_drawn_in_prologo(tmp_path):
    setup_dummy_sdl()
    g = Game(permanent_stats_file=str(tmp_path / "permanent_stats.json"))

    # Ensure left/right towers exist but stage is prologo
    assert getattr(g, "left_tower", None) is not None
    assert getattr(g, "right_tower", None) is not None

    g.select_stage("prologo")

    # Clear enemies/bosses/projectiles so nothing overlaps tower area
    g.enemies = []
    g.bosses = []
    g.projectiles.empty()
    g.enemy_projectiles.empty()

    # Sample pixel at expected left tower head location before drawing
    tx = int(g.left_tower.x)
    ty = int(g.left_tower.y - 8)
    before = tuple(g.screen.get_at((tx, ty))[:3])

    # Draw game objects in Prologo
    g.ui.draw_game_objects()

    after = tuple(g.screen.get_at((tx, ty))[:3])

    # Color used by statue model for fire body is (58,10,10) - ensure it's NOT present
    assert after != (58, 10, 10), f"Found statue color in Prologo at {tx},{ty}: {after}"
    # And preferably didn't change from 'before'
    assert after == before
