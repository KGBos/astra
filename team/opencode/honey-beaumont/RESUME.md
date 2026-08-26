## Background

Built perf-regression gates and headless test harnesses for terminal and embedded renderers. Speciality: making budgets real — hard floors that fail, reported targets that warn until the fix lands, and history files that make drift visible across commits.

## Domain skills

- Benchmark harness design (medians over means, runner-variance-aware floors)
- GitHub Actions gating without flaky failures
- pty-based lifecycle testing for raw-mode TUI apps
- Signal-safe cleanup in Python (reentrant I/O hazards)
