import importlib
from typing import TYPE_CHECKING, Any

from pygame import Rect, Surface

if TYPE_CHECKING:
    import pygame  # type: ignore

try:
    pygame: importlib.ModuleType = importlib.import_module("pygame")
except Exception:
    pygame: importlib.ModuleType = importlib.import_module("pygame_ce")  # type: ignore

import math
import os


class Projectile(pygame.sprite.Sprite):
    def __init__(
        self,
        x,
        y,
        vel_x,
        vel_y,
        damage=15,
        radius=5,
        is_enemy_projectile=False,
        weapon_type=None,
        source=None,
    ) -> None:
        super().__init__()
        self.x: Any = x
        self.y: Any = y
        self.vel_x: Any = vel_x
        self.vel_y: Any = vel_y
        self.damage: int = damage
        self.radius: int = radius
        self.is_enemy_projectile: bool = is_enemy_projectile
        self.weapon_type = weapon_type  # 'spear', 'shotgun', or None for regular
        self.source = source  # 'orbital' for orbital projectiles
        self.pierce_all = False  # Default: projectiles don't pierce
        self.pierce_count = 0  # For limited piercing

        # Create image
        self.image = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        self.draw_projectile()
        self.rect: Rect | math.Any = self.image.get_rect(center=(self.x, self.y))

    def draw_projectile(self) -> None:
        """Draw projectile, try to load image first"""
        # Special handling for different weapon types
        if self.weapon_type == "spear":
            # Create spear image: long shaft with arrowhead
            length: int = max(30, self.radius * 6)
            width: int = max(2, int(self.radius * 0.6))
            self.image = pygame.Surface((length, width * 2), pygame.SRCALPHA)

            # Shaft (tan color)
            pygame.draw.rect(
                self.image,
                (217, 211, 183),
                (0, width // 2, length - self.radius * 2, width),
            )

            # Arrowhead (light tan)
            arrowhead_points: list[tuple[int, int]] = [
                (length, width),  # tip
                (length - self.radius * 2, width // 2),  # center back
                (length, 0),  # top
            ]
            pygame.draw.polygon(self.image, (255, 220, 178), arrowhead_points)

            # Outline
            pygame.draw.polygon(self.image, (207, 162, 111), arrowhead_points, 1)

        elif self.weapon_type == "shotgun":
            # Shotgun pellets: orange circles
            self.image = pygame.Surface(
                (self.radius * 2, self.radius * 2), pygame.SRCALPHA
            )
            pygame.draw.circle(
                self.image, (255, 200, 0), (self.radius, self.radius), self.radius
            )
            pygame.draw.circle(
                self.image, (255, 150, 0), (self.radius, self.radius), self.radius - 1
            )

        elif self.source == "orbital":
            # Orbital projectiles: light blue circles
            self.image = pygame.Surface(
                (self.radius * 2, self.radius * 2), pygame.SRCALPHA
            )
            pygame.draw.circle(
                self.image, (102, 204, 255), (self.radius, self.radius), self.radius
            )
            pygame.draw.circle(
                self.image, (51, 170, 255), (self.radius, self.radius), self.radius - 1
            )

        else:
            # Regular projectiles or enemy projectiles
            try:
                image_name: str = (
                    "enemy_projectile.png"
                    if self.is_enemy_projectile
                    else "projectile.png"
                )
                image_path: str = os.path.join("assets", image_name)
                loaded_image: Surface | math.Any = pygame.image.load(image_path).convert_alpha()
                self.image: Surface | math.Any = pygame.transform.scale(
                    loaded_image, (self.radius * 2, self.radius * 2)
                )
            except Exception:
                # Fallback to drawing - use simple shapes as fallback (log the error for debugging)
                # print(f"Warning: projectile image load failed: {e}")  # Uncomment for debugging
                if self.is_enemy_projectile:
                    # Enemy projectile (golden/shiny)
                    pygame.draw.circle(
                        self.image,
                        (255, 215, 0),
                        (self.radius, self.radius),
                        self.radius,
                    )  # Gold outer
                    pygame.draw.circle(
                        self.image,
                        (255, 255, 0),
                        (self.radius, self.radius),
                        self.radius - 1,
                    )  # Bright yellow inner
                    # Shiny highlight
                    pygame.draw.circle(
                        self.image,
                        (255, 255, 255),
                        (self.radius - 1, self.radius - 1),
                        max(1, self.radius // 3),
                    )
                else:
                    # Player projectile - draw as a red "6" as a simple fallback
                    self.image.fill((0, 0, 0, 0))  # Transparent background
                    font = pygame.font.Font(None, max(8, int(self.radius * 2)))
                    text: Surface | math.Any = font.render("6", True, (255, 51, 51))  # Red color fallback
                    text_rect: Rect | math.Any = text.get_rect(center=(self.radius, self.radius))
                    self.image.blit(text, text_rect)

    def update(self) -> None:
        self.x += self.vel_x / 60  # Divide by FPS
        self.y += self.vel_y / 60
        self.rect.center = (self.x, self.y)

    def draw(self, screen, shake_x=0, shake_y=0) -> None:
        draw_x: int | math.Any = self.rect.x + shake_x
        draw_y: int | math.Any = self.rect.y + shake_y

        if self.weapon_type == "spear":
            # Rotate spear based on velocity direction
            angle: float = math.degrees(math.atan2(self.vel_y, self.vel_x))
            rotated_image: Surface | math.Any = pygame.transform.rotate(self.image, -angle)
            rotated_rect: Rect | math.Any = rotated_image.get_rect(
                center=(draw_x + self.radius, draw_y + self.radius)
            )
            screen.blit(rotated_image, rotated_rect)
        else:
            screen.blit(self.image, (draw_x, draw_y))
