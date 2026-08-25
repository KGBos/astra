# Astra 3D — Production Task Board

> Pickable tickets on the road to v1.0. Plan: `docs/ROADMAP_PRODUCTION.md`.
> Designs: `docs/DESIGN_LOD_FIDELITY.md`, `docs/DESIGN_ENGINE_API.md`.
> Maintainer: Theo Lindqvist 🧭 (Cursor). Raise questions in my `inbox/`.

## How to claim a ticket

1. Check **Depends** — do not start a ticket whose dependencies are unmerged.
2. Put your name in the **Owner** column below and update your row in `BULLETIN.md`.
3. `git worktree add -b <branch> .worktrees/<your-name> master` (Guardrail #6 — one
   worktree per branch per task, never shared, never stacked).
4. Work only inside the files listed under **Owns**. If you need a file another live
   ticket owns, memo that owner first — this is what keeps parallel worktrees safe.
5. Open a PR with a green suite. Leon merges (Guardrail #5).

**Ready to start now, in parallel, zero file overlap: T-01, T-02, T-03, T-08.**

---

## Board

| ID | Title | Phase | Size | Owner | Status |
| :-- | :--- | :-- | :-- | :--- | :--- |
| T-01 | Re-baseline STATUS & README against measured reality | 0 | S | — | Ready |
| T-02 | Golden-frame regression harness | 0 | M | — | Ready |
| T-03 | CI perf gate at the real budget | 0 | S | — | Ready |
| T-04 | Split `raycaster.py` into seams | 1 | L | — | Blocked (T-02) |
| T-05 | Floor caster: kill per-pixel allocation | 1 | M | — | Blocked (T-04) |
| T-06 | Fuse post-FX into the primary write pass | 1 | M | — | Blocked (T-04) |
| T-07 | Wall slice: direct writes, hoisted LUTs | 1 | M | — | Blocked (T-04) |
| T-08 | Seed-reproducible entity spawning | 1 | S | — | Ready |
| T-09 | `MaterialRegistry` — named materials, no ID collisions | 2 | M | — | Blocked (T-04) |
| T-10 | `Scene` protocol + conformance | 2 | M | — | Blocked (T-09) |
| T-11 | `GridScene` loader — bring your own world | 2 | M | — | Blocked (T-10) |
| T-12 | Package split: `engine/` · `scenes/` · `game/` | 2 | L | — | Blocked (T-10) |
| T-13 | `MipTexture` pyramid with palette-indexed storage | 3 | L | — | Blocked (T-09) |
| T-14 | Per-column LOD selection | 3 | M | — | Blocked (T-13) |
| T-15 | Dithered cross-fade between levels | 3 | S | — | Blocked (T-14) |
| T-16 | World-anchored detail synthesis | 3 | L | — | Blocked (T-13) |
| T-17 | Near-field decal layer | 3 | L | — | Blocked (T-14) |
| T-18 | Sub-cell resolution via quadrant blocks | 3 | M | — | Blocked (T-14) |
| T-19 | Floor & ceiling LOD parity | 3 | M | — | Blocked (T-14, T-05) |
| T-20 | Sprite LOD ladder | 3 | M | — | Blocked (T-14) |
| T-21 | In-game help & pause overlay | 4 | S | — | Ready |
| T-22 | Settings persistence | 4 | M | — | Ready |
| T-23 | Seed bookmarks & share format | 4 | S | — | Blocked (T-08) |
| T-24 | Objectives driven by the landmark registry | 4 | L | — | Ready |
| T-25 | Adaptive quality governor | 4 | M | — | Blocked (T-14) |
| T-26 | Colour-depth fallback (truecolor / 256 / 16 / mono) | 4 | M | — | Blocked (T-02) |
| T-27 | Accessibility: palettes, contrast, reduced motion | 4 | M | — | Blocked (T-26) |
| T-28 | Crash safety, safe mode, tiny-terminal handling | 4 | S | — | Ready |
| T-29 | Split `procedural_gen.py` into seams | 4 | L | — | Blocked (T-02) |
| T-30 | zipapp packaging & `--version` | 5 | M | — | Blocked (T-12) |
| T-31 | Engine authoring guide + refreshed demo | 5 | M | — | Blocked (T-11) |
| T-32 | Branch hygiene, re-measure, tag v1.0 | 5 | S | — | Blocked (all) |

---

# Phase 0 — Truth & guard rails

### T-01 — Re-baseline STATUS & README against measured reality
**Size** S · **Branch** `<you>/status-rebaseline` · **Depends** none · **Ready**
**Owns**: `STATUS.md`, `README.md`

Every published number in our status docs is currently wrong. Re-measure and rewrite,
and treat this as a recurring release chore rather than a one-off.

**Done when**
- Test count says 211, not 209.
- FPS figures replaced with measured values (160.8 @80×32, 83.6 @120×40, 40.2 @160×50 on
  reference hardware) and labelled with the hardware they came from.
- The M4 row no longer claims the 60 FPS budget is met; it is marked **regressed** with a
  pointer to Phase 1.
- The stale `master @ 82ff314` pin is removed or updated.
- README structure tree includes the seven missing modules: `procedural_gen`, `interiors`,
  `npc`, `pedestrian`, `vehicle_controller`, `soundscape`, `cockpit_hud`.
- README controls table includes the eight missing keys: F, G, V, L, N, U, B, E, plus mouse.
- README FPS badge reflects a real, current measurement.
- STATUS has a populated **NOW** section again (it is currently all checked off).

### T-02 — Golden-frame regression harness
**Size** M · **Branch** `<you>/golden-frames` · **Depends** none · **Ready**
**Owns**: `tests/test_golden_frames.py`, `tools/golden_capture.py`, `tests/golden/**`

The single highest-leverage ticket on the board. Nearly every later ticket rewrites
pixel-producing code, and unit tests cannot tell you that a refactor changed the image.
This is what makes Phases 1–3 safe.

**Done when**
- `tools/golden_capture.py` renders a fixed matrix — seed, camera pose, time of day,
  weather, viewport, render mode — to deterministic framebuffer digests.
- At least 8 scenarios covering: day/night, clear/rain/fog, interior, driving, all three
  render modes, and both 80×32 and 160×50.
- `tests/test_golden_frames.py` fails loudly on any digest change and prints a readable
  diff (which cells changed, not just "not equal").
- Regenerating goldens is one documented command, so intentional visual changes are cheap
  to accept and accidental ones are impossible to miss.
- Runs in under 5 s so it stays in the default suite.

### T-03 — CI perf gate at the real budget
**Size** S · **Branch** `<you>/ci-perf-gate` · **Depends** none · **Ready**
**Owns**: `tools/bench_matrix.py`, `.github/workflows/ci.yml`

`FPS_FLOOR = 30.0` is half the documented guardrail, which is why a 60 → 40 FPS
regression landed without anything going red.

**Done when**
- Two-level gating: a hard **floor** that fails the build, and a **budget** (60 FPS) that
  is reported and fails once Phase 1 completes.
- Until Phase 1 lands, the budget check runs in warn-only mode so the board is not red
  for a known reason — but it prints the shortfall on every run.
- The benchmark job is not `continue-on-error`; a crash fails CI.
- Results append to a small committed history file so trends are visible across commits.
- The pty terminal-restore test from the Shift 1 review is added to CI.

---

# Phase 1 — Structure & performance

> **Ordering note.** T-04 lands first *on purpose*. Once the raycaster is split, T-05,
> T-06 and T-07 operate on different files and can run in genuinely parallel worktrees
> instead of fighting over a 1,700-line file. T-08 is independent of all of them.

### T-04 — Split `raycaster.py` into seams
**Size** L · **Branch** `<you>/raycaster-seams` · **Depends** T-02 · **Blocked**
**Owns**: `src/engine/raycaster.py` → new `src/engine/raycast/` package

Pure structural move. **Not one pixel may change** — T-02's goldens are the proof.

Target layout (from the Shift 1 review):

```
src/engine/raycast/
  column_dda.py       _cast_ray, _cast_ray_layers, RayHit
  wall_column.py      _draw_wall_slice, _draw_far_body
  floor_caster.py     the floor loop inside _render_sky_and_floor
  sky_renderer.py     sky gradient, clouds, stars, moon
  sprite_projector.py _render_sprites, _render_volumetric
  screen_fx.py        _render_wet_reflections, _postfx
  raycaster.py        thin facade: render() orchestration + z-buffer ownership
```

**Done when**
- All 211 tests green and all golden digests byte-identical.
- Shared per-frame state (`ppm`, `horizon_y`, `lights`, `haze_col`) passed as one
  `FrameContext` rather than long parameter lists.
- `src/engine/raycaster.py` re-exports the public surface so no call site changes.
- Dead code removed: unused `shade_lut` bindings (lines 595, 951), unused `plane_shade`
  (1390, 1394), unused `strongest_light_at` import (line 12).
- No file over 500 lines.
- Benchmark within 3% of pre-split (this is a move, not an optimisation).

### T-05 — Floor caster: kill per-pixel allocation
**Size** M · **Branch** `<you>/perf-floor-caster` · **Depends** T-04 · **Blocked**
**Owns**: `src/engine/raycast/floor_caster.py`

The largest single hotspot, ~1.0–1.5 ms/frame at 160×50. The inner loop allocates two
fresh RGB tuples per pixel, re-sorts the light-pool list every row, and churns a Python
list for active pools.

**Done when**
- No tuple allocation in the per-pixel path (write channels directly, or reuse buffers).
- Light-pool activation replaced with a precomputed per-row span structure — no per-row
  `sort()`, no `list.pop()` churn.
- Fog blend LUT lookups hoisted out of the pixel loop where the index is row-constant.
- Golden digests unchanged.
- Measured improvement reported at all three viewports.

### T-06 — Fuse post-FX into the primary write pass
**Size** M · **Branch** `<you>/perf-postfx-fusion` · **Depends** T-04 · **Blocked**
**Owns**: `src/engine/raycast/screen_fx.py`

`_postfx` traverses all 8,000 cells a second time purely to apply vignette and grain,
allocating a grain row and a vignette-LUT dict every frame. Vignette is a pure function
of cell position and can be folded into the primary write.

**Done when**
- Vignette is applied during primary writes via a precomputed per-cell factor table
  rebuilt only on resize.
- Grain is applied from a precomputed tile indexed by frame phase, not rebuilt per frame.
- The standalone full-frame pass is deleted, or reduced to genuinely global effects only.
- Golden digests unchanged (the maths must be equivalent, not merely similar).
- Measured improvement reported.

### T-07 — Wall slice: direct writes, hoisted LUTs
**Size** M · **Branch** `<you>/perf-wall-slice` · **Depends** T-04 · **Blocked**
**Owns**: `src/engine/raycast/wall_column.py`

Walls go through `buffer.set_pixel` — bounds check plus optional glyph transliteration
per pixel — while the floor writes `pixels[y][x]` directly. Bayer perturbation is
recomputed per row and the wash path allocates tuples.

**Done when**
- Direct pixel writes with the bounds check hoisted to the clipped row range.
- Per-column constants (Bayer column, blend LUTs, wash) computed once per column.
- Consistent write strategy documented so walls, floor and sprites no longer disagree.
- Golden digests unchanged; measured improvement reported.

### T-08 — Seed-reproducible entity spawning
**Size** S · **Branch** `<you>/deterministic-spawns` · **Depends** none · **Ready**
**Owns**: `src/entities/traffic_manager.py`, `src/entities/pedestrian_manager.py`,
`src/entities/pedestrian.py`, `src/entities/npc.py`, `tests/test_determinism.py`

Verified in the Shift 1 review: the same seed produces an identical wall grid but
different vehicle and pedestrian placements, because these modules call the global
`random` module. `procedural_gen.py` already does this correctly with `random.Random`.

**Done when**
- Both managers own a `random.Random` derived from `city_map.seed` with a per-system salt.
- Pedestrian runtime behaviour (archetype, timers, turns, speech) draws from an injected
  instance, not module-level `random`.
- Hardcoded NPC coordinates in `npc.py:108-153` are seed-placed, or explicitly documented
  as fixed story anchors with a bounds check for the 320 m map.
- New `tests/test_determinism.py` asserts two `CityMap`+`TrafficManager`+
  `PedestrianManager` builds at the same seed are identical, and that different seeds differ.
- `CityMap(seed=None)` records the seed it chose so a session is reproducible after the fact.

---

# Phase 2 — Engine core

### T-09 — `MaterialRegistry`
**Size** M · **Branch** `<you>/material-registry` · **Depends** T-04 · **Blocked**
**Owns**: `src/engine/materials.py` (new), `src/world/textures.py`

Fixes a live bug and builds the foundation LOD needs. `WALL_PERIMETER = 5` and
`WALL_WAREHOUSE = 5` currently alias, so the city's boundary renders as a warehouse
facade — and `get_texture` masks unknown IDs by falling back to skyscraper glass, which
hides the whole bug class.

**Done when**
- `Material` dataclass per `DESIGN_ENGINE_API.md` §4; registration allocates IDs so
  collisions are structurally impossible.
- Perimeter and warehouse are distinct materials with distinct art.
- Unknown-ID lookup raises instead of silently returning glass.
- Existing integer constants remain as registry-backed aliases; suite stays green.

### T-10 — `Scene` protocol + conformance
**Size** M · **Branch** `<you>/scene-protocol` · **Depends** T-09 · **Blocked**
**Owns**: `src/engine/scene.py` (new), `src/world/city_map.py`, `src/world/interiors.py`

**Done when**
- `Scene` declared per `DESIGN_ENGINE_API.md` §3, zero-dependency safe on Python 3.8
  (`TYPE_CHECKING` protocol with an ABC fallback — do **not** add `typing_extensions`).
- `CityMap` and `InteriorView` both conform, with old method names kept as shims.
- A conformance test suite any scene implementation can be run against.
- The renderer type-hints `Scene`, not `CityMap`.

### T-11 — `GridScene` loader — bring your own world
**Size** M · **Branch** `<you>/grid-scene` · **Depends** T-10 · **Blocked**
**Owns**: `src/scenes/grid_scene.py` (new), `examples/**`, `tests/test_grid_scene.py`

The ticket that makes the engine claim real and demonstrable.

**Done when**
- A plain-text/JSON format: character grid, character→material legend, spawn point,
  optional per-material height overrides.
- `python3 main.py --scene examples/maze.txt` walks a world that has nothing to do with
  the city.
- At least three worked examples (a maze, a single room, a terrain-ish heightfield stub).
- Format documented with a copy-pasteable minimal example.
- Small `GridScene` fixtures adopted as the fast deterministic base for renderer tests.

### T-12 — Package split: `engine/` · `scenes/` · `game/`
**Size** L · **Branch** `<you>/package-split` · **Depends** T-10 · **Blocked**
**Owns**: repo-wide module moves — **coordinate before starting; conflicts with everything**

**Done when**
- `engine/` imports nothing from `scenes/` or `game/`, enforced by a test that walks imports.
- The world → entities inversion at `procedural_gen.py:33-46` is unwound.
- All 211 tests green; golden digests unchanged.

---

# Phase 3 — Visual fidelity

> Full design in `docs/DESIGN_LOD_FIDELITY.md`. Read it before picking any of these up.
> The measured problem: at 160×50 the break-even for one texel per character cell is
> ~78 m, so **the entire near field is magnified** — 9.8 cells per texel at 8 m, 39 at 2 m.

### T-13 — `MipTexture` pyramid with palette-indexed storage
**Size** L · **Branch** `<you>/mip-pyramid` · **Depends** T-09 · **Blocked**
**Owns**: `src/engine/miptexture.py` (new), `src/world/textures.py`

**Done when**
- Levels L0–L4 at 8/16/32/64/128, L0 being today's hand-authored art **unchanged**.
- Storage is `str` glyphs + `bytearray` palette indices + shared palette (design §3.1) —
  a naive nested-tuple layout costs ~2 MB per material and is not acceptable.
- Levels build lazily on first use and are cached.
- A pyramid-consistency test: downsampling level *n* reproduces level *n−1* within tolerance.
- Memory for a full city's materials measured and reported; budget ≤ 5 MB.
- Golden digests unchanged (nothing samples above L0 yet).

### T-14 — Per-column LOD selection
**Size** M · **Branch** `<you>/lod-selection` · **Depends** T-13 · **Blocked**
**Owns**: `src/engine/raycast/wall_column.py`, `src/engine/lod.py` (new)

The ticket where the feature becomes visible.

**Done when**
- Level chosen once per column from `span / TARGET_CELLS_PER_TEXEL` (design §3.2), never
  per pixel.
- `--lod off|auto|<fixed>` flag for A/B comparison and for the golden harness.
- **Distance-monotonicity test**: distinct glyph count across a wall face at 64/32/16/8/4 m
  increases monotonically. This is the automated statement of the feature.
- Benchmark impact reported at all three viewports; must not breach the Phase 1 budget.
- Golden digests regenerated with `--lod off` still byte-identical.

### T-15 — Dithered cross-fade between levels
**Size** S · **Branch** `<you>/lod-crossfade` · **Depends** T-14 · **Blocked**
**Owns**: `src/engine/lod.py`

**Done when**
- Fractional level dithers between neighbours via the existing Bayer matrix (design §3.3):
  one texture fetch, no blend arithmetic.
- A walk-toward-wall test shows no single-frame discontinuity in glyph-distribution
  statistics at level boundaries.
- Measured cost is within noise.

### T-16 — World-anchored detail synthesis
**Size** L · **Branch** `<you>/lod-detail-synth` · **Depends** T-13 · **Blocked**
**Owns**: `src/engine/detail_synth.py` (new), `src/engine/miptexture.py`

Generates L1–L4 from L0 plus a detail octave. **The correctness bar here is crawl-freedom**
— get it wrong and the feature is worse than not shipping.

**Done when**
- Detail hashed on material identity and UV texel coordinates only — never on screen
  position, camera state, or frame counter (design §3.4).
- **No-crawl test**: translating the camera parallel to a wall in small steps leaves the
  glyph at a fixed *world* point on that wall unchanged.
- Upsampling preserves the parent average in both glyph density and colour, so T-15's
  cross-fade is statistically invisible.
- Per-material detail character is art-directable, not one generic noise for everything.

### T-17 — Near-field decal layer
**Size** L · **Branch** `<you>/near-field-decals` · **Depends** T-14 · **Blocked**
**Owns**: `src/engine/decals.py` (new), `src/world/textures.py` decal tables

Where most of the *perceived* realism lives: noise gives texture, decals give features.
A wall should read as a specific door, not a well-textured rectangle.

**Done when**
- Per-material decal tables: door handles, buzzer panels, signage, grime, cracks, rivets,
  AC units, fire escapes, meter boxes.
- Placement deterministic on `(map_x, map_y, side)` — a building's handle is always in the
  same place.
- Strictly range-gated (~12 m) so the skyline pays nothing; prove it with a benchmark at a
  viewpoint with no near geometry.
- Decals composite over the mip sample and respect lighting, fog and haze.
- ASCII purity preserved in `--no-color`.

### T-18 — Sub-cell resolution via quadrant blocks
**Size** M · **Branch** `<you>/subcell-blocks` · **Depends** T-14 · **Blocked**
**Owns**: `src/engine/subcell.py` (new), `src/renderer/screen_buffer.py` transliteration

Closes the last stretch: even L4 leaves ~2.5 cells per texel at 2 m.

**Done when**
- 2×2 coverage mask per cell → quadrant glyph (`▘▝▖▗▀▄▌▐▚▞█`), 16-entry table.
- Engaged below ~5 m only.
- Transliteration entries added so `--no-color` still emits pure ASCII —
  `test_render_modes.py` must stay green untouched.
- A/B screenshots at 2 m and 4 m attached to the PR.

### T-19 — Floor & ceiling LOD parity
**Size** M · **Branch** `<you>/floor-lod` · **Depends** T-14, T-05 · **Blocked**
**Owns**: `src/engine/raycast/floor_caster.py`

Ground fills the lower half of the frame, so this is a large share of the visible win.

**Done when**
- Same selection function driven by the floor caster's existing `row_distance`.
- Near-field ground detail: kerb edges, drain grates, road markings, paving joints, litter.
- No crawl as the camera moves (same test discipline as T-16).
- Benchmark impact reported; T-05's gains must not be given back.

### T-20 — Sprite LOD ladder
**Size** M · **Branch** `<you>/sprite-lod` · **Depends** T-14 · **Blocked**
**Owns**: `src/entities/sprite.py`, `src/engine/raycast/sprite_projector.py`

**Done when**
- Each sprite declares a resolution ladder (silhouette → detailed → close-up), selected on
  the same distance metric as walls.
- A pedestrian at 2 m shows facial/clothing detail; at 40 m it is a clean silhouette.
- Vehicles gain near-field detail: window frames, wheel arches, badges.
- No popping between rungs (reuse T-15's dither).

---

# Phase 4 — Production polish

### T-21 — In-game help & pause overlay
**Size** S · **Branch** `<you>/help-overlay` · **Depends** none · **Ready**
**Owns**: `src/renderer/help_overlay.py` (new), `src/game.py` key handling

There is currently no way to discover the controls without quitting to read `--help`.
**Done when**: `?`/`F1` opens a scrollable control reference; `P` pauses with a dimmed
frame; both restore cleanly; the overlay is generated from the same key table as `--help`
so the two cannot drift.

### T-22 — Settings persistence
**Size** M · **Branch** `<you>/settings-persist` · **Depends** none · **Ready**
**Owns**: `src/config.py` (new), `main.py`
**Done when**: `~/.config/astra3d/config.json` stores render mode, audio, FPS target,
viewport and accessibility choices; CLI flags override the file; a corrupt file warns and
falls back to defaults rather than crashing; `--reset-config` exists.

### T-23 — Seed bookmarks & share format
**Size** S · **Branch** `<you>/seed-bookmarks` · **Depends** T-08 · **Ready after T-08**
**Owns**: `src/world/seed_book.py` (new), `src/renderer/hud.py`
**Done when**: name and save the current seed in-game; list and jump to bookmarks; a
short shareable string round-trips seed plus spawn pose. Depends on T-08 because a shared
seed that does not reproduce is worse than no sharing.

### T-24 — Objectives driven by the landmark registry
**Size** L · **Branch** `<you>/objectives` · **Depends** none · **Ready**
**Owns**: `src/game/objectives.py` (new), `src/renderer/hud.py` objective panel
The city is rich but there is nothing to *do* in it. **Done when**: an objective system
generates POI goals from the existing landmark registry (visit, photograph, deliver,
courier-by-vehicle); HUD shows current objective with distance and bearing; completion is
persisted per seed; objectives are seed-deterministic.

### T-25 — Adaptive quality governor
**Size** M · **Branch** `<you>/adaptive-quality` · **Depends** T-14 · **Blocked**
**Owns**: `src/engine/quality.py` (new), `src/game.py`
**Done when**: a governor watches frame time and steps effects down in a documented order
(LOD cap → decals → bloom → wet reflections → grain) to hold the target, and steps back up
with hysteresis so it does not oscillate; `--quality low|medium|high|auto`; the current
tier is visible in the HUD.

### T-26 — Colour-depth fallback
**Size** M · **Branch** `<you>/color-depth` · **Depends** T-02 · **Blocked**
**Owns**: `src/renderer/screen_buffer.py` colour emit path, `src/renderer/palette.py` (new)
Today it is truecolor or nothing. **Done when**: truecolor / 256 / 16 / mono paths with
auto-detection from `COLORTERM` and `TERM`, `--color-depth` override, quantisation tables
with dithering for the 256 and 16 paths, and golden coverage for each depth.

### T-27 — Accessibility
**Size** M · **Branch** `<you>/accessibility` · **Depends** T-26 · **Blocked**
**Owns**: `src/renderer/palette.py`, `src/config.py`
**Done when**: colourblind-safe palettes (deuteranopia, protanopia, tritanopia); a
high-contrast mode; `--reduced-motion` disabling grain, bloom pulsing, lightning flashes
and camera bob; all selectable from persisted settings.

### T-28 — Crash safety, safe mode, tiny terminals
**Size** S · **Branch** `<you>/crash-safety` · **Depends** none · **Ready**
**Owns**: `src/renderer/terminal.py`, `main.py`
Terminal restore itself is verified sound — this is about what surrounds it.
**Done when**: unexpected exceptions restore the terminal *and* write a crash log with
version, seed and pose; `--safe-mode` boots with all effects off; a terminal below the
minimum viewport shows a clear message instead of rendering garbage; the narrow
partial-failure path in `enter_raw_mode` (`terminal.py:60-61`, which can leave raw mode set
with no safety nets installed) is closed.

### T-29 — Split `procedural_gen.py` into seams
**Size** L · **Branch** `<you>/worldgen-seams` · **Depends** T-02 · **Blocked**
**Owns**: `src/world/procedural_gen.py` → `src/world/gen/` package
**Done when**: split into `road_graph`, `road_planner`, `district_zoner`, `block_massing`,
`harbor`, `landmarks`, `map_data`, with `city_generator` as orchestration only; no file
over 500 lines; identical output for identical seeds (assert with T-08's determinism test);
`RoadGraph.short_path`'s `queue.pop(0)` swapped for a `deque`.

---

# Phase 5 — Release

### T-30 — zipapp packaging & `--version`
**Size** M · **Branch** `<you>/packaging` · **Depends** T-12 · **Blocked**
**Owns**: `tools/build_zipapp.py` (new), `.github/workflows/release.yml` (new)
**Done when**: `python3 -m zipapp` produces a single runnable `astra3d.pyz` with zero
dependencies; CI builds and attaches it to tagged releases; `--version` reports version
and build hash; verified on Python 3.8 and 3.12.

### T-31 — Engine authoring guide + refreshed demo
**Size** M · **Branch** `<you>/authoring-guide` · **Depends** T-11 · **Blocked**
**Owns**: `docs/AUTHORING_SCENES.md` (new), `docs/ARCHITECTURE.md`, `README.md`
**Done when**: a guide takes a reader from blank file to walkable scene in under ten
minutes; `ARCHITECTURE.md` documents the `Scene` boundary and the LOD pipeline; the demo
recording is re-captured with LOD on.

### T-32 — Branch hygiene, re-measure, tag v1.0
**Size** S · **Branch** `<you>/release-v1` · **Depends** all · **Blocked**
**Owns**: `STATUS.md`, git refs
**Done when**: the eight fully-merged remote branches are pruned; `nora-voss/worktree`'s
24 unmerged commits (perspective overhaul, world-scale registry, life-size vehicles, plus
`src/world/scale.py`, `src/entities/vehicle_dims.py` and two test files) are landed or
explicitly retired; the stray empty `astra-main-tmp/` directory is removed; every number in
STATUS and README is re-measured on the day of tagging; `v1.0` tagged.

---

## Open decisions for Leon

These shape the plan and I do not want to assume:

1. **Windows support** — currently out of scope (POSIX `termios`/`tty`). Confirm we
   document macOS/Linux only for v1.0, or add it as a phase.
2. **Audio** — harden it, or label it experimental for v1.0? It shells out to external
   players and re-runs `which` on every play.
3. **`nora-voss/worktree`** — 24 unmerged commits including a perspective overhaul that
   overlaps Phase 3 territory. Land it before Phase 3 starts, or retire it? This is the
   biggest sequencing risk on the board.
4. **Unicode blocks** — T-18 needs quadrant glyphs in colour mode (ASCII mode still
   transliterates). Confirm that fits the "pure ASCII" identity.
