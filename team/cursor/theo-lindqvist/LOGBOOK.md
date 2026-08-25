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
