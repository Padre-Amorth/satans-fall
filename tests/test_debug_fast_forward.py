import pygame

from src.game import Game


def test_fast_forward_limbo_final_flag_spawns_boss():
    pygame.init()
    g = Game(debug=True, fast_forward_limbo_final=True)
    # selecting the stage should auto-fast-forward
    g.select_stage("limbo_final")
    # after selection the time should be at or past 165; boss not yet spawned
    assert g.time_elapsed >= 165
    # nothing should have spawned yet – neither the final boss nor the horde boss
    assert not any(b.enemy_type in ("boss_limbo", "boss_limbo_horde") for b in g.bosses)


def test_fast_forward_prologo_flag_still_works():
    pygame.init()
    g = Game(debug=True, fast_forward_prologo=True)
    g.select_stage("prologo")
    assert g.time_elapsed >= 236
    assert any(b.enemy_type == "boss_final" for b in g.bosses)


def test_current_game_global_is_consistent():
    pygame.init()
    g = Game(debug=True)
    # ensure both module paths point to the same object
    from src.game import CURRENT_GAME as pkg_cg
    from src.game.core import CURRENT_GAME as core_cg

    assert pkg_cg is core_cg is g
