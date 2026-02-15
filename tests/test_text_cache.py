import pygame

from src.assets import text_cache as tc


def test_font_and_text_cache(monkeypatch):
    pygame.init()
    tc.clear_cache()
    f1 = tc.get_font(24)
    f2 = tc.get_font(24)
    assert f1 is f2

    t1 = tc.get_text("hello", f1, (255, 0, 0))
    t2 = tc.get_text("hello", f1, (255, 0, 0))
    assert t1 is t2

    tc.clear_cache()
    f3 = tc.get_font(24)
    assert f3 is not f1
