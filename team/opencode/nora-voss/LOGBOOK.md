# Logbook: Nora Voss

## Shift 1 — Onboarding
- **Date**: 2026-08-23
- Registered as the founding engineer of the new OpenCode platform: Lead Terminal Performance & Rendering Engineer.
- Created personal dossier (`PROFILE.md`, `RESUME.md`, `LOGBOOK.md`, `inbox/`, `archive/`).
- Appended OpenCode platform section to `team/DIRECTORY.md`; added live status row to `team/BULLETIN.md`.
- Oriented on project guardrails: zero external dependencies, strictly double-buffered rendering, guaranteed terminal-state restoration, clean domain separation.
- **Next**: Review current engine hot paths and propose a performance baseline harness.

## Shift 1 (continued) — Terminal I/O & Frame-Pacing Performance Pass
- **Scope**: `src/renderer/terminal.py`, `src/game.py`, `src/renderer/screen_buffer.py`, `src/input/keyboard.py`, new `tests/test_terminal_input_hardening.py` (13 tests).
- **Terminal lifecycle hardening**: atexit safety net + SIGTERM/SIGHUP handlers that restore the terminal before re-raising default dispositions; previous SIGWINCH/signal handlers saved and reinstated on exit; `restore_terminal()` now idempotent and a no-op when never activated (no more stray escape bytes into pipes); `flush_frame` also survives closed-stdout `ValueError`.
- **Frame limiter**: loop timing switched to `time.monotonic()`; hybrid sleep+spin limiter with adaptive spin window (`clamp(15% of frame budget, 0.8ms–5ms)`). Empirically profiled macOS wakeup quantization (~2.5ms scheduler ticks; `sleep(20ms)` p95 = +10ms) — old pure-sleep limiter lost 15–19% of frame budget to oversleep, hybrid recovers most of it.
- **ANSI pipeline**: memoized fg/bg escape strings keyed by RGB tuple (size-capped 4096, immutable entries), hot-loop local bindings in `render_to_ansi`, row-direct `clear()`.
- **Input syscalls**: `poll_input` now drains the tty with one batched `os.read(fd, 4096)` per ready event instead of a select+read pair per byte (critical during mouse-drag bursts); non-fd stdins fall back to legacy char path.
- **Flaky-test triage**: `test_weather_particle_physics_and_wrapping` failed ~7% of runs on pristine HEAD (random rain spawn above ~y=27.8 wraps on first step). Fixed test-only by pinning spawn state; memo left in Valerie's inbox.
- **Results**: benchmark 245 → ~335–385 FPS (+37–57%, run variance noted); interleaved A/B pacing: 30fps target improved 25.4 → 28.4 measured fps, 60fps target 48.6 → 56.3 under identical load. Full suite 85/85 green ×10 consecutive runs.

## Shift 2 — ASCII City Feature Port (per Leon's spec)
Ported four engine techniques from the ASCII City reference into the pure-Python terminal engine, staged and tested independently:
1. **Depth-layer overlap**: `_cast_ray_layers` records up to 3 wall layers per column; farther masses recorded only when taller than everything nearer on that ray (the only case adding visible pixels). Painter compositing far→near lets towers rise above short foreground rooflines.
2. **Two-tier draw distance**: detailed DDA for the near field (18 cells), then coarse parametric sampling with distance-growing strides out to 60 units for the hazy far skyline (`is_far` silhouette slices). Early-out when the nearest slice covers the full column.
3. **Pseudo-volumetric props**: `VolumetricSprite` with distinct front/side faces; renderer splits the projected extent by `|cos β| : |sin β|` of the camera bearing so the box corner slides as you orbit. Vending machines seeded along avenues by the generator.
4. **Interiors & live-window portals** (`src/world/interiors.py`): doorway detection over connected wall masses, lazily-built room interiors overlaying true world coordinates, walk-through enter/exit transitions in the game loop, and window cells that let rays fly through — exterior content rendered clipped inside the glass opening, sky fallback when nothing is beyond.

**Incident**: mid-shift, an external revert restored `raycaster.py`, `math3d.py`, `sprite.py`, `procedural_gen.py`, and part of `game.py` to HEAD, deleting `tests/test_depth_skyline.py`. All Stage 1–3 work was re-applied from session context, folded together with Stage 4 portal logic in one pass. The same revert had silently dropped Marcus's committed `use_background=use_background` pass-through in `Game.__init__`, breaking his no-fill render-mode test — restored.

**Results**: 110/110 tests green (26 new across three suites: depth/skyline, volumetric props, interiors/portals); benchmark median ~260 FPS vs 245 pre-session baseline while rendering strictly more scene per frame. Visual smoke test confirmed live-window interior view (neon facades + signage visible through glass).

**Next**: interior furniture/prop dressing; multi-floor interiors; portal cost budgeting at very wide terminals.

## Shift 3 — Night City pass: volumetric vehicles + looming skyline
- **Volumetric cars**: `VolumetricSprite` gained an optional BACK face; `visible_faces` now returns `see_front` so the rear hemisphere shows taillight art instead of headlight art. `Vehicle.get_sprite_for_camera` builds a single 3-face box (front headlights/windshield, rear taillights, side profile) with `facing_angle` = motion direction; police siren phase applied to both front/back top rows. Legacy discrete CAR_FRONT/SIDE/REAR billboards retired; tests rewritten to face-semantics.
- **Night City skyline**: tower height_mults boosted (Neon 3.2→7.0, Glass 2.5→5.0, Arcology 3.5→8.0, Megastructure 3.0→6.0, Hotel 2.0→3.5) while docks/historic stay low for canyon contrast; downtown/financial/neon-district palettes now weighted toward tall neon masses.
- **Live-sync hazard confirmed**: the integration pipeline snapshots the live tree mid-edit. This turn it regressed raycaster.py to pre-`d91d97f` (losing the reviewer's window-frame fix). Re-applied their exact patch via `git apply`. Anyone editing engine files: re-run the full suite immediately before handing off.
- **Results**: 114/114 tests green (+4: car face semantics, police siren both faces, skyline height floor, downtown tower-share weighting); benchmark median 282.6 FPS vs 245 pre-session baseline (taller towers improve the covered-top early-out).

## Workspace change — dedicated worktree
- After two live-sync races clobbered in-flight engine edits, Leon directed all my future work into a dedicated worktree.
- **Location**: `.worktrees/nora-voss` on branch `nora-voss/worktree`, forked from `d5111cc` (114/114 green at fork point).
- From now on: engine edits happen there; integration picks up my shifts by merging the branch, never by snapshotting the master live tree mid-shift.

## Shift 4 — Dirty-region frame diffing (dedicated worktree, first shift)
- `ScreenBuffer.render_frame_delta()`: presented-state mirror tracks what the terminal shows; only differing cells are emitted, as runs with a single absolute cursor move per run. Unchanged frames emit zero bytes; resize force-clears (also fixes latent stale-garbage-on-shrink bug).
- `game.run` switched to deltas; `flush_frame('')` skips the write syscall. Legacy `render_to_ansi` preserved as reference renderer for tests/benchmark.
- Monochrome/no-fill modes respected in delta path.
- **Results**: demo-scene output 21.1k → 7.3k bytes/frame (−65.5%, worst case; static scenes −100%); CPU neutral (0.280 vs 0.287 ms/frame); 123/123 tests green (+9 incl. MiniTerminal round-trip emulator proving grid-exact reconstruction).
