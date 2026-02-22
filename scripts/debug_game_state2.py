import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.append(r"c:\Users\Gla\Desktop\Nuova cartella\giochi\satans fall")
from src.game import Game

g = Game(debug=True)
print(
    "flags before select: paused",
    g.paused,
    "stage_menu",
    g.showing_stage_menu,
    "permanent_upgrades",
    g.showing_permanent_upgrades,
    "prologo_end",
    g.showing_prologo_end,
)

g.select_stage("prologo")
print(
    "flags after select: paused",
    g.paused,
    "stage_menu",
    g.showing_stage_menu,
    "permanent_upgrades",
    g.showing_permanent_upgrades,
    "prologo_end",
    g.showing_prologo_end,
)

# simulate test modifications

g.stage_start_countdown = 0

g.stage_start_timer = 0

print(
    "flags before update",
    g.paused,
    g.showing_stage_menu,
    g.showing_permanent_upgrades,
    g.showing_prologo_end,
)

g.player.health = 0

g.update()
print(
    "flags after update",
    g.paused,
    g.showing_game_over,
    g.showing_stage_menu,
    g.showing_permanent_upgrades,
    g.showing_prologo_end,
)
