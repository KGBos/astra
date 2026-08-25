# Golden Frames (T-02)

`manifest.json` locks the exact framebuffer of every scenario in
`tools/golden_capture.py`: one sha256 digest per frame plus the zlib-packed
cell data used to print readable diffs when a lock breaks.

## The deal

- **Refactoring** (T-04 seams, T-06 post-FX fusion, ...): digests must come out
  **byte-identical**. If `tests/test_golden_frames.py` goes red, your change
  altered pixels — fix the code, not the goldens.
- **Intentional visual change** (T-33 glyph ramp, T-34 sky glyphs, T-35 mode
  matrix, ...): recapture and commit the new manifest in the same PR:

      python3 tools/golden_capture.py --regenerate

  Mention in the PR which scenarios changed and why; the test failure output
  doubles as the before/after evidence.

## Scenario matrix

10 cells covering day/night x clear/rain/fog x interior / driving /
street-life x `blocks` / `ascii-color` / `ascii-mono` x 80x32 / 160x50.
See `python3 tools/golden_capture.py --list`.

## Determinism notes for reviewers

- City grid: seeded procedural generator (city seed 5).
- Everything stochastic outside the generator (weather particles, traffic,
  pedestrians) is drawn from the module-level RNG, seeded by the harness per
  scenario (`SCENARIO_SEED`) — entity modules do not seed it themselves;
  T-08 addresses that properly.
- Time of day is frozen at construction; all simulation steps use fixed dt.
- Digests are sha256 over a canonical glyph/fg/bg serialization — stable
  across runs and Python versions.
