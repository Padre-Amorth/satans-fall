import pygame

from src.utils import sound as sound_utils


def setup_module(module):
    # ensure mixer is available for the tests
    try:
        pygame.mixer.init(frequency=44100, size=-16, channels=1)
    except Exception:
        pass


def test_input_handler_click_triggers_generation(monkeypatch):
    from src.game import Game
    from src.systems.input_handler import InputHandler

    game = Game(debug=True)
    game.sounds_enabled = True

    calls = []

    def fake_click(*args, **kwargs):
        calls.append(True)

        class DummySound:
            def play(self):
                pass

        return DummySound()

    monkeypatch.setattr(sound_utils, "suono_click_soft", fake_click)

    handler = InputHandler(game)
    pygame.event.clear()

    # left-click should play a sound
    evt = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (100, 50), "button": 1})
    pygame.event.post(evt)
    handler.handle_events()
    assert calls, "Expected suono_click_soft to be called on left click"

    # non-left buttons must not trigger sound
    calls.clear()
    for btn in (2, 3, 4, 5):
        pygame.event.clear()
        evt_other = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"pos": (20, 20), "button": btn}
        )
        pygame.event.post(evt_other)
        handler.handle_events()
        assert not calls, f"Button {btn} should not play a click sound"

    # disabling audio also suppresses left-click sounds
    game.sounds_enabled = False
    calls.clear()
    evt2 = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (50, 50), "button": 1})
    pygame.event.post(evt2)
    handler.handle_events()
    assert not calls, "No sound should be generated when sounds are disabled"


def test_suono_click_soft_properties():
    snd = sound_utils.suono_click_soft()
    assert isinstance(snd, pygame.mixer.Sound)
    assert abs(snd.get_length() - 0.04) < 0.02


def test_play_click_variato_uses_soft(monkeypatch):
    called = []

    def fake_soft():
        called.append(True)

        class D:
            def play(self):
                pass

        return D()

    monkeypatch.setattr(sound_utils, "suono_click_soft", fake_soft)
    sound_utils.play_click_variato()
    assert called, "play_click_variato should invoke suono_click_soft"
