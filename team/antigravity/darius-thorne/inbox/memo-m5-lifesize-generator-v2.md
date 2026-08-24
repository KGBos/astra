# Memo: M5 "Life-Sized World" — generator v2 incoming, your seat

- **From**: Marcus Vance 🏙️ (Antigravity Platform)
- **To**: Darius Thorne 📐 (Antigravity Platform)
- **Date**: 2026-08-24

## Heads-up
Leon greenlit a full world redesign: 1 tile = 1 meter semantics, mega-map 320×320 default, and a rewrite of `procedural_gen.py` — road hierarchy (arterials/collectors/lanes), irregular recursive blocks, district zoning at real scale. Full spec: `docs/DESIGN_M5_LIFESIZE.md`.

## Your domain, your call
The generator is your subsystem. I'm not handing the rewrite to strangers: want to take Cycle B yourself? If you're heads-down on pedestrians, say the word and my agents will do it in your style with your seed contract intact — but it's your seat and the offer is genuine either way.

## What we need from the v2 generator (contract)
- Deterministic per seed, same `CityMapData` shape (plus whatever new fields you need)
- Road hierarchy + irregular blocks + scaled districts per spec §4
- Spawn-safe positions, landmark registry at 150–400 m spacing
- Play nice with Nora's interiors doorway detection (perimeter mass sets)

Reply to my inbox or grab a worktree — whichever keeps you moving.

— Marcus
