import pygame
import pytest

pygame.init()
pygame.font.init()
from src.core.entities.tower import Tower  # noqa: E402
from src.game import Game  # noqa: E402


class DummyEnemy:
    def __init__(self, x, y):
        self.x = x
        self.y = y


def test_fire_projectile_has_burn():
    t = Tower(320, 530, tower_type="fire", projectile_speed=100.0, inaccuracy=0.0)
    e1 = DummyEnemy(400, 530)
    proj = t.fire_at_closest([e1])
    assert proj is not None
    if isinstance(proj, dict):
        assert proj.get("effect") == "burn"
        assert "burn_duration" in proj and "burn_damage_per_second" in proj
    else:
        assert getattr(proj, "effect", None) == "burn"
        assert hasattr(proj, "burn_duration") and hasattr(
            proj, "burn_damage_per_second"
        )


def test_burn_applies_and_ticks():
    g = Game()
    g.selected_stage = "limbo"
    # Ensure FIRE tier 2 isn't active in test environment
    g.permanent_stats["fire_2"] = 0
    g.apply_permanent_stats()
    # Use dict-based enemy for deterministic ticking
    enemy = {
        "x": 320,
        "y": 520,
        "health": 20,
        "max_health": 20,
        "speed": 75,
        "radius": 12,
        "damage": 5,
        "type": "normal",
    }
    g.enemies = [enemy]

    t = Tower(320, 530, tower_type="fire", projectile_speed=100.0, inaccuracy=0.0)
    proj = t.fire_at_closest([enemy])
    assert proj is not None
    # Make the projectile hit immediately by placing at same coords
    proj.x = enemy["x"]
    proj.y = enemy["y"]
    # Reduce burn tick interval to 1 for fast test
    proj.burn_duration = 3
    proj.burn_damage_per_second = 6

    # Add projectile and run collision
    try:
        g.projectiles.add(proj)
    except Exception:
        g.projectiles.append(proj)

    g.handle_collisions()

    # Burn should have been applied
    assert enemy.get("burn_timer", 0) > 0
    assert enemy.get("burn_damage_per_second", 0) == 6

    # Speed up ticking: set tick counter small so damage applies next update
    enemy["burn_tick_counter"] = 1

    # Run one frame, which should apply a burn tick
    g.update_game()

    assert (
        enemy["health"] < 20
    ), f"Expected health < 20 after burn tick, got {enemy['health']}"

    # Continue ticking until health <=0
    while enemy["health"] > 0 and enemy.get("burn_timer", 0) > 0:
        enemy["burn_tick_counter"] = 1  # Force tick
        g.update_game()

    # Enemy should be dead and removed
    assert enemy["health"] <= 0
    assert enemy not in g.enemies


def test_fire_left_tier1_chained_propagation():
    g = Game()
    g.selected_stage = "limbo"

    # enable fire_1 permanent so burns schedule propagation and chaining
    g.permanent_stats["fire_1"] = 1
    g.apply_permanent_stats()

    # three dict-based enemies arranged so propagation must chain: e1->e2->e3
    e1 = {
        "x": 320,
        "y": 520,
        "health": 30,
        "max_health": 30,
        "speed": 75,
        "radius": 12,
        "damage": 5,
        "type": "normal",
    }
    e2 = {
        "x": 410,
        "y": 520,
        "health": 30,
        "max_health": 30,
        "speed": 75,
        "radius": 12,
        "damage": 5,
        "type": "normal",
    }
    # place e3 further so e1's propagation won't reach it directly (force chaining e1->e2->e3)
    e3 = {
        "x": 530,
        "y": 520,
        "health": 30,
        "max_health": 30,
        "speed": 75,
        "radius": 12,
        "damage": 5,
        "type": "normal",
    }
    g.enemies = [e1, e2, e3]

    t = Tower(320, 530, tower_type="fire", projectile_speed=100.0, inaccuracy=0.0)
    proj = t.fire_at_closest([e1])
    assert proj is not None
    proj.x = e1["x"]
    proj.y = e1["y"]
    proj.burn_duration = 4
    proj.burn_damage_per_second = 4

    try:
        g.projectiles.add(proj)
    except Exception:
        g.projectiles.append(proj)

    # initial collision
    g.handle_collisions()
    assert e1.get("burn_timer", 0) > 0
    assert e1.get("burn_propagate_on_death", False) is True
    # initial hops should be 2 (we lowered the max chain length)
    assert e1.get("burn_propagate_hops", 0) == 2

    # trigger first propagation by killing e1 (e1 -> e2)
    e1["health"] = 0
    g.update_game()
    assert e2.get("burn_timer", 0) > 0
    # after propagation hops should have been decremented to 1
    assert e2.get("burn_propagate_on_death", False) is True
    assert e2.get("burn_propagate_hops", 0) == 1

    # trigger second propagation by killing e2 (e2 -> e3)
    e2["health"] = 0
    g.update_game()
    assert e3.get("burn_timer", 0) > 0
    # e3 should have hops == 0 (chain limit reached)
    assert e3.get("burn_propagate_hops", 0) == 0

    # Verify burn ticks on e3
    e3["burn_tick_counter"] = 1
    prev = e3["health"]
    g.update_game()
    assert e3["health"] < prev


def test_fire_right_column_increases_burn_damage():
    g = Game()
    # ensure deterministic state
    for k in ("fire_4", "fire_5", "fire_6"):
        g.permanent_stats[k] = 0
    g.apply_permanent_stats()

    # create towers via game and record base burn DPS
    g.apply_tower("fire")
    # Fire once from the left tower
    dummy = type("D", (), {"x": 400, "y": 530})()
    p1 = g.left_tower.fire_at_closest([dummy])
    base_burn = (
        p1.burn_damage_per_second
        if not isinstance(p1, dict)
        else p1.get("burn_damage_per_second")
    )

    # Enable one right-column slot (+10% dmg for tower) and reapply
    g.permanent_stats["fire_4"] = 1
    g.apply_permanent_stats()

    p2 = g.left_tower.fire_at_closest([dummy])
    new_burn = (
        p2.burn_damage_per_second
        if not isinstance(p2, dict)
        else p2.get("burn_damage_per_second")
    )

    assert new_burn == pytest.approx(base_burn * 1.10)


def test_fire_left_tier2_doubles_burn():
    """When `fire_2` is active, burn duration and burn DPS should be doubled."""
    g = Game()
    g.selected_stage = "limbo"

    # enable fire_2 permanent and apply
    g.permanent_stats["fire_2"] = 1
    g.apply_permanent_stats()

    # single dict-based enemy
    enemy = {
        "x": 320,
        "y": 520,
        "health": 20,
        "max_health": 20,
        "speed": 75,
        "radius": 12,
        "damage": 5,
        "type": "normal",
    }
    g.enemies = [enemy]

    # Use a fire tower projectile and force immediate hit
    t = Tower(320, 530, tower_type="fire", projectile_speed=100.0, inaccuracy=0.0)
    proj = t.fire_at_closest([enemy])
    proj.x = enemy["x"]
    proj.y = enemy["y"]
    proj.burn_duration = 3
    proj.burn_damage_per_second = 5

    try:
        g.projectiles.add(proj)
    except Exception:
        g.projectiles.append(proj)

    # Collision should apply burn — values must be doubled by fire_2
    g.handle_collisions()
    assert enemy.get("burn_timer", 0) == 6
    assert enemy.get("burn_damage_per_second", 0) == 10


def test_fire_left_tier3_increases_player_weapon_damage_vs_burning():
    """Player weapons deal +25% damage to enemies that are burning when `fire_3` is active."""
    from src.projectile import Projectile

    g = Game()
    g.selected_stage = "limbo"

    # enable fire_3 permanent and apply
    g.permanent_stats["fire_3"] = 1
    g.apply_permanent_stats()

    # dict-based burning enemy
    enemy = {
        "x": 320,
        "y": 520,
        "health": 50,
        "max_health": 50,
        "speed": 75,
        "radius": 12,
        "damage": 5,
        "type": "normal",
        "burn_timer": 3,
        "burn_damage_per_second": 1,
    }
    g.enemies = [enemy]

    # create a player projectile (not a statue) and force immediate hit
    proj = Projectile(g.player.x, g.player.y, 0, 0, damage=20)
    proj.x = enemy["x"]
    proj.y = enemy["y"]

    try:
        g.projectiles.add(proj)
    except Exception:
        g.projectiles.append(proj)

    # Handle collision -> damage should be 20 * 1.25 == 25
    g.handle_collisions()
    assert enemy["health"] == 50 - int(round(20 * 1.25))

    # Damage number should be shown and highlighted yellow when the +25% bonus applied
    expected_text = str(int(round(20 * 1.25)))
    assert any(
        getattr(ft, "text", "") == expected_text
        and getattr(ft, "color", (255, 255, 255)) == (255, 200, 0)
        for ft in g.floating_texts
    )


def test_fire_left_tier3_does_not_affect_tower_projectiles():
    """Ensure `fire_3` only affects player weapons, not statue/tower projectiles."""
    g = Game()
    g.selected_stage = "limbo"

    g.permanent_stats["fire_3"] = 1
    g.apply_permanent_stats()

    enemy = {
        "x": 320,
        "y": 520,
        "health": 40,
        "max_health": 40,
        "speed": 75,
        "radius": 12,
        "damage": 5,
        "type": "normal",
        "burn_timer": 3,
        "burn_damage_per_second": 1,
    }
    g.enemies = [enemy]

    t = Tower(320, 530, tower_type="fire", projectile_speed=100.0, inaccuracy=0.0)
    p = t.fire_at_closest([enemy])
    p.x = enemy["x"]
    p.y = enemy["y"]
    base = p.damage if not isinstance(p, dict) else p.get("damage")

    try:
        g.projectiles.add(p)
    except Exception:
        g.projectiles.append(p)

    g.handle_collisions()
    # tower damage should be unchanged (no 1.25 multiplier)
    assert enemy["health"] == 40 - base


def test_fire_left_tier3_applies_to_multiple_player_weapons():
    """Ensure `fire_3` applies the +25% bonus across player weapons (basic, spear, shotgun, DemonStrike, Soul Drain) and shows visual indicator."""
    from src.projectile import Projectile, SoulDrainProjectile

    g = Game()
    g.selected_stage = "limbo"
    g.permanent_stats["fire_3"] = 1
    g.apply_permanent_stats()

    # helper to run collision for a projectile and assert +25% applied
    def assert_bonus_applies(proj, enemy_health_before, base_damage):
        proj.x = 320
        proj.y = 520
        # Ensure no other projectiles interfere with this assertion
        try:
            g.projectiles.empty()
        except Exception:
            g.projectiles = []
        try:
            g.projectiles.add(proj)
        except Exception:
            g.projectiles.append(proj)
        g.enemies = [
            {
                "x": 320,
                "y": 520,
                "health": enemy_health_before,
                "max_health": enemy_health_before,
                "speed": 75,
                "radius": 12,
                "damage": 5,
                "type": "normal",
                "burn_timer": 3,
                "burn_damage_per_second": 1,
            }
        ]
        g.handle_collisions()
        expected = enemy_health_before - int(round(base_damage * 1.25))
        assert g.enemies[0]["health"] == expected
        expected_text = str(int(round(base_damage * 1.25)))
        assert any(
            getattr(ft, "text", "") == expected_text
            and getattr(ft, "color", (255, 255, 255)) == (255, 200, 0)
            for ft in g.floating_texts
        )
        # clear floating texts for next case
        g.floating_texts.clear()

    # Basic projectile
    p_basic = Projectile(0, 0, 0, 0, damage=12)
    assert_bonus_applies(p_basic, 50, 12)

    # Spear
    p_spear = Projectile(0, 0, 0, 0, damage=20, weapon_type="spear")
    assert_bonus_applies(p_spear, 60, 20)

    # Shotgun pellet
    p_shot = Projectile(0, 0, 0, 0, damage=8, weapon_type="shotgun")
    assert_bonus_applies(p_shot, 40, 8)

    # DemonStrike (use method to ensure matching properties)
    g.player.x = 0
    g.player.y = 0
    g.fire_demon_strike(0, 1)
    # find the DemonStrike projectile in game.projectiles
    ds = next(
        (
            pp
            for pp in list(g.projectiles)
            if getattr(pp, "weapon_type", None) == "DemonStrike"
        ),
        None,
    )
    assert ds is not None
    assert_bonus_applies(ds, 100, getattr(ds, "damage", 0))

    # Soul Drain (use explicit class)
    sd = SoulDrainProjectile(0, 0, 0, 0, damage=10)
    assert_bonus_applies(sd, 40, 10)


def test_fire_left_tier1_propagates_burn_to_nearby_enemies():
    g = Game()
    g.selected_stage = "limbo"

    # enable fire_1 permanent so burns schedule propagation
    g.permanent_stats["fire_1"] = 1
    # ensure fire_2 doesn't interfere with these tests
    g.permanent_stats["fire_2"] = 0
    g.apply_permanent_stats()

    # two dict-based enemies close to each other
    e1 = {
        "x": 320,
        "y": 520,
        "health": 20,
        "max_health": 20,
        "speed": 75,
        "radius": 12,
        "damage": 5,
        "type": "normal",
    }
    e2 = {
        "x": 360,  # within 80px radius of e1
        "y": 520,
        "health": 20,
        "max_health": 20,
        "speed": 75,
        "radius": 12,
        "damage": 5,
        "type": "normal",
    }
    g.enemies = [e1, e2]

    t = Tower(320, 530, tower_type="fire", projectile_speed=100.0, inaccuracy=0.0)
    proj = t.fire_at_closest([e1])
    assert proj is not None
    # make projectile hit immediately
    proj.x = e1["x"]
    proj.y = e1["y"]
    proj.burn_duration = 3
    proj.burn_damage_per_second = 6

    try:
        g.projectiles.add(proj)
    except Exception:
        g.projectiles.append(proj)

    # collision should apply burn and mark e1 to propagate on death
    g.handle_collisions()
    assert e1.get("burn_timer", 0) > 0
    assert e1.get("burn_propagate_on_death", False) is True
    assert e1.get("burn_propagate_hops", 0) == 2

    # Simulate e1 dying to trigger propagation
    e1["health"] = 0
    g.update_game()

    # After propagation, e2 should have received a burn and be marked for chained propagation
    assert e2.get("burn_timer", 0) > 0
    assert e2.get("burn_damage_per_second", 0) == 6
    assert e2.get("burn_propagate_on_death", False) is True


def test_fire_left_tier1_propagates_burn_even_if_projectile_not_fire():
    """Burn propagation should work even if the projectile appearance is not "fire".

    This reproduces the gameplay case where burn comes from a non-fire appearance
    source (e.g. player shot) — propagation must still trigger when `fire_1` is active.
    """
    g = Game()
    g.selected_stage = "limbo"
    g.permanent_stats["fire_1"] = 1
    g.apply_permanent_stats()

    e1 = {
        "x": 320,
        "y": 520,
        "health": 20,
        "max_health": 20,
        "speed": 75,
        "radius": 12,
        "damage": 5,
        "type": "normal",
    }
    e2 = {
        "x": 360,
        "y": 520,
        "health": 20,
        "max_health": 20,
        "speed": 75,
        "radius": 12,
        "damage": 5,
        "type": "normal",
    }
    g.enemies = [e1, e2]

    t = Tower(320, 530, tower_type="fire", projectile_speed=100.0, inaccuracy=0.0)
    proj = t.fire_at_closest([e1])
    proj.x = e1["x"]
    proj.y = e1["y"]
    # simulate a non-fire appearance (player shot / other source)
    try:
        proj.appearance = "player_shot"
    except Exception:
        if isinstance(proj, dict):
            proj["appearance"] = "player_shot"

    proj.burn_duration = 3
    proj.burn_damage_per_second = 6

    try:
        g.projectiles.add(proj)
    except Exception:
        g.projectiles.append(proj)

    g.handle_collisions()

    # e1 must be marked for propagation regardless of projectile.appearance
    assert e1.get("burn_timer", 0) > 0
    assert e1.get("burn_propagate_on_death", False) is True

    # Kill e1 to trigger propagation
    e1["health"] = 0
    g.update_game()

    assert e2.get("burn_timer", 0) > 0


def test_fire_left_tier1_propagates_when_burning_enemy_killed_by_projectile():
    """If a burning enemy dies from a projectile/weapon, burn must still propagate."""
    from src.projectile import Projectile

    g = Game()
    g.selected_stage = "limbo"
    g.permanent_stats["fire_1"] = 1
    g.apply_permanent_stats()

    # two close dict enemies
    e1 = {
        "x": 320,
        "y": 520,
        "health": 12,
        "max_health": 12,
        "speed": 75,
        "radius": 12,
        "damage": 5,
        "type": "normal",
    }
    e2 = {
        "x": 360,
        "y": 520,
        "health": 20,
        "max_health": 20,
        "speed": 75,
        "radius": 12,
        "damage": 5,
        "type": "normal",
    }
    g.enemies = [e1, e2]

    # Apply burn to e1 (fire projectile)
    t = Tower(320, 530, tower_type="fire", projectile_speed=100.0, inaccuracy=0.0)
    p_fire = t.fire_at_closest([e1])
    p_fire.x = e1["x"]
    p_fire.y = e1["y"]
    p_fire.burn_duration = 6
    p_fire.burn_damage_per_second = 2
    try:
        g.projectiles.add(p_fire)
    except Exception:
        g.projectiles.append(p_fire)
    g.handle_collisions()

    assert e1.get("burn_timer", 0) > 0
    assert e1.get("burn_propagate_on_death", False) is True

    # Now create a player projectile that will *kill* e1 immediately
    # Place it on top of e1 so collision resolves through the normal projectile path
    killer = Projectile(
        e1["x"], e1["y"], 0, -500, damage=20, radius=6, weapon_type=None
    )
    try:
        g.projectiles.add(killer)
    except Exception:
        g.projectiles.append(killer)

    # Process collisions -> e1 should die from projectile hit and propagation should run
    g.handle_collisions()

    # e2 must receive the propagated burn
    assert e2.get("burn_timer", 0) > 0
    # propagated target hops should be source_hops - 1 == 1
    assert e2.get("burn_propagate_hops", 0) == 1

    # Ensure burn actually ticks on e2
    e2["burn_tick_counter"] = 1
    prev_health = e2["health"]
    g.update_game()
    assert e2["health"] < prev_health


def test_fire_left_tier1_propagates_when_burning_enemy_killed_by_beast_projectile():
    """Regression test: beast projectiles must allow burn propagation on death."""
    from src.projectile import Projectile

    g = Game()
    g.selected_stage = "limbo"
    g.permanent_stats["fire_1"] = 1
    g.apply_permanent_stats()

    e1 = {
        "x": 320,
        "y": 520,
        "health": 12,
        "max_health": 12,
        "speed": 75,
        "radius": 12,
        "damage": 5,
        "type": "normal",
    }
    e2 = {
        "x": 360,
        "y": 520,
        "health": 20,
        "max_health": 20,
        "speed": 75,
        "radius": 12,
        "damage": 5,
        "type": "normal",
    }
    g.enemies = [e1, e2]

    # Apply burn to e1
    t = Tower(320, 530, tower_type="fire", projectile_speed=100.0, inaccuracy=0.0)
    p_fire = t.fire_at_closest([e1])
    p_fire.x = e1["x"]
    p_fire.y = e1["y"]
    p_fire.burn_duration = 6
    p_fire.burn_damage_per_second = 2
    try:
        g.projectiles.add(p_fire)
    except Exception:
        g.projectiles.append(p_fire)
    g.handle_collisions()

    assert e1.get("burn_timer", 0) > 0
    assert e1.get("burn_propagate_on_death", False) is True

    # Now kill e1 using a Beast projectile (weapon_type="beast")
    killer = Projectile(
        e1["x"], e1["y"], 0, -500, damage=20, radius=6, weapon_type="beast"
    )
    try:
        g.projectiles.add(killer)
    except Exception:
        g.projectiles.append(killer)

    # Process collisions -> e1 should die and propagation should occur
    g.handle_collisions()

    assert e2.get("burn_timer", 0) > 0
    assert e2.get("burn_propagate_hops", 0) == 1


def test_fire_left_tier1_propagates_burn_to_sprite_enemies_on_death():
    """Ensure propagation works for sprite-based (in-game) enemies when the
    burned enemy dies."""
    import pygame

    g = Game()
    g.selected_stage = "limbo"

    # enable fire_1 permanent
    g.permanent_stats["fire_1"] = 1
    # ensure fire_2 doesn't interfere with these tests
    g.permanent_stats["fire_2"] = 0
    g.apply_permanent_stats()

    class SpriteEnemy(pygame.sprite.Sprite):
        def __init__(self, x, y):
            super().__init__()
            self.x = x
            self.y = y
            self.health = 30
            self.max_health = 30
            self.radius = 12
            self.damage = 5
            self.enemy_type = "normal"
            self.rect = pygame.Rect(int(x), int(y), 8, 8)

        def kill(self):
            # emulate pygame.sprite.Sprite.kill behaviour
            try:
                self.remove(self.groups())
            except Exception:
                pass

        def update(self, player, game):
            # Minimal update to support burn ticking in tests
            try:
                if (
                    not hasattr(self, "burn_tick_timer")
                    or getattr(self, "burn_tick_timer", 0) <= 0
                ):
                    self.burn_tick_timer = getattr(game, "fps", 60)
                self.burn_tick_timer -= 1
                if getattr(self, "burn_tick_timer", 0) <= 0:
                    bdps = getattr(self, "burn_damage_per_second", 0)
                    if bdps:
                        self.health = max(0, self.health - bdps)
                    self.burn_tick_timer = getattr(game, "fps", 60)
            except Exception:
                pass

    # create and add sprite enemies to the game's enemy group
    e1 = SpriteEnemy(320, 520)
    e2 = SpriteEnemy(370, 520)  # within 100px radius
    g.enemies = pygame.sprite.Group()
    g.enemies.add(e1)
    g.enemies.add(e2)

    # Fire a projectile at e1 so collision applies burn
    t = Tower(320, 530, tower_type="fire", projectile_speed=100.0, inaccuracy=0.0)
    proj = t.fire_at_closest([e1])
    proj.x = e1.x
    proj.y = e1.y
    proj.burn_duration = 3
    proj.burn_damage_per_second = 5
    try:
        g.projectiles.add(proj)
    except Exception:
        g.projectiles.append(proj)

    # Collision applies burn and marks e1 for propagation-on-death
    g.handle_collisions()
    assert getattr(e1, "burn_timer", 0) > 0
    assert getattr(e1, "burn_propagate_on_death", False) is True
    assert getattr(e1, "burn_propagate_hops", 0) == 2

    # Kill e1 to trigger propagation
    e1.health = 0
    g.update_game()

    # e2 (sprite) should receive burn attributes
    assert getattr(e2, "burn_timer", 0) > 0
    assert getattr(e2, "burn_damage_per_second", 0) == 5
    assert getattr(e2, "burn_propagate_on_death", False) is True
    # propagated sprite target hops should be source_hops - 1 == 1
    assert getattr(e2, "burn_propagate_hops", 0) == 1

    # Ensure burn ticks on e2
    e2.burn_tick_timer = 1
    prev = e2.health
    g.update_game()
    assert e2.health < prev


def test_fire_left_tier1_propagates_burn_to_boss_on_death():
    """Propagation should affect bosses when a burned enemy dies."""
    import pygame

    g = Game()
    g.selected_stage = "limbo"
    g.permanent_stats["fire_1"] = 1
    # ensure fire_2 doesn't interfere with this propagation test
    g.permanent_stats["fire_2"] = 0
    g.apply_permanent_stats()

    # small dict enemy that will be burned and then killed
    e = {
        "x": 320,
        "y": 520,
        "health": 10,
        "max_health": 10,
        "speed": 0,
        "radius": 12,
        "damage": 0,
        "type": "normal",
    }
    g.enemies = [e]

    # simple Boss sprite implementing minimal fields used by propagation
    class DummyBoss(pygame.sprite.Sprite):
        def __init__(self, x, y):
            super().__init__()
            self.x = x
            self.y = y
            self.health = 200
            self.max_health = 200
            self.radius = 24
            self.damage = 20
            self.enemy_type = "boss_medium"
            self.rect = pygame.Rect(int(x), int(y), 16, 16)

        def kill(self):
            try:
                self.remove(self.groups())
            except Exception:
                pass

        def update(self, player, game):
            # minimal tick support for burn
            try:
                if (
                    not hasattr(self, "burn_tick_timer")
                    or getattr(self, "burn_tick_timer", 0) <= 0
                ):
                    self.burn_tick_timer = getattr(game, "fps", 60)
                self.burn_tick_timer -= 1
                if getattr(self, "burn_tick_timer", 0) <= 0:
                    bdps = getattr(self, "burn_damage_per_second", 0)
                    if bdps:
                        self.health = max(0, self.health - bdps)
                    self.burn_tick_timer = getattr(game, "fps", 60)
            except Exception:
                pass

    boss = DummyBoss(460, 520)  # within 150px of e (adjusted for smaller radius)
    g.bosses = pygame.sprite.Group()
    g.bosses.add(boss)

    # Apply a fire projectile to the small enemy
    t = Tower(320, 530, tower_type="fire", projectile_speed=100.0, inaccuracy=0.0)
    proj = t.fire_at_closest([e])
    proj.x = e["x"]
    proj.y = e["y"]
    proj.burn_duration = 3
    proj.burn_damage_per_second = 8

    try:
        g.projectiles.add(proj)
    except Exception:
        g.projectiles.append(proj)

    g.handle_collisions()
    # simulate enemy death to trigger propagation
    e["health"] = 0
    g.update_game()

    # Boss should receive burn
    assert getattr(boss, "burn_timer", 0) > 0
    assert getattr(boss, "burn_damage_per_second", 0) == 8

    # Visual chain effect should have been added
    assert any(
        len(e.get("points", [])) >= 2
        for e in getattr(g.game_state, "chain_lightning_effects", [])
    )

    # Burn should tick on boss
    boss.burn_tick_timer = 1
    prev = boss.health
    g.update_game()
    assert boss.health < prev


def test_boss_receives_burn_when_hit_by_fire_projectile():
    """Boss (Inquisitor) must receive burn when directly hit by a fire projectile."""

    g = Game()
    g.selected_stage = "limbo"
    # spawn inquisitor boss via manager
    boss = g.enemy_manager.spawn_boss("inquisitor")
    assert any(getattr(b, "enemy_type", "") == "boss_inquisitor" for b in g.bosses)

    # Fire a Tower (statue) projectile at the boss to apply burn
    from src.core.entities.tower import Tower

    t = Tower(320, 530, tower_type="fire", projectile_speed=100.0, inaccuracy=0.0)
    proj = t.fire_at_closest([boss])
    proj.x = getattr(boss, "x", 0)
    proj.y = getattr(boss, "y", 0)
    proj.burn_duration = 6
    proj.burn_damage_per_second = 3
    try:
        g.projectiles.add(proj)
    except Exception:
        g.projectiles.append(proj)
    # ensure projectile.rect matches boss position so pygame.sprite.spritecollide detects hit
    try:
        proj.rect.center = (int(getattr(boss, "x", 0)), int(getattr(boss, "y", 0)))
    except Exception:
        pass

    g.handle_collisions()

    # Boss should become burning
    assert getattr(boss, "burn_timer", 0) > 0
    # account for FIRE tier-2 doubling if present in permanent_stats
    expected_dps = proj.burn_damage_per_second * (
        2 if g.permanent_stats.get("fire_2", 0) else 1
    )
    expected_duration = proj.burn_duration * (
        2 if g.permanent_stats.get("fire_2", 0) else 1
    )
    assert getattr(boss, "burn_damage_per_second", 0) == expected_dps
    assert getattr(boss, "burn_timer", 0) == expected_duration

    # Burn should tick
    boss.burn_tick_timer = 1
    prev = boss.health
    g.update_game()
    assert boss.health < prev
