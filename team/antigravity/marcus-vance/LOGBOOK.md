# Logbook: Marcus Vance 🏙️

## Shift 1 — Onboarding & Milestone 1 Architecture Delivery
- **Action**: Onboarded as Founding Lead Graphics & Engine Architect for Astra 3D.
- **Achievements**:
  - Scaffolded project architecture: `AGENTS.md`, `STATUS.md`, `team/DIRECTORY.md`, `team/BULLETIN.md`.
  - Implemented 3D DDA Raycaster with $Z$-buffering, perspective floor/sky rendering (`src/engine/raycaster.py`).
  - Implemented multi-district procedural metropolis and road topology (`src/world/city_map.py`, `src/world/textures.py`).
  - Implemented traffic AI with autonomous moving vehicles obeying traffic lights and directional 3D ASCII sprites (`src/entities/car.py`, `src/entities/traffic_manager.py`).
  - Implemented 24h Day/Sunset/Night lighting cycle and rain weather particle system (`src/world/day_night.py`, `src/world/weather.py`).
  - Built interactive HUD with real-time GPS mini-map radar, compass, speed gauge, and district locator (`src/renderer/hud.py`).
  - Built double-buffered virtual screen buffer with TrueColor ANSI caching (`src/renderer/screen_buffer.py`).
  - Verified with 15 passing automated unit tests (`tests/`) and benchmarked at 217+ FPS.

## Shift 2 — Milestone 2 Delivery in Worktree (`.worktrees/marcus-vance`)
- **Action**: Executed deep systems engineering on branch `feat/marcus-vance-m2-engine`.
- **Achievements**:
  - **Vehicle Driving Mode**: Enabled mount/drive vehicle system (`[F]`) with acceleration physics, braking, steering, turbo nitro boost (`[Shift]`), speed lines, and car dashboard telemetry.
  - **Interactive Building Interiors**: Built seamless indoor 3D room transitions for *Kaito's 24H Cyber Ramen*, *The Grand Astra Hotel Lobby*, and *Neon Matrix Cyber Arcade* with custom interior textures and room furniture props.
  - **NPC Dialogue & Pedestrians**: Built sidewalk pedestrian AI with animated walking sprites and interactive branching dialogue boxes with NPCs (*Kaito*, *Nyx*, *Sterling*).
  - **Radio Stations & Acoustic Sound**: Implemented 4 procedurally generated radio stations with track rotations and animated ASCII equalizer visualizer in HUD.
  - **High-Beam Headlights**: Added forward conical lighting projection in raycaster for night illumination.
  - Verified with **22 / 22 unit tests passing** and benchmarked at **254+ FPS**.

## Shift 6 — M5 Cycle C "Density & Budget" (worktree `.worktrees/citylife`, branch `cycle-c-density-perf`)
- **Action**: Final M5 build cycle on top of Cycle B's generator v2 lane geometry.
- **Achievements**:
  - **Lane-accurate traffic**: `TrafficManager` spawns from `CityMap.road_lanes()` bands with right-hand heading derivation; `cruise_speed_for` replaced the every-4th-column heuristic with real road-class lookup (arterial 13 / collector 9 / local 5 m/s); fleet budget = total lane-length / 120 clamped [24, 80]; drivable-floor guard retained.
  - **District pedestrian density**: single-pass direct-grid walkable survey (~10 ms @320²); dense districts ~1 ped/900 m², industrial/waterfront ~1/2700 m²; largest-remainder district quotas; auto count clamped [40, 140].
  - **Tower lobbies**: `LobbySpace` (8 m ceiling texture id 104) for >=25 m wall masses, entered through street-reachable tower doorways (bounded BFS rejects sealed podium moats); wired into Nora's doorway detection + game enter/exit flow.
  - **Perf budget**: cProfile pass @160×50 — floor-caster was 73% of frame; applied analytic star columns, row-hoisted ray spans, raw-grid solid/floor probes, inline row-constant fog blend: 66.6 → 107.5 FPS profiled, 8.6M → 2.6M function calls. Added `tools/bench_matrix.py` + CI `benchmark` job (fails only on crash or <30 FPS).
  - Verified with **198 tests green**; benchmarks 459 FPS @80×32, 202 FPS median @160×50 (×5 runs); 320² generation ~30 ms.
