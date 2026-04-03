import pygame

from src.game import Game

# generate a placeholder if missing
from tools.generate_limbo_boss_asset import main

main()

pygame.init()
g = Game(debug=True)
boss = g.enemy_manager.spawn_boss("limbo")
print("boss dims", boss.width, boss.height)
print("centre pixel", boss.image.get_at((boss.width // 2, boss.height // 2)))
