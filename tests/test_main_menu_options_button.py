from src.game import Game


def test_gear_button_opens_and_closes_options(tmp_path):
    # use isolated stats file to avoid interference from prior runs
    g = Game()
    # ensure sound toggle initially true (should be default)
    g.sounds_enabled = True
    # Game starts on the main menu
    assert g.showing_main_menu is True
    # Compute options button center (must match draw_main_menu math)
    opt_size = 38
    opt_x = g.width - opt_size - 14
    opt_y = g.height - opt_size - 14
    opt_center = (opt_x + opt_size // 2, opt_y + opt_size // 2)

    # Click gear -> options should open
    g.handle_mouse_click(opt_center, button=1)
    assert g.showing_options is True

    # Toggle damage numbers: compute toggle center and click it
    dialog_w, dialog_h = 520, 320
    dx = g.width // 2 - dialog_w // 2
    dy = g.height // 2 - dialog_h // 2
    toggle_w, toggle_h = 48, 24
    toggle_x = dx + dialog_w - 24 - toggle_w
    toggle_y = dy + 64
    toggle_center = (toggle_x + toggle_w // 2, toggle_y + toggle_h // 2)

    # Default should be True, click to toggle off
    assert g.show_damage_numbers is True
    g.handle_mouse_click(toggle_center, button=1)
    assert g.show_damage_numbers is False

    # Click again to toggle back on
    g.handle_mouse_click(toggle_center, button=1)
    assert g.show_damage_numbers is True

    # Now compute sound toggle at dy+104 (matches draw_options_menu)
    snd_toggle_y = dy + 104
    snd_center = (toggle_x + toggle_w // 2, snd_toggle_y + toggle_h // 2)

    # sounds enabled default True
    assert g.sounds_enabled is True
    g.handle_mouse_click(snd_center, button=1)
    assert g.sounds_enabled is False
    # verify persistence in global_progress
    assert g.global_progress.get("audio", {}).get("enabled") is False

    # toggle back on
    g.handle_mouse_click(snd_center, button=1)
    assert g.sounds_enabled is True
    assert g.global_progress.get("audio", {}).get("enabled") is True

    # Compute close button center from dialog math in UI
    btn_w, btn_h = 120, 36
    btn_x = dx + (dialog_w - btn_w) // 2
    btn_y = dy + dialog_h - 50
    close_center = (btn_x + btn_w // 2, btn_y + btn_h // 2)

    # Click close -> options should close
    g.handle_mouse_click(close_center, button=1)
    assert g.showing_options is False


def test_gear_not_active_when_stage_menu_hidden():
    g = Game()
    # Simulate being in-game: no menu shown
    g.showing_main_menu = False
    g.showing_stage_menu = False
    # Compute gear button center (matches draw_main_menu)
    opt_size = 38
    opt_x = g.width - opt_size - 14
    opt_y = g.height - opt_size - 14
    opt_center = (opt_x + opt_size // 2, opt_y + opt_size // 2)
    g.handle_mouse_click(opt_center, button=1)
    assert g.showing_options is False
