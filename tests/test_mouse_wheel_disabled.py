import os
import sys

import pygame

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from game import Game


def test_mouse_wheel_ignored_in_pause_menu():
    g = Game()
    g.showing_stage_menu = False
    g.paused = True
    g.pause_menu_option = 1

    # Mouse wheel click should not change selection
    g.handle_mouse_click((0, 0), 4)
    g.handle_mouse_click((0, 0), 5)
    assert g.pause_menu_option == 1

    # Posting a MOUSEWHEEL event should also be ignored
    ev_up = pygame.event.Event(pygame.MOUSEWHEEL, {"y": 1})
    ev_down = pygame.event.Event(pygame.MOUSEWHEEL, {"y": -1})
    pygame.event.post(ev_up)
    pygame.event.post(ev_down)
    g.handle_events()
    assert g.pause_menu_option == 1


def test_mouse_wheel_ignored_in_player_stats():
    g = Game()
    g.showing_stage_menu = False
    g.showing_player_stats = True
    g.paused = True

    # Wheel clicks should be ignored (no change to state)
    g.handle_mouse_click((0, 0), 4)
    g.handle_mouse_click((0, 0), 5)
    assert g.showing_player_stats is True
    assert g.paused is True

    # Posting a MOUSEWHEEL event should not close the stats or unpause
    ev = pygame.event.Event(pygame.MOUSEWHEEL, {"y": 1})
    pygame.event.post(ev)
    g.handle_events()
    assert g.showing_player_stats is True
    assert g.paused is True
