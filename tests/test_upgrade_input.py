import pygame

from src.game import Game


def test_upgrade_input_methods():
    g = Game()
    # Simulate in-game state
    g.showing_stage_menu = False
    g.show_upgrades()

    # Arrow keys should not change selection
    initial_index = g.selected_upgrade_index
    g.handle_keydown(pygame.K_UP)
    g.handle_keydown(pygame.K_DOWN)
    assert g.selected_upgrade_index == initial_index

    # Enter/Space should not apply
    old_awaiting = g.awaiting_upgrade
    g.handle_keydown(pygame.K_RETURN)
    g.handle_keydown(pygame.K_SPACE)
    assert g.awaiting_upgrade == old_awaiting

    # 1-3 keys should apply and close the upgrade menu
    g.show_upgrades()
    g.handle_keydown(pygame.K_1)
    assert not g.awaiting_upgrade and not g.paused


def test_mouse_wheel_ignored_in_upgrades():
    g = Game()
    g.showing_stage_menu = False
    g.show_upgrades()

    # Save current index and ensure wheel up/down doesn't affect it
    initial_index = g.selected_upgrade_index
    # Simulate wheel up (button 4) and wheel down (button 5)
    g.handle_mouse_click((0, 0), 4)
    g.handle_mouse_click((0, 0), 5)
    assert g.selected_upgrade_index == initial_index
    assert g.awaiting_upgrade
