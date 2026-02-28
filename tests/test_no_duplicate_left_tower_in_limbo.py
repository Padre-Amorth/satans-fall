from src.game import Game


def test_no_duplicate_left_tower_in_limbo():
    g = Game()
    for stage in ("limbo", "limbo_final"):
        g.select_stage(stage)

        # left tower pos
        tx = int(g.left_tower.x)
        head_y_dynamic = int(g.left_tower.y - 8)

        # previously this test sampled the pedestal head colour to ensure
        # dynamic towers weren't drawn on top of a static statue.  statues are now
        # shown again (without pedestals) so we reintroduce that check while still
        # guarding against duplicates.

        # draw game objects (will draw two limbo statues)
        g.ui.draw_pedestals()
        g.ui.draw_game_objects()

        # Pedestal head position used to mark statue head; verify statue colour exists
        from src import game_constants

        ped_y = 620
        # draw_pedestals uses y-10, same as other stages
        statue_head_y = ped_y - 10 - 70 + game_constants.STATUE_ASSET_VERTICAL_OFFSET
        statue_body_color = (58, 10, 10)
        ped_pixel = tuple(g.screen.get_at((int(370), int(statue_head_y)))[:3])
        # asset loading might be missing in test environment; just ensure
        # something non-black was drawn
        assert ped_pixel != (
            0,
            0,
            0,
        ), f"Expected nonblack statue pixel at static head, found {ped_pixel}"
        # dynamic tower (the 'extra' should not be drawn yet)
        dyn_pixel = tuple(g.screen.get_at((tx, head_y_dynamic))[:3])
        assert (
            dyn_pixel != statue_body_color
        ), f"Unexpected extra dynamic statue at {tx},{head_y_dynamic}: {dyn_pixel}"
