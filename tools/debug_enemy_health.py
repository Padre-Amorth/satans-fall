import os
import sys

# ensure project root is on path
sys.path.append(os.getcwd())
from src.entities.enemy import Enemy

# inspect attribute behavior

e = Enemy(0, 0, enemy_type="normal", health=100)
print("initial dict", e.__dict__)
print("initial health", e.health)

# subtract
print("subtracting 20")
e.health -= 20
print("after subtract dict", e.__dict__)
print("after subtract health", e.health)

# assign
print("assign health 50")
e.health = 50
print("after assign dict", e.__dict__)
print("after assign health", e.health)
