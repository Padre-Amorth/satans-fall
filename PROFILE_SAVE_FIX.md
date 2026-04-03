# Profile Save System Fix - March 14 2026

## Problem Summary

Player profiles were being reset to level 1 on each session reload, losing all meta-progression (XP, levels, points) accumulated during gameplay.

**Example**: Profile had `meta_level: 17, meta_xp: 18896` but loaded as `meta_level: 1, meta_xp: 50`.

## Root Cause

Profile files (`profile_1.json`, `profile_2.json`, `profile_3.json`) were **tracked by git version control**. During git merge/rebase/stash operations on March 13, git corrupted these files:

- Git doesn't handle binary/dynamic save files well
- Save files change constantly during gameplay
- Git operations (merge, stash, rebase) corrupted the JSON content
- Result: Player profiles reset to default values (level 1)

## Solution

### 1. ✅ Added Profiles to `.gitignore` (Commit: 7fe1da7)

**File**: `.gitignore`
```diff
 # Player save data — must NOT be tracked by git to avoid resets on checkout/pull
 permanent_stats.json
 permanent_stats.json.bak
 permanent_stats.json.tmp
+profile_1.json
+profile_2.json
+profile_3.json
+*.json.tmp
```

**Action**:
- Profiles are now excluded from git tracking
- Removed from git repository (but local copies preserved)
- Matches existing pattern for `permanent_stats.json`

### 2. ✅ Added Comprehensive Persistence Tests (Commit: 8e0a12d)

**File**: `tests/test_profile_meta_persistence.py`

10 tests verify:
1. Profiles save meta_level correctly to JSON
2. Profiles load meta_level correctly from JSON
3. Save→Load round-trip preserves all values
4. Multiple profiles maintain independent meta data
5. Accumulated XP never resets
6. Profile info queries reflect correct meta_level
7. Corrupted profiles gracefully default to level 1
8. Integration with award_meta_xp() system
9. Profile switching preserves all data
10. Type safety: meta values always integers

**Run tests**:
```bash
python -m pytest tests/test_profile_meta_persistence.py -v
```

Result: **10/10 tests passing** ✅

## Impact

### Before Fix
- Git operations corrupted save files
- Players lost progress on reload
- Profile meta_level reset to 1
- Meta progression was not persistent

### After Fix
- ✅ Profiles stay completely local (not tracked by git)
- ✅ Players' progress persists across sessions
- ✅ Meta levels and XP saved and loaded correctly
- ✅ Git operations cannot corrupt save files anymore
- ✅ Comprehensive test coverage prevents regression

## How It Works

### Save Cycle (During Gameplay)
1. Player gains XP → `award_meta_xp()` called
2. If level-up occurs → `save_permanent_stats()` called
3. Meta data written to `profile_N.json` (stays local, not in git)
4. File never affected by git operations

### Load Cycle (On Startup)
1. Game detects last played profile slot
2. Loads `profile_N.json` from disk
3. `load_permanent_stats()` reads meta_level, meta_xp, meta_points
4. Values restored to game state
5. Player continues where they left off

## Testing

All profile persistence tests are in `tests/test_profile_meta_persistence.py`:

```bash
# Run just the profile tests
python -m pytest tests/test_profile_meta_persistence.py -v

# Run full test suite (to verify no regressions)
python -m pytest tests/ -q
```

## Files Modified

1. **`.gitignore`**: Added profile file exclusions
   - `profile_1.json`, `profile_2.json`, `profile_3.json`
   - `*.json.tmp` (temp files during atomic writes)

2. **`tests/test_profile_meta_persistence.py`**: New file with 10 tests
   - Save/load verification
   - Round-trip integrity
   - Multi-profile independence
   - Error handling
   - Integration tests

## No Code Changes Needed

The save/load system in `src/game/persistence.py` already works correctly:
- `save_permanent_stats()` properly writes profiles
- `load_permanent_stats()` properly reads profiles
- Game initialization loads the last played profile

The bug was purely due to git tracking, not application logic.

## Prevention

Future regressions are prevented by:
1. ✅ Profiles excluded from git (won't be corrupted)
2. ✅ 10 regression tests in the test suite (catch any issues)
3. ✅ Clear documentation (explains the fix)

Any future changes to the persistence system must pass all 10 profile tests.

## Migration

No migration needed for existing players:
- Local profiles were never deleted, just removed from git
- Profiles continue to work exactly as before
- Git corruption fixed going forward
