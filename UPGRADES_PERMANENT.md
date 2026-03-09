# Satan's Fall — Permanent Upgrades (Meta-Progression)

## Overview
Permanent upgrades are **persistent meta-progression** unlocks purchased with `meta_points` (earned by reaching new Satan levels). They appear in the **Main Menu** under the gear icon and provide permanent bonuses across all future runs.

All permanent upgrades are saved in `permanent_stats.json` and loaded automatically at game start.

---

## 📊 Upgrade Categories

### A) Base Permanent Stats (4 types)
Earned by reaching specific Satan levels, can be purchased in pairs at Main Menu.

#### 1. **POWER**
- **Effect**: +5% damage per level
- **Scaling**: Linear — Lv1 = +5%, Lv2 = +10%, Lv3 = +15%, etc.
- **Max Levels**: 3 (typically)
- **When**: Baseline meta upgrade, purchasable early
- **Code**: [src/systems/upgrade_system.py:919-922](src/systems/upgrade_system.py#L919-L922)

#### 2. **VIGOR**
- **Effect**: +10 Max HP per level + passive healing
- **Healing**: 0.5 HP every 5 seconds per level
- **Example**: Lv2 = +20 Max HP, heal 1 HP every 5s
- **Max Levels**: 3 (typically)
- **When**: Early survivability boost
- **Code**: [src/systems/upgrade_system.py:923-935](src/systems/upgrade_system.py#L923-L935)

#### 3. **ADRENALINE**
- **Effect**: +5% fire rate + crit chance per level
- **Crit Bonus**: +2% crit chance per level
- **Example**: Lv2 = +10% fire rate, +4% crit chance
- **Max Levels**: 3 (typically)
- **When**: Offensive scaling
- **Code**: [src/systems/upgrade_system.py:936-944](src/systems/upgrade_system.py#L936-L944)

#### 4. **STRUCTURE**
- **Effect**: -2% damage taken per level + XP gain bonus
- **XP Bonus**: +3% XP per level
- **Example**: Lv2 = -4% dmg taken, +6% XP gain
- **Max Levels**: 3 (typically)
- **When**: Defensive scaling + progression
- **Code**: [src/systems/upgrade_system.py:945-949](src/systems/upgrade_system.py#L945-L949)

---

## 🔮 Blasphemy Upgrades (10 types)
Special unlockable powers, each up to Level 3. Accessed via **skill tree grid** in Main Menu (2 rows × 5 columns = 10 slots).

### Grid Layout (5-column grid)
```
Row 1: [ 1 ] [ 2 ] [ 3 ] [ 4 ] [ 5 ]
Row 2: [ 6 ] [ 7 ] [ 8 ] [ 9 ] [10 ]
```

### Individual Blasphemies

#### **BLASPHEMY_1**: Enhanced Health
- **Effect**: +15 Max HP per level
- **Max Levels**: 3 (total +45 HP)
- **Stacking**: Direct health buff, no cap
- **Code**: [src/systems/upgrade_system.py:951-954](src/systems/upgrade_system.py#L951-L954)

#### **BLASPHEMY_2**: Passive Regeneration
- **Effect**: Heal 0.5 HP every 2 seconds per level
- **Max Levels**: 3 (total: 1.5 HP every 2s = 0.75 HP/s)
- **Stacking**: Additive healing over time
- **Code**: [src/systems/upgrade_system.py:955-961](src/systems/upgrade_system.py#L955-L961)

#### **BLASPHEMY_3**: Damage Reduction
- **Effect**: -10% damage taken per level
- **Max Levels**: 3 (total: -30% damage taken)
- **Stacking**: Multiplicative — 0.9 × 0.9 × 0.9 = 0.729 = 27.1% reduction
- **Code**: [src/systems/upgrade_system.py:962-965](src/systems/upgrade_system.py#L962-L965)

#### **BLASPHEMY_4**: XP Multiplier
- **Effect**: +10% XP gain per level
- **Max Levels**: 3 (total: +30% XP)
- **Progression**: Speeds up Satan level advancement
- **Code**: [src/systems/upgrade_system.py:966-969](src/systems/upgrade_system.py#L966-L969)

#### **BLASPHEMY_5**: Blink Teleport
- **Effect**: SPACEBAR ability — teleport in movement direction
- **Cooldown**: 5 seconds per use
- **Max Levels**: 1 (binary unlock)
- **Mechanics**: Defensive mobility tool, non-upgradeable
- **Code**: [src/systems/upgrade_system.py:970-971](src/systems/upgrade_system.py#L970-L971)
- **Implementation**: [src/systems/blasphemy5_system.py](src/systems/blasphemy5_system.py) (blink teleport mechanics)

#### **BLASPHEMY_6**: Critical Strikes
- **Effect**: +50% damage on crits + crit chance stacking
- **Crit Chance**: +10% per level (max 30% at Lv3)
- **Max Levels**: 3
- **Mechanics**: Multiplicative crit damage scaling
- **Code**: [src/systems/upgrade_system.py:972-975](src/systems/upgrade_system.py#L972-L975)
- **Used by**: [src/systems/collision_system.py:539](src/systems/collision_system.py#L539) (random 10% crit check per level)

#### **BLASPHEMY_7**: Movement Speed Boost
- **Effect**: +10% movement speed per level
- **Max Levels**: 3 (total: +30% speed)
- **Stacking**: Additive speed multiplier
- **Code**: [src/systems/upgrade_system.py:976-979](src/systems/upgrade_system.py#L976-L979)
- **Implementation**: [src/game/core.py:2626](src/game/core.py#L2626) (applied after permanent stats)

#### **BLASPHEMY_8**: Tower Fire Rate Boost
- **Effect**: +20% tower firing speed per level
- **Max Levels**: 3 (total: +60% fire rate for towers)
- **Towers Affected**: Fire, Storm, Ice (all types)
- **Code**: [src/systems/upgrade_system.py:980-983](src/systems/upgrade_system.py#L980-L983)

#### **BLASPHEMY_9**: Upgrade Reroll System
- **Effect**: +2 reroll tokens per level per run
- **Max Levels**: 3 (total: 6 rerolls per run)
- **Mechanic**: Reroll level-up upgrade choices (costs 1 reroll)
- **Code**: [src/systems/upgrade_system.py:984-987](src/systems/upgrade_system.py#L984-L987)
- **Initialization**: [src/game/core.py:2649](src/game/core.py#L2649) (rerolls set on game start)

#### **BLASPHEMY_10**: Revive Once Per Run
- **Effect**: Single revive on death with 50% Max HP restored
- **Max Levels**: 1 (binary unlock)
- **Mechanics**: Non-upgradeable, activates once per run
- **Code**: [src/systems/upgrade_system.py:988-989](src/systems/upgrade_system.py#L988-L989)

---

## ⚔️ Tower Upgrades (Skill Tree Tiers 1-7)
Tower-specific stat bonuses and special abilities, accessed via **skill tree** in Main Menu.

### Tower Types & Tiers
Three tower types (Fire, Storm, Ice) × 7 tiers = **21 unique upgrades**

#### **FIRE TOWER** (fire_X)
- **Tier 1**: Burn spreads on death (chains up to 2 enemies)
- **Tier 2**: Burn duration ×2, burn DPS ×2
- **Tier 3**: +25% damage to burning enemies
- **Tiers 4-6**: +10% dmg, +10% crit chance (stacking)
- **Tier 7**: AR.MAGA.EDDON special — Right-click fires up to 4 burning orbs
- **Code**: [src/systems/upgrade_system.py:1006-1008](src/systems/upgrade_system.py#L1006-L1008)

#### **STORM TOWER** (storm_X)
- **Tier 1**: Chain lightning +2 extra targets
- **Tier 2**: Chain-kills trigger lightning explosion
- **Tier 3**: Chain lightning +2 extra targets (refreshed)
- **Tiers 4-6**: +20% fire rate, +10% crit chance (stacking)
- **Tier 7**: Voltaic Mayhem special — Controllable stream of electric chaos
  - Endpoint moves toward cursor at ~200px/sec
- **Code**: [src/systems/upgrade_system.py:1009-1014](src/systems/upgrade_system.py#L1009-L1014)

#### **ICE TOWER** (ice_X)
- **Tier 1**: Projectiles deal area damage + create slowing puddles
- **Tier 2**: +50% puddle area & area damage radius
- **Tier 3**: Projectiles pierce through enemies
- **Tiers 4-6**: +20% dmg, +10% fire rate (stacking)
- **Tier 7**: Blizzard special — Blizzard puddle spawning at mouse click
- **Code**: [src/systems/upgrade_system.py:1000-1002](src/systems/upgrade_system.py#L1000-L1002)

---

## 🎮 Run-Time Level-Up Upgrades (During Game)

### Category A: Run Stats (available every level-up)
These are temporary, **not persisted** across runs.

1. **Damage +10%** — per-run damage multiplier
2. **Fire Rate +10%** — per-run fire rate multiplier
3. **Max Health +20** — increase player max HP
4. **Movement Speed +5%** — speed multiplier
5. **Health Regen +1 HP/5s** — passive healing
6. **XP +10%** — per-run XP multiplier
7. **Armor +5%** — damage reduction (multiplicative 0.95×)
8. **SHIELD** (max 5 levels) — reduce shield cooldown by 2s per level
   - **Availability**: Only from Limbo onwards (not Prologo)
9. **Projectile Size +10%** — size multiplier
   - **Availability**: Only Hell stages
10. **Tower Fire Rate +10%** — tower fire rate
    - **Availability**: Only Purgatory+ stages
11. **BOOM! (+50 dmg per upgrade)** — explosion on every 10 kills
    - **Availability**: Only Purgatory+ stages

### Category B: Weapon Upgrades (if weapon available)
Each weapon that the player has unlocked can be upgraded to next level (up to Lv6).

**Available weapons shown as level-up options**:
- Hellgun Lv.2 (if player has Hellgun Lv.1)
- Orbitals Lv.3 (if player has Orbitals Lv.2)
- etc.

---

## 📍 Where Upgrades Are Used

### Main Menu (Permanent Upgrades)
- **File**: [src/ui/menus.py](src/ui/menus.py)
- **Drawing**: [src/ui/menus.py:1168-1279](src/ui/menus.py#L1168-L1279) — `_draw_blasphemies()`
- **Tooltips**: Display effect text on hover
- **Cost**: 1 meta_point per purchase (from meta-progression)

### Level-Up Screen
- **File**: [src/systems/upgrade_system.py:89-354](src/systems/upgrade_system.py#L89-L354)
- **Function**: `generate_upgrade_choices()` — generates 3 random run-time upgrades
- **Cost**: Immediate (no currency cost)
- **Applies Immediately**: Selected upgrade effect applied instantly

### Effect Application
- **File**: [src/systems/upgrade_system.py:1062-1093](src/systems/upgrade_system.py#L1062-L1093)
- **Function**: `apply_upgrade()` — applies lambda effect to game state
- **Tracking**: Stored in `self.game.upgrade_levels[upgrade_id]`

### Permanent Stats Application
- **File**: [src/systems/upgrade_system.py](src/systems/upgrade_system.py) (multiple functions)
- **Function**: `apply_permanent_stats()` — applies all `permanent_stats` at game start
- **Triggers**: Called in `_init_managers()` and after loading saves

---

## 💾 Persistence System

### Save Location
- **File**: `permanent_stats.json` (project root)
- **Loaded at**: [src/game/persistence.py:69](src/game/persistence.py#L69)
- **Saved at**: [src/game/persistence.py:115](src/game/persistence.py#L115)

### Structure
```json
{
  "permanent_stats": {
    "power": 1,
    "vigor": 2,
    "adrenaline": 1,
    "structure": 0,
    "blasphemy_1": 2,
    "blasphemy_5": 1,
    "blasphemy_9": 3,
    "fire_1": 1,
    "fire_7": 1,
    "storm_3": 2,
    "ice_2": 1
  },
  "global_progress": {
    "meta_xp": 1250,
    "meta_level": 7,
    "meta_points": 4,
    "stages_cleared": { "prologo": true, "limbo": true, "limbo_2": true }
  }
}
```

---

## 🔄 Summary Table

| Upgrade Type | Count | Max Level | Persistence | Stage-Specific |
|---|---|---|---|---|
| **Base Stats** (Power/Vigor/etc.) | 4 | 3 | ✅ YES | ❌ No |
| **Blasphemies** | 10 | 3 (1 or binary) | ✅ YES | ❌ No |
| **Tower Tiers** | 21 | 7 | ✅ YES | ❌ No |
| **Run Upgrades** | 11 | 1-5 | ❌ NO | ✅ Yes (some) |
| **Weapon Upgrades** | ~6 per run | 6 | ❌ NO (per-run) | ❌ No |

**Total Permanent Upgrades**: 35 (4 base + 10 blasphemy + 21 tower)

---

## 🎯 Stage Availability for Run-Time Upgrades

| Upgrade | Prologo | Limbo | Purgatory | Hell |
|---|---|---|---|---|
| Damage +10% | ✅ | ✅ | ✅ | ✅ |
| Fire Rate | ✅ | ✅ | ✅ | ✅ |
| Max Health | ✅ | ✅ | ✅ | ✅ |
| Movement Speed | ✅ | ✅ | ✅ | ✅ |
| Health Regen | ✅ | ✅ | ✅ | ✅ |
| XP Multiplier | ✅ (66% chance) | ✅ (66%) | ✅ (66%) | ✅ (66%) |
| Armor | ✅ | ✅ | ✅ | ✅ |
| **SHIELD** | ❌ | ✅ | ✅ | ✅ |
| **Projectile Size** | ❌ | ❌ | ❌ | ✅ |
| **Tower Fire Rate** | ❌ | ❌ | ✅ | ✅ |
| **BOOM!** | ❌ | ❌ | ✅ | ✅ |

