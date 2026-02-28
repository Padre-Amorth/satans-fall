import pygame

from src.game import Game


def test_virtual_surface_and_window_sizes(tmp_path):
    _ = tmp_path / "permanent_stats.json"
    g = Game()
    # `screen` remains the virtual render surface used by game/UI
    assert g.screen.get_size() == (g.width, g.height)
    # window surface initially matches virtual size
    assert (g.window_width, g.window_height) == (g.width, g.height)

    # programmatic resize should update window size but not virtual surface
    g.set_window_size(800, 600)
    assert (g.window_width, g.window_height) == (800, 600)
    assert g.screen.get_size() == (g.width, g.height)


def test_options_menu_resolution_preset_click(tmp_path):
    _ = tmp_path / "permanent_stats.json"
    g = Game()
    # Open main menu and options overlay
    g.showing_stage_menu = True
    g.showing_options = True

    # Coordinates must match ui.draw_options_menu layout
    dialog_w, dialog_h = 520, 320
    dx = g.width // 2 - dialog_w // 2
    dy = g.height // 2 - dialog_h // 2
    btn_w, btn_h = 140, 28
    start_x = dx + 24
    btn_y = dy + 248

    # Click dropdown header to open
    dropdown_x = start_x
    dropdown_y = btn_y
    g.handle_mouse_click((dropdown_x + btn_w // 2, dropdown_y + btn_h // 2), 1)

    # Then click the preset item for 1280x720 (find its index dynamically)
    from src.game_constants import DEFAULT_DISPLAY_PRESETS

    preset_index = DEFAULT_DISPLAY_PRESETS.index((1280, 720))
    item_h = 24
    item_spacing = 2
    item_x = dropdown_x + btn_w // 2
    item_y = dropdown_y + btn_h + preset_index * (item_h + item_spacing) + item_h // 2
    g.handle_mouse_click((item_x, item_y), 1)

    # Verify window size changed -- but persistence is disabled so a new
    # game should start with default dimensions.
    assert (g.window_width, g.window_height) == (1280, 720)
    g2 = Game()
    assert (g2.window_width, g2.window_height) == (g2.width, g2.height)


def test_clicks_work_after_window_resize_event(tmp_path):
    """Simulate window-space mouse events after resizing and ensure UI buttons remain clickable.

    This verifies that window->virtual coordinate mapping is applied so clicks
    still hit UI elements even when the window is scaled."""
    _ = tmp_path / "permanent_stats.json"
    g = Game()
    g.showing_stage_menu = True
    g.showing_options = True

    # Resize window to a non-default size (window coordinates will differ)
    g.set_window_size(800, 600)
    assert (g.window_width, g.window_height) == (800, 600)

    # Compute virtual center of the dropdown header and item (same formula as UI)
    dialog_w, dialog_h = 520, 320
    dx = g.width // 2 - dialog_w // 2
    dy = g.height // 2 - dialog_h // 2
    btn_w, btn_h = 140, 28
    start_x = dx + 24
    btn_y = dy + 248

    # Open the dropdown (window coords)
    dropdown_x = start_x
    dropdown_y = btn_y
    hx = dropdown_x + btn_w // 2
    hy = dropdown_y + btn_h // 2
    wx = int(hx * (g.window_width / g.width))
    wy = int(hy * (g.window_height / g.height))

    pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION, {"pos": (wx, wy)}))
    pygame.event.post(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (wx, wy), "button": 1})
    )

    # Click the preset item (window coords)
    from src.game_constants import DEFAULT_DISPLAY_PRESETS

    preset_index = DEFAULT_DISPLAY_PRESETS.index((1280, 720))
    item_h = 24
    item_spacing = 2
    item_x = dropdown_x + btn_w // 2
    item_y = dropdown_y + btn_h + preset_index * (item_h + item_spacing) + item_h // 2
    wx_item = int(item_x * (g.window_width / g.width))
    wy_item = int(item_y * (g.window_height / g.height))
    pygame.event.post(
        pygame.event.Event(pygame.MOUSEMOTION, {"pos": (wx_item, wy_item)})
    )
    pygame.event.post(
        pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"pos": (wx_item, wy_item), "button": 1}
        )
    )

    # Process events (this should map coords back to virtual and handle click)
    g.handle_events()

    # Click should have applied the preset and updated window size
    assert (g.window_width, g.window_height) == (1280, 720)
    g2 = Game()
    # new instance should forget the setting
    assert (g2.window_width, g2.window_height) == (g2.width, g2.height)


def test_options_menu_smooth_scaling_toggle_click(tmp_path):
    _ = tmp_path / "permanent_stats.json"
    g = Game()
    g.showing_stage_menu = True
    g.showing_options = True

    dialog_w, dialog_h = 520, 320
    dx = g.width // 2 - dialog_w // 2
    dy = g.height // 2 - dialog_h // 2
    toggle_w, toggle_h = 48, 24
    smooth_toggle_x = dx + dialog_w - 24 - toggle_w
    smooth_toggle_y = dy + 104

    # Click smooth-scaling toggle
    g.handle_mouse_click(
        (smooth_toggle_x + toggle_w // 2, smooth_toggle_y + toggle_h // 2), 1
    )

    # Persistence disabled so the toggle only affects current game instance
    g2 = Game()
    assert g2.global_progress.get("display", {}).get("smooth_scale", True) is True


def test_draw_uses_smoothscale_when_enabled(monkeypatch, tmp_path):
    _ = tmp_path / "permanent_stats.json"
    g = Game()

    # Explicitly enable smooth scaling and resize window to be larger than virtual
    g.global_progress.setdefault("display", {})["smooth_scale"] = True
    g.set_window_size(1920, 1080)

    called = {"v": False}
    orig = pygame.transform.smoothscale

    def fake_smooth(src, size):
        called["v"] = True
        return orig(src, size)

    monkeypatch.setattr(pygame.transform, "smoothscale", fake_smooth)

    # Trigger a draw (should call smoothscale)
    g.draw()
    assert called["v"] is True


def test_draw_uses_scale_when_smooth_disabled(monkeypatch, tmp_path):
    _ = tmp_path / "permanent_stats.json"
    g = Game()

    # Disable smooth scaling and resize window to be larger than virtual
    g.global_progress.setdefault("display", {})["smooth_scale"] = False
    g.set_window_size(1920, 1080)

    called = {"scale": False}
    orig_scale = pygame.transform.scale

    def fake_scale(src, size):
        called["scale"] = True
        return orig_scale(src, size)

    monkeypatch.setattr(pygame.transform, "scale", fake_scale)

    # Trigger a draw (should call scale, not smoothscale)
    g.draw()
    assert called["scale"] is True


def test_startup_ignores_saved_window_size(tmp_path):
    import json

    from src.game_constants import DEFAULT_HEIGHT, DEFAULT_WIDTH

    # Prepare a persistent file that contains a different window_size
    payload = {
        "permanent_stats": {},
        "global_progress": {
            "display": {"window_size": [800, 600], "fullscreen": False}
        },
    }
    _ = tmp_path / "permanent_stats.json"
    _.write_text(json.dumps(payload))

    # Game should still start at the default virtual resolution (1280x720)
    g = Game()
    assert (
        (g.window_width, g.window_height)
        == (g.width, g.height)
        == (DEFAULT_WIDTH, DEFAULT_HEIGHT)
    )

    # With persistence removed, the new game should not even see the
    # stored window_size entry   (global_progress will be empty).
    assert g.global_progress.get("display") in (None, {})
