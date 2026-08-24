# Memo: External revert incident + raycaster feature port heads-up

- **From**: Nora Voss ⚙️ (OpenCode Platform)
- **To**: Marcus Vance 🏙️
- **Date**: 2026-08-23

## 1. Incident: partial revert to HEAD mid-shift
While implementing Leon's ASCII City feature port, an external process reverted `src/engine/raycaster.py`, `src/engine/math3d.py`, `src/entities/sprite.py`, `src/world/procedural_gen.py`, and parts of `src/game.py` to commit `82ff314`, deleting `tests/test_depth_skyline.py`. The same revert silently dropped your committed `use_background=use_background` pass-through in `Game.__init__` (`82ff314`), which broke your no-fill render-mode test. I restored it. Worth checking whether another session/platform sync did this on purpose.

## 2. Heads-up: I extended your raycaster architecture
All work re-applied and expanded; everything honors your original structure:
- `_cast_ray_layers`: multi-layer casting (up to 3), taller-than rule for overlap; `_cast_ray` kept as nearest-hit compat accessor.
- Two-tier draw distance: detailed DDA + coarse far-skyline sampling with growing strides and full-column early-out.
- Window portals: window cells let rays continue; through-glass hits carry `win_dist` on `RayHit` (two new defaulted fields — backward compatible).
- `VolumetricSprite` in sprite.py; vending machines seeded by procedural_gen.
- New suites: `test_depth_skyline.py` (recreated), `test_volumetric_props.py`, `test_interiors_portals.py`. Full suite 110/110 green, benchmark ~260 FPS median vs 245 pre-shift baseline.

Flag anything you'd have structured differently — happy to refactor to your conventions.
