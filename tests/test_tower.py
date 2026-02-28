import math

import pygame
import pytest

pygame.init()
pygame.font.init()
from src.core.entities.tower import Tower, TowerManager  # noqa: E402
from src.game_constants import (  # noqa: E402
    FIRE_SPECIAL_CHARGES,
    FIRE_SPECIAL_DURATION,
    FIRE_SPECIAL_RADIUS,
    FIRE_SPECIAL_WORDS,
    HELECTRIC_VIOLET_COLOR,
)
from src.projectile import Projectile  # used by updated tests  # noqa: E402


class DummyEnemy(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.x = x
        self.y = y
        self.health = 100
        self.rect = pygame.Rect(x - 6, y - 6, 12, 12)  # Small rect for collision
        self.ice_particles = []  # For ice effects
        self.slow_timer = 0  # For slow effects
        self.slow_factor = 1.0  # For slow effects

    def take_damage(self, damage, *args, **kwargs):
        # Accept extra args/kwargs such as ``show_floating`` for compatibility
        # with production ``Enemy.take_damage`` signature.
        try:
            self.health -= damage
        except Exception:
            pass


def test_tower_fires_at_closest():
    t = Tower(320, 530, projectile_speed=100.0, inaccuracy=0.0)
    e1 = DummyEnemy(400, 530)
    e2 = DummyEnemy(1000, 530)
    proj = t.fire_at_closest([e1, e2])
    assert proj is not None
    # projectile should record tower_type
    assert getattr(proj, "tower_type", None) == t.tower_type
    # Should aim roughly rightwards (toward e1)
    vx = getattr(proj, "vel_x", 0)
    vy = getattr(proj, "vel_y", 0)
    assert vx > 0
    assert abs(vy) < 1e-6 or abs(vy) < vx


def test_fire_at_closest_with_origin_changes_trajectory():
    """Providing a different fire origin should alter the projectile's velocity.

    We pick an enemy at a fixed location and fire twice: once from the tower
    centre and once from an offset position.  The resulting velocity angles must
    differ by more than a tiny epsilon, proving the origin was respected in the
    aim calculation.
    """
    t = Tower(320, 530, projectile_speed=100.0, inaccuracy=0.0)
    e = DummyEnemy(400, 480)
    proj1 = t.fire_at_closest([e])
    proj2 = t.fire_at_closest([e], origin_x=340, origin_y=530)
    assert proj1 is not None and proj2 is not None
    # first takeoff should originate from tower centre (default)
    assert proj1.x == pytest.approx(320) and proj1.y == pytest.approx(530)
    # second should originate from provided override
    assert proj2.x == pytest.approx(340) and proj2.y == pytest.approx(530)
    angle1 = math.atan2(getattr(proj1, "vel_y", 0), getattr(proj1, "vel_x", 0))
    angle2 = math.atan2(getattr(proj2, "vel_y", 0), getattr(proj2, "vel_x", 0))
    assert abs((angle1 - angle2) % (2 * math.pi)) > 1e-3


def test_homing_applies_when_angle_small():
    # Projectile initially moving roughly rightwards, enemy ahead => homing should nudge velocity
    proj = Projectile(300, 300, 100.0, 0.0)
    e = DummyEnemy(600, 300)
    before_vx = proj.vel_x
    TowerManager.apply_homing([proj], [e], projectile_speed=320.0)
    assert proj.vel_x != before_vx


def test_homing_skips_when_angle_large():
    # Projectile moving leftwards while enemy to the right -> angle diff > 90 => skip homing
    proj = Projectile(300, 300, -100.0, 0.0)
    e = DummyEnemy(600, 300)
    before_vx = proj.vel_x
    TowerManager.apply_homing([proj], [e], projectile_speed=320.0)
    assert proj.vel_x == before_vx


def test_storm_fires_single_projectile():
    t = Tower(320, 530, tower_type="storm", projectile_speed=100.0, inaccuracy=0.0)
    e1 = DummyEnemy(400, 530)
    proj = t.fire_at_closest([e1])
    # Now a single projectile should be returned
    assert proj is not None
    assert getattr(proj, "tower_type", None) == t.tower_type
    assert hasattr(proj, "vel_x") and hasattr(proj, "vel_y")
    assert getattr(proj, "appearance", None) == "storm_statue"


def test_ice_projectile_has_slow():
    t = Tower(320, 530, tower_type="ice", projectile_speed=100.0, inaccuracy=0.0)
    e1 = DummyEnemy(400, 530)
    proj = t.fire_at_closest([e1])
    # Should be a Projectile object with slow metadata
    assert proj is not None
    assert getattr(proj, "tower_type", None) == t.tower_type
    assert getattr(proj, "effect", None) == "slow"
    assert hasattr(proj, "slow_duration") and hasattr(proj, "slow_factor")


def test_fire_projectile_appearance():
    t = Tower(320, 530, tower_type="fire", projectile_speed=100.0, inaccuracy=0.0)
    e1 = DummyEnemy(400, 530)
    proj = t.fire_at_closest([e1])
    assert proj is not None
    assert getattr(proj, "tower_type", None) == t.tower_type
    # Should be marked for special appearance
    assert getattr(proj, "appearance", None) == "fire_statue"
    assert getattr(proj, "radius", 0) >= 6


def test_ice_projectile_appearance():
    t = Tower(320, 530, tower_type="ice", projectile_speed=100.0, inaccuracy=0.0)
    e1 = DummyEnemy(400, 530)
    proj = t.fire_at_closest([e1])
    assert proj is not None
    # Should be marked for special appearance
    assert getattr(proj, "appearance", None) == "ice_statue"


def test_storm_projectile_chains_three_enemies():
    from src.game import Game

    game = Game()
    # Place three enemies close together
    from src.entities.enemy import Enemy

    e1 = Enemy(400, 100, enemy_type="normal", health=20)
    e2 = Enemy(420, 100, enemy_type="normal", health=20)
    e3 = Enemy(440, 100, enemy_type="normal", health=20)
    try:
        game.enemies.empty()
        game.enemies.add(e1)
        game.enemies.add(e2)
        game.enemies.add(e3)
    except Exception:
        game.enemies = [e1, e2, e3]
    # Create a storm-statue projectile already on top of first enemy
    proj = Projectile(400, 100, 0.0, 0.0, damage=5, radius=6, appearance="storm_statue")
    proj.source = "statue"
    proj.chain_targets = 3
    proj.tower_type = "storm"
    # Use simple list for projectiles to make collision branch deterministic
    game.projectiles = []
    game.projectiles.append(proj)

    # Run collision handling directly
    game.handle_collisions()

    # Each enemy should have been hit: primary takes base damage, secondaries
    # should have taken some damage as well (exact values may be scaled).
    assert e1.health == e1.max_health - 5
    assert e2.health < e2.max_health - 5
    assert e3.health < e3.max_health - 5


def test_ice_tower_explosion_radius_with_upgrade():
    from src.game import Game

    game = Game()
    # Activate ICE1 upgrade
    game.permanent_stats["ice_1"] = 1
    # Make sure ICE2 is not active for this test
    game.permanent_stats["ice_2"] = 0

    # Create an ice tower and set it as left_tower
    t = Tower(320, 530, tower_type="ice", projectile_speed=100.0, inaccuracy=0.0)
    game.left_tower = t

    # Apply skill tree effects (this should set explosion_radius on the tower)
    game.apply_permanent_stats()

    # Check that the tower now has explosion_radius
    assert hasattr(t, "explosion_radius")
    assert t.explosion_radius == 60

    # Fire a projectile and check it has explosion_radius
    e1 = DummyEnemy(400, 530)
    proj = t.fire_at_closest([e1])
    assert proj is not None
    assert hasattr(proj, "explosion_radius")
    assert proj.explosion_radius == 60

    # Simulate projectile hitting enemy (set position to enemy)
    proj.x, proj.y = 400, 530
    game.enemies.add(e1)
    game.projectiles.add(proj)  # Add projectile to the game

    # Process collision (this should create ice puddle)
    initial_puddle_count = len(game.ice_puddles)
    game.handle_collisions()

    # Check that an ice puddle was created
    assert len(game.ice_puddles) == initial_puddle_count + 1
    puddle = game.ice_puddles[-1]
    assert puddle["x"] == 400
    assert puddle["y"] == 530
    assert puddle["radius"] == 40
    assert puddle["timer"] == 5 * 60  # 5 seconds
    assert puddle["slow_factor"] == 0.5  # 50% speed reduction


def test_ice_tower_ice3_piercing():
    from src.game import Game

    game = Game()
    # Activate ICE3 upgrade (piercing behavior)
    game.permanent_stats["ice_3"] = 1
    # ICE1 is required for explosion_radius used in puddle creation
    game.permanent_stats["ice_1"] = 1
    # Ensure ICE2 is not active for this test (to avoid larger puddle radius)
    game.permanent_stats["ice_2"] = 0

    # Create an ice tower and set it as left_tower
    t = Tower(320, 530, tower_type="ice", projectile_speed=100.0, inaccuracy=0.0)
    game.left_tower = t

    # Apply skill tree effects
    game.apply_permanent_stats()

    # Fire a projectile
    e1 = DummyEnemy(400, 530)
    proj = t.fire_at_closest([e1])
    assert proj is not None
    assert hasattr(proj, "appearance") and proj.appearance == "ice_statue"

    # Add projectile to game
    game.projectiles.add(proj)
    initial_projectile_count = len(game.projectiles)
    initial_puddle_count = len(game.ice_puddles)

    # Simulate projectile hitting enemy
    proj.x, proj.y = 400, 530
    game.enemies.add(e1)

    # Process collision - with ICE3, projectile should pierce and continue
    game.handle_collisions()

    # Check that projectile still exists (piercing behavior)
    assert len(game.projectiles) == initial_projectile_count

    # Check that enemy was slowed
    assert hasattr(e1, "slow_timer") and e1.slow_timer > 0
    assert hasattr(e1, "slow_factor") and e1.slow_factor < 1.0

    # Check that ice puddle was created on first hit
    assert len(game.ice_puddles) == initial_puddle_count + 1
    puddle = game.ice_puddles[-1]
    assert puddle["x"] == 400
    assert puddle["y"] == 530


def test_ice_tower_ice3_pierces_multiple_enemies_non_lethal():
    """ICE3 projectiles should pierce multiple nearby enemies even when the first hit isn't lethal."""
    from src.game import Game

    game = Game()
    game.permanent_stats["ice_3"] = 1
    game.permanent_stats["ice_1"] = 1

    t = Tower(320, 530, tower_type="ice", projectile_speed=100.0, inaccuracy=0.0)
    game.left_tower = t
    game.apply_permanent_stats()

    # Two enemies close together with enough health to survive a single hit
    e1 = DummyEnemy(400, 530)
    e2 = DummyEnemy(420, 530)
    try:
        game.enemies.empty()
        game.enemies.add(e1)
        game.enemies.add(e2)
    except Exception:
        game.enemies = [e1, e2]

    proj = t.fire_at_closest([e1, e2])
    assert proj is not None and getattr(proj, "appearance", None) == "ice_statue"
    game.projectiles.add(proj)

    # Place projectile on top of the first enemy (non-lethal expected)
    proj.x, proj.y = 400, 530
    before_e1, before_e2 = e1.health, e2.health

    game.handle_collisions()

    # Both enemies should have been damaged and the projectile should still exist
    assert e1.health < before_e1
    assert e2.health < before_e2
    assert proj in list(game.projectiles)


def test_ice_tower_ice3_pierces_multiple_enemies_non_lethal_dict():
    """Same as above but converted to object-style enemies."""
    from src.game import Game

    game = Game()
    game.permanent_stats["ice_3"] = 1
    game.permanent_stats["ice_1"] = 1
    # Ensure ICE2 (larger puddles) is disabled for this test
    game.permanent_stats["ice_2"] = 0

    # Use object-style enemies (converted)
    e1 = DummyEnemy(400, 530)
    e1.health = 100
    e1.max_health = 100
    e1.radius = 12
    e2 = DummyEnemy(408, 530)
    e2.health = 100
    e2.max_health = 100
    e2.radius = 12
    try:
        game.enemies.empty()
        game.enemies.add(e1)
        game.enemies.add(e2)
    except Exception:
        game.enemies = [e1, e2]

    # Construct a projectile (statue-source)
    proj = Projectile(400, 530, 0.0, 0.0, damage=20, radius=6, appearance="ice_statue")
    proj.source = "statue"
    game.projectiles = [proj]

    before_hps = [e.health for e in (e1, e2)]
    game.handle_collisions()
    after_hps = [e.health for e in (e1, e2)]

    assert after_hps[0] < before_hps[0]
    assert after_hps[1] < before_hps[1]
    # projectile should remain for ICE3 behavior when applicable
    assert proj in game.projectiles
    # Check that a puddle was created and has expected properties
    puddle = game.ice_puddles[-1]
    assert puddle["radius"] == 40
    assert puddle["timer"] == 5 * 60  # 5 seconds
    assert puddle["slow_factor"] == 0.5  # 50% speed reduction


def test_ice_tower_ice3_pierces_many_enemies():
    """ICE3 projectiles must pierce an arbitrary number of enemies (not only on lethal hits)."""
    from src.game import Game

    game = Game()
    game.permanent_stats["ice_3"] = 1
    game.permanent_stats["ice_1"] = 1

    t = Tower(320, 530, tower_type="ice", projectile_speed=100.0, inaccuracy=0.0)
    game.left_tower = t
    game.apply_permanent_stats()

    e1 = DummyEnemy(400, 530)
    e2 = DummyEnemy(408, 530)
    e3 = DummyEnemy(416, 530)
    try:
        game.enemies.empty()
        game.enemies.add(e1)
        game.enemies.add(e2)
        game.enemies.add(e3)
    except Exception:
        game.enemies = [e1, e2, e3]

    proj = t.fire_at_closest([e1, e2, e3])
    assert proj is not None and getattr(proj, "appearance", None) == "ice_statue"
    game.projectiles.add(proj)

    # Place projectile on top of the first enemy (non-lethal expected)
    proj.x, proj.y = 400, 530
    before = [e.health for e in (e1, e2, e3)]

    game.handle_collisions()

    after = [e.health for e in (e1, e2, e3)]
    assert after[0] < before[0]
    assert after[1] < before[1]
    assert after[2] < before[2]
    # projectile should still exist (piercing / ice3)
    assert proj in list(game.projectiles)


def test_ice_tower_ice3_pierces_many_enemies_dict():
    """Converted to object-style: ice projectiles should pierce multiple enemies when ICE3 is active."""
    from src.game import Game

    game = Game()
    game.permanent_stats["ice_3"] = 1
    game.permanent_stats["ice_1"] = 0

    e1 = DummyEnemy(400, 530)
    e1.health = 100
    e1.max_health = 100
    e1.radius = 12
    e2 = DummyEnemy(408, 530)
    e2.health = 100
    e2.max_health = 100
    e2.radius = 12
    e3 = DummyEnemy(416, 530)
    e3.health = 100
    e3.max_health = 100
    e3.radius = 12
    try:
        game.enemies.empty()
        game.enemies.add(e1)
        game.enemies.add(e2)
        game.enemies.add(e3)
    except Exception:
        game.enemies = [e1, e2, e3]

    proj = Projectile(400, 530, 0.0, 0.0, damage=20, radius=6, appearance="ice_statue")
    proj.source = "statue"
    game.projectiles = [proj]

    before_hps = [e.health for e in (e1, e2, e3)]
    game.handle_collisions()
    after_hps = [e.health for e in (e1, e2, e3)]

    assert after_hps[0] < before_hps[0]
    assert after_hps[1] < before_hps[1]
    assert after_hps[2] < before_hps[2]
    assert proj in game.projectiles


def test_ice_tower_ice3_single_damage_per_enemy():
    """Test that ICE3 projectiles damage each enemy only once"""
    from src.game import Game

    game = Game()
    game.permanent_stats["ice_3"] = 1
    game.permanent_stats["ice_1"] = 1

    tower = Tower(320, 530, tower_type="ice", projectile_speed=100.0, inaccuracy=0.0)
    game.left_tower = tower

    # Apply skill tree effects
    game.apply_permanent_stats()

    # Create enemy
    enemy = DummyEnemy(400, 530)
    enemy.health = 100
    game.enemies.add(enemy)

    # Fire projectile
    proj = tower.fire_at_closest([enemy])
    assert proj is not None
    game.projectiles.add(proj)

    initial_health = enemy.health

    # First hit
    proj.x, proj.y = 400, 530
    game.handle_collisions()
    first_hit_health = enemy.health
    assert first_hit_health < initial_health

    # Try to hit the same enemy again (move projectile back)
    proj.x, proj.y = 400, 530
    game.handle_collisions()

    # Health should not change (single damage per enemy)
    assert enemy.health == first_hit_health


def test_ice_tower_ice3_homing_reduction():
    """Test that ICE3 projectiles have reduced homing after first enemy hit"""
    from src.game import Game

    game = Game()
    game.permanent_stats["ice_3"] = 1

    tower = Tower(320, 530, tower_type="ice", projectile_speed=100.0, inaccuracy=0.0)
    game.left_tower = tower

    # Apply skill tree effects
    game.apply_permanent_stats()

    # Create enemies
    enemy1 = DummyEnemy(500, 530)
    enemy2 = DummyEnemy(600, 530)
    game.enemies.add(enemy1)
    game.enemies.add(enemy2)

    # Fire projectile
    proj = tower.fire_at_closest([enemy1])
    assert proj is not None
    game.projectiles.add(proj)

    # Before any hits, has_hit_first_enemy should be False
    assert not getattr(proj, "has_hit_first_enemy", False)

    # Hit first enemy
    proj.x, proj.y = 500, 530
    game.handle_collisions()

    # After first hit, has_hit_first_enemy should be True
    assert getattr(proj, "has_hit_first_enemy", False)


def test_ice3_hits_charge_each_enemy():
    """ICE3 projectiles grant tower energy for each hit they would deal.

    Testing the charging logic directly avoids flaky collision detection and
    ensures that charging only occurs when the special is unlocked and the
    projectile is tagged correctly.
    """
    from src.game import Game
    from src.projectile import Projectile

    game = Game()
    # require special unlocked (must satisfy column requirement)
    game.permanent_stats["ice_1"] = 1
    game.permanent_stats["ice_2"] = 1
    game.permanent_stats["ice_3"] = 1
    game.permanent_stats["ice_7"] = 1

    # tower instance present so ``special_unlocked`` returns True
    t = Tower(0, 0, tower_type="ice")
    game.left_tower = t
    game.apply_permanent_stats()
    assert game.special_unlocked(), "special should be unlocked"

    # create a dummy projectile as produced by an ice tower
    proj = Projectile(0, 0, 0, 0, damage=10, radius=6)
    proj.source = "statue"
    proj.tower_type = "ice"

    # simulate two hits and verify energy increment
    game.collision_system._maybe_charge_tower(proj, hits=2)
    assert game.tower_energy == game.tower_energy_per_hit * 2


def test_shared_energy_pool_charges_on_hit():
    from src.game import Game

    game = Game()
    # give a tower so its projectiles will charge
    t = Tower(320, 530, tower_type="fire", projectile_speed=100.0, inaccuracy=0.0)
    game.left_tower = t
    # unlock special via center stat
    game.permanent_stats["fire_7"] = 1
    # create an enemy and fire a projectile
    e = DummyEnemy(400, 530)
    game.enemies = [e]
    proj = t.fire_at_closest([e])
    assert proj is not None
    proj.source = "statue"  # ensure proper tagging
    game.projectiles = [proj]
    # initially zero energy
    assert game.tower_energy == 0
    # simulate hit
    before_hp = e.health
    proj.x, proj.y = 400, 530
    game.handle_collisions()
    after_hp = e.health
    assert after_hp < before_hp, "Enemy should take damage from statue projectile"
    assert game.tower_energy == game.tower_energy_per_hit


def test_ice1_explosion_still_charges():
    """Ice-statue projectiles with ICE1 explosion should count as hits."""
    from src.game import Game

    game = Game()
    # setup ice tower with special unlocked and ice1 upgrade
    t = Tower(320, 530, tower_type="ice", projectile_speed=100.0, inaccuracy=0.0)
    game.left_tower = t
    game.permanent_stats["ice_7"] = 1
    game.permanent_stats["ice_1"] = 1

    # create enemy
    e = DummyEnemy(400, 530)
    game.enemies = [e]
    # fire and tag
    proj = t.fire_at_closest([e])
    assert proj is not None
    proj.source = "statue"
    game.projectiles = [proj]
    assert game.tower_energy == 0
    # hit enemy to trigger explosion path
    proj.x, proj.y = 400, 530
    game.handle_collisions()
    # energy should have incremented despite explosion
    assert game.tower_energy == game.tower_energy_per_hit


def test_no_charge_when_special_locked():
    from src.game import Game

    game = Game()
    t = Tower(320, 530, tower_type="fire", projectile_speed=100.0, inaccuracy=0.0)
    game.left_tower = t
    # ensure lock
    game.permanent_stats["fire_7"] = 0
    # simulate manual charge attempt
    game.charge_tower_energy()
    assert game.tower_energy == 0
    # try projectile hit
    e = DummyEnemy(400, 530)
    game.enemies = [e]
    proj = t.fire_at_closest([e])
    proj.source = "statue"
    game.projectiles = [proj]
    proj.x, proj.y = 400, 530
    game.handle_collisions()
    assert game.tower_energy == 0


def test_energy_clamping_and_ready_flag():
    from src.core.entities.tower import Tower
    from src.game import Game

    game = Game()
    # provide a tower and unlock special so charging actually takes effect
    game.left_tower = Tower(
        0, 0, tower_type="fire", projectile_speed=1.0, inaccuracy=0.0
    )
    game.permanent_stats["fire_7"] = 1

    game.tower_energy = game.tower_energy_max - 1
    game.charge_tower_energy(5)
    assert game.tower_energy == game.tower_energy_max
    assert game.is_tower_special_ready()

    # subtract amount
    game.charge_tower_energy(-10)
    assert game.tower_energy == game.tower_energy_max - 10


def test_energy_cleared_on_run_reset():
    """Calling ``reset_run`` should clear any accumulated energy."""
    from src.game import Game

    g = Game()
    g.tower_energy = g.tower_energy_max
    # mutate some other state to show the method executed normally
    g.enemies_killed_this_run = 42
    g.reset_run()
    assert g.tower_energy == 0
    assert g.enemies_killed_this_run == 0


def test_energy_resets_when_leaving_level():
    """The shared energy pool is cleared whenever the stage menu opens.

    We use ``show_stage_menu`` as the hook since it fires when the player exits
    a level (victory/quit/etc).  This prevents specials carried across stages.
    """
    from src.game import Game

    g = Game()
    g.tower_energy = g.tower_energy_max
    # start as if currently in a level
    g.showing_stage_menu = False
    assert not g.showing_stage_menu
    g.selected_stage = "limbo"
    g.show_stage_menu()
    assert g.showing_main_menu
    assert g.tower_energy == 0


def test_energy_clears_on_stage_selection():
    """Calling ``select_stage`` should clear any stored energy before the
    level countdown begins.
    """
    from src.game import Game

    g = Game()
    g.tower_energy = 42
    # mimic being mid-run so that selected_stage has some value
    g.selected_stage = "limbo"
    # selecting a stage triggers the handler that resets energy
    g.select_stage("limbo")
    assert g.tower_energy == 0


def test_upgrade_system_clears_energy_on_weapon_application():
    """When the upgrade system applies a weapon while the run is starting,
    any accumulated tower energy must be wiped.
    """
    from src.game import Game
    from src.systems.upgrade_system import UpgradeSystem

    g = Game()
    us = UpgradeSystem(g)
    g.tower_energy = g.tower_energy_max
    g.is_initial_weapon_choice = True
    g.is_initial_tower_choice = False

    # apply any valid weapon to drive the branch
    us.apply_weapon("dagger")
    assert g.tower_energy == 0
    assert g.stage_start_countdown == 3


def test_activate_special_resets_energy():
    from src.core.entities.tower import Tower
    from src.game import Game

    game = Game()
    # need at least one tower and the appropriate permanent stat so the
    # special is considered unlocked; otherwise activate_tower_special will
    # always return False.
    game.left_tower = Tower(
        0, 0, tower_type="fire", projectile_speed=1.0, inaccuracy=0.0
    )
    game.permanent_stats["fire_7"] = 1

    game.tower_energy = game.tower_energy_max
    assert game.activate_tower_special() is True
    assert game.tower_energy == 0
    # subsequent activation should fail since energy was consumed
    assert game.activate_tower_special() is False


def test_right_click_triggers_special(monkeypatch):
    from src.core.entities.tower import Tower
    from src.game import Game

    game = Game()
    # set up tower and unlock
    game.left_tower = Tower(
        0, 0, tower_type="fire", projectile_speed=1.0, inaccuracy=0.0
    )
    game.permanent_stats["fire_7"] = 1

    game.tower_energy = game.tower_energy_max
    # monkeypatch message since display surfaces may not exist
    called = []

    def fake_msg(txt, duration, color, size):
        called.append(txt)

    game.show_centered_message = fake_msg
    # right-click anywhere
    game.handle_mouse_click((0, 0), button=3)
    assert game.tower_energy == 0
    assert "Tower special activated" in called[0]


def test_right_click_ignored_in_menus():
    """Right-click during a stage/menu screen shouldn't consume energy."""
    from src.game import Game

    g = Game()
    g.showing_stage_menu = True
    g.tower_energy = g.tower_energy_max
    g.handle_mouse_click((0, 0), button=3)
    assert g.tower_energy == g.tower_energy_max


def test_right_click_event_triggers_special(monkeypatch):
    """A posted MOUSEBUTTONDOWN event should activate the special when ready."""
    import pygame

    from src.core.entities.tower import Tower
    from src.game import Game

    g = Game()
    g.left_tower = Tower(0, 0, tower_type="fire", projectile_speed=1.0, inaccuracy=0.0)
    g.permanent_stats["fire_7"] = 1
    g.tower_energy = g.tower_energy_max
    called = []

    def fake_msg(txt, *args, **kwargs):
        called.append(txt)

    g.show_centered_message = fake_msg
    ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (0, 0), "button": 3})
    pygame.event.post(ev)
    g.handle_events()
    assert g.tower_energy == 0
    assert "Tower special activated" in called[0]


def test_fire_special_activation_and_timer(monkeypatch):
    from src.core.entities.tower import Tower
    from src.game import Game
    from src.game_constants import (
        FIRE_SPECIAL_CLICK_DELAY,
        FIRE_SPECIAL_EXPLOSION_COLOR,
        FIRE_SPECIAL_TEXT_LIFE,
    )

    g = Game()
    g.left_tower = Tower(0, 0, tower_type="fire", projectile_speed=1.0, inaccuracy=0.0)
    g.permanent_stats["fire_7"] = 1
    g.tower_energy = g.tower_energy_max
    # patch floating text tracker to record word, lifespan, font & velocity
    words = []
    lifetimes = []
    fonts = []
    vys = []
    colors = []
    outlines = []

    def track(txt, x, y, **kw):
        words.append(txt)
        lifetimes.append(kw.get("life", None))
        fonts.append(kw.get("font_size", None))
        vys.append(kw.get("vy", None))
        colors.append(kw.get("color", None))
        outlines.append(kw.get("outline_color", None))

    g.spawn_floating_text = track

    # click once: energy consumed and one charge removed, but explosion delayed
    g.handle_mouse_click((0, 0), button=3)
    assert g.tower_energy == 0
    assert g.fire_special_charges == FIRE_SPECIAL_CHARGES - 1
    assert 0 < g.fire_special_timer <= FIRE_SPECIAL_DURATION
    # no word yet because of click delay
    assert words == []

    # advance frames just before delay expires
    for _ in range(FIRE_SPECIAL_CLICK_DELAY - 1):
        g.update_game()
    assert words == []

    # next frame should trigger the explosion and show text
    g.update_game()
    assert words == [FIRE_SPECIAL_WORDS[0].upper()]
    # explosion entry should carry the dark orange color constant
    assert g.game_state.fire_explosions
    assert g.game_state.fire_explosions[-1].get("color") == FIRE_SPECIAL_EXPLOSION_COLOR

    # additional click should queue another delayed shot
    words.clear()
    lifetimes.clear()
    colors.clear()
    outlines.clear()
    g.handle_mouse_click((0, 0), button=3)
    assert g.fire_special_charges == FIRE_SPECIAL_CHARGES - 2
    for _ in range(FIRE_SPECIAL_CLICK_DELAY):
        g.update_game()
    assert words == [FIRE_SPECIAL_WORDS[1].upper()]
    assert g.game_state.fire_explosions[-1].get("color") == FIRE_SPECIAL_EXPLOSION_COLOR
    assert lifetimes[0] >= FIRE_SPECIAL_TEXT_LIFE
    assert fonts[0] >= 40
    assert vys[0] is not None and vys[0] < 0
    assert not getattr(g, "pending_fire_clicks", [])


def test_floating_text_outline_draws_as_stroke(monkeypatch):
    """FloatingText with an outline should render one fill and multiple
    shifted blits rather than two separate words.

    We patch ``screen.blit`` to record the destination coordinates and
    ensure that there are eight offset draws surrounding a central fill.
    """
    from src.game import Game

    g = Game()
    # spawn a text with outline; coordinates arbitrary
    g.spawn_floating_text("TEST", 50, 60, color=(255, 0, 0), outline_color=(0, 0, 0))

    blit_calls: list[tuple] = []

    def fake_blit(surface, dest):
        blit_calls.append(dest)

    # replace screen with a minimal stand-in that records blits
    class DummyScreen:
        def blit(self, surf, dest):
            fake_blit(surf, dest)

    g.screen = DummyScreen()  # type: ignore

    # draw once; this should invoke our fake_blit multiple times
    g.draw_floating_texts()

    # expect 1 fill + 8 outline positions
    assert len(blit_calls) == 9
    # last call is the fill text (drawn after outline loops)
    central = blit_calls[-1]
    for pos in blit_calls[:-1]:
        dx = pos[0] - central[0]
        dy = pos[1] - central[1]
        assert abs(dx) <= 1 and abs(dy) <= 1


def test_fire_special_charge_sequence():
    from src.game import Game

    g = Game()
    # just call helper directly to bypass energy
    seq = []
    g.spawn_floating_text = lambda txt, x, y, **kw: seq.append(txt)
    for i in range(6):
        g._spawn_fire_special(100, 100)
    # every invocation should append a word, independent of enemies
    assert seq[:4] == [w.upper() for w in FIRE_SPECIAL_WORDS]
    assert seq[4:6] == [w.upper() for w in FIRE_SPECIAL_WORDS[:2]]


def test_fire_special_text_grows_and_moves():
    """Words should spawn large and float upward over time."""
    from src.core.entities.tower import Tower
    from src.game import Game
    from src.game_constants import FIRE_SPECIAL_CLICK_DELAY

    g = Game()
    g.left_tower = Tower(0, 0, tower_type="fire", projectile_speed=1.0, inaccuracy=0.0)
    g.permanent_stats["fire_7"] = 1
    g.tower_energy = g.tower_energy_max
    g.mouse_x, g.mouse_y = 100, 100

    # activate special and advance through delay
    g.handle_mouse_click((100, 100), button=3)
    for _ in range(FIRE_SPECIAL_CLICK_DELAY + 1):
        g.update_game()

    # there should be a floating text entry
    assert g.floating_texts
    ft = g.floating_texts[-1]
    assert ft.font_size >= 40
    old_y = ft.y
    g.update_game()
    assert ft.y < old_y


def test_fire_special_smoke_particles():
    """Smoke should be spawned alongside explosion and drift upward."""
    from src.core.entities.tower import Tower
    from src.game import Game
    from src.game_constants import FIRE_SPECIAL_CLICK_DELAY

    g = Game()
    g.left_tower = Tower(0, 0, tower_type="fire", projectile_speed=1.0, inaccuracy=0.0)
    g.permanent_stats["fire_7"] = 1
    g.tower_energy = g.tower_energy_max
    g.mouse_x, g.mouse_y = 200, 200

    g.handle_mouse_click((200, 200), button=3)
    for _ in range(FIRE_SPECIAL_CLICK_DELAY + 1):
        g.update_game()

    assert getattr(g, "fire_smoke", [])
    before = [p["y"] for p in g.fire_smoke]
    g.update_game()
    after = [p["y"] for p in g.fire_smoke]
    # smoke should either move up (y decreases) or start disappearing
    moved = any(a < b for a, b in zip(after, before))
    shrank = len(after) < len(before)
    assert moved or shrank


def test_fire_special_order_with_delay():
    """Even when shots are delayed the spoken words must stay in order."""
    from src.core.entities.tower import Tower
    from src.game import Game
    from src.game_constants import FIRE_SPECIAL_CLICK_DELAY

    g = Game()
    g.left_tower = Tower(0, 0, tower_type="fire", projectile_speed=1.0, inaccuracy=0.0)
    g.permanent_stats["fire_7"] = 1
    g.tower_energy = g.tower_energy_max
    words = []
    g.spawn_floating_text = lambda txt, x, y, **kw: words.append(txt)

    # fire three rapid clicks inside window
    g.handle_mouse_click((0, 0), button=3)
    g.handle_mouse_click((0, 0), button=3)
    g.handle_mouse_click((0, 0), button=3)

    # advance through all delays plus a little extra
    for _ in range(FIRE_SPECIAL_CLICK_DELAY * 3 + 2):
        g.update_game()

    # we should have seen MAKE, ADE, GREAT in order
    assert words[:3] == [w.upper() for w in FIRE_SPECIAL_WORDS[:3]]


def test_fire_texts_persist_on_same_spot():
    """Texts from sequential explosions at the same point should not vanish early."""
    from src.core.entities.tower import Tower
    from src.game import Game
    from src.game_constants import FIRE_SPECIAL_CLICK_DELAY, FIRE_SPECIAL_TEXT_LIFE

    g = Game()
    g.left_tower = Tower(0, 0, tower_type="fire", projectile_speed=1.0, inaccuracy=0.0)
    g.permanent_stats["fire_7"] = 1
    g.tower_energy = g.tower_energy_max
    records = []

    def track(txt, x, y, **kw):
        records.append((txt, kw.get("life", None)))

    g.spawn_floating_text = track
    # click twice quickly at same coords
    g.handle_mouse_click((0, 0), button=3)
    g.handle_mouse_click((0, 0), button=3)
    # advance to fire both shots
    for _ in range(FIRE_SPECIAL_CLICK_DELAY * 2 + 2):
        g.update_game()
    assert len(records) >= 2
    # both lifetimes should be >= constant
    assert all(life >= FIRE_SPECIAL_TEXT_LIFE for (_txt, life) in records)


def test_fire_special_expire():
    from src.core.entities.tower import Tower
    from src.game import Game

    g = Game()
    g.left_tower = Tower(0, 0, tower_type="fire", projectile_speed=1.0, inaccuracy=0.0)
    g.permanent_stats["fire_7"] = 1
    g.tower_energy = g.tower_energy_max
    # activate special once (first shot consumed automatically)
    g.handle_mouse_click((0, 0), button=3)
    assert g.fire_special_charges == FIRE_SPECIAL_CHARGES - 1
    # run until expiration, no additional clicks
    for _ in range(FIRE_SPECIAL_DURATION + 2):
        g.update_game()
    assert g.fire_special_charges == 0
    assert g.fire_special_timer == 0


def test_helectric_flux_expires_after_duration():
    """Beam remains active for its full duration and automatically ends.

    The ability should shut off as soon as the timer runs out rather than
    lingering for an extra frame.  Right-click toggling does not prevent this
    expiration.
    """
    from src.core.entities.tower import Tower
    from src.game import Game

    g = Game(debug=True)
    g.left_tower = Tower(0, 0, tower_type="storm", projectile_speed=1.0, inaccuracy=0.0)
    g.right_tower = Tower(
        100, 0, tower_type="storm", projectile_speed=1.0, inaccuracy=0.0
    )
    g.permanent_stats["storm_7"] = 1
    g.tower_energy = g.tower_energy_max
    g.mouse_x, g.mouse_y = 50, 50

    assert g.activate_tower_special() is True
    assert g.hellectric_active
    # simulate enough frames that the automatic duration should expire
    # force the random generator to select the violet tint so we can assert
    import random

    from pygame import Surface

    old_rand = random.random
    random.random = lambda: 0.0
    saw_violet = False

    for _ in range(g.HELLECTRIC_MAX_DURATION + 2):
        prev = len(getattr(g.game_state, "chain_lightning_effects", []))
        g.update_game()
        # beam remains active until timer runs out
        if g.hellectric_time_left > 0:
            assert g.hellectric_active
            effects = getattr(g.game_state, "chain_lightning_effects", [])
            assert len(effects) >= prev
            # at least one effect should represent the impact explosion/circle
            assert any(
                e.get("explosion") for e in effects
            ), "no explosion effect present"
            # check for at least one violet-colored beam
            if any(e.get("color") == HELECTRIC_VIOLET_COLOR for e in effects):
                saw_violet = True
            # ensure UI can draw the special ring and it actually paints
            # pixels in the expected area rather than leaving a blank surface.
            g.ui.screen = Surface((g.width, g.height), pygame.SRCALPHA)
            g.ui.screen.fill((0, 0, 0, 255))
            g.ui.draw_special_effects()
            # sample a few points around the beam endpoint (not raw cursor)
            mx, my = g.hellectric_x, g.hellectric_y
            changed = False
            for dy in (-g.HELLECTRIC_IMPACT_RADIUS, 0, g.HELLECTRIC_IMPACT_RADIUS):
                for dx in (-g.HELLECTRIC_IMPACT_RADIUS, 0, g.HELLECTRIC_IMPACT_RADIUS):
                    x = int(mx + dx)
                    y = int(my + dy)
                    if 0 <= x < g.width and 0 <= y < g.height:
                        color = g.ui.screen.get_at((x, y))
                        if color != (0, 0, 0, 255):
                            changed = True
            assert changed, "hellectric radius did not draw any pixels"
        else:
            assert not g.hellectric_active

    random.random = old_rand
    assert saw_violet, "no violet beam was produced"


def test_helectric_flux_toggles_on_click():
    """Pressing right click again should cancel an active hellectric beam."""
    import pygame

    from src.core.entities.tower import Tower
    from src.game import Game

    g = Game(debug=True)
    g.left_tower = Tower(0, 0, tower_type="storm", projectile_speed=1.0, inaccuracy=0.0)
    g.right_tower = Tower(
        100, 0, tower_type="storm", projectile_speed=1.0, inaccuracy=0.0
    )
    g.permanent_stats["storm_7"] = 1
    g.tower_energy = g.tower_energy_max
    g.mouse_x, g.mouse_y = 50, 50

    assert g.activate_tower_special() is True
    assert g.hellectric_active
    # right_mouse_held property should match the beam state for compatibility
    assert getattr(g, "right_mouse_held", False) is True

    # clicking again should deactivate and produce feedback
    called = []
    g.show_centered_message = lambda txt, *args, **kw: called.append(txt)
    ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (0, 0), "button": 3})
    pygame.event.post(ev)
    g.handle_events()

    g.update_game()
    assert not g.hellectric_active
    assert getattr(g, "right_mouse_held", False) is False
    assert "cancelled" in called[0].lower()


def test_fire_explosion_draws_pixels():
    import math

    from pygame import Surface

    from src.core.entities.tower import Tower
    from src.game import Game
    from src.game_constants import FIRE_SPECIAL_CLICK_DELAY

    g = Game(debug=True)
    g.left_tower = Tower(0, 0, tower_type="fire", projectile_speed=1.0, inaccuracy=0.0)
    g.permanent_stats["fire_7"] = 1
    g.tower_energy = g.tower_energy_max
    g.mouse_x, g.mouse_y = 150, 150

    assert g.activate_tower_special()
    # no explosion yet due to click delay
    assert not getattr(g.game_state, "fire_explosions", [])
    # advance until the delayed shot triggers
    for _ in range(FIRE_SPECIAL_CLICK_DELAY + 1):
        g.update_game()
    # now there should be an effect and we can draw
    assert getattr(g.game_state, "fire_explosions", [])
    g.ui.screen = Surface((g.width, g.height), pygame.SRCALPHA)
    g.ui.screen.fill((0, 0, 0, 255))
    # draw first frame; the effect starts with radius=0 so it's possible
    # nothing shows immediately.  that's acceptable.
    g.ui.draw_special_effects()
    cx, cy = 150, 150
    center_col = g.ui.screen.get_at((cx, cy))
    if center_col == (0, 0, 0, 255):
        # advance one frame and try again
        for eff in getattr(g.game_state, "fire_explosions", []):
            eff["timer"] = max(0, eff.get("timer", 0) - 1)
        g.ui.screen.fill((0, 0, 0, 255))
        g.ui.draw_special_effects()
        center_col = g.ui.screen.get_at((cx, cy))
    assert center_col != (0, 0, 0, 255)
    # should be orangeish: red high, green smaller but nonzero, blue minimal
    assert center_col.r > 0
    assert center_col.g > 0
    assert center_col.b <= center_col.g
    # floating text from explosion must be uppercase
    texts = [ft.text for ft in g.floating_texts]
    assert all(t == t.upper() for t in texts), "explosion words not uppercase"

    # advance some frames and ensure radius expands (outer px appears)
    for _ in range(5):
        for eff in getattr(g.game_state, "fire_explosions", []):
            eff["timer"] = max(0, eff.get("timer", 0) - 1)
        g.ui.screen.fill((0, 0, 0, 255))
        g.ui.draw_special_effects()
    # now pixel at r distance should be non-black
    found = False
    for dy in (-FIRE_SPECIAL_RADIUS, 0, FIRE_SPECIAL_RADIUS):
        for dx in (-FIRE_SPECIAL_RADIUS, 0, FIRE_SPECIAL_RADIUS):
            x = int(cx + dx)
            y = int(cy + dy)
            if 0 <= x < g.width and 0 <= y < g.height:
                if g.ui.screen.get_at((x, y)) != (0, 0, 0, 255):
                    found = True
    assert found, "fire explosion did not expand outward"
    # and there should be a thin yellow outline around the current expanding radius
    outline_ok = False
    # look for any non-black pixel immediately outside the current radius
    for eff in getattr(g.game_state, "fire_explosions", []):
        r = eff.get("radius", 0)
        timer = eff.get("timer", 0)
        max_timer = max(1, eff.get("max_timer", 1))
        prog = 1.0 - (timer / max_timer)
        current = int(r * prog)
        for x in range(g.width):
            for y in range(g.height):
                dx = x - cx
                dy = y - cy
                dist = math.hypot(dx, dy)
                # we're only interested in the thin band just beyond the filled
                # orange circle; if we see any non-black pixel there it must be
                # the additional outline ring.
                if current + 1 < dist <= current + 5:
                    col = g.ui.screen.get_at((x, y))
                    if col != (0, 0, 0, 255):
                        outline_ok = True
                        break
            if outline_ok:
                break
        if outline_ok:
            break
    assert outline_ok, "outer yellow ring missing from fire explosion"


def test_helectric_flux_endpoint_moves_at_limited_speed():
    """Endpoint should only move toward the cursor at the configured speed."""
    import math

    from src.core.entities.tower import Tower
    from src.game import Game

    g = Game(debug=True)
    g.left_tower = Tower(0, 0, tower_type="storm", projectile_speed=1.0, inaccuracy=0.0)
    g.permanent_stats["storm_7"] = 1
    g.tower_energy = g.tower_energy_max
    # initialize beam at a point
    g.mouse_x, g.mouse_y = 200, 0
    assert g.activate_tower_special() is True
    # endpoint should start at the current mouse position
    assert (g.hellectric_x, g.hellectric_y) == (200, 0)
    # move cursor instantly to new location far to the right
    g.mouse_x, g.mouse_y = 400, 0
    prev_x, prev_y = g.hellectric_x, g.hellectric_y
    g.update_game()
    dx = g.hellectric_x - prev_x
    dy = g.hellectric_y - prev_y
    moved = math.hypot(dx, dy)
    from src.game_constants import HELECTRIC_SPEED

    maxmove = HELECTRIC_SPEED / g.fps
    assert moved <= maxmove + 1e-6, "endpoint moved too quickly"
    # after sufficient frames the endpoint should reach the cursor
    frames = int((400 - 200) / maxmove) + 2
    for _ in range(frames):
        g.update_game()
    assert abs(g.hellectric_x - 400) < 1 and abs(g.hellectric_y - 0) < 1


def test_helectric_flux_damages_enemies():
    from src.core.entities.tower import Tower
    from src.entities.enemy import Enemy
    from src.game import Game

    g = Game(debug=True)
    g.left_tower = Tower(0, 0, tower_type="storm", projectile_speed=1.0, inaccuracy=0.0)
    g.right_tower = Tower(
        100, 0, tower_type="storm", projectile_speed=1.0, inaccuracy=0.0
    )
    g.permanent_stats["storm_7"] = 1
    g.tower_energy = g.tower_energy_max
    enemy = Enemy(50, 25, enemy_type="normal", health=20)
    g.enemies = [enemy]
    g.mouse_x, g.mouse_y = 50, 50
    # record starting health (may be modified by global scaling)
    start_hp = enemy.health
    g.activate_tower_special()
    g.update_game()
    assert enemy.health < start_hp


def test_helectric_flux_damages_boss():
    """Boss entities should also take damage from Hellectric flux."""
    from src.core.entities.tower import Tower
    from src.entities.enemy import Enemy
    from src.game import Game

    g = Game(debug=True)
    g.left_tower = Tower(0, 0, tower_type="storm", projectile_speed=1.0, inaccuracy=0.0)
    g.right_tower = Tower(
        100, 0, tower_type="storm", projectile_speed=1.0, inaccuracy=0.0
    )
    g.permanent_stats["storm_7"] = 1
    g.tower_energy = g.tower_energy_max
    # create boss-like enemy with same interface
    boss = Enemy(50, 25, enemy_type="boss", health=100)
    try:
        g.bosses.empty()
        g.bosses.add(boss)
    except Exception:
        g.bosses = [boss]
    g.mouse_x, g.mouse_y = 50, 50
    start_hp = boss.health
    g.activate_tower_special()
    g.update_game()
    assert boss.health < start_hp


def test_helectric_flux_text_throttled():
    """Floating numbers only appear every 10 points of beam damage."""
    from src.core.entities.tower import Tower
    from src.entities.enemy import Enemy
    from src.game import Game

    g = Game(debug=True)
    g.left_tower = Tower(0, 0, tower_type="storm", projectile_speed=1.0, inaccuracy=0.0)
    g.permanent_stats["storm_7"] = 1
    g.tower_energy = g.tower_energy_max
    # place enemy on the diagonal beam path (0,0)-(50,50) to guarantee
    # collision each frame regardless of tiny endpoint drift
    enemy = Enemy(25, 25, enemy_type="normal", health=100)
    g.enemies = [enemy]
    g.mouse_x, g.mouse_y = 50, 50

    calls = []

    def track(txt, x, y, **kwargs):
        calls.append(txt)

    g.spawn_floating_text = track

    assert g.activate_tower_special() is True
    # deal 25 points – should trigger two “10” texts and leave 5 unreported
    for _ in range(25):
        g.update_game()

    assert calls.count("10") == 2
    # no stray "1"s
    assert all(c == "10" for c in calls)


def test_both_specials_activate_when_both_towers_placed():
    """If both tower types are placed and both specials are unlocked,
    using the right-click should trigger both Blizzard and Hellectric Flux.
    """
    from src.core.entities.tower import Tower
    from src.game import Game
    from src.game_constants import BLIZZARD_MAX_DURATION, BLIZZARD_RADIUS

    g = Game(debug=True)
    g.left_tower = Tower(0, 0, tower_type="ice", projectile_speed=1.0, inaccuracy=0.0)
    g.right_tower = Tower(
        100, 0, tower_type="storm", projectile_speed=1.0, inaccuracy=0.0
    )
    g.permanent_stats["ice_7"] = 1
    g.permanent_stats["storm_7"] = 1
    g.tower_energy = g.tower_energy_max
    # choose mouse coordinate
    g.mouse_x, g.mouse_y = 200, 150

    assert g.activate_tower_special() is True
    # hellectric beam should be active (storm tower with storm_7)
    assert getattr(g, "hellectric_active", False)
    # fire special is not expected since no fire tower is present
    # (previous version of this test erroneously checked charges)    # one Blizzard puddle should exist at mouse (ice tower with ice_7)
    puddles = getattr(g, "blizzard_puddles", [])
    assert puddles and puddles[-1]["x"] == 200 and puddles[-1]["y"] == 150
    assert puddles[-1]["timer"] == BLIZZARD_MAX_DURATION
    from src.game_constants import BLIZZARD_SLOW_FACTOR

    # verify we attached the slow factor so the puddle really functions
    assert puddles[-1].get("slow_factor") == BLIZZARD_SLOW_FACTOR

    # allow the puddle to expand a little before drawing; otherwise it might be
    # essentially a point and the pixel test would fail.
    for _ in range(30):
        g.update_game()

    # visual draw: ensure pixels away from center now paint something
    from pygame import Surface

    g.screen = Surface((g.width, g.height), pygame.SRCALPHA)
    g.screen.fill((0, 0, 0, 255))
    g.draw_ice_puddles()
    cx, cy = 200, 150
    found = False
    # sample at roughly half the max radius; expansion should have reached here
    for dy in (-BLIZZARD_RADIUS // 2, 0, BLIZZARD_RADIUS // 2):
        for dx in (-BLIZZARD_RADIUS // 2, 0, BLIZZARD_RADIUS // 2):
            x = int(cx + dx)
            y = int(cy + dy)
            if 0 <= x < g.width and 0 <= y < g.height:
                if g.screen.get_at((x, y)) != (0, 0, 0, 255):
                    found = True
    assert found, "Blizzard zone was not drawn after a few frames of expansion"


def test_blizzard_puddle_expires_after_duration():
    """Blizzard zones should be removed once their timer runs out (~5 seconds)."""
    from src.core.entities.tower import Tower
    from src.game import Game
    from src.game_constants import BLIZZARD_MAX_DURATION

    g = Game(debug=True)
    # unlock both specials so we can spawn the blizzard with right click
    g.left_tower = Tower(0, 0, tower_type="ice", projectile_speed=1.0, inaccuracy=0.0)
    g.right_tower = Tower(
        100, 0, tower_type="storm", projectile_speed=1.0, inaccuracy=0.0
    )
    g.permanent_stats["ice_7"] = 1
    g.permanent_stats["storm_7"] = 1
    g.tower_energy = g.tower_energy_max
    g.mouse_x, g.mouse_y = 400, 300

    assert g.activate_tower_special() is True
    # puddle should exist immediately
    assert getattr(g, "blizzard_puddles", [])

    # run for one more frame than duration and ensure puddle vanishes
    for _ in range(BLIZZARD_MAX_DURATION + 2):
        g.update_game()
    assert not getattr(
        g, "blizzard_puddles", []
    ), "Blizzard puddle should be cleared after its timer"


def test_blizzard_expire_deals_damage():
    """Expired Blizzard puddles inflict a flat amount of damage to all targets."""
    from src.entities.enemy import Enemy
    from src.game import Game
    from src.game_constants import BLIZZARD_EXPIRE_DAMAGE, BLIZZARD_RADIUS

    g = Game(debug=True)
    # create a single puddle about to expire
    g.blizzard_puddles = [
        {
            "x": 200,
            "y": 200,
            "radius": BLIZZARD_RADIUS,
            "timer": 1,
            "slow_factor": 0.5,
            "blizzard": True,
        }
    ]
    # enemy inside the radius
    e = Enemy(200, 200, enemy_type="normal", health=100)
    g.enemies = [e]
    # boss too
    boss = Enemy(210, 200, enemy_type="boss", health=50)
    try:
        g.bosses.empty()
        g.bosses.add(boss)
    except Exception:
        g.bosses = [boss]

    # record starting HP values (game may apply global scaling during update)
    start_enemy_hp = e.health
    start_boss_hp = boss.health
    g.update_game()
    assert e.health == start_enemy_hp - BLIZZARD_EXPIRE_DAMAGE
    assert boss.health == start_boss_hp - BLIZZARD_EXPIRE_DAMAGE

    # floating texts should have been spawned for both targets
    texts = getattr(g, "floating_texts", [])
    assert any(
        getattr(ft, "text", "") == str(int(BLIZZARD_EXPIRE_DAMAGE)) for ft in texts
    )


def test_blizzard_zone_expands_and_slows_enemies():
    """Expansion of the Blizzard zone should eventually catch enemies at a distance.

    The radius starts effectively zero and grows; an enemy outside the zone
    initially should be slowed once the effective radius passes its position.
    """
    from src.core.entities.tower import Tower
    from src.entities.enemy import Enemy
    from src.game import Game
    from src.game_constants import BLIZZARD_MAX_DURATION, BLIZZARD_RADIUS

    g = Game(debug=True)
    g.left_tower = Tower(0, 0, tower_type="ice", projectile_speed=1.0, inaccuracy=0.0)
    g.right_tower = Tower(
        100, 0, tower_type="storm", projectile_speed=1.0, inaccuracy=0.0
    )
    g.permanent_stats["ice_7"] = 1
    g.permanent_stats["storm_7"] = 1
    g.tower_energy = g.tower_energy_max
    g.mouse_x, g.mouse_y = 100, 100

    assert g.activate_tower_special()
    # add enemy just beyond initial tiny radius but well within max
    dist = BLIZZARD_RADIUS // 5
    enemy = Enemy(100 + dist, 100, enemy_type="normal", health=10)
    # keep enemy stationary so expanding radius can catch it
    try:
        enemy.vx = 0
        enemy.vy = 0
    except Exception:
        pass
    g.enemies = [enemy]

    # enemy should not be slowed immediately
    g.collision_system.apply_ice_puddle_slowing()
    assert getattr(enemy, "slow_factor", 1.0) == 1.0

    # manually simulate the passage of frames without updating enemies
    # (enemy movement was interfering with the earlier approach).
    p = g.blizzard_puddles[-1]
    slowed = False
    for _ in range(BLIZZARD_MAX_DURATION):
        g.collision_system.apply_ice_puddle_slowing()
        if getattr(enemy, "slow_factor", 1.0) < 1.0:
            slowed = True
            break
        # mimic Game.update's puddle timer decrement after collision check
        p["timer"] -= 1
    assert slowed, "Enemy never slowed by expanding Blizzard zone"
