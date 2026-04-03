"""Fast-forward preview to boss spawn (live window).

Run this from the workspace Python environment. It will:
 - create a Game instance
 - select the requested stage (default: limbo)
 - fast-forward simulation until the wave boss (boss_big) spawns
 - then run the game in real-time for a few seconds so you can inspect the spawn

Usage:
  python tools/ff_to_boss_spawn.py [--stage limbo] [--wave 3] [--show-seconds 8]

"""

from __future__ import annotations

import argparse
import time

from src.game import Game


def main() -> int:
    p = argparse.ArgumentParser(
        description="Fast-forward to boss spawn and show live window"
    )
    p.add_argument(
        "--stage",
        default="limbo",
        help="Stage to use (limbo/limbo_2/limbo_3/limbo_final)",
    )
    p.add_argument(
        "--wave", type=int, default=3, help="Wave number to jump to (default: 3)"
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
        help="Seconds to show the live window after spawn",
    )
    p.add_argument(
        "--skip-to-boss",
        action="store_true",
        help="Skip timing logic and spawn boss immediately",
    )
    args = p.parse_args()

    print(f"Starting Game (debug) and selecting stage {args.stage}...")
    g = Game(debug=True)
    g.select_stage(args.stage)

    # Bypass initial weapon/tower choice so update() runs immediately
    g.awaiting_weapon_choice = False
    g.awaiting_tower_choice = False

    # Put player roughly in the center-bottom so boss spawn is visible
    try:
        g.player.x = g.width // 2
        g.player.y = g.height - 90
    except Exception:
        pass

    # Clear any previous bosses/projectiles and ensure groups exist
    try:
        if hasattr(g, "bosses"):
            try:
                g.bosses.empty()
            except Exception:
                g.bosses = type(g.bosses)()
    except Exception:
        pass

    if args.skip_to_boss:
        print("Spawning boss immediately (skip-to-boss)")
        g.spawn_boss("big")
    else:
        # Fast-forward simulation by setting wave + wave_time and running updates
        print(f"Fast-forwarding simulation to wave={args.wave} and spawn-time (38s)...")
        g.wave = args.wave
        # put wave_time just before spawn so the next few updates will trigger a spawn
        g.wave_time = 37.0

        simulated_frames = 0
        timeout_frames = int(g.fps * 30)  # safety timeout (simulate max 30s)
        boss_spawned = False
        while not boss_spawned and simulated_frames < timeout_frames:
            # Run multiple update steps between draws to accelerate time
            for _ in range(max(1, args.fast_factor)):
                g.update()
                simulated_frames += 1
            # Draw occasional frames so you can see fast-forward happening
            try:
                g.handle_events()
                g.draw()
            except Exception:
                pass

            if hasattr(g, "bosses") and list(getattr(g, "bosses", [])):
                boss_spawned = True
                break

        if not boss_spawned:
            print(
                "Timeout: boss did not spawn within fast-forward window. Spawning directly."
            )
            g.spawn_boss("big")

    print("Entering live preview — press ESC or close the window to exit early.")

    # Show real-time for a short while so user can inspect boss behaviour
    live_frames = int(max(1, args.show_seconds) * g.fps)
    frame = 0
    start_time = time.time()
    while g.running and frame < live_frames:
        g.handle_events()
        g.update()
        g.draw()
        g.clock.tick(g.fps)
        frame += 1

    print(f"Preview finished ({time.time() - start_time:.1f}s). Exiting.")
    # Ensure pygame quits cleanly
    try:
        import pygame

        pygame.quit()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
