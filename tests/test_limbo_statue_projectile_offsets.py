import pygame

from src.core.entities.tower import Tower
from src.game import Game
from tests.test_tower import DummyEnemy


def _assert_offsets_for_stage(stage_name: str, expected_x_offset: int) -> None:
    """Helper to spawn a single statue shot on both sides and verify offsets.

    * ``stage_name`` is the stage passed to ``Game.select_stage``.
    * ``expected_x_offset`` is the number of pixels projectiles should move
      toward the centre from their origin (applied left/right depending on
      firing side).  The vertical offset is assumed to be constant (10px).
    """
    pygame.init()
    g = Game()
    g.select_stage(stage_name)

    g.left_tower = Tower(320, 530, projectile_speed=100.0, inaccuracy=0.0)
    g.right_tower = Tower(960, 530, projectile_speed=100.0, inaccuracy=0.0)
    g.enemies = [DummyEnemy(400, 530)]

    g.statue_cooldown = 0
    g.statue_next_left = True

    from src.systems.weapon_system import WeaponSystem

    ws = WeaponSystem(g)
    ws.update_statue_weapons()

    projs = []
    try:
        projs = list(g.projectiles)
    except Exception:
        projs = g.projectiles
    assert projs, "Expected at least one projectile spawned"

    p = projs[0]
    assert (
        int(p.x) == 320 + expected_x_offset
    ), f"{stage_name} left projectile x offset wrong: {p.x}"
    assert int(p.y) == 530 + 10, f"{stage_name} left projectile y offset wrong: {p.y}"

    # now fire right side
    g.statue_cooldown = 0
    g.statue_next_left = False
    try:
        g.projectiles.empty()
    except Exception:
        g.projectiles.clear()
    ws.update_statue_weapons()
    projs = (
        list(g.projectiles)
        if hasattr(g.projectiles, "sprites")
        else list(g.projectiles)
    )
    assert projs, "Expected a second projectile spawned"
    p2 = projs[0]
    assert (
        int(p2.x) == 960 - expected_x_offset
    ), f"{stage_name} right projectile x offset wrong: {p2.x}"
    assert (
        int(p2.y) == 530 + 10
    ), f"{stage_name} right projectile y offset wrong: {p2.y}"


def test_statue_projectile_offsets():
    # verify all stages that use statues/towers
    _assert_offsets_for_stage("limbo", 50)
    _assert_offsets_for_stage("limbo_2", 50)
    _assert_offsets_for_stage("limbo_3", 50)
    # limbo_final uses dynamic towers so offset is irrelevant, but should
    # still match the limbo constant when they do fire
    # limbo_final has no firing until tower choice, so skip it here
    _assert_offsets_for_stage("purgatory", 10)
    _assert_offsets_for_stage("hell", 10)


def test_no_statues_fire_during_limbo_final_choice():
    """When awaiting tower choice in limbo_final, no projectiles should spawn."""
    pygame.init()
    g = Game(debug=True)
    from src.systems.input_handler import InputHandler

    InputHandler(g).select_stage("limbo_final")
    assert g.awaiting_tower_choice
    g.enemies = [type("E", (), {"x": 400, "y": 300})()]
    g.statue_cooldown = 0
    g.statue_next_left = True
    g.projectiles.empty()
    g.update_statue_weapons()
    # still empty
    assert len(list(g.projectiles)) == 0


def test_limbo_final_outward_offset():
    """After tower choice, limbo_final projectiles should spawn 20px further
    from centre than regular limbo (i.e. use 30px offset)."""
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "limbo_final"
    # simulate tower choice complete
    g.awaiting_tower_choice = False
    g.left_tower = Tower(320, 530, projectile_speed=100.0, inaccuracy=0.0)
    g.right_tower = Tower(960, 530, projectile_speed=100.0, inaccuracy=0.0)
    g.enemies = [DummyEnemy(400, 530)]
    g.statue_cooldown = 0
    g.statue_next_left = True
    g.projectiles.empty()
    g.update_statue_weapons()
    projs = list(g.projectiles)
    assert len(projs) >= 1
    # first shot should be from left tower with 15px inward offset
    assert int(projs[0].x) == 320 + 15, f"Expected x 335, got {projs[0].x}"
    # fire again for right tower
    g.statue_cooldown = 0
    g.statue_next_left = False
    g.projectiles.empty()
    g.update_statue_weapons()
    projs = list(g.projectiles)
    assert int(projs[0].x) == 960 - 15, f"Expected x 945, got {projs[0].x}"


def test_towers_always_on_top_of_specials():
    """Towers/statues should render after the special-effects layer in any
    stage where they appear.

    This covers both Limbo pedestals and Purgatory/Hell dynamic models. The
    drawing order is validated by stubbing the relevant methods and capturing
    the sequence of calls.
    """
    pygame.init()
    for stage in ("limbo", "limbo_final", "purgatory", "hell"):
        # limbo_final intentionally never draws a statue layer
        g = Game()
        g.select_stage(stage)
        log: list[str] = []

        # stub special effects always; pedestal stubbing only for non-final
        orig_special = g.ui.draw_special_effects

        def _log_special(shake_x=0, shake_y=0):
            log.append("special")

        g.ui.draw_special_effects = _log_special
        if stage != "limbo_final":
            orig_ped = g.ui.draw_pedestals

            def _log_pedestals(shake_x=0, shake_y=0):
                log.append("statue")

            g.ui.draw_pedestals = _log_pedestals
        else:
            orig_ped = None

        # make sure at least one tower/statue gets drawn; left_tower is enough
        from src.core.entities.tower import Tower

        g.left_tower = Tower(0, 0, projectile_speed=1.0, inaccuracy=0.0)
        g.left_tower.visible = True
        if stage == "limbo":
            # pedestals path is taken automatically
            pass
        else:
            g.right_tower = Tower(0, 0, projectile_speed=1.0, inaccuracy=0.0)
            g.right_tower.visible = True

        # invoke drawing
        g.ui.draw_game_objects()

        # restore
        g.ui.draw_special_effects = orig_special
        if orig_ped is not None:
            g.ui.draw_pedestals = orig_ped

        # statue/tower should be last call for regular stages; limbo_final
        # doesn't draw a statue so there may be no arrival log.
        if stage == "limbo_final":
            assert "statue" not in log, f"Unexpected statue call in {stage}: {log}"
        else:
            assert log and log[-1] == "statue", f"{stage} order wrong: {log}"


def test_limbs_statue_above_projectiles():
    """Ensure statues render after both projectiles and special effects.

    Previously the limbo pedestal call happened immediately after projectiles,
    meaning later effects such as hellectric beams could overdraw the statue.
    We intercept calls to the projectile layer, the special-effects layer, and
    the pedestal renderer to log the order and assert the statue comes last.
    """
    pygame.init()
    g = Game()
    g.select_stage("limbo")

    # create a dummy projectile with a logging draw method
    log: list[str] = []

    class DummyProj:
        def draw(self, surf, sx, sy):
            log.append("projectile")

    # patch draw_special_effects and draw_pedestals to log their invocations
    orig_special = g.ui.draw_special_effects
    orig_ped = g.ui.draw_pedestals

    def _log_special(shake_x=0, shake_y=0):
        log.append("special")

    def _log_pedestals(shake_x=0, shake_y=0):
        log.append("statue")

    g.ui.draw_special_effects = _log_special
    g.ui.draw_pedestals = _log_pedestals

    # use lists so we can bypass pygame Group behavior
    g.projectiles = [DummyProj()]
    g.enemy_projectiles = []

    # run the drawing routine
    g.ui.draw_game_objects()

    # restore original implementations
    g.ui.draw_special_effects = orig_special
    g.ui.draw_pedestals = orig_ped

    assert log == [
        "projectile",
        "special",
        "statue",
    ], f"Statue should be drawn last, got order {log}"
