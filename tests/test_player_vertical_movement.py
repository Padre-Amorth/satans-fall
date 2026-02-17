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
    assert g.player_vertical_max_y == baseline + (g.player_vertical_range // 2)
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
    # Simulate holding S for many frames
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys({pygame.K_s}))
    for _ in range(50):
        g.handle_input()
        g.player.update(g.width)
    # Player should be clamped to the maximum Y
    assert int(g.player.y) == g.player_vertical_max_y
    assert g.player.y >= baseline
