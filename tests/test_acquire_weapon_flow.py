from src.game import Game


def test_apply_acquire_weapon_adds_correct_weapon():
    game = Game()
    # Ensure no weapons initially
    game.player_weapons = []
    game.weapon_levels = {}

    # Simulate level-6 choices where IDs use acquire_ prefix
    game.apply_weapon("acquire_shotgun")
    assert "shotgun" in game.player_weapons
    assert game.weapon_levels.get("shotgun", 0) == 1

    # Adding another weapon
    game.apply_weapon("acquire_orbital")
    assert "orbital" in game.player_weapons
    assert game.weapon_levels.get("orbital", 0) == 1

    # Ensure we respect the max extra weapons limit: fill to capacity and attempt another
    max_allowed = game.max_extra_weapons
    game.player_weapons = ["shotgun"]
    game.weapon_levels = {"shotgun": 1}
    # Add until just below limit then add one more
    while len(game.player_weapons) < max_allowed:
        # pick a non-owned weapon id
        candidate = "orbital" if "orbital" not in game.player_weapons else "spear"
        game.apply_weapon(f"acquire_{candidate}")

    assert len(game.player_weapons) == max_allowed
    # Attempt to add another weapon should fail
    before = list(game.player_weapons)
    game.apply_weapon("acquire_spear")
    assert list(game.player_weapons) == before
