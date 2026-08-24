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

### NOW — In Flight
| Item | Owner | State | Done When |
| :--- | :--- | :--- | :--- |
| Two-tier far-skyline raycaster (near DDA + coarse parametric far tier, depth-layer stacking) | Nora Voss | WIP in working tree | Review gate passed (Marcus): correctness vs z-buffer/sprite occlusion, perf delta measured, no comment-style violations |
| Standing review gate on master | Marcus Vance | Policy adopted | Every merge to master carries reviewer sign-off in the commit body |

### NEXT — Integration Wave (M3 "Take the Wheel")
Priority order; each lands as its own reviewed change:
1. **Reconcile audio stacks** — `src/audio/soundscape.py` (master, unwired) vs M2 branch `test_sound_system.py`; pick one engine, port the other's best bits, delete the loser. No parallel audio systems ship.
2. **Merge M2 branch** (`obelisk/feat/marcus-vance-m2-engine`, 38 files / +1,033) — rebase onto current master (expect conflicts in game.py, keyboard.py, hud.py, terminal.py — all four moved since it forked). Land interiors/NPC/radio content before driving so the city is populated when you take the wheel.
3. **Wire drivable mode** — mount `vehicle_controller.py` + `cockpit_hud.py` into the Game loop (enter/exit vehicles with E near a car), remove their M3-WIP docstring stamps only when live.
4. **Soundscape activation** — procedural audio wired to weather/thunder/horn/engine events behind a mute-default flag.

### LATER — Backlog (unordered)
- **Performance budget**: lock 60 FPS at 160×50 viewport; profile hot loops (floor casting, sprite projection) if Nora's skyline tier shifts cost
- **Missions & landmarks**: POI-driven objectives on top of existing landmark registry
- **District life simulation**: traffic lights influencing peds (currently cosmetic), crosswalk congestion, rush-hour density curves
- **Save/share seeds**: named seed bookmarks, `/seed` share format
- **Packaging**: single-file zipapp distribution, still zero dependencies

### INFRASTRUCTURE
- [ ] **CI**: GitHub Actions running `python3 -m unittest discover -s tests` + compileall on every push (stdlib-only runner, no installs)
- [ ] **Obelisk sync**: resolve checked-out-master push refusal — set `receive.denyCurrentBranch=updateInstead` or re-point workflows at GitHub exclusively
- [ ] **Release tags**: tag `v0.4` at current master once pushed; tag per milestone hereafter
- [ ] **Branch hygiene**: delete merged `feat/*` branches on both remotes

## 4. Milestone Ledger (updated from legacy STATUS)
| Milestone | Focus | Status |
| :--- | :--- | :--- |
| **M1** | Core raycasting engine, city, traffic, weather, HUD, game loop | ✅ Shipped |
| **M2** | Driving mode, interiors, NPCs, radio | 📦 Built on branch — merge scheduled (NEXT.2) |
| **M3** | Vehicle integration, cockpit HUD, procedural audio | 🔧 Modules staged on master — wire-up scheduled (NEXT.3/4) |
| **M4** | Far-skyline LOD, performance budget, missions layer | 📋 Scoping (NOW feeds M4) |

## 5. Verification Baseline
- Suite: `python3 -m unittest discover -s tests` → 85 tests, all green
- Benchmark: `python3 main.py --benchmark` → ~310 FPS @ 80×32 (target ≥ 60 FPS at large viewports)
- Modes: `--no-fill`, `--no-color` purity asserted by `tests/test_render_modes.py`
