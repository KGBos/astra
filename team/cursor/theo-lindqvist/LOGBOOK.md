# Logbook — Theo Lindqvist 🧭

## Shift 1 — Onboarding & Full Project Review

**Onboarded** into the open Cursor Platform Lead seat (Lead Systems Refactoring
Engineer). Created dossier, registered in `team/DIRECTORY.md`, claimed a radar row in
`team/BULLETIN.md`. `team/cursor/` did not exist before this shift — I am the founding
seat on this platform.

**Task**: full project review requested by Leon.

### Method
Ran the verification baseline first, then reviewed by subsystem, then wrote a throwaway
harness to reproduce every runtime claim before recording it. Scratch harness deleted.

- Suite: `python3 -m unittest discover -s tests` → **211 passed** in 4.9s.
- Benchmarks: 160.8 FPS @80×32, 83.6 FPS @120×40, **40.2 FPS @160×50**.
- Terminal lifecycle tested under a real pty across three exit paths.

### Confirmed findings
1. **Perf budget breached.** 160×50 measures 40 FPS against the 60 FPS budget in
   AGENTS.md Guardrail #2. STATUS.md §4 still claims the M4 budget is met at
   "medians 196–446 FPS", and §5 claims "~300-450 FPS @80×32" against a measured 160.
   Rendering 2.0 spent the entire headroom; the ledger was never re-measured.
2. **CI cannot catch it.** `tools/bench_matrix.py` floor is 30.0 FPS, half the budget.
   The guardrail is documented but unenforced.
3. **Entity spawning is not seed-reproducible.** Same seed → identical wall grid, but
   different vehicle and pedestrian placements. `traffic_manager.py` and
   `pedestrian_manager.py` use the global `random` module instead of a seeded instance.
4. **Wall texture ID collision.** `WALL_PERIMETER = 5` and `WALL_WAREHOUSE = 5`
   (`procedural_gen.py:73,78`) — perimeter renders as warehouse facade.
5. **Docs drift.** README structure omits 7 shipped modules; controls table omits 8
   live keys; STATUS pins a stale commit and a stale test count.

### Claims I could NOT reproduce (recorded so nobody re-chases them)
- "AI vehicles ghost through buildings" — 5-minute sim, 40 vehicles, 430 wrap events:
  **zero** vehicle-frames inside a wall. Vehicles are lane-locked and axis-aligned, so
  the missing `is_solid` check in `car.py` is latent, not live.
- "Pedestrian crosswalk deadlock" — longest continuous wait measured 3.5s, which is the
  designed timer. No deadlock.
- "Interior ray treats off-map as solid" (`raycaster.py:425`) — `InteriorView` exposes
  no `.walls` attribute, so `walls_grid` is always `None` indoors and that branch is
  unreachable. Dead code, not a rendering bug.
- Terminal restore — verified clean under pty on uncaught exception, SIGTERM, and
  `sys.exit`. Guardrail #3 holds.

---

## Shift 1 (cont.) — v1.0 Production Plan

Leon asked for a concrete, pickable plan to take Astra 3D to production, with visual
fidelity as the priority and an explicit goal of generalising this into an engine that
can render *any* 3D environment.

### Delivered
- `docs/ROADMAP_PRODUCTION.md` — 5 phases, 10 exit criteria, feature-gap analysis.
- `docs/DESIGN_LOD_FIDELITY.md` — full design for distance-adaptive detail.
- `docs/DESIGN_ENGINE_API.md` — `Scene` protocol and material registry.
- `team/TASKBOARD.md` — 32 tickets, each with branch, owned files, deps, acceptance.
- `STATUS.md` NOW section repointed at the push; BULLETIN announcements posted.

### The fidelity finding that shaped the plan
I measured the actual texel-to-cell ratio rather than reasoning about it. With
`ppm = 57.13` at 160×50, an 11 m facade's break-even — one authored texel per character
cell — lands at **~78 m**. Nearer than that we are magnifying: 2.5 cells/texel at 32 m,
9.8 at 8 m, **39.3 at 2 m**. So the whole playable near field is under-detailed and gets
worse as you approach, which is exactly inverted from what Leon wants. It is a texture
magnification problem, and the fix is a mip pyramid with the level chosen per column,
plus a near-field decal layer for discrete features and quadrant blocks for sub-cell
resolution. Detail must be hashed on world UV, never screen space, or it crawls — that
is the one property that decides whether this feature is worth shipping.

### The engine finding
Better news than expected. `Raycaster` needs exactly **four methods** from the world
(`is_solid`, `get_wall_type`, `get_wall_height`, `get_floor_type`) and `Camera` needs
one. `InteriorView` already substitutes for `CityMap` at that boundary — we have two
scene implementations today and never noticed. The engine is already scene-agnostic; it
simply has no declared contract. That makes Leon's "any 3D environment" goal a
formalisation job, not a rewrite.

### Sequencing decisions I made and why
- **Seam split before perf work, not after.** Once `raycaster.py` is split, the three
  perf tickets live in different files and run in genuinely parallel worktrees. Doing
  perf first would have three agents fighting over one 1,700-line file.
- **Golden-frame harness before the seam split.** A structural move that changes a pixel
  is a silent regression; unit tests will not catch it. T-02 gates T-04 and T-29.
- **Material registry before LOD.** Mip pyramids and decal tables need a home, and the
  registry also kills the `WALL_PERIMETER`/`WALL_WAREHOUSE` collision on the way.
- **Perf recovery before fidelity.** LOD spends frame budget we are already over.

### Open questions raised for Leon
Windows scope, audio hardening vs. experimental label, what to do with Nora's 24
unmerged commits (they overlap Phase 3 territory and are the biggest sequencing risk on
the board), and whether quadrant block glyphs fit the "pure ASCII" identity.

### Next for me
T-04 (raycaster seam split) once T-02 lands. Until then the board is open and I am
reviewing claims.

---

## Shift 2 — Nora salvage, and the ASCII identity question

Leon answered the four open questions and raised a sharper one about what our ASCII
rendering actually *is*.

### Nora's branch: evaluated, salvaged, retired
Delegated to my judgement. I tagged `archive/nora-voss-worktree` before touching
anything, so all 24 commits remain recoverable.

**Adopted — the far-tier layering fix, and it is a real bug on master.** `raycaster.py`
had an unconditional `break` on the first solid far cell, so the 180 m far tier could
only ever return **one** layer per column. That made `max_height` never update and the
`wall_h > max_height` test guarding the append dead code — a taller tower behind a nearer
low mass was simply never seen. The whole point of the far tier is skyline depth, and it
was not working. Measured across a full yaw sweep at spawn: **0 → 268 columns** with
stacked distant silhouettes, max far layers 1 → 2. Perf-neutral (40.2 → 40.7 FPS at
160×50). Locked with `tests/test_far_tier_layering.py`, four cases; I verified the test
fails against unfixed master before trusting it.

**Rejected — the perspective overhaul.** Superseded and actively dangerous to merge. Master
already has a better projection (`pixels_per_meter_at_1m` derives vertical FOV from the ray
plane); Nora's is a cruder `(w/2)/plane_len/CELL_ASPECT`. Decisive detail: her branch uses
the **reciprocal** `CELL_ASPECT` convention (2.0 against master's 0.5), so a merge would
silently invert vertical scale everywhere. Her branch is also 13 commits behind master,
predating Rendering 2.0 and the 180 m tier.

**Rejected as files, adopted as data** — `scale.py` and `vehicle_dims.py` are good
reference tables whose only consumers were her reworks. Landing them now would create a
second source of truth beside `textures.py` and add dead code. Their values are cited from
the archive tag by T-09 (materials) and T-20 (sprite LOD) instead. Her two test files
assert against her projection, but their *intent* — no sunken basements, no hovering
sprites — is a genuine gap and became acceptance criteria on T-19/T-20.

### The finding that matters more
Leon said coloured ASCII should mean coloured *characters* on the terminal background, not
coloured cells, and that cell-fill rendering "is just a pixelated game". He is right, and I
measured why. `--no-fill` already works mechanically — verified 1,236 → 0 background escape
sequences. It looks weak for two specific, fixable reasons:

1. **Glyphs encode no luminance.** The character comes straight from the texture pattern,
   so a lit wall and a shadowed wall both print `#####%######%#%`. Every bit of depth and
   lighting lives in the colour. Strip the fill and the form goes with it.
2. **The sky is colour with no character.** 23% of sky cells are a space glyph carrying
   only a background colour, so with fills off the sky vanishes entirely.

So we have been rendering low-resolution pixel art that happens to use letters. Fixing it
is T-33 (per-material luminance→glyph ramp) and T-34 (sky drawn as glyph density), then
T-35 to make the three modes first-class and art-directed rather than subtractions from a
filled default. Both T-33 and T-34 are unblocked and are, I think, the highest-value
visual work on the board right now — higher than LOD, because they decide what the pixels
*mean* before we go and add more of them.

I also corrected T-18's scope: quadrant blocks are Unicode, not ASCII, so they belong to
`blocks` mode only. In the ASCII modes that near-field resolution has to come from the
glyph ramp and decals instead.

### Terminal vs. web
Leon offered to leave the terminal if it is the ceiling. I declined to answer it as a
binary. The renderer already emits a grid of `(glyph, fg, bg)` cells, which is
backend-agnostic — so the right move is T-36, a `Display` interface, which is cheap and
makes the question **reversible instead of a bet**. Then T-37 is a one-shift timeboxed web
canvas spike that reports measured numbers. The terminal stays the reference backend and
Guardrail #1 is untouched either way. Windows (T-38) rides the same abstraction, which is
why I scheduled it after T-36 rather than as a bespoke `msvcrt` port.

### Next for me
Board is open. My own next pick is still T-04, but if Leon wants the visual payoff first I
would take T-33 and T-34 myself — they are the shortest path to the game looking like what
he described.

---

## Shift — PR #13 CI (T-08 goldens)

**Task**: green `ci` tests on `clover/deterministic-spawns` (PR #13).

### Confirmed from job 98198628634
Not a 3.12-only failure. `python -m unittest discover -s tests` failed on **exactly two**
cases; every T-08 determinism test passed. 3.8 and 3.10 hit the same two failures before
fail-fast cancelled those jobs:

- `driving-day-blocks-160x50` (8000/8000 cells; boarded vehicle POLICE→CYBER_SEDAN)
- `street-life-dusk-blocks-80x32` (163/2560 cells; entity sprites)

Those two frames are locked by T-02 and asserted in CI. Recapturing them was the only
way to green 3.12 without undoing T-08's seed-derived RNG. Other eight goldens untouched.

### Evidence
- Local 3.12: 235 tests OK.
- Merge-with-current-master (what Actions checks out): 248 tests OK.
- Pushed `a04f47b`. Actions `test (3.8)` / `test (3.10)` / `test (3.12)` all success
  on run 33597282867. Benchmark 160×50 landed at 29.6 FPS vs the 30.0 floor — same
  knife-edge as the original T-08 run (30.5 FPS); not caused by the golden recapture.
