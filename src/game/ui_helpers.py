"""UI-related helpers: FloatingText, StatConfig, and text rendering utilities."""

from typing import TypedDict


class StatConfig(TypedDict):
    name: str
    key: str
    color: tuple[int, int, int]
    y: int


class FloatingText:
    """Simple floating text for damage/feedback displayed on screen."""

    def __init__(
        self,
        text: str,
        x: float,
        y: float,
        *,
        color=(255, 255, 255),
        outline_color: tuple[int, int, int] | None = None,
        font_size: int = 20,
        vy: float = -1.2,
        life: int = 70,
        max_rise_pixels: int = 12,
    ):
        self.text = str(text)
        self.x = float(x)
        self.y = float(y)
        self.initial_y = float(y)
        # Maximum number of pixels the text may rise before stopping
        self.max_rise_pixels = int(max_rise_pixels)
        self.vy = float(vy)
        self.life = int(life)
        self.max_life = int(life)
        self.color = tuple(color)
        self.outline_color = tuple(outline_color) if outline_color is not None else None
        self.font_size = int(font_size)

    def update(self) -> None:
        # Move
        self.y += self.vy

        # Enforce maximum rise: do not allow the text to rise above initial_y - max_rise_pixels
        try:
            if (self.initial_y - self.y) > self.max_rise_pixels:
                # Clamp position and stop upward motion
                self.y = self.initial_y - float(self.max_rise_pixels)
                self.vy = 0.0

        except Exception:
            pass

        # While text is fading (past 60% of life), reduce movement speed smoothly
        try:
            if self.life < (self.max_life * 0.6):
                # Damp velocity toward zero so upward motion slows as it fades
                self.vy *= 0.92
                # apply a smaller upward pull to keep slight motion
                self.vy -= 0.02
            else:
                # normal upward acceleration early on
                self.vy -= 0.05
        except Exception:
            # Fallback behavior
            self.vy -= 0.03
        self.life -= 1

    @property
    def alive(self) -> bool:
        return self.life > 0

    def fade_alpha(self) -> int:
        try:
            # Slower fade due to larger max_life; just map life ratio to alpha
            return max(0, int(255 * (self.life / max(1, self.max_life))))
        except Exception:
            return 255
