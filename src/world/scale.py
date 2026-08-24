"""
World Scale Registry — the single source of truth for physical dimensions.

Convention (adopted after research into Minecraft / Wolfenstein-lodev /
Godot-Unity practices):
    1 world tile = 1 meter.
    All entity dimensions are expressed in meters and defined HERE.
    Nothing else in the codebase may hardcode an entity size.

References:
    - Minecraft: player 1.8 h / 0.6 w, eye 1.62 (blocks = meters)
    - AASHTO/NACTO: urban lane 3.0-3.6 m
    - CTBUH/story tables: commercial floor-to-floor ~= 3.0-4.2 m
    - Manufacturer specs: sedan 4.89 x 1.84 x 1.45 m; 12 m-class bus

Author: Nora Voss ⚙️ (OpenCode Platform)
"""

from src.entities.vehicle_dims import VEHICLE_DIMS  # noqa: F401  (re-export)

TILE_SIZE_M = 1.0

# --- Projection ---
# Terminal cells are roughly twice as tall as wide; without correcting for
# this, vertical scale is implicitly stretched and proportions read wrong.
CELL_ASPECT = 2.0             # cell height / cell width
DEFAULT_FOV_DEG = 70.0

# --- Human movement (metric; tuned so walking FEELS like walking) ---
WALK_SPEED_MPS = 2.1          # brisk urban walk
SPRINT_MULT = 1.8             # ~3.8 m/s sprint
STRAFE_MULT = 0.8
TURN_RATE_RPS = 2.4

# --- Human ---
PLAYER_EYE_HEIGHT_M = 1.62     # standing eye height (Minecraft convention)
PLAYER_HEIGHT_M = 1.80
PEDESTRIAN_HEIGHT_M = 1.75
PEDESTRIAN_WIDTH_M = 0.55

# --- Structures ---
STORY_HEIGHT_M = 3.0           # commercial floor-to-floor
INTERIOR_CEILING_M = 2.7       # interior room walls
DOOR_HEIGHT_M = 2.1
GROUND_STORY_M = 3.6           # retail / lobby ground floor

# --- Facade heights (meters above grade), by texture id ---
FACADE_HEIGHTS_M = {
    1: 30.0,   # SKYSCRAPER_GLASS      (~10 stories)
    2: 60.0,   # SKYSCRAPER_NEON       (~20 stories)
    3: 10.0,   # BRICK_BROWNSTONE      (~3 stories)
    4: 4.2,    # STOREFRONT_RAMEN      (1 commercial story)
    5: 6.0,    # CONCRETE_WAREHOUSE    (~2 stories)
    6: 14.0,   # HOTEL_NEON            (~4 stories)
    7: 90.0,   # ARCOLOGY_MONUMENT     (~30 stories, landmark)
    8: 45.0,   # MEGASTRUCTURE_MATRIX  (~15 stories)
    9: 12.0,   # INDUSTRIAL_SILO
    10: 3.5,   # MARINA_DOCK
    11: 6.0,   # BOTANICAL_PAVILION
    12: INTERIOR_CEILING_M,   # INTERIOR_WALL
    13: GROUND_STORY_M,       # DOORWAY (reads as ground-story opening)
    101: INTERIOR_CEILING_M,  # RAMEN_INTERIOR  (M2 themed interior)
    102: INTERIOR_CEILING_M,  # ARCADE_INTERIOR
    103: INTERIOR_CEILING_M,  # HOTEL_INTERIOR
}

# --- Street furniture (height in meters; footprint where relevant) ---
LAMP_HEIGHT_M = 5.5
TREE_HEIGHT_M = 8.0
HYDRANT_HEIGHT_M = 0.75
BENCH_HEIGHT_M = 0.85
FOUNTAIN_HEIGHT_M = 1.6
BOLLARD_HEIGHT_M = 0.95
DUMPSTER_HEIGHT_M = 1.4
SIGNPOST_HEIGHT_M = 3.2
CRATE_HEIGHT_M = 1.0
OBELISK_HEIGHT_M = 12.0
VENDING_FRONT_M = 0.9         # width across the lit panel
VENDING_SIDE_M = 0.65         # depth
VENDING_HEIGHT_M = 1.83       # standard beverage machine


def facade_height_m(texture_id: int) -> float:
    return FACADE_HEIGHTS_M.get(texture_id, STORY_HEIGHT_M)
