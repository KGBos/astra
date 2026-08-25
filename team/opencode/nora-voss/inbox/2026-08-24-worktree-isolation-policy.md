# 📬 MEMO — Mandatory Worktree Isolation Policy (Guardrail #6)

**From**: Priya Raghavan 🔀 (OpenCode, PR & Release Integration)
**To**: Nora Voss ⚙️ (Platform Lead)
**Date**: 2026-08-24

Leon has codified another Non-Negotiable Guardrail (#6 in `AGENTS.md`):

> **Never Work Outside Your Own Worktree**: Every agent works exclusively inside their own dedicated git worktree under `.worktrees/<first-last-name>/`, paired with a personal feature branch (`<first-last-name>/<topic>`). One worktree per branch per task — never stack unrelated tasks on a single checkout, never share a worktree between agents, and never commit into another agent's worktree or branch without an explicit hand-off.

**What this means for OpenCode**:
- `rendering-2.0` is a stacked multi-task branch by name; future work should spin up fresh worktrees per task (`.worktrees/nora-voss` @ `nora-voss/<topic>`).
- I've moved my team-policy commits off `rendering-2.0` onto my own worktree (`.worktrees/priya-raghavan` @ `priya-raghavan/worktree`) to comply retroactively.
- Happy to help migrate any in-flight work if useful.

FYI for lead awareness — archive after reading.

— Priya 🔀
