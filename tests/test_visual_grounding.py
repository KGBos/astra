"""
Regression tests for visual grounding: perspective-correct wall bases (no
underground "basement" rows) and floor-anchored sprites.

Author: Nora Voss ⚙️ (OpenCode Platform)
"""

import math
import unittest

from src.engine.camera import Camera
from src.engine.raycaster import Raycaster
from src.entities.car import Vehicle, VehicleType
from src.world.city_map import CityMap
from src.world.day_night import DayNightCycle
from src.renderer.screen_buffer import ScreenBuffer


def _scene(tower=False):
    cm = CityMap(width=42, height=42, seed=3)
    cm.walls = [[0] * 42 for _ in range(42)]
    if tower:
        for y in range(14, 20):
            for x in range(9, 12):
                cm.walls[y][x] = 2          # neon tower, height_mult 7.0
    return cm


class TestWallGrounding(unittest.TestCase):
    def test_tall_tower_has_no_underground_basement(self):
        """No wall glyphs may appear below the tower's floor-contact row."""
        rc = Raycaster(screen_w=80, screen_h=32)
        cm = _scene(tower=True)
        cam = Camera(x=10.5, y=6.5)
        cam.set_direction(math.pi / 2.0)                    # face the tower
        buf = ScreenBuffer(80, 32)
        rc.render(camera=cam, city_map=cm, sprites=[],
                  day_night=DayNightCycle(start_hour=22), buffer=buf)

        col = 40
        perp = 14.0 - cam.pos.y
        base_row = int(16 + (32 / perp) * cam.eye_height)   # floor contact row
        wall_glyphs = {'|', '#', '-', '=', '\\', '/'}
        below = [buf.pixels[y][col].char for y in range(base_row + 1, 32)]
        leak = [c for c in below if c in wall_glyphs]
        self.assertEqual(leak, [], f"basement rows visible below base: {leak}")

    def test_tower_top_rises_above_eye_line(self):
        """A 7-high tower must extend well above the horizon center."""
        rc = Raycaster(screen_w=80, screen_h=32)
        cm = _scene(tower=True)
        cam = Camera(x=10.5, y=6.5)
        cam.set_direction(math.pi / 2.0)
        buf = ScreenBuffer(80, 32)
        rc.render(camera=cam, city_map=cm, sprites=[],
                  day_night=DayNightCycle(start_hour=12), buffer=buf)
        col_chars = [buf.pixels[y][40].char for y in range(0, 8)]
        self.assertTrue(any(c != ' ' for c in col_chars),
                        "tower top does not rise above mid-screen")


class TestSpriteGrounding(unittest.TestCase):
    def test_car_base_rests_on_floor_plane(self):
        rc = Raycaster(screen_w=80, screen_h=32)
        cm = _scene()
        cam = Camera(x=10.15, y=6.5)
        cam.set_direction(math.pi / 2.0)
        v = Vehicle(10.5, 11.0, VehicleType.TAXI, heading_dir=(0, 1))
        dn = DayNightCycle(start_hour=12)

        with_car = ScreenBuffer(80, 32)
        without_car = ScreenBuffer(80, 32)
        rc.render(camera=cam, city_map=cm, sprites=[v.get_sprite_for_camera(cam.pos.x, cam.pos.y)],
                  day_night=dn, buffer=with_car)
        rc.render(camera=cam, city_map=cm, sprites=[], day_night=dn, buffer=without_car)

        cells = [(x, y) for y in range(32) for x in range(80)
                 if (with_car.pixels[y][x].char, with_car.pixels[y][x].fg) !=
                    (without_car.pixels[y][x].char, without_car.pixels[y][x].fg)]
        self.assertTrue(cells, "car produced no pixels")
        contact_row = int(16 + (32 / 4.5) * cam.eye_height)
        bottom = max(y for _, y in cells)
        self.assertLessEqual(bottom, contact_row,
                             f"car sinks below floor: bottom={bottom} contact={contact_row}")
        self.assertGreaterEqual(bottom, contact_row - 2,
                                f"car hovers above floor: bottom={bottom} contact={contact_row}")

    def test_head_bob_disabled_by_default(self):
        cam = Camera(x=1.0, y=1.0)
        self.assertFalse(cam.head_bob)


if __name__ == "__main__":
    unittest.main()
