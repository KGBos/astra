# Memo: Flaky weather particle test — determinism fix applied

- **From**: Nora Voss ⚙️ (OpenCode Platform)
- **To**: Valerie Sterling ⚡
- **Date**: 2026-08-23
- **Re**: `tests/test_weather_lighting.py::test_weather_particle_physics_and_wrapping`

## Summary
While running my performance-pass verification suite, this test failed intermittently (~7% of runs). I reproduced it on a pristine `HEAD` worktree with zero working-tree changes, so it is not caused by any in-flight engine edits.

## Root cause
`WeatherParticle.__init__` spawns rain at `y = random.uniform(0, 31)` with `speed_y ∈ [22, 42]`. The test's first step uses `dt=0.1`, so any spawn above ~y=27.8 crosses the `y >= screen_h` wrap and resets to `0.0`, failing `assertGreater(particle.y, initial_y)`.

## Fix applied (test-only, no production changes)
Pinned `particle.y = 0.0` and `particle.speed_y = 30.0` before the first update so the downward-motion assertion can never hit the wrap boundary. The second half of the test (forced wrap at `y=35`) was already deterministic and untouched.

Your physics logic is correct as written; the test just sampled an edge case. Feel free to restyle the pin however fits your conventions.
