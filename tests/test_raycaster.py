"""
Unit tests for 3D raycasting, wall distance, and depth buffering.
"""

import math
import unittest
from src.engine.camera import Camera
from src.engine.raycaster import Raycaster
from src.world.city_map import CityMap
from src.world.day_night import DayNightCycle
from src.renderer.screen_buffer import ScreenBuffer


class TestRaycaster(unittest.TestCase):
    def setUp(self):
        self.city_map = CityMap(width=42, height=42)
        self.camera = Camera(x=12.5, y=6.5)
        self.camera.set_direction(math.pi / 2.0)  # Face South
        self.raycaster = Raycaster(screen_w=80, screen_h=32)
        self.day_night = DayNightCycle(start_hour=12.0)
        self.buffer = ScreenBuffer(80, 32)

    def test_cast_ray_hit(self):
        # Guaranteed facade straight ahead of the center column (open-horizon
        # world edges must never masquerade as hits since Rendering 2.0)
        self.city_map.walls[20][12] = 5
        hit = self.raycaster._cast_ray(40, self.camera, self.city_map)
        self.assertTrue(hit.hit)
        self.assertGreater(hit.perp_wall_dist, 0.0)
        self.assertLess(hit.perp_wall_dist, 50.0)
        self.assertIn(hit.side, (0, 1))

    def test_full_scene_render(self):
        self.raycaster.render(
            camera=self.camera,
            city_map=self.city_map,
            sprites=[],
            day_night=self.day_night,
            buffer=self.buffer
        )
        # Check that Z-buffer was populated for all columns
        self.assertEqual(len(self.raycaster.z_buffer), 80)
        for z in self.raycaster.z_buffer:
            self.assertGreater(z, 0.0)

        # Check that buffer has characters rendered
        non_empty = sum(
            1 for row in self.buffer.pixels for p in row if p.char != ' '
        )
        self.assertGreater(non_empty, 100)


    def test_ragged_sprite_frames_are_normalized(self):
        from src.entities.sprite import Sprite

        # Malformed frame: chars rows wider/taller than their fg color rows.
        spr = Sprite(
            x=0, y=0, name="ragged",
            chars=["@@@@@@@@", "@@"],
            fg_colors=[[(200, 200, 200)] * 2],
        )
        for art_row, fg_row in zip(spr.chars, spr.fg_colors):
            self.assertEqual(len(fg_row), len(art_row))
        # Padded cells inherit the row's last known color.
        self.assertEqual(spr.fg_colors[0][-1], (200, 200, 200))
        self.assertEqual(len(spr.fg_colors), len(spr.chars))

    def test_ragged_sprite_render_does_not_crash(self):
        from src.entities.sprite import Sprite

        spr = Sprite(
            x=0, y=0, name="ragged",
            chars=["@@@@@@@@", "@@"],
            fg_colors=[[(200, 200, 200)] * 2],
        )
        self.raycaster.render(
            camera=self.camera,
            city_map=self.city_map,
            sprites=[spr],
            day_night=self.day_night,
            buffer=self.buffer
        )


if __name__ == "__main__":
    unittest.main()
