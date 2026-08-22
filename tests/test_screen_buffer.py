"""
Unit tests for ScreenBuffer, ANSI escape generation, and HUD overlays.
"""

import unittest
from src.renderer.screen_buffer import ScreenBuffer
from src.engine.camera import Camera
from src.world.city_map import CityMap
from src.world.day_night import DayNightCycle
from src.world.weather import WeatherSystem
from src.renderer.hud import HUD


class TestScreenBufferAndHUD(unittest.TestCase):
    def test_screen_buffer_operations(self):
        buf = ScreenBuffer(width=40, height=20, use_color=True)
        self.assertEqual(buf.width, 40)
        self.assertEqual(buf.height, 20)

        buf.set_pixel(5, 5, '@', (255, 0, 0), (0, 0, 255))
        p = buf.pixels[5][5]
        self.assertEqual(p.char, '@')
        self.assertEqual(p.fg, (255, 0, 0))
        self.assertEqual(p.bg, (0, 0, 255))

        buf.draw_string(2, 2, "HELLO", (100, 100, 100))
        for i, ch in enumerate("HELLO"):
            self.assertEqual(buf.pixels[2][2 + i].char, ch)

        ansi_str = buf.render_to_ansi()
        self.assertTrue(len(ansi_str) > 0)
        self.assertIn("\033[H", ansi_str)

    def test_hud_rendering(self):
        buf = ScreenBuffer(width=80, height=30, use_color=True)
        cam = Camera(x=12.5, y=6.5)
        city_map = CityMap(width=42, height=42)
        day_night = DayNightCycle()
        weather = WeatherSystem()
        hud = HUD(show_minimap=True)

        hud.render(cam, city_map, [], day_night, weather, 60.0, buf)
        
        # Verify top header bar rendered
        p_top = buf.pixels[0][2]
        self.assertNotEqual(p_top.char, ' ')
        
        # Verify bottom bar rendered
        p_bot = buf.pixels[29][2]
        self.assertNotEqual(p_bot.char, ' ')


if __name__ == "__main__":
    unittest.main()
