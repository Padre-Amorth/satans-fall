import pygame

from src.projectile import Projectile


def test_default_projectile_segment():
    pygame.init()
    # create a default projectile (no weapon_type, player shot)
    p = Projectile(0, 0, 1, 0, damage=1, radius=5, is_enemy_projectile=False)
    # image should not be fully transparent
    w, h = p.image.get_size()
    non_trans = False
    colors = set()
    for x in range(w):
        for y in range(h):
            c = p.image.get_at((x, y))
            ct = tuple(c)
            colors.add(ct)
            if ct[3] != 0:
                non_trans = True
    assert non_trans, "Projectile image should contain visible pixels"
    # check presence of white/light-blue color
    assert any(c[:3] in [(255, 255, 255), (200, 255, 255)] for c in colors)

    # enemy projectiles from normal enemies should be yellow
    p2 = Projectile(0, 0, 0, 1, damage=1, radius=5, is_enemy_projectile=True, appearance="enemy_normal")
    colors2 = set(tuple(p2.image.get_at((x, y))) for x in range(w) for y in range(h))
    assert any(c[:3] == (255, 200, 0) for c in colors2), "Enemy normal projectile should be yellow"

    # only archer appearance uses the segment
    p3 = Projectile(0, 0, 1, 1, damage=1, radius=5, is_enemy_projectile=True, appearance="archer_segment")
    colors3 = set(tuple(p3.image.get_at((x, y))) for x in range(w) for y in range(h))
    assert any(c[:3] == (200, 255, 255) for c in colors3), "Archer projectile should be light-cyan"
