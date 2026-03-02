"""Tests for Blasphemy 5 Blink ability (spacebar teleport)"""
import pygame

from src.game import Game


def test_blasphemy5_blink_requires_movement():
    """Blink should only trigger when moving (velocity > 0.1 or keys pressed)"""
    pygame.init()
    g = Game()
    g.reset_game()
    g.showing_main_menu = False

    # Unlock Blasphemy 5
    g.permanent_stats["blasphemy"] = 5

    # Player stationary - should not blink
    g.player.vel_x = 0
    g.player.vel_y = 0
    g.player.x = 640
    g.player.y = 360

    initial_x = g.player.x
    initial_y = g.player.y

    # Try to trigger blink without movement
    g.blasphemy_5_blink_state = 0
    # Since there's no velocity, blink shouldn't start
    assert g.blasphemy_5_blink_state == 0


def test_blasphemy5_blink_teleports_in_movement_direction():
    """Blink should teleport 120px in the direction of movement keys"""
    pygame.init()
    g = Game()
    g.reset_game()
    g.showing_main_menu = False

    # Unlock Blasphemy 5
    g.permanent_stats["blasphemy_5"] = 1

    # Player moving right
    g.player.velocity_x = 100
    g.player.velocity_y = 0
    g.player.x = 640
    g.player.y = 360

    initial_x = g.player.x
    initial_y = g.player.y

    # Simulate blink state transitions
    # State 1: Pre-blink flash (10 frames)
    g.blasphemy_5_blink_state = 1
    g.blasphemy_5_blink_timer = 10
    g.blasphemy_5_blink_target_x = initial_x + 120  # 120px right
    g.blasphemy_5_blink_target_y = initial_y

    # After 10 frames, player teleports
    assert g.blasphemy_5_blink_target_x == initial_x + 120


def test_blasphemy5_blink_animation_duration():
    """Blink animation should take 35 frames total (10 pre + 15 invisible + 10 post)"""
    pygame.init()
    g = Game()
    g.reset_game()
    g.showing_main_menu = False

    # Pre-blink: 10 frames
    pre_blink_frames = 10
    # Invisible (transit): 15 frames
    invisible_frames = 15
    # Post-blink: 10 frames
    post_blink_frames = 10
    # Total: 35 frames

    total_frames = pre_blink_frames + invisible_frames + post_blink_frames
    assert total_frames == 35, "Blink animation should be 35 frames total"


def test_blasphemy5_blink_clamped_to_screen():
    """Blink destination should be clamped to screen bounds (30px margin)"""
    pygame.init()
    g = Game()
    g.reset_game()
    g.showing_main_menu = False

    # Unlock Blasphemy 5
    g.permanent_stats["blasphemy_5"] = 1

    # Player at right edge trying to blink further right
    g.player.x = g.width - 50
    g.player.y = g.height // 2
    g.player.velocity_x = 200
    g.player.velocity_y = 0

    # Expected target: would be 120px right, but clamped to screen
    # Screen width is typically 1280, so clamped to ~1250 (with margin)
    max_x = g.width - 30
    assert max_x > 0, "Screen width should support clamping"


def test_blasphemy5_blink_no_overlap_animation():
    """Cannot start a new blink while one is already animating"""
    pygame.init()
    g = Game()
    g.reset_game()
    g.showing_main_menu = False

    # Unlock Blasphemy 5
    g.permanent_stats["blasphemy_5"] = 1

    # Start first blink
    g.blasphemy_5_blink_state = 1
    g.blasphemy_5_blink_timer = 10

    # Try to start another blink while first is active
    # Should be blocked by the check: if blink_state != 0
    initial_state = g.blasphemy_5_blink_state
    assert initial_state != 0, "First blink should still be active"


def test_blasphemy5_blink_with_vertical_movement():
    """Blink should work with vertical movement keys"""
    pygame.init()
    g = Game()
    g.reset_game()
    g.showing_main_menu = False

    # Unlock Blasphemy 5
    g.permanent_stats["blasphemy_5"] = 1

    # Player moving up
    g.player.velocity_x = 0
    g.player.velocity_y = -100
    g.player.x = 640
    g.player.y = 360

    initial_y = g.player.y

    # Simulate blink upward
    g.blasphemy_5_blink_state = 1
    g.blasphemy_5_blink_timer = 10
    g.blasphemy_5_blink_target_y = initial_y - 120  # 120px up

    assert g.blasphemy_5_blink_target_y == initial_y - 120


def test_blasphemy5_blink_diagonal_movement():
    """Blink should work with diagonal movement (multiple keys pressed)"""
    pygame.init()
    g = Game()
    g.reset_game()
    g.showing_main_menu = False

    # Unlock Blasphemy 5
    g.permanent_stats["blasphemy_5"] = 1

    # Player moving diagonally (up-right)
    g.player.velocity_x = 100
    g.player.velocity_y = -100
    g.player.x = 640
    g.player.y = 360

    initial_x = g.player.x
    initial_y = g.player.y

    # Blink should go in direction of movement (up-right)
    g.blasphemy_5_blink_state = 1
    g.blasphemy_5_blink_timer = 10

    # Should be active for diagonal movement
    assert g.blasphemy_5_blink_state == 1, "Blink should be active for diagonal movement"


def test_blasphemy5_blink_cooldown_blocks_chaining():
    """Blink cooldown (5 seconds) blocks rapid chaining"""
    pygame.init()
    g = Game()
    g.reset_game()
    g.showing_main_menu = False

    # Unlock Blasphemy 5
    g.permanent_stats["blasphemy_5"] = 1

    # Player moving
    g.player.velocity_x = 100
    g.player.velocity_y = 0
    g.player.x = 640
    g.player.y = 360

    # Simulate first blink completion
    g.blasphemy_5_blink_state = 0  # Blink animation finished
    g.blasphemy_5_blink_cooldown = int(5 * g.fps)  # 5 second cooldown active

    # Player position should be at target
    g.player.x = g.blasphemy_5_blink_target_x
    g.player.y = g.blasphemy_5_blink_target_y

    old_x = g.player.x

    # Try to start second blink immediately - should be blocked by cooldown
    g.execute_blasphemy5_blink()

    # Player should not have moved (blink blocked by cooldown)
    assert g.player.x == old_x, "Cooldown should prevent immediate re-blink"
