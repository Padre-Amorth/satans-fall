from __future__ import annotations

from src.game import Game


def _contains_projectile_size(choices: list[dict]) -> bool:
    return any(c.get("id") == "projectile_size" for c in choices)


def test_projectile_size_not_offered_in_early_stages():
    """Projectile Size should NOT be offered in Prologo, Limbo, or Purgatory."""
    for stage in ["prologo", "limbo", "purgatory"]:
        g = Game()
        g.selected_stage = stage

        # Should never include projectile_size in these stages
        for _ in range(10):
            choices = g.generate_upgrade_choices()
            assert not _contains_projectile_size(
                choices
            ), f"projectile_size should not be in {stage}"


def test_projectile_size_available_in_hell():
    """Projectile Size should be available in Hell stage."""
    g = Game()
    g.selected_stage = "hell"

    found = False
    # Try several times to account for randomness; projectile_size should
    # appear at least once across multiple draws when allowed.
    for _ in range(40):
        choices = g.generate_upgrade_choices()
        if _contains_projectile_size(choices):
            found = True
            break
    assert found, "projectile_size upgrade should be available in Hell"
