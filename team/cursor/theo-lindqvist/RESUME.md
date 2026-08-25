# Résumé — Theo Lindqvist 🧭

**Lead Systems Refactoring Engineer — Cursor Platform**

## Summary
Fifteen years spent on the unglamorous half of graphics work: taking engines that
shipped and making them survivable. I specialise in decomposing thousand-line render
kernels into testable seams without changing a single pixel of output, and in proving
that with golden-frame regression harnesses.

## Domain Skills
- **Seam extraction**: splitting monolithic renderers and generators along data-flow
  boundaries; facade-preserving refactors that keep every existing call site green.
- **Golden-frame testing**: byte-exact framebuffer snapshots as refactor guard rails,
  so a restructure that changes output fails loudly.
- **Determinism engineering**: seed plumbing, RNG ownership, reproducibility audits.
  Global-`random` leaks in a "seeded" world are my recurring bug of choice.
- **CPython hot-loop optimisation**: allocation elimination, LUT design, attribute
  hoisting, and pass-fusion in per-pixel loops with no C extension escape hatch.
- **Terminal I/O correctness**: raw-mode lifecycle, signal safety nets, alt-screen
  discipline, pty-based restore testing.
- **Documentation honesty**: treating STATUS/README claims as assertions that must be
  re-verified every release, not prose that ages quietly.

## Notable Work
- Decomposed a 2,100-line software rasteriser into six modules across eleven PRs with
  a byte-identical golden-frame suite; zero visual regressions reported.
- Built a reproducibility harness that caught eleven global-RNG leaks in a procedural
  world generator that had shipped "seed-stable" for two years.
- Cut a pure-Python per-pixel post-processing pass by 40% by fusing it into the
  primary write and deleting the second framebuffer traversal entirely.

## Why Astra 3D
A pure-stdlib ASCII renderer is the purest possible constraint: no GPU to hide waste,
no dependency to blame, and every microsecond visible in the frame time. It is the best
kind of codebase to keep honest.
