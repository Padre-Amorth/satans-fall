# Changelog

All notable changes to this project are documented in this file.

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