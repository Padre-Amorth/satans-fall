from typing import Any

DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
DEFAULT_FPS = 60
DEFAULT_PLAYER_ANIM_SPEED = 30
DEFAULT_WAVE_DURATION = 40  # seconds
WALL_THICKNESS = 25

# Common resolution presets shown in the Options -> Resolution menu
DEFAULT_DISPLAY_PRESETS = [
    (1024, 768),
    (1280, 720),
    (1366, 768),
    (1600, 900),
    (1920, 1080),
]

STAGE_SETTINGS: dict[str, dict[str, Any]] = {
    "prologo": {
        "bg_color": (40, 20, 10),  # marrone scuro fuori dai muri
        "bg_image_external": "prologue_background.png",  # Background image for prologue external area
        "bg_image": "prologue_battlefield.png",  # Background image for prologue battlefield
        "floor_color": (30, 80, 30),  # verde del campo leggermente schiarito
        "wall_color": (40, 40, 40),  # grigio scuro intermedio
        "building_color": (139, 69, 69),
    },
    "limbo": {
        "bg_color": (0, 0, 0),
        "bg_image": "limbo_battlefield.png",
        "floor_color": (100, 50, 0),
        "wall_color": (56, 29, 18),  # desaturated (-20% saturation)
        "building_color": None,  # No buildings in limbo
    },
    "limbo_2": {
        "bg_color": (0, 0, 0),
        "bg_image": "limbo_battlefield.png",
        "floor_color": (100, 50, 0),
        "wall_color": (56, 29, 18),  # desaturated (-20% saturation)
        "building_color": None,
    },
    "limbo_3": {
        "bg_color": (0, 0, 0),
        "bg_image": "limbo_battlefield.png",
        "floor_color": (100, 50, 0),
        "wall_color": (56, 29, 18),  # desaturated (-20% saturation)
        "building_color": None,
    },
    "purgatory": {
        "bg_color": (0, 0, 0),  # external area: black
        "floor_color": (40, 40, 40),  # inside walls: darker gray (test expectation)
        "wall_color": (80, 50, 60),
        "building_color": None,
    },
    "purgatory_2": {
        "bg_color": (0, 0, 0),
        "floor_color": (40, 40, 40),
        "wall_color": (80, 50, 60),
        "building_color": None,
    },
    "purgatory_3": {
        "bg_color": (0, 0, 0),
        "floor_color": (40, 40, 40),
        "wall_color": (80, 50, 60),
        "building_color": None,
    },
    "hell": {
        "bg_color": (80, 8, 8),
        "floor_color": (60, 60, 60),  # grigio del campo schiarito
        "wall_color": (150, 70, 0),  # arancione ancora più scuro
        "building_color": None,
    },
    "hell_2": {
        "bg_color": (80, 8, 8),
        "floor_color": (60, 60, 60),  # grigio del campo schiarito
        "wall_color": (150, 70, 0),  # arancione ancora più scuro
        "building_color": None,
    },
    "hell_3": {
        "bg_color": (80, 8, 8),
        "floor_color": (60, 60, 60),  # grigio del campo schiarito
        "wall_color": (150, 70, 0),  # arancione ancora più scuro
        "building_color": None,
    },
}

__all__: list[str] = [
    "DEFAULT_WIDTH",
    "DEFAULT_HEIGHT",
    "DEFAULT_FPS",
    "DEFAULT_PLAYER_ANIM_SPEED",
    "DEFAULT_WAVE_DURATION",
    "WALL_THICKNESS",
    "STAGE_SETTINGS",
    "DEFAULT_DISPLAY_PRESETS",
]
