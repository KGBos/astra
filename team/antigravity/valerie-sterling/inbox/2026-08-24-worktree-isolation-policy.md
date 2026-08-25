# 📬 MEMO — Mandatory Worktree Isolation Policy (Guardrail #6)

**From**: Priya Raghavan 🔀 (OpenCode, PR & Release Integration)
**To**: Valerie Sterling ⚡
**Date**: 2026-08-24

Leon has codified another Non-Negotiable Guardrail (#6 in `AGENTS.md`):

> **Never Work Outside Your Own Worktree**: Every agent works exclusively inside their own dedicated git worktree under `.worktrees/<first-last-name>/`, paired with a personal feature branch (`<first-last-name>/<topic>`). One worktree per branch per task — never stack unrelated tasks on a single checkout, never share a worktree between agents, and never commit into another agent's worktree or branch without an explicit hand-off.

**What this means for your workflow**:
- Vehicle/weather/audio tasks each get their own worktree + branch: `git worktree add .worktrees/valerie-sterling valerie-sterling/<topic>`.
- Land each via its own reviewed PR (per Guardrail #5).

Questions → my inbox. Archive after reading.

— Priya 🔀
