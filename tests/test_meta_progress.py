#!/usr/bin/env python3
"""Unit tests covering meta-experience and point progression behavior."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.balance import META_XP_BASE, META_XP_GROWTH
from src.game import Game


def test_meta_xp_thresholds():
    g = Game()
    # start fresh
    g.global_progress["meta_level"] = 1
    # level1 threshold
    assert g.get_meta_xp_to_next_level() == int(META_XP_BASE * (META_XP_GROWTH**0))
    g.global_progress["meta_level"] = 2
    # threshold should have grown by factor META_XP_GROWTH
    expected = int(META_XP_BASE * (META_XP_GROWTH**1))
    assert g.get_meta_xp_to_next_level() == expected
    # manual computation for later levels
    g.global_progress["meta_level"] = 5
    expected2 = int(META_XP_BASE * (META_XP_GROWTH**4))
    assert g.get_meta_xp_to_next_level() == expected2


def test_award_meta_xp_and_points():
    g = Game()
    g.global_progress["meta_level"] = 1
    g.global_progress["meta_xp"] = 0
    g.global_progress["meta_points"] = 0
    # give XP exactly equal to threshold
    thresh = g.get_meta_xp_to_next_level()
    g.award_meta_xp(thresh)
    assert g.global_progress["meta_level"] == 2
    assert g.global_progress["meta_points"] == 1
    assert g.global_progress["meta_xp"] == 0
    # extra XP carries over; compute xp required for the next level too
    next_thresh = g.get_meta_xp_to_next_level()
    # award sufficient XP to guarantee two level-ups
    g.award_meta_xp(thresh + next_thresh)
    assert g.global_progress["meta_level"] >= 3
    # at least two points received total
    assert g.global_progress["meta_points"] >= 2


def test_score_to_meta_xp_conversion():
    g = Game()
    # Score grants meta_xp at 1:1 ratio (1 point = 1 meta_xp)
    g.score = 0
    g.global_progress["meta_xp"] = 0
    g.global_progress["meta_points"] = 0
    g.global_progress["meta_level"] = 1
    # Add 1,000,000 score should grant 1,000,000 meta_xp
    g.add_score(1_000_000)
    assert g.global_progress["meta_xp"] > 0
    # With 100,000 XP per level, 1,000,000 score should level up the meta progression
    assert g.global_progress["meta_level"] > 1


def test_meta_xp_persists_across_death():
    g = Game()
    # seed some xp and level
    g.global_progress["meta_xp"] = 42
    g.global_progress["meta_level"] = 1
    # simulate death via explicit game_over call
    g.game_over()
    assert g.showing_game_over
    # meta xp should remain unchanged
    assert g.global_progress["meta_xp"] == 42
    # resetting the run should also preserve it
    g.reset_game()
    assert g.global_progress["meta_xp"] == 42
    assert g.global_progress["meta_level"] == 1


def test_award_stage_clear_once(tmp_path):
    g = Game(permanent_stats_file=str(tmp_path / "perm_stats.json"))
    assert g.award_stage_clear("prologo")
    assert g.global_progress.get("meta_points", 0) == 1
    # second call should not give another
    assert not g.award_stage_clear("prologo")
    assert g.global_progress.get("meta_points", 0) == 1
    # persisting and reloading keeps the information
    g.save_permanent_stats()
    g2 = Game(permanent_stats_file=str(tmp_path / "perm_stats.json"))
    assert not g2.award_stage_clear("prologo")
    assert g2.global_progress.get("meta_points", 0) == 1
    # xp reward should also have been applied and persisted
    assert g2.global_progress.get("meta_xp", 0) > 0


def test_prologo_defeat_grants_meta_reward():
    g = Game()
    # ensure starting xp zero
    g.global_progress["meta_xp"] = 0
    g.global_progress["meta_points"] = 0
    # call prologo_defeat which should award stage clear once
    g.prologo_defeat()
    assert g.global_progress.get("meta_points", 0) == 1
    assert g.global_progress.get("meta_xp", 0) > 0
    # subsequent call does not award again
    old_xp = g.global_progress.get("meta_xp", 0)
    g.prologo_defeat()
    assert g.global_progress.get("meta_xp", 0) == old_xp


def test_killing_enemy_earns_meta_xp():
    g = Game()
    g.global_progress["meta_xp"] = 0
    g.global_progress["meta_points"] = 0
    g.record_enemy_kill()
    assert g.global_progress.get("meta_xp", 0) == 5
    # multiple kills accumulate
    g.record_enemy_kill()
    assert g.global_progress.get("meta_xp", 0) == 10


def test_boss_kill_awards_meta_xp_with_sprite():
    """A projectile that collides with a boss should grant meta XP.

    The projectile must provide a ``rect`` attribute so the boss branch is
    executed, mirroring normal gameplay.  Regression test for the mid-run XP
    bar not filling on boss kills.
    """
    import pygame

    g = Game()
    g.global_progress["meta_xp"] = 0

    # build a minimal boss sprite
    class Boss(pygame.sprite.Sprite):
        def __init__(self):
            super().__init__()
            self.enemy_type = "boss_medium"
            self.health = 10
            self.max_health = 10
            self.x = 100
            self.y = 100
            self.radius = 20
            # simple rect for collision tests
            self.rect = pygame.Rect(0, 0, 40, 40)

        def take_damage(self, dmg):
            self.health -= dmg

    boss = Boss()
    # ensure the boss rect is centered at its logical position for spritecollide
    boss.rect.center = (boss.x, boss.y)
    g.bosses = pygame.sprite.Group(boss)

    # projectile positioned exactly on the boss
    proj = pygame.sprite.Sprite()
    proj.x = 100
    proj.y = 100
    proj.radius = 5
    proj.damage = 20
    proj.rect = pygame.Rect(0, 0, 10, 10)
    proj.rect.center = (proj.x, proj.y)
    g.projectiles = pygame.sprite.Group(proj)
    g.width = 800
    g.height = 600

    g.handle_collisions()
    assert g.global_progress.get("meta_xp", 0) > 0


def test_boss_health_zero_awards_meta_xp_even_without_projectiles():
    """Ensure the fallback sweep grants XP for an already-dead boss.

    This simulates edge cases where boss health is manipulated directly (e.g.
    tests or exotic effects) and guarantees the progress bar still moves.
    """
    import pygame

    g = Game()
    g.global_progress["meta_xp"] = 0

    # boss with zero health from the start
    class Bizac(pygame.sprite.Sprite):
        def __init__(self):
            super().__init__()
            self.enemy_type = "boss_medium"
            self.health = 0
            self.max_health = 10
            self.x = 50
            self.y = 50
            self.radius = 20
            self.rect = pygame.Rect(0, 0, 40, 40)

        def take_damage(self, dmg):
            self.health -= dmg

    boss = Bizac()
    boss.rect.center = (boss.x, boss.y)
    g.bosses = pygame.sprite.Group(boss)
    g.handle_collisions()
    # boss started dead so meta xp should increment via fallback
    assert g.global_progress.get("meta_xp", 0) > 0


def test_meta_point_refund_and_spend():
    g = Game()
    g.global_progress["meta_points"] = 1
    g.permanent_stats["power"] = 0
    # upgrade consumes point
    g.permanent_stats["power"] = 0
    g.showing_stage_menu = False
    g.showing_permanent_upgrades = True
    left_x = g.width // 2 - 420
    pos = (left_x + 5, 140 + 5)
    g.handle_mouse_click(pos, button=1)
    assert g.global_progress.get("meta_points", 0) == 0
    # right click should refund
    g.handle_mouse_click(pos, button=3)
    assert g.global_progress.get("meta_points", 0) == 1


def test_xp_bar_fill_helper():
    """Verify that small XP yields at least one pixel and text uses the values."""
    from src.ui import PygameUIManager

    # helper only; bar width arbitrary (e.g. 100)
    ui = PygameUIManager(Game())
    assert ui._calculate_meta_xp_fill(0, 100000, 100) == 0
    assert ui._calculate_meta_xp_fill(1, 100000, 100) == 1
    # large XP should saturate
    assert ui._calculate_meta_xp_fill(200000, 100000, 100) == 100


def test_no_upgrade_without_meta_points():
    g = Game()
    # ensure permanent upgrades menu
    g.showing_stage_menu = False
    g.showing_permanent_upgrades = True
    # no available meta points
    g.global_progress["meta_points"] = 0
    left_x = g.width // 2 - 420
    pos = (left_x + 5, 140 + 5)  # power
    orig = g.permanent_stats.get("power", 0)
    g.handle_mouse_click(pos, button=1)
    assert g.permanent_stats.get("power", 0) == orig
    assert g.global_progress.get("meta_points", 0) == 0
