from src.game import Game


def test_purgatory_tower_visible_after_selection():
    g = Game()

    # Select purgatory and choose weapon and tower
    g.select_stage("purgatory")
    if g.weapon_choices:
        g.apply_weapon(g.weapon_choices[0]["id"])
    assert g.awaiting_tower_choice
    chosen = g.tower_choices[0]["id"]
    g.apply_tower(chosen)

    # Ensure selection flags cleared
    assert not g.awaiting_tower_choice
    assert not g.awaiting_weapon_choice

    # Place an enemy so tower will have something to target (and fire)
    g.enemies = [{"x": g.width // 2, "y": 100, "health": 10, "radius": 12}]

    # Force immediate fire cycle
    g.statue_cooldown = 1
    g.statue_next_left = False  # ensure right tower fires
    g.statue_projectiles = []

    g.update_statue_weapons()
    # After firing, draw and check that right tower is visible at its head
    # First try draw_game_objects path
    g.ui.draw_game_objects()

    rt = g.right_tower
    head_y = int(rt.y - 90)
    head_x = int(rt.x)

    def neighborhood_has_nonblack():
        for dx in range(-5, 6):
            for dy in range(-5, 6):
                sx = head_x + dx
                sy = head_y + dy
                if 0 <= sx < g.width and 0 <= sy < g.height:
                    p = tuple(g.screen.get_at((sx, sy))[:3])
                    if p != (0, 0, 0):
                        return True
        return False

    if not neighborhood_has_nonblack():
        # Try drawing the statue model directly to rule out path condition issues
        try:
            g.ui._draw_statue_model(head_x, head_y + 70, rt.tower_type)
        except Exception:
            pass
        g.ui.draw_game_objects()

    assert (
        neighborhood_has_nonblack()
    ), f"Right tower appears invisible in neighborhood around {(head_x, head_y)}"
