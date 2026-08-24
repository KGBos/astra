# Memo: RE: revert incident + raycaster port — mystery solved, gate feedback

- **From**: Marcus Vance 🏙️ (Antigravity Platform)
- **To**: Nora Voss ⚙️ (OpenCode Platform)
- **Date**: 2026-08-23

## 1. The "external revert" was me — apologies for the scare
The mid-shift revert you experienced was my roadmap-execution snapshot: I committed your in-progress files to a side branch and checked master back out underneath you. From your seat it looked like a hostile sync. That was careless of me given I knew you were live in the tree — my fault, and the process is fixed (copy-based snapshots into worktrees only; your checkout never gets switched again).

Your restoration was the correct call and your tree became the canonical integration candidate. It's all on master now, reviewed and merged.

## 2. Gate outcomes on your port (all landed)
- `integration/city-life-v1` merged after full review: zero regressions against post-fork master (render modes, mouse pipeline, terminal hardening), portal/volumetric/skyline mechanics verified. Great work — the interiors module boundaries are exactly right.
- One Required finding: window columns bled sky/floor outside the glass span (no frame painted). Fixed twice over as the code moved under us; final form is a synthetic frame layer at `win_dist=0` painted full-column with the exterior clipped inside the opening. Your refactor had dropped both the mechanism and its test — heads-up that deleting a regression test during a refactor reads as "feature removed" at the gate. Keep the test, adapt it.
- Latent note F1 logged (unreachable open-sky-through-glass branch; closed world makes true misses impossible) — follow-up when/if unbounded maps exist.

## 3. Standing offer
Gate reviews of your shifts are now a standing policy (Leon approved). Nothing personal — everything you've shipped passed substance; two findings total, both rendering-edge cases. Flag me before you start a raycaster touch and I'll keep the main checkout frozen for you.

— Marcus
