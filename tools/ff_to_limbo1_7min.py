"""Fast-forward to 7:00 in Limbo 1.

This tool starts the Limbo 1 stage and immediately fast-forwards to 7:00 (420 seconds)
without waiting for weapon selection. The default weapon will be selected automatically.

Usage:
  python tools/ff_to_limbo1_7min.py [--fast-factor 60] [--show-seconds 8] [--play]

Options:
  --fast-factor FACTOR    Simulation updates per draw while fast-forwarding (default 60)
  --show-seconds SECS     Seconds to show the live window after reaching target time (default 8)
  --invincible            Make player invincible during fast-forward (optional)
  --play                  Continue running the game after reaching the target time instead of exiting
"""

from __future__ import annotations

import argparse

from src.game import Game


def main() -> int:
    p = argparse.ArgumentParser(
        description="Fast-forward to 7:00 in Limbo 1 with initial weapon selection"
    )
    p.add_argument(
        "--fast-factor",
        type=int,
        default=60,
        help="Simulation updates per draw while fast-forwarding",
    )
    p.add_argument(
        "--show-seconds",
        type=float,
        default=8.0,
        help="Seconds to show the live window after jumping (ignored with --play)",
    )
    p.add_argument(
        "--invincible",
        action="store_true",
        help="Make player invincible during the fast-forward to prevent death",
    )
    p.add_argument(
        "--play",
        action="store_true",
        help="Continue running the game indefinitely after reaching target time",
    )
    p.add_argument(
        "--no-auto-exit",
        action="store_true",
        help="When used with --play, do not auto-exit on boss observation or after the safety timeout",
    )
    args = p.parse_args()

    # Jump to exactly 7 minutes (420 seconds) in the stage rather than
    # waiting for the horde trigger.  This matches the tool name and user's
    # request to start at minute 7.
    target_time = 7 * 60.0  # 420 seconds

    print("Starting Limbo 1...")
    # debug=False avoids repeated draw logs during startup
    g = Game(debug=False)
    g.select_stage("limbo")

    # Generate initial weapon choices
    g.is_initial_weapon_choice = True
    g.weapon_choices = g.generate_initial_weapon_choices()
    g.selected_weapon_index = 0

    # Automatically select the first weapon to start the game
    if g.weapon_choices:
        first_weapon_id = g.weapon_choices[0]["id"]
        print(
            f"Automatically selecting weapon: {g.weapon_choices[0].get('name', first_weapon_id)}"
        )
        g.apply_weapon(first_weapon_id)

    # Bypass tower choice
    g.awaiting_tower_choice = False
    g.is_initial_tower_choice = False

    # Put player roughly in the center-bottom so any events are visible
    try:
        g.player.x = g.width // 2
        g.player.y = g.height - 90
    except Exception:
        pass

    # Make player invincible if requested
    if args.invincible and hasattr(g, "player"):
        try:
            g.player.health = getattr(g.player, "max_health", g.player.health)
            setattr(g.player, "invincible", True)
        except Exception:
            pass

    # Instead of playing out the first seven minutes, directly compute the
    # wave state that would have resulted.  We still set ``time_elapsed`` for
    # any systems that read it, but avoid running ``update()`` loops entirely.
    print(f"\nJumping immediately to {target_time:.1f}s (minute 7) without simulating)")
    g.time_elapsed = target_time

    # compute how many whole waves have elapsed and the remaining wave_time
    duration = g.wave_duration
    if duration <= 0:
        duration = 1.0  # guard against division by zero
    waves_completed = int(target_time // duration)
    leftover = target_time - waves_completed * duration

    # replay the wave increments to get spawn rates/flags right
    # start from fresh state (wave 0, wave_time 0)
    g.wave = 0
    g.wave_time = 0.0
    for _ in range(waves_completed):
        # force the condition that triggers an increment
        g.wave_time = duration
        g.update_wave_progression()
    # now set the partial progress within the current wave
    g.wave_time = leftover
    print(
        f"[OK] Time set to {g.time_elapsed:.1f}s, Wave set to {g.wave}, wave_time={g.wave_time:.1f}s"
    )

    # Remove temporary invincibility so user can play normally
    if args.invincible and hasattr(g, "player"):
        try:
            setattr(g.player, "invincible", False)
        except Exception:
            pass

    print("\nStarting game at 7:00...")

    # Force UI/menu flags off so the game starts in-play rather than showing menus.
    try:
        g.showing_main_menu = False
        g.showing_stage_menu = False
        g.showing_profiles_menu = False
        g.showing_permanent_upgrades = False
        g.showing_prologo_end = False
        g.showing_game_over = False
        g.showing_victory = False
        g.awaiting_weapon_choice = False
        g.is_initial_weapon_choice = False
        g.awaiting_tower_choice = False
        g.is_initial_tower_choice = False
        g.paused = False
        g.stage_start_countdown = 0
        g.stage_start_timer = 0
    except Exception:
        pass

    # two modes: a brief live preview or full-play mode.
    if not args.play:
        # preview for a fixed number of seconds then exit automatically.
        live_frames = int(max(0.0, args.show_seconds) * g.fps)
        print(
            f"Showing live preview for {args.show_seconds:.1f}s ({live_frames} frames)..."
        )
        frames = 0
        boss_reported = False
        try:
            while g.running and frames < live_frames:
                g.handle_events()
                g.update()
                # report if boss appears during preview
                if not boss_reported:
                    for b in getattr(g, "bosses", []):
                        if getattr(b, "enemy_type", "") == "boss_limbo_horde":
                            print("[INFO] Limbo horde boss has spawned")
                            boss_reported = True
                            break
                g.draw()
                g.clock.tick(g.fps)
                frames += 1
        except Exception:
            import traceback

            print("[ERROR] Exception during preview loop:")
            traceback.print_exc()
        finally:
            print("Preview finished, exiting game.")
    else:
        # full play mode continues until user exits or boss is observed
        frames = 0
        boss_reported = False
        try:
            while g.running:
                g.handle_events()
                g.update()
                # report once when boss shows up
                if not boss_reported:
                    for b in getattr(g, "bosses", []):
                        if getattr(b, "enemy_type", "") == "boss_limbo_horde":
                            print("[INFO] Limbo horde boss has spawned")
                            boss_reported = True
                            break
                g.draw()
                g.clock.tick(g.fps)
                frames += 1
                # safety: if we simulate more than 60 seconds, bail out
                if not args.no_auto_exit:
                    if frames > int(g.fps * 60):
                        print("[WARN] reached 60 seconds of simulation, exiting")
                        break
                    if boss_reported:
                        print("[INFO] Exiting after boss observed")
                        break
        except Exception:
            import traceback

            print("[ERROR] Exception during main loop:")
            traceback.print_exc()
        finally:
            print("Game exited.")

    # Ensure pygame quits cleanly
    try:
        import pygame

        pygame.quit()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
