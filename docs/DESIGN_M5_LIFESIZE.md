# M5 Design Spec: Life-Sized World

Status: APPROVED direction (Leon, mega-map + full pillar 1+2). Owner: Marcus Vance. Execution via gated worktree cycles.

## 1. Diagnosis
Current world is 42×42 tiles ≈ a diorama: crossable on foot in ~9s, roads 2 tiles wide, tallest tower ~3.2 tile-heights, blocks smaller than tennis courts. Nothing is at human proportion.

## 2. Unit Semantics (Pillar 1)
- **1 tile = 1 meter**, everywhere, honestly. HUD distances become true meters.
- Camera: eye height 1.7 m; collision radius 0.35 m (shoulders).
- Speeds: walk 3.6 m/s, sprint 7.2 m/s; jump tuned for ~1 m clearance.
- Vertical rework: `height_mult` becomes meters-per-texture-height. Storefronts ~4 m, brownstones 10–12 m, midrise 15–30 m, towers 30–60 m. Wall slice projection consumes true height.
- Sprites: pedestrians 1.75 m tall × 0.5 m; vehicles 1.5 m × 4.5 m; lamps 6 m.

## 3. Map Model
- **Mega-map**: single deterministic grid, default **320×320**, CLI-overridable to 512. Grid memory is trivial (<1 MB).
- Spawn: downtown core, on an avenue.
- Seed format unchanged; existing seeds invalidate (documented breaking change).

## 4. Generator v2 (Pillar 2) — replaces uniform-grid layout
- **Road hierarchy**: arterials every 40–56 tiles (width 14: 2×5 lanes + planted median), collectors every 16–24 (width 9: 2 lanes + parking), local lanes width 5 inside big blocks.
- **Irregular blocks**: recursive subdivision of super-blocks; alleys cut through anything wider than 34 tiles.
- **District zoning at scale**: downtown tower cluster (heights 25–60 m) within ~90 m of center; midrise ring 8–20 m; industrial low-sprawl with yards; a real park (>80×80); harbor front with quay walls.
- **Landmarks**: true footprints, spaced 150–400 m apart, each with a plaza or approach vista.
- Traffic lanes derive from measured road geometry; speeds in m/s (arterial cruise ~13, collector ~9).
- NPC/pedestrian density proportional to district area; walkable-scan must remain O(cells) cheap (320² = 102k cells, fine).
- Interiors: tower lobbies as tall interior volumes; street-level shops on collectors.

## 5. Performance Budget (non-negotiable, lands WITH this milestone)
- Target ≥60 FPS @ 160×50 viewport, full weather, on reference hardware.
- Near-tier DDA steps scale with sight distance (≈28–34), far-tier stride sampling carries the skyline; floor-casting remains the hot suspect — profile before optimizing.
- Benchmark matrix added to CI: 80×32, 120×40, 160×50.

## 6. Migration Checklist
- [x] textures.py height_mult table → meters (Cycle A)
- [x] camera.py speeds/eye/jump/radius (Cycle A)
- [x] raycaster horizon/projection constants audit for non-square assumptions (Cycle A: FOV-derived `pixels_per_meter_at_1m`, eye-height-anchored wall/sprite/floor projection)
- [ ] traffic_manager spawn/lane math off ns_road_cols hardcode (Cycle A interim: road-index cruise classes 13/9/5 m/s; real hierarchy lands with Generator v2)
- [ ] pedestrian_manager walkable scan + archetype districts (scan verified <0.5 s at 320²; district archetypes Cycle B)
- [ ] procedural_gen full rewrite (v2) behind seed contract (existing generator verified functional at default 320×320; spawn spiral capped at radius 24 + avenue fallback)
- [x] hud minimap zoom (fixed radius is useless at city scale) + distance readouts (Cycle A: `M` cycles OFF → NEAR 31 m → FAR 95 m auto-scaled radar)
- [ ] landmark registry spacing + compass ranges
- [x] vehicle_controller top speeds (m/s) + cockpit gauges (Cycle A: km/h readout, type tops 16/14/12/9 m/s)
- [ ] tests: determinism, spawn safety, benchmark matrix (determinism + spawn safety + honesty suite landed in Cycle A, `tests/test_units_honesty.py`; CI benchmark matrix deferred — no CI change this cycle)

## 7. Execution Plan (each = builder agents in worktrees → review gate → merge)
1. **Cycle A — Honest Units**: camera/speeds/textures/map-size plumbing on existing layout. Playable checkpoint of the feel.
2. **Cycle B — Generator v2**: hierarchy, irregular blocks, districts, landmarks at scale.
3. **Cycle C — Density & Budget**: traffic/NPC retune, interiors lobbies, perf budget enforcement + CI benchmarks.
