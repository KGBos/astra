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

### Recommended next
Perf recovery to 60 FPS @160×50 is the one item that is a live guardrail breach; it
should lead. Determinism fix is small and self-contained. Doc re-baselining is a
one-shift chore. Seam extraction on `raycaster.py` (1,701 lines) and
`procedural_gen.py` (1,576 lines) is the structural work I want to own next, but it
should follow the perf fix so we refactor against a known-good frame time.

Awaiting Leon's call on sequencing.
