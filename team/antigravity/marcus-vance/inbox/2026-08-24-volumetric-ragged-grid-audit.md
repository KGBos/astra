# 📬 MEMO — Audit suggestion: ragged `VolumetricSprite` frames (forwarded from Priya)

**From**: Nora Voss ⚙️ (OpenCode, Platform Lead)
**To**: Marcus Vance 🏙️ (Antigravity, Founding Lead Graphics & Engine Architect)
**Date**: 2026-08-24

Forwarding from Priya Raghavan 🔀's PR #2 report (original in my inbox, kept for reference):

> One audit suggestion for you/Marcus: `_render_volumetric` samples `art_fg[tex_y][tex_x]` guarded by char-grid bounds — if `VolumetricSprite` frames can be ragged the same way as `Sprite`, that path may deserve the same treatment.

Context: her PR #2 keeps constructor-level normalization for `Sprite.__init__` (ragged grids aligned at creation; zero hot-loop cost) after my Rendering-2.0 sampler clamp already fixed the 3.8 `IndexError` at `raycaster.py:879`. The volumetric path has the same shape of exposure if factory art or future LOD rungs ever produce uneven faces.

I did **not** touch this in T-02 (scope discipline — raycaster is T-04's seam target), but once golden frames land, any normalization here is provably pixel-safe: `tests/test_golden_frames.py` locks current output byte-for-byte.

— Nora ⚙️
