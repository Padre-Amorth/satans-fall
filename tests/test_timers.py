# Tkinter version removed; use Pygame implementation
from src.game import Game  # Use pygame version instead


def make_game():
    # root = tk.Tk()
    # # Prevent test runs from showing a window
    # root.withdraw()
    # game = SatanGame(root)
    game = Game()  # Use pygame version
    return game, None


def teardown_game(game, root):
    try:
        game.stop_game_loop()
    except Exception:
        pass
    try:
        if root is not None:
            root.destroy()
    except Exception:
        pass


def test_big_enemy_timer_decrements_once():
    game, root = make_game()
    try:
        game.big_enemy_timer = 50
        game.paused = False
        game.awaiting_upgrade = False
        # Call update once and assert it decremented by exactly 1
        game.update_game()
        assert game.big_enemy_timer == 49, (
            f"Expected big_enemy_timer==49, got {game.big_enemy_timer}"
        )
    finally:
        teardown_game(game, root)


def test_wave_increments_once_on_period_boundary():
    game, root = make_game()
    try:
        # Ensure a valid stage is selected so draw() does not error
        game.selected_stage = "prologo"
        period = int(game.wave_duration * game.fps)
        # Set frame_count to one before the boundary
        game.frame_count = period - 1
        game.wave = 0
        game.paused = False
        game.awaiting_upgrade = False

        # First update should cross the boundary and increment wave once
        game.update_game()
        assert game.wave == 1, (
            f"Expected wave==1 after crossing boundary, got {game.wave}"
        )

        # Immediate second update should NOT increment wave again
        game.update_game()
        assert game.wave == 1, (
            f"Wave incremented more than once; current wave {game.wave}"
        )
    finally:
        teardown_game(game, root)


def test_limbo_statues_spawn_once_each():
    game, root = make_game()
    try:
        # Configure Limbo with at least one enemy so statues have targets
        game.selected_stage = "limbo"
        # Provide fully populated enemy dicts to satisfy enemy update expectations
        game.enemies = [
            {
                "x": 400,
                "y": 100,
                "health": 10,
                "max_health": 10,
                "speed": 75,
                "radius": 12,
                "damage": 5,
                "type": "normal",
            },
            {
                "x": 600,
                "y": 120,
                "health": 10,
                "max_health": 10,
                "speed": 75,
                "radius": 12,
                "damage": 5,
                "type": "normal",
            },
        ]
        # Force statues to be ready to fire
        game.statue_cooldown_left = 1
        game.statue_cooldown_right = 1
        game.statue_projectiles = []
        game.paused = False
        game.awaiting_upgrade = False

        game.update_game()

        # Expect two statue projectiles (one left, one right) to have been spawned
        assert len(game.statue_projectiles) == 2, (
            f"Expected 2 statue projectiles, got {len(game.statue_projectiles)}"
        )
    finally:
        teardown_game(game, root)
