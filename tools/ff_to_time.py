"""Fast-forward preview to an arbitrary elapsed time (live window).

This tool is similar to ``ff_to_boss_spawn`` but lets you jump to a specific
point in the run.  It's useful for testing long‑running events such as the
7:30 horde in the first limbo level.

Usage:
  python tools/ff_to_time.py [--stage limbo] [--time 450] [--show-seconds 8]

The ``--time`` argument accepts a floating point number of seconds or a
``MIN:SEC`` string (e.g. ``7:30``).

"""

from __future__ import annotations

import argparse
import time

from src.game import Game


def parse_time(value: str) -> float:
    """Convert a time string to seconds.

    Accepts either a plain number or ``MM:SS`` format.
    """
    if ":" in value:
        parts = value.split(":")
        if len(parts) != 2:
            raise argparse.ArgumentTypeError(f"invalid time format: {value}")
        minutes, seconds = parts
        return float(minutes) * 60.0 + float(seconds)
    return float(value)


def main() -> int:
    p = argparse.ArgumentParser(
        description="Fast-forward to a given elapsed time and show live window"
    )
    p.add_argument(
        "--stage",
        default="limbo",
        help="Stage to use (limbo/limbo_2/limbo_3/limbo_final)",
    )
    p.add_argument(
        "--time",
        type=parse_time,
        default=450.0,
        help="Target elapsed time in seconds or MM:SS (default 7:30)",
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
        help="Continue running the game indefinitely after reaching the target time instead of exiting after a short preview",
    )
    args = p.parse_args()

    print(f"Starting Game (debug) and selecting stage {args.stage}...")
    g = Game(debug=True)
    g.select_stage(args.stage)

    # Bypass initial weapon/tower choice so update() runs immediately
    g.awaiting_weapon_choice = False
    g.awaiting_tower_choice = False

    # Put player roughly in the center-bottom so any events are visible
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

    # optionally make the player invincible so simulation can't kill them
    if args.invincible and hasattr(g, "player"):
        try:
            g.player.health = getattr(g.player, "max_health", g.player.health)
            setattr(g.player, "invincible", True)
        except Exception:
            pass

    # Fast-forward simulation by running updates until time_elapsed >= target
    print(f"Fast-forwarding simulation to elapsed time {args.time:.1f}s...")
    simulated_frames = 0
    timeout_frames = int(g.fps * (args.time + 60))  # safety timeout (target + 1min)
    while g.time_elapsed < args.time and simulated_frames < timeout_frames:
        # run multiple update steps between draws to accelerate time
        for _ in range(max(1, args.fast_factor)):
            # ensure player doesn't die mid-simulation
            if args.invincible and hasattr(g, "player"):
                try:
                    g.player.health = getattr(g.player, "max_health", g.player.health)
                except Exception:
                    pass
            g.update()
            simulated_frames += 1
        # draw occasional frames so you can see fast-forward happening
        try:
            g.handle_events()
            g.draw()
        except Exception:
            pass

    if g.time_elapsed < args.time:
        print("Timeout: target time not reached within fast-forward window.")
    else:
        print(
            f"Reached {g.time_elapsed:.1f}s after {simulated_frames} simulated frames."
        )

    # remove temporary invincibility so user can play normally
    if args.invincible and hasattr(g, "player"):
        try:
            setattr(g.player, "invincible", False)
        except Exception:
            pass

    if args.play:
        print(
            "Target reached — continuing game until window is closed (ESC also works)."
        )
        while g.running:
            g.handle_events()
            g.update()
            g.draw()
            g.clock.tick(g.fps)
        print("Game loop exited.")
    else:
        print("Entering live preview — press ESC or close the window to exit early.")

        # Show real-time for a short while so the user can inspect the state
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
