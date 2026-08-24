# Astra 3D World Scale Standard

> Single source of truth: `src/world/scale.py` (+ `src/entities/vehicle_dims.py`).
> Nothing else may hardcode an entity size.

## Convention

**1 world tile = 1 meter.** All entity dimensions are expressed in meters and
must come from the registry. This follows the Minecraft "1 block = 1 m"
convention and Godot/Unity's "1 unit = 1 m" practice; projection math follows
the classic lodev raycasting model with eye-height anchoring.

## Core constants

| Constant | Value | Basis |
|---|---|---|
| `TILE_SIZE_M` | 1.0 | grid unit |
| `PLAYER_EYE_HEIGHT_M` | 1.62 | standing eye height (Minecraft convention) |
| `PLAYER_HEIGHT_M` | 1.80 | average adult |
| `PEDESTRIAN_HEIGHT_M` | 1.75 / width 0.55 | anthropometric averages |
| `STORY_HEIGHT_M` | 3.0 | commercial floor-to-floor |
| `INTERIOR_CEILING_M` | 2.7 | interior room walls |
| `DOOR_HEIGHT_M` | 2.1 | standard door clearance |

## Vehicles (length × width × height, m)

| Type | L × W × H | Source |
|---|---|---|
| Sedan / taxi | 4.6–4.8 × 1.85 × 1.45–1.5 | Camry-class spec sheets |
| Police cruiser | 4.9 × 1.95 × 1.7 | Explorer-class |
| Transit bus | 11.9 × 2.55 × 3.0 | standard 12 m-class |

Urban lane ≈ 3.0–3.6 m (NACTO/AASHTO) — one car per lane, matches road gen.

## Facades (meters above grade)

Storefront 4.2 (1 story) · Warehouse 6 · Brownstone 10 · Hotel 14 · Silo 12 ·
Glass tower 30 (~10 stories) · Megastructure 45 (~15) · Neon tower 60 (~20) ·
Arcology 90 (~30, landmark). Historic/docks stay low for canyon contrast.
Story height 3.0 m per research (residential 3.0–3.3, commercial 3.9–4.2).

## Street furniture

Lamp 5.5 m · tree 8 m · hydrant 0.75 m · bench 0.85 m · bollard 0.95 m ·
dumpster 1.4 m · vending machine 1.83 h × 0.9 w × 0.65 d (standards spec).

## Projection rules (engine-side)

1. Wall slices: `top = horizon − (H/d)·(h − eye)`, `base = horizon + (H/d)·eye`
   — the base always lands on the floor plane; centering was only valid for
   1-unit walls and produced "underground basements" for towers.
2. Sprites are floor-anchored: bottom row sits on the projected ground line
   (`horizon + (H/d)·eye`), never centered on the horizon.
3. Volumetric boxes use TRUE orthographic face spans:
   `face_px = (H/d) · face_units · |trig component|` — no normalization
   (normalizing collapsed a 4.5 m car toward its width at oblique angles).
4. Windows: glass band = sill 0.9 m to header 2.1 m on the window-cell face,
   computed via `Raycaster._window_span`.

## Process rule

Changing any dimension happens HERE, in one commit, with the regression
suites re-run (`tests/test_visual_grounding.py`, `tests/test_depth_skyline.py`,
`tests/test_world_scale.py`). Hand-tuning sizes in factories/renderers is a
gate finding.
