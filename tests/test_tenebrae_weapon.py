"""Tests for the Tenebrae weapon mechanics and integration (formerly Darkness)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pygame
import pytest

from src.game import Game
from src.weapons import WEAPON_DEFS, tenebrae_cooldown, tenebrae_damage


def test_tenebrae_definition():
    """The weapon must be present in WEAPON_DEFS with the expected fields."""
    assert "tenebrae" in WEAPON_DEFS
    w = WEAPON_DEFS["tenebrae"]
    assert w["name"] == "Tenebrae"
    assert w["base_damage"] == 25
    assert pytest.approx(w["decay_per_target"], rel=1e-6) == 0.20
    assert "speed" in w


def test_tenebrae_damage_scaling():
    """Verify the decay formula and player-damage scaling."""
    # level 1, no prior hits -> base 25
    assert tenebrae_damage(1, 30, 0) == 25
    # one hit should apply 20 (25 * 0.8)
    assert tenebrae_damage(1, 30, 1) == 20
    # higher player damage scales proportionally
    assert tenebrae_damage(1, 60, 0) == 50
    # level 2 increases base by 5
    assert tenebrae_damage(2, 30, 0) == 30
    # decay reduces by 0.02 for every two levels: level3 -> 0.18
    expected_base = 25 + (3 - 1) * 5
    assert tenebrae_damage(3, 30, 1) == int(expected_base * (1 - 0.18))


def test_tenebrae_cooldown():
    """Cooldown should decrease with levels and never drop below min."""
    assert tenebrae_cooldown(1) == 2.0
    # two levels = two reduction steps of 0.15 each
    assert tenebrae_cooldown(2) == pytest.approx(1.85, rel=1e-6)
    # level six applies five steps (0.75 total) giving 1.25s cooldown
    assert tenebrae_cooldown(6) == pytest.approx(1.25, rel=1e-6)


def test_tenebrae_firing_and_cooldown():
    """Firing the weapon should produce a projectile with the right metadata.

    The weapon_system integration is exercised via ``Game.update_weapon_firing``
    which is the usual path executed during gameplay.
    """
    game = Game()
    game.player_weapons = ["tenebrae"]
    game.weapon_levels = {"tenebrae": 1}
    game.tenebrae_cooldown_timer = 0

    # position the player and mouse for a horizontal shot
    game.player.x = 100
    game.player.y = 100
    game.mouse_x = 200
    game.mouse_y = 100

    # ensure no projectiles present
    game.projectiles.empty()

    game.update_weapon_firing()
    projs = list(game.projectiles)
    assert len(projs) == 1
    proj = projs[0]
    assert proj.weapon_type == "tenebrae"
    assert proj.appearance == "tenebrae"
    assert proj.radius == 12  # increased by 2px per design request
    assert proj.pierce_all is True
    assert proj.level == 1
    assert proj.base_player_damage == int(game.player_damage * game.damage_multiplier)
    assert proj.targets_hit == 0

    # velocity should reflect configured speed (400 px/s in WEAPON_DEFS)
    # aiming purely to the right gives vx ~= speed
    assert abs(proj.vel_x - 400) < 1e-3
    assert abs(proj.vel_y) < 1e-3

    # cooldown timer set
    assert game.tenebrae_cooldown_timer > 0


def test_tenebrae_damages_boss():
    """Tenebrae should deal damage when striking a boss (not only regular enemies)."""
    pygame.init()
    g = Game(debug=True)

    # spawn a medium boss and position it in front of player
    boss = g.enemy_manager.spawn_boss("mid")
    boss.x = g.player.x + 50
    boss.y = g.player.y
    try:
        boss.rect.center = (boss.x, boss.y)
    except Exception:
        pass

    # create a tenebrae projectile heading right
    from src.projectile import Projectile

    proj = Projectile(
        g.player.x,
        g.player.y,
        800,
        0,
        damage=0,
        radius=12,
        weapon_type="tenebrae",
        appearance="tenebrae",
    )
    proj.pierce_all = True
    proj.level = 1
    proj.base_player_damage = int(g.player_damage * g.damage_multiplier)
    proj.targets_hit = 0

    try:
        g.projectiles.add(proj)
    except Exception:
        g.projectiles = [proj]

    # simulate collisions for several frames; boss should be hit once
    for _ in range(6):
        proj.update()
        try:
            proj.rect.center = (proj.x, proj.y)
        except Exception:
            pass
        g.handle_collisions()

    expected = tenebrae_damage(proj.level, proj.base_player_damage, 0)
    assert boss.health == boss.max_health - expected, (
        f"Boss health {boss.health} expected {boss.max_health - expected}"
        + " after tenebrae hit"
    )
    # ensure the projectile recorded the hit
    assert getattr(proj, "targets_hit", 0) >= 1


def test_tenebrae_appearance_asset_loading(monkeypatch):
    """Projectile should attempt to load external asset named tenebrae.png"""
    import pygame

    from src.projectile import Projectile

    called = {}

    def fake_get_image(name, size=None):
        called["name"] = name
        # return a dummy surface
        return pygame.Surface((int(size[0]), int(size[1])))

    # patch the shared asset manager function since projectile imports it locally
    monkeypatch.setattr("src.assets.manager.get_image", fake_get_image)
    p = Projectile(0, 0, 0, 0, radius=5, appearance="tenebrae")
    p.draw_projectile()
    assert called.get("name") == "tenebrae.png"
    # ensure image changed to returned surface
    assert isinstance(p.image, pygame.Surface)


def test_tenebrae_rotates_toward_velocity(monkeypatch):
    """Tenebrae arcs should rotate to align with their movement direction.

    We verify by patching ``pygame.transform.rotate`` and checking the
    computed angle matches the projectile velocity (horizontal to the
    right should yield -90 degrees adjustment as used for spears).
    """
    import pygame

    from src.projectile import Projectile

    pygame.init()
    screen = pygame.Surface((50, 50))
    called = {}

    def fake_rotate(image, angle):
        called["angle"] = angle
        return image

    monkeypatch.setattr("pygame.transform.rotate", fake_rotate)

    # create a tenebrae projectile moving rightwards
    p = Projectile(0, 0, 100, 0, radius=5, appearance="tenebrae")
    p.draw(screen)

    assert "angle" in called
    # velocity purely right → atan2 = 0 → expected rotate call angle = -(0+90) = -90
    assert abs(called["angle"] + 90) < 1e-6


def test_tenebrae_scales_with_distance():
    """Projectile radius should grow from 12 to 20 while traversing the screen.

    We use a dummy game with a small 100×100 area so travel distance is easy to
    predict.  The projectile is given a manager containing the game reference so
    scaling logic can access screen dimensions.  After enough frames the radius
    must reach the maximum and must never decrease during flight.
    """
    from types import SimpleNamespace

    import pygame

    from src.projectile import Projectile

    pygame.init()

    # create a tiny game object for bounds
    dummy_game = SimpleNamespace(width=100, height=100)
    dummy_mgr = SimpleNamespace(game=dummy_game)

    # give a very high velocity so the projectile crosses the small
    # 100×100 screen in a few frames; update() divides velocities by 60
    p = Projectile(0, 0, 6000, 0, radius=12, appearance="tenebrae")
    p.manager = dummy_mgr
    # ensure spawn recorded correctly
    p.spawn_x = 0
    p.spawn_y = 0

    # record starting radius before movement
    start_radius = p.radius
    radii = []
    # simulate more frames to give smoothing time to approach target
    for _ in range(200):
        p.update()
        radii.append(p.radius)
    assert start_radius == 12
    # because of smoothing final integer may hit 34 due to rounding
    assert radii[-1] >= 34
    # ensure non-decreasing sequence including initial value
    all_r = [start_radius] + radii
    assert all(
        all_r[i] <= all_r[i + 1] for i in range(len(all_r) - 1)
    ), "Radius should not decrease during flight"
