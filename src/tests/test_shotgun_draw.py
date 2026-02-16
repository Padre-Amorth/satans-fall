import pygame

from src.projectile import Projectile


def test_shotgun_draw_does_not_crash():
    pygame.init()
    surf = pygame.Surface((64, 64))
    p = Projectile(32, 32, 0, 0, damage=10, radius=6, weapon_type="shotgun")

    # Should not raise
    p.draw(surf)


def test_shotgun_draw_center_pixel_is_dark_yellow():
    pygame.init()
    surf = pygame.Surface((128, 128))
    p = Projectile(64, 64, 0, 0, damage=10, radius=6, weapon_type="shotgun")

    p.draw(surf)
    cx, cy = p.rect.center
    col = surf.get_at((int(cx), int(cy)))

    # Expect a yellow-ish pixel with stronger red channel and moderate green
    assert col.r >= 180 and col.g >= 110 and col.b <= 100, f"unexpected color {col}"
