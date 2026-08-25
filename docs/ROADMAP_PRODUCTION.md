# Astra 3D — Road to Production (v1.0)

> **Author**: Theo Lindqvist 🧭 (Cursor Lead Systems Refactoring Engineer), Shift 1
> **Companion docs**: `DESIGN_LOD_FIDELITY.md`, `DESIGN_ENGINE_API.md`
> **Executable task list**: `team/TASKBOARD.md`

---

## 1. What "production" means here

Astra 3D has shipped five milestones and has real depth: a life-sized 320 m city,
lane-accurate traffic, crowd simulation, interiors, driving, weather, and a
gamma-correct lighting pipeline. It is not short on features. What separates it from a
v1.0 is three things:

1. **It does not hold its own performance budget.** 40 FPS at 160×50 against a
   documented 60 FPS guardrail.
2. **Detail runs backwards.** Surfaces are least resolved exactly where the player
   spends their time — up close. Measured in `DESIGN_LOD_FIDELITY.md` §1.
3. **It is a game, not yet an engine.** The renderer is genuinely scene-agnostic
   already, but nothing declares or enforces that, so no one else can point it at
   their own world.

Everything below serves those three, plus the polish that turns a working build into
something you can hand to a stranger.

## 2. Definition of done for v1.0

| # | Exit criterion | How it is proven |
| :-- | :--- | :--- |
| 1 | 60 FPS at 160×50 with all features on | `tools/bench_matrix.py` gate at 60, enforced in CI |
| 2 | Detail increases monotonically as distance decreases | Distance-monotonicity test (T-14) |
| 3 | No detail crawl during movement | No-crawl test (T-16) |
| 4 | A third party can render their own world | `GridScene` + authoring guide + worked example |
| 5 | Identical seed reproduces an identical world, entities included | Determinism test (T-08) |
| 6 | Terminal always restored, on every exit path | pty test matrix (already passing; keep in CI) |
| 7 | Runs on a bare Python 3.8 with no install step | zipapp artifact built in CI |
| 8 | Degrades on 256-colour, 16-colour, and mono terminals | Render-mode matrix tests |
| 9 | Every published number is re-measured at tag time | Release checklist (T-32) |
| 10 | Zero known P0/P1 defects | Task board clear |

## 3. Phases

Phases are ordered by dependency, not by appeal. The sequencing that matters most:
**perf recovery precedes fidelity work**, because LOD spends frame budget we do not
currently have, and **the material registry precedes LOD**, because mip pyramids and
decal tables need somewhere to live.

### Phase 0 — Truth & guard rails · T-01…T-03
Small, fast, and it unblocks honest measurement of everything after it. Re-baseline the
status documents against measured reality, then build the golden-frame harness that
makes every later refactor safe, then raise the CI perf gate to the actual budget so
drift cannot recur silently. Nothing here changes a pixel.

### Phase 1 — Structure & performance · T-04…T-08
Target 60 FPS at 160×50. The floor caster and the full-frame post-FX pass are the two
largest costs; between them they account for most of the gap. Determinism lands here
too because it is small, self-contained, and needed by the golden-frame harness.

### Phase 2 — Engine core · T-09…T-12
Turn the accidental scene interface into a declared one. Material registry, `Scene`
protocol, a `GridScene` loader that lets anyone bring their own world, and the package
split into `engine/` · `scenes/` · `game/`.

### Phase 3 — Visual fidelity · T-13…T-20
The centrepiece, designed in full in `DESIGN_LOD_FIDELITY.md`: mip pyramid,
per-column level selection, dithered anti-pop, world-anchored detail synthesis,
near-field decals, sub-cell blocks, and parity for floors and sprites.

### Phase 4 — Production polish · T-21…T-29
The gap between "runs" and "shippable": in-game help, settings persistence, seed
bookmarks, objectives, an adaptive-quality governor, colour-depth fallbacks,
accessibility, crash safety, and the two big seam splits.

### Phase 5 — Release engineering · T-30…T-32
zipapp packaging, the engine authoring guide, hygiene, and the v1.0 tag.

## 4. Feature gaps found in review

Beyond the three headline problems, these are missing for a v1.0 and are ticketed in
Phase 4:

**Player-facing.** There is no in-game way to see the controls — they exist only in
`--help` and the README, and the README's table is missing eight live keys. No settings
persist between runs; every launch is CLI flags. Seeds cannot be bookmarked or shared
despite being the main replayability hook. The landmark registry is rich but drives no
objectives, so there is nothing to *do* in the city.

**Robustness.** Colour handling is all-or-nothing — truecolor or `--no-color` — with no
256-colour or 16-colour path, which covers a lot of real terminals. There is no adaptive
quality, so a slow terminal has no graceful path other than a smaller window. There is no
crash log or safe mode, and no explicit handling for a terminal smaller than the minimum
viewport.

**Accessibility.** No colourblind-safe palettes, no high-contrast mode, and no way to
disable the grain, bloom, and lightning flashes.

**Platform.** `termios`/`tty` are POSIX-only, so Windows is unsupported. This is
consistent with the stated macOS/Linux scope and I am **not** proposing it for v1.0 — but
it should be a conscious decision recorded in the README rather than an accident.

**Audio.** The soundscape shells out to external players (`afplay`, `paplay`) via
`subprocess`, re-running `which` on every play, and synthesises the sound bank on the
calling thread when unmuted. It is mute-by-default, which is the right call. For v1.0 it
should either be hardened or labelled experimental — not left ambiguous.

## 5. How the team picks this up

Every ticket in `team/TASKBOARD.md` carries a branch name, a worktree path, an explicit
list of files it owns, its dependencies, and acceptance criteria. Tickets are written so
that **two agents working different tickets in the same phase do not touch the same
file**, which is what makes parallel worktrees safe.

Working agreement, per Guardrails #5 and #6:

1. Claim a ticket by setting your name on its row and updating `team/BULLETIN.md`.
2. `git worktree add -b <you>/<topic> .worktrees/<you> master` — one worktree per branch
   per task, never shared, never stacked.
3. Land through a PR with a green suite and a review sign-off. Leon merges.
4. Do not start a ticket whose dependencies are unmerged; the board marks them BLOCKED.

Ready to start right now, in parallel, with no conflicts between them: **T-01, T-02,
T-03, T-08**.
