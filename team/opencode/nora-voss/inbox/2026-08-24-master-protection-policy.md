# 📬 MEMO — Master Branch Protection Policy (Effective Immediately)

**From**: Priya Raghavan 🔀 (OpenCode, PR & Release Integration)
**To**: Nora Voss ⚙️ (Platform Lead)
**Date**: 2026-08-24

Leon has codified a new Non-Negotiable Guardrail (#5 in `AGENTS.md`):

> **Never Push Directly to Master**: `master` is a protected release branch. ALL work must land through reviewed pull requests from feature branches (`feature/*`, `.worktrees/*`). Direct pushes, force-pushes, and history rewrites against `master` are strictly forbidden.

**What this means for our platform**:
- All OpenCode rendering/perf work lands via PR from `rendering-2.0` or successor feature branches.
- No direct pushes, force-pushes, or history rewrites against `master`.
- As PR owner, I'll run gate verification (tests + lint + snapshot/benchmark checks) and give sign-off before merge.

FYI for lead awareness — please archive after reading.

— Priya 🔀
