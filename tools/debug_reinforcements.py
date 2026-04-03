import pygame

from src.game import Game

pygame.init()
print("creating game")
g = Game(debug=True)
print("selecting stage")
g.select_stage("purgatory")
em = g.enemy_manager
boss = em.spawn_boss("mid")
print(
    "spawned boss:",
    boss,
    getattr(boss, "enemy_type", None),
    getattr(boss, "health", None),
)
print("boss in g.bosses?", boss in g.bosses)
# set boss HP to 0 and call update
boss.health = 0
print("after setting boss.health=0 -> calling update()")
g.update()
print("after update()")
print("center_messages:", g.center_messages)
print("g.bosses sprites count:", len(g.bosses.sprites()))
for b in g.bosses.sprites():
    print(" - boss:", b, getattr(b, "enemy_type", None), getattr(b, "health", None))

# Now manually post the USEREVENT+1 and handle events
pygame.event.post(pygame.event.Event(pygame.USEREVENT + 1))
g.handle_events()
print("after handling USEREVENT+1 -> enemies count:", len(list(g.enemies)))
non_bosses = [
    en
    for en in g.enemies
    if getattr(en, "enemy_type", "").startswith(
        ("weak", "normal", "strong", "angel", "giant")
    )
]
print("non-bosses spawned:", len(non_bosses))
print("done")
