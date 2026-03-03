"""Tests for Orbital projectile appearance (light blue circles)"""

import pygame

from src.projectile import Projectile


def test_orbital_projectile_color():
    """Orbital projectiles should be light blue with dark blue inner ring"""
    pygame.init()

    # Create an orbital projectile
    p = Projectile(100, 100, vel_x=50, vel_y=50, damage=15, radius=4, source="orbital")

    # Check that the projectile was drawn
    assert p.image is not None, "Projectile image should be created"

    # Get dimensions
    w, h = p.image.get_size()
    assert (
        w == 8 and h == 8
    ), f"Orbital projectile should be 8x8 (radius 4), got {w}x{h}"

    # Sample center pixel - should be dark blue (51, 170, 255) from inner circle
    center_color = p.image.get_at((4, 4))
    # Colors: outer light blue (102, 204, 255), inner dark blue (51, 170, 255)
    # Center should be dark blue or mix depending on overlap
    assert center_color[2] == 255, "Blue channel should be 255"
    # Accept either light or dark blue center (depending on exact pixel position)
    is_light_blue = center_color[0] > 90 and center_color[1] > 190
    is_dark_blue = center_color[0] < 70 and center_color[1] < 180
    assert (
        is_light_blue or is_dark_blue
    ), f"Should be light or dark blue, got {center_color[:3]}"


def test_orbital_projectile_not_arrow():
    """Orbital projectiles should NOT be drawn as archer arrows"""
    pygame.init()

    # Create an orbital projectile
    p = Projectile(100, 100, vel_x=50, vel_y=50, damage=15, radius=4, source="orbital")

    # If it was an archer arrow, it would be much smaller (height ~2 for radius 4)
    # Orbital should be square (8x8)
    w, h = p.image.get_size()
    assert w == h, "Orbital should be square, not a thin segment"
    assert h >= 8, "Orbital should be at least 8px tall"


def test_orbital_projectile_distinct_from_archer():
    """Orbital projectile appearance should be different from archer projectile"""
    pygame.init()

    # Orbital projectile
    orbital = Projectile(
        100, 100, vel_x=50, vel_y=50, damage=15, radius=4, source="orbital"
    )

    # Archer projectile
    archer = Projectile(
        100,
        100,
        vel_x=50,
        vel_y=50,
        damage=12,
        radius=5,
        is_enemy_projectile=True,
        appearance="archer_segment",
    )

    # Sizes should be different
    orbital_size = orbital.image.get_size()
    archer_size = archer.image.get_size()

    # Orbital: 8x8 (square)
    # Archer: ~12x2 (thin horizontal line)
    assert orbital_size[0] == orbital_size[1], "Orbital should be square"
    assert archer_size[1] < archer_size[0], "Archer should be wider than tall"


def test_orbital_projectile_radius_scaling():
    """Orbital projectiles with different radii should scale correctly"""
    pygame.init()

    # Small orbital (radius 3)
    small = Projectile(
        100, 100, vel_x=50, vel_y=50, damage=15, radius=3, source="orbital"
    )

    # Large orbital (radius 6)
    large = Projectile(
        100, 100, vel_x=50, vel_y=50, damage=15, radius=6, source="orbital"
    )

    small_size = small.image.get_size()
    large_size = large.image.get_size()

    # Small should be 6x6, large should be 12x12
    assert small_size == (6, 6), f"Small orbital should be 6x6, got {small_size}"
    assert large_size == (12, 12), f"Large orbital should be 12x12, got {large_size}"
