from src.ui import UIManager
from src.weapons import skull_bomb_cooldown, skull_bomb_damage


class DummyCanvas:
    def __init__(self):
        self.texts = []

    def create_text(self, *args, **kwargs):
        # capture the text argument for assertions
        self.texts.append(kwargs.get("text") or (args[2] if len(args) > 2 else None))

    # provide minimal stubs used by UIManager.draw_weapon_hud
    def create_rectangle(self, *a, **k):
        return None


class DummyGameState:
    def __init__(self):
        self.player_weapons = ["skull_bomb"]
        self.weapon_levels = {"skull_bomb": 1}


class DummyGame:
    def __init__(self):
        self.canvas = DummyCanvas()
        self.width = 800
        self.height = 600
        self.game_state = DummyGameState()
        # UIManager references game.weapon_levels in some places
        self.weapon_levels = {"skull_bomb": 1}
        self.player_damage = 10
        self.damage_multiplier = 1.0


def test_ui_shows_skull_bomb_cooldown_and_damage():
    game = DummyGame()
    ui = UIManager(game)

    ui.draw_weapon_hud()

    # Build expected substrings
    expected_dmg = skull_bomb_damage(1)
    expected_cd = skull_bomb_cooldown(1)
    expected_text = f"{expected_dmg} explosion dmg (cd {expected_cd:.2f}s)"

    # Ensure one of the rendered texts contains the expected HUD string
    assert any(
        expected_text in (t or "") for t in game.canvas.texts
    ), "HUD does not include expected skull bomb damage+cooldown text"
