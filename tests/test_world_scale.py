"""
Guards the world-scale registry: entities must derive dimensions from
src/world/scale.py, not from scattered magic numbers.

Author: Nora Voss ⚙️ (OpenCode Platform)
"""

import math
import unittest

from src.engine.camera import Camera
from src.engine.raycaster import Raycaster
from src.entities.car import Vehicle, VehicleType
from src.entities.sprite import VolumetricSprite
from src.world import scale
from src.world.city_map import CityMap
from src.world.day_night import DayNightCycle
from src.renderer.screen_buffer import ScreenBuffer


class TestScaleRegistry(unittest.TestCase):
    def test_vehicle_dims_cover_all_types(self):
        from src.entities.car import VehicleType
        for vt in VehicleType:
            self.assertIn(vt.name, scale.VEHICLE_DIMS)

    def test_facades_cover_texture_registry(self):
        from src.world.textures import TEXTURE_REGISTRY
        for tid in TEXTURE_REGISTRY:
            self.assertIn(tid, scale.FACADE_HEIGHTS_M, f"texture {tid} unmapped")

    def test_towers_are_multistory_landmarks(self):
        self.assertGreaterEqual(scale.FACADE_HEIGHTS_M[2], 20 * 3.0)  # neon >= 20 stories
        self.assertGreaterEqual(scale.FACADE_HEIGHTS_M[7], 30 * 3.0)  # arcology


class TestLifeSizeProjection(unittest.TestCase):
    """A sedan seen head-on at 5 m must project ~1.8 m wide / ~1.45 m tall."""

    def _car_pixels(self):
        rc = Raycaster(screen_w=80, screen_h=40)
        cm = CityMap(width=42, height=42, seed=3)
        cm.walls = [[0] * 42 for _ in range(42)]
        cam = Camera(x=10.15, y=6.5)
        cam.set_direction(math.pi / 2.0)
        v = Vehicle(10.5, 11.5, VehicleType.TAXI, heading_dir=(0, 1))
        dn = DayNightCycle(start_hour=12)
        with_car = ScreenBuffer(80, 40)
        without = ScreenBuffer(80, 40)
        rc.render(camera=cam, city_map=cm, sprites=[v.get_sprite_for_camera(cam.pos.x, cam.pos.y)],
                  day_night=dn, buffer=with_car)
        rc.render(camera=cam, city_map=cm, sprites=[], day_night=dn, buffer=without)
        cells = [(x, y) for y in range(40) for x in range(80)
                 if (with_car.pixels[y][x].char, with_car.pixels[y][x].fg) !=
                    (without.pixels[y][x].char, without.pixels[y][x].fg)]
        return cells

    def test_head_on_width_matches_meters(self):
        cells = self._car_pixels()
        xs = sorted(set(x for x, _ in cells))
        dist = 11.5 - 6.5
        expected_w = scale.VEHICLE_DIMS["TAXI"]["width_m"] * (40 / dist)
        self.assertAlmostEqual(len(xs), expected_w, delta=4,
                               msg=f"head-on width {len(xs)} px vs {expected_w:.1f} expected")

    def test_height_matches_meters(self):
        cells = self._car_pixels()
        ys = sorted(set(y for _, y in cells))
        dist = 11.5 - 6.5
        px_per_unit = 40 / dist
        expected_h = scale.VEHICLE_DIMS["TAXI"]["height_m"] * px_per_unit
        self.assertAlmostEqual(len(ys), expected_h, delta=3,
                               msg=f"height {len(ys)} rows vs {expected_h:.1f} expected")


if __name__ == "__main__":
    unittest.main()
