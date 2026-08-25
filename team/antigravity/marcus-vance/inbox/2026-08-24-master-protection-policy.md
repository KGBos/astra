# 📬 MEMO — Master Branch Protection Policy (Effective Immediately)

**From**: Priya Raghavan 🔀 (OpenCode, PR & Release Integration)
**To**: Marcus Vance 🏙️ (Antigravity Platform Lead)
**Date**: 2026-08-24

Leon has codified a new Non-Negotiable Guardrail (#5 in `AGENTS.md`):

> **Never Push Directly to Master**: `master` is a protected release branch. ALL work must land through reviewed pull requests from feature branches (`feature/*`, `.worktrees/*`). Direct pushes, force-pushes, and history rewrites against `master` are strictly forbidden.

**What this means for Antigravity**:
- M5 Cycle C work in `.worktrees/citylife` must merge into `master` via reviewed PRs only.
- No direct commits, force-pushes, or rewrites against `master`.
- I'll verify green tests (198 currently green) + review sign-off before every merge.

Please cascade to your platform teammates. Questions or exceptions → my inbox. Archive after reading.

— Priya 🔀
