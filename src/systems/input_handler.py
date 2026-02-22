"""Input handler system — centralized keyboard and mouse event processing."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game import Game

logger: logging.Logger = logging.getLogger(__name__)


class InputHandler:
    """Manages keyboard and mouse input events.

    Service Locator pattern: receives game reference and accesses state via self.game.attr
    """

    def __init__(self, game: "Game") -> None:
        self.game = game

    def handle_events(self) -> None:
        """Process all queued pygame events (QUIT, KEYDOWN, MOUSEBUTTONDOWN, VIDEORESIZE, USEREVENT)."""
        try:
            import pygame
        except Exception:
            pygame = None

        if not pygame:
            return

        for event in pygame.event.get():
            # Explicitly ignore mouse wheel events globally to prevent accidental scrolling
            if event.type == pygame.MOUSEWHEEL:
                # Intentionally do nothing (ignore)
                continue
            if event.type == pygame.QUIT:
                logger.info("[EVENT] QUIT received")
                self.game.running = False
            elif event.type == pygame.KEYDOWN:
                self.handle_keydown(event.key)
            elif event.type == pygame.MOUSEMOTION:
                # Convert window coords to virtual coords so hover logic uses the
                # same coordinate space as UI drawing (self.game.width x self.game.height).
                self.game.mouse_x, self.game.mouse_y = self.game._window_to_virtual(
                    event.pos
                )
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # Map incoming (window) mouse click position to virtual coords
                virt_pos = self.game._window_to_virtual(event.pos)
                self.handle_mouse_click(virt_pos, event.button)
            elif event.type == pygame.VIDEORESIZE:
                # Window resized by user/OS — update actual window surface (virtual surface unchanged)
                self.game.window_width, self.game.window_height = event.w, event.h
                try:
                    self.game.window_surface = pygame.display.set_mode(
                        (self.game.window_width, self.game.window_height),
                        pygame.RESIZABLE,
                    )
                except Exception:
                    pass
                try:
                    self.game.global_progress.setdefault("display", {})[
                        "window_size"
                    ] = [self.game.window_width, self.game.window_height]
                    self.game.save_permanent_stats()
                except Exception:
                    pass
            elif event.type == pygame.USEREVENT + 1:
                logger.info("[EVENT] USEREVENT+1 (reinforcements) fired")
                # Reinforcement timer event
                self.game.spawn_reinforcements()
                # Clear the timer after firing
                pygame.time.set_timer(pygame.USEREVENT + 1, 0)
            elif event.type == pygame.USEREVENT + 2:
                # USEREVENT+2 is used to return to menu after various timed events.
                # If the game over overlay is active, ignore timer-based returns so the
                # user must press Enter/Esc to proceed.
                logger.info("[EVENT] USEREVENT+2 fired")
                if self.game.showing_game_over:
                    logger.info(
                        "USEREVENT+2 ignored because game over overlay is active"
                    )
                    # Clear any stray timer so it doesn't keep firing
                    pygame.time.set_timer(pygame.USEREVENT + 2, 0)
                else:
                    logger.info("USEREVENT+2 handling: returning to menu")
                    self.show_stage_menu()
                    pygame.time.set_timer(pygame.USEREVENT + 2, 0)

        # Final load to ensure persistent stats survive any later init code
        try:
            self.game.load_permanent_stats()
        except Exception:
            pass

    def handle_keydown(self, key):
        """Handle keyboard input based on game state."""
        try:
            import pygame
        except Exception:
            pygame = None

        if not pygame:
            return

        # If a pause confirmation dialog is active, it takes absolute precedence
        if getattr(self.game, "pause_confirmation", None):
            # Toggle selection (0 = Yes, 1 = No)
            if key == pygame.K_LEFT or key == pygame.K_UP:
                self.game.pause_confirmation["selection"] = max(
                    0, self.game.pause_confirmation["selection"] - 1
                )
                return
            elif key == pygame.K_RIGHT or key == pygame.K_DOWN:
                self.game.pause_confirmation["selection"] = min(
                    1, self.game.pause_confirmation["selection"] + 1
                )
                return
            elif key == pygame.K_RETURN or key == pygame.K_SPACE or key == pygame.K_y:
                # Confirm
                if self.game.pause_confirmation["selection"] == 0:
                    action = self.game.pause_confirmation["action"]
                    self.game.pause_confirmation = None
                    if action == "quit":
                        self.game.reset_game()
                else:
                    # Cancel
                    self.game.pause_confirmation = None
                return
            elif key == pygame.K_n or key == pygame.K_ESCAPE:
                # Explicit cancel
                self.game.pause_confirmation = None
                return

        if self.game.showing_stage_menu:
            if key == pygame.K_p:
                self.select_stage("prologo")
            elif key == pygame.K_l:
                # Open the Limbo second menu (keyboard shortcut)
                self.game.showing_limbo_menu = True
            elif key == pygame.K_g:
                # Open the Purgatory second menu (keyboard shortcut)
                self.game.showing_purgatory_menu = True
            elif key == pygame.K_ESCAPE:
                # Close any open submenu
                if self.game.showing_limbo_menu:
                    self.game.showing_limbo_menu = False
                elif self.game.showing_purgatory_menu:
                    self.game.showing_purgatory_menu = False
                elif self.game.showing_hell_menu:
                    self.game.showing_hell_menu = False
            elif key == pygame.K_u:
                self.show_permanent_upgrades()
        elif self.game.showing_permanent_upgrades:
            if key == pygame.K_ESCAPE:
                self.show_stage_menu()
        elif self.game.showing_prologo_end:
            if key == pygame.K_RETURN:
                self.continue_to_limbo()
            elif key == pygame.K_ESCAPE:
                self.game.reset_game()
        elif self.game.showing_stage_menu and self.game.showing_limbo_menu:
            if key == pygame.K_ESCAPE:
                self.game.showing_limbo_menu = False
        elif self.game.showing_stage_menu and self.game.showing_purgatory_menu:
            if key == pygame.K_ESCAPE:
                self.game.showing_purgatory_menu = False
        elif self.game.showing_stage_menu and self.game.showing_hell_menu:
            if key == pygame.K_ESCAPE:
                self.game.showing_hell_menu = False
        elif self.game.showing_game_over:
            # When the game-over overlay is active:
            # Restart disabled: ignore Enter/Space, ESC returns to the main menu.
            if key == pygame.K_RETURN or key == pygame.K_SPACE:
                # Restart is disabled — ignore Enter/Space
                return
            elif key == pygame.K_ESCAPE:
                logger.info("Escape pressed on game over screen; returning to menu")
                self.show_stage_menu()
        elif self.game.showing_player_stats:
            # Close stats overlay with ESC or Tab
            if key == pygame.K_ESCAPE or key == pygame.K_TAB:
                self.game.showing_player_stats = False
                self.game.paused = False
        elif self.game.awaiting_weapon_choice:
            if key == pygame.K_1 and len(self.game.weapon_choices) > 0:
                self.game.apply_weapon(self.game.weapon_choices[0]["id"])
            elif key == pygame.K_2 and len(self.game.weapon_choices) > 1:
                self.game.apply_weapon(self.game.weapon_choices[1]["id"])
            elif key == pygame.K_3 and len(self.game.weapon_choices) > 2:
                self.game.apply_weapon(self.game.weapon_choices[2]["id"])
            elif key == pygame.K_UP:
                self.game.selected_weapon_index = max(
                    0, self.game.selected_weapon_index - 1
                )
                # Keep GameStateManager in sync so UI highlights update
                try:
                    self.game.game_state.selected_weapon_index = (
                        self.game.selected_weapon_index
                    )
                except Exception:
                    pass
            elif key == pygame.K_DOWN:
                self.game.selected_weapon_index = min(
                    max(0, len(self.game.weapon_choices) - 1),
                    self.game.selected_weapon_index + 1,
                )
                try:
                    self.game.game_state.selected_weapon_index = (
                        self.game.selected_weapon_index
                    )
                except Exception:
                    pass
            elif key == pygame.K_RETURN or key == pygame.K_SPACE:
                self.game.apply_weapon(
                    self.game.weapon_choices[self.game.selected_weapon_index]["id"]
                )
        elif self.game.awaiting_tower_choice:
            if key == pygame.K_1 and len(self.game.tower_choices) > 0:
                self.game.apply_tower(self.game.tower_choices[0]["id"])
            elif key == pygame.K_2 and len(self.game.tower_choices) > 1:
                self.game.apply_tower(self.game.tower_choices[1]["id"])
            elif key == pygame.K_3 and len(self.game.tower_choices) > 2:
                self.game.apply_tower(self.game.tower_choices[2]["id"])
            elif key == pygame.K_UP:
                self.game.selected_tower_index = max(
                    0, self.game.selected_tower_index - 1
                )
                try:
                    self.game.game_state.tower_choice_index = (
                        self.game.selected_tower_index
                    )
                except Exception:
                    pass
            elif key == pygame.K_DOWN:
                self.game.selected_tower_index = min(
                    max(0, len(self.game.tower_choices) - 1),
                    self.game.selected_tower_index + 1,
                )
                try:
                    self.game.game_state.tower_choice_index = (
                        self.game.selected_tower_index
                    )
                except Exception:
                    pass
            elif key == pygame.K_RETURN or key == pygame.K_SPACE:
                self.game.apply_tower(
                    self.game.tower_choices[self.game.selected_tower_index]["id"]
                )
            elif key == pygame.K_ESCAPE and not self.game.is_initial_tower_choice:
                # Cancel tower selection and resume
                self.game.awaiting_tower_choice = False
                self.game.paused = False
                try:
                    self.game.game_state.awaiting_tower_choice = False
                except Exception:
                    pass
        elif self.game.awaiting_upgrade:
            # Allow selection only via hotkeys 1-3 or direct mouse click. Arrow navigation
            # and Enter/Space confirmation are intentionally disabled.
            if key == pygame.K_1 and len(self.game.upgrade_choices) > 0:
                self.game.apply_upgrade(self.game.upgrade_choices[0])
            elif key == pygame.K_2 and len(self.game.upgrade_choices) > 1:
                self.game.apply_upgrade(self.game.upgrade_choices[1])
            elif key == pygame.K_3 and len(self.game.upgrade_choices) > 2:
                self.game.apply_upgrade(self.game.upgrade_choices[2])
            elif key == pygame.K_4 and len(self.game.upgrade_choices) > 3:
                # Support 4th hotkey when an extra normal upgrade choice is available
                self.game.apply_upgrade(self.game.upgrade_choices[3])
            elif (
                key == pygame.K_r
                and getattr(self.game, "upgrade_rerolls_remaining", 0) > 0
            ):
                # Keyboard reroll shortcut (consume one reroll and replace choices)
                self.game.reroll_upgrade_choices()
        elif self.game.paused:
            if key == pygame.K_UP or key == pygame.K_w:
                self.game.pause_menu_option = max(0, self.game.pause_menu_option - 1)
            elif key == pygame.K_DOWN or key == pygame.K_s:
                self.game.pause_menu_option = min(1, self.game.pause_menu_option + 1)
            elif key == pygame.K_RETURN or key == pygame.K_SPACE:
                self.execute_pause_option()
        else:
            if key == pygame.K_ESCAPE:
                self.toggle_pause()
            if key == pygame.K_TAB:
                # Toggle player stats overlay when in-game
                self.game.showing_player_stats = not self.game.showing_player_stats
                # Pause game while viewing stats
                self.game.paused = self.game.showing_player_stats
            if key == pygame.K_F3:
                self.game.show_fps = not getattr(self.game, "show_fps", True)

    def handle_mouse_click(self, pos, button=1):
        """Handle mouse clicks in menus.

        Mouse wheel buttons are ignored to prevent accidental menu selection.
        """
        try:
            import pygame
        except Exception:
            pygame = None

        if not pygame:
            return

        try:
            # Ignore mouse wheel buttons (4/5) globally
            if button in (4, 5):
                return

            # If a pause confirmation dialog is active, allow Yes/No to be clicked
            if getattr(self.game, "pause_confirmation", None):
                dialog_w, dialog_h = 260, 70
                dx = self.game.width // 2 - dialog_w // 2
                # Align dialog click area with UI; accept legacy +20 layout as well
                dy_base = self.game.height // 2 - dialog_h // 2
                # Button regions: smaller buttons (match UI) with padding
                btn_w = 80
                btn_h = 28
                # Accept both the current and the legacy vertical offsets so tests
                # relying on different layouts remain stable.
                for dy in (dy_base, dy_base + 20):
                    yes_rect = pygame.Rect(dx + 10, dy + 30, btn_w, btn_h)
                    no_rect = pygame.Rect(
                        dx + dialog_w - btn_w - 10, dy + 30, btn_w, btn_h
                    )
                    if yes_rect.collidepoint(pos):
                        # Confirm Yes
                        action = self.game.pause_confirmation["action"]
                        self.game.pause_confirmation = None
                        if action == "quit":
                            self.game.reset_game()
                        return
                    elif no_rect.collidepoint(pos):
                        # Cancel (No)
                        self.game.pause_confirmation = None
                        return

            # Give level-up UI priority over menus: if awaiting an upgrade, handle
            # clicks for the upgrade/reroll dialog even if other menus are visible.
            if getattr(self.game, "awaiting_upgrade", False) and getattr(
                self.game, "upgrade_choices", None
            ):
                # Upgrade selection — layout constants must match draw_upgrade_selection
                from src.game_constants import (
                    SELECTION_BOX_HEIGHT,
                    SELECTION_BOX_SPACING,
                    SELECTION_BOX_WIDTH,
                )

                cx: int = self.game.width // 2
                box_width = SELECTION_BOX_WIDTH
                box_height = SELECTION_BOX_HEIGHT
                spacing = SELECTION_BOX_SPACING
                total_height = (
                    len(self.game.upgrade_choices) * box_height
                    + (len(self.game.upgrade_choices) - 1) * spacing
                )
                start_y: int = self.game.height // 2 - total_height // 2 + 30
                x_pos: int = cx - box_width // 2

                # Allow clicking the reroll button if present (same math as draw)
                if getattr(self.game, "upgrade_rerolls_remaining", 0) > 0:
                    try:
                        from src.assets.text_cache import get_font, get_text

                        reroll_label = (
                            f"Reroll  ({self.game.upgrade_rerolls_remaining} left)"
                        )
                        reroll_surf = get_text(
                            reroll_label, get_font(15), (220, 180, 180)
                        )
                        reroll_w = reroll_surf.get_width() + 24
                        reroll_h = reroll_surf.get_height() + 10
                        reroll_x = self.game.width // 2 - reroll_w // 2
                        title_h = get_font(38).get_height()
                        sub_h = get_font(15).get_height()
                        div_y = 60 + title_h + sub_h + 10
                        title_bottom = div_y + 6
                        reroll_y = int((title_bottom + start_y) / 2 - reroll_h / 2)
                        pad = 8
                        hot_rect = pygame.Rect(
                            reroll_x - pad,
                            reroll_y - pad,
                            reroll_w + pad * 2,
                            reroll_h + pad * 2,
                        )
                        if hot_rect.collidepoint(pos):
                            self.game.reroll_upgrade_choices()
                            return
                        band_top = title_bottom - 16
                        band_bottom = start_y + 16
                        if (
                            band_top <= pos[1] <= band_bottom
                            and abs(pos[0] - (self.game.width // 2)) <= 300
                        ):
                            self.game.reroll_upgrade_choices()
                            return
                    except Exception:
                        pass

                for i in range(len(self.game.upgrade_choices)):
                    y_pos: int = start_y + i * (box_height + spacing)
                    if (
                        x_pos <= pos[0] <= x_pos + box_width
                        and y_pos <= pos[1] <= y_pos + box_height
                    ):
                        self.game.apply_upgrade(i)
                        return

            if self.game.showing_stage_menu:
                # Check stage selection buttons
                prologo_rect = pygame.Rect(
                    self.game.width // 2 - 100, self.game.height // 2 - 50, 200, 40
                )
                limbo_rect = pygame.Rect(
                    self.game.width // 2 - 100, self.game.height // 2 + 10, 200, 40
                )
                purgatory_rect = pygame.Rect(
                    self.game.width // 2 - 100, self.game.height // 2 + 70, 200, 40
                )
                hell_rect = pygame.Rect(
                    self.game.width // 2 - 100, self.game.height // 2 + 130, 200, 40
                )

                # If options overlay is open, check for clicks on its controls
                if getattr(self.game, "showing_options", False):
                    dialog_w, dialog_h = 520, 320
                    dx = self.game.width // 2 - dialog_w // 2
                    dy = self.game.height // 2 - dialog_h // 2

                    # Damage numbers toggle rect (compact right-aligned)
                    toggle_w, toggle_h = 48, 24
                    toggle_x = dx + dialog_w - 24 - toggle_w
                    toggle_y = dy + 64
                    toggle_rect = pygame.Rect(toggle_x, toggle_y, toggle_w, toggle_h)
                    if toggle_rect.collidepoint(pos):
                        # Toggle option
                        try:
                            self.game.show_damage_numbers = (
                                not self.game.show_damage_numbers
                            )
                        except Exception:
                            pass
                        return

                    # Smooth-scaling toggle (moved up after removing fullscreen option)
                    smooth_toggle_x = dx + dialog_w - 24 - toggle_w
                    smooth_toggle_y = dy + 104
                    smooth_toggle_rect = pygame.Rect(
                        smooth_toggle_x, smooth_toggle_y, toggle_w, toggle_h
                    )
                    if smooth_toggle_rect.collidepoint(pos):
                        try:
                            dsp = self.game.global_progress.setdefault("display", {})
                            dsp["smooth_scale"] = not dsp.get("smooth_scale", True)
                            self.game.save_permanent_stats()
                        except Exception:
                            pass
                        return

                    # Resolution presets dropdown
                    try:
                        from src.game_constants import DEFAULT_DISPLAY_PRESETS
                    except Exception:
                        DEFAULT_DISPLAY_PRESETS = [(1280, 720)]
                    btn_w, btn_h = 140, 28
                    start_x = dx + 24
                    btn_y = dy + 248
                    dropdown_x, dropdown_y = start_x, btn_y
                    dropdown_w, dropdown_h = btn_w, btn_h

                    # Click the dropdown header to open/close
                    dropdown_rect = pygame.Rect(
                        dropdown_x, dropdown_y, dropdown_w, dropdown_h
                    )
                    if dropdown_rect.collidepoint(pos):
                        self.game.options_resolution_dropdown_open = not getattr(
                            self.game, "options_resolution_dropdown_open", False
                        )
                        return

                    # If dropdown is open, check for selection clicks
                    if getattr(self.game, "options_resolution_dropdown_open", False):
                        item_h = 24
                        item_spacing = 2
                        for i, (pw, ph) in enumerate(DEFAULT_DISPLAY_PRESETS):
                            iy = dropdown_y + dropdown_h + i * (item_h + item_spacing)
                            item_rect = pygame.Rect(dropdown_x, iy, dropdown_w, item_h)
                            if item_rect.collidepoint(pos):
                                try:
                                    self.game.set_window_size(pw, ph)
                                except Exception:
                                    pass
                                self.game.options_resolution_dropdown_open = False
                                return
                        # Click outside items will close the dropdown (fall through)
                        return

                    close_rect = pygame.Rect(
                        dx + (dialog_w - 120) // 2, dy + dialog_h - 50, 120, 36
                    )
                    if close_rect.collidepoint(pos):
                        self.game.showing_options = False
                        return
                    # ignore other clicks while options overlay open
                    return
                # Upgrades button moved to bottom of screen to avoid overlap and be more accessible
                upgrades_rect = pygame.Rect(
                    self.game.width // 2 - 125, max(20, self.game.height - 80), 250, 35
                )

                if self.game.showing_limbo_menu:
                    # Coordinates should match draw_stage_menu limbo layout
                    option_w = 320
                    option_h = 48
                    start_x: int = self.game.width // 2 - option_w // 2
                    start_y: int = self.game.height // 2 - 40
                    spacing = 60

                    limbo1_rect = pygame.Rect(start_x, start_y, option_w, option_h)
                    limbo2_rect = pygame.Rect(
                        start_x, start_y + spacing, option_w, option_h
                    )
                    limbo3_rect = pygame.Rect(
                        start_x, start_y + spacing * 2, option_w, option_h
                    )
                    back_rect = pygame.Rect(
                        self.game.width // 2 - 60, start_y + spacing * 3 + 10, 120, 36
                    )

                    if limbo1_rect.collidepoint(pos):
                        self.game.showing_limbo_menu = False
                        self.select_stage("limbo")
                        return
                    elif limbo2_rect.collidepoint(pos):
                        self.game.showing_limbo_menu = False
                        self.select_stage("limbo_2")
                        return
                    elif limbo3_rect.collidepoint(pos):
                        self.game.showing_limbo_menu = False
                        self.select_stage("limbo_3")
                        return
                    elif back_rect.collidepoint(pos):
                        self.game.showing_limbo_menu = False
                        return

                if self.game.showing_purgatory_menu:
                    option_w = 320
                    option_h = 48
                    start_x: int = self.game.width // 2 - option_w // 2
                    start_y: int = self.game.height // 2 - 40
                    spacing = 60

                    purg1_rect = pygame.Rect(start_x, start_y, option_w, option_h)
                    purg2_rect = pygame.Rect(
                        start_x, start_y + spacing, option_w, option_h
                    )
                    purg3_rect = pygame.Rect(
                        start_x, start_y + spacing * 2, option_w, option_h
                    )
                    purg_back_rect = pygame.Rect(
                        self.game.width // 2 - 60, start_y + spacing * 3 + 10, 120, 36
                    )

                    if purg1_rect.collidepoint(pos):
                        self.select_stage("purgatory")
                        self.game.showing_purgatory_menu = False
                        return
                    elif purg2_rect.collidepoint(pos):
                        self.select_stage("purgatory_2")
                        self.game.showing_purgatory_menu = False
                        return
                    elif purg3_rect.collidepoint(pos):
                        self.select_stage("purgatory_3")
                        self.game.showing_purgatory_menu = False
                        return
                    elif purg_back_rect.collidepoint(pos):
                        self.game.showing_purgatory_menu = False
                        return
                    # Defensive logging in case user reports that submenu doesn't show
                    logger.debug(
                        "Purgatory submenu click handling: purgatory_menu=%s, pos=%s",
                        self.game.showing_purgatory_menu,
                        pos,
                    )

                if self.game.showing_hell_menu:
                    option_w = 320
                    option_h = 48
                    start_x: int = self.game.width // 2 - option_w // 2
                    start_y: int = self.game.height // 2 - 40
                    spacing = 60

                    hell1_rect = pygame.Rect(start_x, start_y, option_w, option_h)
                    hell2_rect = pygame.Rect(
                        start_x, start_y + spacing, option_w, option_h
                    )
                    hell3_rect = pygame.Rect(
                        start_x, start_y + spacing * 2, option_w, option_h
                    )
                    hell_back_rect = pygame.Rect(
                        self.game.width // 2 - 60, start_y + spacing * 3 + 10, 120, 36
                    )

                    if hell1_rect.collidepoint(pos):
                        self.select_stage("hell")
                        self.game.showing_hell_menu = False
                        return
                    elif hell2_rect.collidepoint(pos):
                        self.select_stage("hell_2")
                        self.game.showing_hell_menu = False
                        return
                    elif hell3_rect.collidepoint(pos):
                        self.select_stage("hell_3")
                        self.game.showing_hell_menu = False
                        return
                    elif hell_back_rect.collidepoint(pos):
                        self.game.showing_hell_menu = False
                        return
                    logger.debug(
                        "HELL submenu click handling: hell_menu=%s, pos=%s",
                        self.game.showing_hell_menu,
                        pos,
                    )

                # If no submenu handled the click, proceed to main menu handling
                if prologo_rect.collidepoint(pos):
                    self.select_stage("prologo")
                elif limbo_rect.collidepoint(pos):
                    # Open the limbo submenu (second menu)
                    self.game.showing_limbo_menu = True
                elif purgatory_rect.collidepoint(pos):
                    # Open the purgatory submenu (second menu)
                    logger.debug("Mouse click: opening Purgatory submenu")
                    self.game.showing_purgatory_menu = True
                    self.game.showing_limbo_menu = False
                    self.game.showing_hell_menu = False
                    # Keep stage menu visible while showing submenu
                    self.game.showing_stage_menu = True
                elif hell_rect.collidepoint(pos):
                    # Open the HELL submenu (second menu)
                    logger.debug("Mouse click: opening HELL submenu")
                    self.game.showing_hell_menu = True
                    self.game.showing_limbo_menu = False
                    self.game.showing_purgatory_menu = False
                    # Keep stage menu visible while showing submenu
                    self.game.showing_stage_menu = True
                elif upgrades_rect.collidepoint(pos):
                    self.show_permanent_upgrades()
                # Options (gear) button bottom-right
                options_rect = pygame.Rect(
                    self.game.width - 54, max(20, self.game.height - 54), 40, 40
                )
                if options_rect.collidepoint(pos):
                    # Only open options from main stage menu
                    self.game.showing_options = True
                    return
            elif self.game.showing_permanent_upgrades:
                # Handle clicks on permanent stat upgrades
                stat_configs = [
                    {
                        "name": "POWER",
                        "key": "power",
                        "color": (255, 68, 68),
                        "y": 140,
                    },
                    {
                        "name": "VIGOR",
                        "key": "vigor",
                        "color": (255, 204, 0),
                        "y": 185,
                    },
                    {
                        "name": "ADRENALINE",
                        "key": "adrenaline",
                        "color": (170, 68, 255),
                        "y": 230,
                    },
                    {
                        "name": "STRUCTURE",
                        "key": "structure",
                        "color": (139, 105, 20),
                        "y": 275,
                    },
                ]

                # Use same left offset as drawing code so clicks line up with text
                left_x = self.game.width // 2 - 420
                for stat in stat_configs:
                    # Check if click is on the stat name area
                    name_rect = pygame.Rect(left_x, stat["y"], 120, 30)
                    if name_rect.collidepoint(pos):
                        if (
                            button == 1
                            and self.game.permanent_stats[stat["key"]] < 10
                            and self.game.global_progress.get("meta_points", 0) > 0
                        ):  # Left click to upgrade (must have a point)
                            self.game.permanent_stats[stat["key"]] += 1
                            # consume a meta point
                            self.game.global_progress["meta_points"] = (
                                self.game.global_progress.get("meta_points", 0) - 1
                            )
                            # Persist the change immediately
                            self.game.save_permanent_stats()
                            # Apply changes immediately in-game
                            self.game.apply_permanent_stats()
                            self.game.show_centered_message(
                                f"{stat['name']} upgraded to level {self.game.permanent_stats[stat['key']]}!",
                                120,
                                stat["color"],
                                24,
                            )
                        elif (
                            button == 3 and self.game.permanent_stats[stat["key"]] > 0
                        ):  # Right click to downgrade and refund a meta point
                            self.game.permanent_stats[stat["key"]] -= 1
                            # refund currency so the player can reassign points freely
                            self.game.global_progress["meta_points"] = (
                                self.game.global_progress.get("meta_points", 0) + 1
                            )
                            self.game.save_permanent_stats()
                            self.game.apply_permanent_stats()
                            self.game.show_centered_message(
                                f"{stat['name']} downgraded to level {self.game.permanent_stats[stat['key']]}!",
                                120,
                                stat["color"],
                                24,
                            )
                        return

                # --- Blasphemies grid (one row of 5) click handling ---
                # Coordinates mirror the drawing code so clicks line up with boxes
                box_width = 80
                box_height = 80
                box_spacing = 100
                start_x = left_x + box_spacing // 2 - 40
                separator_y = 320
                box_y1 = separator_y + 60

                # Top row (1..5)
                for i in range(5):
                    box_x = start_x + (i * box_spacing)
                    rect = pygame.Rect(
                        box_x - box_width // 2, box_y1, box_width, box_height
                    )
                    key = f"blasphemy_{i + 1}"
                    if rect.collidepoint(pos):
                        # Treat blasphemy slots 1..4 as multi-level (0..3); others toggle
                        if key in (
                            "blasphemy_1",
                            "blasphemy_2",
                            "blasphemy_3",
                            "blasphemy_4",
                        ):
                            if (
                                button == 1
                                and self.game.permanent_stats.get(key, 0) < 3
                            ):
                                self.game.permanent_stats[key] = (
                                    self.game.permanent_stats.get(key, 0) + 1
                                )
                                self.game.save_permanent_stats()
                                self.game.apply_permanent_stats()
                                self.game.show_centered_message(
                                    f"Blasphemy {i + 1} upgraded to level {self.game.permanent_stats[key]}!",
                                    100,
                                    (200, 80, 80),
                                    20,
                                )
                            elif (
                                button == 3
                                and self.game.permanent_stats.get(key, 0) > 0
                            ):
                                self.game.permanent_stats[key] = (
                                    self.game.permanent_stats.get(key, 0) - 1
                                )
                                self.game.save_permanent_stats()
                                self.game.apply_permanent_stats()
                                self.game.show_centered_message(
                                    f"Blasphemy {i + 1} downgraded to level {self.game.permanent_stats[key]}!",
                                    100,
                                    (200, 80, 80),
                                    20,
                                )
                        else:
                            # Other blasphemy slots toggle on/off (boolean)
                            if button == 1 and not self.game.permanent_stats.get(
                                key, 0
                            ):
                                self.game.permanent_stats[key] = 1
                                self.game.save_permanent_stats()
                                self.game.apply_permanent_stats()
                                self.game.show_centered_message(
                                    f"Blasphemy {i + 1} unlocked!",
                                    100,
                                    (200, 80, 80),
                                    20,
                                )
                            elif button == 3 and self.game.permanent_stats.get(key, 0):
                                self.game.permanent_stats[key] = 0
                                self.game.save_permanent_stats()
                                self.game.apply_permanent_stats()
                                self.game.show_centered_message(
                                    f"Blasphemy {i + 1} locked!",
                                    100,
                                    (200, 80, 80),
                                    20,
                                )
                        return

                # Bottom row (6..10) — mirror top-row logic; blasphemy_6 is multi-level (0..3)
                box_y2 = box_y1 + box_height + 12
                for i in range(5):
                    box_x = start_x + (i * box_spacing)
                    rect = pygame.Rect(
                        box_x - box_width // 2, box_y2, box_width, box_height
                    )
                    key = f"blasphemy_{i + 6}"
                    if rect.collidepoint(pos):
                        # Make blasphemy_6..8 leveled stats (0..3)
                        if key in (
                            "blasphemy_6",
                            "blasphemy_7",
                            "blasphemy_8",
                            "blasphemy_9",
                        ):
                            if (
                                button == 1
                                and self.game.permanent_stats.get(key, 0) < 3
                            ):
                                self.game.permanent_stats[key] = (
                                    self.game.permanent_stats.get(key, 0) + 1
                                )
                                self.game.save_permanent_stats()
                                self.game.apply_permanent_stats()
                                self.game.show_centered_message(
                                    f"Blasphemy {i + 6} upgraded to level {self.game.permanent_stats[key]}!",
                                    100,
                                    (200, 80, 80),
                                    20,
                                )
                            elif (
                                button == 3
                                and self.game.permanent_stats.get(key, 0) > 0
                            ):
                                self.game.permanent_stats[key] = (
                                    self.game.permanent_stats.get(key, 0) - 1
                                )
                                self.game.save_permanent_stats()
                                self.game.apply_permanent_stats()
                                self.game.show_centered_message(
                                    f"Blasphemy {i + 6} downgraded to level {self.game.permanent_stats[key]}!",
                                    100,
                                    (200, 80, 80),
                                    20,
                                )
                        else:
                            # Other bottom-row blasphemies remain toggles for now
                            if button == 1 and not self.game.permanent_stats.get(
                                key, 0
                            ):
                                self.game.permanent_stats[key] = 1
                                self.game.save_permanent_stats()
                                self.game.apply_permanent_stats()
                                self.game.show_centered_message(
                                    f"Blasphemy {i + 6} unlocked!",
                                    100,
                                    (200, 80, 80),
                                    20,
                                )
                            elif button == 3 and self.game.permanent_stats.get(key, 0):
                                self.game.permanent_stats[key] = 0
                                self.game.save_permanent_stats()
                                self.game.apply_permanent_stats()
                                self.game.show_centered_message(
                                    f"Blasphemy {i + 6} locked!",
                                    100,
                                    (200, 80, 80),
                                    20,
                                )
                        return

                # Handle clicks on the 3 skill trees on the right side
                tree_types = [
                    ("FIRE", "fire", (255, 68, 68)),
                    ("STORM", "storm", (170, 68, 255)),
                    ("ICE", "ice", (100, 200, 255)),
                ]
                tree_box_w = 50
                tree_box_h = 36
                tree_v_spacing = 46
                tree_col_spacing = 120
                # Compute same left anchor used for drawing
                left_x = self.game.width // 2 - 420
                tree_base_x: int = left_x + 680  # moved right to match drawing
                tree_top_y: int = 320 - 150  # moved much higher to match drawing

                for col_idx, (label, key_prefix, color) in enumerate(tree_types):
                    col_x = tree_base_x + col_idx * tree_col_spacing
                    # Bring inner columns very close (boxes nearly touch)
                    inner_col_offset = tree_box_w // 2 + 1
                    left_col_x = col_x - inner_col_offset
                    right_col_x = col_x + inner_col_offset

                    # check left and right 3x2 grid
                    for row in range(3):
                        y = tree_top_y + row * tree_v_spacing
                        # left tier
                        left_tier = row + 1
                        left_key = f"{key_prefix}_{left_tier}"
                        left_rect = pygame.Rect(
                            left_col_x - tree_box_w // 2, y, tree_box_w, tree_box_h
                        )
                        if left_rect.collidepoint(pos):
                            if button == 1:
                                prev_ok = (
                                    True
                                    if left_tier == 1
                                    else all(
                                        self.game.permanent_stats.get(
                                            f"{key_prefix}_{i + 1}", 0
                                        )
                                        for i in range(left_tier - 1)
                                    )
                                )
                                if (
                                    not self.game.permanent_stats.get(left_key, 0)
                                    and prev_ok
                                ):
                                    self.game.permanent_stats[left_key] = 1
                                    self.game.save_permanent_stats()
                                    self.game.show_centered_message(
                                        f"{label} tier {left_tier} unlocked!",
                                        120,
                                        color,
                                        20,
                                    )
                            elif button == 3:
                                if self.game.permanent_stats.get(left_key, 0):
                                    # clear this and any higher tiers in left column
                                    for r2 in range(row, 3):
                                        k = f"{key_prefix}_{r2 + 1}"
                                        self.game.permanent_stats[k] = 0
                                    # ensure center cleared if condition no longer holds
                                    self.game._enforce_center_requirement(key_prefix)
                                    self.game.save_permanent_stats()
                                    self.game.show_centered_message(
                                        f"{label} tier {left_tier} downgraded!",
                                        120,
                                        color,
                                        20,
                                    )
                            return

                        # right tier
                        right_tier = 4 + row
                        right_key = f"{key_prefix}_{right_tier}"
                        right_rect = pygame.Rect(
                            right_col_x - tree_box_w // 2, y, tree_box_w, tree_box_h
                        )
                        if right_rect.collidepoint(pos):
                            if button == 1:
                                if right_tier == 4:
                                    prev_ok = True
                                else:
                                    # check that previous tiers in right column are active (4..right_tier-1)
                                    prev_ok = all(
                                        self.game.permanent_stats.get(
                                            f"{key_prefix}_{i}", 0
                                        )
                                        for i in range(4, right_tier)
                                    )
                                if (
                                    not self.game.permanent_stats.get(right_key, 0)
                                    and prev_ok
                                ):
                                    self.game.permanent_stats[right_key] = 1
                                    self.game.save_permanent_stats()
                                    self.game.show_centered_message(
                                        f"{label} tier {right_tier} unlocked!",
                                        120,
                                        color,
                                        20,
                                    )
                            elif button == 3:
                                if self.game.permanent_stats.get(right_key, 0):
                                    for r2 in range(row, 3):
                                        k = f"{key_prefix}_{4 + r2}"
                                        self.game.permanent_stats[k] = 0
                                    self.game._enforce_center_requirement(key_prefix)
                                    self.game.save_permanent_stats()
                                    self.game.show_centered_message(
                                        f"{label} tier {right_tier} downgraded!",
                                        120,
                                        color,
                                        20,
                                    )
                            return

                    # center bottom
                    center_y = tree_top_y + 3 * tree_v_spacing
                    center_rect = pygame.Rect(
                        col_x - tree_box_w // 2, center_y, tree_box_w, tree_box_h
                    )
                    if center_rect.collidepoint(pos):
                        center_key = f"{key_prefix}_7"
                        if button == 1:
                            # can unlock only if at least one column of 3 is full
                            left_full = all(
                                self.game.permanent_stats.get(
                                    f"{key_prefix}_{i + 1}", 0
                                )
                                for i in range(3)
                            )
                            right_full = all(
                                self.game.permanent_stats.get(
                                    f"{key_prefix}_{4 + i}", 0
                                )
                                for i in range(3)
                            )
                            if not self.game.permanent_stats.get(center_key, 0) and (
                                left_full or right_full
                            ):
                                self.game.permanent_stats[center_key] = 1
                                self.game.save_permanent_stats()
                                self.game.show_centered_message(
                                    f"{label} final tier unlocked!",
                                    120,
                                    color,
                                    20,
                                )
                        elif button == 3:
                            if self.game.permanent_stats.get(center_key, 0):
                                self.game.permanent_stats[center_key] = 0
                                self.game.save_permanent_stats()
                                self.game.show_centered_message(
                                    f"{label} final tier downgraded!",
                                    120,
                                    color,
                                    20,
                                )
                        return
            elif self.game.awaiting_weapon_choice and self.game.weapon_choices:
                # Weapon selection — layout must match draw_weapon_selection
                from src.game_constants import (
                    SELECTION_BOX_HEIGHT,
                    SELECTION_BOX_SPACING,
                    SELECTION_BOX_WIDTH,
                )

                cx: int = self.game.width // 2
                box_width = SELECTION_BOX_WIDTH
                box_height = SELECTION_BOX_HEIGHT
                spacing = SELECTION_BOX_SPACING
                total_height = (
                    len(self.game.weapon_choices) * box_height
                    + (len(self.game.weapon_choices) - 1) * spacing
                )
                start_y: int = self.game.height // 2 - total_height // 2 + 30
                x_pos: int = cx - box_width // 2

                for i in range(len(self.game.weapon_choices)):
                    y_pos: int = start_y + i * (box_height + spacing)
                    if (
                        x_pos <= pos[0] <= x_pos + box_width
                        and y_pos <= pos[1] <= y_pos + box_height
                    ):
                        self.game.apply_weapon(self.game.weapon_choices[i]["id"])
                        return
            elif self.game.awaiting_tower_choice and self.game.tower_choices:
                # Tower selection — layout must match draw_tower_selection
                from src.game_constants import (
                    SELECTION_BOX_HEIGHT,
                    SELECTION_BOX_SPACING,
                    SELECTION_BOX_WIDTH,
                )

                cx: int = self.game.width // 2
                box_width = SELECTION_BOX_WIDTH
                box_height = SELECTION_BOX_HEIGHT
                spacing = SELECTION_BOX_SPACING
                total_height = (
                    len(self.game.tower_choices) * box_height
                    + (len(self.game.tower_choices) - 1) * spacing
                )
                start_y: int = self.game.height // 2 - total_height // 2 + 30
                x_pos: int = cx - box_width // 2

                for i in range(len(self.game.tower_choices)):
                    y_pos: int = start_y + i * (box_height + spacing)
                    if (
                        x_pos <= pos[0] <= x_pos + box_width
                        and y_pos <= pos[1] <= y_pos + box_height
                    ):
                        self.game.apply_tower(self.game.tower_choices[i]["id"])
                        return
            elif self.game.paused:
                # Pause menu options (now 2 options: Resume, Quit to Menu)
                options_y_start: int = self.game.height // 2 - 20
                option_height = 40
                for i in range(2):
                    option_y: int = options_y_start + i * option_height
                    # Check if click is within a reasonable area around the text
                    if (
                        option_y - 20 <= pos[1] <= option_y + 20
                        and self.game.width // 2 - 150
                        <= pos[0]
                        <= self.game.width // 2 + 150
                    ):
                        self.game.pause_menu_option = i
                        self.execute_pause_option()
                        return
        except Exception as e:
            logger.exception("Error handling mouse click: %s", e)
            try:
                self.game.show_centered_message(
                    "An error occurred handling click", 2000, (255, 100, 100)
                )
            except Exception:
                pass
            return

    def show_stage_menu(self) -> None:
        """Show stage selection menu."""
        self.game.showing_stage_menu = True
        self.game.showing_permanent_upgrades = False
        self.game.showing_prologo_end = False
        # If we were showing the game over overlay, clear it and resume normal menu state
        self.game.showing_game_over = False
        self.game.paused = False
        self.game.game_over_alpha = 0
        # Clear any selected stage so the main menu is truly reset
        self.game.selected_stage = None

    def show_permanent_upgrades(self) -> None:
        """Show permanent stats upgrade menu.

        Also pre-load the blasphemy box asset so the first UI frame renders the
        imported asset (avoids a visible fallback black rectangle on menu open).
        """
        self.game.showing_stage_menu = False
        self.game.showing_permanent_upgrades = True
        self.game.showing_prologo_end = False

        # Defensive preload: ensure `blasphemy_box.png` is cached by AssetManager
        try:
            from src.assets.manager import get_image

            # size used by the UI (80x80) — load into cache so first draw can blit it
            _ = get_image("blasphemy_box.png", (80, 80))
        except Exception:
            # silent fallback — drawing code already handles missing assets
            pass

    def select_stage(self, stage) -> None:
        """Select a stage and prepare for gameplay."""
        logger.info("Selecting stage: %s", stage)
        self.game.selected_stage = stage
        # Keep GameStateManager in sync so initial-choice logic uses the
        # currently selected stage (fixes Purgatory-only weapon availability).
        try:
            if hasattr(self.game, "game_state") and self.game.game_state is not None:
                self.game.game_state.selected_stage = stage
        except Exception:
            pass
        self.game.showing_stage_menu = False
        self.game.showing_permanent_upgrades = False

        # Set stage-specific buildings/spawn points
        if stage == "prologo":
            self.game.buildings = [
                {"x": 460, "y": 70},  # Outer left church - raised 5 pixels
                {"x": 520, "y": 75},  # Left church
                {"x": 640, "y": 60},  # Center cathedral
                {"x": 760, "y": 75},  # Right church
                {"x": 820, "y": 70},  # Outer right church - raised 5 pixels
            ]
        else:  # limbo
            self.game.buildings = []  # No buildings in limbo

        # Generate stage-specific features
        if str(stage).startswith("limbo"):
            self.game.generate_dead_trees()
            # Configure statue/tower types per Limbo level
            if stage == "limbo":
                # Limbo 1 -> Fire
                from src.core.entities.tower import Tower

                self.game.left_tower = Tower(
                    320,
                    530,
                    fire_rate=self.game.statue_fire_rate,
                    tower_type="fire",
                )
                self.game.left_tower._base_damage = self.game.left_tower.damage
                self.game.left_tower._base_fire_rate = self.game.left_tower.fire_rate
                self.game.right_tower = Tower(
                    960,
                    530,
                    fire_rate=self.game.statue_fire_rate,
                    tower_type="fire",
                )
                self.game.right_tower._base_damage = self.game.right_tower.damage
                self.game.right_tower._base_fire_rate = self.game.right_tower.fire_rate
            elif stage == "limbo_2":
                # Limbo 2 -> Storm
                from src.core.entities.tower import Tower

                self.game.left_tower = Tower(
                    320,
                    530,
                    fire_rate=self.game.statue_fire_rate,
                    tower_type="storm",
                )
                self.game.left_tower._base_damage = self.game.left_tower.damage
                self.game.left_tower._base_fire_rate = self.game.left_tower.fire_rate
                self.game.right_tower = Tower(
                    960,
                    530,
                    fire_rate=self.game.statue_fire_rate,
                    tower_type="storm",
                )
                self.game.right_tower._base_damage = self.game.right_tower.damage
                self.game.right_tower._base_fire_rate = self.game.right_tower.fire_rate
            elif stage == "limbo_3":
                # Limbo 3 -> Ice
                from src.core.entities.tower import Tower

                self.game.left_tower = Tower(
                    320,
                    530,
                    fire_rate=self.game.statue_fire_rate,
                    tower_type="ice",
                )
                self.game.left_tower._base_damage = self.game.left_tower.damage
                self.game.left_tower._base_fire_rate = self.game.left_tower.fire_rate
                self.game.right_tower = Tower(
                    960,
                    530,
                    fire_rate=self.game.statue_fire_rate,
                    tower_type="ice",
                )
                self.game.right_tower._base_damage = self.game.right_tower.damage
                self.game.right_tower._base_fire_rate = self.game.right_tower.fire_rate
        elif str(stage).startswith(("purgatory", "hell")):
            # Purgatory/HELL is a stage category with three variants. For parity with Limbo,
            # set up no buildings and trigger initial weapon/tower choice behavior.
            self.game.buildings = []  # No buildings in purgatory/hell for now

            # Determine tower type by variant (fire / storm / ice)
            if stage in ("purgatory", "hell"):
                tower_type = "fire"
            elif stage in ("purgatory_2", "hell_2"):
                tower_type = "storm"
            elif stage in ("purgatory_3", "hell_3"):
                tower_type = "ice"
            else:
                tower_type = "fire"

            from src.core.entities.tower import Tower

            self.game.left_tower = Tower(
                320,
                530,
                fire_rate=self.game.statue_fire_rate,
                tower_type=tower_type,
            )
            self.game.left_tower._base_damage = self.game.left_tower.damage
            self.game.left_tower._base_fire_rate = self.game.left_tower.fire_rate
            self.game.right_tower = Tower(
                960,
                530,
                fire_rate=self.game.statue_fire_rate,
                tower_type=tower_type,
            )
            self.game.right_tower._base_damage = self.game.right_tower.damage
            self.game.right_tower._base_fire_rate = self.game.right_tower.fire_rate

            # Keep towers hidden until the player confirms the tower selection
            # to avoid confusing pre-selection visuals.
            self.game.left_tower.visible = False
            self.game.right_tower.visible = False
        self.game.generate_walls()

        # Reset game state for new run
        self.game.reset_run()

        # Prologo-specific starting weapon
        if stage == "prologo":
            self.game.player_weapons = ["beast"]
            self.game.weapon_levels = {"beast": 1}
            self.game.game_state.player_weapons = ["beast"]
            self.game.game_state.weapon_levels = {"beast": 1}
        elif str(stage).startswith("limbo"):
            # For Limbo, ask GameStateManager to initiate an initial weapon choice
            self.game.is_initial_weapon_choice = True
            try:
                self.game.game_state.show_initial_weapon_choice()
                # Mirror immediately into Game local view for deterministic behavior in the same frame
                self.game.awaiting_weapon_choice = (
                    self.game.game_state.awaiting_weapon_choice
                )
                self.game.weapon_choices = list(self.game.game_state.weapon_choices)
                self.game.selected_weapon_index = (
                    self.game.game_state.weapon_choice_index
                )
            except Exception:
                # Fallback behavior (in case GS isn't available)
                self.game.awaiting_weapon_choice = True
                self.game.weapon_choices = self.game.generate_initial_weapon_choices()
                self.game.selected_weapon_index = 0

            # Do not start countdown yet
        elif str(stage).startswith(("purgatory", "hell")):
            # For Purgatory/HELL, mimic Limbo's initial weapon selection behavior and enable tower choice
            self.game.is_initial_weapon_choice = True
            self.game.is_initial_tower_choice = True
            try:
                self.game.game_state.show_initial_weapon_choice()
                self.game.awaiting_weapon_choice = (
                    self.game.game_state.awaiting_weapon_choice
                )
                self.game.weapon_choices = list(self.game.game_state.weapon_choices)
                self.game.selected_weapon_index = (
                    self.game.game_state.weapon_choice_index
                )
            except Exception:
                self.game.awaiting_weapon_choice = True
                self.game.weapon_choices = self.game.generate_initial_weapon_choices()
                self.game.selected_weapon_index = 0

            # Also prepare tower selection for Purgatory/HELL
            try:
                self.game.game_state.show_initial_tower_choice()
                self.game.awaiting_tower_choice = (
                    self.game.game_state.awaiting_tower_choice
                )
                self.game.tower_choices = list(self.game.game_state.tower_choices)
                self.game.selected_tower_index = self.game.game_state.tower_choice_index
            except Exception:
                self.game.awaiting_tower_choice = True
                self.game.tower_choices = (
                    self.game.game_state.generate_initial_tower_choices()
                    if hasattr(self.game, "game_state")
                    else [
                        {
                            "id": "fire",
                            "name": "Fire Tower",
                            "description": "Damage: 10 — Burn nearby enemies (4 DPS, 3s)",
                        },
                        {
                            "id": "storm",
                            "name": "Storm Tower",
                            "description": "Damage: 10 (projectile ~9) — Chains to multiple enemies",
                        },
                        {
                            "id": "ice",
                            "name": "Ice Tower",
                            "description": "Damage: 15 — Slows enemies 50% for 2s",
                        },
                    ]
                )
                self.game.selected_tower_index = 0

            # Do not start countdown yet

        # Start 3-second countdown before gameplay begins (unless initial weapon or tower choice)
        if (
            not self.game.is_initial_weapon_choice
            and not self.game.is_initial_tower_choice
        ):
            self.game.stage_start_countdown = 3  # 3 seconds
            self.game.stage_start_timer = self.game.fps  # 1 second in frames
        logger.debug("Stage selected, game should start")

        # Debug: fast-forward to Prologo final boss if requested
        if (
            stage == "prologo"
            and getattr(self.game, "fast_forward_prologo", False)
            and not getattr(self.game, "fast_forward_applied", False)
        ):
            logger.debug(
                "Fast-forward: setting time_elapsed to trigger final boss events"
            )
            # Set time beyond final-boss spawn time and process prologo events immediately
            self.game.time_elapsed = (
                236  # > 235 so update_prologo_events spawns boss immediately
            )
            self.game.update_prologo_events()

            # Optionally force the boss to become immortal and force a lightning strike for quick repro
            if getattr(self.game, "fast_forward_prologo_force_lightning", False):
                logger.debug(
                    "Fast-forward: forcing immortal state to trigger lightning immediately"
                )
                # Find the final boss we just spawned
                final_boss = None
                for b in self.game.bosses:
                    if getattr(b, "enemy_type", "") == "boss_final":
                        final_boss = b
                        break
                if final_boss is not None:
                    # Reduce health under 10% and set immortal so regen will begin
                    final_boss.health = final_boss.max_health * 0.05
                    self.game.prologo_final_boss_immortal = True
                    # Run the regen loop a few times to push boss back to full and trigger lightning
                    for i in range(2000):
                        self.game.update_prologo_events()
                        if self.game.prologo_lightning_strike:
                            logger.debug(
                                "Lightning strike triggered after %s iterations",
                                i + 1,
                            )
                            break
                else:
                    logger.debug("Could not find final boss to force lightning")
            self.game.fast_forward_applied = True

    def toggle_pause(self) -> None:
        """Toggle pause state."""
        if not self.game.awaiting_upgrade and not self.game.showing_prologo_end:
            self.game.paused = not self.game.paused
            if self.game.paused:
                self.game.pause_menu_option = 0

    def execute_pause_option(self) -> None:
        """Execute the selected pause menu option."""
        if self.game.pause_menu_option == 0:  # Resume
            self.game.paused = False
            return
        elif self.game.pause_menu_option == 1:  # Quit to Menu
            # Show confirmation dialog instead of quitting immediately
            self.game.pause_confirmation = {"action": "quit", "selection": 0}
            return

    def continue_to_limbo(self) -> None:
        """Continue from prologo to Limbo stage."""
        self.game.showing_prologo_end = False
        self.game.selected_stage = "limbo"
        self.game.generate_dead_trees()
        self.game.reset_run()
