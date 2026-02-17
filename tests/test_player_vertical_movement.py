import math

import pygame

from src.game import Game


class FakeKeys:
    def __init__(self, pressed_keys: set[int]):
        self.pressed = pressed_keys

    def __getitem__(self, key: int) -> bool:  # support indexing like ScancodeWrapper
        return key in self.pressed


def test_player_vertical_range_initialized():
    g = Game()
    baseline = int(g.height - 80)
    assert g.player_vertical_min_y == baseline - (g.player_vertical_range // 2)
    # max must equal the starting baseline (no downward movement allowed)
    assert g.player_vertical_max_y == baseline
    # Player instance should also expose the same bounds
    assert getattr(g.player, "vertical_min_y") == g.player_vertical_min_y
    assert getattr(g.player, "vertical_max_y") == g.player_vertical_max_y


def test_player_move_up_and_clamp(monkeypatch):
    g = Game()
    baseline = g.player.y
    # Simulate holding W for many frames
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys({pygame.K_w}))
    for _ in range(50):
        g.handle_input()
        g.player.update(g.width)
    # Player should be clamped to the minimum Y
    assert int(g.player.y) == g.player_vertical_min_y
    assert g.player.y <= baseline


def test_player_move_down_and_clamp(monkeypatch):
    g = Game()
    baseline = g.player.y
    # Simulate holding S for many frames (starting at baseline)
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys({pygame.K_s}))
    for _ in range(50):
        g.handle_input()
        g.player.update(g.width)
    # Player should NOT move below the starting baseline
    assert int(g.player.y) == baseline
    assert int(g.player.y) == g.player_vertical_max_y


def test_player_move_up_then_down_returns_to_baseline(monkeypatch):
    g = Game()
    baseline = g.player.y
    # Move up first
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys({pygame.K_w}))
    for _ in range(20):
        g.handle_input()
        g.player.update(g.width)
    assert g.player.y < baseline
    # Then move down back to baseline (allowed, but not below)
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys({pygame.K_s}))
    for _ in range(40):
        g.handle_input()
        g.player.update(g.width)
    assert int(g.player.y) == baseline


def test_diagonal_speed_normalized(monkeypatch):
    g = Game()
    start_x, start_y = g.player.x, g.player.y
    # Simulate holding RIGHT + W (diagonal up-right) for one frame
    monkeypatch.setattr(
        pygame.key, "get_pressed", lambda: FakeKeys({pygame.K_RIGHT, pygame.K_w})
    )
    g.handle_input()
    g.player.update(g.width)
    dx = g.player.x - start_x
    dy = g.player.y - start_y
    moved = math.hypot(dx, dy)
    # Expected movement magnitude per frame == speed / 60
    expected = g.player.speed / 60.0
    assert (
        abs(moved - expected) < 0.01
    ), f"diagonal moved {moved:.3f}, expected {expected:.3f}"
