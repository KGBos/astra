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

**Ready to start now, in parallel, zero file overlap: T-01, T-02 (claimed), T-03, T-08, T-34.**

---

## Decisions from Leon (2026-08-24)

1. **Audio — experimental.** Visuals come first; audio is not a v1.0 quality target.
   Ships mute-default and clearly labelled. → **T-39**.
2. **Windows — yes.** Native terminal support is wanted. Effort is moderate and
   stdlib-only (`msvcrt` input, `ctypes` VT-mode enable, polled resize). → **T-38**.
   Note: a web backend (**T-37**) delivers Windows for free, so T-38 is scheduled
   *after* the backend interface exists rather than as a bespoke port.
3. **Nora's branch — evaluated, salvaged, retired.** See "Salvage record" below.
4. **Render aesthetic — this is now a headline v1.0 concern.** Leon's position: coloured
   **ASCII** mode should be coloured *characters* on the terminal's own background, not
   coloured cells. Cell-fill rendering "is just a pixelated game". A background-filled
   mode may still exist, but it must be *a* mode, not *the* mode, and each mode must be
   art-directed rather than a degradation of the default. → **T-33, T-34, T-35**.
5. **Terminal vs. web — do not choose; abstract the backend.** The renderer already
   emits a grid of `(glyph, fg, bg)` cells, which is backend-agnostic. → **T-36**
   (interface, cheap, now) then **T-37** (web canvas spike, timeboxed). The terminal
   stays the reference backend and Guardrail #1 is untouched.

### Salvage record — `nora-voss/worktree` (24 commits, retired)

Archived as tag **`archive/nora-voss-worktree`** before deletion; nothing is lost and any
commit can be recovered with `git show archive/nora-voss-worktree`.

| Item | Verdict | Reasoning |
| :--- | :--- | :--- |
| Far-tier skyline layering fix | **Adopted** (landed) | Real bug on master: an unconditional `break` on the first solid far cell meant the 180 m tier could only ever return one layer, so `max_height` never updated and the height test guarding the append was dead code. Measured: 0 → 268 columns with stacked distant silhouettes. Locked by `tests/test_far_tier_layering.py`. |
| Perspective overhaul (`_v_proj`) | **Rejected** | Superseded. Master's `pixels_per_meter_at_1m` derives vertical FOV properly from the ray plane; Nora's is a cruder `(w/2)/plane_len/CELL_ASPECT`. Her branch also uses the **reciprocal** `CELL_ASPECT` convention (2.0 vs master's 0.5), so merging would silently invert vertical scale. |
| `src/world/scale.py` | **Rejected as a file, adopted as data** | A central scale registry is the right idea, but landing it now creates a second source of truth alongside `textures.py`. Its `FACADE_HEIGHTS_M` table is the reference data for **T-09** (`MaterialRegistry`) — pull the values from the archive tag. |
| `src/entities/vehicle_dims.py` | **Rejected as a file, adopted as data** | Good metric reference, but its only consumer was her sprite rework. Landing it alone is dead code. Reference data for **T-20** (sprite LOD). |
| `test_visual_grounding.py`, `test_world_scale.py` | **Rejected as written, intent adopted** | Both assert against her projection maths. The *intent* — no sunken basements, no hovering sprites — is a genuine gap and becomes an acceptance criterion on **T-19**/**T-20**. |

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
| T-33 | Per-material luminance→glyph ramps | 3b | M | **Nora Voss** ⚙️ | In progress (`nora-voss/t33-material-glyph-ramps`) |
| T-34 | Sky drawn as glyph density | 3b | M | — | Ready (independent of T-33) |
| T-35 | Formal mode matrix (`blocks`/`ascii-color`/`ascii-mono`), art-directed | 3b | M | — | Ready (after T-33/T-34 land) |
| **T-33** | **ASCII glyph luminance ramp** | **3** | **M** | — | **Ready** |
| **T-34** | **Sky as glyphs, not background fill** | **3** | **M** | — | **Ready** |
| **T-35** | **Formalise the render-mode matrix** | **3** | **M** | — | Blocked (T-33, T-34) |
| **T-36** | **`Display` backend interface** | **2** | **M** | — | Blocked (T-02) |
| **T-37** | **Web canvas backend (timeboxed spike)** | **6** | **L** | — | Blocked (T-36) |
| **T-38** | **Windows support** | **4** | **M** | — | Blocked (T-36) |
| **T-39** | **Label audio experimental** | **4** | **S** | — | Ready |

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
**Size** M · **Branch** `<you>/subcell-blocks` · **Depends** T-14, T-35 · **Blocked**
**Owns**: `src/engine/subcell.py` (new), `src/renderer/screen_buffer.py` transliteration

Closes the last stretch: even L4 leaves ~2.5 cells per texel at 2 m.

**Scope correction (Leon, 2026-08-24)**: quadrant blocks are Unicode box-drawing glyphs,
not ASCII. They therefore belong to the **`blocks` render mode only** and must never
appear in `ascii-color` or `ascii-mono`, where the character set is the whole point. In
the ASCII modes the equivalent near-field resolution comes from T-33's glyph ramp and
T-17's decals instead. Do not start this before T-35 has established the mode matrix.

**Done when**
- 2×2 coverage mask per cell → quadrant glyph (`▘▝▖▗▀▄▌▐▚▞█`), 16-entry table.
- Engaged below ~5 m and **only** in `blocks` mode.
- ASCII modes are provably unaffected: `test_render_modes.py` green, plus an assertion
  that no non-ASCII glyph reaches the buffer in either ASCII mode.
- A/B captures at 2 m and 4 m attached to the PR.

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

# Phase 3b — Render aesthetic (the ASCII identity)

> Added after Leon's 2026-08-24 direction. **Measured starting point**: `--no-fill`
> already emits zero background codes (verified: 1,236 → 0 `48;2;` sequences), so the
> mode Leon wants mechanically exists. It looks weak for two specific reasons, both
> fixable and both ticketed here:
> 1. Wall glyphs come straight from the texture pattern and encode **no luminance** —
>    a lit wall and a shadowed wall print the identical `#####%######%#%`. All the depth
>    and lighting information lives in the colour, so stripping the fill strips the form.
> 2. **23% of sky cells carry a space glyph** with only a background colour, so with
>    fills off the sky disappears into the terminal background entirely.

### T-33 — ASCII glyph luminance ramp
**Size** M · **Branch** `<you>/glyph-ramp` · **Depends** none · **Ready**
**Owns**: `src/engine/glyph_ramp.py` (new), `src/world/textures.py` ramp declarations

The core of the ASCII identity. In ASCII modes the **character must carry the shading**,
not just the colour. Each material declares a density ramp (e.g. `" .:-=+*#%@"` plus
structural glyphs), and the final glyph is chosen from computed luminance — shade,
ambient, point lights, fog — rather than read verbatim from the texture.

**Done when**
- A luminance → glyph selection stage sits between shading and the buffer write.
- Per-material ramps, art-directable: glass reads differently from brick from concrete,
  and structural glyphs (mullions, courses, lintels) survive at their own luminance bands.
- A lit wall and a shadowed wall are **visibly different with colour disabled** — assert
  it: glyph histograms for the same wall at two ambient levels must differ.
- Ramp choice is stable under small luminance jitter (no flicker); Bayer dithering applies
  to ramp *index*, not to colour, in ASCII modes.
- Golden coverage for `ascii-color` and `ascii-mono`.

### T-34 — Sky as glyphs, not background fill
**Size** M · **Branch** `<you>/ascii-sky` · **Depends** none · **Ready**
**Owns**: `src/engine/raycast/sky_renderer.py` (post T-04; today `raycaster.py` sky block)

The sky is currently a background-colour gradient behind space glyphs — the clearest case
of "colour doing work the characters should do". With fills off there is no sky at all.

**Done when**
- Sky renders as glyph density: a vertical ramp from zenith to horizon, cloud structure as
  stippled characters, stars and moon as glyphs (they already are).
- The gradient reads as a gradient in `ascii-mono` with no colour whatsoever.
- No space-glyph-plus-background cells remain in the sky band in ASCII modes.
- Existing `test_render_modes.py:41` sky-ASCII contract still holds.
- Same treatment audited for the floor/ground band, which has the same failure mode.

### T-35 — Formalise the render-mode matrix
**Size** M · **Branch** `<you>/render-modes` · **Depends** T-33, T-34 · **Blocked**
**Owns**: `main.py` flags, `src/renderer/screen_buffer.py` mode plumbing, `docs/CONTROLS.md`

Today's modes are flags that *subtract* from a filled-cell default (`--no-fill`,
`--no-color`). Make them first-class, named, and individually art-directed.

**Done when**
- `--render blocks|ascii-color|ascii-mono` with `--no-fill`/`--no-color` kept as aliases.
- **`ascii-color`** — coloured ASCII glyphs on the terminal's own background, zero
  background fills. This is the mode Leon wants and it becomes the **default**.
- **`blocks`** — today's filled-cell look, retained as an explicit choice.
- **`ascii-mono`** — no colour at all; form carried entirely by glyph density.
- In-game cycling (a key binding) so modes can be compared live.
- Golden-frame coverage for all three; each is judged on its own terms, not as a
  degradation of another.
- `README.md` and `docs/CONTROLS.md` document the aesthetic intent of each mode.

---

# Phase 2b — Display backend

### T-36 — `Display` backend interface
**Size** M · **Branch** `<you>/display-backend` · **Depends** T-02 · **Blocked**
**Owns**: `src/renderer/display.py` (new), `src/renderer/terminal.py`, `src/game.py` flush path

The renderer already produces a grid of `(glyph, fg, bg)` cells — that is inherently
backend-agnostic. Nothing declares it, so the ANSI terminal is hardwired as the only
possible output. This is the same abstraction move as the `Scene` protocol, applied to
output, and it is what makes the terminal-vs-web question **reversible instead of a bet**.

**Done when**
- A `Display` interface: `size()`, `present(buffer)`, `poll_input()`, `enter()`, `exit()`.
- `TerminalDisplay` wraps the current ANSI + termios path with **no behaviour change** —
  golden digests and the pty restore tests unchanged.
- `ScreenBuffer` no longer knows about ANSI; escape-sequence generation moves into the
  terminal backend.
- A `NullDisplay` for headless benchmarking and tests.
- Input is part of the backend contract, since a web backend has entirely different input.

### T-37 — Web canvas backend (timeboxed spike)
**Size** L · **Branch** `<you>/web-backend` · **Depends** T-36 · **Blocked** · **Phase 6**
**Owns**: `src/renderer/web_display.py` (new), `web/**` (new)

**Timebox: one shift.** Deliver a judgement, not a product. The terminal remains the
reference backend regardless of outcome; this exists to find out whether the terminal is
the ceiling on ASCII fidelity.

Why it is worth trying: the terminal caps us at a fixed font, a ~1:2 cell aspect we can
only correct for rather than control, ~8,000 cells at 160×50, and ANSI throughput. A
canvas backend controls the font and cell aspect exactly, renders 400×150 glyphs without
strain, can push the glyph atlas to the GPU so frame budget stops constraining LOD and
decals, gets real key-down/key-up and pointer lock, is shareable by URL, and delivers
Windows and mobile for free. **It is still 100% ASCII** — the aesthetic is the glyph grid,
not the terminal that happens to host it.

**Done when**
- Zero-dependency transport: stdlib `http.server` serving a static page plus a frame
  stream. Do **not** add a websocket library.
- The same `Game` loop drives it through `Display` with no engine changes.
- A written recommendation with measured numbers: cells/frame, FPS, latency, input
  fidelity, and an honest assessment of whether it should become the primary target.
- Explicitly answers: does this unlock fidelity the terminal cannot reach?

### T-38 — Windows support
**Size** M · **Branch** `<you>/windows-support` · **Depends** T-36 · **Blocked**
**Owns**: `src/renderer/windows_display.py` (new), `.github/workflows/ci.yml`

Confirmed wanted. Genuinely feasible stdlib-only — no dependency-guardrail risk.

**Done when**
- `msvcrt`-based non-blocking input backend (`kbhit`/`getwch`) behind the `Display`
  contract, replacing the `termios`/`tty`/`select` path.
- VT processing enabled via `ctypes` (`ENABLE_VIRTUAL_TERMINAL_PROCESSING`) so ANSI
  truecolor works in Windows Terminal and modern conhost.
- Resize handled by polling `os.get_terminal_size()` — Windows has no `SIGWINCH`.
- Console mode restored on every exit path, including Ctrl+C and Ctrl+Break; pty-equivalent
  test adapted for Windows.
- `windows-latest` added to the CI matrix.
- README platform support updated.

---

# Phase 4 addendum

### T-39 — Label audio experimental
**Size** S · **Branch** `<you>/audio-experimental` · **Depends** none · **Ready**
**Owns**: `src/audio/soundscape.py` docstring, `main.py` help text, `README.md`, `STATUS.md`

Leon's call: audio is not a v1.0 quality target. Make that explicit rather than ambiguous,
and remove the two ways it can stall the main thread.

**Done when**
- `--audio` help text and README mark it **experimental**; mute-default is unchanged.
- Sound-bank synthesis moves off the calling thread, so neither startup with `--audio` nor
  pressing `V` can hitch a frame.
- The per-play `which paplay` subprocess probe is cached once at init.
- No hardening beyond that; the module is explicitly out of scope for v1.0 polish.

---

## Open decisions

All four questions from the first pass are now answered — see **Decisions from Leon** at
the top of this board. One new question is outstanding:

1. **Does `ascii-color` become the default?** T-35 assumes yes, on Leon's stated
   preference for coloured characters over coloured cells. That changes the look of every
   screenshot and demo we have, so it is worth confirming before T-35 lands rather than
   after.
2. **If T-37's spike is convincing, does the web backend become the primary target?**
   Deferred until there are measured numbers to argue over. The terminal stays supported
   either way, so this can be decided late.
