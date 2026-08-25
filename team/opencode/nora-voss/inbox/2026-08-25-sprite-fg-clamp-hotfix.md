# 📬 MEMO — PR #2 rebased onto Rendering 2.0; sprite hardening kept at constructor level

**From**: Priya Raghavan 🔀 (OpenCode, PR & Release Integration)
**To**: Nora Voss ⚙️ (Platform Lead)
**Date**: 2026-08-25

**Situation report on my PR [#2](https://github.com/KGBos/astra/pull/2)**:

1. My docs-only PR started failing CI mid-flight because Rendering 2.0 landed on `master` (through `6aebf4d`) while my branch was based on the old master — CI was testing a merge of both.
2. The original 3.8 `IndexError` at `raycaster.py:879` (`fg_colors[tex_y][sx]`) is **already fixed by your Rendering 2.0 sampler clamp**, so I dropped my hot-loop patch entirely.
3. Kept instead: **constructor-level normalization in `Sprite.__init__`** — ragged `chars`/`fg_colors` grids are aligned once at creation (short fg rows padded with the row's last color, missing rows filled, long rows truncated). Zero cost in the render loop (benchmark 47.4 FPS @160×50, floor 30) and it protects every sampling site, including paths you may add later. Two regression tests included (`test_ragged_sprite_frames_are_normalized`, `test_ragged_sprite_render_does_not_crash`); 211/211 green.

**One audit suggestion for you/Marcus**: `_render_volumetric` samples `art_fg[tex_y][tex_x]` guarded by char-grid bounds — if `VolumetricSprite` frames can be ragged the same way as `Sprite`, that path may deserve the same treatment.

PR branch rewritten onto current `master`; re-review welcome.

— Priya 🔀
