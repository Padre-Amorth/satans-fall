# Game.py Refactoring Progress

## Completed (Phases 1-3)
- ✅ **Phase 1**: FloatingText, StatConfig → `ui_helpers.py` (80L)
- ✅ **Phase 2**: Weapon initialization → `weapons.py` (50L)
- ✅ **Phase 3**: Persistence/profiles → `persistence.py` (192L)

## Remaining Opportunities (Phase 4+)

### High-Priority Extraction Candidates

1. **Helper Properties & Proxies** (~20L)
   - Tower special proxies: `_hellectric_accum`, `_tower_energy`, `_fire_special_*`
   - Boss state proxies: `_wave_boss_spawned`, `_prologo_*`
   - Could move to separate module if needed; currently low value since they're thin wrappers

2. **Input Handling** (~200L estimated in separate methods)
   - `_handle_paused_input()`, `_handle_main_menu_input()`, etc.
   - Already delegated to `InputHandler` in many places
   - Game class retains menu state management (pause_menu_option, etc.)

3. **Draw Methods** (~1200L across 25+ methods)
   - `draw_*` methods for UI (menus, HUD, stats, upgrades)
   - `draw_game_world()`, `draw_fog()`, `draw_special_effects()`, etc.
   - Tightly coupled to PygameUIManager and game state
   - Could extract UI-only draws to `ui.py` delegation layer (low priority)

4. **Update Methods** (~800L across update_game, update_*, etc.)
   - `update_game()`: main game loop orchestrator
   - `update_weapon_firing()`: weapon/projectile logic
   - `update_enemy_spawning()`, wave progression, boss logic
   - Highly coupled; already delegated to systems (SpawnSystem, WeaponSystem, etc.)

5. **Utility Helpers** (~50L)
   - `_window_to_virtual()`: coordinate conversion
   - `_wall_x_at()`: geometry helper
   - `_enemy_pos()`, `_enemy_radius()`: collision helpers
   - Low impact; most are single-line or very simple

### Low-Priority or Coupled Logic

- **Menu state management** (pause_confirmation, showing_*_menu flags)
  - Mixed with game logic; difficult to separate cleanly

- **Boss/special event logic** (Prologo lightning, Limbo horde, Satan growth)
  - Deeply interwoven with update() and game state
  - Could extract to separate class (BossController), but risky without full test coverage

- **Drawing coordinate transformations & shake effects**
  - Pervasive throughout draw methods; hard to centralize

### Recommended Next Steps

**For Code Reduction:**
1. Extract UI draw delegation to a `DrawManager` class in `ui.py`
2. Extract update orchestration to an `UpdateManager` class
3. Separate boss/event logic into optional subsystem classes

**For Maintainability (Low Risk):**
1. Move remaining helper functions to `helpers.py` (coordinate, geometry)
2. Consolidate proxy properties into a single `properties.py` file
3. Add type stubs or Protocol classes for tightly-coupled delegates

**Current Impact:**
- core.py: 4672L → down from original 4950L (~5.6% reduction with phases 1-3)
- Further extraction would require significant architectural changes
- Recommend pausing major refactoring and focusing on feature development
- Can revisit if core.py reaches 5000+ lines again

## API Stability Notes

All public Game methods remain unchanged. Internal organization:
- Game.__init__ calls: init_weapons(), init_player_weapons(), load_last_profile_slot()
- Game.load_permanent_stats() delegates to persistence.load_permanent_stats(self)
- Game.save_permanent_stats() delegates to persistence.save_permanent_stats(self)
- Game._profile_path() delegates to persistence.profile_path()
- All 200+ external imports work unchanged

No test modifications needed for any phase.
