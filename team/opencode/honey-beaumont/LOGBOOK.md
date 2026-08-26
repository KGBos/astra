# Logbook

## Shift 1 — 2026-08-26
- Onboarded; claimed T-03 (CI perf gate at the real budget).
- Two-level gating in `tools/bench_matrix.py` (30 FPS hard floor, 60 FPS budget warn-only, `--enforce-budget` for Phase 1+); committed `docs/perf_history.tsv`.
- Added real pty terminal-restore matrix `tests/test_pty_terminal_restore.py`; it caught a live master bug: SIGTERM mid-frame left the terminal unrestored (reentrant stdout write raised RuntimeError inside the fatal handler and was swallowed). Fixed in `src/renderer/terminal.py` via signal-safe `os.write`.
- Full suite: 254 tests green.
