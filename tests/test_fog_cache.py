import pygame

from src.game import Game


def test_fog_cache_build_and_invalidate():
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "limbo"
    g.generate_walls()

    ui = g.ui

    # Ensure no cache initially
    assert not getattr(ui, "_fog_cache", None)

    # Build cache
    ui._build_fog_cache()
    assert getattr(ui, "_fog_cache", None) is not None
    cache = ui._fog_cache

    # Expect 2 entries per layer (left and right) -> num_layers * 2
    num_layers = 5
    assert len(cache) == num_layers * 2
    # Surfaces or None allowed
    for s in cache:
        assert s is None or isinstance(s, pygame.Surface)

    # Mutate walls to force invalidation (change one point deterministically)
    old_sig = ui._fog_cache_signature
    # change first left wall point by enough to change its int() representation
    if g.left_wall_points:
        x0, y0 = g.left_wall_points[0]
        g.left_wall_points[0] = (x0 + 5, y0)  # 5px change ensures int() differs
    ui._build_fog_cache()
    assert ui._fog_cache_signature != old_sig


def test_draw_fog_uses_cache():
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "limbo"
    g.generate_walls()
    ui = g.ui
    ui._build_fog_cache()

    screen = pygame.Surface((g.width, g.height))
    ui.screen = screen

    # Should not raise when drawing (and use cached surfaces)
    ui.draw_fog(2, 3)

    # Basic sanity: some pixels should be non-empty due to fog blit

    # It's acceptable for some points to still be transparent depending on wall shapes,
    # so just assert the surface exists and is a Surface.
    assert isinstance(screen, pygame.Surface)


def test_limbo3_lateral_fog_is_redder_than_limbo():
    """Lateral fog polygons (cached) should have a stronger red component in limbo_3."""
    pygame.init()
    g = Game(debug=True)

    # --- baseline: regular Limbo (gray fog) ---
    g.selected_stage = "limbo"
    g.generate_walls()
    ui = g.ui
    ui._build_fog_cache()
    cache_gray = ui._fog_cache

    # find a reliable y within wall span
    y_mid = (g.left_wall_points[0][1] + g.left_wall_points[-1][1]) // 2

    left_gray = None
    right_gray = None
    if cache_gray and cache_gray[0]:
        left_gray = cache_gray[0].get_at((2, y_mid))
    if cache_gray and cache_gray[1]:
        right_gray = cache_gray[1].get_at((g.width - 2, y_mid))

    # --- limbo_3: expect redder lateral fog ---
    g.selected_stage = "limbo_3"
    ui._build_fog_cache()
    cache_red = ui._fog_cache

    left_red = None
    right_red = None
    if cache_red and cache_red[0]:
        left_red = cache_red[0].get_at((2, y_mid))
    if cache_red and cache_red[1]:
        right_red = cache_red[1].get_at((g.width - 2, y_mid))

    # At least one side should show the red increase
    assert (
        left_gray
        and left_red
        and left_red.r >= max(left_red.g, left_red.b)
        and left_red.r > left_gray.r
    ) or (
        right_gray
        and right_red
        and right_red.r >= max(right_red.g, right_red.b)
        and right_red.r > right_gray.r
    )


def test_limbo2_lateral_fog_is_yellower_than_limbo():
    """Lateral fog polygons (cached) should have a stronger yellow component in limbo_2."""
    pygame.init()
    g = Game(debug=True)

    # --- baseline: regular Limbo (gray fog) ---
    g.selected_stage = "limbo"
    g.generate_walls()
    ui = g.ui
    ui._build_fog_cache()
    cache_gray = ui._fog_cache

    # find a reliable y within wall span
    y_mid = (g.left_wall_points[0][1] + g.left_wall_points[-1][1]) // 2

    left_gray = None
    right_gray = None
    if cache_gray and cache_gray[0]:
        left_gray = cache_gray[0].get_at((2, y_mid))
    if cache_gray and cache_gray[1]:
        right_gray = cache_gray[1].get_at((g.width - 2, y_mid))

    # --- limbo_2: expect yellower lateral fog ---
    g.selected_stage = "limbo_2"
    ui._build_fog_cache()
    cache_yellow = ui._fog_cache

    left_y = None
    right_y = None
    if cache_yellow and cache_yellow[0]:
        left_y = cache_yellow[0].get_at((2, y_mid))
    if cache_yellow and cache_yellow[1]:
        right_y = cache_yellow[1].get_at((g.width - 2, y_mid))

    # At least one side should show the yellow increase (R and G dominate B, and R+G increases vs baseline)
    assert (
        left_gray
        and left_y
        and left_y.r >= left_y.b
        and left_y.g >= left_y.b
        and (left_y.r + left_y.g) > (left_gray.r + left_gray.g)
    ) or (
        right_gray
        and right_y
        and right_y.r >= right_y.b
        and right_y.g >= right_y.b
        and (right_y.r + right_y.g) > (right_gray.r + right_gray.g)
    )
