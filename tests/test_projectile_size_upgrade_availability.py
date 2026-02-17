from __future__ import annotations

from src.game import Game


def _contains_projectile_size(choices: list[dict]) -> bool:
    return any(c.get("id") == "projectile_size" for c in choices)


def test_projectile_size_not_offered_in_prologo():
    g = Game()
    g.selected_stage = "prologo"

    # Single call should never include projectile_size in Prologo
    for _ in range(10):
        choices = g.generate_upgrade_choices()
        assert not _contains_projectile_size(choices)


def test_projectile_size_available_from_limbo_onwards():
    g = Game()
    g.selected_stage = "limbo"

    found = False
    # Try several times to account for randomness; projectile_size should
    # appear at least once across multiple draws when allowed.
    for _ in range(40):
        choices = g.generate_upgrade_choices()
        if _contains_projectile_size(choices):
            found = True
            break
    assert found, "projectile_size upgrade should be available in Limbo or later"
