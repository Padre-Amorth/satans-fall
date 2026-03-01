#!/usr/bin/env python3
"""Unit tests covering meta-experience and point progression behavior."""

import pytest

from src.balance import META_XP_BASE, META_XP_GROWTH
from src.game import Game


def test_meta_xp_thresholds():
    g = Game()
    # start fresh
    g.global_progress["meta_level"] = 1
    # level1 threshold
    assert g.get_meta_xp_to_next_level() == int(META_XP_BASE * (META_XP_GROWTH**0))
    g.global_progress["meta_level"] = 2
    # threshold should have grown by factor META_XP_GROWTH (currently 1.1)
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
    # With 10,000 XP per level (new base), 1,000,000 score should level up the meta progression
    assert g.global_progress["meta_level"] > 1


def test_score_multiplier_removed_attribute():
    g = Game()
    g.score = 0
    g.global_progress["meta_xp"] = 0
    # accessing or assigning score_multiplier should raise
    with pytest.raises(AttributeError):
        _ = g.score_multiplier
    with pytest.raises(AttributeError):
        g.score_multiplier = 5.0
    # add_score still works normally
    g.add_score(10)
    assert g.score == 10
    assert g.global_progress["meta_xp"] == 10


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


def test_award_stage_clear_once():
    """award_stage_clear grants a one-time reward; repeated calls are no-ops."""
    g = Game()
    # Reset stages so the test is independent of any existing save file
    g.global_progress["stages_cleared"] = {}
    initial_points = g.global_progress.get("meta_points", 0)

    assert g.award_stage_clear("prologo")
    assert g.global_progress.get("meta_points", 0) == initial_points + 1
    # calling again should not grant another reward
    assert not g.award_stage_clear("prologo")
    assert g.global_progress.get("meta_points", 0) == initial_points + 1


def test_prologo_defeat_grants_meta_reward():
    """Defeating Prologo should ultimately grant a stage-clear reward.

    The game no longer awards this automatically, so this test exercises the
    underlying ``award_stage_clear`` call and then ensures that ``prologo_defeat``
    doesn't accidentally change meta progress itself.
    """
    g = Game()
    # Reset to clean state (independent of any save file)
    g.global_progress["meta_xp"] = 0
    g.global_progress["meta_points"] = 0
    g.global_progress["stages_cleared"] = {}
    # manually award the stage clear as the real game logic would
    assert g.award_stage_clear("prologo")
    assert g.global_progress.get("meta_points", 0) == 1
    assert g.global_progress.get("meta_xp", 0) > 0
    # calling the helper again should not double-dip
    old_xp = g.global_progress.get("meta_xp", 0)
    assert not g.award_stage_clear("prologo")
    assert g.global_progress.get("meta_xp", 0) == old_xp
    # invoking the defeat screen afterwards has no side-effects on progress
    g.prologo_defeat()
    assert g.global_progress.get("meta_points", 0) == 1
    assert g.global_progress.get("meta_xp", 0) == old_xp


def test_limbo_final_defeat_grants_meta_reward():
    g = Game()
    g.global_progress["meta_xp"] = 0
    g.global_progress["meta_points"] = 0
    g.global_progress["stages_cleared"] = {}
    g.limbo_final_defeat()
    assert g.global_progress.get("meta_points", 0) == 1
    assert g.global_progress.get("meta_xp", 0) > 0
    old_xp = g.global_progress.get("meta_xp", 0)
    g.limbo_final_defeat()
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
    # use META_XP_BASE constant so tests stay valid when thresholds change
    assert ui._calculate_meta_xp_fill(0, META_XP_BASE, 100) == 0
    assert ui._calculate_meta_xp_fill(1, META_XP_BASE, 100) == 1
    # large XP should saturate (200% of base)
    assert ui._calculate_meta_xp_fill(META_XP_BASE * 2, META_XP_BASE, 100) == 100


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


def test_meta_xp_not_reloaded_during_gameplay():
    """Verify that handle_events never resets meta_xp during active gameplay.

    XP earned within a session must survive event-loop iterations.
    """
    import pygame

    g = Game()
    # Start from a known baseline
    g.global_progress["meta_xp"] = 0

    # Award some XP
    g.award_meta_xp(50)
    assert g.global_progress["meta_xp"] == 50

    # simulate a frame; handle_events must not reset anything
    pygame.init()
    g.input_handler.handle_events()
    assert g.global_progress["meta_xp"] == 50


def test_meta_xp_accumulates_within_session():
    """meta_xp accumulates across award calls within a single session."""
    g1 = Game()
    g1.global_progress["meta_xp"] = 0

    for _ in range(10):
        g1.award_meta_xp(5)
    assert g1.global_progress["meta_xp"] == 50

    # game_over / reset does not wipe meta progress
    g1.game_over()
    assert g1.global_progress["meta_xp"] == 50

    # additional XP continues accumulating
    for _ in range(5):
        g1.award_meta_xp(5)
    assert g1.global_progress["meta_xp"] == 75


def test_handle_events_does_not_overwrite_meta_xp():
    """handle_events must never reset meta_xp earned within the session.

    XP set manually (or earned via award_meta_xp) should survive multiple
    event-loop iterations without being overwritten.
    """
    import pygame

    g = Game()
    g.global_progress["meta_xp"] = 0

    g.award_meta_xp(100)
    assert g.global_progress["meta_xp"] == 100

    # simulate frames; value must not be overwritten
    pygame.init()
    for _ in range(5):
        g.input_handler.handle_events()
    assert g.global_progress["meta_xp"] == 100
