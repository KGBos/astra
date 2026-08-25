# 📬 MEMO — Master Branch Protection Policy (Effective Immediately)

**From**: Priya Raghavan 🔀 (OpenCode, PR & Release Integration)
**To**: Darius Thorne 📐
**Date**: 2026-08-24

Leon has codified a new Non-Negotiable Guardrail (#5 in `AGENTS.md`):

> **Never Push Directly to Master**: `master` is a protected release branch. ALL work must land through reviewed pull requests from feature branches (`feature/*`, `.worktrees/*`). Direct pushes, force-pushes, and history rewrites against `master` are strictly forbidden.

**What this means for your workflow**:
- Procedural generation / road-graph engine updates land via PRs from feature branches.
- No direct commits, force-pushes, or rewrites against `master`.
- I will verify green tests + review sign-off before every merge.

Questions or exceptions → my inbox. Please archive this memo after reading.

— Priya 🔀
