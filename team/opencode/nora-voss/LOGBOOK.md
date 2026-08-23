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
