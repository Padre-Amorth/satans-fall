"""Input handler system — centralized keyboard and mouse event processing."""

import logging
from typing import TYPE_CHECKING

from src.game_constants import HELL_STAGES, LIMBO_STAGES, PURGATORY_STAGES

if TYPE_CHECKING:
    from src.game import Game

logger: logging.Logger = logging.getLogger(__name__)


class InputHandler:
    """Manages keyboard and mouse input events.

    Service Locator pattern: receives game reference and accesses state via self.game.attr
    """

    def __init__(self, game: "Game") -> None:
        self.game = game
        # GIF recording state
        self._gif_recording = False
        self._gif_frames: list = []
        self._gif_frame_counter = 0
        self._gif_start_time = 0.0

    def handle_events(self) -> None:
        """Process all queued pygame events (QUIT, KEYDOWN, MOUSEBUTTONDOWN, VIDEORESIZE, USEREVENT)."""
        try:
            import pygame
        except (AttributeError, TypeError, ValueError, KeyError):
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
                # Show exit confirmation dialog instead of quitting immediately
                # Determine context: in-game vs. menu
                # If selected_stage is set AND we're not in any menu overlay, we're in-game
                in_game = (
                    getattr(self.game, "selected_stage", None) is not None
                    and not getattr(self.game, "showing_main_menu", False)
                    and not getattr(self.game, "showing_stage_menu", False)
                    and not getattr(self.game, "showing_permanent_upgrades", False)
                    and not getattr(self.game, "showing_profiles_menu", False)
                    and not getattr(self.game, "showing_game_over", False)
                )
                if in_game:
                    # In game: use pause_confirmation (displays "Quit to menu?")
                    self.game.pause_confirmation = {"action": "quit", "selection": 0}
                else:
                    # In menu: use exit_confirm_pending (displays "Exit Game?")
                    self.game.exit_confirm_pending = True
            elif event.type == pygame.KEYDOWN:
                self.handle_keydown(event.key)
            elif event.type == pygame.MOUSEMOTION:
                # Convert window coords to virtual coords so hover logic uses the
                # same coordinate space as UI drawing (self.game.width x self.game.height).
                self.game.mouse_x, self.game.mouse_y = self.game._window_to_virtual(
                    event.pos
                )
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # play soft click noise for left-button presses when sounds are active;
                # this used to live in a utility helper but belongs here so every
                # menu interaction (and any other click) makes audio feedback.
                # ignore wheel buttons (4/5) by only handling button 1.
                if event.button == 1 and getattr(self.game, "sounds_enabled", True):
                    try:
                        from src.utils import sound as sound_utils

                        sound_utils.suono_click_soft().play()
                    except (AttributeError, TypeError, ValueError, KeyError):
                        # audio is purely cosmetic; fail silently if something
                        # goes wrong (e.g. no mixer in headless tests)
                        pass

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
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
                try:
                    self.game.global_progress.setdefault("display", {})[
                        "window_size"
                    ] = [self.game.window_width, self.game.window_height]
                except (AttributeError, TypeError, ValueError, KeyError):
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

    def _blasphemy_point_cost(self, key: str) -> int:
        """Return point cost to purchase one level of the given blasphemy key."""
        return 3 if key == "blasphemy_10" else 1

    def _blasphemy_can_afford(self, key: str) -> bool:
        """Check if player has enough blasphemy points to afford this upgrade."""
        cost = self._blasphemy_point_cost(key)
        return self.game.global_progress.get("blasphemy_points", 0) >= cost

    def _blasphemy_spend(self, key: str) -> None:
        """Deduct blasphemy points for a purchase."""
        cost = self._blasphemy_point_cost(key)
        self.game.global_progress["blasphemy_points"] = (
            self.game.global_progress.get("blasphemy_points", 0) - cost
        )

    def _blasphemy_refund(self, key: str) -> None:
        """Refund blasphemy points for a downgrade."""
        cost = self._blasphemy_point_cost(key)
        self.game.global_progress["blasphemy_points"] = (
            self.game.global_progress.get("blasphemy_points", 0) + cost
        )

    def handle_keydown(self, key):
        """Handle keyboard input based on game state."""
        try:
            import pygame
        except (AttributeError, TypeError, ValueError, KeyError):
            pygame = None

        if not pygame:
            return

        # Screenshot works in any game state
        if key == pygame.K_F12:
            self._take_screenshot()

        # GIF recording toggle works in any game state
        if key == pygame.K_F11:
            self._toggle_gif_recording()

        # If unlock overlay is showing, dismiss it on any confirmation key
        if getattr(self.game, "showing_unlock_overlay", False):
            if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                self.game.showing_unlock_overlay = False
                self.game.global_progress["pending_unlock_notifications"] = []
                try:
                    self.game.save_permanent_stats()
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
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
            elif key == pygame.K_RETURN or key == pygame.K_y:
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

        # Profile name text input
        if getattr(self.game, "editing_profile_name", False):
            self._handle_profile_name_keydown(key, pygame)
            return

        # ESC closes profiles menu
        if getattr(self.game, "showing_profiles_menu", False):
            if key == pygame.K_ESCAPE:
                self.game.showing_profiles_menu = False
                self.game.showing_main_menu = True
                return

        # Handle game over keys before any menu logic so ESC always returns to
        # the main menu even if a stage menu flag was left true due to a bug.
        if getattr(self.game, "showing_game_over", False):
            if key == pygame.K_RETURN:
                # Restart is disabled — ignore Enter
                return
            elif key == pygame.K_ESCAPE:
                logger.info("Escape pressed on game over screen; returning to menu")
                self.show_stage_menu()
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
                # Save before closing the menu to preserve any point changes
                self.game.save_permanent_stats()
                self.show_stage_menu()
        elif self.game.showing_prologo_end:
            if key == pygame.K_RETURN:
                self.continue_to_limbo()
            elif key == pygame.K_ESCAPE:
                self.game.reset_game()
        elif getattr(self.game, "showing_victory", False):
            # on victory overlay provide two choices
            if key == pygame.K_RETURN:
                logger.info("ENTER pressed on victory screen; advancing")
                self.continue_after_victory()
                return
            elif key == pygame.K_ESCAPE:
                logger.info("ESC pressed on victory screen; returning to menu")
                self.show_stage_menu()
                return
        elif self.game.showing_stage_menu and self.game.showing_limbo_menu:
            if key == pygame.K_ESCAPE:
                self.game.showing_limbo_menu = False
        elif self.game.showing_stage_menu and self.game.showing_purgatory_menu:
            if key == pygame.K_ESCAPE:
                self.game.showing_purgatory_menu = False
        elif self.game.showing_stage_menu and self.game.showing_hell_menu:
            if key == pygame.K_ESCAPE:
                self.game.showing_hell_menu = False
        elif self.game.showing_stage_menu:
            if key == pygame.K_ESCAPE:
                self.game.showing_stage_menu = False
                self.game.showing_main_menu = True
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
                except (AttributeError, TypeError, ValueError, KeyError):
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
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
            elif key == pygame.K_RETURN:
                self.game.apply_weapon(
                    self.game.weapon_choices[self.game.selected_weapon_index]["id"]
                )
            elif key == pygame.K_SPACE:
                # Blink disabled during weapon choice
                pass
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
                except (AttributeError, TypeError, ValueError, KeyError):
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
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
            elif key == pygame.K_RETURN:
                self.game.apply_tower(
                    self.game.tower_choices[self.game.selected_tower_index]["id"]
                )
            elif key == pygame.K_SPACE:
                # Blink disabled during tower choice
                pass
            elif key == pygame.K_ESCAPE and not self.game.is_initial_tower_choice:
                # Cancel tower selection and resume
                self.game.awaiting_tower_choice = False
                self.game.paused = False
                try:
                    self.game.game_state.awaiting_tower_choice = False
                except (AttributeError, TypeError, ValueError, KeyError):
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
            elif key == pygame.K_RETURN:
                self.execute_pause_option()
        else:
            if key == pygame.K_ESCAPE:
                self.toggle_pause()
            if key == pygame.K_TAB:
                # Toggle player stats overlay when in-game
                self.game.showing_player_stats = not self.game.showing_player_stats
                # Pause game while viewing stats
                self.game.paused = self.game.showing_player_stats
            if key == pygame.K_SPACE:
                # Blasphemy 5 Blink ability
                self.game.execute_blasphemy5_blink()
            if key == pygame.K_F3:
                self.game.show_fps = not getattr(self.game, "show_fps", True)

    def handle_mouse_click(self, pos, button=1):
        """Handle mouse clicks in menus.

        Mouse wheel buttons are ignored to prevent accidental menu selection.
        """
        try:
            import pygame
        except (AttributeError, TypeError, ValueError, KeyError):
            pygame = None

        if not pygame:
            return

        try:
            # Ignore mouse wheel buttons (4/5) globally
            if button in (4, 5):
                return

            # If unlock overlay is showing, ignore all mouse clicks
            if getattr(self.game, "showing_unlock_overlay", False):
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
                            reroll_label, get_font(23), (220, 180, 180)
                        )
                        reroll_w = reroll_surf.get_width() + 36
                        reroll_h = reroll_surf.get_height() + 15
                        reroll_x = self.game.width // 2 - reroll_w // 2
                        title_h = get_font(38).get_height()
                        sub_h = get_font(15).get_height()
                        div_y = 60 + title_h + sub_h + 10
                        title_bottom = div_y + 6
                        reroll_y = int((title_bottom + start_y) / 2 - reroll_h / 2)
                        pad = 12
                        hot_rect = pygame.Rect(
                            reroll_x - pad,
                            reroll_y - pad,
                            reroll_w + pad * 2,
                            reroll_h + pad * 2,
                        )
                        if hot_rect.collidepoint(pos) and button == 1:
                            self.game.reroll_upgrade_choices()
                            return
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass

                for i in range(len(self.game.upgrade_choices)):
                    y_pos: int = start_y + i * (box_height + spacing)
                    if (
                        x_pos <= pos[0] <= x_pos + box_width
                        and y_pos <= pos[1] <= y_pos + box_height
                        and button == 1
                    ):
                        self.game.apply_upgrade(i)
                        return

            if getattr(self.game, "showing_profiles_menu", False):
                self._handle_profiles_menu_click(pos)
                return

            if getattr(self.game, "showing_main_menu", False):
                # EXIT confirmation dialog has HIGHEST priority - blocks all other clicks
                if getattr(self.game, "exit_confirm_pending", False):
                    dialog_w, dialog_h = 400, 160
                    dialog_x = self.game.width // 2 - dialog_w // 2
                    dialog_y = self.game.height // 2 - dialog_h // 2

                    # YES button (left)
                    yes_w, yes_h = 75, 36
                    yes_x = dialog_x + dialog_w // 2 - yes_w - 12
                    yes_y = dialog_y + dialog_h - 52
                    yes_rect = pygame.Rect(yes_x, yes_y, yes_w, yes_h)
                    if yes_rect.collidepoint(pos):
                        self.game.running = False
                        return

                    # NO button (right)
                    no_w, no_h = 75, 36
                    no_x = dialog_x + dialog_w // 2 + 12
                    no_y = dialog_y + dialog_h - 52
                    no_rect = pygame.Rect(no_x, no_y, no_w, no_h)
                    if no_rect.collidepoint(pos):
                        self.game.exit_confirm_pending = False
                        return

                    # Any other click on the overlay dismisses nothing, just return
                    return

                # Options overlay takes priority (gear on main menu)
                if getattr(self.game, "showing_options", False):
                    dialog_w, dialog_h = 520, 320
                    dx = self.game.width // 2 - dialog_w // 2
                    dy = self.game.height // 2 - dialog_h // 2
                    toggle_w, toggle_h = 48, 24
                    toggle_x = dx + dialog_w - 24 - toggle_w
                    if pygame.Rect(toggle_x, dy + 64, toggle_w, toggle_h).collidepoint(
                        pos
                    ):
                        try:
                            self.game.show_damage_numbers = (
                                not self.game.show_damage_numbers
                            )
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                        return
                    if pygame.Rect(toggle_x, dy + 104, toggle_w, toggle_h).collidepoint(
                        pos
                    ):
                        try:
                            self.game.sounds_enabled = not getattr(
                                self.game, "sounds_enabled", True
                            )
                            self.game.global_progress.setdefault("audio", {})[
                                "enabled"
                            ] = self.game.sounds_enabled
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                        return
                    if pygame.Rect(toggle_x, dy + 144, toggle_w, toggle_h).collidepoint(
                        pos
                    ):
                        try:
                            dsp = self.game.global_progress.setdefault("display", {})
                            dsp["smooth_scale"] = not dsp.get("smooth_scale", True)
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                        return
                    try:
                        from src.game_constants import DEFAULT_DISPLAY_PRESETS
                    except (AttributeError, TypeError, ValueError, KeyError):
                        DEFAULT_DISPLAY_PRESETS = [(1280, 720)]
                    dd_w, dd_h = 140, 28
                    dd_x = dx + 24
                    dd_y = dy + 248
                    if pygame.Rect(dd_x, dd_y, dd_w, dd_h).collidepoint(pos):
                        self.game.options_resolution_dropdown_open = not getattr(
                            self.game, "options_resolution_dropdown_open", False
                        )
                        return
                    if getattr(self.game, "options_resolution_dropdown_open", False):
                        item_h = 24
                        for i, (pw, ph) in enumerate(DEFAULT_DISPLAY_PRESETS):
                            iy = dd_y + dd_h + i * (item_h + 2)
                            if pygame.Rect(dd_x, iy, dd_w, item_h).collidepoint(pos):
                                try:
                                    self.game.set_window_size(pw, ph)
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
                                    pass
                                self.game.options_resolution_dropdown_open = False
                                return
                        return
                    if pygame.Rect(
                        dx + (dialog_w - 120) // 2, dy + dialog_h - 50, 120, 36
                    ).collidepoint(pos):
                        self.game.showing_options = False
                        return
                    return

                # START button
                btn_w, btn_h = 300, 68
                start_rect = pygame.Rect(
                    self.game.width // 2 - btn_w // 2,
                    self.game.height // 2 - 34,
                    btn_w,
                    btn_h,
                )
                if start_rect.collidepoint(pos):
                    # If no profile is selected, force player to pick one first
                    if getattr(self.game, "active_profile_slot", None) is None:
                        self._open_profiles_menu()
                    else:
                        self.game.showing_main_menu = False
                        self.game.showing_stage_menu = True
                    return

                # Permanent upgrades button
                up_rect = pygame.Rect(
                    self.game.width // 2 - 125,
                    self.game.height // 2 + 55,
                    250,
                    36,
                )
                if up_rect.collidepoint(pos):
                    # Only allow permanent upgrades if a profile is active
                    if getattr(self.game, "active_profile_slot", None) is not None:
                        self.show_permanent_upgrades()
                    else:
                        # Force profile selection first
                        self._open_profiles_menu()
                    return

                # PROFILES button (below Permanent Upgrades)
                prof_rect = pygame.Rect(
                    self.game.width // 2 - 110,
                    self.game.height // 2 + 100,
                    220,
                    36,
                )
                if prof_rect.collidepoint(pos):
                    self._open_profiles_menu()
                    return

                # EXIT button (bottom center)
                exit_rect = pygame.Rect(
                    self.game.width // 2 - 110,
                    self.game.height - 110,
                    220,
                    36,
                )
                if exit_rect.collidepoint(pos):
                    # Show confirmation prompt instead of exiting immediately
                    self.game.exit_confirm_pending = True
                    return

                # Gear (options) button
                opt_size = 38
                main_options_rect = pygame.Rect(
                    self.game.width - opt_size - 14,
                    self.game.height - opt_size - 14,
                    opt_size,
                    opt_size,
                )
                if main_options_rect.collidepoint(pos):
                    self.game.showing_options = True
                    return

            if self.game.showing_stage_menu:
                # Stage selection buttons — geometry matches draw_stage_menu
                btn_w, btn_h = 280, 46
                btn_x = self.game.width // 2 - btn_w // 2
                base_y = self.game.height // 2 - 100
                spacing_stage = 58
                prologo_rect = pygame.Rect(btn_x, base_y, btn_w, btn_h)
                limbo_rect = pygame.Rect(btn_x, base_y + spacing_stage, btn_w, btn_h)
                purgatory_rect = pygame.Rect(
                    btn_x, base_y + spacing_stage * 2, btn_w, btn_h
                )
                hell_rect = pygame.Rect(btn_x, base_y + spacing_stage * 3, btn_w, btn_h)
                stage_back_rect = pygame.Rect(
                    self.game.width // 2 - 55,
                    base_y + 4 * spacing_stage + 10,
                    110,
                    32,
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
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                        return

                    # Sounds toggle at dy+104 (matches draw_options_menu)
                    snd_toggle_x = dx + dialog_w - 24 - toggle_w
                    snd_toggle_y = dy + 104
                    snd_toggle_rect = pygame.Rect(
                        snd_toggle_x, snd_toggle_y, toggle_w, toggle_h
                    )
                    if snd_toggle_rect.collidepoint(pos):
                        try:
                            self.game.sounds_enabled = not getattr(
                                self.game, "sounds_enabled", True
                            )
                            self.game.global_progress.setdefault("audio", {})[
                                "enabled"
                            ] = self.game.sounds_enabled
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                        return

                    # Smooth-scaling toggle at dy+144 (matches draw_options_menu)
                    smooth_toggle_x = dx + dialog_w - 24 - toggle_w
                    smooth_toggle_y = dy + 144
                    smooth_toggle_rect = pygame.Rect(
                        smooth_toggle_x, smooth_toggle_y, toggle_w, toggle_h
                    )
                    if smooth_toggle_rect.collidepoint(pos):
                        try:
                            dsp = self.game.global_progress.setdefault("display", {})
                            dsp["smooth_scale"] = not dsp.get("smooth_scale", True)
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                        return

                    # Resolution presets dropdown
                    try:
                        from src.game_constants import DEFAULT_DISPLAY_PRESETS
                    except (AttributeError, TypeError, ValueError, KeyError):
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
                                except (
                                    AttributeError,
                                    TypeError,
                                    ValueError,
                                    KeyError,
                                ):
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

                if self.game.showing_limbo_menu:
                    # Coordinates should match draw_stage_menu limbo layout
                    # LIMBO has 4 options: 1, 2, 3, FINAL + BACK below all 4
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
                    limbo_final_rect = pygame.Rect(
                        start_x, start_y + spacing * 3, option_w, option_h
                    )
                    back_rect = pygame.Rect(
                        self.game.width // 2 - 55, start_y + spacing * 4 + 10, 110, 32
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
                    elif limbo_final_rect.collidepoint(pos):
                        self.game.showing_limbo_menu = False
                        self.select_stage("limbo_final")
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
                        self.game.width // 2 - 55, start_y + spacing * 3 + 10, 110, 32
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
                        self.game.width // 2 - 55, start_y + spacing * 3 + 10, 110, 32
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

                # If no submenu handled the click, check stage buttons / back
                if stage_back_rect.collidepoint(pos):
                    self.game.showing_stage_menu = False
                    self.game.showing_main_menu = True
                    return
                if prologo_rect.collidepoint(pos):
                    self.select_stage("prologo")
                elif limbo_rect.collidepoint(pos):
                    self.game.showing_limbo_menu = True
                elif purgatory_rect.collidepoint(pos):
                    logger.debug("Mouse click: opening Purgatory submenu")
                    self.game.showing_purgatory_menu = True
                    self.game.showing_limbo_menu = False
                    self.game.showing_hell_menu = False
                    self.game.showing_stage_menu = True
                elif hell_rect.collidepoint(pos):
                    logger.debug("Mouse click: opening HELL submenu")
                    self.game.showing_hell_menu = True
                    self.game.showing_limbo_menu = False
                    self.game.showing_purgatory_menu = False
                    self.game.showing_stage_menu = True
            elif self.game.showing_permanent_upgrades:
                # EXIT confirmation dialog has HIGHEST priority - blocks all other clicks
                if getattr(self.game, "exit_confirm_pending", False):
                    dialog_w, dialog_h = 400, 160
                    dialog_x = self.game.width // 2 - dialog_w // 2
                    dialog_y = self.game.height // 2 - dialog_h // 2

                    # YES button (left)
                    yes_w, yes_h = 75, 36
                    yes_x = dialog_x + dialog_w // 2 - yes_w - 12
                    yes_y = dialog_y + dialog_h - 52
                    yes_rect = pygame.Rect(yes_x, yes_y, yes_w, yes_h)
                    if yes_rect.collidepoint(pos):
                        self.game.running = False
                        return

                    # NO button (right)
                    no_w, no_h = 75, 36
                    no_x = dialog_x + dialog_w // 2 + 12
                    no_y = dialog_y + dialog_h - 52
                    no_rect = pygame.Rect(no_x, no_y, no_w, no_h)
                    if no_rect.collidepoint(pos):
                        self.game.exit_confirm_pending = False
                        return

                    # Any other click on the overlay dismisses nothing, just return
                    return

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
                        current_level = self.game.permanent_stats.get(stat["key"], 0)
                        if (
                            button == 1
                            and current_level < 10
                            and self.game.global_progress.get("meta_points", 0) > 0
                        ):  # Left click to upgrade (must have a point)
                            self.game.permanent_stats[stat["key"]] = current_level + 1
                            # consume a meta point
                            self.game.global_progress["meta_points"] = (
                                self.game.global_progress.get("meta_points", 0) - 1
                            )
                            # Apply changes immediately in-game then persist
                            self.game.apply_permanent_stats()
                            self.game.save_permanent_stats()
                            self.game.show_centered_message(
                                f"{stat['name']} upgraded to level {self.game.permanent_stats[stat['key']]}!",
                                120,
                                stat["color"],
                                24,
                            )
                        elif (
                            button == 3 and current_level > 0
                        ):  # Right click to downgrade and refund a meta point
                            self.game.permanent_stats[stat["key"]] = current_level - 1
                            # refund currency so the player can reassign points freely
                            self.game.global_progress["meta_points"] = (
                                self.game.global_progress.get("meta_points", 0) + 1
                            )
                            self.game.apply_permanent_stats()
                            self.game.save_permanent_stats()
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
                                if not self._blasphemy_can_afford(key):
                                    cost = self._blasphemy_point_cost(key)
                                    pts = self.game.global_progress.get(
                                        "blasphemy_points", 0
                                    )
                                    self.game.show_centered_message(
                                        f"Need {cost} Blasphemy Point{'s' if cost > 1 else ''} (have {pts})",
                                        80,
                                        (180, 80, 80),
                                        18,
                                    )
                                    return
                                self._blasphemy_spend(key)
                                self.game.permanent_stats[key] = (
                                    self.game.permanent_stats.get(key, 0) + 1
                                )
                                self.game.apply_permanent_stats()
                                self.game.save_permanent_stats()
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
                                self._blasphemy_refund(key)
                                self.game.permanent_stats[key] = (
                                    self.game.permanent_stats.get(key, 0) - 1
                                )
                                self.game.apply_permanent_stats()
                                self.game.save_permanent_stats()
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
                                if not self._blasphemy_can_afford(key):
                                    cost = self._blasphemy_point_cost(key)
                                    pts = self.game.global_progress.get(
                                        "blasphemy_points", 0
                                    )
                                    self.game.show_centered_message(
                                        f"Need {cost} Blasphemy Point{'s' if cost > 1 else ''} (have {pts})",
                                        80,
                                        (180, 80, 80),
                                        18,
                                    )
                                    return
                                self._blasphemy_spend(key)
                                self.game.permanent_stats[key] = 1
                                self.game.apply_permanent_stats()
                                self.game.save_permanent_stats()
                                self.game.show_centered_message(
                                    f"Blasphemy {i + 1} unlocked!",
                                    100,
                                    (200, 80, 80),
                                    20,
                                )
                            elif button == 3 and self.game.permanent_stats.get(key, 0):
                                self._blasphemy_refund(key)
                                self.game.permanent_stats[key] = 0
                                self.game.apply_permanent_stats()
                                self.game.save_permanent_stats()
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
                                if not self._blasphemy_can_afford(key):
                                    cost = self._blasphemy_point_cost(key)
                                    pts = self.game.global_progress.get(
                                        "blasphemy_points", 0
                                    )
                                    self.game.show_centered_message(
                                        f"Need {cost} Blasphemy Point{'s' if cost > 1 else ''} (have {pts})",
                                        80,
                                        (180, 80, 80),
                                        18,
                                    )
                                    return
                                self._blasphemy_spend(key)
                                self.game.permanent_stats[key] = (
                                    self.game.permanent_stats.get(key, 0) + 1
                                )
                                self.game.apply_permanent_stats()
                                self.game.save_permanent_stats()
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
                                self._blasphemy_refund(key)
                                self.game.permanent_stats[key] = (
                                    self.game.permanent_stats.get(key, 0) - 1
                                )
                                self.game.apply_permanent_stats()
                                self.game.save_permanent_stats()
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
                                if not self._blasphemy_can_afford(key):
                                    cost = self._blasphemy_point_cost(key)
                                    pts = self.game.global_progress.get(
                                        "blasphemy_points", 0
                                    )
                                    self.game.show_centered_message(
                                        f"Need {cost} Blasphemy Point{'s' if cost > 1 else ''} (have {pts})",
                                        80,
                                        (180, 80, 80),
                                        18,
                                    )
                                    return
                                self._blasphemy_spend(key)
                                self.game.permanent_stats[key] = 1
                                self.game.apply_permanent_stats()
                                self.game.save_permanent_stats()
                                self.game.show_centered_message(
                                    f"Blasphemy {i + 6} unlocked!",
                                    100,
                                    (200, 80, 80),
                                    20,
                                )
                            elif button == 3 and self.game.permanent_stats.get(key, 0):
                                self._blasphemy_refund(key)
                                self.game.permanent_stats[key] = 0
                                self.game.apply_permanent_stats()
                                self.game.save_permanent_stats()
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
                                self.game.apply_permanent_stats()
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
            # no UI element claimed the click.  only trigger a tower special
            # when the player is actually in-game (menus should not activate it).
            if button == 3 and not any(
                (
                    self.game.showing_main_menu,
                    self.game.showing_stage_menu,
                    self.game.showing_permanent_upgrades,
                    self.game.awaiting_upgrade,
                    self.game.awaiting_weapon_choice,
                    self.game.awaiting_tower_choice,
                )
            ):
                # if beam already active, a second click should cancel it
                try:
                    if getattr(self.game, "voltaic_active", False):
                        # cancel active beam
                        self.game.voltaic_active = False
                        if getattr(self.game, "tower_special", None):
                            self.game.tower_special._voltaic_accum.clear()
                        try:
                            self.game.right_mouse_held = False
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                        # feedback so player knows the beam ended early
                        try:
                            self.game.show_centered_message(
                                "Tower special cancelled", 100, (200, 200, 255), 20
                            )
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                        return
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

                # otherwise attempt normal activation
                try:
                    # mark the property for consistency even though it's not relied on
                    self.game.right_mouse_held = True
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
                try:
                    if (
                        self.game.is_tower_special_ready()
                        and self.game.activate_tower_special()
                    ):
                        try:
                            self.game.show_centered_message(
                                "Tower special activated!", 100, (255, 255, 255), 24
                            )
                        except (AttributeError, TypeError, ValueError, KeyError):
                            pass
                    elif self.game.fire_special_charges > 0:
                        # consume next fire charge from the active window
                        self.game.use_fire_charge()
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
                return
        except Exception as e:
            logger.exception("Error handling mouse click: %s", e)
            try:
                self.game.show_centered_message(
                    "An error occurred handling click", 2000, (255, 100, 100)
                )
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
            return

    def _handle_profile_name_keydown(self, key, pygame) -> None:
        """Handle text-input keyboard events while editing a profile name."""
        slot = getattr(self.game, "editing_profile_slot", None)
        current = getattr(self.game, "profile_name_input", "")
        if key == pygame.K_RETURN or key == pygame.K_KP_ENTER:
            # Confirm: save the new name and exit edit mode
            name = current.strip() or f"Profile {slot}"
            self.game.global_progress["profile_name"] = name
            # Check if this is a NEW profile (doesn't exist yet)
            path = self.game._profile_path(slot)
            is_new_profile = not path.exists()

            # If this slot is the active one, persist immediately
            if getattr(self.game, "active_profile_slot", None) == slot:
                try:
                    self.game.save_permanent_stats()
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
            else:
                # Save profile file
                try:
                    import json
                    import os

                    if path.exists():
                        # Existing profile: update name only
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        data["name"] = name
                        tmp = path.with_suffix(".json.tmp")
                        with open(tmp, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2)
                        os.replace(tmp, path)
                    else:
                        # New profile: create with completely empty/reset stats
                        from datetime import datetime

                        data = {
                            "version": 1,
                            "name": name,
                            "last_played": datetime.now().isoformat(timespec="seconds"),
                            "permanent_stats": {},  # Empty — no upgrades selected
                            "global_progress": {
                                "meta_xp": 0,
                                "meta_level": 1,
                                "meta_points": 0,
                                "stages_cleared": {},
                                "display": {},
                                "audio": {},
                            },
                        }
                        tmp = path.with_suffix(".json.tmp")
                        with open(tmp, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2)
                        os.replace(tmp, path)
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

            # If this was a NEW profile, activate it and reset game memory to clean state
            if is_new_profile:
                self.game.active_profile_slot = slot
                # Reset game state to factory defaults
                self.game.permanent_stats = {}
                self.game.global_progress = {
                    "meta_xp": 0,
                    "meta_level": 1,
                    "meta_points": 0,
                    "stages_cleared": {},
                    "profile_name": name,
                    "display": {},
                    "audio": {},
                }
                # Return to main menu (profile is now active)
                self.game.showing_profiles_menu = False
                self.game.showing_main_menu = True

            self.game.editing_profile_name = False
            self.game.editing_profile_slot = None
            self.game.profile_name_input = ""
        elif key == pygame.K_ESCAPE:
            # Cancel edit
            self.game.editing_profile_name = False
            self.game.editing_profile_slot = None
            self.game.profile_name_input = ""
        elif key == pygame.K_BACKSPACE:
            self.game.profile_name_input = current[:-1]
        else:
            # Append printable character (max 20)
            try:
                char = pygame.key.name(key)
                if len(char) == 1 and len(current) < 20:
                    self.game.profile_name_input = current + char
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

    def _handle_profiles_menu_click(self, pos) -> None:
        """Handle mouse clicks in the profiles selection screen."""
        try:
            import pygame
        except (AttributeError, TypeError, ValueError, KeyError):
            return
        g = self.game
        w, h = g.width, g.height

        # Layout constants (must match draw_profiles_menu in ui.py)
        card_w, card_h = 460, 120
        card_x = w // 2 - card_w // 2
        start_y = h // 2 - 210
        spacing = 140

        for slot in range(1, 4):
            cy = start_y + (slot - 1) * spacing
            card_rect = pygame.Rect(card_x, cy, card_w, card_h)

            # Only process clicks inside this card
            if not card_rect.collidepoint(pos):
                continue

            info = g.get_profile_info(slot)
            slot_exists = info["exists"]

            # --- DELETE confirmation ---
            if getattr(g, "profile_delete_confirm", {}).get(slot):
                # YES button (confirm delete)
                yes_rect = pygame.Rect(card_x + card_w - 120, cy + card_h - 30, 50, 22)
                no_rect = pygame.Rect(card_x + card_w - 62, cy + card_h - 30, 50, 22)
                if yes_rect.collidepoint(pos):
                    g.profile_delete_confirm[slot] = False
                    g.delete_profile(slot)
                    return
                if no_rect.collidepoint(pos):
                    g.profile_delete_confirm[slot] = False
                    return
                return  # click inside card but not on YES/NO → ignore

            # --- EDIT button (top-right of card) ---
            edit_rect = pygame.Rect(card_x + card_w - 56, cy + 8, 48, 22)
            if edit_rect.collidepoint(pos):
                g.editing_profile_name = True
                g.editing_profile_slot = slot
                # Pre-fill with existing name or default
                if slot_exists:
                    g.profile_name_input = info["name"]
                else:
                    g.profile_name_input = f"Profile {slot}"
                return

            # --- DELETE button (right side, mid-card) ---
            if slot_exists:
                del_rect = pygame.Rect(card_x + card_w - 56, cy + 36, 48, 22)
                if del_rect.collidepoint(pos):
                    g.profile_delete_confirm = getattr(g, "profile_delete_confirm", {})
                    g.profile_delete_confirm[slot] = True
                    return

            # --- SELECT button (bottom-right) or CREATE (empty slot) ---
            select_rect = pygame.Rect(card_x + card_w - 80, cy + card_h - 30, 72, 22)
            if select_rect.collidepoint(pos):
                if not slot_exists:
                    # Create: open name input first
                    g.editing_profile_name = True
                    g.editing_profile_slot = slot
                    g.profile_name_input = f"Profile {slot}"
                else:
                    # Select and return to main menu
                    g.select_profile(slot)
                    g.showing_profiles_menu = False
                    g.showing_main_menu = True
                return

            return  # click inside card but not on any button

        # BACK button
        back_rect = pygame.Rect(w // 2 - 55, start_y + 3 * spacing + 10, 110, 32)
        if back_rect.collidepoint(pos):
            g.showing_profiles_menu = False
            g.showing_main_menu = True

    def _open_profiles_menu(self) -> None:
        """Open the profiles selection screen, clearing any residual game state."""
        g = self.game
        g.showing_profiles_menu = True
        g.showing_main_menu = False
        g.showing_stage_menu = False
        g.showing_permanent_upgrades = False
        g.showing_prologo_end = False
        # Clear residual combat / game-over state so the menu is clean
        try:
            g.showing_game_over = False
            g.game_over_alpha = 0
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        try:
            g.shake_timer = 0
            g.shake_intensity = 0
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        try:
            g.paused = False
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def show_stage_menu(self) -> None:
        """Return to the main menu."""
        self.game.showing_main_menu = True
        self.game.showing_stage_menu = False
        self.game.showing_permanent_upgrades = False
        self.game.showing_prologo_end = False
        # also clear any active victory overlay so the UI doesn't linger
        self.game.showing_victory = False
        # If we were showing the game over overlay, clear it and resume normal menu state
        self.game.showing_game_over = False
        self.game.paused = False
        self.game.game_over_alpha = 0
        # Clear any selected stage so the main menu is truly reset
        self.game.selected_stage = None
        # when leaving a limbo victory we must also reset the horde tracking
        # state/timer.  otherwise the fallback logic in ``update_game`` can
        # restart the countdown while we're sitting in the menu, causing the
        # SATANIC VICTORY overlay to pop up again after a few seconds (see
        # regression described in issue).
        try:
            self.game.limbo_horde_completed = False
            self.game.limbo_horde_ready_for_victory = False
            self.game.limbo_horde_victory_timer = 0
        except (AttributeError, TypeError, ValueError, KeyError):
            # defensive: in some tests the attributes may not exist
            pass

    def show_permanent_upgrades(self) -> None:
        """Show permanent stats upgrade menu.

        Also pre-load the blasphemy box asset so the first UI frame renders the
        imported asset (avoids a visible fallback black rectangle on menu open).
        """
        self.game.showing_main_menu = False
        self.game.showing_stage_menu = False
        self.game.showing_permanent_upgrades = True
        self.game.showing_prologo_end = False

        # Defensive preload: ensure `blasphemy_box.png` is cached by AssetManager
        try:
            from src.assets.manager import get_image

            # size used by the UI (80x80) — load into cache so first draw can blit it
            _ = get_image("blasphemy_box.png", (80, 80))
        except (AttributeError, TypeError, ValueError, KeyError):
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
        except (AttributeError, TypeError, ValueError, KeyError):
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
        if str(stage) in LIMBO_STAGES:
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
            elif stage == "limbo_final":
                # Final limbo uses dynamic tower type chosen by player.
                # Create placeholder towers and keep them hidden until selection.
                from src.core.entities.tower import Tower

                # use fire as a neutral default; it will be overwritten by apply_tower
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
                # hide until player chooses option
                self.game.left_tower.visible = False
                self.game.right_tower.visible = False
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

        # Generate lamps for limbo stages (after reset_run so they're not cleared)
        if str(stage) in LIMBO_STAGES:
            self.game.generate_limbo_lamps()

        # Generate cauldrons for purgatory stages
        if str(stage) in PURGATORY_STAGES:
            self.game.generate_purgatory_cauldrons()

        # Generate lamps for hell stages
        if str(stage) in HELL_STAGES:
            self.game.generate_hell_lamps()

        # Generate torches for prologo stage
        if stage == "prologo":
            self.game.generate_prologo_torches()

        # Prologo-specific starting weapon
        if stage == "prologo":
            self.game.player_weapons = ["beast"]
            self.game.weapon_levels = {"beast": 1}
            self.game.game_state.player_weapons = ["beast"]
            self.game.game_state.weapon_levels = {"beast": 1}
        elif str(stage) in LIMBO_STAGES:
            # For Limbo we always do an initial weapon choice.  The final Limbo
            # level also requires the player to select a tower type, mirroring
            # the behaviour of the Purgatory stages.
            self.game.is_initial_weapon_choice = True
            is_final = stage == "limbo_final"
            if is_final:
                self.game.is_initial_tower_choice = True
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
            except (AttributeError, TypeError, ValueError, KeyError):
                # Fallback behavior (in case GS isn't available)
                self.game.awaiting_weapon_choice = True
                self.game.weapon_choices = self.game.generate_initial_weapon_choices()
                self.game.selected_weapon_index = 0

            # If final limbo also prepare tower selection now
            if is_final:
                try:
                    self.game.game_state.show_initial_tower_choice()
                    self.game.awaiting_tower_choice = (
                        self.game.game_state.awaiting_tower_choice
                    )
                    self.game.tower_choices = list(self.game.game_state.tower_choices)
                    self.game.selected_tower_index = (
                        self.game.game_state.tower_choice_index
                    )
                except (AttributeError, TypeError, ValueError, KeyError):
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
            except (AttributeError, TypeError, ValueError, KeyError):
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
            except (AttributeError, TypeError, ValueError, KeyError):
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

        # Debug: fast-forward to limbo-final near boss spawn time if requested
        if (
            stage == "limbo_final"
            and getattr(self.game, "fast_forward_limbo_final", False)
            and not getattr(self.game, "fast_forward_applied", False)
        ):
            logger.debug("Fast-forward: advancing time_elapsed for limbo_final stage")
            # push time close to boss spawn threshold without actually spawning
            self.game.time_elapsed = 165
            # do not trigger events yet; boss will spawn naturally in update loop
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
        self.game.generate_limbo_lamps()
        self.game.generate_purgatory_cauldrons()
        self.game.generate_hell_lamps()
        self.game.generate_prologo_torches()

    def continue_after_victory(self) -> None:
        """After a victory overlay, start the next limbo variant (or return to limbo).

        Cycling order: limbo -> limbo_2 -> limbo_3 -> limbo
        """
        # clear horde/victory timer before switching stages; the new level
        # should start clean and not accidentally re-trigger the overlay.
        try:
            self.game.limbo_horde_victory_timer = 0
            self.game.limbo_horde_completed = False
            self.game.limbo_horde_ready_for_victory = False
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        self.game.showing_victory = False
        # pick next in sequence if we're on limbo series
        seq = ["limbo", "limbo_2", "limbo_3"]
        cur = getattr(self.game, "selected_stage", None)
        if cur in seq:
            nxt = seq[(seq.index(cur) + 1) % len(seq)]
        else:
            nxt = "limbo"

        # Use Game.select_stage to ensure full initialization:
        # - runs reset_run()
        # - applies spawn rate penalties
        # - sets is_initial_weapon_choice / tower choice flags
        # - starts countdown only if no choice is pending
        try:
            self.game.select_stage(nxt)
        except (AttributeError, TypeError, ValueError, KeyError):
            # fall back to manual logic in case select_stage is unavailable
            self.game.selected_stage = nxt
            if nxt in LIMBO_STAGES:
                try:
                    self.game.generate_dead_trees()
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
            try:
                self.game.reset_run()
            except (AttributeError, TypeError, ValueError, KeyError):
                pass
            # Generate lamps for limbo stages
            if nxt in LIMBO_STAGES:
                try:
                    self.game.generate_limbo_lamps()
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

            # Generate cauldrons for purgatory stages
            if nxt in PURGATORY_STAGES:
                try:
                    self.game.generate_purgatory_cauldrons()
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

            # Generate lamps for hell stages
            if nxt in HELL_STAGES:
                try:
                    self.game.generate_hell_lamps()
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

            # Generate torches for prologo stage
            if nxt == "prologo":
                try:
                    self.game.generate_prologo_torches()
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

    def _take_screenshot(self) -> None:
        """Save a screenshot of the current game window to the screenshots folder."""
        try:
            import os
            from datetime import datetime

            import pygame
        except (AttributeError, TypeError, ValueError, KeyError, ImportError):
            return

        try:
            # Create screenshots directory if it doesn't exist
            # Use absolute path relative to this file to avoid permission issues
            base_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            screenshots_dir = os.path.join(base_dir, "screenshots")
            os.makedirs(screenshots_dir, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(screenshots_dir, f"screenshot_{timestamp}.png")

            # Save the window surface
            pygame.image.save(self.game.window_surface, filename)
            logger.info(f"Screenshot saved: {filename}")
            print(f"[Screenshot] Salvato: {os.path.abspath(filename)}")
        except Exception as e:
            logger.warning(f"Failed to save screenshot: {e}")
            print(f"[Screenshot] ERRORE: {e}")

    def _toggle_gif_recording(self) -> None:
        """Toggle GIF recording on/off."""
        import time

        if not self._gif_recording:
            # START recording
            self._gif_recording = True
            self._gif_frames = []
            self._gif_frame_counter = 0
            self._gif_start_time = time.time()
            self.game._gif_recording = True
            print("[GIF] Registrazione avviata — premi F11 per fermare")
        else:
            # STOP recording
            self._gif_recording = False
            self.game._gif_recording = False
            self._save_gif()

    def _capture_gif_frame(self) -> None:
        """Capture a frame for GIF recording."""
        import time

        from src.game_constants import (
            DEFAULT_FPS,
            GIF_MAX_DURATION_SECONDS,
            GIF_RECORDING_FPS,
            GIF_SCALE_FACTOR,
        )

        # Auto-stop after max duration
        if time.time() - self._gif_start_time > GIF_MAX_DURATION_SECONDS:
            self._gif_recording = False
            self.game._gif_recording = False
            self._save_gif()
            return

        # Capture only 1 frame every N (to reach ~15fps)
        skip = max(1, DEFAULT_FPS // GIF_RECORDING_FPS)
        self._gif_frame_counter += 1
        if self._gif_frame_counter % skip != 0:
            return

        try:
            import pygame
            from PIL import Image

            surface = self.game.window_surface
            raw = pygame.image.tostring(surface, "RGB")
            w, h = surface.get_size()
            img = Image.frombytes("RGB", (w, h), raw)

            # Scale to reduce file size
            new_w = int(w * GIF_SCALE_FACTOR)
            new_h = int(h * GIF_SCALE_FACTOR)
            img = img.resize((new_w, new_h), Image.NEAREST)

            self._gif_frames.append(img)
        except Exception as e:
            print(f"[GIF] Errore cattura frame: {e}")

    def _save_gif(self) -> None:
        """Save captured frames as a GIF file."""
        if not self._gif_frames:
            print("[GIF] Nessun frame da salvare")
            return

        try:
            import os
            from datetime import datetime

            from src.game_constants import GIF_RECORDING_FPS

            base_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            recordings_dir = os.path.join(base_dir, "recordings")
            os.makedirs(recordings_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(recordings_dir, f"clip_{timestamp}.gif")

            duration_ms = int(1000 / GIF_RECORDING_FPS)  # ms per frame
            first = self._gif_frames[0]
            first.save(
                filename,
                save_all=True,
                append_images=self._gif_frames[1:],
                duration=duration_ms,
                loop=0,
                optimize=True,
            )

            n = len(self._gif_frames)
            secs = round(n / GIF_RECORDING_FPS, 1)
            size_mb = round(os.path.getsize(filename) / 1024 / 1024, 1)
            print(f"[GIF] Salvato: {filename} ({n} frame, {secs}s, {size_mb} MB)")
            logger.info(f"GIF saved: {filename}")
            self._gif_frames = []
        except Exception as e:
            print(f"[GIF] Errore salvataggio: {e}")
            logger.warning(f"Failed to save GIF: {e}")
            self._gif_frames = []
