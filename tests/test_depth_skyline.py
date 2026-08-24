"""
Regression tests for depth-layer overlap (towers rising behind short buildings)
and the two-tier draw distance (detailed near cast + coarse far skyline).

Author: Nora Voss ⚙️ (OpenCode Platform)
"""

import math
import unittest

from src.engine.camera import Camera
from src.engine.raycaster import Raycaster
from src.engine.math3d import RayHit
from src.world.city_map import CityMap
from src.world.day_night import DayNightCycle
from src.entities.sprite import Sprite
from src.renderer.screen_buffer import ScreenBuffer


ARCLOGY_TYPE = 7     # height_mult 3.5
WAREHOUSE_TYPE = 5   # height_mult 1.0
TOWER_TYPE = 2       # height_mult 3.2


def _empty_walls(size):
    return [[0 for _ in range(size)] for _ in range(size)]


class _Scene:
    """Deterministic city: blank grid + hand-placed masses along +Y axis."""

    def __init__(self):
        self.city_map = CityMap(width=42, height=42, seed=3)
        self.city_map.walls = _empty_walls(42)

    def short_building(self, x0, x1, y0, y1):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.city_map.walls[y][x] = WAREHOUSE_TYPE

    def tower(self, x0, x1, y0, y1, wtype=TOWER_TYPE):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.city_map.walls[y][x] = wtype


def _camera_at(x=10.5, y=8.5):
    cam = Camera(x=x, y=y)
    cam.set_direction(math.pi / 2.0)  # face South (+Y)
    return cam


class TestDepthLayerOverlap(unittest.TestCase):
    def setUp(self):
        self.scene = _Scene()
        self.camera = _camera_at()
        self.rc = Raycaster(screen_w=80, screen_h=32)
        self.center_col = 40

    def test_two_structures_yield_two_layers(self):
        self.scene.short_building(9, 11, 12, 13)
        self.scene.tower(8, 12, 20, 24)
        layers = self.rc._cast_ray_layers(self.center_col, self.camera, self.scene.city_map)
        self.assertGreaterEqual(len(layers), 2)
        self.assertEqual(layers[0].wall_type, WAREHOUSE_TYPE)
        self.assertEqual(layers[1].wall_type, TOWER_TYPE)
        for a, b in zip(layers, layers[1:]):
            self.assertLess(a.perp_wall_dist, b.perp_wall_dist)

    def test_equal_height_structure_is_not_stacked(self):
        self.scene.short_building(9, 11, 12, 13)
        self.scene.short_building(9, 11, 16, 18)
        layers = self.rc._cast_ray_layers(self.center_col, self.camera, self.scene.city_map)
        self.assertEqual(len([h for h in layers if not h.is_far and h.wall_type == WAREHOUSE_TYPE]), 1)

    def test_tall_layer_rises_above_short_roofline(self):
        self.scene.short_building(9, 11, 12, 13)
        self.scene.tower(8, 12, 17, 22)
        scene_without_tower = _Scene()
        scene_without_tower.short_building(9, 11, 12, 13)

        day_night = DayNightCycle(start_hour=12.0)
        buf_with = ScreenBuffer(80, 32)
        buf_without = ScreenBuffer(80, 32)
        self.rc.render(camera=self.camera, city_map=self.scene.city_map,
                       sprites=[], day_night=day_night, buffer=buf_with)
        self.rc.render(camera=self.camera, city_map=scene_without_tower.city_map,
                       sprites=[], day_night=day_night, buffer=buf_without)

        perp_near = 12.0 - self.camera.pos.y
        line_h = int((32 / perp_near) * 1.0)
        horizon = int(32 / 2.0)
        roof_row = int(horizon - line_h / 2.0)

        differing_above_roof = [
            y for y in range(0, max(0, roof_row))
            if buf_with.pixels[y][self.center_col].char != buf_without.pixels[y][self.center_col].char
        ]
        self.assertGreater(len(differing_above_roof), 0,
                           "no tower pixels above the short roofline")

    def test_zbuffer_tracks_nearest_layer(self):
        self.scene.short_building(9, 11, 12, 13)
        self.scene.tower(8, 12, 20, 24)
        day_night = DayNightCycle(start_hour=12.0)
        buf = ScreenBuffer(80, 32)
        self.rc.render(camera=self.camera, city_map=self.scene.city_map,
                       sprites=[], day_night=day_night, buffer=buf)
        expected = 12.0 - self.camera.pos.y
        self.assertAlmostEqual(self.rc.z_buffer[self.center_col], expected, delta=0.01)

    def test_cast_ray_compat_returns_nearest(self):
        self.scene.short_building(9, 11, 12, 13)
        self.scene.tower(8, 12, 20, 24)
        hit = self.rc._cast_ray(self.center_col, self.camera, self.scene.city_map)
        self.assertIsInstance(hit, RayHit)
        self.assertTrue(hit.hit)
        self.assertEqual(hit.wall_type, WAREHOUSE_TYPE)


class TestTwoTierDrawDistance(unittest.TestCase):
    def setUp(self):
        self.scene = _Scene()
        self.camera = _camera_at()
        self.rc = Raycaster(screen_w=80, screen_h=32)
        self.center_col = 40

    def test_far_cluster_resolved_by_coarse_tier(self):
        self.scene.tower(9, 11, 34, 38)
        layers = self.rc._cast_ray_layers(self.center_col, self.camera, self.scene.city_map)
        self.assertTrue(layers)
        far_hits = [h for h in layers if h.is_far]
        self.assertEqual(len(far_hits), 1)
        self.assertEqual(far_hits[0].wall_type, TOWER_TYPE)
        self.assertGreater(far_hits[0].perp_wall_dist, self.rc.NEAR_STEPS)
        self.assertEqual(layers[-1], far_hits[0])

    def test_near_hit_suppresses_redundant_far_scan(self):
        self.scene.short_building(9, 11, 12, 13)
        self.scene.tower(8, 12, 16, 18)
        self.scene.tower(8, 12, 22, 26, ARCLOGY_TYPE)
        layers = self.rc._cast_ray_layers(self.center_col, self.camera, self.scene.city_map)
        self.assertEqual(len(layers), self.rc.MAX_LAYERS)
        self.assertFalse(any(h.is_far for h in layers))

    def test_far_slice_draws_blocky_ascii_silhouette(self):
        self.scene.tower(9, 11, 34, 38)
        day_night = DayNightCycle(start_hour=12.0)
        buf = ScreenBuffer(80, 32)
        self.rc.render(camera=self.camera, city_map=self.scene.city_map,
                       sprites=[], day_night=day_night, buffer=buf)
        col_chars = {buf.pixels[y][self.center_col].char for y in range(32)}
        silhouette = col_chars & {'#', '%'}
        self.assertTrue(silhouette, f"no far-silhouette glyphs found: {col_chars}")

    def test_sprites_occluded_by_nearest_wall_still_work(self):
        spr = Sprite(10.5, 14.0, "TEST", ["@@@@"],
                     [[[(255, 0, 0)] * 4]], scale_x=0.5, scale_y=0.5)
        self.scene.short_building(9, 11, 12, 13)
        day_night = DayNightCycle(start_hour=12.0)
        buf = ScreenBuffer(80, 32)
        self.rc.render(camera=self.camera, city_map=self.scene.city_map,
                       sprites=[spr], day_night=day_night, buffer=buf)
        red_seen = any(
            p.char != ' ' and p.fg and p.fg[0] > 200 and p.fg[1] < 80
            for row in buf.pixels for p in [row[self.center_col]]
        )
        self.assertFalse(red_seen, "sprite behind wall was not occluded")


class TestNightCitySkyline(unittest.TestCase):
    """Night City profile: towers loom, downtown favors neon masses."""

    def test_tower_heights_loom_over_low_districts(self):
        from src.world.textures import get_texture
        self.assertGreaterEqual(get_texture(TOWER_TYPE).height_mult, 6.5)      # neon tower
        self.assertGreaterEqual(get_texture(ARCLOGY_TYPE).height_mult, 7.5)    # arcology
        self.assertLess(get_texture(WAREHOUSE_TYPE).height_mult, 1.5)          # low docks

    def test_downtown_blocks_favor_tall_types(self):
        """Across seeds, downtown blocks are mostly tower-class wall types."""
        tall_types = {1, 2, 7, 8}
        tall_hits = 0
        total = 0
        for seed in range(6):
            cm = CityMap(width=42, height=42, seed=seed)
            for y in range(cm.height):
                for x in range(cm.width):
                    t = cm.walls[y][x]
                    if cm.get_district_at(x, y) == "CYBER-DOWNTOWN" and t > 0:
                        total += 1
                        if t in tall_types:
                            tall_hits += 1
        self.assertGreater(total, 0)
        self.assertGreater(tall_hits / total, 0.7,
                           f"downtown tower share too low: {tall_hits}/{total}")


if __name__ == "__main__":
    unittest.main()
