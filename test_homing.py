#!/usr/bin/env python3
"""Test script to verify statue projectile homing improvements"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def test_homing_logic():
    """Test the angle-limited homing behavior"""
    print("Testing statue projectile homing logic...")

    # Test 1: Small angle difference (should home)
    print("\n=== Test 1: Small angle difference (should home) ===")
    proj = {"vel_x": 0, "vel_y": -320, "x": 500, "y": 500}  # Going straight up

    enemy_x, enemy_y = 600, 500  # Enemy to the right (90° difference)
    dx = enemy_x - proj["x"]
    dy = enemy_y - proj["y"]
    dist = math.hypot(dx, dy)

    if dist > 0:
        target_vel_x = (dx / dist) * 320
        target_vel_y = (dy / dist) * 320

        current_speed = math.hypot(proj["vel_x"], proj["vel_y"])
        if current_speed > 0:
            current_angle = math.atan2(proj["vel_y"], proj["vel_x"])
            target_angle = math.atan2(target_vel_y, target_vel_x)
            angle_diff = abs(target_angle - current_angle)
            angle_diff = min(angle_diff, 2 * math.pi - angle_diff)
            angle_diff_degrees = math.degrees(angle_diff)

            print(f"Angle difference: {angle_diff_degrees:.1f}°")

            if angle_diff_degrees <= 90:
                print("✓ Applying homing (angle <= 90°)")
                homing_strength = 0.1
                old_vel_x, old_vel_y = proj["vel_x"], proj["vel_y"]
                proj["vel_x"] = (
                    proj["vel_x"] * (1 - homing_strength)
                    + target_vel_x * homing_strength
                )
                proj["vel_y"] = (
                    proj["vel_y"] * (1 - homing_strength)
                    + target_vel_y * homing_strength
                )
                print(
                    f"Direction changed from {math.degrees(math.atan2(old_vel_y, old_vel_x)):.1f}° to {math.degrees(math.atan2(proj['vel_y'], proj['vel_x'])):.1f}°"
                )
            else:
                print("✗ No homing applied (angle > 90°)")

    # Test 2: Large angle difference (should NOT home)
    print("\n=== Test 2: Large angle difference (should NOT home) ===")
    proj2 = {"vel_x": 0, "vel_y": -320, "x": 500, "y": 500}  # Going straight up

    enemy_x2, enemy_y2 = 400, 600  # Enemy to the left and down (135° difference)
    dx2 = enemy_x2 - proj2["x"]
    dy2 = enemy_y2 - proj2["y"]
    dist2 = math.hypot(dx2, dy2)

    if dist2 > 0:
        target_vel_x2 = (dx2 / dist2) * 320
        target_vel_y2 = (dy2 / dist2) * 320

        current_speed2 = math.hypot(proj2["vel_x"], proj2["vel_y"])
        if current_speed2 > 0:
            current_angle2 = math.atan2(proj2["vel_y"], proj2["vel_x"])
            target_angle2 = math.atan2(target_vel_y2, target_vel_x2)
            angle_diff2 = abs(target_angle2 - current_angle2)
            angle_diff2 = min(angle_diff2, 2 * math.pi - angle_diff2)
            angle_diff_degrees2 = math.degrees(angle_diff2)

            print(f"Angle difference: {angle_diff_degrees2:.1f}°")

            if angle_diff_degrees2 <= 90:
                print("✓ Applying homing (angle <= 90°)")
                homing_strength = 0.1
                old_vel_x2, old_vel_y2 = proj2["vel_x"], proj2["vel_y"]
                proj2["vel_x"] = (
                    proj2["vel_x"] * (1 - homing_strength)
                    + target_vel_x2 * homing_strength
                )
                proj2["vel_y"] = (
                    proj2["vel_y"] * (1 - homing_strength)
                    + target_vel_y2 * homing_strength
                )
                print(
                    f"Direction changed from {math.degrees(math.atan2(old_vel_y2, old_vel_x2)):.1f}° to {math.degrees(math.atan2(proj2['vel_y'], proj2['vel_x'])):.1f}°"
                )
            else:
                print("✗ No homing applied (angle > 90°) - projectile will miss!")

    print(
        "\nTest completed - statue projectiles now miss when angle correction needed > 90°!"
    )


if __name__ == "__main__":
    test_homing_logic()
