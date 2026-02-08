import os
import logging

import pygame

logger = logging.getLogger(__name__)


class Player(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.x = x
        self.y = y
        self.width = 61  # Increased by another 10%
        self.height = 73  # Increased by another 10%
        self.max_health = 100
        self.health = self.max_health
        self.speed = 300
        self.velocity_x = 0

        # XP and Level system
        self.xp = 0
        self.level = 1
        self.xp_to_next_level = 100
        self.damage_multiplier = 1.0
        self.fire_rate_multiplier = 1.0
        self.projectile_size_multiplier = 1.0
        self.damage_reduction_multiplier = 1.0

        # Load image
        try:
            assets_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
            self.base_image = pygame.image.load(
                os.path.join(assets_dir, "satan.png")
            ).convert_alpha()
            self.base_image = pygame.transform.scale(
                self.base_image, (self.width, self.height)
            )
            self.image = self.base_image.copy()

            # Create walking animation frames
            self.walk_frames = []
            try:
                self.create_walk_frames()
            except Exception as e:
                logger.warning("Could not create walk animation: %s", e)
                self.walk_frames = []
        except Exception as e:
            logger.warning("Could not load satan.png, using fallback drawing: %s", e)
            # Fallback to drawing
            self.base_image = None
            self.image = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self.draw_satan()
            self.walk_frames = []
        self.rect = self.image.get_rect(center=(self.x, self.y))

    def create_walk_frames(self):
        """Create walking animation frames by shifting pixels"""
        if self.base_image is None:
            return

        width, height = self.base_image.get_size()

        # Create 4 walking frames
        for frame in range(4):
            frame_surface = self.base_image.copy()
            pixels = pygame.surfarray.pixels3d(frame_surface)
            alpha_pixels = pygame.surfarray.pixels_alpha(frame_surface)

            # Calculate leg movement offsets
            if frame == 0:
                offset_left = 0
                offset_right = 0
            elif frame == 1:
                offset_left = -2  # Left leg forward
                offset_right = 1
            elif frame == 2:
                offset_left = 0
                offset_right = 0
            elif frame == 3:
                offset_left = 1  # Right leg forward
                offset_right = -2

            # Apply pixel shifting to simulate leg movement
            new_pixels = pixels.copy()
            new_alpha = alpha_pixels.copy()

            for y in range(height):
                for x in range(width):
                    if x < width // 2:
                        # Left side (left leg)
                        src_x = x - offset_left
                        if 0 <= src_x < width:
                            new_pixels[x, y] = pixels[src_x, y]
                            new_alpha[x, y] = alpha_pixels[src_x, y]
                        else:
                            new_pixels[x, y] = [0, 0, 0]
                            new_alpha[x, y] = 0
                    else:
                        # Right side (right leg)
                        src_x = x - offset_right
                        if 0 <= src_x < width:
                            new_pixels[x, y] = pixels[src_x, y]
                            new_alpha[x, y] = alpha_pixels[src_x, y]
                        else:
                            new_pixels[x, y] = [0, 0, 0]
                            new_alpha[x, y] = 0

            # Unlock surface arrays
            del pixels
            del alpha_pixels

            # Create new surface with modified pixels
            new_frame = pygame.Surface((width, height), pygame.SRCALPHA)
            pygame.surfarray.blit_array(new_frame, new_pixels)
            pygame.surfarray.pixels_alpha(new_frame)[:] = new_alpha

            self.walk_frames.append(new_frame)

            # Create flipped version
            flipped_frame = pygame.transform.flip(new_frame, True, False)
            self.walk_frames.append(flipped_frame)

    def draw_satan(self):
        """Draw Satan character - bright red demon with horns"""
        self.image.fill((0, 0, 0, 0))  # Transparent background

        # Body (bright red)
        pygame.draw.ellipse(self.image, (255, 0, 0), (10, 20, 30, 25))

        # Head (bright red)
        pygame.draw.circle(self.image, (255, 50, 50), (25, 12), 8)

        # Horns (bright red)
        pygame.draw.polygon(self.image, (255, 100, 100), [(15, 5), (18, 0), (20, 6)])
        pygame.draw.polygon(self.image, (255, 100, 100), [(30, 5), (32, 0), (35, 6)])

        # Eyes (white and black)
        pygame.draw.circle(self.image, (255, 255, 255), (21, 10), 2)
        pygame.draw.circle(self.image, (255, 255, 255), (29, 10), 2)
        pygame.draw.circle(self.image, (0, 0, 0), (21, 10), 1)
        pygame.draw.circle(self.image, (0, 0, 0), (29, 10), 1)

        # Evil grin (white)
        pygame.draw.line(self.image, (255, 200, 200), (20, 14), (30, 14), 2)

        # Arms
        pygame.draw.line(self.image, (255, 0, 0), (12, 30), (5, 35), 3)
        pygame.draw.line(self.image, (255, 0, 0), (38, 30), (45, 35), 3)

        # Legs
        pygame.draw.line(self.image, (150, 0, 0), (18, 45), (18, 55), 3)
        pygame.draw.line(self.image, (150, 0, 0), (32, 45), (32, 55), 3)

    def move_left(self):
        self.velocity_x = -self.speed

    def move_right(self):
        self.velocity_x = self.speed

    def update(self, screen_width):
        # Apply velocity
        self.x += self.velocity_x / 60  # Divide by FPS

        # Clamp to screen
        self.x = max(self.width // 2, min(self.x, screen_width - self.width // 2))

        # Reset velocity
        self.velocity_x = 0

        # Update rect
        self.rect.center = (self.x, self.y)

    def take_damage(self, damage):
        actual_damage = damage * self.damage_reduction_multiplier
        self.health = max(0, self.health - actual_damage)

    def gain_xp(self, amount):
        self.xp += amount
        if self.xp >= self.xp_to_next_level:
            self.level_up()

    def level_up(self):
        self.level += 1
        self.xp -= self.xp_to_next_level
        self.xp_to_next_level = int(
            self.xp_to_next_level * 1.2
        )  # Increase XP requirement
        # Note: Upgrade selection will be handled in the game class

    def draw(self, screen, shake_x=0, shake_y=0, anim_frame=0, is_moving=False):
        # Apply shake offset
        draw_x = self.rect.x + shake_x
        draw_y = self.rect.y + shake_y

        # Apply bobbing effect if moving
        bob_offset = 0
        current_image = self.image

        if is_moving and self.walk_frames:
            # Create bobbing effect (up and down movement)
            bob_cycle = anim_frame % 4
            if bob_cycle == 1:
                bob_offset = -1
            elif bob_cycle == 3:
                bob_offset = 1
            else:
                bob_offset = 0

            # Use walking frames
            frame_index = anim_frame % 8  # 8 frames total (4 normal + 4 flipped)
            if frame_index < len(self.walk_frames):
                current_image = self.walk_frames[frame_index]

        screen.blit(current_image, (draw_x, draw_y + bob_offset))

        # Draw health bar with shake offset
        bar_width = 40
        bar_height = 5
        bar_x = self.rect.centerx - bar_width // 2 + shake_x
        bar_y = self.rect.bottom + 5 + shake_y

        # Health bar background
        pygame.draw.rect(screen, (100, 0, 0), (bar_x, bar_y, bar_width, bar_height))

        # Health bar fill
        health_ratio = max(0, self.health / self.max_health)
        pygame.draw.rect(
            screen, (0, 200, 0), (bar_x, bar_y, bar_width * health_ratio, bar_height)
        )
