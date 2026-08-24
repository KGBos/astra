"""
Regression tests for depth-layer overlap (towers rising behind short buildings)
and the two-tier draw distance (detailed near cast + coarse far skyline).

Author: Nora Voss ⚙️ (OpenCode Platform)
"""

import math
import random
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
        self.center_col = 40  # central ray travels straight +Y through x=10.5

    def test_two_structures_yield_two_layers(self):
        """A short mass in front of a taller one records both as ordered layers."""
        self.scene.short_building(9, 11, 12, 13)
        self.scene.tower(8, 12, 20, 24)
        layers = self.rc._cast_ray_layers(self.center_col, self.camera, self.scene.city_map)
        self.assertGreaterEqual(len(layers), 2)
        self.assertEqual(layers[0].wall_type, WAREHOUSE_TYPE)
        self.assertEqual(layers[1].wall_type, TOWER_TYPE)
        for a, b in zip(layers, layers[1:]):
            self.assertLess(a.perp_wall_dist, b.perp_wall_dist)

    def test_equal_height_structure_is_not_stacked(self):
        """A second mass of EQUAL height adds nothing (no visible pixels)."""
        self.scene.short_building(9, 11, 12, 13)
        self.scene.short_building(9, 11, 16, 18)
        layers = self.rc._cast_ray_layers(self.center_col, self.camera, self.scene.city_map)
        self.assertEqual(len([h for h in layers if not h.is_far and h.wall_type == WAREHOUSE_TYPE]), 1)

    def test_tall_layer_rises_above_short_roofline(self):
        """Tower pixels appear ABOVE the short building's roofline after compositing."""
        self.scene.short_building(9, 11, 12, 13)
        self.scene.tower(8, 12, 17, 22)  # near enough that h3.2 out-projects h1.0
        scene_without_tower = _Scene()
        scene_without_tower.short_building(9, 11, 12, 13)

        day_night = DayNightCycle(start_hour=12.0)
        buf_with = ScreenBuffer(80, 32)
        buf_without = ScreenBuffer(80, 32)
        self.rc.render(camera=self.camera, city_map=self.scene.city_map,
                       sprites=[], day_night=day_night, buffer=buf_with)
        self.rc.render(camera=self.camera, city_map=scene_without_tower.city_map,
                       sprites=[], day_night=day_night, buffer=buf_without)

        # Roofline row of the near short building (perp ~ 12 - 8.5)
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
        """_cast_ray still yields the single nearest RayHit for legacy callers."""
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
        """Structure beyond the detailed budget arrives flagged is_far=True."""
        self.scene.tower(9, 11, 34, 38)  # ~26 units out: past NEAR_STEPS=18
        layers = self.rc._cast_ray_layers(self.center_col, self.camera, self.scene.city_map)
        self.assertTrue(layers)
        far_hits = [h for h in layers if h.is_far]
        self.assertEqual(len(far_hits), 1)
        self.assertEqual(far_hits[0].wall_type, TOWER_TYPE)
        self.assertGreater(far_hits[0].perp_wall_dist, self.rc.NEAR_STEPS)
        self.assertEqual(layers[-1], far_hits[0])  # far layer sorts last

    def test_near_hit_suppresses_redundant_far_scan(self):
        """When near layers already fill MAX_LAYERS the far tier never runs."""
        self.scene.short_building(9, 11, 12, 13)
        self.scene.tower(8, 12, 16, 18)              # taller -> layer 2
        self.scene.tower(8, 12, 22, 26, ARCLOGY_TYPE)  # even taller -> layer 3
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
        """Z-buffer semantics stay intact for sprite occlusion."""
        spr = Sprite(10.5, 14.0, "TEST", ["@@@@"],
                     [[[(255, 0, 0)] * 4]], scale_x=0.5, scale_y=0.5)
        self.scene.short_building(9, 11, 12, 13)  # wall closer than sprite
        day_night = DayNightCycle(start_hour=12.0)
        buf = ScreenBuffer(80, 32)
        self.rc.render(camera=self.camera, city_map=self.scene.city_map,
                       sprites=[spr], day_night=day_night, buffer=buf)
        red_seen = any(
            p.char != ' ' and p.fg and p.fg[0] > 200 and p.fg[1] < 80
            for row in buf.pixels for p in [row[self.center_col]]
        )
        self.assertFalse(red_seen, "sprite behind wall was not occluded")


class TestFarTierHazards(unittest.TestCase):
    """Regression coverage for the two-tier hazard audit (near/far parity,
    z-buffer semantics, paint ordering, numeric safety, termination)."""

    def setUp(self):
        self.scene = _Scene()
        self.camera = _camera_at()
        self.rc = Raycaster(screen_w=80, screen_h=32)
        self.center_col = 40

    def test_far_hit_respects_wall_height_semantics(self):
        """Far tier must carry the same height_mult as the near DDA would."""
        self.scene.tower(9, 11, 34, 38)
        layers = self.rc._cast_ray_layers(self.center_col, self.camera, self.scene.city_map)
        far_hits = [h for h in layers if h.is_far]
        self.assertEqual(len(far_hits), 1)
        expected = self.scene.city_map.get_wall_height(TOWER_TYPE)
        self.assertEqual(far_hits[0].wall_height, expected)

    def test_zbuffer_holds_nearest_hit_for_far_columns(self):
        """Columns resolved only by the far tier still expose a usable depth."""
        self.scene.tower(9, 11, 34, 38)
        day_night = DayNightCycle(start_hour=12.0)
        buf = ScreenBuffer(80, 32)
        self.rc.render(camera=self.camera, city_map=self.scene.city_map,
                       sprites=[], day_night=day_night, buffer=buf)
        z = self.rc.z_buffer[self.center_col]
        true_face = 34.0 - self.camera.pos.y
        self.assertGreaterEqual(z, true_face - 0.5)   # never nearer than the face
        self.assertLess(z, true_face + 3.0)           # coarse stride lands inside footprint
        self.assertLess(z, self.rc.FAR_MAX_DIST)

    def test_near_slice_painted_last_beats_far_layer(self):
        """Reversed far-to-near painting: rows owned by the near wall match a
        near-only render exactly, while the taller mid-tower shows above it."""
        self.scene.short_building(9, 11, 12, 13)
        self.scene.tower(8, 12, 17, 22)                # pokes above near roofline
        self.scene.tower(8, 12, 34, 38, ARCLOGY_TYPE)  # far skyline tier
        near_only = _Scene()
        near_only.short_building(9, 11, 12, 13)

        day_night = DayNightCycle(start_hour=12.0)
        buf_full = ScreenBuffer(80, 32)
        buf_near = ScreenBuffer(80, 32)
        self.rc.render(camera=self.camera, city_map=self.scene.city_map,
                       sprites=[], day_night=day_night, buffer=buf_full)
        self.rc.render(camera=self.camera, city_map=near_only.city_map,
                       sprites=[], day_night=day_night, buffer=buf_near)

        # All three layers are stacked on this column, far tier included
        layers = self.rc._cast_ray_layers(self.center_col, self.camera, self.scene.city_map)
        self.assertGreaterEqual(len(layers), 3)
        self.assertTrue(layers[-1].is_far)

        perp_near = 12.0 - self.camera.pos.y
        line_h = int((32 / perp_near) * 1.0)
        horizon = int(32 / 2.0)
        y0 = max(0, int(horizon - line_h / 2.0))
        y1 = min(31, int(horizon + line_h / 2.0))

        for y in range(y0, y1 + 1):
            self.assertEqual(
                buf_full.pixels[y][self.center_col].char,
                buf_near.pixels[y][self.center_col].char,
                f"a farther layer overwrote the near slice at row {y}"
            )
        above = [y for y in range(0, y0)
                 if buf_full.pixels[y][self.center_col].char != buf_near.pixels[y][self.center_col].char]
        self.assertGreater(len(above), 0, "tower pixels missing above near roofline")

    def test_is_far_defaults_false_for_legacy_hits(self):
        hit = RayHit(True, 1, 1, 0, 2.0, 0.5, WAREHOUSE_TYPE, 1.0, 0.0, 1.0)
        self.assertFalse(hit.is_far)

    def test_zero_component_ray_direction_is_safe(self):
        """Center column facing due East yields ray_dir_y == 0 exactly."""
        cam = Camera(x=10.5, y=10.5)
        cam.set_direction(0.0)  # East (+X): plane is vertical, center ray has no Y
        camera_x = 2.0 * self.center_col / float(self.rc.width) - 1.0
        self.assertAlmostEqual(cam.dir.y + cam.plane.y * camera_x, 0.0)

        for sx in range(self.rc.width):
            layers = self.rc._cast_ray_layers(sx, cam, self.scene.city_map)
            for i in range(len(layers) - 1):
                self.assertLess(layers[i].perp_wall_dist, layers[i + 1].perp_wall_dist)

    def test_far_tier_terminates_within_far_max_dist(self):
        """Every far-tier world sample projects inside FAR_MAX_DIST and the
        stride loop cannot run away."""
        self.scene.tower(9, 11, 34, 38)
        cm = self.scene.city_map
        orig_solid = cm.is_solid
        samples = []
        pos = self.camera.pos

        def tracked(x, y):
            if isinstance(x, float) and isinstance(y, float):
                dx = x - pos.x
                dy = y - pos.y
                n = math.hypot(dx, dy)
                if n > 1e-9:
                    samples.append(n)
            return orig_solid(x, y)

        cm.is_solid = tracked
        try:
            for sx in range(0, self.rc.width, 7):
                self.rc._cast_ray_layers(sx, self.camera, cm)
        finally:
            del cm.is_solid

        self.assertTrue(samples)
        self.assertLessEqual(max(samples), self.rc.FAR_MAX_DIST + 1e-6)
        # Growing stride keeps the sample count small (termination proof)
        self.assertLess(len(samples), 60 * len(range(0, self.rc.width, 7)))

    def _legacy_first_hit(self, screen_x, camera, city_map):
        """Reference single-tier DDA (pre-refactor behaviour, 45 steps).

        Returns ((side, perp, wall_type) | None, inside_detailed_tier) where
        inside_detailed_tier marks hits found within NEAR_STEPS crossings —
        the exact span where the refactored near tier must match bit-for-bit.
        """
        camera_x = 2.0 * screen_x / float(self.rc.width) - 1.0
        rdx = camera.dir.x + camera.plane.x * camera_x
        rdy = camera.dir.y + camera.plane.y * camera_x
        map_x, map_y = int(camera.pos.x), int(camera.pos.y)
        ddx = abs(1.0 / rdx) if rdx != 0 else 1e30
        ddy = abs(1.0 / rdy) if rdy != 0 else 1e30
        if rdx < 0:
            step_x, sdx = -1, (camera.pos.x - map_x) * ddx
        else:
            step_x, sdx = 1, (map_x + 1.0 - camera.pos.x) * ddx
        if rdy < 0:
            step_y, sdy = -1, (camera.pos.y - map_y) * ddy
        else:
            step_y, sdy = 1, (map_y + 1.0 - camera.pos.y) * ddy

        for step in range(45):
            if sdx < sdy:
                sdx += ddx
                map_x += step_x
                side, perp = 0, sdx - ddx
            else:
                sdy += ddy
                map_y += step_y
                side, perp = 1, sdy - ddy
            if city_map.is_solid(map_x, map_y):
                return (side, perp, city_map.get_wall_type(map_x, map_y)), \
                    step < self.rc.NEAR_STEPS
        return None, False

    def test_near_field_parity_with_single_tier_dda(self):
        """Within the detailed tier's coverage the nearest layer must equal the
        legacy first-solid DDA exactly, across angles and spawn sites."""
        rng = random.Random(1234)
        open_cells = [
            (cx, cy)
            for cy in range(2, 40) for cx in range(2, 40)
            if not self.scene.city_map.is_solid(cx, cy)
        ]
        checked = 0
        for cx, cy in rng.sample(open_cells, 6):
            for angle in (0.3, 1.05, 2.2, 3.7, 4.8):
                cam = Camera(x=cx + 0.5, y=cy + 0.5)
                cam.set_direction(angle)
                for sx in range(0, self.rc.width, 9):
                    legacy, inside_detailed = self._legacy_first_hit(sx, cam, self.scene.city_map)
                    layers = self.rc._cast_ray_layers(sx, cam, self.scene.city_map)
                    for a, b in zip(layers, layers[1:]):
                        self.assertLess(a.perp_wall_dist, b.perp_wall_dist)
                    if legacy is None or not inside_detailed:
                        # Beyond the detailed budget the coarse tier is
                        # best-effort: it may resolve nothing (stride can hop
                        # thin silhouettes), so only assert whatever it did
                        # resolve arrived flagged as far skyline
                        for h in layers:
                            self.assertTrue(h.is_far,
                                            "near tier missed a wall outside its budget")
                        continue
                    side, perp, wtype = legacy
                    # Hit inside the detailed tier: must match bit-for-bit
                    self.assertTrue(layers)
                    nearest = layers[0]
                    self.assertFalse(nearest.is_far)
                    self.assertEqual(nearest.side, side)
                    self.assertEqual(nearest.wall_type, wtype)
                    self.assertAlmostEqual(nearest.perp_wall_dist, perp, places=9)
                    checked += 1
        self.assertGreater(checked, 100)


class TestGameSmokeMatrix(unittest.TestCase):
    """Full-pipeline smoke: Game at 100x40 renders every weather x day/night
    combination without exceptions and leaves no unpopulated buffer cells."""

    @classmethod
    def setUpClass(cls):
        from src.game import Game
        cls.game = Game(width=100, height=40, demo_mode=True)

    def _render_case(self, weather_value, hour):
        from src.world.weather import WeatherSystem, WeatherType
        wtype = WeatherType(weather_value)
        self.game.weather = WeatherSystem(weather=wtype)
        self.game.day_night.time_of_day = float(hour)
        self.game._update_simulation(0.016)
        self.game._render_frame()

        for y, row in enumerate(self.game.buffer.pixels):
            for x, p in enumerate(row):
                self.assertIsNotNone(
                    p.bg,
                    f"unpopulated cell ({x},{y}) in {weather_value}@{hour}h"
                )

    def test_clear_and_rain_day_night(self):
        self._render_case("CLEAR", 12)
        self._render_case("RAIN", 12)
        self._render_case("CLEAR", 23)
        self._render_case("RAIN", 23)

    def test_storm_and_foggy_day_night(self):
        self._render_case("STORM", 12)
        self._render_case("FOGGY", 12)
        self._render_case("STORM", 23)
        self._render_case("FOGGY", 23)


if __name__ == "__main__":
    unittest.main()
