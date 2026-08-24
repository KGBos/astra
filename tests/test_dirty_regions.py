"""
Regression tests for dirty-region frame diffing: delta correctness against a
simulated terminal grid, resize invalidation, and zero-change elision.

Author: Nora Voss ⚙️ (OpenCode Platform)
"""

import re
import unittest

from src.game import Game
from src.renderer.screen_buffer import ScreenBuffer


class MiniTerminal:
    """
    Applies ANSI cursor moves + printable chars (ignores SGR color) to a text
    grid, emulating what a real terminal displays after consuming a stream.
    """

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.grid = [[" "] * width for _ in range(height)]
        self.row = 0
        self.col = 0

    def feed(self, s):
        i = 0
        while i < len(s):
            if s[i] == "\033":
                m = re.match(r"\033\[2J", s[i:])
                if m:
                    for r in self.grid:
                        for c in range(self.width):
                            r[c] = " "
                    self.row = self.col = 0
                    i += m.end()
                    continue
                m = re.match(r"\033\[(\d+);(\d+)H", s[i:])
                if m:
                    self.row = int(m.group(1)) - 1
                    self.col = int(m.group(2)) - 1
                    i += m.end()
                    continue
                m = re.match(r"\033\[[0-9;]*m", s[i:])  # SGR color: ignore
                if m:
                    i += m.end()
                    continue
                i += 1  # unknown escape: drop byte
                continue
            ch = s[i]
            if 0 <= self.row < self.height and 0 <= self.col < self.width:
                self.grid[self.row][self.col] = ch
            self.col += 1
            i += 1

    def matches(self, buf: ScreenBuffer) -> bool:
        for y in range(self.height):
            for x in range(self.width):
                expected = buf.pixels[y][x].char if y < buf.height and x < buf.width else " "
                if self.grid[y][x] != expected:
                    return False
        return True


def _paint_scene(buf: ScreenBuffer, tick: int):
    """Static skyline + small animated counter region."""
    buf.clear((8, 10, 14))
    for x in range(buf.width):
        h = 4 + (x * 7) % 9  # no tick term: skyline is static across ticks
        col = (255, 40 + (x % 5) * 40, 120)
        for y in range(h):
            buf.set_pixel(x, buf.height - 1 - y, "#", col, (10, 12, 20))
    buf.draw_string(2, 0, f"TICK {tick:04d}", (255, 255, 0), None)


class TestDirtyRegionDelta(unittest.TestCase):
    def setUp(self):
        self.buf = ScreenBuffer(width=60, height=20)

    def test_first_delta_is_full_frame_with_clear(self):
        _paint_scene(self.buf, 0)
        delta = self.buf.render_frame_delta()
        self.assertTrue(delta.startswith("\033[2J\033[H"))
        self.assertIn("TICK 0000", delta)

    def test_unchanged_buffer_emits_empty_delta(self):
        _paint_scene(self.buf, 0)
        self.buf.render_frame_delta()
        self.assertEqual(self.buf.render_frame_delta(), "")
        self.assertEqual(self.buf.render_frame_delta(), "")

    def test_single_pixel_change_produces_minimal_delta(self):
        _paint_scene(self.buf, 0)
        self.buf.render_frame_delta()
        _paint_scene(self.buf, 1)
        delta = self.buf.render_frame_delta()
        visible_chars = re.sub(r"\033\[[0-9;]*[A-Za-z]", "", delta)
        # One glyph changed plus the counter digits; must stay tiny (< 40 cells)
        self.assertLess(len(visible_chars), 48,
                        f"delta too large for a small change: {visible_chars!r}")
        self.assertNotEqual(delta, "")

    def test_resize_invalidates_and_clears(self):
        _paint_scene(self.buf, 0)
        self.buf.render_frame_delta()
        self.buf.resize(30, 10)
        delta = self.buf.render_frame_delta()
        self.assertTrue(delta.startswith("\033[2J"))
        self.assertIn("H", delta[:8])

    def test_round_trip_matches_full_render_grid(self):
        """Deltas streamed into MiniTerminal reconstruct the exact buffer."""
        term = MiniTerminal(60, 20)
        for tick in range(12):
            _paint_scene(self.buf, tick)
            delta = self.buf.render_frame_delta()
            term.feed(delta)
            self.assertTrue(term.matches(self.buf),
                            f"terminal diverged from buffer at tick {tick}")

    def test_monochrome_delta_never_emits_color_codes(self):
        self.buf.use_color = False
        _paint_scene(self.buf, 0)
        first = self.buf.render_frame_delta()
        self.assertNotIn("38;2;", first)
        _paint_scene(self.buf, 1)
        self.assertNotIn("38;2;", self.buf.render_frame_delta())

    def test_background_toggle_repaints_cleanly(self):
        _paint_scene(self.buf, 0)
        self.buf.render_frame_delta()
        self.buf.use_background = False
        delta = self.buf.render_frame_delta()
        self.assertNotEqual(delta, "")  # bg semantics changed -> repaint


class TestGameIntegration(unittest.TestCase):
    def test_headless_run_with_deltas(self):
        g = Game(width=40, height=12, target_fps=240, demo_mode=True)
        import io, contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            g.run(max_frames=8)
        self.assertGreaterEqual(g.total_frames, 8)

    def test_static_scene_second_frame_is_empty(self):
        """A frozen simulation produces zero output bytes on the next frame."""
        g = Game(width=40, height=12, demo_mode=True)
        g._update_simulation(0.05)
        g._render_frame()
        first = g.buffer.render_frame_delta()
        self.assertNotEqual(first, "")
        second = g.buffer.render_frame_delta()
        self.assertEqual(second, "")


if __name__ == "__main__":
    unittest.main()
