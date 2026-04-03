from src.game import Game
from src.ui import PygameUIManager


def test_fog_spawn_no_longer_produces_particles():
    """The legacy purgatory fog particle helpers are now inert.

    Calling ``_spawn_purgatory_fog_particles`` should never populate the
    internal list, and ``_update_and_draw_purgatory_fog_particles`` should
    handle an empty collection without raising.
    """
    g = Game(debug=True)
    ui = PygameUIManager(g)

    # provide wall points so the old logic would attempt generation
    g.left_wall_points = [(280, 0), (400, 720)]
    g.right_wall_points = [(1000, 0), (880, 720)]
    g.selected_stage = "purgatory_2"

    ui._purgatory_fog_particles.clear()
    for _ in range(10):
        ui._spawn_purgatory_fog_particles()
        assert (
            ui._purgatory_fog_particles == []
        ), "spawn helper should not emit particles"

    # update/draw should simply return without error
    ui._update_and_draw_purgatory_fog_particles()
