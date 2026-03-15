from typing import Any

DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
DEFAULT_FPS = 60

# Duration (in frames) of the storm-tier7 "Voltaic Mayhem" special when
# activated.  The beam can persist up to this many frames but also cancels
# early if the right mouse button is released.
VOLTAIC_MAYHEM_MAX_DURATION = int(3.5 * DEFAULT_FPS)  # 210 frames (3.5 seconds)

# Movement speed for the beam's controllable endpoint (pixels/second).  The
# endpoint will chase the mouse cursor at this rate rather than teleporting
# instantly, giving the ability a more deliberate feel.
VOLTAIC_MAYHEM_SPEED = 200

# radius of the pulsing electric circle drawn at the cursor during Voltaic Mayhem
VOLTAIC_MAYHEM_IMPACT_RADIUS = 50

# a small fraction of the Voltaic Mayhem beams will be tinted a more
# purplish/violaceous color.  the probability controls how often the effect
# occurs; the hue itself is chosen to blend with the existing cyan palette
# without going completely purple.
VOLTAIC_MAYHEM_VIOLET_CHANCE = 0.25  # 0.0-1.0 probability per beam
VOLTAIC_MAYHEM_VIOLET_COLOR = (180, 150, 255)  # rgb colour used when chance triggers

# -- Fire tier-7 special: large area bomb
# radius now 20px larger than original so effects feel beefier
FIRE_SPECIAL_RADIUS = 70  # px (was 50, then 60)
FIRE_SPECIAL_DAMAGE = 20  # flat damage per explosion
FIRE_SPECIAL_CHARGES = 4  # number of shots per activation

# Winged enemies detonate when touching the player.  The configuration
# constants below control the visual radius, how long the orange circle
# lingers, and the flat damage inflicted.  These were originally hard‑coded
# in the collision logic but have been promoted so tests can rely on them.
WINGED_EXPLOSION_RADIUS = 30  # visual radius of the contact explosion
WINGED_EXPLOSION_DURATION = 6  # frames the effect persists
WINGED_EXPLOSION_COLOR = (255, 120, 0)  # slightly bright orange
WINGED_CONTACT_DAMAGE = 15  # damage dealt to player on contact

# Archer enemy tuning
ARCHER_VERTICAL_LIMIT = 250  # vertical boundary so archers stay in upper region
ARCHER_PROJECTILE_DAMAGE = 12
ARCHER_PROJECTILE_RADIUS = 5

# Duration of the firing window (player has this many frames to use all charges)
# extended to eight seconds for more flexibility.
FIRE_SPECIAL_DURATION = 8 * DEFAULT_FPS
# Time delay between clicking and the actual explosion spawn.  The delay
# gives the ability more weight and allows a quick "wind‑up" animation.
FIRE_SPECIAL_CLICK_DELAY = int(0.5 * DEFAULT_FPS)
# Minimum lifetime (frames) for the floating text words triggered by this
# special; they should remain visible for at least two seconds.
# Text shown by the fire special should linger for at least two seconds
# plus an extra second so the word remains visible even when multiple
# explosions happen in quick succession.
FIRE_SPECIAL_TEXT_LIFE = 3 * DEFAULT_FPS  # 3 seconds
# Visual duration (frames) of the orange circle effect created by each shot.
# Was previously hard-coded at 8 frames, bump to roughly one second for clarity.
FIRE_SPECIAL_VISUAL_DURATION = DEFAULT_FPS
# color used for the orange ring effect; darker than the original bright
# orange so the explosion feels heavier on screen.
FIRE_SPECIAL_EXPLOSION_COLOR = (200, 100, 40)
# words shown by successive shots
FIRE_SPECIAL_WORDS = ["Make", "Ade", "Great", "Again!"]


# Blizzard ice-zone constants (ice tier‑7 special)
BLIZZARD_RADIUS = 250
# Duration in frames of Blizzard zone.  Originally 5 seconds, now extended
# by 1 second to give players an extra moment of area denial.
BLIZZARD_MAX_DURATION = 6 * DEFAULT_FPS  # six seconds
BLIZZARD_SLOW_FACTOR = 0.5
BLIZZARD_DAMAGE_PER_SECOND = 5
# Damage dealt to all enemies/bosses when the zone expires
BLIZZARD_EXPIRE_DAMAGE = 20

# Growth speed modifier for blizzard radius.  A value >1 makes the area
# expand slightly faster than linear lifetime.  1.0 = linear, 1.2 = 20% faster.
BLIZZARD_GROWTH_MULTIPLIER = 1.2

# Blizzard spiral snowflake particle constants
BLIZZARD_PARTICLE_COUNT = 100  # number of snow particles per blizzard zone
BLIZZARD_PARTICLE_SPEED = 0.5  # radial inward speed (pixels/frame) - slower movement
BLIZZARD_PARTICLE_SPIRAL_SPEED = (
    0.03  # angular velocity (radians/frame) - slower spiral
)
BLIZZARD_PARTICLE_SIZE = (
    3  # snowflake radius in pixels (slightly larger for visibility)
)
BLIZZARD_PARTICLE_MAX_ALPHA = 100  # maximum alpha for particles (0-255)
BLIZZARD_PARTICLE_SPAWN_DELAY = (
    2  # frames between spawning new particles at edges (reduced for 100 particles)
)
BLIZZARD_PARTICLE_ALIGNED_RATIO = (
    0.7  # fraction of particles with S-curve alignment (70%)
)
BLIZZARD_PARTICLE_S_CURVE_AMPLITUDE = 0.25  # amplitude of S-curve oscillation (radians)
BLIZZARD_PARTICLE_S_CURVE_RADIAL = (
    0.15  # radial offset multiplier for S-curve (fraction of radius)
)
BLIZZARD_PARTICLE_EXPANSION = 0.50  # radial expansion near respawn point (fraction of original spawn distance) - increased for outward bulge

DEFAULT_PLAYER_ANIM_SPEED = 40
DEFAULT_WAVE_DURATION = 45  # seconds (increased from 40)
WALL_THICKNESS = 25

# Wall brick pattern settings per stage group
WALL_BRICK_PROLOGO = {"w": 10, "h": 6, "mortar": (20, 20, 20), "base": (50, 50, 50)}
WALL_BRICK_LIMBO = {"w": 9, "h": 5, "mortar": (10, 10, 10), "base": (35, 35, 35)}
WALL_BRICK_PURGATORY = {"w": 11, "h": 7, "mortar": (25, 20, 20), "base": (60, 55, 55)}
WALL_BRICK_HELL = {"w": 12, "h": 7, "mortar": (20, 10, 5), "base": (70, 35, 20)}

# Limbo wall lamps decorative elements
LIMBO_LAMP_SPACING = 120  # distance between consecutive lamps (pixels)
LIMBO_LAMP_SIZE = (27, 79)  # width, height of lamp sprite (2/3 scale, maintains aspect ratio)
LIMBO_LAMP_OFFSET_LEFT = 15  # horizontal offset from left wall edge (pixels, towards center)
LIMBO_LAMP_OFFSET_LEFT_TOP = 12  # offset for top 2 left lamps (3px closer to wall)
LIMBO_LAMP_OFFSET_LEFT_BOTTOM = 13  # offset for bottom 2 left lamps (2px closer to wall)
LIMBO_LAMP_OFFSET_RIGHT = 40  # horizontal offset from right wall edge (pixels, towards center)

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
PURGATORY_OVERLAY_ALPHA = 40  # 0=fully transparent, 255=opaque
PURGATORY_OVERLAY_COLOR = (190, 190, 190)  # light gray mist

# Similar full-screen haze applied to all Limbo variants.  This overlay is
# rendered on top of the walls/objects but beneath any particle effects, and
# it uses ``convert()`` + ``set_alpha()`` for maximum blit performance.
# Default values give a subtle bluish‑gray wash.
LIMBO_OVERLAY_ALPHA = 80
LIMBO_OVERLAY_COLOR = (60, 60, 60)

# Full-screen haze for Hell stages — dark red ember tint.
HELL_OVERLAY_ALPHA = 70
HELL_OVERLAY_COLOR = (60, 10, 10)

# Full-screen haze for the Prologo stage — very subtle warm smoke.
PROLOGO_OVERLAY_ALPHA = 30
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
FOG_TEXTURE_SIZE = 500  # diameter of generated cloud texture
FOG_MIN_SPEED = 0.3  # horizontal velocity range (increased from 0.15)
FOG_MAX_SPEED = 0.65  # (increased from 0.4)
FOG_AMPLITUDE_RANGE = (10, 30)  # vertical sine amplitude
FOG_TIMER_RANGE = (0, 10)  # initial timer offset
FOG_COLOR = (200, 210, 220)  # blue‑gray fog tint
FOG_ALPHA = 65  # maximum alpha for texture (increased from 40)

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

# When showing weapon choices the UI will optionally display a small icon
# representing each weapon on the left side of the box.  These constants
# control the rendered icon size and gap between the icon and the text
# that follows.  They are intentionally modest so the overall box width
# does not need to change; spacing is applied inside the existing layout.
WEAPON_ICON_SIZE = 48  # width/height in pixels
WEAPON_ICON_PADDING = 8  # space between icon and subsequent text

# Common resolution presets shown in the Options -> Resolution menu
DEFAULT_DISPLAY_PRESETS = [
    (1024, 768),
    (1280, 720),
    (1366, 768),
    (1600, 900),
    (1920, 1080),
]

# Vertical adjustment applied to imported statue assets.  Designers can
# increase this value (positive pixels) to drop statues lower on the screen
# if their artwork includes excessive headroom.  The default is 100, which
# reflects the typical offset needed for the first fire statue asset imported
# in early 2026.  Feel free to modify this to suit your art.
#
# NOTE: an earlier version mistakenly set this to 1000, causing fire statues
# to be blitted well off‑screen and appear "invisible".  100 keeps the
# graphic within the play area for normal-sized assets.
STATUE_ASSET_VERTICAL_OFFSET: int = 80

# -------------------------------------------------------------
# Statue projectile offsets
#
# To visually align statue/tower projectiles with their source artwork, the
# game adds a small spawn offset when a statue fires.  Historically Limbo
# shots were displaced 50px toward the centre and 10px downward; the value has
# since been tuned and made stage‑specific.  ``*_OFFSET_X`` values are applied
# horizontally (positive moves left‑side shots right and right‑side shots left)
# while ``STATUE_PROJECTILE_OFFSET_Y`` is a constant vertical shift downward.
#
# Changing these constants lets designers tweak the appearance without
# touching code.  The offsets are only used by ``WeaponSystem.update_statue_weapons``.
#
# Default values correspond to the current stage tuning requested by the user:
#   * Limbo        : 50px toward centre (legacy and unified across all
#     Limbo variants – limbo, limbo_2 and limbo_3)
#   * Purgatory/Hell : 10px toward centre
#
# NOTE: this value was previously 60 but was rolled back after limbo_3
# artwork showed the firing nozzle 10px closer to the tower center than the
# other Limbo stages.  The constant now matches the original 50px value used
# by earlier versions.
STATUE_PROJECTILE_OFFSET_X_LIMBO: int = 60
STATUE_PROJECTILE_OFFSET_X_PURGATORY: int = 10
STATUE_PROJECTILE_OFFSET_X_HELL: int = 10

# Vertical offset applied to statue projectiles.  Purgatory and Hell towers
# fire 30px higher than the default (smaller Y = higher on screen).
STATUE_PROJECTILE_OFFSET_Y: int = 60
STATUE_PROJECTILE_OFFSET_Y_PURGATORY: int = 10
STATUE_PROJECTILE_OFFSET_Y_HELL: int = 10

# Limbo Final timing constants
LIMBO_FINAL_ACCEL_START_TIME: float = (
    30.0  # seconds into the run when spawn accelerates
)
LIMBO_FINAL_HALT_BEFORE_BOSS: float = 5.0  # seconds before boss when spawning stops

# Additional limbo stages horde event — tuning by stage variant
LIMBO_HORDE_TIME: float = (
    480.0  # seconds into run when huge horde arrives (8 minutes) — used by limbo_3 and limbo_final
)
LIMBO_HORDE_TIME_1: float = 360.0  # limbo: 6 minutes
LIMBO_HORDE_TIME_2: float = 420.0  # limbo_2: 7 minutes
LIMBO_HORDE_TIME_3: float = 480.0  # limbo_3: 8 minutes
# tuning for the (legacy) horde system.  the current implementation
# uses a scripted, multi‑phase schedule instead of a simple rate-based burst.
# these constants remain around mostly for testing and backward compatibility
# and are ignored by the revised schedule in ``spawn_system._start_limbo_horde``.
LIMBO_HORDE_DURATION: float = 10.0  # seconds over which the horde spawns
LIMBO_HORDE_ACCEL_START: float = 7.0  # seconds after start when rate increases
LIMBO_HORDE_BASE_RATE: float = 5.0  # enemies per second before accel
LIMBO_HORDE_ACCEL_EXTRA_RATE: float = 10.0  # additional enemies/sec after accel

# Purgatory horde event — tuning by stage variant (no boss, no buff)
PURGATORY_HORDE_TIME_1: float = 480.0  # purgatory: 8 minutes
PURGATORY_HORDE_TIME_2: float = 540.0  # purgatory_2: 9 minutes
PURGATORY_HORDE_TIME_3: float = 600.0  # purgatory_3: 10 minutes

# Universal Y coordinate (screen pixels from top) at which all statue/tower
# models are anchored, regardless of stage.  Both Limbo pedestals and the
# dynamic Purgatory/Hell towers pass this value as statue_base_y so the
# rendered height is identical everywhere.
STATUE_BASE_Y: int = 640

# Stage groupings for conditional logic
PROLOGO_STAGES = {"prologo"}
LIMBO_STAGES = {"limbo", "limbo_2", "limbo_3", "limbo_final"}
PURGATORY_STAGES = {"purgatory", "purgatory_2", "purgatory_3"}
HELL_STAGES = {"hell", "hell_2", "hell_3"}

# Hell stage destructible barriers
BARRIER_MAX_COUNT = 3
BARRIER_HP = 350
BARRIER_WIDTH = 80
BARRIER_HEIGHT = 40
BARRIER_SPAWN_INTERVAL_MIN = 15.0  # min seconds between spawn attempts (random)
BARRIER_SPAWN_INTERVAL_MAX = 35.0  # max seconds between spawn attempts (random)
BARRIER_DESPAWN_TIME = 45.0  # natural despawn after this many seconds
BARRIER_SPAWN_DELAY = 0.0  # seconds after stage start before first spawn
HELL_BARRIER_Y_MIN = 50
HELL_BARRIER_Y_MAX = 360  # top half only
HELL_BARRIER_X_MIN = 380  # inside hell arena walls
HELL_BARRIER_X_MAX = 900
BARRIER_ARCHER_COVER_CHANCE = 0.95  # High aggressiveness: 95% chance to seek cover
BARRIER_HIDE_DISTANCE = 40  # px — archer considered "behind" barrier
BARRIER_HIDE_SUPPRESS_FRAMES = 150  # frames archer won't shoot while hiding (~2.5s)
BARRIER_DAMAGED_THRESHOLD = 0.40  # Seek new cover if current barrier has < 40% HP

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
        "bg_image_external": "limbo_background.png",  # optional full‑screen external image like prologue/purgatory
        "bg_image": "limbo_battlefield.png",
        "floor_color": (100, 50, 0),
        # walls are now dark gray like prologue
        "wall_color": (25, 25, 25),
        "building_color": None,  # No buildings in limbo
    },
    "limbo_2": {
        "bg_color": (0, 0, 0),
        "bg_image_external": "limbo_background.png",
        "bg_image": "limbo_battlefield.png",
        "floor_color": (100, 50, 0),
        "wall_color": (25, 25, 25),
        "building_color": None,
    },
    "limbo_3": {
        "bg_color": (0, 0, 0),
        "bg_image_external": "limbo_background.png",
        "bg_image": "limbo_battlefield.png",
        "floor_color": (100, 50, 0),
        "wall_color": (25, 25, 25),
        "building_color": None,
    },
    # special final variant: visually identical to limbo_3 but triggers its own
    # boss/spawn behaviour.  Using a separate key keeps UI/menu enumeration
    # straightforward and allows tuning later without affecting limbo_3.
    "limbo_final": {
        "bg_color": (0, 0, 0),
        "bg_image_external": "limbo_background.png",
        "bg_image": "limbo_battlefield.png",
        "floor_color": (100, 50, 0),
        "wall_color": (25, 25, 25),
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
    "PROLOGO_STAGES",
    "LIMBO_STAGES",
    "PURGATORY_STAGES",
    "HELL_STAGES",
    "STAGE_SETTINGS",
    "DEFAULT_DISPLAY_PRESETS",
    "SELECTION_BOX_WIDTH",
    "SELECTION_BOX_HEIGHT",
    "SELECTION_BOX_SPACING",
    "PURGATORY_FOG_ALPHA_RANGE",
    "PURGATORY_2_FOG_ALPHA_RANGE",
    "PURGATORY_3_FOG_ALPHA_RANGE",
    "PURGATORY_OVERLAY_ALPHA",
    "PURGATORY_OVERLAY_COLOR",
    "HELL_OVERLAY_ALPHA",
    "HELL_OVERLAY_COLOR",
    "PROLOGO_OVERLAY_ALPHA",
    "BLIZZARD_RADIUS",
    "BLIZZARD_MAX_DURATION",
    "BLIZZARD_GROWTH_MULTIPLIER",
    "BLIZZARD_EXPIRE_DAMAGE",
    "BLIZZARD_PARTICLE_COUNT",
    "BLIZZARD_PARTICLE_SPEED",
    "BLIZZARD_PARTICLE_SPIRAL_SPEED",
    "BLIZZARD_PARTICLE_SIZE",
    "BLIZZARD_PARTICLE_MAX_ALPHA",
    "BLIZZARD_PARTICLE_SPAWN_DELAY",
    "BLIZZARD_PARTICLE_ALIGNED_RATIO",
    "BLIZZARD_PARTICLE_S_CURVE_AMPLITUDE",
    "BLIZZARD_PARTICLE_S_CURVE_RADIAL",
    "BLIZZARD_PARTICLE_EXPANSION",
    "PROLOGO_OVERLAY_COLOR",
    "PURGATORY_HORDE_TIME_1",
    "PURGATORY_HORDE_TIME_2",
    "PURGATORY_HORDE_TIME_3",
    "BARRIER_MAX_COUNT",
    "BARRIER_HP",
    "BARRIER_WIDTH",
    "BARRIER_HEIGHT",
    "BARRIER_SPAWN_INTERVAL_MIN",
    "BARRIER_SPAWN_INTERVAL_MAX",
    "BARRIER_DESPAWN_TIME",
    "BARRIER_SPAWN_DELAY",
    "HELL_BARRIER_Y_MIN",
    "HELL_BARRIER_Y_MAX",
    "HELL_BARRIER_X_MIN",
    "HELL_BARRIER_X_MAX",
    "BARRIER_ARCHER_COVER_CHANCE",
    "BARRIER_HIDE_DISTANCE",
    "BARRIER_HIDE_SUPPRESS_FRAMES",
    "BARRIER_DAMAGED_THRESHOLD",
    "GIF_RECORDING_FPS",
    "GIF_MAX_DURATION_SECONDS",
    "GIF_SCALE_FACTOR",
    "PENTAGRAM_FIRE_SHIELD_COLOR",
    "PENTAGRAM_STORM_SHIELD_COLOR",
    "PENTAGRAM_ICE_SHIELD_COLOR",
    "PENTAGRAM_ELEMENTAL_BODY_HP",
    "PENTAGRAM_ELEMENTAL_SHIELD_HP",
    "LIMBO_LAMP_SPACING",
    "LIMBO_LAMP_SIZE",
    "LIMBO_LAMP_OFFSET_LEFT",
    "LIMBO_LAMP_OFFSET_LEFT_TOP",
    "LIMBO_LAMP_OFFSET_LEFT_BOTTOM",
    "LIMBO_LAMP_OFFSET_RIGHT",
]

# Elemental pentagram variant shield colours and stats
PENTAGRAM_FIRE_SHIELD_COLOR = (220, 60, 60)  # red
PENTAGRAM_STORM_SHIELD_COLOR = (160, 80, 220)  # purple
PENTAGRAM_ICE_SHIELD_COLOR = (80, 200, 220)  # cyan
PENTAGRAM_ELEMENTAL_BODY_HP = 500
PENTAGRAM_ELEMENTAL_SHIELD_HP = 500

# GIF Recording
GIF_RECORDING_FPS = 15  # frame rate GIF (cattura 1 frame ogni 4 @ 60fps)
GIF_MAX_DURATION_SECONDS = 60  # sicurezza: ferma auto dopo 60s
GIF_SCALE_FACTOR = 0.5  # scala a 640x360 per ridurre dimensione file
