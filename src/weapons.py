"""Centralized weapon definitions and helper utilities."""

from typing import Dict, List

# Centralized weapon definitions to avoid duplication across modules
WEAPON_DEFS: Dict[str, Dict] = {
    "shotgun": {
        "name": "Hellgun",
        "description": "Fires multiple pellets in a spread pattern",
        "max_level": 6,
        "upgrade_descriptions": {
            1: "Lv1: Fires 4 pellets in a spread pattern",
            2: "Lv2: +1 pellet and reduced cooldown",
            3: "Lv3: +10% pellet damage",
            4: "Lv4: +1 pellet (now 6)",
            5: "Lv5: +10% pellet damage",
            6: "Lv6: Max level — larger spread and highest damage",
        },
    },
    "orbital": {
        "name": "Orbitals",
        "description": "Summon orbiting sentinels that auto-fire",
        "max_level": 6,
        "upgrade_descriptions": {
            1: "Lv1: 3 orbitals that auto-fire",
            2: "Lv2: +1 orbital",
            3: "Lv3: +10% orbital damage",
            4: "Lv4: +1 orbital",
            5: "Lv5: +10% orbital damage",
            6: "Lv6: +1 orbital",
        },
    },
    "spear": {
        "name": "Spear",
        "description": "Pierces through multiple enemies",
        "max_level": 6,
        "upgrade_descriptions": {
            1: "Lv1: Fires piercing spears",
            2: "Lv2: +2 base damage",
            3: "Lv3: +2 base damage",
            4: "Lv4: +2 base damage",
            5: "Lv5: +2 base damage",
            6: "Lv6: Max level",
        },
    },
    "Soul Drain": {
        "name": "Soul Drain",
        "description": "Fires homing soul projectiles that drain life from enemies and heal the player",
        "max_level": 6,
        "available_from": "limbo",  # Not available in Prologo; available from Limbo onwards
        "upgrade_descriptions": {
            1: "Lv1: Fires 2 homing projectiles that drain HP and heal the player",
            2: "Lv2: +1 projectile",
            3: "Lv3: +10% damage & heal",
            4: "Lv4: +1 projectile",
            5: "Lv5: +10% damage & heal",
            6: "Lv6: Can bounce",
        },
    },
    "beast": {
        "name": "The number of the beast",
        "description": "Unleash demonic power with devastating attacks",
        "max_level": 6,
        "upgrade_descriptions": {
            1: "Lv1: +5% damage and increased burst rate",
            2: "Lv2: +5% damage and faster burst rate",
            3: "Lv3: +5% damage and faster burst rate",
            4: "Lv4: +5% damage and faster burst rate",
            5: "Lv5: +5% damage and faster burst rate",
            6: "Lv6: +5% damage and maximum burst rate",
        },
    },
    "skull_bomb": {
        "name": "Skull Bomb",
        "description": "Launches explosive skulls that detonate on enemy contact, dealing area damage",
        "max_level": 6,
        "upgrade_descriptions": {
            1: "Lv1: Launches explosive skulls",
            2: "Lv2: +10% damage and reduced cooldown",
            3: "Lv3: +10% explosion radius",
            4: "Lv4: +10% damage and reduced cooldown",
            5: "Lv5: +10% explosion radius",
            6: "Lv6: Max level",
        },
    },
    "DemonStrike": {
        "name": "DemonStrike",
        "description": "A rolling bowling ball — travels vertically, pierces enemies and slows them",
        "max_level": 6,
        "available_from": "purgatory",  # only available from Purgatory stages onwards
        "upgrade_descriptions": {
            1: "Lv1: Fires a piercing rolling ball that slows enemies (50% for 2s)",
            2: "Lv2: +10 base damage",
            3: "Lv3: +10 base damage",
            4: "Lv4: +10 base damage",
            5: "Lv5: +10 base damage",
            6: "Lv6: Max level",
        },
    },
}

# Additional weapon-specific parameters (cooldowns, counts, damage factors)
WEAPON_DEFS["shotgun"].update(
    {
        "base_pellets": 4,
        "pellet_level_step": 2,
        "pellet_increase": 1,
        "spread_deg": 12,
        "damage_mult": 0.55,
        "base_cd": 1.5,
        "cd_reduction_per_pair": 0.15,
        "min_cd": 0.4,
        "base_radius": 5,
    }
)

WEAPON_DEFS["orbital"].update(
    {
        "base_count": 3,
        "extra_per_pair": 1,
        "cooldown_base_min": 40,
        "cooldown_base_max": 100,
        "cooldown_reduction_per_pair": 6,
    }
)

WEAPON_DEFS["spear"].update(
    {
        "base_cd": 0.6,
        "cd_reduction_per_level": 0.06,
        "min_cd": 0.15,
        "damage_base_mult": 0.5,
        "damage_per_level": 2,
        "speed_factor": 800 / 500.0,
        "base_radius": 5,
    }
)

# DemonStrike tuning (custom scaling & visuals)
WEAPON_DEFS["DemonStrike"].update(
    {
        # Cooldown tuned similar to skull_bomb but slightly *shorter* (more frequent)
        "base_cd": 1.8,  # Skull Bomb = 2.0 -> DemonStrike slightly more often
        "cd_reduction_per_level": 0.12,
        "min_cd": 0.5,
        "damage_base_mult": 0.5,  # retains player-damage component multiplier
        "damage_per_level": 10,  # <-- now +10 damage per weapon level
        # Much slower than spear: emulate a rolling bowling ball
        "speed_factor": 120 / 500.0,
        "base_radius": 8,  # kept for backward compatibility (rounded)
        "base_diameter": 15,  # requested base diameter in pixels
        "radius_increase_per_level": 4,  # +4 pixels per upgrade level
    }
)

WEAPON_DEFS["Soul Drain"].update(
    {
        "base_cd": 1.5,
        "cd_reduction_at_level_4": 0.3,
        "min_cd": 0.5,
        "base_damage": 10,  # doubled from 5
        "base_heal": 2,
        "damage_heal_increments": {
            3: 0.1,
            5: 0.1,
        },  # Base projectiles increased to 2 (Lv1 fires 2 projectiles).
        # Additional projectiles at level thresholds add 1 projectile each.
        "base_projectiles": 2,
        "projectiles_at_level": {
            2: 1,
            4: 1,
        },  # level -> extra projectiles (increments at thresholds)
    }
)

WEAPON_DEFS["beast"].update(
    {
        "burst_rate_multiplier_per_level": 0.05,
    }
)

WEAPON_DEFS["skull_bomb"].update(
    {
        "base_cd": 2.0,
        "cd_reduction_per_level": 0.15,
        "min_cd": 0.5,
        "base_damage": 20,
        "damage_increase_per_level": 2,
        "base_explosion_radius": 80,
        "radius_increase_per_level": 8,
    }
)


def get_orbital_count(level: int) -> int:
    base = WEAPON_DEFS.get("orbital", {}).get("base_count", 3)
    extra = (level // 2) * WEAPON_DEFS.get("orbital", {}).get("extra_per_pair", 1)
    return base + extra


def orbital_cooldown_range(level: int) -> tuple[int, int]:
    d = WEAPON_DEFS.get("orbital", {})
    reductions = level // 2
    base_min = d.get("cooldown_base_min", 40)
    base_max = d.get("cooldown_base_max", 100)
    min_cd = max(10, base_min - reductions * d.get("cooldown_reduction_per_pair", 6))
    max_cd = max(
        min_cd + 5,
        base_max - reductions * (d.get("cooldown_reduction_per_pair", 6) * 2),
    )
    return int(min_cd), int(max_cd)


def shotgun_pellets(level: int) -> int:
    d = WEAPON_DEFS.get("shotgun", {})
    base = d.get("base_pellets", 4)
    step = d.get("pellet_level_step", 2)
    inc = d.get("pellet_increase", 1)
    return base + (level // step) * inc


def shotgun_cooldown(level: int) -> float:
    d = WEAPON_DEFS.get("shotgun", {})
    base_cd = d.get("base_cd", 1.5)
    reductions = level // 2
    cd = base_cd - reductions * d.get("cd_reduction_per_pair", 0.15)
    return max(d.get("min_cd", 0.4), cd)


def spear_cooldown(level: int) -> float:
    d = WEAPON_DEFS.get("spear", {})
    base_cd = d.get("base_cd", 0.6)
    cd = base_cd - level * d.get("cd_reduction_per_level", 0.06)
    return max(d.get("min_cd", 0.15), cd)


def DemonStrike_cooldown(level: int) -> float:
    """Cooldown for DemonStrike — uses DemonStrike-specific tuning from WEAPON_DEFS."""
    d = WEAPON_DEFS.get("DemonStrike", {})
    base_cd = d.get("base_cd", 1.8)
    cd = base_cd - level * d.get("cd_reduction_per_level", 0.12)
    return max(d.get("min_cd", 0.5), cd)


def soul_drain_cd(level: int) -> float:
    d = WEAPON_DEFS.get("Soul Drain", {})
    base_cd = d.get("base_cd", 1.5)
    if level >= 4:
        base_cd -= d.get("cd_reduction_at_level_4", 0.3)
    return max(d.get("min_cd", 0.5), base_cd)


def soul_drain_projectile_count(level: int) -> int:
    d = WEAPON_DEFS.get("Soul Drain", {})
    # Base projectiles now come from definition (default 2)
    base = d.get("base_projectiles", 2)
    extra = 0
    proj_map = d.get("projectiles_at_level", {})
    for thresh, extra_n in proj_map.items():
        if level >= thresh:
            extra += extra_n
    return base + extra


def soul_drain_damage_heal_mult(level: int) -> tuple[float, float]:
    d = WEAPON_DEFS.get("Soul Drain", {})
    incs = d.get("damage_heal_increments", {})
    mult = 1.0
    for thresh, inc in incs.items():
        if level >= thresh:
            mult += inc
    return mult, mult


def skull_bomb_cooldown(level: int) -> float:
    d = WEAPON_DEFS.get("skull_bomb", {})
    base_cd = d.get("base_cd", 2.0)
    cd = base_cd - (level - 1) * d.get("cd_reduction_per_level", 0.15)
    return max(d.get("min_cd", 0.5), cd)


def skull_bomb_damage(level: int) -> int:
    d = WEAPON_DEFS.get("skull_bomb", {})
    base_damage = d.get("base_damage", 20)
    damage = base_damage + (level - 1) * d.get("damage_increase_per_level", 2)
    return int(damage * 1.2)  # 20% damage increase


def skull_bomb_explosion_radius(level: int) -> int:
    d = WEAPON_DEFS.get("skull_bomb", {})
    base_radius = d.get("base_explosion_radius", 50)
    return base_radius + (level - 1) * d.get("radius_increase_per_level", 5)


def get_weapon_definitions() -> List[Dict[str, str]]:
    """Return list of basic weapon choice dicts used by UIs and game logic."""
    return [
        {"id": wid, "name": d["name"], "description": d["description"]}
        for wid, d in WEAPON_DEFS.items()
    ]


def get_weapon_upgrade_description(weapon: str, level: int) -> str:
    """Get a human-readable description for a weapon upgrade to given level.

    This function first attempts to return the explicit description from
    WEAPON_DEFS[weapon]["upgrade_descriptions"]. If not present, it will
    try to normalize common naming differences (e.g., 'soul_drain' -> 'Soul Drain')
    and finally attempt to infer a useful description from known weapon params
    (like projectile counts or damage increments) rather than returning a
    generic fallback.
    """
    # Direct lookup
    w = WEAPON_DEFS.get(weapon)

    # Try normalized variants (underscore -> space, title case)
    if w is None:
        alt = weapon.replace("_", " ").title()
        w = WEAPON_DEFS.get(alt)
        if w is not None:
            weapon = alt

    # Case-insensitive match
    if w is None:
        for k, v in WEAPON_DEFS.items():
            if k.lower() == weapon.lower():
                w = v
                weapon = k
                break

    if not w:
        return f"Upgrade to level {level}"

    upd = w.get("upgrade_descriptions", {})
    if level in upd:
        return upd[level]

    # Inference fallback: try to construct a useful description based on known params
    try:
        if weapon.lower() in ("shotgun",):
            pellets = shotgun_pellets(level)
            cd = shotgun_cooldown(level)
            return f"Lv{level}: Fires {pellets} pellets (cooldown ~{cd:.2f}s)"

        if weapon.lower() in ("orbital", "orbitals"):
            cnt = get_orbital_count(level)
            return f"Lv{level}: {cnt} orbitals that auto-fire"

        if weapon.lower() in ("soul drain", "soul_drain", "souldrain", "soul drain"):
            projs = soul_drain_projectile_count(level)
            dmg_mult, heal_mult = soul_drain_damage_heal_mult(level)
            parts = [f"Lv{level}: Fires {projs} homing projectiles"]
            if abs(dmg_mult - 1.0) > 1e-6:
                parts.append(f"Damage & heal x{dmg_mult:.2f}")
            if level >= 6:
                parts.append("Can bounce on hit")
            return "; ".join(parts)

        if weapon.lower() in ("spear",):
            # Spear: +2 base damage per level
            return f"Lv{level}: +{2 * level} base spear damage total (rough guide)"

        if weapon.lower() in ("demonstrike",):
            # DemonStrike: +10 base damage per level
            return (
                f"Lv{level}: +{10 * level} base DemonStrike damage total (rough guide)"
            )

        if weapon.lower() in ("skull_bomb", "skull bomb", "skullbomb"):
            cd = skull_bomb_cooldown(level)
            dmg = skull_bomb_damage(level)
            radius = skull_bomb_explosion_radius(level)
            return f"Lv{level}: Damage {dmg}, radius {radius} (cooldown ~{cd:.2f}s)"

        if "damage_heal_increments" in w:
            incs = w.get("damage_heal_increments", {})
            mult = 1.0
            for thresh, inc in incs.items():
                if level >= thresh:
                    mult += inc
            if abs(mult - 1.0) > 1e-6:
                return f"Lv{level}: +{int((mult-1.0)*100)}% damage & heal"
    except Exception:
        pass

    # As a last-resort, include the weapon name so the UI is less generic
    return f"Upgrade {w.get('name', weapon)} to level {level}"
