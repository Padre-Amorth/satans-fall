from typing import Any

DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
DEFAULT_FPS = 60
DEFAULT_PLAYER_ANIM_SPEED = 30
DEFAULT_WAVE_DURATION = 40  # seconds
WALL_THICKNESS = 25

# Limbo fog alpha ranges (min, max) for each limbo variant

# Legacy fog alpha ranges used by the now‑disabled particle system.  The
# current purgatory haze is a simple overlay so these constants are retained
# only for backward compatibility/testing and may be removed in a future
# cleanup.
PURGATORY_FOG_ALPHA_RANGE = (8, 45)
PURGATORY_2_FOG_ALPHA_RANGE = (6, 35)
PURGATORY_3_FOG_ALPHA_RANGE = (6, 35)

# Overlay used for Purgatory stages.  The original effect was quite strong
# (alpha 100) and could feel oppressive; reduce this value to make the fog
# lighter.  The color may also be changed if a different hue is desired.
# These values are consulted by ``ui.draw_purgatory_fog``.
PURGATORY_OVERLAY_ALPHA = 60  # 0=fully transparent, 255=opaque
PURGATORY_OVERLAY_COLOR = (190, 190, 190)  # light gray mist

# Similar full-screen haze applied to all Limbo variants.  This overlay is
# rendered on top of the walls/objects but beneath any particle effects, and
# it uses ``convert()`` + ``set_alpha()`` for maximum blit performance.
# Default values give a subtle bluish‑gray wash.
LIMBO_OVERLAY_ALPHA = 10
LIMBO_OVERLAY_COLOR = (60, 60, 60)

# Full-screen haze for Hell stages — dark red ember tint.
HELL_OVERLAY_ALPHA = 80
HELL_OVERLAY_COLOR = (60, 10, 10)

# Full-screen haze for the Prologo stage — very subtle warm smoke.
PROLOGO_OVERLAY_ALPHA = 50
PROLOGO_OVERLAY_COLOR = (30, 15, 5)

# Configuration for the new “cloud” particles that float near the top of
# Purgatory stages.  The system spawns a few large, oval, irregular shapes in
# the upper screen region and drifts them slowly across the playfield.  These
# constants control their size, speed, spawn frequency, and appearance.
# spawn rate defines the per-frame probability of a new cloud; reducing
# it by roughly one third lowers the average number of clouds by a third.
# default was 0.05, now 2/3 of that to cut quantity.
PURGATORY_CLOUD_SPAWN_RATE = 0.02 * 2 / 3  # ≈0.0333 chance per frame
PURGATORY_CLOUD_WIDTH_RANGE = (150, 300)
PURGATORY_CLOUD_HEIGHT_RANGE = (60, 140)
PURGATORY_CLOUD_SPEED_RANGE = (-0.2, 0.2)  # horizontal velocity
# vertical spawn limits; clouds may start partially above the top edge
PURGATORY_CLOUD_SPAWN_Y_RANGE = (-180, 50)
# alpha for the cloud fill and the overlay bumps; lower = more transparent
PURGATORY_CLOUD_ALPHA = 10
PURGATORY_CLOUD_BUMP_ALPHA = 20

# --- Dynamic fog particle system (replacing simple clouds) ---
# The requested tweak: bump count to 12 and slow particles slightly by reducing
# their horizontal velocity range.  Tests will validate the new count and
# speeds are initialized within bounds.
FOG_PARTICLE_COUNT = 12  # number of fog particles to maintain
FOG_TEXTURE_SIZE = 450  # diameter of generated cloud texture (increased 50%)
FOG_MIN_SPEED = 0.15  # horizontal velocity range
FOG_MAX_SPEED = 0.4
FOG_AMPLITUDE_RANGE = (10, 30)  # vertical sine amplitude
FOG_TIMER_RANGE = (0, 10)  # initial timer offset
FOG_COLOR = (200, 210, 220)  # blue‑gray fog tint
FOG_ALPHA = 40  # maximum alpha for texture

# colors for dynamic fog particles by Purgatory variant
PURGATORY_FOG_COLORS: dict[str, tuple[int, int, int]] = {
    "purgatory": FOG_COLOR,
    "purgatory_2": (210, 220, 150),  # yellowish green
    "purgatory_3": (220, 150, 120),  # light red/orange
}

# Selection box layout constants (used in UI drawing and input handling)
SELECTION_BOX_WIDTH = 560
SELECTION_BOX_HEIGHT = 80
SELECTION_BOX_SPACING = 14

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
        # walls are now uniformly dark gray across all stages
        "wall_color": (40, 40, 40),
        "building_color": (139, 69, 69),
    },
    "limbo": {
        "bg_color": (0, 0, 0),
        "bg_image": "limbo_battlefield.png",
        "floor_color": (100, 50, 0),
        # walls are now dark gray like prologue
        "wall_color": (40, 40, 40),
        "building_color": None,  # No buildings in limbo
    },
    "limbo_2": {
        "bg_color": (0, 0, 0),
        "bg_image": "limbo_battlefield.png",
        "floor_color": (100, 50, 0),
        "wall_color": (40, 40, 40),
        "building_color": None,
    },
    "limbo_3": {
        "bg_color": (0, 0, 0),
        "bg_image": "limbo_battlefield.png",
        "floor_color": (100, 50, 0),
        "wall_color": (40, 40, 40),
        "building_color": None,
    },
    "purgatory": {
        "bg_color": (0, 0, 0),  # external area: black
        "bg_image_external": "purgatory_background.png",  # optional full‑screen external image
        "bg_image": "purgatory_battlefield.png",  # battlefield image inside the walls
        "floor_color": (40, 40, 40),  # inside walls: darker gray (test expectation)
        "wall_color": (40, 40, 40),
        "building_color": None,
    },
    "purgatory_2": {
        "bg_color": (0, 0, 0),
        "bg_image_external": "purgatory_background.png",
        "bg_image": "purgatory_battlefield.png",
        "floor_color": (40, 40, 40),
        "wall_color": (40, 40, 40),
        "building_color": None,
    },
    "purgatory_3": {
        "bg_color": (0, 0, 0),
        "bg_image_external": "purgatory_background.png",
        "bg_image": "purgatory_battlefield.png",
        "floor_color": (40, 40, 40),
        "wall_color": (40, 40, 40),
        "building_color": None,
    },
    "hell": {
        "bg_color": (80, 8, 8),
        "floor_color": (60, 60, 60),  # grigio del campo schiarito
        "wall_color": (40, 40, 40),  # now dark gray like other stages
        "building_color": None,
    },
    "hell_2": {
        "bg_color": (80, 8, 8),
        "floor_color": (60, 60, 60),  # grigio del campo schiarito
        "wall_color": (40, 40, 40),
        "building_color": None,
    },
    "hell_3": {
        "bg_color": (80, 8, 8),
        "floor_color": (60, 60, 60),  # grigio del campo schiarito
        "wall_color": (40, 40, 40),
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
    "SELECTION_BOX_WIDTH",
    "SELECTION_BOX_HEIGHT",
    "SELECTION_BOX_SPACING",
    "PURGATORY_FOG_ALPHA_RANGE",
    "PURGATORY_2_FOG_ALPHA_RANGE",
    "PURGATORY_3_FOG_ALPHA_RANGE",
    "HELL_OVERLAY_ALPHA",
    "HELL_OVERLAY_COLOR",
    "PROLOGO_OVERLAY_ALPHA",
    "PROLOGO_OVERLAY_COLOR",
]
