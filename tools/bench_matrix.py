#!/usr/bin/env python3
"""
Headless render benchmark matrix for Astra 3D (M5 Cycle C perf budget).

Runs the full game loop (raycaster, entities, HUD, ANSI frame builder) in demo
mode at a matrix of viewport sizes and reports median FPS across repeats.
Numbers are informational -- runner hardware varies; the tool exits non-zero
only on crashes or when a size drops below a generous playability floor.

Usage:
    python3 tools/bench_matrix.py                       # CI defaults
    python3 tools/bench_matrix.py --runs 5              # local medians
    python3 tools/bench_matrix.py --sizes 80x32 --frames 120
"""

import argparse
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.game import Game

DEFAULT_SIZES = ("80x32", "120x40", "160x50")
DEFAULT_FRAMES = 300
DEFAULT_RUNS = 1
# Generous floor: runner variance must never fail CI on healthy hardware;
# anything under this signals a real regression or a broken environment.
FPS_FLOOR = 30.0


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


def parse_size(text: str):
    w, _, h = text.lower().partition("x")
    width, height = int(w), int(h)
    if width < 20 or height < 10:
        raise argparse.ArgumentTypeError(f"viewport {text} too small to render")
    return width, height


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Astra 3D benchmark matrix")
    parser.add_argument("--sizes", default=",".join(DEFAULT_SIZES),
                        help="comma-separated WxH viewports")
    parser.add_argument("--frames", type=int, default=DEFAULT_FRAMES,
                        help=f"frames per run (default {DEFAULT_FRAMES})")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS,
                        help=f"repeats per size, median reported (default {DEFAULT_RUNS})")
    parser.add_argument("--floor", type=float, default=FPS_FLOOR,
                        help=f"playability floor in FPS (default {FPS_FLOOR:g})")
    args = parser.parse_args(argv)

    sizes = [parse_size(token) for token in args.sizes.split(",") if token.strip()]

    print(f"astra3d bench matrix: {args.frames} frames x {args.runs} run(s) "
          f"per size, floor {args.floor:g} FPS")
    header = f"{'viewport':>10} | {'median fps':>10} | {'min':>7} | {'max':>7} | status"
    print(header)
    print("-" * len(header))

    failed = False
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
        ok = median >= args.floor
        failed |= not ok
        print(f"{width}x{height:>6} | {median:>10.1f} | {min(samples):>7.1f} | "
              f"{max(samples):>7.1f} | {'OK' if ok else 'BELOW FLOOR'}")

    print("result:", "PASS" if not failed else "FAIL")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
