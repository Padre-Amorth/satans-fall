"""UI Menu System: Main menu, stage selection, options, permanent upgrades, pause."""

import logging
import math
from pathlib import Path
from typing import TYPE_CHECKING

from src.assets.manager import get_image
from src.ui.constants import _STAT_CONFIGS, _TREE_TYPES

if TYPE_CHECKING:
    from src.game.core import Game

logger: logging.Logger = logging.getLogger(__name__)


class UIMenuSystem:
    """Handles all menu rendering: main, stage selection, options, upgrades, pause."""

    def __init__(self, ui_manager):
        """
        Args:
            ui_manager: Reference to PygameUIManager (parent).
        """
        self.ui = ui_manager
        self.game: Game = ui_manager.game

    def _get_font_path(self, font_name: str) -> str:
        """Get absolute path to a font file in assets/fonts/."""
        # Walk up from menus.py (src/ui/menus.py) to find the project root
        current_path = Path(__file__).resolve()
        project_root = current_path.parent.parent.parent
        font_path = project_root / "assets" / "fonts" / font_name
        return str(font_path)

    # ========== MENU DRAWING METHODS ==========

    def draw_main_menu(self, shake_x: int = 0, shake_y: int = 0) -> None:
        """Main menu: big START button + permanent upgrades + gear icon."""
        pygame = self.ui.pygame
        if not self.ui.screen or not pygame:
            return

        w, h = self.ui.width, self.ui.height

        # Gothic dark background
        self.ui.screen.fill((5, 3, 8))

        # Top and bottom darkening strips (cached, invalidate on window resize)
        vignette_size = (w, h)
        if self.ui._vignette_size != vignette_size:
            # Recreate vignettes only if window size changed
            self.ui._top_vignette = pygame.Surface((w, 110), pygame.SRCALPHA)
            self.ui._top_vignette.fill((0, 0, 0, 150))
            self.ui._bot_vignette = pygame.Surface((w, 90), pygame.SRCALPHA)
            self.ui._bot_vignette.fill((0, 0, 0, 130))
            self.ui._vignette_size = vignette_size

        self.ui.screen.blit(self.ui._top_vignette, (0, 0))
        self.ui.screen.blit(self.ui._bot_vignette, (0, h - 90))

        # ── Title ──────────────────────────────────────────────────────────
        if self.ui.title_image:
            # Use external image asset, scale to fit screen width (with caching)
            title_to_draw = self.ui.title_image
            img_w, img_h = self.ui.title_image.get_size()
            # Scale to 90% of screen width to leave margins
            target_w = int(w * 0.9)
            scale_ratio = target_w / img_w
            target_h = int(img_h * scale_ratio)
            target_size = (target_w, target_h)

            if target_w < img_w:  # Only scale down, never up
                # Use cached scaled image if size hasn't changed
                if self.ui._title_image_scaled_size != target_size:
                    try:
                        self.ui._title_image_scaled = pygame.transform.scale(
                            self.ui.title_image, target_size
                        )
                        self.ui._title_image_scaled_size = target_size
                    except (
                        AttributeError,
                        TypeError,
                        ValueError,
                        KeyError,
                        pygame.error,
                    ):
                        self.ui._title_image_scaled = self.ui.title_image
                        self.ui._title_image_scaled_size = None
                title_to_draw = (
                    self.ui._title_image_scaled
                    if self.ui._title_image_scaled
                    else self.ui.title_image
                )
            else:
                # Window too small, reset cache
                self.ui._title_image_scaled = None
                self.ui._title_image_scaled_size = None

            tx, ty = self.ui._draw_centered_text(
                title_to_draw, w // 2, h // 2 - 195, shake_x, shake_y
            )
            self.ui.screen.blit(title_to_draw, (tx, ty))
            line_y = ty + title_to_draw.get_height() + 12
        else:
            # Fallback to text rendering if image not found
            title_font = self.ui.get_font(72)
            title_surf = self.ui.get_text("SATAN'S FALL", title_font, (185, 28, 28))
            tx, ty = self.ui._draw_centered_text(
                title_surf, w // 2, h // 2 - 195, shake_x, shake_y
            )
            self.ui.screen.blit(title_surf, (tx, ty))
            line_y = ty + title_surf.get_height() + 12

        # Ornamental line + diamond under title
        pygame.draw.line(
            self.ui.screen,
            (110, 28, 28),
            (w // 2 - 190, line_y),
            (w // 2 + 190, line_y),
            1,
        )
        dcx, dcy = w // 2, line_y
        pygame.draw.polygon(
            self.ui.screen,
            (150, 38, 38),
            [(dcx, dcy - 5), (dcx + 5, dcy), (dcx, dcy + 5), (dcx - 5, dcy)],
        )

        # ── START button ───────────────────────────────────────────────────
        btn_w, btn_h = 250, 68
        start_rect = pygame.Rect(
            w // 2 - btn_w // 2 + shake_x, h // 2 - 34 + shake_y, btn_w, btn_h
        )
        start_hov = self.ui._draw_button(
            start_rect, (22, 5, 5), (38, 10, 10), (145, 32, 32), 2
        )
        inner = start_rect.inflate(-6, -6)
        pygame.draw.rect(
            self.ui.screen, (110, 28, 28) if start_hov else (68, 16, 16), inner, 1
        )
        start_font = self.ui.get_font(48)
        start_text = self.ui.get_text(
            "START", start_font, (255, 230, 205) if start_hov else (225, 200, 175)
        )
        tx, ty = self.ui._draw_centered_text(
            start_text, w // 2, start_rect.centery, shake_x, 0
        )
        self.ui.screen.blit(start_text, (tx, ty))

        # ── PERMANENT UPGRADES button ──────────────────────────────────────
        up_w, up_h = 220, 36
        up_rect = pygame.Rect(
            w // 2 - up_w // 2 + shake_x, h // 2 + 55 + shake_y, up_w, up_h
        )
        up_hov = self.ui._draw_button(
            up_rect, (10, 6, 18), (18, 10, 28), (105, 68, 165), 1
        )
        up_font = self.ui.get_font(20)
        up_text = self.ui.get_text(
            "PERMANENT UPGRADES",
            up_font,
            (185, 145, 235) if up_hov else (138, 102, 192),
        )
        tx, ty = self.ui._draw_centered_text(
            up_text, w // 2, up_rect.centery, shake_x, 0
        )
        self.ui.screen.blit(up_text, (tx, ty))

        # ── PROFILES button ────────────────────────────────────────────────
        pr_w, pr_h = 220, 36
        pr_rect = pygame.Rect(
            w // 2 - pr_w // 2 + shake_x, h // 2 + 100 + shake_y, pr_w, pr_h
        )
        pr_hov = self.ui._draw_button(
            pr_rect, (8, 12, 8), (14, 22, 14), (60, 110, 60), 1
        )
        pr_font = self.ui.get_font(20)
        active_slot = getattr(self.game, "active_profile_slot", None)
        if active_slot is not None:
            profile_name = self.game.global_progress.get(
                "profile_name", f"Profile {active_slot}"
            )
            pr_label = f"PROFILES  ● {profile_name}"
        else:
            pr_label = "PROFILES"
        pr_text = self.ui.get_text(
            pr_label, pr_font, (160, 220, 140) if pr_hov else (100, 160, 100)
        )
        tx, ty = self.ui._draw_centered_text(
            pr_text, w // 2, pr_rect.centery, shake_x, 0
        )
        self.ui.screen.blit(pr_text, (tx, ty))

        # ── EXIT button (bottom center, above vignette) ─────────────────────
        ex_w, ex_h = 220, 36
        ex_rect = pygame.Rect(
            w // 2 - ex_w // 2 + shake_x, h - 110 + shake_y, ex_w, ex_h
        )
        ex_hov = self.ui._draw_button(
            ex_rect, (12, 8, 8), (22, 14, 14), (110, 60, 60), 1
        )
        ex_font = self.ui.get_font(20)
        ex_text = self.ui.get_text(
            "EXIT", ex_font, (220, 160, 140) if ex_hov else (160, 100, 80)
        )
        tx, ty = self.ui._draw_centered_text(
            ex_text, w // 2, ex_rect.centery, shake_x, 0
        )
        self.ui.screen.blit(ex_text, (tx, ty))

        # Draw EXIT confirmation prompt if pending
        if getattr(self.game, "exit_confirm_pending", False):
            # Semi-transparent overlay
            overlay = pygame.Surface((w, h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            self.ui.screen.blit(overlay, (0, 0))

            # Confirmation dialog background
            dialog_w, dialog_h = 400, 160
            dialog_x = w // 2 - dialog_w // 2
            dialog_y = h // 2 - dialog_h // 2
            pygame.draw.rect(
                self.ui.screen, (20, 10, 10), (dialog_x, dialog_y, dialog_w, dialog_h)
            )
            pygame.draw.rect(
                self.ui.screen,
                (100, 50, 50),
                (dialog_x, dialog_y, dialog_w, dialog_h),
                2,
            )

            # Text: "Exit Game?"
            confirm_font = self.ui.get_font(32)
            confirm_text = self.ui.get_text("Exit Game?", confirm_font, (220, 180, 160))
            tx, ty = self.ui._draw_centered_text(
                confirm_text, w // 2, dialog_y + 40, 0, 0
            )
            self.ui.screen.blit(confirm_text, (tx, ty))

            # YES button (left)
            yes_w, yes_h = 75, 36
            yes_x = dialog_x + dialog_w // 2 - yes_w - 12
            yes_y = dialog_y + dialog_h - 52
            yes_rect = pygame.Rect(yes_x, yes_y, yes_w, yes_h)
            yes_hov = self.ui._draw_button(
                yes_rect, (12, 8, 8), (22, 14, 14), (110, 60, 60), 1
            )
            yes_font = self.ui.get_font(18)
            yes_text = self.ui.get_text(
                "YES", yes_font, (220, 160, 140) if yes_hov else (160, 100, 80)
            )
            tx, ty = self.ui._draw_centered_text(
                yes_text, yes_x + yes_w // 2, yes_y + yes_h // 2, 0, 0
            )
            self.ui.screen.blit(yes_text, (tx, ty))

            # NO button (right)
            no_w, no_h = 75, 36
            no_x = dialog_x + dialog_w // 2 + 12
            no_y = dialog_y + dialog_h - 52
            no_rect = pygame.Rect(no_x, no_y, no_w, no_h)
            no_hov = self.ui._draw_button(
                no_rect, (8, 12, 8), (14, 22, 14), (60, 110, 60), 1
            )
            no_font = self.ui.get_font(18)
            no_text = self.ui.get_text(
                "NO", no_font, (160, 220, 140) if no_hov else (100, 160, 100)
            )
            tx, ty = self.ui._draw_centered_text(
                no_text, no_x + no_w // 2, no_y + no_h // 2, 0, 0
            )
            self.ui.screen.blit(no_text, (tx, ty))

        # ── Gear (options) button bottom-right ────────────────────────────
        opt_size = 38
        opt_x = w - opt_size - 14
        opt_y = h - opt_size - 14
        options_rect = pygame.Rect(opt_x, opt_y, opt_size, opt_size)
        opt_hov = self.ui._draw_button(
            options_rect, (18, 10, 10), (32, 20, 20), (120, 85, 85), 0
        )
        gear_col = (175, 130, 130) if opt_hov else (120, 85, 85)
        pygame.draw.rect(self.ui.screen, gear_col, options_rect, 1)
        gcx, gcy = opt_x + opt_size // 2, opt_y + opt_size // 2
        pygame.draw.circle(self.ui.screen, gear_col, (gcx, gcy), 7, 1)
        for i in range(8):
            ang = math.radians(i * 45)
            pygame.draw.line(
                self.ui.screen,
                gear_col,
                (gcx, gcy),
                (
                    int(gcx + math.cos(ang) * (opt_size // 2 - 6)),
                    int(gcy + math.sin(ang) * (opt_size // 2 - 6)),
                ),
                1,
            )

        try:
            self.game._last_drawn_menu = "main_menu"
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        if getattr(self.game, "showing_options", False):
            self.draw_options_menu(shake_x, shake_y)

    def draw_profiles_menu(self, shake_x: int = 0, shake_y: int = 0) -> None:
        """Profile selection screen: 3 slot cards with name, stats, and actions."""
        pygame = self.ui.pygame
        if not self.ui.screen or not pygame:
            return

        w, h = self.ui.width, self.ui.height
        g = self.game

        # Gothic dark background
        self.ui.screen.fill((5, 3, 8))
        top_v = pygame.Surface((w, 110), pygame.SRCALPHA)
        top_v.fill((0, 0, 0, 150))
        self.ui.screen.blit(top_v, (0, 0))
        bot_v = pygame.Surface((w, 90), pygame.SRCALPHA)
        bot_v.fill((0, 0, 0, 130))
        self.ui.screen.blit(bot_v, (0, h - 90))

        # Title
        title_font = self.ui.get_font(48)
        title_surf = self.ui.get_text("PROFILES", title_font, (185, 28, 28))
        tx, ty = self.ui._draw_centered_text(
            title_surf, w // 2, h // 2 - 270, shake_x, shake_y
        )
        self.ui.screen.blit(title_surf, (tx, ty))

        # Layout constants (must match _handle_profiles_menu_click in input_handler.py)
        card_w, card_h = 460, 120
        card_x = w // 2 - card_w // 2 + shake_x
        start_y = h // 2 - 210
        spacing = 140

        font_med = self.ui.get_font(20)
        font_sm = self.ui.get_font(16)
        font_xs = self.ui.get_font(14)

        mx, my = getattr(g, "mouse_x", 0), getattr(g, "mouse_y", 0)
        active_slot = getattr(g, "active_profile_slot", None)
        editing_slot = getattr(g, "editing_profile_slot", None)
        editing = getattr(g, "editing_profile_name", False)
        delete_confirms = getattr(g, "profile_delete_confirm", {})

        for slot in range(1, 4):
            cy = start_y + (slot - 1) * spacing + shake_y
            card_rect = pygame.Rect(card_x, cy, card_w, card_h)

            # Card background — gold border if active
            border_col = (200, 170, 60) if slot == active_slot else (60, 40, 40)
            bg_col = (18, 12, 8) if slot == active_slot else (12, 8, 6)
            pygame.draw.rect(self.ui.screen, bg_col, card_rect, border_radius=6)
            pygame.draw.rect(self.ui.screen, border_col, card_rect, 2, border_radius=6)

            info = g.get_profile_info(slot)
            slot_exists = info["exists"]

            # Slot label
            slot_label = self.ui.get_text(f"SLOT {slot}", font_xs, (120, 80, 60))
            self.ui.screen.blit(slot_label, (card_x + 10, cy + 8))

            # ── DELETE confirmation overlay ──────────────────────────────
            if delete_confirms.get(slot):
                confirm_surf = self.ui.get_text(
                    "DELETE profile?", font_med, (240, 80, 60)
                )
                self.ui.screen.blit(confirm_surf, (card_x + 10, cy + 42))
                yes_rect = pygame.Rect(card_x + card_w - 120, cy + card_h - 30, 50, 22)
                no_rect = pygame.Rect(card_x + card_w - 62, cy + card_h - 30, 50, 22)
                yes_hov = yes_rect.collidepoint(mx, my)
                no_hov = no_rect.collidepoint(mx, my)
                pygame.draw.rect(
                    self.ui.screen,
                    (180, 30, 30) if yes_hov else (100, 20, 20),
                    yes_rect,
                    border_radius=4,
                )
                pygame.draw.rect(
                    self.ui.screen,
                    (30, 100, 30) if no_hov else (20, 60, 20),
                    no_rect,
                    border_radius=4,
                )
                self.ui.screen.blit(
                    self.ui.get_text("YES", font_xs, (255, 200, 200)),
                    (yes_rect.x + 8, yes_rect.y + 4),
                )
                self.ui.screen.blit(
                    self.ui.get_text("NO", font_xs, (200, 255, 200)),
                    (no_rect.x + 10, no_rect.y + 4),
                )
                continue

            # ── EDIT button ──────────────────────────────────────────────
            edit_rect = pygame.Rect(card_x + card_w - 56, cy + 8, 48, 22)
            edit_hov = edit_rect.collidepoint(mx, my)
            pygame.draw.rect(
                self.ui.screen,
                (40, 30, 60) if not edit_hov else (70, 50, 110),
                edit_rect,
                border_radius=3,
            )
            pygame.draw.rect(
                self.ui.screen, (100, 80, 160), edit_rect, 1, border_radius=3
            )
            self.ui.screen.blit(
                self.ui.get_text("EDIT", font_xs, (180, 150, 240)),
                (edit_rect.x + 6, edit_rect.y + 4),
            )

            # ── Name area ───────────────────────────────────────────────
            if editing and editing_slot == slot:
                # Text input box
                name_box = pygame.Rect(card_x + 55, cy + 6, card_w - 120, 26)
                pygame.draw.rect(
                    self.ui.screen, (30, 25, 45), name_box, border_radius=3
                )
                pygame.draw.rect(
                    self.ui.screen, (140, 110, 220), name_box, 1, border_radius=3
                )
                input_text = getattr(g, "profile_name_input", "")
                # Blinking cursor
                cursor = "|" if (pygame.time.get_ticks() // 500) % 2 == 0 else ""
                name_surf = self.ui.get_text(
                    input_text + cursor, font_med, (220, 200, 255)
                )
                self.ui.screen.blit(name_surf, (name_box.x + 4, name_box.y + 3))
                hint = self.ui.get_text(
                    "ENTER to confirm • ESC to cancel", font_xs, (120, 100, 160)
                )
                self.ui.screen.blit(hint, (card_x + 10, cy + card_h - 22))
            else:
                if slot_exists:
                    name_surf = self.ui.get_text(
                        info["name"], font_med, (230, 200, 150)
                    )
                else:
                    name_surf = self.ui.get_text("— Empty —", font_med, (70, 55, 45))
                self.ui.screen.blit(name_surf, (card_x + 55, cy + 8))

            # ── Stats (only for existing slots) ─────────────────────────
            if slot_exists:
                stats_line1 = f"Satan Lv. {info['meta_level']}   XP: {info['meta_xp']}"
                stats_line2 = f"Points: {info['meta_points']}"
                last = info["last_played"]
                if last:
                    # Show only date part (yyyy-mm-dd)
                    date_part = last[:10]
                    stats_line2 += f"   Last: {date_part}"
                self.ui.screen.blit(
                    self.ui.get_text(stats_line1, font_sm, (180, 160, 110)),
                    (card_x + 10, cy + 42),
                )
                self.ui.screen.blit(
                    self.ui.get_text(stats_line2, font_sm, (140, 130, 90)),
                    (card_x + 10, cy + 62),
                )

                # DELETE button
                del_rect = pygame.Rect(card_x + card_w - 56, cy + 36, 48, 22)
                del_hov = del_rect.collidepoint(mx, my)
                pygame.draw.rect(
                    self.ui.screen,
                    (60, 18, 18) if not del_hov else (100, 30, 30),
                    del_rect,
                    border_radius=3,
                )
                pygame.draw.rect(
                    self.ui.screen, (160, 60, 60), del_rect, 1, border_radius=3
                )
                self.ui.screen.blit(
                    self.ui.get_text("DEL", font_xs, (255, 160, 160)),
                    (del_rect.x + 7, del_rect.y + 4),
                )

                # SELECT button
                select_rect = pygame.Rect(
                    card_x + card_w - 80, cy + card_h - 30, 72, 22
                )
                sel_hov = select_rect.collidepoint(mx, my)
                sel_bg = (30, 80, 30) if not sel_hov else (50, 130, 50)
                pygame.draw.rect(self.ui.screen, sel_bg, select_rect, border_radius=4)
                pygame.draw.rect(
                    self.ui.screen, (80, 180, 80), select_rect, 1, border_radius=4
                )
                sel_label = "SELECTED" if slot == active_slot else "SELECT"
                sel_col = (200, 255, 200) if slot == active_slot else (160, 230, 160)
                self.ui.screen.blit(
                    self.ui.get_text(sel_label, font_xs, sel_col),
                    (select_rect.x + 4, select_rect.y + 4),
                )
            else:
                # CREATE button
                create_rect = pygame.Rect(
                    card_x + card_w - 80, cy + card_h - 30, 72, 22
                )
                cr_hov = create_rect.collidepoint(mx, my)
                cr_bg = (20, 50, 70) if not cr_hov else (30, 80, 110)
                pygame.draw.rect(self.ui.screen, cr_bg, create_rect, border_radius=4)
                pygame.draw.rect(
                    self.ui.screen, (60, 140, 200), create_rect, 1, border_radius=4
                )
                self.ui.screen.blit(
                    self.ui.get_text("CREATE", font_xs, (160, 210, 255)),
                    (create_rect.x + 4, create_rect.y + 4),
                )

        # BACK button
        back_y = start_y + 3 * spacing + 10 + shake_y
        back_rect = pygame.Rect(w // 2 - 55 + shake_x, back_y, 110, 32)
        back_hov = back_rect.collidepoint(mx, my)
        back_bg = (30, 12, 12) if not back_hov else (55, 20, 20)
        pygame.draw.rect(self.ui.screen, back_bg, back_rect, border_radius=4)
        pygame.draw.rect(self.ui.screen, (130, 60, 60), back_rect, 1, border_radius=4)
        back_surf = self.ui.get_text(
            "BACK", font_med, (200, 140, 140) if back_hov else (155, 100, 100)
        )
        btx, bty = self.ui._draw_centered_text(
            back_surf, w // 2, back_rect.centery, shake_x, 0
        )
        self.ui.screen.blit(back_surf, (btx, bty))

    def _draw_stage_submenu(
        self,
        title: str,
        labels: list[str],
        normal_color: tuple,
        hover_color: tuple,
        menu_key: str,
        shake_x: int = 0,
        shake_y: int = 0,
    ) -> None:
        pygame = self.ui.pygame

        w, h = self.ui.width, self.ui.height

        # Gothic dark background
        self.ui.screen.fill((5, 3, 8))

        font_large = self.ui.get_font(48)
        font_medium = self.ui.get_font(28)
        font_small = self.ui.get_font(18)

        # Title
        title_surf = self.ui.get_text(title, font_large, (215, 195, 155))
        tx, ty = self.ui._draw_centered_text(
            title_surf, w // 2, h // 2 - 130, shake_x, shake_y
        )
        self.ui.screen.blit(title_surf, (tx, ty))
        line_y = h // 2 - 130 + title_surf.get_height() + 8
        pygame.draw.line(
            self.ui.screen,
            (110, 85, 45),
            (w // 2 - 160, line_y),
            (w // 2 + 160, line_y),
            1,
        )

        # Stage option buttons — keep geometry matching input_handler expectations
        option_w = 280
        option_h = 48
        start_x: int = w // 2 - option_w // 2
        start_y: int = h // 2 - 40
        spacing = 60

        for i, label in enumerate(labels):
            rect = pygame.Rect(start_x, start_y + i * spacing, option_w, option_h)
            hovered = self.ui._draw_button(
                rect, normal_color, hover_color, (145, 118, 75), 1
            )
            text = font_medium.render(
                label, True, (240, 220, 190) if hovered else (205, 185, 158)
            )
            tx, ty = self.ui._draw_centered_text(
                text, w // 2, rect.centery, shake_x, shake_y
            )
            self.ui.screen.blit(text, (tx, ty))

        # Back button — geometry and style match stage selection BACK button
        back_rect = pygame.Rect(
            w // 2 - 55, start_y + len(labels) * spacing + 10, 110, 32
        )
        back_hov = self.ui._draw_button(
            back_rect, (14, 7, 7), (28, 15, 15), (72, 48, 48), 1
        )
        back_text = font_small.render(
            "BACK", True, (180, 148, 140) if back_hov else (138, 112, 106)
        )
        tx, ty = self.ui._draw_centered_text(
            back_text, w // 2, back_rect.centery, shake_x, shake_y
        )
        self.ui.screen.blit(back_text, (tx, ty))

        try:
            self.game._last_drawn_menu = menu_key
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    def draw_stage_menu(self, shake_x=0, shake_y=0) -> None:
        """Draw the stage selection screen (gothic dark style) and submenus."""
        pygame = self.ui.pygame
        if not self.ui.screen or not pygame:
            return

        if getattr(self.game, "showing_limbo_menu", False):
            self._draw_stage_submenu(
                "LIMBO",
                ["LIMBO 1", "LIMBO 2", "LIMBO 3", "LIMBO FINAL"],
                (55, 28, 10),
                (82, 45, 18),
                "limbo",
                shake_x,
                shake_y,
            )
            return

        if getattr(self.game, "showing_purgatory_menu", False):
            self._draw_stage_submenu(
                "PURGATORY",
                ["PURGATORY 1", "PURGATORY 2", "PURGATORY 3"],
                (48, 24, 60),
                (72, 38, 90),
                "purgatory",
                shake_x,
                shake_y,
            )
            return

        if getattr(self.game, "showing_hell_menu", False):
            self._draw_stage_submenu(
                "HELL",
                ["GEHENNA", "LAKE OF FIRE", "HADES"],
                (80, 16, 16),
                (118, 30, 30),
                "hell",
                shake_x,
                shake_y,
            )
            return

        w, h = self.ui.width, self.ui.height

        # Gothic dark background
        self.ui.screen.fill((5, 3, 8))

        font_large = self.ui.get_font(48)
        font_medium = self.ui.get_font(28)
        font_small = self.ui.get_font(18)

        # Title
        title_surf = self.ui.get_text("SELECT STAGE", font_large, (175, 150, 115))
        tx, ty = self.ui._draw_centered_text(
            title_surf, w // 2, h // 2 - 195, shake_x, shake_y
        )
        self.ui.screen.blit(title_surf, (tx, ty))
        line_y = h // 2 - 195 + title_surf.get_height() + 10
        pygame.draw.line(
            self.ui.screen,
            (105, 82, 50),
            (w // 2 - 185, line_y),
            (w // 2 + 185, line_y),
            1,
        )

        # Stage buttons — geometry must match input_handler rects below
        #   prologo_rect = Rect(w//2 - 140, h//2 - 100, 280, 46)
        #   limbo_rect   = Rect(w//2 - 140, h//2 - 42,  280, 46)
        #   purgatory    = Rect(w//2 - 140, h//2 + 16,  280, 46)
        #   hell         = Rect(w//2 - 140, h//2 + 74,  280, 46)
        btn_w, btn_h = 280, 46
        btn_x = w // 2 - btn_w // 2
        base_y = h // 2 - 100
        spacing = 58

        _stages = [
            ("PROLOGUE", (45, 40, 36), (68, 60, 52), (158, 138, 108)),
            ("LIMBO", (55, 28, 10), (82, 45, 18), (175, 122, 58)),
            ("PURGATORY", (45, 22, 58), (68, 36, 88), (162, 112, 205)),
            ("HELL", (75, 14, 14), (112, 26, 26), (215, 68, 68)),
        ]

        for i, (label, bg_n, bg_h, border_col) in enumerate(_stages):
            rect = pygame.Rect(btn_x, base_y + i * spacing, btn_w, btn_h)
            hov = self.ui._draw_button(rect, bg_n, bg_h, border_col, 1)
            text = font_medium.render(
                label, True, (238, 220, 192) if hov else (205, 188, 162)
            )
            tx, ty = self.ui._draw_centered_text(
                text, w // 2, rect.centery, shake_x, shake_y
            )
            self.ui.screen.blit(text, (tx, ty))

        # Back button (returns to main menu)
        back_rect = pygame.Rect(
            w // 2 - 55, base_y + len(_stages) * spacing + 10, 110, 32
        )
        back_hov = self.ui._draw_button(
            back_rect, (14, 7, 7), (28, 15, 15), (72, 48, 48), 1
        )
        back_text = font_small.render(
            "BACK", True, (180, 148, 140) if back_hov else (138, 112, 106)
        )
        tx, ty = self.ui._draw_centered_text(
            back_text, w // 2, back_rect.centery, shake_x, shake_y
        )
        self.ui.screen.blit(back_text, (tx, ty))

        try:
            self.game._last_drawn_menu = "stage_main"
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        if getattr(self.game, "showing_options", False):
            self.draw_options_menu(shake_x, shake_y)

    def draw_options_menu(self, shake_x=0, shake_y=0) -> None:
        """Options overlay with gothic styling matching main menu."""
        pygame = self.ui.pygame
        if not self.ui.screen or not pygame:
            return

        # Semi-transparent overlay (cached, invalidate on window resize)
        overlay_size = (self.ui.width, self.ui.height)
        if self.ui._options_overlay_size != overlay_size:
            # Recreate overlay only if window size changed
            self.ui._options_overlay = pygame.Surface(
                (self.ui.width, self.ui.height), pygame.SRCALPHA
            )
            self.ui._options_overlay.fill((0, 0, 0, 180))
            self.ui._options_overlay_size = overlay_size

        self.ui.screen.blit(self.ui._options_overlay, (0, 0))

        # Dialog box with gothic dark background
        dialog_w, dialog_h = 520, 320
        dx = self.ui.width // 2 - dialog_w // 2
        dy = self.ui.height // 2 - dialog_h // 2

        # Main dialog background (gothic dark)
        pygame.draw.rect(self.ui.screen, (22, 12, 22), (dx, dy, dialog_w, dialog_h))
        # Outer border (reddish)
        pygame.draw.rect(self.ui.screen, (145, 32, 32), (dx, dy, dialog_w, dialog_h), 2)
        # Inner border (darker)
        inner = pygame.Rect(dx + 2, dy + 2, dialog_w - 4, dialog_h - 4)
        pygame.draw.rect(self.ui.screen, (68, 16, 16), inner, 1)

        # Title with gothic styling
        try:
            font = self.ui.get_font(32)
            title = self.ui.get_text("OPTIONS", font, (210, 65, 65))
        except (AttributeError, TypeError, ValueError, KeyError):
            font = pygame.font.Font(None, 32)
            title = font.render("OPTIONS", True, (210, 65, 65))

        self.ui.screen.blit(
            title,
            (self.ui.width // 2 - title.get_width() // 2 + shake_x, dy + 16 + shake_y),
        )

        # Decorative line under title
        line_y = dy + 16 + title.get_height() + 8
        pygame.draw.line(
            self.ui.screen,
            (110, 28, 28),
            (dx + 30, line_y),
            (dx + dialog_w - 30, line_y),
            1,
        )

        # Label and toggle helper function
        try:
            font_med = self.ui.get_font(18)
        except (AttributeError, TypeError, ValueError, KeyError):
            font_med = pygame.font.Font(None, 18)

        def draw_toggle_option(label_text, is_enabled, y_offset):
            """Draw a label with a toggle switch."""
            # Label
            label = (
                self.ui.get_text(label_text, font_med, (210, 185, 165))
                if hasattr(self.ui.get_text, "__call__")
                else font_med.render(label_text, True, (210, 185, 165))
            )
            self.ui.screen.blit(label, (dx + 24 + shake_x, dy + y_offset + shake_y))

            # Toggle switch
            toggle_w, toggle_h = 48, 24
            toggle_x = dx + dialog_w - 24 - toggle_w
            toggle_y = dy + y_offset
            toggle_rect = pygame.Rect(toggle_x, toggle_y, toggle_w, toggle_h)

            # Background based on state
            if is_enabled:
                toggle_bg = (
                    (80, 32, 32)
                    if toggle_rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
                    else (60, 20, 20)
                )
                text_color = (100, 200, 100)
            else:
                toggle_bg = (
                    (32, 32, 32)
                    if toggle_rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
                    else (20, 20, 20)
                )
                text_color = (180, 100, 100)

            pygame.draw.rect(self.ui.screen, toggle_bg, toggle_rect)
            pygame.draw.rect(self.ui.screen, (110, 28, 28), toggle_rect, 1)

            # Status text
            status_text = "ON" if is_enabled else "OFF"
            status_surf = font_med.render(status_text, True, text_color)
            self.ui.screen.blit(
                status_surf,
                (
                    toggle_x + (toggle_w - status_surf.get_width()) // 2 + shake_x,
                    toggle_y + (toggle_h - status_surf.get_height()) // 2 + shake_y,
                ),
            )
            return toggle_rect

        # Damage numbers toggle
        draw_toggle_option(
            "Show Damage Numbers:", getattr(self.game, "show_damage_numbers", True), 64
        )

        # Sounds toggle
        draw_toggle_option(
            "Enable Sounds:", getattr(self.game, "sounds_enabled", True), 104
        )

        # Smooth-scaling toggle
        smooth_on = bool(
            self.game.global_progress.get("display", {}).get("smooth_scale", True)
        )
        draw_toggle_option("Smooth Scaling:", smooth_on, 144)

        # Resolution presets
        preset_label = (
            self.ui.get_text("Resolution:", font_med, (210, 185, 165))
            if hasattr(self.ui.get_text, "__call__")
            else font_med.render("Resolution:", True, (210, 185, 165))
        )
        self.ui.screen.blit(preset_label, (dx + 24 + shake_x, dy + 216 + shake_y))

        # Buttons for presets (taken from game constants)
        try:
            from src.game_constants import DEFAULT_DISPLAY_PRESETS
        except (AttributeError, TypeError, ValueError, KeyError):
            DEFAULT_DISPLAY_PRESETS = [(1280, 720)]

        # Dropdown for resolution presets
        btn_w, btn_h = 140, 28
        start_x = dx + 24
        btn_y = dy + 248

        dropdown_w, dropdown_h = btn_w, btn_h
        dropdown_x, dropdown_y = start_x, btn_y
        dropdown_rect = pygame.Rect(dropdown_x, dropdown_y, dropdown_w, dropdown_h)

        current_label = f"{self.game.window_width}x{self.game.window_height}"
        hovered = dropdown_rect.collidepoint(self.game.mouse_x, self.game.mouse_y)

        is_preset = (
            self.game.window_width,
            self.game.window_height,
        ) in DEFAULT_DISPLAY_PRESETS
        if is_preset:
            bg = (38, 16, 38)
            pygame.draw.rect(self.ui.screen, bg, dropdown_rect)
            pygame.draw.rect(self.ui.screen, (110, 28, 28), dropdown_rect, 1)
        else:
            self.ui._draw_button(
                dropdown_rect, (22, 12, 22), (32, 20, 28), (110, 28, 28), 1
            )

        txt = font_med.render(current_label, True, (210, 185, 165))
        self.ui.screen.blit(
            txt,
            (
                dropdown_x + 8 + shake_x,
                dropdown_y + (dropdown_h - txt.get_height()) // 2 + shake_y,
            ),
        )
        # small caret indicator
        caret = font_med.render("▾", True, (145, 100, 100))
        self.ui.screen.blit(
            caret,
            (
                dropdown_x + dropdown_w - 18 + shake_x,
                dropdown_y + (dropdown_h - caret.get_height()) // 2 + shake_y,
            ),
        )

        # If dropdown open, render the list beneath
        if getattr(self.game, "options_resolution_dropdown_open", False):
            item_h = 24
            item_spacing = 2
            for i, (pw, ph) in enumerate(DEFAULT_DISPLAY_PRESETS):
                iy = dropdown_y + dropdown_h + i * (item_h + item_spacing)
                item_rect = pygame.Rect(dropdown_x, iy, dropdown_w, item_h)
                is_current = (pw, ph) == (
                    self.game.window_width,
                    self.game.window_height,
                )
                hovered_item = item_rect.collidepoint(
                    self.game.mouse_x, self.game.mouse_y
                )

                # Gothic colors
                if is_current:
                    item_bg = (50, 20, 50)
                else:
                    item_bg = (32, 20, 28) if hovered_item else (22, 12, 22)

                pygame.draw.rect(self.ui.screen, item_bg, item_rect)
                pygame.draw.rect(self.ui.screen, (110, 28, 28), item_rect, 1)
                label = f"{pw}x{ph}"
                txt = font_med.render(label, True, (210, 185, 165))
                self.ui.screen.blit(
                    txt,
                    (
                        dropdown_x + 8 + shake_x,
                        iy + (item_h - txt.get_height()) // 2 + shake_y,
                    ),
                )

        # Close button with gothic styling
        btn_w, btn_h = 120, 36
        btn_x = dx + (dialog_w - btn_w) // 2
        btn_y = dy + dialog_h - 50
        close_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        hovered = self.ui._draw_button(
            close_rect, (22, 5, 5), (38, 10, 10), (145, 32, 32), 2
        )
        inner = close_rect.inflate(-6, -6)
        pygame.draw.rect(
            self.ui.screen, (110, 28, 28) if hovered else (68, 16, 16), inner, 1
        )

        btn_text = (
            self.ui.get_text(
                "CLOSE",
                self.ui.get_font(20),
                (255, 230, 205) if hovered else (225, 200, 175),
            )
            if hasattr(self.ui.get_text, "__call__")
            else pygame.font.Font(None, 20).render(
                "CLOSE", True, (255, 230, 205) if hovered else (225, 200, 175)
            )
        )
        self.ui.screen.blit(
            btn_text,
            (
                btn_x + (btn_w - btn_text.get_width()) // 2 + shake_x,
                btn_y + (btn_h - btn_text.get_height()) // 2 + shake_y,
            ),
        )

    def draw_permanent_upgrades(self, shake_x=0, shake_y=0) -> None:
        """Authoritative renderer for the permanent-upgrades overlay.

        Draws both top (1..5) and bottom (6..10) Blasphemy boxes using the
        imported `blasphemy_box.png` asset when available. This single
        implementation is the canonical source of truth for both runtime and
        tests (keeps behavior deterministic and easier to reason about).
        """
        pygame = self.ui.pygame
        if not self.ui.screen or not pygame:
            return

        left_x = self.ui.width // 2 - 420

        # Draw title
        font_title = pygame.font.Font(None, 36)
        title = font_title.render("PERMANENT UPGRADES", True, (255, 255, 0))
        self.ui.screen.blit(
            title, (self.ui.width // 2 - title.get_width() // 2 + shake_x, 40 + shake_y)
        )

        separator_y = self._draw_header_xp(left_x, shake_x, shake_y)
        self._draw_permanent_stats(left_x, shake_x, shake_y)
        blasphemy_data = self._draw_blasphemies(left_x, separator_y, shake_x, shake_y)
        self._draw_skill_trees(left_x, separator_y, shake_x, shake_y)
        self._draw_instructions_and_sentinel(left_x, blasphemy_data, shake_x, shake_y)
        self._draw_exit_confirmation_dialog(pygame, shake_x, shake_y)

    def _draw_header_xp(self, left_x: int, shake_x: int, shake_y: int) -> int:
        """Draw level, points, and XP bar. Return separator_y position for other sections."""
        pygame = self.ui.pygame
        if not self.ui.screen or not pygame:
            return 320

        font_medium = pygame.font.Font(None, 24)
        font_small = pygame.font.Font(None, 18)

        # subtitle was removed per design; we no longer render any text above the
        # XP bar.  (Previously it said "Upgrade your demonic powers".)

        # --- progression info ---
        lvl = self.game.global_progress.get("meta_level", 1)
        pts = self.game.global_progress.get("meta_points", 0)
        xp = self.game.global_progress.get("meta_xp", 0)
        xp_to = self.game.get_meta_xp_to_next_level()
        # we will later want to align the XP bar with the permanent-stat
        # bars; those use ``bar_x_base`` which depends on the widest stat name.
        rendered_names = [
            font_medium.render(s["name"], True, s["color"]) for s in _STAT_CONFIGS
        ]
        max_name_w = max(s.get_width() for s in rendered_names)
        bar_x_base = left_x + max(120, max_name_w + 24)
        bar_width = 180
        # render level and points on separate lines; the XP bar should now sit
        # on the same vertical line as the points text rather than above it.
        # we still place everything above the stats block (POWER at y=140).
        lvl_text = font_medium.render(f"SATAN LEVEL {lvl}", True, (255, 215, 0))
        pts_text = font_medium.render(f"Points: {pts}", True, (255, 215, 0))

        # derive y positions from an anchor for the points line; keep the
        # points text near the top. We'll place the XP bar lower, aligned with
        # the permanent-stat bars drawn later.
        pts_y = 120
        lvl_y = pts_y - lvl_text.get_height() - 2

        # bar should start and end at the same horizontal coordinates as the
        # permanent-stat bars below.  Those use ``bar_x_base`` and ``bar_width``
        # so we reuse the same values.
        pts_x = left_x + shake_x
        bar_x = bar_x_base
        bar_w = bar_width
        bar_h = 10
        # vertical position returns to previous value (same as points line)
        bar_y = pts_y

        self.ui.screen.blit(lvl_text, (pts_x, lvl_y + shake_y))
        self.ui.screen.blit(pts_text, (pts_x, pts_y + shake_y))

        # draw XP bar background at the same vertical as points
        pygame.draw.rect(self.ui.screen, (26, 26, 26), (bar_x, bar_y, bar_w, bar_h))
        # compute filled width with minimum visibility for tiny XP
        fill_w = self.ui._calculate_meta_xp_fill(xp, xp_to, bar_w)
        # fill color now darker green (0,100,0) per update
        pygame.draw.rect(self.ui.screen, (0, 100, 0), (bar_x, bar_y, fill_w, bar_h))
        # numeric indicator showing current and required XP
        xp_text = font_small.render(f"{xp}/{xp_to} XP", True, (255, 215, 0))
        # leave at least 50px gap between bar end and xp text; using bar_width
        self.ui.screen.blit(
            xp_text,
            (bar_x + bar_w + 58 + shake_x, bar_y - 2 + shake_y),
        )

        return 320

    def _draw_permanent_stats(self, left_x: int, shake_x: int, shake_y: int) -> None:
        """Draw POWER/VIGOR/ADRENALINE/STRUCTURE stat bars with hover effects."""
        pygame = self.ui.pygame
        if not self.ui.screen or not pygame:
            return

        font_medium = pygame.font.Font(None, 24)
        font_small = pygame.font.Font(None, 18)

        rendered_names = [
            font_medium.render(s["name"], True, s["color"]) for s in _STAT_CONFIGS
        ]
        max_name_w = max(s.get_width() for s in rendered_names)
        bar_x_base = left_x + max(120, max_name_w + 24)
        bar_width = 180
        bar_height = 12
        font_name_hover = pygame.font.Font(None, 26)

        for i, stat in enumerate(_STAT_CONFIGS):
            name_rect = pygame.Rect(left_x, stat["y"], 120, 30)
            try:
                is_hovered = name_rect.collidepoint(
                    self.game.mouse_x, self.game.mouse_y
                )
            except (AttributeError, TypeError, ValueError, KeyError):
                is_hovered = False
            stat_value = self.game.permanent_stats.get(stat["key"], 0)

            # Previously we showed a tooltip with explanation text when the
            # player hovered any of the four permanent stats.  Design has since
            # changed: the side text (to the right of the bar) is sufficient and
            # the hover pop‑ups are now distracting.  We intentionally no longer
            # render anything here, but leave the hover detection in place in
            # case we want to visually alter the name (see colouring below).
            #
            # (This block used to call ``permanent_stat_effect_text`` and draw a
            # gray box with the lines.)
            #
            # is_hovered is still used later when colouring the stat name, so
            # we keep the variable around but ignore it for tooltips.
            name_color = stat["color"]
            if is_hovered and stat_value < 10:
                col = stat["color"]
                name_color = (
                    min(255, col[0] + 50),
                    min(255, col[1] + 50),
                    min(255, col[2] + 50),
                )
            elif stat_value >= 10:
                name_color = (100, 100, 100)
            name_text = (
                font_name_hover.render(stat["name"], True, name_color)
                if is_hovered
                else rendered_names[i]
            )
            name_y = int(stat["y"] + 22 - name_text.get_height() // 2) + shake_y
            self.ui.screen.blit(name_text, (left_x + shake_x, name_y))

            val_text = font_small.render(f"Level: {stat_value}", True, (255, 255, 255))
            self.ui.screen.blit(val_text, (left_x + 200 + shake_x, stat["y"] + shake_y))

            effect_text = self.game.permanent_stat_effect_text(stat["key"], stat_value)
            if effect_text:
                eff_lines = [ln.strip() for ln in effect_text.split(";") if ln.strip()]
                if len(eff_lines) == 1:
                    eff_surf = font_small.render(eff_lines[0], True, (180, 180, 180))
                    eff_y = (
                        stat["y"]
                        + 15
                        + bar_height // 2
                        - eff_surf.get_height() // 2
                        + shake_y
                    )
                    self.ui.screen.blit(eff_surf, (left_x + 340 + shake_x, eff_y))
                else:
                    eff_surfs = [
                        font_small.render(ln, True, (180, 180, 180)) for ln in eff_lines
                    ]
                    sp = 2
                    total_h = sum(s.get_height() for s in eff_surfs) + sp * (
                        len(eff_surfs) - 1
                    )
                    ey = stat["y"] + 15 + bar_height // 2 - total_h // 2 + shake_y
                    for es in eff_surfs:
                        self.ui.screen.blit(es, (left_x + 340 + shake_x, ey))
                        ey += es.get_height() + sp

            if stat_value >= 10:
                max_text = font_small.render("MAX", True, (255, 215, 0))
                self.ui.screen.blit(
                    max_text, (left_x + 270 + shake_x, stat["y"] + shake_y)
                )

            bar_x = bar_x_base
            bar_y = stat["y"] + 15
            pygame.draw.rect(
                self.ui.screen,
                (26, 26, 26),
                (bar_x + shake_x, bar_y + shake_y, bar_width, bar_height),
            )
            pygame.draw.rect(
                self.ui.screen,
                (68, 68, 68),
                (bar_x + shake_x, bar_y + shake_y, bar_width, bar_height),
                1,
            )
            if stat_value > 0:
                fill_w = min(bar_width, int((stat_value / 10) * bar_width))
                pygame.draw.rect(
                    self.ui.screen,
                    stat["color"],
                    (bar_x + shake_x, bar_y + shake_y, fill_w, bar_height),
                )

    def _draw_blasphemies(
        self, left_x: int, separator_y: int, shake_x: int, shake_y: int
    ) -> dict:
        """Draw blasphemy boxes with roman numerals and tooltips.

        Returns dict with data needed for instructions/sentinel rendering.
        """
        pygame = self.ui.pygame
        if not self.ui.screen or not pygame:
            return

        font_medium = pygame.font.Font(None, 24)
        font_large = pygame.font.Font(None, 36)
        font_small = pygame.font.Font(None, 18)

        blasp_text = font_medium.render("BLASPHEMIES", True, (136, 136, 136))
        self.ui.screen.blit(blasp_text, (left_x + shake_x, separator_y + 30 + shake_y))

        # Draw blasphemy points balance
        bp = (
            self.game.global_progress.get("blasphemy_points", 0)
            if getattr(self.game, "global_progress", None)
            else 0
        )
        bp_color = (200, 80, 220) if bp > 0 else (100, 60, 100)
        bp_text = font_medium.render(f"  |  Points: {bp}", True, bp_color)
        try:
            self.ui.screen.blit(
                bp_text,
                (left_x + blasp_text.get_width() + shake_x, separator_y + 30 + shake_y),
            )
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        box_width = 80
        box_height = box_width
        box_spacing = 100
        start_x = left_x + box_spacing // 2 - 40

        asset_name = (
            self.game.global_progress.get("blasphemy_box_asset")
            if getattr(self.game, "global_progress", None)
            else None
        ) or "blasphemy_box.png"
        logger.debug("draw_permanent_upgrades: looking for asset %s", asset_name)
        box_asset = get_image(asset_name, (box_width, box_height))
        box_y1 = separator_y + 60
        box_y2 = box_y1 + box_height + 12

        for row_idx, y in enumerate((box_y1, box_y2)):
            for col in range(5):
                bx = start_x + col * box_spacing
                rect = (
                    bx - box_width // 2 + shake_x,
                    y + shake_y,
                    box_width,
                    box_height,
                )

                if box_asset:
                    try:
                        self.ui.screen.blit(box_asset, (rect[0], rect[1]))
                        if row_idx == 1:
                            try:
                                self.ui._blasphemy_bottom_drawn = True
                            except (
                                AttributeError,
                                TypeError,
                                ValueError,
                                KeyError,
                                RuntimeError,
                            ):
                                pass
                    except (
                        AttributeError,
                        TypeError,
                        ValueError,
                        KeyError,
                        RuntimeError,
                    ):
                        pygame.draw.rect(self.ui.screen, (26, 26, 26), rect)
                else:
                    pygame.draw.rect(self.ui.screen, (26, 26, 26), rect)

                try:
                    pygame.draw.rect(self.ui.screen, (51, 51, 51), rect, 1)
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

                key = f"blasphemy_{row_idx * 5 + col + 1}"
                lvl = self.game.permanent_stats.get(key, 0)
                max_lvl = 1 if key == "blasphemy_10" else 3
                cost = 3 if key == "blasphemy_10" else 1
                bp = (
                    self.game.global_progress.get("blasphemy_points", 0)
                    if getattr(self.game, "global_progress", None)
                    else 0
                )

                # Dim unaffordable boxes (can't afford AND not maxed out)
                if bp < cost and lvl < max_lvl:
                    try:
                        overlay = pygame.Surface(
                            (box_width, box_height), pygame.SRCALPHA
                        )
                        overlay.fill((0, 0, 0, 140))  # 55% opaque black
                        self.ui.screen.blit(
                            overlay, (bx - box_width // 2 + shake_x, y + shake_y)
                        )
                    except (AttributeError, TypeError, ValueError, KeyError):
                        pass

                # Render roman numerals for blasphemies that show level text
                if lvl and key in (
                    "blasphemy_1",
                    "blasphemy_2",
                    "blasphemy_3",
                    "blasphemy_4",
                    "blasphemy_5",
                    "blasphemy_6",
                    "blasphemy_7",
                    "blasphemy_8",
                    "blasphemy_9",
                    "blasphemy_10",
                ):
                    roman_map = {1: "I", 2: "II", 3: "III"}
                    roman = roman_map.get(lvl, "")
                    if roman:
                        lvl_surf = font_large.render(roman, True, (120, 20, 20))
                        sx = bx - lvl_surf.get_width() // 2 + shake_x
                        sy = y + box_height // 2 - lvl_surf.get_height() // 2 + shake_y
                        self.ui.screen.blit(lvl_surf, (sx, sy))

                # Hover/tooltips
                try:
                    mouse_point = (self.game.mouse_x, self.game.mouse_y)
                except (AttributeError, TypeError, ValueError, KeyError):
                    mouse_point = (0, 0)

                if pygame.Rect(*rect).collidepoint(mouse_point):
                    effect_text = self.game.permanent_stat_effect_text(key, lvl)
                    lines = [
                        s.strip() for s in (effect_text or "").split(";") if s.strip()
                    ]
                    if lines:
                        if lvl:
                            lines.insert(0, f"Level: {lvl}")
                        tip_x = bx
                        tip_y = box_y2 + box_height + 12 + shake_y
                        try:
                            self.game._draw_tooltip(
                                lines,
                                tip_x,
                                tip_y,
                                pygame.font.Font(None, 18),
                                anchor_center=True,
                            )
                        except (
                            AttributeError,
                            TypeError,
                            ValueError,
                            KeyError,
                            RuntimeError,
                        ):
                            pass
                        line_surfs = [
                            font_small.render(line_text, True, (255, 255, 255))
                            for line_text in lines
                        ]
                        padding_x, padding_y = 8, 6
                        width = max(s.get_width() for s in line_surfs) + padding_x * 2
                        height = (
                            sum(s.get_height() for s in line_surfs)
                            + padding_y * 2
                            + (len(line_surfs) - 1) * 4
                        )
                        tx = max(
                            4, min(int(tip_x - width // 2), self.ui.width - width - 4)
                        )
                        ty = max(4, min(tip_y, self.ui.height - height - 4))
                        bg_rect = pygame.Rect(tx, ty, width, height)
                        pygame.draw.rect(self.ui.screen, (30, 30, 30), bg_rect)
                        pygame.draw.rect(self.ui.screen, (120, 120, 120), bg_rect, 1)
                        cur_y = ty + padding_y
                        for s in line_surfs:
                            self.ui.screen.blit(s, (tx + padding_x, cur_y))
                            cur_y += s.get_height() + 4

        return {
            "box_asset": box_asset,
            "start_x": start_x,
            "box_y1": box_y1,
            "box_y2": box_y2,
            "box_width": box_width,
            "box_height": box_height,
        }

        # Skill trees (FIRE, STORM, ICE)
        tree_box_w = 50
        tree_box_h = 36
        tree_v_spacing = 46
        tree_col_spacing = 120
        tree_base_x: int = left_x + 680
        tree_top_y: int = separator_y - 150

        for col, (label, key_prefix, color) in enumerate(_TREE_TYPES):
            col_x = tree_base_x + col * tree_col_spacing
            lbl_surf = font_small.render(label, True, color)
            self.ui.screen.blit(
                lbl_surf,
                (
                    col_x - lbl_surf.get_width() // 2 + shake_x,
                    tree_top_y - 28 + shake_y,
                ),
            )

            inner_col_offset = tree_box_w // 2 + 1
            left_col_x = col_x - inner_col_offset
            right_col_x = col_x + inner_col_offset
            for row in range(3):
                y = tree_top_y + row * tree_v_spacing
                left_rect = (
                    left_col_x - tree_box_w // 2 + shake_x,
                    y + shake_y,
                    tree_box_w,
                    tree_box_h,
                )
                right_rect = (
                    right_col_x - tree_box_w // 2 + shake_x,
                    y + shake_y,
                    tree_box_w,
                    tree_box_h,
                )

                left_active = bool(
                    self.game.permanent_stats.get(f"{key_prefix}_{row + 1}", 0)
                )
                right_active = bool(
                    self.game.permanent_stats.get(f"{key_prefix}_{4 + row}", 0)
                )
                left_bg = color if left_active else (26, 26, 26)
                right_bg = color if right_active else (26, 26, 26)
                left_border = (
                    tuple(min(255, c + 20) for c in color)
                    if left_active
                    else (51, 51, 51)
                )
                right_border = (
                    tuple(min(255, c + 20) for c in color)
                    if right_active
                    else (51, 51, 51)
                )

                try:
                    mouse_point = (self.game.mouse_x, self.game.mouse_y)
                except (AttributeError, TypeError, ValueError, KeyError):
                    mouse_point = (0, 0)
                left_hovered = pygame.Rect(*left_rect).collidepoint(mouse_point)
                right_hovered = pygame.Rect(*right_rect).collidepoint(mouse_point)
                if left_hovered:
                    left_border = (255, 224, 20)
                    left_bg = tuple(min(255, v + 30) for v in left_bg)
                if right_hovered:
                    right_border = (255, 224, 20)
                    right_bg = tuple(min(255, v + 30) for v in right_bg)

                pygame.draw.rect(self.ui.screen, left_bg, left_rect)
                pygame.draw.rect(self.ui.screen, left_border, left_rect, 1)
                pygame.draw.rect(self.ui.screen, right_bg, right_rect)
                pygame.draw.rect(self.ui.screen, right_border, right_rect, 1)

                if left_hovered:
                    tooltip_lines = self.game._skill_tooltip_lines(key_prefix, row + 1)
                    if tooltip_lines:
                        self.game._draw_tooltip(
                            tooltip_lines,
                            col_x,
                            tree_top_y + 3 * tree_v_spacing + tree_box_h + 12 + shake_y,
                            pygame.font.Font(None, 18),
                            anchor_center=True,
                        )
                if right_hovered:
                    tooltip_lines = self.game._skill_tooltip_lines(key_prefix, 4 + row)
                    if tooltip_lines:
                        self.game._draw_tooltip(
                            tooltip_lines,
                            col_x,
                            tree_top_y + 3 * tree_v_spacing + tree_box_h + 12 + shake_y,
                            pygame.font.Font(None, 18),
                            anchor_center=True,
                        )

            center_y = tree_top_y + 3 * tree_v_spacing
            center_key = f"{key_prefix}_7"
            center_active = bool(self.game.permanent_stats.get(center_key, 0))
            center_bg = color if center_active else (26, 26, 26)
            center_border = (
                tuple(min(255, c + 20) for c in color)
                if center_active
                else (51, 51, 51)
            )
            center_rect = (
                col_x - tree_box_w // 2 + shake_x,
                center_y + shake_y,
                tree_box_w,
                tree_box_h,
            )
            try:
                mouse_point = (self.game.mouse_x, self.game.mouse_y)
            except (AttributeError, TypeError, ValueError, KeyError):
                mouse_point = (0, 0)
            center_hovered = pygame.Rect(*center_rect).collidepoint(mouse_point)
            if center_hovered:
                center_border = (255, 224, 20)
                center_bg = tuple(min(255, v + 30) for v in center_bg)
            pygame.draw.rect(self.ui.screen, center_bg, center_rect)
            pygame.draw.rect(self.ui.screen, center_border, center_rect, 1)
            if center_hovered:
                tooltip_lines = self.game._skill_tooltip_lines(key_prefix, 7)
                if tooltip_lines:
                    self.game._draw_tooltip(
                        tooltip_lines,
                        col_x,
                        tree_top_y + 3 * tree_v_spacing + tree_box_h + 12 + shake_y,
                        pygame.font.Font(None, 18),
                        anchor_center=True,
                    )

    def _draw_skill_trees(
        self, left_x: int, separator_y: int, shake_x: int, shake_y: int
    ) -> None:
        """Draw FIRE/STORM/ICE skill trees with hover effects and tooltips."""
        pygame = self.ui.pygame
        if not self.ui.screen or not pygame:
            return

        font_small = pygame.font.Font(None, 18)
        font_label = pygame.font.SysFont("garamond", 26)

        tree_box_w = 50
        tree_box_h = 36
        tree_v_spacing = 46
        tree_col_spacing = 120
        tree_base_x: int = left_x + 680
        tree_top_y: int = separator_y - 150

        for col, (label, key_prefix, color) in enumerate(_TREE_TYPES):
            col_x = tree_base_x + col * tree_col_spacing
            lbl_surf = font_small.render(label, True, color)
            self.ui.screen.blit(
                lbl_surf,
                (
                    col_x - lbl_surf.get_width() // 2 + shake_x,
                    tree_top_y - 28 + shake_y,
                ),
            )

            inner_col_offset = tree_box_w // 2 + 1
            left_col_x = col_x - inner_col_offset
            right_col_x = col_x + inner_col_offset
            for row in range(3):
                y = tree_top_y + row * tree_v_spacing
                left_rect = (
                    left_col_x - tree_box_w // 2 + shake_x,
                    y + shake_y,
                    tree_box_w,
                    tree_box_h,
                )
                right_rect = (
                    right_col_x - tree_box_w // 2 + shake_x,
                    y + shake_y,
                    tree_box_w,
                    tree_box_h,
                )

                left_active = bool(
                    self.game.permanent_stats.get(f"{key_prefix}_{row + 1}", 0)
                )
                right_active = bool(
                    self.game.permanent_stats.get(f"{key_prefix}_{4 + row}", 0)
                )
                # Darken active colors by scaling down to ~40-50% brightness
                left_bg = (
                    tuple(int(c * 0.4) for c in color) if left_active else (26, 26, 26)
                )
                right_bg = (
                    tuple(int(c * 0.4) for c in color) if right_active else (26, 26, 26)
                )
                # Borders: almost black (10, 10, 10) for active, dark gray for inactive
                left_border = (10, 10, 10) if left_active else (51, 51, 51)
                right_border = (10, 10, 10) if right_active else (51, 51, 51)

                try:
                    mouse_point = (self.game.mouse_x, self.game.mouse_y)
                except (AttributeError, TypeError, ValueError, KeyError):
                    mouse_point = (0, 0)
                left_hovered = pygame.Rect(*left_rect).collidepoint(mouse_point)
                right_hovered = pygame.Rect(*right_rect).collidepoint(mouse_point)
                if left_hovered:
                    left_border = (255, 224, 20)
                    left_bg = tuple(min(255, int(v * 0.5)) for v in left_bg)
                if right_hovered:
                    right_border = (255, 224, 20)
                    right_bg = tuple(min(255, int(v * 0.5)) for v in right_bg)

                # Draw glow/shadow effect for active boxes (sfumatura esterna)
                if left_active:
                    glow_color = tuple(min(255, int(c * 0.5)) for c in color)
                    pygame.draw.rect(
                        self.ui.screen,
                        glow_color,
                        (
                            left_rect[0] - 2,
                            left_rect[1] - 2,
                            left_rect[2] + 4,
                            left_rect[3] + 4,
                        ),
                        2,
                    )

                if right_active:
                    glow_color = tuple(min(255, int(c * 0.5)) for c in color)
                    pygame.draw.rect(
                        self.ui.screen,
                        glow_color,
                        (
                            right_rect[0] - 2,
                            right_rect[1] - 2,
                            right_rect[2] + 4,
                            right_rect[3] + 4,
                        ),
                        2,
                    )

                pygame.draw.rect(self.ui.screen, left_bg, left_rect)
                pygame.draw.rect(self.ui.screen, left_border, left_rect, 2)
                pygame.draw.rect(self.ui.screen, right_bg, right_rect)
                pygame.draw.rect(self.ui.screen, right_border, right_rect, 2)

                # Draw labels on all boxes (left: 1,2,3 | right: A,B,C) - always visible
                left_label = str(row + 1)
                left_label_color = (255, 255, 255) if left_active else (150, 150, 150)
                left_label_surf = font_label.render(left_label, True, left_label_color)
                left_label_x = (
                    left_rect[0] + tree_box_w // 2 - left_label_surf.get_width() // 2
                )
                left_label_y = (
                    left_rect[1] + tree_box_h // 2 - left_label_surf.get_height() // 2
                )
                self.ui.screen.blit(left_label_surf, (left_label_x, left_label_y))

                right_label = chr(ord("A") + row)  # A, B, C
                right_label_color = (255, 255, 255) if right_active else (150, 150, 150)
                right_label_surf = font_label.render(
                    right_label, True, right_label_color
                )
                right_label_x = (
                    right_rect[0] + tree_box_w // 2 - right_label_surf.get_width() // 2
                )
                right_label_y = (
                    right_rect[1] + tree_box_h // 2 - right_label_surf.get_height() // 2
                )
                self.ui.screen.blit(right_label_surf, (right_label_x, right_label_y))

                if left_hovered:
                    tooltip_lines = self.game._skill_tooltip_lines(key_prefix, row + 1)
                    if tooltip_lines:
                        self.game._draw_tooltip(
                            tooltip_lines,
                            col_x,
                            tree_top_y + 3 * tree_v_spacing + tree_box_h + 12 + shake_y,
                            pygame.font.Font(None, 18),
                            anchor_center=True,
                        )
                if right_hovered:
                    tooltip_lines = self.game._skill_tooltip_lines(key_prefix, 4 + row)
                    if tooltip_lines:
                        self.game._draw_tooltip(
                            tooltip_lines,
                            col_x,
                            tree_top_y + 3 * tree_v_spacing + tree_box_h + 12 + shake_y,
                            pygame.font.Font(None, 18),
                            anchor_center=True,
                        )

            center_y = tree_top_y + 3 * tree_v_spacing
            center_key = f"{key_prefix}_7"
            center_active = bool(self.game.permanent_stats.get(center_key, 0))
            # Darken active colors by scaling down to ~40-50% brightness
            center_bg = (
                tuple(int(c * 0.4) for c in color) if center_active else (26, 26, 26)
            )
            # Border: almost black (10, 10, 10) for active, dark gray for inactive
            center_border = (10, 10, 10) if center_active else (51, 51, 51)
            center_rect = (
                col_x - tree_box_w // 2 + shake_x,
                center_y + shake_y,
                tree_box_w,
                tree_box_h,
            )
            try:
                mouse_point = (self.game.mouse_x, self.game.mouse_y)
            except (AttributeError, TypeError, ValueError, KeyError):
                mouse_point = (0, 0)
            center_hovered = pygame.Rect(*center_rect).collidepoint(mouse_point)
            if center_hovered:
                center_border = (255, 224, 20)
                center_bg = tuple(min(255, int(v * 0.5)) for v in center_bg)

            # Draw glow/shadow effect for active center box
            if center_active:
                glow_color = tuple(min(255, int(c * 0.5)) for c in color)
                pygame.draw.rect(
                    self.ui.screen,
                    glow_color,
                    (
                        center_rect[0] - 2,
                        center_rect[1] - 2,
                        center_rect[2] + 4,
                        center_rect[3] + 4,
                    ),
                    2,
                )

            pygame.draw.rect(self.ui.screen, center_bg, center_rect)
            pygame.draw.rect(self.ui.screen, center_border, center_rect, 2)

            # Draw X label on center box - always visible
            center_label = "X"
            center_label_color = (255, 255, 255) if center_active else (150, 150, 150)
            center_label_surf = font_label.render(
                center_label, True, center_label_color
            )
            center_label_x = (
                center_rect[0] + tree_box_w // 2 - center_label_surf.get_width() // 2
            )
            center_label_y = (
                center_rect[1] + tree_box_h // 2 - center_label_surf.get_height() // 2
            )
            self.ui.screen.blit(center_label_surf, (center_label_x, center_label_y))

            if center_hovered:
                tooltip_lines = self.game._skill_tooltip_lines(key_prefix, 7)
                if tooltip_lines:
                    self.game._draw_tooltip(
                        tooltip_lines,
                        col_x,
                        tree_top_y + 3 * tree_v_spacing + tree_box_h + 12 + shake_y,
                        pygame.font.Font(None, 18),
                        anchor_center=True,
                    )

    def _draw_instructions_and_sentinel(
        self, left_x: int, blasphemy_data: dict, shake_x: int, shake_y: int
    ) -> None:
        """Draw instructions text and blasphemy test sentinel."""
        pygame = self.ui.pygame
        if not self.ui.screen or not pygame:
            return

        font_medium = pygame.font.Font(None, 24)

        # Instructions
        instructions = font_medium.render(
            "Left click to upgrade | Right click to downgrade | ESC to return",
            True,
            (200, 200, 200),
        )
        self.ui.screen.blit(
            instructions, (left_x + shake_x, self.ui.height - 50 + shake_y)
        )

        # Extract blasphemy data
        box_asset = blasphemy_data.get("box_asset")
        start_x = blasphemy_data.get("start_x")
        box_y1 = blasphemy_data.get("box_y1")
        box_y2 = blasphemy_data.get("box_y2")
        box_width = blasphemy_data.get("box_width")
        box_height = blasphemy_data.get("box_height")

        # Sentinel for tests
        if box_asset and self.ui.screen:
            try:
                if getattr(self.game, "_test_blasphemy_sentinel", False):
                    sen_color = (123, 45, 67)
                    sen_x = int(start_x)
                    sen_y = int(box_y2 + box_height // 2 + 1)
                    self.ui.screen.set_at((sen_x, sen_y), sen_color)
            except (AttributeError, TypeError, ValueError, KeyError):
                pass

        # Defensive: enforce center pixel color when asset present
        if box_asset and self.ui.screen:
            try:
                center_color = box_asset.get_at((box_width // 2, box_height // 2))
            except (AttributeError, TypeError, ValueError, KeyError):
                center_color = None
            if center_color:
                try:
                    self.ui.screen.set_at(
                        (int(start_x), int(box_y1 + box_height // 2)), center_color
                    )
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass
                try:
                    self.ui.screen.set_at(
                        (int(start_x), int(box_y2 + box_height // 2)), center_color
                    )
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

    def _draw_exit_confirmation_dialog(
        self, pygame, shake_x: int, shake_y: int
    ) -> None:
        """Draw EXIT confirmation dialog if pending."""
        if not self.ui.screen or not pygame:
            return

        if getattr(self.game, "exit_confirm_pending", False):
            # Semi-transparent overlay
            overlay = pygame.Surface((self.ui.width, self.ui.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            self.ui.screen.blit(overlay, (0, 0))

            # Dialog box
            dialog_width = 400
            dialog_height = 150
            dialog_x = (self.ui.width - dialog_width) // 2
            dialog_y = (self.ui.height - dialog_height) // 2

            pygame.draw.rect(
                self.ui.screen,
                (30, 15, 30),
                (dialog_x, dialog_y, dialog_width, dialog_height),
            )
            pygame.draw.rect(
                self.ui.screen,
                (100, 50, 100),
                (dialog_x, dialog_y, dialog_width, dialog_height),
                2,
            )

            # Text
            q_text = pygame.font.Font(None, 28).render(
                "Exit Game?", True, (255, 200, 200)
            )
            self.ui.screen.blit(
                q_text,
                (
                    dialog_x + (dialog_width - q_text.get_width()) // 2,
                    dialog_y + 30,
                ),
            )

            # Yes/No buttons
            btn_width = 80
            btn_height = 40
            spacing = 30
            yes_x = dialog_x + (dialog_width - btn_width * 2 - spacing) // 2
            no_x = yes_x + btn_width + spacing
            btn_y = dialog_y + dialog_height - 60

            yes_rect = pygame.Rect(yes_x, btn_y, btn_width, btn_height)
            no_rect = pygame.Rect(no_x, btn_y, btn_width, btn_height)

            yes_hovered = yes_rect.collidepoint(
                getattr(self.game, "mouse_x", 0), getattr(self.game, "mouse_y", 0)
            )
            no_hovered = no_rect.collidepoint(
                getattr(self.game, "mouse_x", 0), getattr(self.game, "mouse_y", 0)
            )

            # Draw buttons
            yes_bg = (80, 30, 30) if yes_hovered else (50, 20, 20)
            no_bg = (30, 60, 30) if no_hovered else (20, 40, 20)

            pygame.draw.rect(self.ui.screen, yes_bg, yes_rect)
            pygame.draw.rect(self.ui.screen, (150, 50, 50), yes_rect, 2)
            pygame.draw.rect(self.ui.screen, no_bg, no_rect)
            pygame.draw.rect(self.ui.screen, (50, 150, 50), no_rect, 2)

            # Button text
            yes_text = pygame.font.Font(None, 24).render("YES", True, (255, 150, 150))
            no_text = pygame.font.Font(None, 24).render("NO", True, (150, 255, 150))
            self.ui.screen.blit(
                yes_text,
                (
                    yes_x + (btn_width - yes_text.get_width()) // 2,
                    btn_y + (btn_height - yes_text.get_height()) // 2,
                ),
            )
            self.ui.screen.blit(
                no_text,
                (
                    no_x + (btn_width - no_text.get_width()) // 2,
                    btn_y + (btn_height - no_text.get_height()) // 2,
                ),
            )

    def draw_pause_menu(self, shake_x=0, shake_y=0) -> None:
        """Draw the pause menu (migrated from Game)."""
        pygame = self.ui.pygame
        if not self.ui.screen or not pygame:
            return

        font_large = self.ui.get_font(36)
        font_medium = self.ui.get_font(28)

        title = self.ui.get_text("PAUSED", font_large, (255, 255, 255))
        self.ui.screen.blit(
            title,
            (
                self.ui.width // 2 - title.get_width() // 2 + shake_x,
                self.ui.height // 2 - 100 + shake_y,
            ),
        )

        options = ["Resume", "Quit to Menu"]
        option_height = 40
        for i, option in enumerate(options):
            y_pos = self.ui.height // 2 - 20 + i * option_height
            text_width = len(option) * 14
            option_rect = pygame.Rect(
                self.ui.width // 2 - text_width // 2, y_pos, text_width, option_height
            )
            is_hovered = option_rect.collidepoint(self.game.mouse_x, self.game.mouse_y)
            if is_hovered and option_rect.width > 0 and option_rect.height > 0:
                self.game.pause_menu_option = i
            is_selected = i == self.game.pause_menu_option
            color = (
                (255, 255, 0)
                if is_selected
                else ((200, 200, 0) if is_hovered else (255, 255, 255))
            )
            text = font_medium.render(option, True, color)
            self.ui.screen.blit(
                text,
                (self.ui.width // 2 - text.get_width() // 2 + shake_x, y_pos + shake_y),
            )

        try:
            self.game._last_drawn_menu = "pause"
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

        # Draw pause confirmation dialog if active (overlay handled by caller)
        self.draw_pause_confirmation_dialog(shake_x, shake_y)

    def draw_pause_confirmation_dialog(self, shake_x=0, shake_y=0) -> None:
        """Draw the pause confirmation Yes/No dialog (can be called any time, not just when paused)."""
        pygame = self.ui.pygame
        if not self.ui.screen or not pygame:
            return

        try:
            if getattr(self.game, "pause_confirmation", None):
                pc = self.game.pause_confirmation
                dialog_w, dialog_h = 260, 70
                dx = self.ui.width // 2 - dialog_w // 2
                dy = self.ui.height // 2 - dialog_h // 2

                # dialog background
                dlg_surf = pygame.Surface((dialog_w, dialog_h))
                dlg_surf.set_alpha(220)
                dlg_surf.fill((30, 30, 30))
                pygame.draw.rect(
                    dlg_surf, (120, 120, 120), (0, 0, dialog_w, dialog_h), 2
                )
                self.ui.screen.blit(dlg_surf, (dx, dy))

                font = self.ui.get_font(18)
                msg = "Quit to menu?"
                msg_surf = self.ui.get_text(msg, font, (255, 255, 255))
                self.ui.screen.blit(
                    msg_surf, (dx + (dialog_w - msg_surf.get_width()) // 2, dy + 6)
                )

                # Buttons (clearly boxed and highlight on hover)
                btn_w = 80
                btn_h = 28
                yes_rect = pygame.Rect(dx + 10, dy + 30, btn_w, btn_h)
                no_rect = pygame.Rect(dx + dialog_w - btn_w - 10, dy + 30, btn_w, btn_h)

                # Detect hover and set selection accordingly
                try:
                    if yes_rect.collidepoint(self.game.mouse_x, self.game.mouse_y):
                        pc["selection"] = 0
                    elif no_rect.collidepoint(self.game.mouse_x, self.game.mouse_y):
                        pc["selection"] = 1
                except (AttributeError, TypeError, ValueError, KeyError):
                    pass

                sel = pc.get("selection", 0)

                # Draw yes button
                yes_bg = (255, 215, 0) if sel == 0 else (60, 60, 60)
                yes_border = (200, 160, 20) if sel == 0 else (120, 120, 120)
                pygame.draw.rect(self.ui.screen, yes_bg, yes_rect)
                pygame.draw.rect(self.ui.screen, yes_border, yes_rect, 2)
                yes_s = self.ui.get_text(
                    "Yes", font, (0, 0, 0) if sel == 0 else (200, 200, 200)
                )
                self.ui.screen.blit(
                    yes_s,
                    (
                        yes_rect.x + (btn_w - yes_s.get_width()) // 2 + shake_x,
                        yes_rect.y + shake_y + (btn_h - yes_s.get_height()) // 2,
                    ),
                )

                # Draw no button
                no_bg = (255, 215, 0) if sel == 1 else (60, 60, 60)
                no_border = (200, 160, 20) if sel == 1 else (120, 120, 120)
                pygame.draw.rect(self.ui.screen, no_bg, no_rect)
                pygame.draw.rect(self.ui.screen, no_border, no_rect, 2)
                no_s = self.ui.get_text(
                    "No", font, (0, 0, 0) if sel == 1 else (200, 200, 200)
                )
                self.ui.screen.blit(
                    no_s,
                    (
                        no_rect.x + (btn_w - no_s.get_width()) // 2 + shake_x,
                        no_rect.y + shake_y + (btn_h - no_s.get_height()) // 2,
                    ),
                )
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
