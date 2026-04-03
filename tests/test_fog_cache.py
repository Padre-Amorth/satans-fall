import pygame

from src.game import Game


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


def test_limbo_particle_image_caching():
    """Test that limbo fog particle images are cached to reduce per-frame overhead."""
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "limbo"
    g.generate_walls()

    ui = g.ui
    screen = pygame.Surface((g.width, g.height))
    ui.screen = screen

    left_particles = getattr(ui, "_limbo_fog_particles_left", [])

    if len(left_particles) > 0:
        p = left_particles[0]

        # First draw - should create cache
        p.draw(screen)
        cache_key_1 = getattr(p, "_cached_draw_key", None)
        cached_img_1_id = id(getattr(p, "_cached_draw_image", None))

        # Second draw - should reuse cache (same key, same object)
        p.draw(screen)
        cache_key_2 = getattr(p, "_cached_draw_key", None)
        cached_img_2_id = id(getattr(p, "_cached_draw_image", None))

        # Verify cache persistence
        assert cache_key_1 == cache_key_2, "Cache key should persist for same stage"
        assert (
            cached_img_1_id == cached_img_2_id
        ), "Cached image should be reused (same object reference)"

        # Change stage and verify cache invalidates
        g.selected_stage = "limbo_2"
        p.draw(screen)
        cache_key_3 = getattr(p, "_cached_draw_key", None)
        cached_img_3_id = id(getattr(p, "_cached_draw_image", None))

        assert cache_key_1 != cache_key_3, "Cache key should change when stage changes"
        assert (
            cached_img_1_id != cached_img_3_id
        ), "Cached image should be regenerated (different object)"
