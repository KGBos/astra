#!/usr/bin/env python3
"""
Astra 3D: Pure ASCII First-Person 3D City Explorer Engine
Run directly inside any terminal on macOS / Linux.
"""

import argparse
import sys
import os
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.game import Game


def run_benchmark(frames: int = 100, width: int = 100, height: int = 40):
    print(f"⚡ Running Astra 3D Engine Benchmark ({frames} frames @ {width}x{height})...")
    game = Game(width=width, height=height, target_fps=120, demo_mode=True)
    start = time.time()
    for _ in range(frames):
        game._update_simulation(0.033)
        game._render_frame()
        # Render ANSI to string
        _ = game.buffer.render_to_ansi()
    duration = time.time() - start
    avg_fps = frames / duration
    print(f"✅ Benchmark Complete! Rendered {frames} 3D frames in {duration:.3f}s -> Avg: {avg_fps:.1f} FPS")


def main():
    parser = argparse.ArgumentParser(
        description="Astra 3D: Pure ASCII First-Person City Explorer Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Controls:
  [W/A/S/D]        Move forward / Strafe left / Move back / Strafe right
  [Q / E] or [← / →] Turn Left / Turn Right
  [I / K]          Look Up / Look Down (Pitch)
  [Shift + W]      Sprint
  [Space]          Jump
  [M]              Toggle Mini-Map Radar
  [T]              Advance Time of Day
  [R]              Cycle Weather (Clear / Rain / Storm / Fog / Snow / Acid Rain)
  [F]              Toggle Tactical Light Beam (Flashlight)
  [L]              Trigger Lightning Flash Strike
  [H]              Honk Horn
  [Esc] or [X]     Exit
        """
    )
    parser.add_argument("--fps", type=int, default=30, help="Target FPS limit (default: 30)")
    parser.add_argument("--width", type=int, default=80, help="Viewport width in characters (auto-detects if omitted)")
    parser.add_argument("--height", type=int, default=32, help="Viewport height in characters (auto-detects if omitted)")
    parser.add_argument("--no-color", action="store_true", help="Disable TrueColor ANSI output (monochrome mode)")
    parser.add_argument("--demo", action="store_true", help="Launch autonomous city tour mode")
    parser.add_argument("--benchmark", action="store_true", help="Run 3D rendering benchmark and exit")

    args = parser.parse_args()

    if args.benchmark:
        run_benchmark(frames=120, width=args.width, height=args.height)
        sys.exit(0)

    game = Game(
        width=args.width,
        height=args.height,
        target_fps=args.fps,
        use_color=not args.no_color,
        demo_mode=args.demo
    )

    try:
        game.run()
    except KeyboardInterrupt:
        pass
    finally:
        game.terminal.restore_terminal()
        print("\033[0m\nThank you for exploring Astra 3D Metropolis!")


if __name__ == "__main__":
    main()
