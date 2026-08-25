# Astra 3D Project Status & Roadmap

## 1. Executive Summary
- **Project**: Astra 3D (Pure ASCII 3D First-Person Open-World City Explorer & Rendering Engine)
- **Founder & Project Lead**: Leon
- **Founding Lead Engineer**: Marcus Vance (Antigravity)
- **Current Status**: Post-M1 hardening delivered (Shift 4). Master carries mouse controls, selectable render modes, terminal lifecycle safety nets, and 85 green tests at ~310 FPS. Two major assets are staged but not yet in players' hands: the **M2 feature branch** (+1,033 lines: driving mode, interiors, NPCs, radio) and **Nora's two-tier far-skyline renderer** (in active development).

## 2. Delivered (master @ 82ff314)
- [x] **M1 — Core Engine**: DDA raycaster, camera physics/collision/pitch, procedural multi-district city, traffic AI, pedestrian crowd sim with dialogue, day/night cycle, 6-mode weather with lightning/fog/wetness, HUD + GPS radar, double-buffered TrueColor ANSI renderer
- [x] **Shift 4 quality pass**: 13 review findings fixed, regression suite established (13 tests), flaky pedestrian tests stabilized
- [x] **Input v2**: SGR mouse support (drag-look, click actions, wheel), held-key decay window, split escape-sequence buffering
- [x] **Render modes**: default filled / `--no-fill` (colored glyphs, no background paints) / `--no-color` (pure ASCII transliteration)
- [x] **Terminal lifecycle hardening**: idempotent restore, SIGTERM/SIGHUP safety nets, atexit last resort, batched stdin drain

## 3. Roadmap

### NOW — Production Push (v1.0)
The M1–M5 feature waves are complete; the project is now in a **production hardening
push** toward v1.0. Plan and tickets:
- **`docs/ROADMAP_PRODUCTION.md`** — phases, exit criteria, feature gaps
- **`team/TASKBOARD.md`** — 32 pickable tickets with branches, file scope, acceptance criteria
- **`docs/DESIGN_LOD_FIDELITY.md`** — distance-adaptive detail (the headline visual work)
- **`docs/DESIGN_ENGINE_API.md`** — `Scene` abstraction so any 3D world can be rendered

Three headline problems drive the push:
1. **Perf regressed below guardrail** — 40 FPS @160×50 against the documented 60 FPS
   budget. The §4 M4 row and §5 figures below are **stale and overstated**; T-01 re-measures.
2. **Detail runs backwards** — the break-even for one texel per character cell is ~78 m,
   so the entire near field is magnified (9.8 cells/texel at 8 m, 39 at 2 m).
3. **Engine claim unenforced** — the renderer needs only 4 methods from the world, but
   nothing declares that contract, so no one can bring their own scene.

### PRIOR WAVES — Complete
- [x] **Two-tier far-skyline raycaster** (Nora Voss): landed through double review gate; window portals, volumetric props, interiors system shipped with it (`integration/city-life-v1`)
- [x] **Standing review gate on master**: exercised on every landing this wave (skyline ×2, city-life, M2, repair); findings tracked and closed pre-merge

### NEXT — Integration Wave: COMPLETE
1. [x] **Audio reconciled** — `soundscape.py` is the one engine (WAV synth); M2 bell system deleted, radio ported as `RadioTuner`; mute-default with `[V]` toggle and `--audio` opt-in (NEXT.4 satisfied)
2. [x] **M2 branch merged** — driving mode, NPC dialogue, storefront themes + furniture; conflicts resolved with master-infra-wins doctrine; 129 tests green
3. [x] **Drivable mode live** — `vehicle_controller.py` wired into the Game loop (F enter/exit), cockpit HUD active, headlights drive-gated; M3-WIP stamps removed
4. [x] **Soundscape activated** — horn/chime/rev/thud/radio events behind mute-default flag; labelled **EXPERIMENTAL** for v1.0 (T-39): synthesis runs on a background thread and the system-player probe is cached once

### LATER — Backlog (unordered)
- **Performance budget**: lock 60 FPS at 160×50 viewport (current: ~250 FPS @ 80×32 with full feature set)
- **Open-sky portals**: F1 latent note — windows facing true open sky paint as wall (unreachable in closed world)
- **Vehicle-vs-vehicle collisions** (dead `other_vehicles` param) and seed-aware NPC spawn points
- **Missions & landmarks**: POI-driven objectives on top of existing landmark registry
- **District life simulation**: rush-hour density curves, crosswalk congestion
- **Save/share seeds**: named seed bookmarks, `/seed` share format
- **Packaging**: single-file zipapp distribution, still zero dependencies

### INFRASTRUCTURE
- [x] **CI**: GitHub Actions (`ci.yml`) — compileall + unittest across Python 3.8/3.10/3.12 on push/PR
- [x] **Obelisk sync**: `receive.denyCurrentBranch=updateInstead`; pushes auto-update its worktree
- [x] **Release tags**: `v0.4` (pre-integration) and `v0.5` (city-life + M2 wave)
- [x] **Branch hygiene**: seatless `procedural-city-worldgen` pruned; remaining `feat/*` refs on obelisk intentionally retained — they hold live agent worktrees (Darius/Valerie/M2 seat)

## 4. Milestone Ledger (updated from legacy STATUS)
| Milestone | Focus | Status |
| :--- | :--- | :--- |
| **M1** | Core raycasting engine, city, traffic, weather, HUD, game loop | ✅ Shipped (v0.4) |
| **M2** | Driving mode, interiors, NPCs, radio | ✅ Shipped — merged via gate (`merge/m2-integration`) |
| **M3** | Vehicle integration, cockpit HUD, procedural audio | ✅ Shipped — live in Game loop, mute-default audio (experimental) |
| **M4** | Far-skyline LOD, performance budget | ✅ Shipped — two-tier skyline + 60 FPS @160×50 budget met (medians 196–446 FPS)
| **M5** | Life-Sized World: 1 tile = 1m, generator v2, mega-map 320², lobbies, lane traffic | ✅ Shipped (v0.6) — spec docs/DESIGN_M5_LIFESIZE.md |

## 5. Verification Baseline
- Suite: `python3 -m unittest discover -s tests` → 209 tests, all green
- Benchmarks: `python3 main.py --benchmark` ~300-450 FPS @80×32; dirty-region frame diffing (`render_frame_delta`) reduces ANSI stream size by 65% (21.1KB → 7.3KB/frame) with zero CPU overhead
- Modes: `--no-fill`, `--no-color`, `--audio` documented in CONTROLS.md; purity asserted by tests
- CI: GitHub Actions green across Python 3.8/3.10/3.12

## 6. M5 Post-Mortem Note
Life-sized world executed as three gated cycles (A honest units / B generator v2 / C density+perf) in `.worktrees/citylife`; every merge passed independent review (7 Required findings total across cycles, all closed with regression coverage). Seed-breaking change documented in README/CONTROLS.
