from src.game import Game


def test_no_duplicate_left_tower_in_limbo():
    g = Game()
    g.select_stage("limbo")

    # left tower pos
    tx = int(g.left_tower.x)
    head_y_dynamic = int(g.left_tower.y - 8)

    # pedestal head pos (hard-coded based on draw_pedestals values)
    ped_y = 620
    statue_head_y = ped_y - 10 - 70  # statue_base_y - 70

    # Colors
    statue_body_color = (58, 10, 10)

    # Draw pedestals (Limbo static statues) then draw game objects
    g.ui.draw_pedestals()
    g.ui.draw_game_objects()

    # Pedestal should contain statue color
    ped_pixel = tuple(g.screen.get_at((int(320), int(statue_head_y)))[:3])
    assert (
        ped_pixel == statue_body_color
    ), f"Expected pedestal statue body color at pedestal head, found {ped_pixel}"

    # Dynamic tower (the 'extra' should not be drawn above the pedestal)
    dyn_pixel = tuple(g.screen.get_at((tx, head_y_dynamic))[:3])
    assert (
        dyn_pixel != statue_body_color
    ), f"Unexpected extra dynamic statue at {tx},{head_y_dynamic}: {dyn_pixel}"
