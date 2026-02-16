import pygame

from src.projectile import Projectile


def test_skull_bomb_draw_with_fire_particles_does_not_crash():
    pygame.init()
    surf = pygame.Surface((128, 128))
    p = Projectile(64, 64, 0, 0, damage=10, radius=11, weapon_type="skull_bomb")

    # Should not raise
    p.draw(surf)
