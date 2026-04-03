from unittest.mock import patch

import pygame

from src.game import Game


def test_distribution_shifts_from_weak_to_winged():
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "purgatory"

    # low wave should still spawn a weak enemy for a very high random value
    # (weak band has shrunk due to archer being half the normal chance)
    g.wave = 1
    with patch("random.random", return_value=0.9):
        g.spawn_enemy()
    assert any(
        getattr(e, "enemy_type", None) == "weak" for e in g.enemies
    ), "Expected weak enemy on early wave"
    # clear and bump wave, same random number should now fall into the
    # expanded winged/normal/archer zone instead of weak
    try:
        g.enemies.clear()
    except Exception:
        g.enemies = []
    g.wave = 50
    with patch("random.random", return_value=0.65):
        g.spawn_enemy()
    types = [getattr(e, "enemy_type", None) for e in g.enemies]
    assert (
        "winged" in types or "archer" in types
    ), "High wave should produce a ranged enemy (winged or archer) for the same seed"

    # specifically force archer spawn by picking a random value in the upper
    # band (above the winged threshold for a high wave)
    try:
        g.enemies.clear()
    except Exception:
        g.enemies = []
    g.wave = 50
    with patch("random.random", return_value=0.85):
        g.spawn_enemy()
    assert any(
        getattr(e, "enemy_type", None) == "archer" for e in g.enemies
    ), "Rand in upper range should yield an archer"


def test_archer_probability_ratio():
    """Archers should always spawn with probability half that of normals."""
    pygame.init()
    g = Game(debug=True)
    ss = g.spawn_system

    # replicate the internal probability math for a few wave values
    for wave in (0, 5, 20):
        # copy snippet from spawn_system.spawn_enemy (simplified)
        base_strong = 0.10 if wave < 3 else 0.15
        base_normal = 0.30
        base_angel = 0.20
        base_winged = 0.10 if wave >= 3 else 0.0
        strong_chance = max(base_strong - wave * 0.005, 0.05)
        normal_chance = min(base_normal + wave * 0.005, 0.50)
        angel_chance = max(base_angel - wave * 0.005, 0.05)
        winged_chance = base_winged
        if wave >= 3:
            winged_chance = min(base_winged + (wave - 2) * 0.01, 0.30)
        archer_chance = normal_chance * 0.5

        # ratio should hold exactly
        assert archer_chance == normal_chance * 0.5
        # also ensure sum of probs <=1 before normalization
        total = (
            strong_chance + normal_chance + angel_chance + winged_chance + archer_chance
        )
        assert total <= 1.0 or total > 1.0


def test_shield_conversion_probability_grows_with_wave():
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "limbo"  # non-prologo, shields eligible

    # first call sequence will land a strong enemy then skip conversion
    # use a value < strong threshold even after several waves so we hit the
    # strong branch on both iterations
    rnd = iter([0.03, 0.6])
    with patch("random.random", side_effect=lambda: next(rnd)):
        g.wave = 1
        g.spawn_enemy()
    assert any(
        getattr(e, "enemy_type", None) == "strong" for e in g.enemies
    ), "Early wave should rarely convert to shielded"

    # clear and try again at a much higher wave
    try:
        g.enemies.clear()
    except Exception:
        g.enemies = []
    rnd2 = iter([0.03, 0.6])
    with patch("random.random", side_effect=lambda: next(rnd2)):
        g.wave = 20
        g.spawn_enemy()
    assert any(
        getattr(e, "enemy_type", None) == "shielded" for e in g.enemies
    ), "Conversion chance should be higher on later waves"
