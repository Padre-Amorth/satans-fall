import math

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
    # If base image exists, the image should have been modified (at least one pixel differs)
    if getattr(boss, "base_image", None) is not None:
        base_px = boss.base_image.get_at((50, 50))  # Original size center
        cur_px = boss.image.get_at((boss.width // 2, boss.height // 2))
        assert base_px != cur_px, "Boss image did not change to show shine overlay"
