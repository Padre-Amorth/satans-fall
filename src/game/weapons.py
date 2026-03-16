"""Weapon state initialization and helpers."""

from typing import Any, Dict, List

from src.balance import (
    BURST_FIRE_RATE,
    BURST_MAX,
    BURST_PAUSE,
    MAX_EXTRA_WEAPONS,
)


def init_weapons(game: Any) -> None:
    """Initialize weapon-related state on Game instance."""
    game.weapon_levels: Dict[str, int] = {}
    game.burst_fire_rate = BURST_FIRE_RATE
    game.burst_cooldown = 0
    game.burst_max = BURST_MAX
    game.burst_pause = BURST_PAUSE
    game.burst_count = 0
    game.fire_rate_multiplier = 1.0
    game.hellgun_cooldown_timer = 0
    game.spear_cooldown_timer = 0
    game.DemonStrike_cooldown_timer = 0
    game.flies_cooldown_timer = 0
    game.skullboom_cooldown_timer = 0
    game.tenebrae_cooldown_timer = 0
    # SkullBoom particles and explosion effects
    game.skullboom_particles: List[Any] = []
    game.skullboom_explosions: List[Dict[str, Any]] = []
    # Special-case particles for blasphemy_5 revive explosion (red)
    game.blasphemy5_particles: List[Any] = []
    # Ice particles for explosions
    game.ice_particles: List[Any] = []
    # Ice puddles for slowing enemies
    game.ice_puddles: List[Dict[str, Any]] = []
    # Hell stage ambient burn fires (sustained burn effects with particles)
    game.hell_burn_fires: List[Dict[str, Any]] = []
    # Orbital defaults
    game.orbital_count = 3
    game.orbitals: List[Dict[str, Any]] = []


def init_player_weapons(game: Any) -> None:
    """Initialize player weapon choice and progression state (called from _init_player)."""
    game.awaiting_weapon_choice = False
    game.weapon_choices: List[Dict[str, Any]] = []
    game.selected_weapon_index = 0
    game.is_initial_weapon_choice = False
    game.player_weapons = []
    game._max_extra_weapons = MAX_EXTRA_WEAPONS
    game.weapon_levels = {}
