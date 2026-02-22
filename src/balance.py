"""Centralized balance and gameplay tuning parameters."""

# XP progression (per-run leveling)
XP_BASE: int = 100
XP_GROWTH: float = 1.2

# Meta‑progression (separate from per-run XP)
# Used for permanent upgrade currency. Goals grow more steeply; players no
# longer earn meta XP directly from score.  Instead XP must be granted
# explicitly via game events or debug commands.
META_XP_BASE: int = 100_000  # XP required for the first meta level (previously 1_000)
META_XP_GROWTH: float = 1.3  # per-level multiplier for subsequent levels

# Player defaults
PLAYER_BASE_DAMAGE: int = 30  # doubled from 15 to increase base weapon damage
PLAYER_BASE_HEALTH: int = 100

# Burst / Beast weapon defaults
BURST_FIRE_RATE: int = 15
BURST_MAX: int = 3
BURST_PAUSE: int = 60

# Statue (limbo) defaults
STATUE_FIRE_RATE: int = 85  # cooldown set to 85 (applied to both statues and towers)

# Spawning / waves
BASE_SPAWN_RATE: int = 72
SPAWN_MIN_RATE: int = 30
SPAWN_RAMP_START_WAVE: int = 3
SPAWN_RAMP_SLOPE_PRE: int = 3
SPAWN_RAMP_SLOPE_POST: float = (
    4.2  # more gradual ramp so spawn_min_rate is reached ~wave 10
)

# Enemy base movement speeds (px/sec) - single source of truth for spawn code
ENEMY_BASE_SPEEDS: dict[str, float] = {
    "weak": 35.0,
    "normal": 75.0,
    "strong": 60.0,
    "angel": 60.0,
    "giant": 45.0,
    # Bosses
    "boss_medium": 45.0,
    "boss_inquisitor": 50.0,
    "boss_big": 40.0,
    "boss_final": 40.0,
}


# Reinforcements
REINFORCEMENT_DELAY_MS: int = 2000
REINFORCEMENT_COUNT: int = 8

# Projectile / game scaling defaults
DEFAULT_PROJECTILE_SIZE_MULTIPLIER: float = 1.0
DEFAULT_FIRE_RATE_MULTIPLIER: float = 1.0
DEFAULT_DAMAGE_REDUCTION_MULTIPLIER: float = 1.0

# Misc
MAX_EXTRA_WEAPONS: int = 3
GAME_OVER_FADE_DURATION_MS: int = 900
