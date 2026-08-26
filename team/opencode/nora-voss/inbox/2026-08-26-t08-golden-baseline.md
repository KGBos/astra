# T-08 golden baseline handoff

T-08 is implemented on commit `2e7f4a6` (`clover/deterministic-spawns`). The
focused entity/generator coverage is green, but the full suite reports two
intentional golden changes because traffic, pedestrian, and NPC state is now
derived from `CityMap.seed` instead of the global RNG:

- `driving-day-blocks-160x50`
- `street-life-dusk-blocks-80x32`

The current T-08 worktree does not edit `tests/golden/manifest.json`, since T-02
owns that asset. Please regenerate those two baselines on the T-02 integration
branch, or confirm that T-08 should include the manifest update before PR open.
