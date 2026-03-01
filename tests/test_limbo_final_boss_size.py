import pygame

from src.game import Game


def test_limbo_final_boss_is_triple_size():
    pygame.init()
    g = Game(debug=True)
    em = g.enemy_manager
    boss = em.spawn_boss("limbo")
    # original default width before triple = 40 (30+10)
    assert boss.width == 120
    assert boss.height == 120
    # report pixel dimensions for user information
    print(f"Limbo final boss dimensions: {boss.width}x{boss.height} pixels")


def test_limbo_final_boss_death_triggers_stage_end():
    """Defeating the Limbo Final boss should start a 5s countdown and end."""
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "limbo_final"
    # prepare basic state needed by various subsystems
    try:
        g.generate_walls()
    except Exception:
        pass
    g._init_managers()

    # spawn the boss and mark the flag so game logic knows it's out
    boss = g.enemy_manager.spawn_boss("limbo")
    g.limbo_final_boss_spawned = True

    # ensure boss exists and stage not ended yet
    assert boss in list(getattr(g, "bosses", []))
    assert not getattr(g, "showing_prologo_end", False)
    if getattr(g, "debug", False):
        print("spawned boss type", boss.enemy_type)

    # kill the boss and trigger tracking
    boss.health = 0

    # clear start countdown so update() doesn't early-return
    g.stage_start_countdown = 0
    g.stage_start_timer = 0

    # run one frame to pick up the death and start the countdown
    g.showing_stage_menu = False
    g.showing_permanent_upgrades = False
    g.showing_main_menu = False
    g.update()
    assert g.limbo_final_victory_timer > 0, "Timer did not start after boss death"

    # spawning should be blocked while timer is active
    before = len(g.enemies)
    for _ in range(10):
        g.spawn_system.update_enemy_spawning()
    assert len(g.enemies) == before, "Enemies spawned while death countdown active"

    # run frames until defeat screen appears (6 seconds allowance)
    appeared = False
    for frame in range(int(g.fps * 6)):
        g.showing_stage_menu = False
        g.showing_permanent_upgrades = False
        g.showing_main_menu = False
        g.update()
        # debug output to help diagnose failures
        if getattr(g, "debug", False):
            boss_list = list(getattr(g, "bosses", []))
            bh = boss_list[0].health if boss_list else "<none>"
            print(
                f"frame {frame}: boss_health={bh} timer={g.limbo_final_victory_timer}, showing_end={g.showing_prologo_end}"
            )
        if g.showing_prologo_end:
            appeared = True
            break
    assert appeared, "Victory timer did not lead to limbo_final_defeat"
