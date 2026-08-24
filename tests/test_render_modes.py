"""
Regression tests for render output modes: pure-ASCII monochrome and no-background-fill.
"""

import unittest

from src.game import Game
from src.renderer.screen_buffer import ScreenBuffer
from src.world.weather import WeatherType


class TestAsciiMonoMode(unittest.TestCase):
    def test_mono_buffer_transliterates_glyphs(self):
        """Monochrome buffers transliterate known glyphs to pure ASCII equivalents."""
        buf = ScreenBuffer(width=20, height=4, use_color=False)
        buf.set_pixel(0, 0, "★")
        buf.draw_string(2, 1, "◄▼▲")
        all_chars = {p.char for row in buf.pixels for p in row if p.char != " "}
        self.assertTrue(all(c.isascii() for c in all_chars), all_chars)

    def test_color_mode_preserves_unicode(self):
        """Color mode must keep original Unicode glyphs untouched."""
        buf = ScreenBuffer(width=20, height=4, use_color=True)
        buf.set_pixel(0, 0, "★")
        self.assertEqual(buf.pixels[0][0].char, "★")

    def test_full_frame_mono_render_is_ascii_only(self):
        """A complete monochrome frame contains zero non-ASCII characters and zero color codes."""
        g = Game(width=64, height=24)
        g.buffer.use_color = False
        g.weather.set_weather(WeatherType.RAIN, 64, 24)
        for _ in range(3):
            g._update_simulation(0.05)
            g._render_frame()
        frame = g.buffer.render_to_ansi()
        self.assertNotIn("38;2;", frame)
        self.assertNotIn("48;2;", frame)
        non_ascii = [c for c in frame if ord(c) > 127]
        self.assertEqual(non_ascii, [])

    def test_sky_glyphs_stay_ascii_by_contract(self):
        """Sky renderer only emits hardcoded ASCII glyphs; locks N1 contract."""
        import inspect
        from src.engine import raycaster
        src = inspect.getsource(raycaster.Raycaster._render_sky_and_floor)
        for ch in ("'.'", "'*'", "' '"):
            self.assertIn(ch, src)
        for line in src.splitlines():
            stripped = line.strip()
            if "p.char" in stripped:
                self.assertTrue(all(ord(c) < 128 for c in stripped),
                                f"non-ASCII sky glyph introduced: {stripped!r}")


class TestNoFillMode(unittest.TestCase):
    def _frame(self, use_background):
        g = Game(width=64, height=24, use_color=True, use_background=use_background)
        g.weather.set_weather(WeatherType.RAIN, 64, 24)
        for _ in range(3):
            g._update_simulation(0.05)
            g._render_frame()
        return g.buffer.render_to_ansi()

    def test_default_mode_keeps_background_fills(self):
        """Default rendering paints background block fills alongside foreground colors."""
        frame = self._frame(use_background=True)
        self.assertIn("48;2;", frame)
        self.assertIn("38;2;", frame)

    def test_no_fill_mode_keeps_fg_and_drops_bg(self):
        """No-fill mode emits foreground TrueColor codes but zero background codes."""
        frame = self._frame(use_background=False)
        self.assertIn("38;2;", frame)
        self.assertNotIn("48;2;", frame)
        self.assertNotIn("\033[49m", frame)


if __name__ == "__main__":
    unittest.main()
