#!/usr/bin/env python3
"""Tests that upgrading/downgrading permanent stats via the UI updates in-game multipliers."""

import pytest

from src.game import Game


def test_clicking_power_updates_damage_multiplier():
    g = Game()
    # ensure we are in-game and showing the permanent upgrades menu
    g.showing_stage_menu = False
    g.showing_permanent_upgrades = True

    # give ourselves a meta point so the stat can be purchased
    g.global_progress["meta_points"] = 1

    left_x = g.width // 2 - 420
    # power stat is at y = 140 (as defined in the config)
    pos = (left_x + 5, 140 + 5)

    # Ensure starting from a known baseline
    g.permanent_stats["power"] = 0
    # isolate from Blasphemy bonuses
    g.permanent_stats["blasphemy_1"] = 0
    g.apply_permanent_stats()

    before = g.permanent_stats.get("power", 0)
    g.handle_mouse_click(pos, button=1)  # left click to upgrade
    after = g.permanent_stats.get("power", 0)
    assert after == before + 1
    # meta point spent
    assert g.global_progress.get("meta_points", 0) == 0
    # multiplier should reflect the upgrade (+5% per level)
    assert g.damage_multiplier == pytest.approx(1.0 + after * 0.05)
    assert g.player.damage_multiplier == pytest.approx(g.damage_multiplier)

    # right-click to refund and re-spend
    g.handle_mouse_click(pos, button=3)
    assert g.permanent_stats["power"] == before
    assert g.global_progress.get("meta_points", 0) == 1
    # spend again
    g.handle_mouse_click(pos, button=1)
    assert g.permanent_stats["power"] == before + 1
    assert g.global_progress.get("meta_points", 0) == 0


def test_clicking_blasphemy1_increases_max_health():
    g = Game()
    g.showing_stage_menu = False
    g.showing_permanent_upgrades = True

    left_x = g.width // 2 - 420
    # compute top-left blasphemy box coords to click inside it
    box_spacing = 100
    start_x = left_x + box_spacing // 2 - 40
    box_x = start_x + (0 * box_spacing)
    box_y1 = 320 + 80
    pos = (box_x - 30 + 5, box_y1 + 5)  # small offset inside the box

    # ensure baseline (isolate blasphemy effect by zeroing POWER)
    # global_progress always starts fresh since persistence is disabled
    g.global_progress["meta_points"] = 0
    g.permanent_stats["power"] = 0
    g.permanent_stats["blasphemy_1"] = 0
    g.apply_permanent_stats()

    # click three times to reach max level (3)
    base_max = g.player.max_health
    for expected in (1, 2, 3):
        g.handle_mouse_click(pos, button=1)
        assert g.permanent_stats["blasphemy_1"] == expected
        # each level should add 15 HP to the player's max health
        assert g.player.max_health == pytest.approx(base_max + expected * 15)

    # right click to downgrade one level and ensure max health drops accordingly
    g.handle_mouse_click(pos, button=3)
    assert g.permanent_stats["blasphemy_1"] == 2
    assert g.player.max_health == pytest.approx(base_max + 2 * 15)


def test_clicking_blasphemy2_increases_regeneration():
    g = Game()
    g.showing_stage_menu = False
    g.showing_permanent_upgrades = True

    left_x = g.width // 2 - 420
    box_spacing = 100
    start_x = left_x + box_spacing // 2 - 40
    box_x = start_x + (1 * box_spacing)  # second box
    box_y1 = 320 + 80
    pos = (box_x - 30 + 5, box_y1 + 5)

    # baseline: no vigor, no blasphemy_2
    g.permanent_stats["vigor"] = 0
    g.permanent_stats["blasphemy_2"] = 0
    g.reset_game()
    g.showing_stage_menu = False
    g.showing_permanent_upgrades = True

    # apply some damage so we can observe healing
    g.player.health = g.player.max_health * 0.5

    for expected in (1, 2, 3):
        g.handle_mouse_click(pos, button=1)
        assert g.permanent_stats["blasphemy_2"] == expected
        # reset baseline health and frame counter so each level is tested independently
        g.player.health = g.player.max_health * 0.5
        g.frame_count = 0
        # simulate enough frames for a single 2‑second tick
        frames = 2 * g.fps
        # clear any enemies/projectiles to avoid incidental damage
        try:
            g.enemies = []
        except Exception:
            import pygame

            g.enemies = pygame.sprite.Group()
        import pygame

        g.enemy_projectiles = pygame.sprite.Group()
        g.enemy_spawn_timer = 10**6
        try:
            g.enemy_manager.enemy_spawn_timer = 10**6
        except Exception:
            pass

        for _ in range(frames):
            g.update_game()
        expected_heal = expected * 0.5  # 0.5 HP per level every 2s
        assert g.player.health == pytest.approx(
            min(g.player.max_health, g.player.max_health * 0.5 + expected_heal)
        )

    # downgrade once and ensure regen rate drops
    g.handle_mouse_click(pos, button=3)
    assert g.permanent_stats["blasphemy_2"] == 2


def test_clicking_blasphemy3_reduces_damage_taken():
    g = Game()
    g.showing_stage_menu = False
    g.showing_permanent_upgrades = True

    left_x = g.width // 2 - 420
    box_spacing = 100
    start_x = left_x + box_spacing // 2 - 40
    box_x = start_x + (2 * box_spacing)  # third box
    box_y1 = 320 + 80
    pos = (box_x - 30 + 5, box_y1 + 5)

    # isolate effect (no structure or blasphemy_6)
    g.permanent_stats["structure"] = 0
    g.permanent_stats["blasphemy_6"] = 0
    g.permanent_stats["blasphemy_3"] = 0
    g.apply_permanent_stats()

    for expected in (1, 2, 3):
        g.handle_mouse_click(pos, button=1)
        assert g.permanent_stats["blasphemy_3"] == expected
        assert g.damage_reduction_multiplier == pytest.approx(1.0 - expected * 0.10)
        assert g.player.damage_reduction_multiplier == pytest.approx(
            g.damage_reduction_multiplier
        )

    # downgrade once
    g.handle_mouse_click(pos, button=3)
    assert g.permanent_stats["blasphemy_3"] == 2
    assert g.damage_reduction_multiplier == pytest.approx(1.0 - 2 * 0.10)


def test_clicking_blasphemy4_updates_xp_multiplier():
    g = Game()
    g.showing_stage_menu = False
    g.showing_permanent_upgrades = True

    left_x = g.width // 2 - 420
    box_spacing = 100
    start_x = left_x + box_spacing // 2 - 40
    box_x = start_x + (3 * box_spacing)  # fourth box
    box_y1 = 320 + 80
    pos = (box_x - 30 + 5, box_y1 + 5)

    g.permanent_stats["structure"] = 0
    g.permanent_stats["blasphemy_4"] = 0
    g.apply_permanent_stats()

    for expected in (1, 2, 3):
        g.handle_mouse_click(pos, button=1)
        assert g.permanent_stats["blasphemy_4"] == expected
        assert g.xp_multiplier == pytest.approx(1.0 + expected * 0.10)

    # downgrade once
    g.handle_mouse_click(pos, button=3)
    assert g.permanent_stats["blasphemy_4"] == 2
    assert g.xp_multiplier == pytest.approx(1.0 + 2 * 0.10)


def test_vigor_regenerates_health_every_5s_per_level():
    g = Game()
    # Apply permanent vigor (blasphemy_2 also grants regen, but we leave it at 0 here)
    g.permanent_stats["vigor"] = 2
    g.permanent_stats["blasphemy_2"] = 0
    g.reset_game()

    max_hp = g.player.max_health
    # simulate player being wounded
    g.player.health = max_hp * 0.5

    # Advance exactly 5 seconds of game time (use update_game to force in-game updates)
    # Prevent incidental enemy contact during this deterministic timing test
    try:
        g.enemies = []
    except Exception:
        import pygame

        g.enemies = pygame.sprite.Group()
    import pygame

    g.enemy_projectiles = pygame.sprite.Group()

    # Prevent automatic spawns during this timing-sensitive test
    g.enemy_spawn_timer = 10**6
    try:
        g.enemy_manager.enemy_spawn_timer = 10**6
    except Exception:
        pass

    frames = 5 * g.fps
    for _ in range(frames):
        g.update_game()

    # Expected heal = 0.5 HP per level -> 1.0 HP total for level 2
    expected_heal = 0.5 * 2
    assert g.player.health == pytest.approx(
        min(max_hp, max_hp * 0.5 + expected_heal), rel=1e-6
    )


def test_clicking_adrenaline_updates_fire_rate_multiplier():
    g = Game()
    g.showing_stage_menu = False
    g.showing_permanent_upgrades = True

    left_x = g.width // 2 - 420
    pos = (left_x + 5, 230 + 5)  # adrenaline y = 230

    # set a known value then downgrade
    g.permanent_stats["adrenaline"] = 2
    # isolate from Blasphemy bonuses (none of them affect fire rate now)
    g.permanent_stats["blasphemy_3"] = 0
    g.apply_permanent_stats()
    before = g.permanent_stats["adrenaline"]

    # right click to downgrade
    g.handle_mouse_click(pos, button=3)
    after = g.permanent_stats["adrenaline"]
    assert after == before - 1
    assert g.fire_rate_multiplier == pytest.approx(1.0 + after * 0.05)
    assert g.player.fire_rate_multiplier == pytest.approx(g.fire_rate_multiplier)


def test_adrenaline_grants_crit_chance_even_without_blasphemy6(monkeypatch):
    # Ensure adrenaline alone contributes to crit chance and deals 50% extra
    g = Game()
    g.permanent_stats["adrenaline"] = 3
    g.permanent_stats["blasphemy_6"] = 0
    # make the collision system ready
    cs = g.collision_system

    class DummyProj:
        def __init__(self):
            self.is_enemy_projectile = False
            self.damage = 10

    class DummyEnemy:
        def __init__(self):
            self.burn_timer = 0

    proj = DummyProj()
    enemy = DummyEnemy()

    # patch random.random to always return 0 (guaranteed crit)
    monkeypatch.setattr("random.random", lambda: 0.0)
    dmg = cs._player_damage_vs_burning(proj, enemy, proj.damage)
    assert dmg == 15

    # patch random.random to return high value (no crit)
    monkeypatch.setattr("random.random", lambda: 0.99)
    dmg = cs._player_damage_vs_burning(proj, enemy, proj.damage)
    assert dmg == 10


def test_crit_shows_only_one_floating_text(monkeypatch):
    # create a simple collision scenario where a player projectile hits an enemy
    import pygame

    g = Game()

    # position enemy in field
    class DummyEnemy(pygame.sprite.Sprite):
        def __init__(self):
            super().__init__()
            self.x = 100
            self.y = 100
            self.health = 100
            self.max_health = 100
            self.enemy_type = "normal"
            self.rect = pygame.Rect(self.x - 10, self.y - 10, 20, 20)

        def take_damage(self, damage, *, show_floating=True):
            try:
                self.health -= damage
            except Exception:
                pass

    class DummyProj(pygame.sprite.Sprite):
        def __init__(self):
            super().__init__()
            self.x = 100
            self.y = 100
            self.radius = 5
            self.damage = 10
            self.is_enemy_projectile = False
            self.source = None
            self.rect = pygame.Rect(self.x - 2, self.y - 2, 4, 4)

    enemy = DummyEnemy()
    proj = DummyProj()
    g.enemies = pygame.sprite.Group()
    g.enemies.add(enemy)
    g.projectiles = pygame.sprite.Group()
    g.projectiles.add(proj)

    # ensure crit occurs
    g.permanent_stats["adrenaline"] = 1
    g.permanent_stats["blasphemy_6"] = 0
    monkeypatch.setattr("random.random", lambda: 0.0)

    g.collision_system.handle_collisions()
    # only one floating text should be added, colored non-white
    assert len(g.floating_texts) == 1
    ft = g.floating_texts[0]
    assert ft.color != (255, 255, 255)
    # crited projectile base damage was 10; 50% extra means 15 displayed
    assert ft.text == "15"
    # enemy health should have dropped appropriately
    assert enemy.health == 100 - 15


def test_crit_shows_only_one_floating_text_plain_list_branch(monkeypatch):
    # simulate situation where spatial grid hit detection fails so the
    # fallback plain-list branch is used; this exercised the sections around
    # lines 2100/2350 in collision_system.
    import pygame

    g = Game()
    # simulate spatial grid failure by clearing it; helper will fall back to spritecollide
    g.spatial_grid = None

    class DummyEnemy(pygame.sprite.Sprite):
        def __init__(self):
            super().__init__()
            self.x = 100
            self.y = 100
            self.health = 100
            self.max_health = 100
            self.enemy_type = "normal"
            self.rect = pygame.Rect(self.x - 10, self.y - 10, 20, 20)

        def take_damage(self, damage, *, show_floating=True):
            try:
                self.health -= damage
            except Exception:
                pass

    class DummyProj(pygame.sprite.Sprite):
        def __init__(self):
            super().__init__()
            self.x = 100
            self.y = 100
            self.radius = 5
            self.damage = 10
            self.is_enemy_projectile = False
            self.source = None
            self.rect = pygame.Rect(self.x - 2, self.y - 2, 4, 4)

    enemy = DummyEnemy()
    proj = DummyProj()
    g.enemies = pygame.sprite.Group()
    g.enemies.add(enemy)
    g.projectiles = pygame.sprite.Group()
    g.projectiles.add(proj)

    # ensure crit occurs
    g.permanent_stats["adrenaline"] = 1
    g.permanent_stats["blasphemy_6"] = 0
    monkeypatch.setattr("random.random", lambda: 0.0)

    g.collision_system.handle_collisions()
    assert len(g.floating_texts) == 1
    ft = g.floating_texts[0]
    assert ft.color != (255, 255, 255)
    assert ft.text == "15"
    assert enemy.health == 100 - 15


def test_structure_reduces_damage_and_grants_xp_bonus_on_kill():
    import pygame

    g = Game()
    # give one point of structure (3% dmg reduction + 3% XP)
    # ensure blasphemy_4 and blasphemy_3 do not affect this test
    g.permanent_stats["blasphemy_4"] = 0
    g.permanent_stats["blasphemy_3"] = 0
    g.permanent_stats["structure"] = 1
    g.reset_game()

    # Player damage reduction multiplier should reflect -3% per level
    assert g.damage_reduction_multiplier == pytest.approx(1.0 - 0.03)
    assert g.player.damage_reduction_multiplier == pytest.approx(1.0 - 0.03)

    # Create a dummy enemy sprite that is already dead so update_game awards XP
    class DummyEnemy(pygame.sprite.Sprite):
        def __init__(self):
            super().__init__()
            self.health = 0
            self.max_health = 10
            self.enemy_type = "strong"  # base XP = 25
            # provide a rect so pygame.sprite functions don't crash; place off-player
            self.rect = pygame.Rect(0, 0, 8, 8)

        def kill(self):
            pass

    g.enemies = pygame.sprite.Group()
    e = DummyEnemy()
    g.enemies.add(e)

    # Run one update; enemy is dead and should award XP with multiplier
    g.update_game()

    # base XP for 'strong' = 25; with structure level 1 -> 25 * 1.03 = 25.75 -> rounded => 26
    assert g.player_xp == 26
