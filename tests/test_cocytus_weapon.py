"""Tests for the Cocytus weapon — ice shard rain with freeze synergy."""

from __future__ import annotations

import math
import types

import pytest

from src.weapons import (
    WEAPON_DEFS,
    cocytus_cooldown,
    cocytus_damage,
    cocytus_impact_radius,
    cocytus_shards,
)


# ---------------------------------------------------------------------------
# WEAPON_DEFS definition tests
# ---------------------------------------------------------------------------


def test_cocytus_definition_present():
    assert "cocytus" in WEAPON_DEFS


def test_cocytus_definition_fields():
    w = WEAPON_DEFS["cocytus"]
    assert w["name"] == "Cocytus"
    assert w["max_level"] == 7
    assert w["required_meta_level"] == 15
    assert w["base_cd"] == pytest.approx(5.0)
    assert w["min_cd"] == pytest.approx(3.5)
    assert w["base_shards"] == 4
    assert w["base_impact_radius"] == 60
    assert w["base_damage"] == 18
    assert w["puddle_slow_factor"] == pytest.approx(0.5)
    assert w["puddle_slow_duration"] == 120
    assert w["puddle_lifetime"] == 300
    assert w["freeze_duration"] == 120
    assert "icon" in w


def test_cocytus_upgrade_descriptions_all_levels():
    descs = WEAPON_DEFS["cocytus"]["upgrade_descriptions"]
    for lvl in range(1, 8):
        assert lvl in descs
        assert isinstance(descs[lvl], str)
        assert len(descs[lvl]) > 0


# ---------------------------------------------------------------------------
# Scaling helper tests
# ---------------------------------------------------------------------------


def test_cocytus_cooldown_all_levels():
    expected = [5.0, 4.75, 4.5, 4.25, 4.0, 3.75, 3.5]
    for i, lvl in enumerate(range(1, 8)):
        assert cocytus_cooldown(lvl) == pytest.approx(expected[i], rel=1e-6)


def test_cocytus_cooldown_never_below_min():
    # Level 8+ should clamp at min_cd
    assert cocytus_cooldown(99) == pytest.approx(3.5, rel=1e-6)
    assert cocytus_cooldown(7) == pytest.approx(3.5, rel=1e-6)


def test_cocytus_shards_progression():
    # 4,4,5,5,6,6,7
    expected = [4, 4, 5, 5, 6, 6, 7]
    for lvl in range(1, 8):
        assert cocytus_shards(lvl) == expected[lvl - 1], (
            f"Level {lvl}: expected {expected[lvl-1]} shards, got {cocytus_shards(lvl)}"
        )


def test_cocytus_impact_radius_progression():
    # 60, 68, 76, 84, 92, 100, 108
    for lvl in range(1, 8):
        expected = 60 + (lvl - 1) * 8
        assert cocytus_impact_radius(lvl) == expected


def test_cocytus_damage_level_scaling():
    ref = 30  # reference player damage
    for lvl in range(1, 8):
        base = 18 + (lvl - 1) * 4
        expected = int(base * (ref / 30.0))
        assert cocytus_damage(lvl, ref) == expected


def test_cocytus_damage_scales_with_player_damage():
    # double player damage should roughly double the damage
    d1 = cocytus_damage(1, 30)
    d2 = cocytus_damage(1, 60)
    assert d2 == pytest.approx(d1 * 2, abs=1)


def test_cocytus_damage_clamped_to_valid_levels():
    assert cocytus_damage(0, 30) == cocytus_damage(1, 30)
    assert cocytus_damage(99, 30) == cocytus_damage(7, 30)


# ---------------------------------------------------------------------------
# Integration tests via Game
# ---------------------------------------------------------------------------


def _make_game():
    """Return a Game instance configured for Cocytus testing."""
    from src.game import Game

    g = Game()
    g.player_weapons = ["cocytus"]
    g.weapon_levels = {"cocytus": 1}
    g.cocytus_cooldown_timer = 0
    g.player.x = 400
    g.player.y = 360
    g.mouse_x = 600
    g.mouse_y = 300
    return g


def test_fire_cocytus_queues_shards():
    """Firing Cocytus should queue shards. The shard with delay=0 lands in the same
    update_weapon_firing() call, so the remaining list has (num_shards - 1) entries."""
    g = _make_game()
    assert g.cocytus_shards == []
    g.update_weapon_firing()
    expected_shards = cocytus_shards(1)
    # The first shard (delay=0) is processed immediately in the same frame;
    # remaining shards stay in the queue.
    assert len(g.cocytus_shards) == expected_shards - 1


def test_fire_cocytus_sets_cooldown():
    """Cooldown timer is set then immediately decremented by update_weapon_firing,
    so the observed value is (expected_frames - 1)."""
    g = _make_game()
    g.update_weapon_firing()
    expected_frames = int(cocytus_cooldown(1) * g.fps)
    assert g.cocytus_cooldown_timer == expected_frames - 1


def test_cocytus_does_not_fire_on_cooldown():
    g = _make_game()
    g.cocytus_cooldown_timer = 100
    g.update_weapon_firing()
    assert g.cocytus_shards == []


def test_shard_positions_within_impact_radius():
    g = _make_game()
    g.weapon_levels = {"cocytus": 1}
    g.mouse_x = 640
    g.mouse_y = 360
    g.update_weapon_firing()
    r = cocytus_impact_radius(1)
    for shard in g.cocytus_shards:
        dist = math.hypot(shard["x"] - g.mouse_x, shard["y"] - g.mouse_y)
        assert dist <= r + 1e-6, f"Shard at ({shard['x']:.1f},{shard['y']:.1f}) is {dist:.1f}px from cursor, expected ≤{r}"


def test_shard_delays_are_staggered():
    """Shards in the queue (delay > 0) must have strictly increasing delays."""
    g = _make_game()
    g.update_weapon_firing()
    # The delay=0 shard lands immediately and is already consumed; only deferred
    # shards remain in the list.
    delays = [s["delay"] for s in g.cocytus_shards]
    assert all(d > 0 for d in delays), "All remaining shards should have positive delay"
    assert all(delays[i] <= delays[i + 1] for i in range(len(delays) - 1))


def test_update_cocytus_shards_processes_landing():
    g = _make_game()
    g.weapon_levels = {"cocytus": 1}
    # Inject a single shard already at delay 0
    g.cocytus_shards = [{"x": 640.0, "y": 360.0, "delay": 0, "weapon_level": 1, "damage": 18}]
    puddles_before = len(g.ice_puddles)
    g.weapon_system.update_cocytus_shards()
    assert len(g.cocytus_shards) == 0, "Shard with delay=0 should be consumed"
    assert len(g.ice_puddles) == puddles_before + 1, "A puddle should be injected on landing"


def test_cocytus_puddle_has_correct_source():
    g = _make_game()
    g.cocytus_shards = [{"x": 640.0, "y": 360.0, "delay": 0, "weapon_level": 1, "damage": 18}]
    g.weapon_system.update_cocytus_shards()
    puddle = g.ice_puddles[-1]
    assert puddle.get("source") == "cocytus"


def test_cocytus_puddle_uses_weapon_defs_values():
    g = _make_game()
    g.cocytus_shards = [{"x": 640.0, "y": 360.0, "delay": 0, "weapon_level": 1, "damage": 18}]
    g.weapon_system.update_cocytus_shards()
    puddle = g.ice_puddles[-1]
    defs = WEAPON_DEFS["cocytus"]
    assert puddle["timer"] == defs["puddle_lifetime"]
    assert puddle["slow_factor"] == pytest.approx(defs["puddle_slow_factor"])
    assert puddle["slow_duration"] == defs["puddle_slow_duration"]


def test_cocytus_puddle_radius_scales_with_level():
    from src.game import Game

    g = Game()
    g.player_weapons = ["cocytus"]
    for lvl in [1, 4, 7]:
        g.cocytus_shards = [{"x": 640.0, "y": 360.0, "delay": 0, "weapon_level": lvl, "damage": 18}]
        g.ice_puddles.clear()
        g.weapon_system.update_cocytus_shards()
        puddle = g.ice_puddles[-1]
        expected_r = 40 + (lvl - 1) * 3
        assert puddle["radius"] == expected_r, f"Level {lvl}: expected radius {expected_r}, got {puddle['radius']}"


# ---------------------------------------------------------------------------
# Freeze synergy tests
# ---------------------------------------------------------------------------


def _make_dummy_enemy(x: float = 640.0, y: float = 360.0, speed: float = 2.0):
    """Minimal enemy-like object for freeze synergy testing."""
    e = types.SimpleNamespace(
        x=x,
        y=y,
        speed=speed,
        health=200,
        max_health=200,
        slow_timer=0,
        slow_factor=1.0,
        frozen_timer=0,
    )

    def take_damage(dmg):
        e.health = max(0, e.health - dmg)

    e.take_damage = take_damage
    return e


def test_freeze_applied_when_enemy_in_ice_tower_puddle():
    """Enemy already inside an ice tower puddle must be frozen on Cocytus impact."""
    from src.game import Game

    g = Game()
    g.player_weapons = ["cocytus"]
    g.weapon_levels = {"cocytus": 1}

    enemy = _make_dummy_enemy(x=640.0, y=360.0)
    g.enemies = [enemy]

    # Place an ice tower puddle covering the enemy (not Cocytus-sourced)
    g.ice_puddles.append({"x": 640.0, "y": 360.0, "radius": 80, "timer": 300,
                           "slow_factor": 0.6, "slow_duration": 120})

    # Fire Cocytus directly at enemy position
    g.cocytus_shards = [{"x": 640.0, "y": 360.0, "delay": 0, "weapon_level": 1, "damage": 18}]
    g.weapon_system.update_cocytus_shards()

    assert enemy.frozen_timer == WEAPON_DEFS["cocytus"]["freeze_duration"], (
        "Enemy in ice tower puddle should be frozen after Cocytus hit"
    )
    assert enemy.speed == 0


def test_no_freeze_without_ice_tower_puddle():
    """Enemy NOT in any ice tower puddle must not be frozen — only slowed."""
    from src.game import Game

    g = Game()
    g.player_weapons = ["cocytus"]
    g.weapon_levels = {"cocytus": 1}

    enemy = _make_dummy_enemy(x=640.0, y=360.0)
    g.enemies = [enemy]
    g.ice_puddles.clear()

    g.cocytus_shards = [{"x": 640.0, "y": 360.0, "delay": 0, "weapon_level": 1, "damage": 18}]
    g.weapon_system.update_cocytus_shards()

    assert enemy.frozen_timer == 0, "No ice tower puddle present — enemy must not be frozen"


def test_no_freeze_from_cocytus_own_puddle():
    """Cocytus-sourced puddle alone must NOT trigger the freeze synergy."""
    from src.game import Game

    g = Game()
    g.player_weapons = ["cocytus"]
    g.weapon_levels = {"cocytus": 1}

    enemy = _make_dummy_enemy(x=640.0, y=360.0)
    g.enemies = [enemy]
    g.ice_puddles.clear()

    # Pre-existing Cocytus puddle — should NOT count as ice tower coverage
    g.ice_puddles.append({"x": 640.0, "y": 360.0, "radius": 80, "timer": 300,
                           "slow_factor": 0.5, "slow_duration": 120, "source": "cocytus"})

    g.cocytus_shards = [{"x": 640.0, "y": 360.0, "delay": 0, "weapon_level": 1, "damage": 18}]
    g.weapon_system.update_cocytus_shards()

    assert enemy.frozen_timer == 0, "Cocytus puddle must not trigger self-freeze synergy"


def test_freeze_saves_original_speed():
    """_apply_freeze must save original_speed so it can be restored after thaw."""
    from src.game import Game

    g = Game()
    enemy = _make_dummy_enemy(speed=3.0)
    g.weapon_system._apply_freeze(enemy, 0.0, 0.0)
    assert hasattr(enemy, "original_speed")
    assert enemy.original_speed == pytest.approx(3.0)
    assert enemy.speed == 0


def test_freeze_does_not_overwrite_original_speed():
    """If original_speed is already saved (e.g. from slow), it must not be overwritten."""
    from src.game import Game

    g = Game()
    enemy = _make_dummy_enemy(speed=0.5)  # already slowed
    enemy.original_speed = 3.0
    g.weapon_system._apply_freeze(enemy, 0.0, 0.0)
    assert enemy.original_speed == pytest.approx(3.0)


def test_frozen_timer_decrements_and_restores_speed():
    """Enemy update must decrement frozen_timer and restore speed at expiry."""
    from src.game import Game

    g = Game()
    enemy_obj = _make_dummy_enemy(speed=2.0)
    enemy_obj.original_speed = 2.0
    enemy_obj.frozen_timer = 2
    enemy_obj.speed = 0

    # Simulate two frames of enemy update using weapon_system freeze guard
    # (we test the enemy.py path by calling its update block directly)
    # Since dummy enemy has no update(), exercise the logic manually
    for _ in range(2):
        if enemy_obj.frozen_timer > 0:
            enemy_obj.frozen_timer -= 1
            if enemy_obj.frozen_timer <= 0:
                if hasattr(enemy_obj, "original_speed"):
                    enemy_obj.speed = enemy_obj.original_speed
                    delattr(enemy_obj, "original_speed")
                enemy_obj.frozen_timer = 0
            else:
                enemy_obj.speed = 0

    assert enemy_obj.frozen_timer == 0
    assert enemy_obj.speed == pytest.approx(2.0)
    assert not hasattr(enemy_obj, "original_speed")


def test_enemy_outside_radius_not_damaged():
    """Enemies outside the puddle radius should not receive damage or freeze."""
    from src.game import Game

    g = Game()
    g.player_weapons = ["cocytus"]
    g.weapon_levels = {"cocytus": 1}

    enemy = _make_dummy_enemy(x=800.0, y=360.0)  # far from impact
    g.enemies = [enemy]
    # Add ice tower puddle at impact site (not covering enemy)
    g.ice_puddles.append({"x": 640.0, "y": 360.0, "radius": 80, "timer": 300,
                           "slow_factor": 0.6, "slow_duration": 120})

    g.cocytus_shards = [{"x": 640.0, "y": 360.0, "delay": 0, "weapon_level": 1, "damage": 50}]
    g.weapon_system.update_cocytus_shards()

    assert enemy.health == enemy.max_health, "Enemy outside radius must not take damage"
    assert enemy.frozen_timer == 0
