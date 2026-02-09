#!/usr/bin/env python3
import sys

sys.path.insert(0, "src")

from src.entities.enemy import Enemy

# Create an enemy instance
enemy = Enemy(100, 100, "basic", 20, 100)

print(f"Enemy class: {Enemy}")
print(f"Enemy instance: {enemy}")
print(f"Has take_damage method: {hasattr(enemy, 'take_damage')}")
print(f"take_damage method: {getattr(Enemy, 'take_damage', 'NOT FOUND')}")

# Try to call take_damage
try:
    enemy.take_damage(5)
    print("take_damage call successful")
except AttributeError as e:
    print(f"AttributeError: {e}")
except Exception as e:
    print(f"Other error: {e}")
