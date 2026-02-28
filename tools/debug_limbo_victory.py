import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), "src"))
from game import Game
from src.entities.enemy import Enemy
from src.game_constants import LIMBO_HORDE_TIME

g = Game()
g.reset_game()
g.select_stage("limbo")
# trigger horde

g.time_elapsed = LIMBO_HORDE_TIME
for _ in range(int(g.fps / 5) + 2):
    g.spawn_system.update_enemy_spawning()

print("initial", g.limbo_horde_initial, "active", g.limbo_horde_active)
# kill all
for i in range(g.limbo_horde_initial):
    g.record_enemy_kill()
print(
    "after kills",
    g.limbo_horde_killed,
    "completed",
    g.limbo_horde_completed,
    "ready",
    g.limbo_horde_ready_for_victory,
)
# add stray
stray = Enemy(0, 0)
g.enemies.add(stray)
print("added stray; enemy count", len(g.enemies))
# run a couple frames
for frame in range(3):
    g.update()
    print(
        "frame",
        frame,
        "timer",
        g.limbo_horde_victory_timer,
        "ready",
        g.limbo_horde_ready_for_victory,
        "enemies",
        len(g.enemies),
    )
# remove stray
g.record_enemy_kill()
g.enemies.remove(stray)
print(
    "removed stray; enemy count",
    len(g.enemies),
    "ready",
    g.limbo_horde_ready_for_victory,
    "timer",
    g.limbo_horde_victory_timer,
)
# run more frames
for frame in range(10):
    g.update()
    print(
        "frame post-removal",
        frame,
        "timer",
        g.limbo_horde_victory_timer,
        "ready",
        g.limbo_horde_ready_for_victory,
        "showing",
        g.showing_victory,
    )
