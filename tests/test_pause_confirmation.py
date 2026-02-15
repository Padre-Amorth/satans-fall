import os
import sys

import pygame

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from game import Game


def test_quit_confirmation_yes():
    g = Game()
    g.select_stage("limbo")
    g.paused = True
    g.pause_menu_option = 1  # Quit to Menu
    g.execute_pause_option()
    assert g.pause_confirmation and g.pause_confirmation["action"] == "quit"

    # Confirm quit
    g.handle_keydown(pygame.K_RETURN)
    assert g.pause_confirmation is None
    # After quitting, we should be back in the stage menu
    assert g.showing_stage_menu is True
    assert g.selected_stage is None


def test_quit_confirmation_no():
    g = Game()
    g.select_stage("limbo")
    g.paused = True
    g.pause_menu_option = 1
    g.execute_pause_option()
    assert g.pause_confirmation

    # Select No
    g.handle_keydown(pygame.K_RIGHT)
    g.handle_keydown(pygame.K_RETURN)
    assert g.pause_confirmation is None
    assert g.paused is True
    assert g.showing_stage_menu is False


def test_quit_confirmation_click_no():
    g = Game()
    g.select_stage("limbo")
    g.paused = True
    g.pause_menu_option = 1  # Quit
    g.execute_pause_option()
    assert g.pause_confirmation and g.pause_confirmation["action"] == "quit"

    # Click No (center-right of dialog)
    dialog_w, dialog_h = 260, 70
    dx = g.width // 2 - dialog_w // 2
    dy = g.height // 2 - dialog_h // 2
    btn_w = 80
    btn_h = 28
    no_pos = (dx + dialog_w - btn_w - 10 + btn_w // 2, dy + 30 + btn_h // 2)
    g.handle_mouse_click(no_pos, 1)

    assert g.pause_confirmation is None
    # Should remain paused and still in-stage
    assert g.paused is True
    assert g.showing_stage_menu is False
