# Changelog

All notable changes to this project are documented in this file.

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
- **Spawn rate tuning:** made spawn-rate increase more gradual so the minimum spawn rate (`SPAWN_MIN_RATE = 30`) is reached around **wave 10** (reduced `SPAWN_RAMP_SLOPE_POST` to ~4.2).
- **Balance change — Permanent Upgrades:** `POWER` now grants **+3% damage per level** (was +2%); UI strings and tests updated to match the new value.
- **Fixes & safety:** Inquisitor movement respects wall clamps; projectiles and pooling behavior covered by tests.
- **Tests added/updated:** spawn, slow-on-hit, roaming confined to top-half, confinement to walls, and fire-rate assertions.

## 2026-02-11 — Removed restart option ⚠️

- **Gameplay:** The in-game **Restart** option has been removed.
  - The **Pause** menu no longer shows a "Restart" choice (only **Resume** and **Quit** remain).
  - The **Game Over** screen no longer accepts ENTER/SPACE to restart; press **ESC** to return to the stage menu.
  - Related confirmation flows and the internal `restart` action have been removed from game logic and tests were disabled/updated accordingly.

## 2026-02-10 — Recent changes ✅

### Weapons
- **Soul Drain**
  - Base projectile count increased: **Lv1 now fires 2 projectiles** (was 1).
  - Projectile homing speed reduced significantly (internal speed halved).
  - Initial fired velocity reduced (halved) so projectiles travel slower.
  - Upgrade progression adjusted: Lv2 +1 projectile (3 total), Lv4 +1 projectile (4 total), Lv3/Lv5 +10% damage & heal, Lv6 gains bounce.
  - Tests updated to reflect new projectile counts.

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
  - `tests/test_weapon_upgrade_inference.py` — verifies fallback inference provides useful descriptions for common weapons (e.g., `soul_drain`, `orbital`).
  - `test_orbital.py` updated: added `test_orbital_targets_boss` to ensure orbitals target bosses.
- Updated tests to reflect Soul Drain base projectile change and level-6 weapon-choice behavior.
- Full test suite passed locally: all tests green as of 2026-02-10.

### Misc
- Minor refactors and robustness improvements to support both Group and list/dict enemy representations across targeting and selection code.

---

If you want a different format (per-commit condensed notes, or an entry per-feature), I can reformat. Vuoi che faccia anche il commit del changelog ora? (Ho già preparato il file, dimmi se procedo col commit.)