#!/usr/bin/env python3
"""Test sprite collision detection directly."""

import os
import sys

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame
from src.game import Game
from src.projectile import Projectile


def test_sprite_collision():
    """Test if spritecollide works with boss and projectile."""
    g = Game(debug=True)
    g.fps = 60
    g.selected_stage = "limbo"

    print("[TEST] Starting collision test")

    # Manually set horde state
    g.limbo_horde_started = True
    g.limbo_horde_active = True
    g.limbo_horde_completed = False
    g.limbo_horde_boss_killed = False
    g.limbo_horde_ready_for_victory = False

    # Spawn boss
    g.spawn_system.spawn_boss("limbo_horde")
    print(f"[TEST] Boss spawned. Bosses count: {len(g.bosses)}")

    if g.bosses:
        boss = list(g.bosses)[0]
        print(f"[TEST] Boss position: ({boss.x}, {boss.y})")
        print(f"[TEST] Boss has rect: {hasattr(boss, 'rect')}")
        if hasattr(boss, 'rect'):
            print(f"[TEST] Boss rect: {boss.rect}")

        # Create a projectile at boss position
        projectile = Projectile(
            x=boss.x,
            y=boss.y,
            vel_x=0,
            vel_y=0,
            damage=100,
            weapon_type="beam"
        )
        g.projectiles.add(projectile)

        print(f"[TEST] Projectile created")
        print(f"[TEST] Projectile position: ({projectile.x}, {projectile.y})")
        print(f"[TEST] Projectile has rect: {hasattr(projectile, 'rect')}")
        if hasattr(projectile, 'rect'):
            print(f"[TEST] Projectile rect: {projectile.rect}")

        # Test spritecollide manually
        print(f"\n[TEST] Testing pygame.sprite.spritecollide manually...")
        hit_bosses = pygame.sprite.spritecollide(projectile, g.bosses, False)
        print(f"[TEST] Manual spritecollide result: {len(hit_bosses)} bosses hit")

        if hit_bosses:
            print(f"[TEST] SUCCESS: Collision detected!")
            for b in hit_bosses:
                print(f"  - Hit boss: {b.enemy_type} at ({b.x}, {b.y})")
            return True
        else:
            print(f"[TEST] FAILURE: No collision detected")
            # Debug: check if rect centers match
            print(f"[TEST] Boss rect center: {boss.rect.center if hasattr(boss, 'rect') else 'N/A'}")
            print(f"[TEST] Projectile rect center: {projectile.rect.center}")
            print(f"[TEST] Distance: {((boss.x - projectile.x)**2 + (boss.y - projectile.y)**2)**0.5}")
            return False
    else:
        print("[TEST] FAILURE: Boss not spawned")
        return False


if __name__ == "__main__":
    success = test_sprite_collision()
    sys.exit(0 if success else 1)
