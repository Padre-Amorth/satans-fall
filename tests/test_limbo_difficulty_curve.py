#!/usr/bin/env python3
"""Ensure the difficulty slope is reduced on limbo stages only."""

from src.balance import (
    DIFFICULTY_MULTIPLIER_PER_WAVE,
    LIMBO_DIFFICULTY_MULTIPLIER_PER_WAVE,
)
from src.game import Game


def test_limbolike_stages_use_lower_slope():
    g = Game()
    # default (no stage) should use global
    assert g.get_difficulty_multiplier_per_wave() == DIFFICULTY_MULTIPLIER_PER_WAVE
    for stage in ("limbo", "limbo_2", "limbo_3"):
        g.selected_stage = stage
        assert (
            g.get_difficulty_multiplier_per_wave()
            == LIMBO_DIFFICULTY_MULTIPLIER_PER_WAVE
        )
    # other arbitrary stage shouldn't change
    g.selected_stage = "purgatory"
    assert g.get_difficulty_multiplier_per_wave() == DIFFICULTY_MULTIPLIER_PER_WAVE
