# Satan's Fall — Guida Armi e Upgrade

## 🎯 Armi Disponibili (9 totali)

### Prologo (6 armi base)
1. **Hellgun** (shotgun)
   - Fires multiple pellets in a spread pattern
   - Lv1: 4 pellets → Lv6: 6 pellets + max damage
   - Base CD: 1.5s, reduces with level upgrades
   - **Where**: src/weapons.py lines 7-126

2. **Orbitals** (orbital)
   - Summon orbiting sentinels that auto-fire
   - Lv1: 3 orbitals → Lv6: 5 orbitals
   - +10% damage per 2 levels
   - **Where**: src/weapons.py lines 21-33

3. **Spear** (spear)
   - Pierces through multiple enemies
   - Lv1-Lv6: +2 base damage per level
   - Consistent pierce mechanic
   - **Where**: src/weapons.py lines 35-47

4. **The number of the beast** (beast)
   - Unleash demonic power with devastating attacks
   - Lv1-Lv6: +5% damage & faster burst rate per level
   - Pure damage/DPS scaling
   - **Where**: src/weapons.py lines 64-76

5. **SkullBoom** (skullboom)
   - Launches explosive skulls that detonate on enemy contact
   - Lv1-Lv6: alternates +damage/cooldown and +radius
   - Area damage mechanic
   - **Where**: src/weapons.py lines 78-90

6. **Hidden upgrade in Prologo** (?)

---

### Limbo+ (Available from Limbo stage)
7. **Flies** (Flies)
   - Fires homing projectiles that latch onto enemies and heal the player
   - Lv1: 2 projectiles → Lv5+: 4 projectiles
   - Heal scaling: +10-20% per level
   - **Cannot be obtained in Prologo, only from Limbo onwards**
   - **Where**: src/weapons.py lines 49-62

---

### Purgatory+ (Available from Purgatory stage)
8. **DemonStrike** (DemonStrike)
   - A rolling bowling ball that travels vertically, pierces enemies and slows them
   - Lv1: Slows 50% for 2s
   - Lv2-Lv6: +10 base damage per level
   - Excellent crowd control + damage scaling
   - **Where**: src/weapons.py lines 92-105

---

### Hell+ (Available from Hell stage)
9. **Tenebrae** (tenebrae)
   - Arc of shadows that pierces enemies, losing power with each hit
   - Lv1: Base damage 25, -20% decay per enemy hit
   - Lv2-Lv6: +5 damage, reduced cooldown, -2% decay reduction
   - Piercing shadow arc with diminishing returns per target
   - **Where**: Not yet visible in current read (continues in weapons.py)

---

## 📊 Weapon Availability by Stage

| Stage | Available Weapons |
|-------|---|
| **Prologo** | Hellgun, Orbitals, Spear, Beast, SkullBoom, (1 hidden) |
| **Limbo** | ↑ + Flies |
| **Purgatory** | ↑ + DemonStrike |
| **Hell** | ↑ + Tenebrae |

**How it works**:
- [game_state.py:480](src/game_state.py#L480) manages weapon selection via `generate_initial_weapon_choices()`
- Availability checked by weapon `available_from` key in WEAPON_DEFS
- Random selection from eligible weapons at each level-up

---

## 🏰 Towers (Defensive Statues)

### Tower Types (3 total)

1. **Fire Tower** (fire_statue)
   - Base: 10 damage, 85 fire rate
   - **Special Effect**: BURN (DOT) on hit
   - Burn duration: 180 frames (~3 seconds)
   - Scales burn DPS with tower damage upgrades
   - **Where**: [src/core/entities/tower.py:77-141](src/core/entities/tower.py#L77-L141)

2. **Storm Tower** (storm_statue)
   - Base: 10 damage (fires at 90%), 85 fire rate
   - **Special Effect**: CHAIN-HITS up to 3 different enemies
   - Single aimed projectile (dark-blue appearance)
   - Zero spread when targeting bosses
   - **Where**: [src/core/entities/tower.py:143-184](src/core/entities/tower.py#L143-L184)

3. **Ice Tower** (ice_statue)
   - Base: 15 damage (highest defensive power), 85 fire rate
   - **Special Effect**: SLOW effect on hit
   - Reduces enemy movement speed
   - Blizzard puddle spawning (with ice_7 upgrade)
   - **Where**: [src/core/entities/tower.py:186+](src/core/entities/tower.py#L186)

### Tower Upgrade System

**Placement**: Left/Right tower placement during game
- Players can select which tower type to place
- Can be placed on both left AND right defensive positions

**Tower _7 Special Upgrades**:
- **fire_7**: Enhanced burn mechanics (unlocked as permanent upgrade)
- **storm_7**: Hellectric Flux activation (right-click special)
- **ice_7**: Blizzard puddle spawning at mouse position (right-click special)

**Where Placed**: [src/game/core.py:390](src/game/core.py#L390) - `activate_tower_special()`
- Routes tower special effects based on `placed_types` set
- Both towers can activate simultaneously if both _7 upgrades are unlocked

---

## ⚡ Permanent Upgrades (Meta Progression)

**Location**: Main Menu (gear icon bottom-right)
- Purchased with meta-progression currency (meta_points)
- Persist across runs via `permanent_stats.json`

| Category | Upgrade Examples | Effect |
|----------|---------|--------|
| **Damage** | damage_1, damage_2, ... | +% total damage scaling |
| **Health** | max_health_1, max_health_2, ... | +% maximum HP |
| **Armor** | armor_1, armor_2, ... | +% damage reduction |
| **Speed** | speed_1, speed_2, ... | +% movement speed |
| **Cooldown** | cooldown_1, cooldown_2, ... | -% weapon cooldown |
| **Tower** | fire_tower, storm_tower, ice_tower | Unlock defensive tower placement |
| **Special** | blasphemy_6, adrenaline | Meta-progression unlock abilities |

**Where Managed**:
- [src/systems/upgrade_system.py](src/systems/upgrade_system.py) - upgrade logic
- [src/game_state.py:57-63](src/game_state.py#L57-L63) - upgrade_levels tracking
- [src/persistence.py](src/game/persistence.py) - save/load system

---

## 🎮 Weapon Balance by Stage

### Prologo (Basic Arsenal)
- **Hellgun**: Safe, consistent AoE damage spread
- **Spear**: Pure pierce damage, skill-focused
- **SkullBoom**: AOE control via explosion scaling
- **Orbitals**: Passive DPS, good for learning
- **Beast**: Pure DPS ramping via burst rate

### Limbo (Adding Support)
- **Flies**: Healing support, homing advantage
- + All Prologo weapons

### Purgatory (Control Focus)
- **DemonStrike**: Crowd control + damage ramping
- Excellent for slowing large groups (Purgatory horde)
- + All prior weapons

### Hell (Advanced Risk/Reward)
- **Tenebrae**: Risk/reward pierce with decay penalty
- Requires target management (decay scales inversely)
- + All prior weapons

---

## 📍 Weapon System Implementation

### Where Weapons Are Used

| Component | Location | Purpose |
|-----------|----------|---------|
| **Definitions** | [src/weapons.py](src/weapons.py) | WEAPON_DEFS dict with all metadata |
| **Level-up Selection** | [src/game_state.py](src/game_state.py) | `generate_initial_weapon_choices()` |
| **Weapon Tracking** | [src/game/core.py](src/game/core.py) | `self.weapon_levels` dict |
| **Firing System** | [src/systems/weapon_system.py](src/systems/weapon_system.py) | Projectile spawning logic |
| **UI Rendering** | [src/ui/renderer.py](src/ui/renderer.py) | Weapon icons and descriptions |
| **Upgrade Effects** | [src/systems/upgrade_system.py](src/systems/upgrade_system.py) | Apply level-based bonuses |

### Level-Up Flow
1. Enemy killed → XP awarded
2. Player reaches next level
3. `await_weapon_choice = True` flag set
4. Random 3 weapons selected from `available_from` stage
5. Player selects one
6. Weapon added to `player_weapons` list
7. `weapon_levels[weapon_name]` incremented

### Firing Flow
1. Player input (left-click or auto-fire)
2. WeaponSystem checks `weapon_levels[weapon_name]`
3. Projectile parameters scaled based on level
4. Projectile spawned with calculated damage/speed/count

---

## 💾 Persistence System

**Save File**: `permanent_stats.json` (project root)

**Tracks**:
- `meta_xp`: Accumulated meta-progression XP
- `meta_level`: Player's "Satan level" (displayed in main menu)
- `meta_points`: Currency for buying permanent upgrades
- `stages_cleared`: Dict tracking which stages completed
- Individual upgrade purchases: `damage_1`, `max_health_2`, etc.

**Load**: Called in [src/game/core.py](src/game/core.py) `_init_managers()`
- Fills missing keys with `setdefault`
- Zero impact on current run (pure meta-progression)

---

## 🔄 References in Code

### Where to Look for Changes
- **New weapon**: Edit [src/weapons.py](src/weapons.py) WEAPON_DEFS dict
- **Weapon balance**: [src/weapons.py](src/weapons.py) `*_damage()` functions + level multipliers
- **Tower balance**: [src/core/entities/tower.py](src/core/entities/tower.py) damage/fire_rate
- **Permanent upgrades**: [src/systems/upgrade_system.py](src/systems/upgrade_system.py)
- **Selection logic**: [src/game_state.py](src/game_state.py) weapon choice generation

