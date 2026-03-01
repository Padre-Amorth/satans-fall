#!/usr/bin/env python3
"""Test limbo horde boss taking damage from projectiles."""

import os
import sys

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame
from src.game import Game
from src.projectile import Projectile


def test_horde_boss_damage():
    """Test if horde boss takes damage."""
    g = Game(debug=True)
    g.fps = 60
    g.selected_stage = "limbo"

    print("[TEST] Starting limbo game")

    # Initialize player
    if g.player:
        g.player.x = 640
        g.player.y = 350

    # Disable stage start countdown
    g.stage_start_countdown = 0
    g.stage_start_timer = 0

    # Manually set horde state
    g.limbo_horde_started = True
    g.limbo_horde_active = True
    g.limbo_horde_completed = False
    g.limbo_horde_boss_killed = False
    g.limbo_horde_ready_for_victory = False
    g.limbo_horde_schedule = []  # Empty schedule so spawn_system doesn't try to use it
    g.limbo_horde_phase_index = 0

    print("[TEST] Horde state initialized")

    # Spawn boss
    g.spawn_system.spawn_boss("limbo_horde")
    print(f"[TEST] Boss spawned. Bosses count: {len(g.bosses)}")

    if g.bosses:
        boss = list(g.bosses)[0]
        print(f"[TEST] Boss type: {boss.enemy_type}, Health: {boss.health}, Max: {boss.max_health}")

        initial_health = boss.health

        # Do one update first to let the game settle
        print("[TEST] Doing 1 initial update...")
        g.update_game()
        print(f"  After initial update: enemies={len(g.enemies)}, bosses={len(g.bosses)}")

        # Create a projectile at boss position AFTER initial update
        projectile = Projectile(
            x=boss.x,
            y=boss.y,
            vel_x=0,
            vel_y=0,
            damage=100,  # 100 damage per projectile
            weapon_type="beam"
        )
        g.projectiles.add(projectile)
        print(f"[TEST] Created projectile at boss position ({boss.x}, {boss.y})")
        print(f"[TEST] Projectile has rect: {hasattr(projectile, 'rect')}")
        print(f"[TEST] Projectiles group size: {len(g.projectiles)}")
        print(f"[TEST] Bosses group size: {len(g.bosses)}")

        # Do updates to trigger collision (use update_game() which handles menus)
        print("[TEST] Doing 3 updates to trigger collision and damage...")
        for i in range(3):
            g.update_game()
            boss_health = boss.health if boss in g.bosses else "DEAD/REMOVED"
            proj_count = len(g.projectiles)
            print(f"  Update {i}: boss_health={boss_health}, proj={proj_count}, enemies={len(g.enemies)}, bosses={len(g.bosses)}, timer={getattr(g, 'limbo_horde_victory_timer', 0)}")

        # Also try manual collision check
        print("\n[TEST] Manually calling handle_collisions()...")
        g.collision_system.handle_collisions()
        boss_health = boss.health if boss in g.bosses else "DEAD/REMOVED"
        print(f"[TEST] After manual collision: boss_health={boss_health}, bosses={len(g.bosses)}")

        # Check if boss took damage
        if boss not in g.bosses:
            print(f"\n[TEST] SUCCESS: Boss died and was removed (victory timer: {getattr(g, 'limbo_horde_victory_timer', 0)})")
            return getattr(g, "limbo_horde_victory_timer", 0) > 0
        elif boss.health < initial_health:
            print(f"\n[TEST] Boss took damage: {initial_health} -> {boss.health}")
            return True
        else:
            print(f"\n[TEST] FAILURE: Boss did not take damage! Health: {boss.health}")
            return False
    else:
        print("[TEST] FAILURE: Boss not spawned")
        return False


if __name__ == "__main__":
    success = test_horde_boss_damage()
    sys.exit(0 if success else 1)
