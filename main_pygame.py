import sys

from src.game import Game


def main():
    # Show usage/help and exit
    if "-h" in sys.argv or "--help" in sys.argv:
        print("Usage: python main_pygame.py [options]\n\nOptions:")
        print(
            "  --fast-forward-prologo, --ff-prologo      Auto-select Prologo and fast-forward to final boss (debug)"
        )
        print(
            "  --fast-forward-limbo-final, --ff-limbo    Auto-select Limbo Final and fast-forward to 2:45 boss (debug)"
        )
        print(
            "  --ff-prologo-force-lightning             Force final boss to become immortal and trigger holy light (debug)"
        )
        print("  -h, --help                               Show this help message")
        return

    # Check CLI flags to fast-forward directly to Prologo's final boss (for debugging)
    ff = ("--fast-forward-prologo" in sys.argv) or ("--ff-prologo" in sys.argv)
    ff_limbo = ("--fast-forward-limbo-final" in sys.argv) or ("--ff-limbo" in sys.argv)
    ff_force_lightning = ("--ff-prologo-force-lightning" in sys.argv) or (
        "--ff-prologo-lightning" in sys.argv
    )
    debug = ("--debug" in sys.argv) or ("-d" in sys.argv)

    # Configure logging early so modules use the desired level
    import logging

    logging.basicConfig(level=logging.DEBUG if debug else logging.WARNING)
    logger = logging.getLogger(__name__)

    game = Game(
        fast_forward_prologo=ff,
        fast_forward_limbo_final=ff_limbo,
        fast_forward_prologo_force_lightning=ff_force_lightning,
        debug=debug,
    )

    if ff:
        logger.debug("CLI flag detected: auto-selecting Prologo and fast-forwarding")
        game.select_stage("prologo")
    if ff_limbo:
        logger.debug(
            "CLI flag detected: auto-selecting Limbo Final and fast-forwarding"
        )
        game.select_stage("limbo_final")

    try:
        game.run()
    except Exception as e:
        import traceback

        print(f"Game crashed with error: {e}")
        traceback.print_exc()
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()
