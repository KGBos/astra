#!/usr/bin/env python3
"""
Headless render benchmark matrix for Astra 3D (M5 Cycle C perf budget).

Runs the full game loop (raycaster, entities, HUD, ANSI frame builder) in demo
mode at a matrix of viewport sizes and reports median FPS across repeats.

Two-level gating (T-03):
  * floor  -- hard playability floor (default 30 FPS). Below this the tool
              exits non-zero: a regression or broken environment.
  * budget -- the documented guardrail target (default 60 FPS). Until Phase 1
              recovers headroom the budget runs in WARN-ONLY mode: shortfalls
              are printed on every run but do not fail the build. Pass
              --enforce-budget once Phase 1 lands to make it a hard gate.

Usage:
    python3 tools/bench_matrix.py                       # CI defaults
    python3 tools/bench_matrix.py --runs 5              # local medians
    python3 tools/bench_matrix.py --sizes 80x32 --frames 120
    python3 tools/bench_matrix.py --history docs/perf_history.tsv
"""

import argparse
import datetime
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.game import Game

DEFAULT_SIZES = ("80x32", "120x40", "160x50")
DEFAULT_FRAMES = 300
DEFAULT_RUNS = 1
# Hard floor: runner variance must never fail CI on healthy hardware;
# anything under this signals a real regression or a broken environment.
FPS_FLOOR = 30.0
# Documented budget (AGENTS.md #2): 60 FPS locked target framerate.
# Warn-only until Phase 1 closes; flip to enforced with --enforce-budget.
FPS_BUDGET = 60.0


def bench_size(width: int, height: int, frames: int) -> float:
    """Runs `frames` engine frames at one size, returning achieved FPS.

    Drives simulation + render + ANSI frame build directly (the established
    `main.py --benchmark` harness), so headless runners cannot silently fall
    back to their default terminal size."""
    game = Game(width=width, height=height, target_fps=1_000_000, demo_mode=True)
    start = time.perf_counter()
    for frame in range(frames):
        game._update_simulation(0.033)
        game._render_frame()
        game.buffer.render_to_ansi()  # frame string build stays in the budget
    elapsed = time.perf_counter() - start
    if elapsed <= 0.0:
        raise RuntimeError("benchmark clock returned zero elapsed time")
    return frames / elapsed


def classify(median: float, floor: float, budget: float,
             enforce_budget: bool = False):
    """Returns (status, failed) for one size's median against floor+budget."""
    if median < floor:
        return "BELOW FLOOR", True
    if median < budget:
        status = "below budget (warn-only)" if not enforce_budget \
            else f"BELOW BUDGET (<{budget:g})"
        return status, enforce_budget
    return "OK", False


def parse_size(text: str):
    w, _, h = text.lower().partition("x")
    width, height = int(w), int(h)
    if width < 20 or height < 10:
        raise argparse.ArgumentTypeError(f"viewport {text} too small to render")
    return width, height


def append_history(path: str, results):
    """Appends one TSV row: timestamp, then median FPS per viewport.

    Committed to the repo so FPS trends are visible across commits; rows are
    cheap and hardware-dependent, so compare shapes rather than absolutes."""
    existed = os.path.exists(path)
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc)\
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(path, "a", encoding="utf-8") as fh:
        if not existed:
            fh.write("timestamp_utc\t" +
                     "\t".join(f"{w}x{h}" for w, h, _ in results) + "\n")
        fh.write(stamp + "\t" +
                 "\t".join(f"{median:.1f}" for _, _, median in results) + "\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Astra 3D benchmark matrix")
    parser.add_argument("--sizes", default=",".join(DEFAULT_SIZES),
                        help="comma-separated WxH viewports")
    parser.add_argument("--frames", type=int, default=DEFAULT_FRAMES,
                        help=f"frames per run (default {DEFAULT_FRAMES})")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS,
                        help=f"repeats per size, median reported (default {DEFAULT_RUNS})")
    parser.add_argument("--floor", type=float, default=FPS_FLOOR,
                        help=f"hard playability floor in FPS (default {FPS_FLOOR:g})")
    parser.add_argument("--budget", type=float, default=FPS_BUDGET,
                        help=f"guardrail budget in FPS (default {FPS_BUDGET:g})")
    parser.add_argument("--enforce-budget", action="store_true",
                        help="fail when under the budget (Phase 1+; default warn-only)")
    parser.add_argument("--history", metavar="PATH", default=None,
                        help="append a TSV result row to this file")
    args = parser.parse_args(argv)

    sizes = [parse_size(token) for token in args.sizes.split(",") if token.strip()]

    mode = "ENFORCED" if args.enforce_budget else "warn-only"
    print(f"astra3d bench matrix: {args.frames} frames x {args.runs} run(s) "
          f"per size, floor {args.floor:g} FPS, budget {args.budget:g} ({mode})")
    header = f"{'viewport':>10} | {'median fps':>10} | {'min':>7} | {'max':>7} | status"
    print(header)
    print("-" * len(header))

    failed = False
    results = []  # (width, height, median) for --history
    for width, height in sizes:
        try:
            samples = [bench_size(width, height, args.frames)
                       for _ in range(max(1, args.runs))]
        except Exception as exc:  # crash counts as a failure, never a slow pass
            print(f"{width}x{height:>6} | {'--':>10} | {'--':>7} | {'--':>7} | "
                  f"FAIL ({exc})")
            failed = True
            continue
        median = statistics.median(samples)
        results.append((width, height, median))
        status, size_failed = classify(median, args.floor, args.budget,
                                       args.enforce_budget)
        failed |= size_failed
        print(f"{width}x{height:>6} | {median:>10.1f} | {min(samples):>7.1f} | "
              f"{max(samples):>7.1f} | {status}")
        if median < args.budget:
            print(f"           budget shortfall: {args.budget - median:.1f} FPS "
                  f"under the {args.budget:g} FPS guardrail"
                  f"{'' if args.enforce_budget else ' (reported, not gating yet)'}")

    if args.history and results:
        try:
            append_history(args.history, results)
            print(f"history appended to {args.history}")
        except OSError as exc:
            print(f"warning: could not write history {args.history}: {exc}")

    print("result:", "PASS" if not failed else "FAIL")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
