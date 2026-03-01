import pygame

from src.game import Game
from src import game_constants
from src.weapons import WEAPON_DEFS


def test_weapon_icon_constants_defined():
    # constants should exist and be reasonable so that layout code can rely on them
    assert hasattr(game_constants, "WEAPON_ICON_SIZE")
    assert hasattr(game_constants, "WEAPON_ICON_PADDING")
    assert game_constants.WEAPON_ICON_SIZE >= 0
    assert game_constants.WEAPON_ICON_PADDING >= 0


def test_weapon_choice_generation_includes_icon():
    """Choices produced by the game state should carry the icon value if
    the underlying weapon definitions include one."""
    # temporarily ensure at least one definition has a unique icon
    WEAPON_DEFS["shotgun"]["icon"] = "weapon_shotgun.png"
    g = Game()
    # force weapon_choices construction
    g.player_weapons = []
    g.player_level = 1
    choices = g.generate_weapon_choices()
    assert any("icon" in c for c in choices), "Expected icon field on some choices"
    # if shotgun appears in choices, its icon should be set
    for c in choices:
        if c.get("id", "").endswith("shotgun"):
            assert c.get("icon") == "weapon_shotgun.png"


def test_weapon_selection_draws_icon_and_offsets(monkeypatch):
    pygame.init()
    calls = []
    icon_surfs = {}
    text_surfs = {}
    blits = []

    # fake get_image to capture requests and return identifiable surfaces
    def fake_get_image(name, size=None):
        calls.append((name, size))
        surf = pygame.Surface((size if size else (10, 10)))
        # store surf by name for later inspection
        icon_surfs[name] = surf
        return surf

    monkeypatch.setattr("src.assets.manager.get_image", fake_get_image)

    # fake get_text to produce unique surfaces and remember them
    import src.ui as ui_module

    def fake_get_text(self, text, font, color):
        surf = pygame.Surface((len(text) * 6 + 1, 10))
        text_surfs[text] = surf
        return surf

    monkeypatch.setattr(ui_module.PygameUIManager, "get_text", fake_get_text)

    # record blit operations on any surface
    orig_blit = pygame.Surface.blit

    def fake_blit(self, surf, dest):
        blits.append((surf, dest))
        return orig_blit(self, surf, dest)

    monkeypatch.setattr(pygame.Surface, "blit", fake_blit)

    # record rectangle draws so we can verify background is rendered
    rect_calls = []
    orig_rect = pygame.draw.rect

    def fake_rect(surface, color, rect, width=0):
        rect_calls.append((color, rect, width))
        return orig_rect(surface, color, rect, width)

    monkeypatch.setattr(pygame.draw, "rect", fake_rect)

    # prepare game with a single weapon choice that has an icon
    WEAPON_DEFS["shotgun"]["icon"] = "weapon_shotgun.png"
    g = Game()
    g.screen = pygame.Surface((800, 600))
    g.weapon_choices = [
        {
            "id": "acquire_shotgun",
            "name": WEAPON_DEFS["shotgun"]["name"],
            "description": WEAPON_DEFS["shotgun"]["description"],
            "icon": "weapon_shotgun.png",
        }
    ]

    # invoke drawing (should not raise)
    g.ui.draw_weapon_selection()

    # ensure get_image was asked to load the icon with appropriate size
    assert any("weapon_shotgun.png" in name for name, _ in calls)

    # locate the blit record for the icon surface
    icon_surf = icon_surfs.get("weapon_shotgun.png")
    assert icon_surf is not None, "icon surface should have been created"
    icon_blits = [b for b in blits if b[0] is icon_surf]
    assert icon_blits, "Icon surface was not blitted"
    icon_x, icon_y = icon_blits[0][1]

    # ensure no background rect was drawn since icons now stay transparent
    assert not rect_calls, "Background rect should not be drawn when transparency is preferred"

    # now find the key text blit and ensure it is to the right of the icon
    key_surf = text_surfs.get("[1]")
    assert key_surf is not None
    key_blits = [b for b in blits if b[0] is key_surf]
    assert key_blits, "Key text not blitted"
    key_x, key_y = key_blits[0][1]
    assert key_x > icon_x + game_constants.WEAPON_ICON_SIZE - 1, "key should appear to the right of the icon"

    # and weapon name should appear further to the right than the key
    name_surf = text_surfs.get(WEAPON_DEFS["shotgun"]["name"])
    assert name_surf is not None
    name_blits = [b for b in blits if b[0] is name_surf]
    assert name_blits, "Weapon name not blitted"
    name_x, name_y = name_blits[0][1]
    assert name_x > key_x, "weapon name should be positioned after key"

    # --- check behaviour when icon asset is missing; layout should still reserve
    # the same left space even though nothing gets blitted.
    calls.clear()
    blits.clear()
    # remove icon path from choice
    g.weapon_choices[0].pop("icon", None)
    # let get_image return None to simulate missing file
    monkeypatch.setattr("src.assets.manager.get_image", lambda n, size=None: None)
    # redraw
    g.ui.draw_weapon_selection()
    # there should be no icon blits now
    assert not any(b[0] in icon_surfs.values() for b in blits)
    # the first key blit x coordinate should still be >= icon reserved width
    key_blits = [b for b in blits if b[0] is key_surf]
    assert key_blits, "Key text not blitted when icon missing"
    key_x_missing, _ = key_blits[0][1]
    assert (
        key_x_missing
        >= icon_x + game_constants.WEAPON_ICON_SIZE + game_constants.WEAPON_ICON_PADDING
    ), "key should still start after reserved icon area even if icon missing"

    # --- verify fallback filename logic when definition lacks explicit icon
    calls.clear()
    blits.clear()
    # craft a choice resembling tenebrae without icon field – UI will compute
    # default weapon_tenebrae.png id
    g.weapon_choices = [
        {"id": "acquire_tenebrae", "name": "Tenebrae", "description": "Desc"}
    ]
    # record get_image attempts
    def fake_get2(name, size=None):
        calls.append((name, size))
        # simulate failure for the primary name so alternate path is exercised
        if name == "weapon_tenebrae.png":
            return None
        return pygame.Surface((game_constants.WEAPON_ICON_SIZE, game_constants.WEAPON_ICON_SIZE))
    monkeypatch.setattr("src.assets.manager.get_image", fake_get2)
    # redraw
    g.ui.draw_weapon_selection()
    # we should have tried both the computed name and its alt
    assert any("weapon_tenebrae.png" in name for name, _ in calls), calls
    assert any("tenebrae.png" in name for name, _ in calls), calls
