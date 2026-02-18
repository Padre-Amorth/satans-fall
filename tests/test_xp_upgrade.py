import pytest

from src.game import Game


def _has_xp(choices: list[dict]) -> bool:
    return any(c.get("id") == "xp" for c in choices)


def test_xp_upgrade_available_in_all_stages():
    g = Game()

    # Ensure XP upgrade can appear in Prologo, Limbo, and Purgatory (available in every stage)
    stages = ["prologo", "limbo", "purgatory"]
    for stage in stages:
        g.selected_stage = stage
        found = False
        for _ in range(60):
            choices = g.generate_upgrade_choices()
            if _has_xp(choices):
                found = True
                break
        assert found, f"XP upgrade not found in stage {stage} after multiple draws"


def test_xp_upgrade_apply_increases_xp_multiplier():
    g = Game()
    g.selected_stage = "limbo"

    # Keep drawing until XP upgrade appears
    xp_choice = None
    for _ in range(200):
        choices = g.generate_upgrade_choices()
        for c in choices:
            if c.get("id") == "xp":
                xp_choice = c
                break
        if xp_choice:
            break

    assert xp_choice is not None, "Could not find xp upgrade in many draws"

    before = getattr(g, "xp_multiplier", 1.0)
    # Apply the upgrade (use the game's apply mechanism if present)
    g.apply_upgrade(xp_choice)
    after = getattr(g, "xp_multiplier", 1.0)

    assert after == pytest.approx(before * 1.1)
