"""Centralized weapon definitions and helper utilities."""

from typing import Dict, List

# Centralized weapon definitions to avoid duplication across modules
WEAPON_DEFS: Dict[str, Dict] = {
    "shotgun": {
        "name": "Hellgun",
        "description": "Fires multiple pellets in a spread pattern",
        "icon": "weapon_shotgun.png",
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
        "icon": "weapon_orbital.png",
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
        "icon": "weapon_spear.png",
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
    "Flies": {
        "name": "Flies",
        "description": "Fires homing projectiles that latch onto enemies and heal the player",
        "icon": "weapon_flies.png",
        "max_level": 6,
        "required_meta_level": 5,  # Unlocked at Satan Level 5
        "upgrade_descriptions": {
            1: "Lv1: Fires 2 homing fly projectiles that heal the player",
            2: "Lv2: +10% damage & heal",
            3: "Lv3: +1 projectile",
            4: "Lv4: +10% damage & heal",
            5: "Lv5: +1 projectile",
            6: "Lv6: +20% damage & heal",
        },
    },
    "beast": {
        "name": "The number of the beast",
        "description": "Unleash demonic power with devastating attacks",
        "icon": "weapon_beast.png",
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
    "skullboom": {
        "name": "SkullBoom",
        "description": "Launches explosive skulls that detonate on enemy contact, dealing area damage",
        "icon": "weapon_skullboom.png",
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
        "icon": "weapon_demonstrike.png",
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
        # a slightly wider spread ensures pellets start a bit farther apart
        "spread_deg": 22,
        "damage_mult": 0.55,  # legacy multiplier (kept for compatibility)
        "base_cd": 1.5,
        "cd_reduction_per_pair": 0.15,
        "min_cd": 0.4,
        "base_radius": 5,
        # New configurable absolute pellet damage targets (used for linear remap)
        "min_pellet_damage": 18,  # Lv1 target damage per pellet
        "max_pellet_damage": 28,  # Lv6 target damage per pellet
    }
)


def shotgun_pellet_damage(level: int, base_player_damage: int) -> int:
    """Return per-pellet damage for Hellgun.

    Behavior:
    - Linearly interpolates between configured min/max pellet damage across levels 1..max_level.
    - Scales the resulting value proportionally to the provided base_player_damage relative to
      the default player base (30) so pellet damage still benefits from player damage upgrades.
    - If level <= 0, falls back to the legacy formula (approx. base_player_damage * damage_mult).
    """
    try:
        d = WEAPON_DEFS.get("shotgun", {})
        min_d = float(d.get("min_pellet_damage", 20))
        max_d = float(d.get("max_pellet_damage", 30))
        max_level = int(d.get("max_level", 6) or 6)
    except (AttributeError, TypeError, ValueError, KeyError):
        # Fallback: legacy behavior proportional to base player damage
        return int(
            base_player_damage
            * float(WEAPON_DEFS.get("shotgun", {}).get("damage_mult", 0.55))
        )

    if level <= 0:
        return int(base_player_damage * float(d.get("damage_mult", 0.55)))

    lvl = max(1, min(int(level), max_level))
    t = (lvl - 1) / max(1, (max_level - 1))
    remapped = min_d + t * (max_d - min_d)

    # Scale remapped absolute pellet damage proportionally to player's base damage.
    # Default player base is 30 (PLAYER_BASE_DAMAGE); use 30 as reference.
    reference = 30.0
    try:
        scaled = remapped * (float(base_player_damage) / reference)
    except (AttributeError, TypeError, ValueError, KeyError):
        scaled = remapped
    # Use int() truncation to match existing conventions
    return int(scaled)


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
        # Cooldown tuned similar to skullboom (kept at 1.8s here)
        "base_cd": 1.8,  # roughly matched to SkullBoom base_cd
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

WEAPON_DEFS["Flies"].update(
    {
        "base_cd": 1.5,
        "cd_reduction_at_level_4": 0.3,
        "min_cd": 0.5,
        "base_damage": 10,  # doubled from 5
        # Halved healing per your request
        "base_heal": 1,
        # damage/heal increments now occur at levels 2,4,6 (20% total at max)
        "damage_heal_increments": {
            2: 0.1,
            4: 0.1,
            6: 0.2,
        },
        # Base projectiles still 2; extra ones at lv3 and lv5
        "base_projectiles": 2,
        "projectiles_at_level": {
            3: 1,
            5: 1,
        },
    }
)


def beast_damage(level: int, base_damage: int) -> int:
    """Return effective beast-adjusted damage for a basic projectile.

    This remaps Beast levels linearly between the configured absolute
    damage targets (min_damage -> max_damage) and then scales the result
    proportionally to the provided `base_damage` relative to the game's
    default player base (30). That makes permanent player damage modifiers
    (e.g. `power`, `blasphemy_1`) correctly affect Beast projectiles.
    If level <= 0, returns the provided base_damage unchanged.
    """
    try:
        d = WEAPON_DEFS.get("beast", {})
        min_d = float(d.get("min_damage", 22))
        max_d = float(d.get("max_damage", 45))
        max_level = int(d.get("max_level", 6) or 6)
    except (AttributeError, TypeError, ValueError, KeyError):
        return int(base_damage)

    if level <= 0:
        return int(base_damage)

    lvl = max(1, min(int(level), max_level))
    # Linear interpolation across levels 1..max_level
    t = (lvl - 1) / max(1, (max_level - 1))
    desired = min_d + t * (max_d - min_d)

    # Scale remapped absolute beast damage proportionally to player's base damage.
    # Default player base is 30 (PLAYER_BASE_DAMAGE); use 30 as reference.
    reference = 30.0
    try:
        scaled = desired * (float(base_damage) / reference)
    except (AttributeError, TypeError, ValueError, KeyError):
        scaled = desired
    return int(scaled)


WEAPON_DEFS["skullboom"].update(
    {
        "base_cd": 1.8,
        # Linear reduction per level so Lv1=1.8s -> Lv6=1.0s (5 steps of 0.16s)
        "cd_reduction_per_level": 0.16,
        "min_cd": 0.5,
        # Pre-multiplied base + fractional per-level increment so final values
        # (after existing *1.2 multiplier in skullboom_damage) are: Lv1=30, Lv6=50
        "base_damage": 25,
        "damage_increase_per_level": 3.3333333333333335,
        "base_explosion_radius": 80,
        "radius_increase_per_level": 8,
    }
)


# Tenebrae weapon: arrow of tenebrae that pierces and decays per enemy
WEAPON_DEFS["tenebrae"] = {
    "name": "Tenebrae",
    "icon": "weapon_tenebrae.png",
    "description": (
        "Arc of shadows that pierces enemies, " "losing power with each hit"
    ),
    "max_level": 6,
    "required_meta_level": 10,  # Unlocked at Satan Level 10
    "upgrade_descriptions": {
        1: "Lv1: Base damage 25, -20% per enemy hit",
        2: "Lv2: +5 base damage, reduced cooldown",
        3: "Lv3: -2% decay per target",
        4: "Lv4: +5 base damage, reduced cooldown",
        5: "Lv5: -2% decay per target",
        6: "Lv6: Max base damage, minimal decay and cooldown",
    },
    # parametri usati dalle funzioni sottostanti
    "base_damage": 25,  # tarato più basso
    "damage_per_level": 5,
    "decay_per_target": 0.20,  # 20 % in meno ad ogni nemico colpito (Lv1)
    "decay_reduction_per_lvl": 0.02,  # ogni due livelli si riduce il decay
    "base_cd": 2.0,
    # cooldown improvement per level was 0.3; reduce so levels grant
    # less cooldown benefit as requested
    "cd_reduction_per_level": 0.15,
    "min_cd": 0.4,
    "speed": 400,  # relativamente lento
}


def tenebrae_damage(level: int, base_player_damage: int, targets_hit: int) -> int:
    """Danno inflitto al *targets_hit*-esimo nemico attraversato.

    Il primo bersaglio prende il danno di base, ogni successivo subisce
    un moltiplicatore (1‑decay) ripetuto per il numero di bersagli già
    in fila. Il risultato viene poi scalato come nelle altre armi.
    """
    d = WEAPON_DEFS["tenebrae"]
    lvl = max(1, min(int(level), d["max_level"]))

    damage = d["base_damage"] + (lvl - 1) * d["damage_per_level"]

    decay = max(
        0.0,
        d["decay_per_target"] - (lvl // 2) * d["decay_reduction_per_lvl"],
    )

    damage *= (1.0 - decay) ** targets_hit

    # scala rispetto al danno del giocatore (rif.)

    reference = 30.0
    if base_player_damage is None:
        base_player_damage = reference
    damage *= base_player_damage / reference
    return int(damage)


def tenebrae_cooldown(level: int) -> float:
    d = WEAPON_DEFS["tenebrae"]
    lvl = max(1, min(int(level), d["max_level"]))
    cd = d["base_cd"] - (lvl - 1) * d["cd_reduction_per_level"]
    return max(d["min_cd"], cd)


def get_orbital_count(level: int) -> int:
    base = int(WEAPON_DEFS.get("orbital", {}).get("base_count", 3) or 3)
    extra = (level // 2) * int(
        WEAPON_DEFS.get("orbital", {}).get("extra_per_pair", 1) or 1
    )
    return int(base + extra)


def orbital_cooldown_range(level: int) -> tuple[int, int]:
    """Return min/max cooldown for an orbital at the given level.

    The configuration in ``WEAPON_DEFS`` still describes base timings
    (40–100 ticks at level 1) and reductions per level pair, but the final
    values are **increased by one third** so that orbitals fire less often
    overall.  This mirrors the previous change request, just inverted.
    """
    d = WEAPON_DEFS.get("orbital", {})
    reductions = level // 2
    base_min = d.get("cooldown_base_min", 40)
    base_max = d.get("cooldown_base_max", 100)
    # compute raw range as before
    min_cd = max(10, base_min - reductions * d.get("cooldown_reduction_per_pair", 6))
    max_cd = max(
        min_cd + 5,
        base_max - reductions * (d.get("cooldown_reduction_per_pair", 6) * 2),
    )

    # apply 1/3 slowdown (multiply by 4/3)
    factor = 4.0 / 3.0
    min_cd = int(min_cd * factor)
    max_cd = int(max_cd * factor)
    return min_cd, max_cd


def shotgun_pellets(level: int) -> int:
    d = WEAPON_DEFS.get("shotgun", {})
    base = int(d.get("base_pellets", 4) or 4)
    step = int(d.get("pellet_level_step", 2) or 2)
    inc = int(d.get("pellet_increase", 1) or 1)
    return int(base + (level // step) * inc)


def shotgun_cooldown(level: int) -> float:
    d = WEAPON_DEFS.get("shotgun", {})
    base_cd = float(d.get("base_cd", 1.5) or 1.5)
    reductions = level // 2
    cd = base_cd - reductions * float(d.get("cd_reduction_per_pair", 0.15) or 0.15)
    return float(max(float(d.get("min_cd", 0.4) or 0.4), cd))


def spear_cooldown(level: int) -> float:
    d = WEAPON_DEFS.get("spear", {})
    base_cd = float(d.get("base_cd", 0.6) or 0.6)
    cd = base_cd - level * float(d.get("cd_reduction_per_level", 0.06) or 0.06)
    return float(max(float(d.get("min_cd", 0.15) or 0.15), cd))


def DemonStrike_cooldown(level: int) -> float:
    """Cooldown for DemonStrike — uses DemonStrike-specific tuning from WEAPON_DEFS."""
    d = WEAPON_DEFS.get("DemonStrike", {})
    base_cd = float(d.get("base_cd", 1.8) or 1.8)
    cd = base_cd - level * float(d.get("cd_reduction_per_level", 0.12) or 0.12)
    return float(max(float(d.get("min_cd", 0.5) or 0.5), cd))


def flies_cd(level: int) -> float:
    d = WEAPON_DEFS.get("Flies", {})
    base_cd = float(d.get("base_cd", 1.5) or 1.5)
    if level >= 4:
        base_cd -= float(d.get("cd_reduction_at_level_4", 0.3) or 0.3)
    return float(max(float(d.get("min_cd", 0.5) or 0.5), base_cd))


def flies_projectile_count(level: int) -> int:
    d = WEAPON_DEFS.get("Flies", {})
    # Base projectiles now come from definition (default 2)
    base = int(d.get("base_projectiles", 2) or 2)
    extra = 0
    proj_map = d.get("projectiles_at_level", {})
    for thresh, extra_n in proj_map.items():
        try:
            t = int(thresh)
        except (AttributeError, TypeError, ValueError, KeyError):
            t = thresh  # keep original if not coercible
        if level >= t:
            extra += int(extra_n or 0)
    return int(base + extra)


def flies_damage_heal_mult(level: int) -> tuple[float, float]:
    d = WEAPON_DEFS.get("Flies", {})
    incs = d.get("damage_heal_increments", {})
    mult = 1.0
    for thresh, inc in incs.items():
        if level >= thresh:
            mult += inc
    return mult, mult


def skullboom_cooldown(level: int) -> float:
    d = WEAPON_DEFS.get("skullboom", {})
    base_cd = float(d.get("base_cd", 2.0) or 2.0)
    cd = base_cd - (level - 1) * float(d.get("cd_reduction_per_level", 0.15) or 0.15)
    return float(max(float(d.get("min_cd", 0.5) or 0.5), cd))


def skullboom_damage(level: int) -> int:
    d = WEAPON_DEFS.get("skullboom", {})
    base_damage = d.get("base_damage", 20)
    damage = base_damage + (level - 1) * d.get("damage_increase_per_level", 2)
    return int(damage * 1.2)  # 20% damage increase


def skullboom_explosion_radius(level: int) -> int:
    d = WEAPON_DEFS.get("skullboom", {})
    base_radius = int(d.get("base_explosion_radius", 50) or 50)
    return int(
        base_radius + (level - 1) * int(d.get("radius_increase_per_level", 5) or 5)
    )


def get_weapon_definitions() -> List[Dict[str, str]]:
    """Return list of basic weapon choice dicts used by UIs and game logic.

    Each dictionary includes an ``icon`` key.  If a specific filename is
    provided in the weapon definition it is used; otherwise we fall back to
    the standard ``weapon_<id>.png`` pattern so that autogenerated or default
    assets are still picked up.  This guarantees that the UI can always
    attempt to load an image and simplifies test expectations.
    """
    result: list[dict] = []
    for wid, d in WEAPON_DEFS.items():
        icon = d.get("icon")
        if not icon:
            icon = f"weapon_{wid.lower()}.png"
        result.append(
            {
                "id": wid,
                "name": d["name"],
                "description": d["description"],
                "icon": icon,
            }
        )
    return result


def get_weapon_upgrade_description(weapon: str, level: int) -> str:
    """Get a human-readable description for a weapon upgrade to given level.

    This function first attempts to return the explicit description from
    WEAPON_DEFS[weapon]["upgrade_descriptions"]. If not present, it will
    try to normalize common naming differences (e.g., 'flies' -> 'Flies')
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
        return str(upd[level])

    # Inference fallback: try to construct a useful description based on known params
    try:
        if weapon.lower() in ("shotgun",):
            pellets = shotgun_pellets(level)
            cd = shotgun_cooldown(level)
            return f"Lv{level}: Fires {pellets} pellets (cooldown ~{cd:.2f}s)"

        if weapon.lower() in ("orbital", "orbitals"):
            cnt = get_orbital_count(level)
            return f"Lv{level}: {cnt} orbitals that auto-fire"

        if weapon.lower() in ("flies", "fly", "flies"):
            projs = flies_projectile_count(level)
            dmg_mult, heal_mult = flies_damage_heal_mult(level)
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

        if weapon.lower() in ("skullboom", "skull bomb", "skullboom"):
            cd = skullboom_cooldown(level)
            dmg = skullboom_damage(level)
            radius = skullboom_explosion_radius(level)
            return f"Lv{level}: Damage {dmg}, radius {radius} (cooldown ~{cd:.2f}s)"

        if "damage_heal_increments" in w:
            incs = w.get("damage_heal_increments", {})
            mult = 1.0
            for thresh, inc in incs.items():
                if level >= thresh:
                    mult += inc
            if abs(mult - 1.0) > 1e-6:
                return f"Lv{level}: +{int((mult - 1.0) * 100)}% damage & heal"
    except (AttributeError, TypeError, ValueError, KeyError):
        pass

    # As a last-resort, include the weapon name so the UI is less generic
    return f"Upgrade {w.get('name', weapon)} to level {level}"
