import pygame

pygame.init()
pygame.font.init()
from src.core.entities.tower import Tower, TowerManager  # noqa: E402
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

    def take_damage(self, damage):
        self.health -= damage


def test_tower_fires_at_closest():
    t = Tower(320, 530, projectile_speed=100.0, inaccuracy=0.0)
    e1 = DummyEnemy(400, 530)
    e2 = DummyEnemy(1000, 530)
    proj = t.fire_at_closest([e1, e2])
    assert proj is not None
    # Should aim roughly rightwards (toward e1)
    vx = getattr(proj, "vel_x", 0)
    vy = getattr(proj, "vel_y", 0)
    assert vx > 0
    assert abs(vy) < 1e-6 or abs(vy) < vx


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
    assert hasattr(proj, "vel_x") and hasattr(proj, "vel_y")
    assert getattr(proj, "appearance", None) == "storm_statue"


def test_ice_projectile_has_slow():
    t = Tower(320, 530, tower_type="ice", projectile_speed=100.0, inaccuracy=0.0)
    e1 = DummyEnemy(400, 530)
    proj = t.fire_at_closest([e1])
    # Should be a Projectile object with slow metadata
    assert proj is not None
    assert getattr(proj, "effect", None) == "slow"
    assert hasattr(proj, "slow_duration") and hasattr(proj, "slow_factor")


def test_fire_projectile_appearance():
    t = Tower(320, 530, tower_type="fire", projectile_speed=100.0, inaccuracy=0.0)
    e1 = DummyEnemy(400, 530)
    proj = t.fire_at_closest([e1])
    assert proj is not None
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
    # Use simple list for projectiles to make collision branch deterministic
    game.projectiles = []
    game.projectiles.append(proj)

    # Run collision handling directly
    game.handle_collisions()

    # Each enemy should have been hit: primary takes 5 damage, secondaries take 10 damage
    assert e1.health == e1.max_health - 5
    assert e2.health == e2.max_health - 10
    assert e3.health == e3.max_health - 10


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

    # Hit second enemy
    proj.x, proj.y = 600, 530
    game.handle_collisions()

    # has_hit_first_enemy should still be True
    assert getattr(proj, "has_hit_first_enemy", False)
