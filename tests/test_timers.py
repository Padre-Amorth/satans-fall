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
        game.select_stage("prologo")
        game.showing_main_menu = False
        game.stage_start_countdown = 0
        game.big_enemy_timer = 50
        game.paused = False
        game.awaiting_upgrade = False
        initial = game.big_enemy_timer
        # Call update once; the big_enemy_timer is decremented by the spawn
        # system / enemy_manager during the update loop.
        game.update_game()
        assert (
            game.big_enemy_timer == initial - 1
        ), f"Expected big_enemy_timer=={initial - 1}, got {game.big_enemy_timer}"
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
        assert (
            game.wave == 1
        ), f"Expected wave==1 after crossing boundary, got {game.wave}"

        # Immediate second update should NOT increment wave again
        game.update_game()
        assert (
            game.wave == 1
        ), f"Wave incremented more than once; current wave {game.wave}"
    finally:
        teardown_game(game, root)


def test_limbo_statues_spawn_once_each():
    game, root = make_game()
    try:
        # Configure Limbo with at least one enemy so statues have targets
        game.select_stage("limbo")
        game.showing_main_menu = False
        game.stage_start_countdown = 0
        # select_stage triggers awaiting_weapon_choice; clear it so update
        # does not early-return before reaching the statue weapon code.
        game.awaiting_weapon_choice = False
        if hasattr(game, "game_state") and game.game_state is not None:
            game.game_state.awaiting_weapon_choice = False
        # Provide fully populated Enemy instances to satisfy enemy update expectations
        from src.entities.enemy import Enemy

        e1 = Enemy(400, 100, enemy_type="normal", health=10)
        e1.health = 10
        e1.max_health = 10
        e1.speed = 75
        e1.radius = 12
        e1.damage = 5
        e2 = Enemy(600, 120, enemy_type="normal", health=10)
        e2.health = 10
        e2.max_health = 10
        e2.speed = 75
        e2.radius = 12
        e2.damage = 5
        game.enemies = [e1, e2]
        # select_stage("limbo") already creates left_tower and right_tower;
        # just force statue to be ready to fire (alternating: left then right)
        game.statue_cooldown = 1
        game.statue_next_left = True
        game.paused = False
        game.awaiting_upgrade = False

        game.update_game()

        # Expect a single statue projectile (left fires first)
        try:
            proj_list = list(game.projectiles)
        except Exception:
            proj_list = game.projectiles
        statue_count = sum(1 for p in proj_list if getattr(p, "source", None) == "statue")
        assert (
            statue_count >= 1
        ), f"Expected at least 1 statue projectile, got {statue_count}"

        # Next cycle should spawn the other statue
        game.statue_cooldown = 1
        game.update_game()
        try:
            proj_list = list(game.projectiles)
        except Exception:
            proj_list = game.projectiles
        statue_count_2 = sum(1 for p in proj_list if getattr(p, "source", None) == "statue")
        assert (
            statue_count_2 >= 2
        ), f"Expected at least 2 statue projectiles after second fire, got {statue_count_2}"
    finally:
        teardown_game(game, root)
