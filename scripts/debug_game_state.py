import os
import sys

# headless
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.append(r"c:\Users\Gla\Desktop\Nuova cartella\giochi\satans fall")
from src.game import Game

print("creating game")
g = Game(debug=True)
print(
    "initial paused",
    g.paused,
    "awaiting_weapon",
    g.awaiting_weapon_choice,
    "awaiting_upgrade",
    g.awaiting_upgrade,
)

print("select stage")
g.select_stage("prologo")
print(
    "after select",
    g.paused,
    g.awaiting_weapon_choice,
    g.awaiting_upgrade,
    "stage_countdown",
    g.stage_start_countdown,
)

print("setting countdown and health")
g.stage_start_countdown = 0

g.player.health = 0

print("before update: paused", g.paused, "awaiting_weapon", g.awaiting_weapon_choice)

g.update()
print(
    "after update",
    g.paused,
    g.awaiting_weapon_choice,
    g.awaiting_upgrade,
    g.showing_game_over,
)
