from src.game import Game


def test_game_initialization_has_basic_state():
    g = Game(debug=True)

    required_attrs = [
        "stage_start_countdown",
        "stage_start_timer",
        "showing_stage_menu",
        "showing_game_over",
        "game_over_alpha",
        "game_over_fade_duration_ms",
        "game_over_fade_speed",
        "burst_fire_rate",
        "burst_cooldown",
        "burst_max",
        "burst_pause",
        "burst_count",
        "hellgun_cooldown_timer",
        "spear_cooldown_timer",
        "soul_drain_cooldown_timer",
        "fire_rate_multiplier",
        "orbital_count",
        "orbitals",
        "shake_timer",
        "shake_intensity",
        "projectile_manager",
        "player_weapons",
    ]

    for attr in required_attrs:
        assert hasattr(g, attr), f"Game missing attribute: {attr}"

    assert isinstance(g.orbitals, list)
    assert isinstance(g.player_weapons, list)
    assert g.game_over_fade_speed > 0


def test_weapon_cooldown_defaults_are_sane():
    g = Game(debug=True)
    assert g.hellgun_cooldown_timer == 0
    assert g.spear_cooldown_timer == 0
    assert g.soul_drain_cooldown_timer == 0
    assert isinstance(g.burst_fire_rate, int)
    assert g.burst_fire_rate > 0


def test_update_does_not_raise_on_initial_state():
    g = Game(debug=True)
    # calling update on a freshly constructed Game should not raise
    g.update()
