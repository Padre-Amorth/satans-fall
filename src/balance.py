"""Centralized balance and gameplay tuning parameters."""

# XP progression (per-run leveling) - tiered growth curve
# Levels 1-10: 1.2 growth (standard)
# Levels 11-15: 1.15 growth (slower)
# Levels 16-20: 1.10 growth (even slower)
# Levels 21+: 1.08 growth (gentler high-level grind)
XP_BASE: int = 100
XP_GROWTH: float = 1.2  # Used for levels 1-10


def calculate_xp_for_next_level(level: int) -> int:
    """Calculate XP required to reach next level using tiered growth curve.

    Args:
        level: Current player level (1-based)

    Returns:
        XP required to reach (level + 1)
    """
    next_level = level + 1

    if next_level <= 10:
        # Levels 1-10: standard 1.2 growth
        return int(XP_BASE * (1.2 ** (next_level - 1)))
    elif next_level <= 15:
        # Levels 11-15: 1.15 growth
        xp_at_10 = int(XP_BASE * (1.2**9))
        extra = next_level - 10
        return int(xp_at_10 * (1.15**extra))
    elif next_level <= 20:
        # Levels 16-20: 1.10 growth
        xp_at_10 = int(XP_BASE * (1.2**9))
        xp_at_15 = int(xp_at_10 * (1.15**5))
        extra = next_level - 15
        return int(xp_at_15 * (1.10**extra))
    else:
        # Levels 21+: 1.08 growth
        xp_at_10 = int(XP_BASE * (1.2**9))
        xp_at_15 = int(xp_at_10 * (1.15**5))
        xp_at_20 = int(xp_at_15 * (1.10**5))
        extra = next_level - 20
        return int(xp_at_20 * (1.08**extra))


# Meta‑progression (separate from per-run XP)
# Used for permanent upgrade currency. Goals grow more steeply; players no
# longer earn meta XP directly from score.  Instead XP must be granted
# explicitly via game events or debug commands.
META_XP_BASE: int = (
    10_000  # XP required for the first meta level (previously 1_000, was 100_000 before tuning)
)
META_XP_GROWTH: float = (
    1.2  # per-level multiplier for subsequent levels (lowered from 1.3 for gentler curve)
)

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
BASE_SPAWN_RATE: int = 80  # increased from 72 to reduce spawn frequency (fewer enemies)
SPAWN_MIN_RATE: int = 30
SPAWN_RAMP_START_WAVE: int = 3
SPAWN_RAMP_SLOPE_PRE: int = 3
SPAWN_RAMP_SLOPE_POST: float = (
    3.8  # reduced from 4.2 to slow spawn acceleration in later waves
)

# Limbo-specific spawn slowdown: adds frames between spawns so each 10s
# period contains roughly two fewer enemies than normal.
LIMBO_SPAWN_RATE_PENALTY: int = 8

# Difficulty scaling
DIFFICULTY_MULTIPLIER_PER_WAVE: float = (
    0.12  # added per‑wave increment for difficulty multiplier
)
# Limbo stages are slightly easier per wave to compensate for the huge horde
# event and slower pacing; this slope only applies to limbo/limbo_2/limbo_3.
LIMBO_DIFFICULTY_MULTIPLIER_PER_WAVE: float = 0.11

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
    # special limbo horde boss moves a bit faster than the regular final boss
    "boss_limbo_horde": 45.0,
    # new fast zig-zagging flying enemy
    "winged": 120.0,
    "archer": 40.0,  # slow-moving ranged enemy confined to top of screen
    # Crusader is extremely slow, slower than a giant
    "crusader": 30.0,
    "pentagram": 50.0,  # slow horizontal traversal tank
    "pentagram_fire": 50.0,
    "pentagram_storm": 50.0,
    "pentagram_ice": 50.0,
    "cross_bearer": 40.0,  # shield-reflecting enemy, Hell+ only
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

# Scoring
# points awarded per unit of enemy health (before difficulty multiplier)
ENEMY_SCORE_PER_HEALTH: float = (
    0.35  # reduced from 18.0 to lower all enemy kill rewards dramatically
)
