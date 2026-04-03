import pygame

from src.game import Game

pygame.init()
print("pygame initialized")
g = Game(debug=True)
print("game created")
g.selected_stage = "hell"
g.spawn_giant_enemy()
custodes = [e for e in g.enemies if getattr(e, "enemy_type", "") == "custode"]
print("custodes after spawn", len(custodes))
if custodes:
    c = custodes[0]
    print("health", c.health, "max", c.max_health)
    c.take_damage(c.max_health // 2 + 1)
    print("health after", c.health)
    custodes2 = [e for e in g.enemies if getattr(e, "enemy_type", "") == "custode"]
    print("custodes now", len(custodes2))
    print("explosions", g.skullboom_explosions)
