import pytest

from src.game import Game


def _has_tower_fr(choices: list[dict]) -> bool:
    return any(c.get("id") == "tower_fire_rate" for c in choices)


def test_tower_fire_rate_only_from_purgatory_and_hell():
    g = Game()

    # Prologo and Limbo should NOT offer this upgrade
    for stage in ("prologo", "limbo"):
        g.selected_stage = stage
        for _ in range(20):
            choices = g.generate_upgrade_choices()
            assert not _has_tower_fr(choices)

    # Purgatory and Hell should be able to offer it (try multiple draws)
    for stage in ("purgatory", "hell"):
        g.selected_stage = stage
        found = False
        for _ in range(60):
            choices = g.generate_upgrade_choices()
            if _has_tower_fr(choices):
                found = True
                break
        assert found, f"tower_fire_rate not found in stage {stage} after many draws"


def test_tower_fire_rate_apply_updates_towers_and_multiplier():
    g = Game(debug=True)
    g.selected_stage = "purgatory"

    # Ensure towers exist and record their base cooldowns
    left = getattr(g, "left_tower", None)
    right = getattr(g, "right_tower", None)
    assert left is not None and right is not None
    base_left = getattr(left, "_base_fire_rate", left.fire_rate)
    base_right = getattr(right, "_base_fire_rate", right.fire_rate)

    # Force an upgrade choice that applies tower fire rate
    choices = g.generate_upgrade_choices()
    # If not present, inject and apply directly for deterministic test
    tf_choice = next((c for c in choices if c.get("id") == "tower_fire_rate"), None)
    if tf_choice is None:
        # Create a direct choice dict matching generator format
        tf_choice = {
            "id": "tower_fire_rate",
            "name": "Tower Fire Rate +10%",
            "description": "Increase firing speed of towers",
            "apply": lambda: None,
        }
        # Apply manually by calling the Game logic for the upgrade (simulate apply)
        # but prefer to use g.apply_upgrade when possible.
        # We'll call the same apply function used by generator to ensure behavior.
        # So find generator-produced apply by generating until it appears.
        found = False
        for _ in range(200):
            cs = g.generate_upgrade_choices()
            for c in cs:
                if c.get("id") == "tower_fire_rate":
                    tf_choice = c
                    found = True
                    break
            if found:
                break
        assert found, "Could not obtain tower_fire_rate upgrade from generator"

    before_mult = getattr(
        g, "tower_fire_rate_multiplier", {"fire": 1.0, "storm": 1.0, "ice": 1.0}
    ).copy()
    # Apply upgrade via game helper
    g.apply_upgrade(tf_choice)

    # Multipliers for each tower type should have increased by ~10%
    for k, v in before_mult.items():
        assert (
            pytest.approx(
                getattr(g, "tower_fire_rate_multiplier", {}).get(k, 1.0), rel=1e-5
            )
            == v * 1.1
        )

    # Towers' effective cooldowns (fire_rate) should be recomputed from their _base_fire_rate
    assert left.fire_rate == max(
        1, int(round(base_left / g.tower_fire_rate_multiplier["fire"]))
    )
    assert right.fire_rate == max(
        1, int(round(base_right / g.tower_fire_rate_multiplier["fire"]))
    )
