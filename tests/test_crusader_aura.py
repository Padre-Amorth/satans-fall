import pygame

from src.entities.enemy import Enemy


def test_crusader_aura_draws_when_invulnerable(monkeypatch):
    pygame.init()
    # we'll inspect pixel colors on the surface after drawing

    c = Enemy(50, 50, enemy_type="crusader", health=100, speed=30)
    # ensure rect defined for centering
    c.rect = pygame.Rect(50 - c.width // 2, 50 - c.height // 2, c.width, c.height)
    surf = pygame.Surface((200, 200))

    # when not invulnerable, there should be no light-blue pixels outside sprite bounds
    c.invulnerable = False
    c.draw(surf)
    cx, cy = 50, 50
    r = max(c.width, c.height) // 2 + 6
    # sample a point just outside the sprite radius
    px = cx + r - 1  # one pixel inside the filled circle
    py = cy
    assert surf.get_at((px, py))[0:3] != (100, 150, 255)

    # turn invulnerable on and draw again
    c.invulnerable = True
    surf.fill((0, 0, 0, 0))
    c.draw(surf)
    # now that pixel should be tinted light blue (alpha blended)
    col = surf.get_at((px, py))
    # should not be transparent/black, and blue component should dominate
    assert col[0:3] != (0, 0, 0), f"expected some color, got {col}"
    assert col[2] >= col[0] and col[2] >= col[1], f"expected bluish tint, got {col}"

    # disable and ensure it disappears
    c.invulnerable = False
    surf.fill((0, 0, 0, 0))
    c.draw(surf)
    col2 = surf.get_at((px, py))
    assert not (col2[0] >= 90 and col2[1] >= 140 and col2[2] >= 240)
