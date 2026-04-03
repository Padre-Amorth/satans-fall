import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.append(r"c:\Users\Gla\Desktop\Nuova cartella\giochi\satans fall")
from src.game import Game
from src.game_constants import STAGE_SETTINGS

print("creating game")
g = Game()
print("selecting hell")
g.select_stage("hell")
# set the walls

g.left_wall_points = [(100, 0), (100, 200)]
g.right_wall_points = [(500, 0), (500, 200)]

settings = STAGE_SETTINGS["hell"]
print("settings", settings)

surface = g.screen
surface.fill(settings["bg_color"])
g.ui.draw_game_world()

coords = [(300, 100), (10, 100), (60, 100), (50, 100), (100, 100)]
for c in coords:
    print(c, surface.get_at(c)[:3])
