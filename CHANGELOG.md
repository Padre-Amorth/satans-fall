# Changelog

All notable changes to this project are documented in this file.

## Unreleased — Bug fixes & tests ✅

- **Inquisitor slow tuning:** boss and normal inquisitor projectiles now apply a 1.5‑second slow (half the previous duration).  Projectile creation now uses `int(1.5 * fps)` for flexibility.  Updated relevant unit tests to expect the shorter slow.

- **Health drops from wave bosses:** end-of-wave bosses (`boss_medium`, `boss_big`, and `boss_inquisitor`) now release a green bonus on death that falls **even faster** (1.5 px/frame) and is still tiny (radius 8).  The drop is more transparent overall and pulses gently to catch the eye while staying subtle.  Drops are clamped to spawn at the top of the visible battlefield when bosses die off-screen. Added game logic, rendering, sound, collision handling, and comprehensive unit tests for the mechanic.

- **Bug fix:** `EnemyManager.spawn_boss` regained support for the `"mid"` boss type (`boss_medium`) which had been accidentally removed—tests now exercise mid, big and inquisitor bosses.

- **Custode spawn bug:** on Hell stages, big enemy spawns now produce the new `custode` type instead of a regular giant.  The `Game.spawn_giant_enemy`, `Game.spawn_big_enemy` and `EnemyManager.spawn_giant_enemy` helpers all check `selected_stage` and choose the appropriate type.  Added new custode‑specific unit tests and updated the enemy manager tests to assert the replacement logic.
- **Custode split visuals & movement:** explosion centre effect now includes full `max_radius`/`max_timer`/`color` metadata so the ring is drawn correctly; prior omission prevented the visual from ever appearing.  Child halves now receive a speed boost of exactly **1.65× the parent’s speed**. Tests updated to validate explosion metadata, spawn type, separation, and correct speed multiplier.
- **Critical hit display bug:** floating text now shows the actual damage applied (50 % bonus on a crit) instead of the projectile’s base damage. The collision system’s text‑render logic was simplified, and regression tests added to cover both spatial‑grid and fallback branches.

- **Balance regression fix:** restored original blasphemy behaviour after accidental rewrite.
  * `blasphemy_1` now grants **+15 HP per level** (max 3) instead of damage.
  * `blasphemy_2` now provides **0.5 HP every 2s per level** (regen only, no HP bonus); descriptions now include the word "Heal".
  * `blasphemy_3` now gives **-10% damage taken per level** (not fire rate).
  Code, UI tooltips, and tests updated to match the intended effects.
- **New limbo horde event:** Regular limbo stages now culminate at 8 minutes with a massive, aggressive enemy horde.  Enemies arrive gradually over a **10‑second window** at roughly 5 per second and spawn from the top using the normal spawning logic.  Survive half the horde and Satan will trigger a scripted explosion that wipes remaining foes and concludes the level successfully (limbo_final unaffected).  Game state, spawn logic, and tests added for the feature.
- **Limbo difficulty tuning:** per-wave difficulty multiplier reduced from 0.12 to **0.11** on `limbo`, `limbo_2` and `limbo_3` only.  New helper method `Game.get_difficulty_multiplier_per_wave()` returns the appropriate slope and tests verify stage‑specific behaviour.
- **Victory overlay:** after horde explosion the game now displays a full “SATANIC VICTORY!” screen (with fade) for a few seconds before automatically returning to the stage menu.  The previous simple center message has been replaced accordingly.
- **Limbo spawn pacing:** enemies spawn slightly slower on the three limbo stages (about two fewer per 10 seconds).  An 8‑frame penalty is added to the computed spawn rate and applied at wave 0 and thereafter.  The initial horde interval was also doubled to 10 seconds.  Tests confirm the reduced counts (6‑8 early, 10‑18 mid‑game, etc.).
- **Horde crescendo:** the limbo horde now becomes more intense during its final three seconds.  An extra ten enemies per second are injected between seconds 7‑10, bringing the overall horde size from 50 to **80**.  Spawn logic, constants, and fast‑forward tooling updated accordingly.  New assertions verify roughly 35 enemies spawn before the accel point and the full 80 arrive by 11 s.
- `ADRENALINE` now also grants **+2% crit chance per level**; UI stats and collision logic updated accordingly.
- Fix: `The number of the beast` (Beast weapon) now correctly scales its projectile damage with the player's `base_damage` so **permanent upgrades** (`power`, `blasphemy_1`) affect Beast damage as intended. Added unit tests for damage scaling.
- Fix: Prologo final boss **no longer dies** when reduced below 10% HP — it now reliably enters the immortal/regeneration phase (HP clamped to 10%). Centralized the immortal-transition in `Enemy.take_damage` and added unit tests for the immortal/regeneration flow.
- Fix: Reinforcement waves are now scheduled reliably when a wave boss dies (including deaths from DOT/burn or direct `take_damage`). The centered HUD message and `USEREVENT+1` timer are scheduled consistently; added tests to cover the sequence.
- Tests: Added/updated tests covering Beast scaling, Prologo final boss immortal phase, and reinforcement scheduling.

## 2026-02-13 — STORM left-column: chain lightning range rebalanced (slot 1 & 3 +2, slot 2 +1) ⚡

- **Balance change — STORM (left column):** `storm_1` and `storm_3` grant **+2 chained targets** each; `storm_2` no longer increases chain targets — instead it makes enemies **killed by chain lightning explode** in a lightning burst that damages nearby enemies. Chain-target stacking from left slots is now up to **+4** total (base 3 → 7 when both slots 1 & 3 active).
- **UI / Tooltip:** Skill-tree tooltips updated to describe the new `storm_2` on-kill explosion and the left-column stacking.
- **Tests updated/added:** `tests/test_skill_tree_effects.py`, `tests/test_skill_tooltips.py`, and `tests/test_storm_extra.py` updated/extended to verify chain-kill explosions and tooltip text.
- **Notes:** Applies to statue/projectile `chain_targets` only for slot 1 & 3; the `storm_2` effect is an additional AoE-on-chain-kill mechanic and is visually represented by lightning effects.

## 2026-02-12 — Add Inquisitor Limbo boss (new feature + tuning) ✨

- **New enemy:** `Inquisitor` — a Limbo end-of-wave boss that roams the top half of the battlefield instead of chasing the player.
  - Roaming AI confined to arena walls and the top half of the stage.
  - Slightly higher movement speed and 50% increased HP vs. previous mid-boss baseline.
  - Fires a 3‑shot orange projectile spread; projectiles apply a slow to the player (stronger and longer than Ice tower slow).
- **Gameplay tuning:** reduced Inquisitor fire rate and tuned projectile slow (duration and strength).
- **Gameplay tuning:** enemy base movement speeds are now centralised in `ENEMY_BASE_SPEEDS` (`src/balance.py`) and applied at spawn. Current values: `weak=35`, `normal=75`, `strong=60`, `angel=60`, `giant=45` (bosses: `boss_medium=45`, `boss_inquisitor=50`, `boss_big=40`, `boss_final=40`). This replaces previous hard-coded spawn values and makes tuning a single-source operation.
- **New enemy type:** introduced the "crusader", a slow, extra-tanky giant variant that alternates three seconds of vulnerability with three seconds of invulnerability. Crusaders only appear on Purgatory‑class or Hell stages (any stage string containing "purgatory" or "hell", including numbered variants) and are limited to three random spawns per wave; the counter resets at each wave boundary. They no longer have a shield or blue shield bar; while invulnerable a light blue circular aura surrounds the unit, disappearing when damageable. Asset support added (`enemy_crusader.png`), spawn helpers (`spawn_crusader_enemy`), and tests for cycle/limit/aura behaviour.

- **Winged enemy AI update:** winged flyers now actively target the player with a rapid darting motion and subtle zigzag offsets instead of mindlessly plunging downward. Added unit tests to confirm chasing behaviour and zig variation.
- **Spawn rate tuning:** made spawn-rate increase more gradual so the minimum spawn rate (`SPAWN_MIN_RATE = 30`) is reached around **wave 10** (reduced `SPAWN_RAMP_SLOPE_POST` to ~4.2).
- **Balance change — Permanent Upgrades:** `POWER` now grants **+5% damage per level** (was +3%); `BLASPHEMY_1` now grants **+10% damage per level**; UI strings and tests updated to match the new values.
- **Fixes & safety:** Inquisitor movement respects wall clamps; projectiles and pooling behavior covered by tests.
- **Tests added/updated:** spawn, slow-on-hit, roaming confined to top-half, confinement to walls, and fire-rate assertions.

## 2026-02-11 — Removed restart option ⚠️

- **Gameplay:** The in-game **Restart** option has been removed.
  - The **Pause** menu no longer shows a "Restart" choice (only **Resume** and **Quit** remain).
  - The **Game Over** screen no longer accepts ENTER/SPACE to restart; press **ESC** to return to the stage menu.
  - Related confirmation flows and the internal `restart` action have been removed from game logic and tests were disabled/updated accordingly.

## 2026-02-10 — Recent changes ✅

### Weapons
- **Flies**
  - Base projectile count increased: **Lv1 now fires 2 projectiles** (was 1).
  - Projectile homing speed reduced significantly (internal speed halved).
  - Initial fired velocity reduced (halved) so projectiles travel slower.
  - Upgrade progression adjusted:
    * Lv2 +10% damage & heal
    * Lv3 +1 projectile (3 total)
    * Lv4 +10% damage & heal
    * Lv5 +1 projectile (4 total)
    * Lv6 +20% damage & heal (bounce removed)
  - Tests updated to reflect new projectile counts and multipliers.

- **Hellgun (Shotgun)**
  - Upgrade descriptions clarified: pellet counts, cooldown and damage increases at Lv3/Lv5 are now described explicitly.
  - Code updated to apply +10% damage at Lv3 and +10% additional at Lv5.

- **Orbitals**
  - Orbitals now consider **bosses** when selecting targets (fix bug where bosses were ignored).
  - Upgrade descriptions updated (counts and damage increases at Lv3/Lv5).
  - Orbital projectile damage now scales with upgrades (Lv3/Lv5 +10% steps).

- **Spear & Beast**
  - Upgrade descriptions clarified for all levels (what each level does).

### Gameplay & UI
- At **player level 6**, the weapon choice UI now proposes **only weapons not yet equipped** (up to 3 unique choices). No weapon upgrades are forced into the 3 choices at level 6.
- `get_weapon_upgrade_description` improved: if explicit description missing, function will normalize weapon ids and infer a helpful description (e.g., projectile count, orbital count, damage/heal multipliers) instead of returning the generic "Upgrade to level X" text.

### Tests
- Added tests:
  - `tests/test_weapon_upgrade_descriptions.py` — verifies explicit descriptions exist for every weapon level.
  - `tests/test_weapon_upgrade_inference.py` — verifies fallback inference provides useful descriptions for common weapons (e.g., `flies`, `orbital`).
  - `test_orbital.py` updated: added `test_orbital_targets_boss` to ensure orbitals target bosses.
- Updated tests to reflect Flies base projectile change and level-6 weapon-choice behavior.
- Full test suite passed locally: all tests green as of 2026-02-10.

### Misc
- Minor refactors and robustness improvements to support both Group and list/dict enemy representations across targeting and selection code.

---

If you want a different format (per-commit condensed notes, or an entry per-feature), I can reformat. Vuoi che faccia anche il commit del changelog ora? (Ho già preparato il file, dimmi se procedo col commit.)
