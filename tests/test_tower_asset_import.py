import pygame

from src.game import Game


def test_statue_model_uses_asset_if_available(monkeypatch):
    """UI helper should attempt to load a named image for each tower type.

    Patching the shared asset manager lets us verify the filename requested
    and ensures the image that is returned is blitted without error.
    """
    pygame.init()
    calls = []

    def fake_get_image(name, size=None):
        calls.append((name, size))
        # return a small dummy surface so blitting is exercised
        return pygame.Surface((10, 10))

    # monkeypatch the same function that ui._draw_statue_model will import
    monkeypatch.setattr("src.assets.manager.get_image", fake_get_image)

    g = Game()
    # draw onto a fresh surface for each invocation just to ensure no state leak
    for tt in ["fire", "storm", "ice"]:
        g.screen = pygame.Surface((200, 200))
        # call the helper directly; coordinates don't matter since we aren't
        # verifying pixels here
        g.ui._draw_statue_model(100, 150, tt)
        # ensure our fake was called with the expected name
        assert any(
            name == f"statue_{tt}.png" for name, _ in calls
        ), f"Expected statue_{tt}.png to be requested, got {calls}"
        # size argument should normally be None since we don't scale
        for name, size in calls:
            if name.startswith("statue_"):
                assert size is None, "get_image should be called without a size"
        calls.clear()

    # also verify that a stage string without an explicit tower_type maps
    # correctly (limbo_2 -> storm, limbo_3 -> ice)
    g.screen = pygame.Surface((200, 200))
    g.selected_stage = "limbo_2"
    g.ui._draw_statue_model(100, 150, None)
    assert any(name == "statue_storm.png" for name, _ in calls)
    calls.clear()
    g.selected_stage = "limbo_3"
    g.ui._draw_statue_model(100, 150, None)
    assert any(name == "statue_ice.png" for name, _ in calls)
    calls.clear()
    g.selected_stage = "limbo_final"
    g.ui._draw_statue_model(100, 150, None)
    assert any(name == "statue_ice.png" for name, _ in calls)
    calls.clear()

    # finally check that vertical offset constant is applied when non-zero
    import src.ui as ui_module
    from src import game_constants

    # default constant should be reasonable so that imported assets are
    # visible; this guards against regressions. assert non-negative value.
    assert game_constants.STATUE_ASSET_VERTICAL_OFFSET >= 0

    # patch both modules so the helper picks up the new value
    monkeypatch.setattr(game_constants, "STATUE_ASSET_VERTICAL_OFFSET", 100)
    monkeypatch.setattr(ui_module, "STATUE_ASSET_VERTICAL_OFFSET", 100)
    # simply exercise drawing with the new offset to ensure no errors
    g.screen = pygame.Surface((200, 200))
    g.ui._draw_statue_model(100, 150, "fire")
    # flip behaviour is tested elsewhere; no need to capture blits here.


def test_statue_model_fallback_when_asset_missing(monkeypatch):
    """If the image isn't available the routine should still draw shapes.

    In addition to exercising the no-error path we verify that the global
    vertical offset constant is respected even when the fallback vector art is
    drawn.  Previously the offset only applied to imported assets, leading to
    inconsistent positioning between stages.
    """
    pygame.init()
    # make get_image always return None to simulate missing files
    monkeypatch.setattr("src.assets.manager.get_image", lambda name, size=None: None)

    g = Game()
    g.screen = pygame.Surface((200, 200))

    # record drawing coords for polygons / circles so we can assert offset
    poly_calls = []
    circle_calls = []
    monkeypatch.setattr(
        pygame.draw, "polygon", lambda surf, color, pts, width=0: poly_calls.append(pts)
    )
    monkeypatch.setattr(
        pygame.draw,
        "circle",
        lambda surf, color, center, radius, width=0: circle_calls.append(center),
    )

    # use an offset value that is easy to spot
    import src.ui as ui_module
    from src import game_constants

    monkeypatch.setattr(game_constants, "STATUE_ASSET_VERTICAL_OFFSET", 42)
    monkeypatch.setattr(ui_module, "STATUE_ASSET_VERTICAL_OFFSET", 42)
    # selecting a stage influences colour logic but isn't necessary here
    # the call should simply complete without error regardless of type
    for tt in ["fire", "storm", "ice", None]:
        poly_calls.clear()
        circle_calls.clear()
        g.ui._draw_statue_model(100, 150, tt)
        # the body points should reflect the applied offset.  the first
        # vertex of the body polygon is at (x, adjusted_base_y - 60).
        expected_y = 150 + 42 - 60
        assert any(
            pts[0][1] == expected_y for pts in poly_calls
        ), f"offset not applied in polygon for tt={tt}: {poly_calls}"
        # head circle center y also expects 192-70 = 122
        assert any(
            c[1] == 122 for c in circle_calls
        ), f"offset not applied for head circle for tt={tt}: {circle_calls}"
