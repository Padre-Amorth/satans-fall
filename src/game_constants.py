DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
DEFAULT_FPS = 60
DEFAULT_PLAYER_ANIM_SPEED = 30
DEFAULT_WAVE_DURATION = 30  # seconds
WALL_THICKNESS = 25

STAGE_SETTINGS = {
    "prologo": {
        "bg_color": (0, 0, 0),
        "floor_color": (0, 50, 0),
        "wall_color": (150, 150, 150),
        "building_color": (139, 69, 69),
    },
    "limbo": {
        "bg_color": (0, 0, 0),
        "floor_color": (100, 50, 0),
        "wall_color": (42, 18, 8),
        "building_color": None,  # No buildings in limbo
    },
    "limbo_2": {
        "bg_color": (0, 0, 0),
        "floor_color": (100, 50, 0),
        "wall_color": (42, 18, 8),
        "building_color": None,
    },
    "limbo_3": {
        "bg_color": (0, 0, 0),
        "floor_color": (100, 50, 0),
        "wall_color": (42, 18, 8),
        "building_color": None,
    },
}

__all__ = [
    "DEFAULT_WIDTH",
    "DEFAULT_HEIGHT",
    "DEFAULT_FPS",
    "DEFAULT_PLAYER_ANIM_SPEED",
    "DEFAULT_WAVE_DURATION",
    "WALL_THICKNESS",
    "STAGE_SETTINGS",
]
