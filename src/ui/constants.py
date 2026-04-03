"""Shared constants used across UI subsystems."""

_STAT_CONFIGS: list[dict] = [
    {"name": "POWER", "key": "power", "color": (255, 68, 68), "y": 140},
    {"name": "VIGOR", "key": "vigor", "color": (255, 204, 0), "y": 185},
    {"name": "ADRENALINE", "key": "adrenaline", "color": (170, 68, 255), "y": 230},
    {"name": "STRUCTURE", "key": "structure", "color": (139, 105, 20), "y": 275},
]

_TREE_TYPES = [
    ("FIRE", "fire", (255, 68, 68)),
    ("STORM", "storm", (170, 68, 255)),
    ("ICE", "ice", (100, 200, 255)),
]

_WEAPON_HUD_NAMES: dict[str, str] = {
    "shotgun": "Hellgun",
    "orbital": "Orbitals",
    "spear": "Spear",
    "beast": "The number of the beast",
    "Flies": "Flies",
}
