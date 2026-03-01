# Satan's Roguelite - Vampire Survivors Style

[![CI](https://github.com/YOUR_GITHUB_USER/YOUR_REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_GITHUB_USER/YOUR_REPO/actions/workflows/ci.yml) <!-- Replace YOUR_GITHUB_USER/YOUR_REPO with your GitHub repository path -->

A fun roguelite game where you play as Satan, fighting off waves of demons from the bottom of the screen!

> ⚠️ **Note:** Progress is **not persisted** between runs or when exiting the game. Each time you launch, the player starts from scratch.

## Installation

1. Make sure you have Python 3.7+ installed
2. Install pygame:
```bash
pip install -r requirements.txt
```

## How to Play

- **Left/A**: Move left
- **Right/D**: Move right
- **ESC**: Pause/Resume
- Stay at the bottom of the screen and dodge incoming demons
- Automatically shoot holy fire at enemies above you
- Survive as many waves as possible to increase your score
- Each wave gets harder with more enemies and increased enemy health (movement speeds are controlled by `ENEMY_BASE_SPEEDS` in `src/balance.py`)

## Running the Game

```bash
python main_pygame.py
```

Debug CLI flags (developer shortcuts):

- `--fast-forward-prologo`, `--ff-prologo` — Auto-select **Prologo** and advance time so the final boss spawns immediately (useful for testing boss behavior).


Additionally, a standalone utility script has been added for finer control:

    tools/ff_to_time.py

This can fast‑forward any stage to an arbitrary elapsed time (seconds or `MM:SS`).
Example: `python tools/ff_to_time.py --stage limbo --time 7:30` will jump into the
first Limbo level at 7 minutes 30 seconds.

This tool can of course be used alongside the normal game logic; no special
flags are required.  (The previous developer toggle for disabling the
horde explosion has been removed because the feature was obsoleted.)
- `--ff-prologo-force-lightning`, `--ff-prologo-lightning` — In addition to the above, force the final boss into the immortal regen state and trigger the holy light strike so you can reproduce prologo-specific holy light effects/crashes.

## Development

The project uses a modular Pygame architecture with separate components:

- `src/entities/player.py` - Player character logic (moved from `src/player.py`)
- `src/game.py` - Core game mechanics
- `src/enemy.py` - Enemy spawning and AI
- `src/projectile.py` - Weapon and projectile systems
- `src/ui.py` - User interface rendering

This modular structure makes it easier to:
1. Test individual components
2. Maintain and extend the codebase

### Setup: pre-commit & ruff
We use `ruff` as the project linter/formatter and `pre-commit` to run it automatically before each commit.

Quick setup (recommended):

```bash
# install dev tools
pip install -r requirements-dev.txt

# install pre-commit hooks (one-time)
pre-commit install

# run hooks on all files (optional, useful the first time)
pre-commit run --all-files

# or use helper scripts
# Windows PowerShell (from repo root):
#   .\scripts\setup_dev.ps1
# Unix / WSL / MacOS:
#   ./scripts/setup_dev.sh
```

The included `.pre-commit-config.yaml` will run `ruff --fix` on changed files so formatting and simple lint issues are fixed before commit.

## Game Features

- **Satan Character**: Custom drawn character with horns and evil grin at bottom of screen
- **Wave System**: Game gets progressively harder with each wave
- **Difficulty Scaling**: Enemies get stronger as waves progress
- **Score System**: Earn points by defeating enemies
- **Health System**: Take damage from enemy contact and projectiles, game ends when health reaches 0
- **Auto-Attack**: Automatically shoot projectiles upward
- **Dynamic Enemy Spawning**: Enemies spawn from all sides of the screen
- **XP and Leveling**: Gain experience from defeated enemies, level up automatically
- **Weapon System**: Choose from 3 powerful weapons every 3 levels:
  - Each selection box now reserves a small icon area on the left; designers
    can place weapon artwork in `assets/weapon_<id>.png` and configure the
    corresponding `icon` field in `src/weapons.py`.
  - **Orbitals**: Summon orbiting sentinels that auto-target enemies
  - **Shotgun**: Fire spread of pellets with cooldown
  - **Spear**: Piercing spear that hits all enemies in path

- **Statues / Towers (Limbo / Purgatory)**: Base projectile damage **10** —
  - **Fire**: deals 10 damage and applies Burn (4 DPS for 3s)
  - **Storm**: deals ~9 projectile damage and chains between enemies. Left-column STORM permanents: slots 1 & 3 grant **+2 chained targets** each; slot 2 causes **chain-kills to explode in a lightning burst** that damages nearby enemies (chain-target total stacks up to **+4** when both slots 1 & 3 are active).
  - **Ice**: deals 10 damage and applies a 50% slow for 2s

- **Upgrade System**: Choose from 6 different upgrades every level with visual icons:
  - Damage +20% (damage icon)
  - Fire Rate +15% (fire rate icon)
  - Projectile Size +10% (area icon)
  - Damage Reduction +10% (piercing icon)
  - Max Health +20 (bounce icon)
  - Speed +20% (speed icon)

  - **Permanent Upgrades — POWER:** increases player damage **+5% per level** (was +3%); reflected in UI and tests.
- **Multiple Enemy Types**:
  - Weak demons (blue angels)
  - Normal demons (white angels)
  - Strong demons (golden archangels)
  - Angel flyers (special winged enemies)
  - Giant demons (spawn every 12 seconds)
- **Boss Battles**: Four types of bosses spawn every 3 waves:
  - Small boss
  - Medium boss (violet)
  - Big boss (divine figure)
  - Final boss (large divine figure)
- **Enemy Projectiles**: Angels and bosses shoot homing projectiles at the player
- **Asset Loading**: Uses PNG images from assets/ folder for enhanced visuals (stage‑specific backgrounds such as limbo or purgatory can also be added)

- **Wall color**: all stages now use a consistent dark gray wall color, replacing earlier stage‑specific hues.
- **Purgatory fog**: every Purgatory variant draws a semi‑transparent gray overlay
  to create a hazy atmosphere; no extra assets required.  The opacity and
  color of this overlay are set via constants (`PURGATORY_OVERLAY_ALPHA` and
  `PURGATORY_OVERLAY_COLOR` in `src/game_constants.py`), so you can make the
  effect as light or heavy as you like.  (The previous particle effect has been
  removed.)
  A dynamic fog particle system now runs in Purgatory.  A fixed number of
  semi‑transparent fog blobs slowly drift across the stage with gentle
  vertical oscillation, wrapping horizontally when they reach the edge.  You
  can adjust the particle count, texture size, speed range, oscillation
  amplitude, color and opacity via the `FOG_*` constants in
  `src/game_constants.py`.
- **Periodic Giant Spawns**: Giant enemies spawn every 12 seconds for added challenge
- **Burst Fire Mechanics**: Basic weapon fires in bursts for tactical gameplay

## Game Mechanics

- **Waves**: Last 60 seconds each
- **Enemy Spawn Rate**: Increases difficulty over time
- **Difficulty Multiplier**: Health and speed increase with each wave
- **Score Multiplier**: Points earned scale with difficulty

## Controls

- Move left: LEFT ARROW or A
- Move right: RIGHT ARROW or D
- Pause: ESC
  - Note: The **Restart** option has been removed from the Pause menu (only Resume and Quit remain).
- Game Over behavior: Pressing ENTER/SPACE no longer restarts a level; press **ESC** to return to the stage menu.
- During upgrade selection:
  - LEFT/RIGHT arrows: Select upgrade (shown with icons)
  - ENTER: Confirm selection
- During weapon selection (every 3 levels):
  - LEFT/RIGHT arrows: Select weapon
  - ENTER: Confirm selection

The game supports custom PNG assets in the `assets/` folder. See `ASSETS_INFO.md` for details on supported image files and their recommended dimensions.
