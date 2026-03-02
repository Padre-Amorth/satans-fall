import pygame

from src.entities.enemy import Enemy
from src.game import Game


def _make_orbital_game():
    pygame.init()
    g = Game()
    g.reset_game()
    # give player orbital weapon
    g.player_weapons = ["orbital"]
    g.weapon_levels = {"orbital": 1}
    g.orbital_count = 1
    g.create_orbitals()
    return g


def test_orbital_single_hit_per_enemy():
    g = _make_orbital_game()
    # place first orbital and an enemy exactly at its position
    orb = g.orbitals[0]
    orb["x"] = 100
    orb["y"] = 100
    e = Enemy(100, 100)
    try:
        g.enemies.empty()
        g.enemies.add(e)
    except Exception:
        g.enemies = [e]

    hp_before = e.health
    g.handle_collisions()
    assert e.health == hp_before - 15
    # second frame should not apply again
    g.handle_collisions()
    assert e.health == hp_before - 15

    # move orb away and back to allow new hit
    orb["x"] = 0
    orb["y"] = 0
    g.handle_collisions()
    orb["x"] = 100
    orb["y"] = 100
    g.handle_collisions()
    assert e.health == hp_before - 30


def test_multiple_orbitals_stack_damage():
    g = _make_orbital_game()
    # create two orbitals (simulate upgrade)
    g.orbital_count = 2
    g.create_orbitals()
    e = Enemy(200, 200)
    try:
        g.enemies.empty()
        g.enemies.add(e)
    except Exception:
        g.enemies = [e]

    # move both orbitals onto the enemy
    for orb in g.orbitals:
        orb["x"] = 200
        orb["y"] = 200

    hp_before = e.health
    g.handle_collisions()
    # two orbitals should yield 30 damage
    assert e.health == hp_before - 30

    # additional frames don't stack further
    g.handle_collisions()
    assert e.health == hp_before - 30


def test_orbital_damage_bonus_level3():
    """Test that orbitals gain +10% damage at level 3"""
    g = _make_orbital_game()
    # upgrade to level 3
    g.weapon_levels["orbital"] = 3
    orb = g.orbitals[0]
    orb["x"] = 100
    orb["y"] = 100
    e = Enemy(100, 100)
    try:
        g.enemies.empty()
        g.enemies.add(e)
    except Exception:
        g.enemies = [e]

    hp_before = e.health
    g.handle_collisions()
    # Level 3: 15 * 1.1 = 16.5 → 16 damage (int)
    assert e.health == hp_before - 16, f"Expected 16 damage at level 3, got {hp_before - e.health}"


def test_orbital_damage_bonus_level5():
    """Test that orbitals gain stacked +10% damage at level 5 (1.1 * 1.1 = 1.21x)"""
    g = _make_orbital_game()
    # upgrade to level 5
    g.weapon_levels["orbital"] = 5
    orb = g.orbitals[0]
    orb["x"] = 100
    orb["y"] = 100
    e = Enemy(100, 100)
    try:
        g.enemies.empty()
        g.enemies.add(e)
    except Exception:
        g.enemies = [e]

    hp_before = e.health
    g.handle_collisions()
    # Level 5: 15 * 1.1 = 16 (int), then 16 * 1.1 = 17 (int)
    assert e.health == hp_before - 17, f"Expected 17 damage at level 5, got {hp_before - e.health}"


def test_orbital_damage_bonus_with_multiple_orbitals():
    """Test that damage bonuses apply to all orbitals"""
    g = _make_orbital_game()
    # upgrade to level 5 with 3 orbitals
    g.weapon_levels["orbital"] = 5
    g.orbital_count = 3
    g.create_orbitals()
    e = Enemy(200, 200)
    try:
        g.enemies.empty()
        g.enemies.add(e)
    except Exception:
        g.enemies = [e]

    # move all 3 orbitals onto the enemy
    for orb in g.orbitals:
        orb["x"] = 200
        orb["y"] = 200

    hp_before = e.health
    g.handle_collisions()
    # 3 orbitals at level 5: 3 * 17 = 51 damage (17 = int(int(15*1.1)*1.1))
    assert e.health == hp_before - 51, f"Expected 51 damage (3x17), got {hp_before - e.health}"
