"""
Cycle A "Honest Units" verification: true-metre projection math, human-scale
camera kinematics, pedestrian sprite sizing, 320x320 spawn safety/timing, and
determinism at the mega-map default.

Every expected pixel value is derived from pixels_per_meter_at_1m() and
Camera constants — nothing is eyeballed.
"""

import math
import time
import unittest

from src.engine.camera import Camera
from src.engine.raycaster import Raycaster, pixels_per_meter_at_1m
from src.world.city_map import CityMap
from src.world.day_night import DayNightCycle
from src.world.procedural_gen import ProceduralCityGenerator
from src.world.textures import get_texture
from src.entities.pedestrian import Pedestrian, PedestrianArchetype, PedestrianState
from src.entities.car import (
    Vehicle,
    VehicleType,
    ARTERIAL_CRUISE,
    COLLECTOR_CRUISE,
    ALLEY_CRUISE,
    CRUISE_BY_CLASS,
    cruise_speed_for,
)
from src.entities.vehicle_controller import VehicleController
from src.renderer.cockpit_hud import CockpitHUD
from src.renderer.screen_buffer import ScreenBuffer


SCREEN_W, SCREEN_H = 80, 32


def _ppm(cam=None):
    plane_len = cam.plane.length() if cam else math.tan(math.radians(66.0) / 2.0)
    return pixels_per_meter_at_1m(SCREEN_W, SCREEN_H, plane_len)


class _OpenWorld:
    """Duck-typed map with no obstacles, for displacement measurement."""

    def is_solid(self, x: float, y: float) -> bool:
        return False


def _wall_rows(wall_type: int, y0: int, y1: int, cam):
    """Rows of the center column repainted by a facade vs an empty world.

    The probe raycaster's far tier is capped inside the 42-cell test grid so
    the world-edge void cannot masquerade as a phantom skyline layer.
    """
    rc = Raycaster(screen_w=SCREEN_W, screen_h=SCREEN_H)
    rc.FAR_MAX_DIST = 20.0
    day_night = DayNightCycle(start_hour=12.0)

    def render(walls_value_fn):
        cm = CityMap(width=42, height=42, seed=3)
        cm.walls = [[0 for _ in range(42)] for _ in range(42)]
        for y in range(y0, y1 + 1):
            for x in (9, 10, 11):
                cm.walls[y][x] = walls_value_fn
        buf = ScreenBuffer(SCREEN_W, SCREEN_H)
        rc.render(camera=cam, city_map=cm, sprites=[],
                  day_night=day_night, buffer=buf)
        return [(p.char, p.fg) for p in (buf.pixels[y][40] for y in range(SCREEN_H))]

    baseline = render(0)
    with_wall = render(wall_type)
    return [y for y in range(SCREEN_H) if baseline[y] != with_wall[y]]


class TestProjectionMath(unittest.TestCase):
    def test_pixels_per_meter_formula_matches_fov_derivation(self):
        """PPM_1M = (H/2)/tan(fav_v/2), fov_v derived from the horizontal plane."""
        fov_h = math.radians(66.0)
        plane_len = math.tan(fov_h / 2.0)
        tan_half_v = plane_len * SCREEN_H / (0.5 * SCREEN_W)
        expected = (SCREEN_H / 2.0) / tan_half_v
        self.assertAlmostEqual(pixels_per_meter_at_1m(SCREEN_W, SCREEN_H, plane_len), expected)
        self.assertAlmostEqual(expected, SCREEN_W / (4.0 * plane_len))

    def test_facade_height_projects_per_projection_math(self):
        """A low facade's painted extent equals ppm * height_m / dist rows."""
        cam = Camera(x=10.5, y=8.5)
        cam.set_direction(math.pi / 2.0)
        doorway_h = get_texture(13).height_mult          # 2.5 m threshold
        dist = 12.0 - 8.5

        rows = _wall_rows(13, 12, 13, cam)
        exp_top = int(16 - _ppm(cam) * (doorway_h - cam.eye_m) / dist)
        exp_bot = int(16 + _ppm(cam) * cam.eye_m / dist)
        self.assertEqual(min(rows), exp_top)
        self.assertLessEqual(abs(max(rows) - exp_bot), 1)
        self.assertLessEqual(abs(len(rows) - _ppm(cam) * doorway_h / dist), 2)

    def test_tower_slices_exceed_screen_top_when_close(self):
        """A 40 m tower 5.5 m away must overflow the top of the frame."""
        cam = Camera(x=10.5, y=8.5)
        cam.set_direction(math.pi / 2.0)

        rows = _wall_rows(1, 14, 15, cam)                # glass tower, 40 m
        exp_bot = int(16 + _ppm(cam) * cam.eye_m / (14.0 - 8.5))
        self.assertEqual(min(rows), 0, "tower roofline did not clip screen top")
        self.assertLessEqual(abs(max(rows) - exp_bot), 1)

    def test_eye_raise_shifts_ground_line_by_projection(self):
        """Raising the eye by 0.5 m pushes the ground line down ppm*0.5/dist."""
        cam = Camera(x=10.5, y=8.5)
        cam.set_direction(math.pi / 2.0)
        dist = 16.0 - 8.5

        standing = _wall_rows(13, 16, 17, cam)
        cam.eye_m += 0.5
        elevated = _wall_rows(13, 16, 17, cam)

        self.assertAlmostEqual(max(elevated) - max(standing),
                               _ppm(cam) * 0.5 / dist, delta=1)
        self.assertEqual(min(standing), min(elevated) - int(_ppm(cam) * 0.5 / dist))


class TestSpriteScales(unittest.TestCase):
    def test_pedestrian_sprite_is_175_cm(self):
        """All standing orientations project to ~1.75 m: scale_y * art rows."""
        ped = Pedestrian(10.0, 10.0, archetype=PedestrianArchetype.CASUAL_CITIZEN)
        ped.state = PedestrianState.WALKING
        seen = set()
        for angle in (0.0, math.pi / 2.0, math.pi):
            spr = ped.get_sprite_for_camera(10.0 + math.cos(angle) * 5.0,
                                            10.0 + math.sin(angle) * 5.0)
            seen.add(spr.height)
            self.assertAlmostEqual(spr.scale_y * spr.height, 1.75, delta=0.01,
                                   msg=f"{spr.name} is {spr.scale_y * spr.height:.3f} m")
        self.assertEqual(seen, {3})

    def test_pedestrian_rendered_height_follows_projection(self):
        spr_h_expected = _ppm() * 1.75 / 5.0              # viewed from 5 m
        self.assertAlmostEqual(spr_h_expected, 10.8, delta=0.1)
        self.assertGreater(spr_h_expected, 8.0)

    def test_prop_scales_match_real_sizes(self):
        from src.entities.sprite import (
            make_streetlamp_sprite, make_tree_sprite, make_fire_hydrant_sprite,
            make_bollard_sprite, make_vending_machine_sprite,
        )
        lamp = make_streetlamp_sprite(0, 0)
        tree = make_tree_sprite(0, 0)
        hydrant = make_fire_hydrant_sprite(0, 0)
        bollard = make_bollard_sprite(0, 0)
        vending = make_vending_machine_sprite(0, 0)
        self.assertAlmostEqual(lamp.scale_y * lamp.height, 6.0)       # lamps 6 m
        self.assertTrue(8.0 <= tree.scale_y * tree.height <= 10.0)    # trees 8-10 m
        self.assertAlmostEqual(hydrant.scale_y * hydrant.height, 0.75, delta=0.01)
        self.assertAlmostEqual(bollard.scale_y * bollard.height, 1.0, delta=0.02)
        self.assertAlmostEqual(vending.scale_y * vending.height, 1.8, delta=0.01)

    def test_vehicle_side_face_spans_real_length_when_rendered(self):
        """Vehicle box stays 1.5 m tall; side-face world span derives from scale_x."""
        vehicle = Vehicle(12.5, 12.5, VehicleType.TAXI, (0, 1))
        spr = vehicle.get_sprite_for_camera(20.0, 12.5)
        self.assertAlmostEqual(spr.scale_y * max(len(spr.front_chars), len(spr.side_chars)),
                               1.5, delta=0.01)
        self.assertAlmostEqual(spr.scale_x * len(spr.side_chars[0]) / len(spr.front_chars[0]),
                               2.86, delta=0.1)

    def test_rendered_square_sprite_has_2_to_1_cell_aspect(self):
        """A 1 m x 1 m sprite at 5 m renders ~23 cols x ~11 rows on 160x50 (2:1 cells)."""
        from types import SimpleNamespace
        from src.entities.sprite import Sprite
        w, h = 160, 50
        cam = Camera(x=0.0, y=0.0, fov_deg=70.0)
        stub_map = SimpleNamespace(
            is_solid=lambda x, y: False,
            get_wall_type=lambda x, y: 0,
            get_wall_height=lambda wt: 1.0,
            get_floor_type=lambda x, y: 4,
            traffic_lights={},
        )
        art_rows, art_cols = 4, 4
        spr = Sprite(5.0, 0.0, "PROBE",
                     ["####"] * art_rows,
                     [[(255, 255, 255)] * art_cols for _ in range(art_rows)],
                     scale_x=1.0 / art_cols, scale_y=1.0 / art_rows)
        buf = ScreenBuffer(w, h)
        raycaster = Raycaster(w, h)
        dn = DayNightCycle(start_hour=12.0)
        raycaster.render(camera=cam, city_map=stub_map, sprites=[spr], day_night=dn, buffer=buf)
        rows = sum(1 for y in range(h) if buf.pixels[y][w // 2].char == '#')
        cols = max(sum(1 for x in range(w) if buf.pixels[y][x].char == '#')
                   for y in range(h))
        ppm = pixels_per_meter_at_1m(w, h, cam.plane.length())
        self.assertAlmostEqual(cols, ppm / 0.5 / 5.0, delta=3)
        self.assertAlmostEqual(rows, ppm / 5.0, delta=2)
        self.assertGreater(cols, rows * 1.7)
        self.assertLess(cols, rows * 2.3)


class TestHumanKinematics(unittest.TestCase):
    def test_walk_speed_is_36_m_per_second(self):
        cam = Camera()
        start = (cam.pos.x, cam.pos.y)
        steps = 100
        for _ in range(steps):
            cam.move_forward(1.0 / steps, False, _OpenWorld())
        walked = math.hypot(cam.pos.x - start[0], cam.pos.y - start[1])
        self.assertAlmostEqual(walked, 3.6, delta=0.05)

    def test_sprint_doubles_to_72(self):
        cam = Camera()
        start = (cam.pos.x, cam.pos.y)
        steps = 100
        for _ in range(steps):
            cam.move_forward(1.0 / steps, True, _OpenWorld())
        walked = math.hypot(cam.pos.x - start[0], cam.pos.y - start[1])
        self.assertAlmostEqual(walked, 7.2, delta=0.1)

    def test_strafe_is_eight_tenths_of_walk(self):
        cam = Camera()
        start = (cam.pos.x, cam.pos.y)
        steps = 100
        for _ in range(steps):
            cam.strafe_right(1.0 / steps, _OpenWorld())
        moved = math.hypot(cam.pos.x - start[0], cam.pos.y - start[1])
        self.assertAlmostEqual(moved, 3.6 * 0.8, delta=0.05)

    def test_jump_clears_about_one_meter(self):
        cam = Camera()
        cam.jump()
        self.assertTrue(cam.is_jumping)
        apex = cam.EYE_HEIGHT_M
        guard = 0
        while cam.is_jumping and guard < 10000:
            cam.update_physics(1.0 / 240.0)
            apex = max(apex, cam.eye_m)
            guard += 1
        clearance = apex - cam.EYE_HEIGHT_M
        self.assertGreater(clearance, 0.9)
        self.assertLess(clearance, 1.1)
        self.assertFalse(cam.is_jumping)

    def test_human_scale_constants(self):
        self.assertAlmostEqual(Camera.EYE_HEIGHT_M, 1.7)
        self.assertAlmostEqual(Camera.SEATED_EYE_M, 1.0)
        self.assertAlmostEqual(Camera.COLLISION_RADIUS, 0.35)
        self.assertAlmostEqual(Camera.WALK_SPEED, 3.6)
        self.assertAlmostEqual(Camera.SPRINT_MULT, 2.0)
        self.assertAlmostEqual(Camera.JUMP_VELOCITY, 4.4, delta=0.05)
        self.assertAlmostEqual(math.sqrt(2 * Camera.GRAVITY * 1.0), Camera.JUMP_VELOCITY, delta=0.05)


class TestMegaMapSpawnSafety(unittest.TestCase):
    def test_spawn_safe_on_320_default(self):
        city = CityMap(width=320, height=320, seed=7)
        sx, sy = city.spawn_pos
        self.assertTrue(1 <= sx < city.width - 1)
        self.assertTrue(1 <= sy < city.height - 1)
        self.assertFalse(city.is_solid(sx, sy))
        self.assertFalse(city.is_water(sx, sy))
        self.assertEqual((city.width, city.height), (320, 320))

    def test_spawn_scan_capped_and_falls_back_to_avenue(self):
        gen = ProceduralCityGenerator()
        size = 320
        mid = size // 2
        floors = [[0 for _ in range(size)] for _ in range(size)]

        walls = [[0 for _ in range(size)] for _ in range(size)]
        for y in range(mid - 26, mid + 27):               # sealed downtown core
            for x in range(mid - 26, mid + 27):
                walls[y][x] = 5
        start = time.perf_counter()
        pos = gen._find_safe_spawn_pos(size, size, floors, walls, [4, 12, 20])
        elapsed = time.perf_counter() - start
        self.assertEqual(pos, (4.5, float(mid) + 0.5))    # avenue-column fallback
        self.assertLess(elapsed, 0.5)

    def test_spawn_scan_fast_even_when_fully_blocked(self):
        gen = ProceduralCityGenerator()
        size = 320
        walls = [[5 for _ in range(size)] for _ in range(size)]
        floors = [[0 for _ in range(size)] for _ in range(size)]
        start = time.perf_counter()
        pos = gen._find_safe_spawn_pos(size, size, floors, walls, [4, 12, 20])
        elapsed = time.perf_counter() - start
        self.assertEqual(pos, (4.5, 4.5))                 # last-resort corner
        self.assertLess(elapsed, 0.5)

    def test_pedestrian_walkable_scan_under_half_second(self):
        city = CityMap(width=320, height=320, seed=11)
        start = time.perf_counter()
        walkable = []
        for y in range(2, city.height - 2):
            for x in range(2, city.width - 2):
                ftype = city.get_floor_type(x, y)
                if not city.is_solid(x, y) and not city.is_water(x, y):
                    if ftype in (4, 6, 5, 9, 10):
                        walkable.append((x, y))
        elapsed = time.perf_counter() - start
        self.assertGreater(len(walkable), 1000)
        self.assertLess(elapsed, 0.5)


class TestDeterminismAt320(unittest.TestCase):
    def test_same_seed_same_city_at_320(self):
        a = ProceduralCityGenerator().generate(seed=424242, width=320, height=320)
        b = ProceduralCityGenerator().generate(seed=424242, width=320, height=320)
        self.assertEqual(a.walls, b.walls)
        self.assertEqual(a.floors, b.floors)
        self.assertEqual(a.districts, b.districts)
        self.assertEqual(a.spawn_pos, b.spawn_pos)
        self.assertEqual([lm.name for lm in a.landmarks], [lm.name for lm in b.landmarks])


class TestTrafficSpeeds(unittest.TestCase):
    def test_cruise_classes_from_grid_hierarchy(self):
        """Cruise classes come from the measured road hierarchy: every segment
        line's cruise speed equals its class constant (arterial 13, collector
        9, local alley 5 m/s), in both travel directions."""
        cm = CityMap(width=160, height=160, seed=0)
        segments = cm.road_segments
        self.assertTrue(segments, "generator v2 exposed no road segments")
        seen_classes = set()
        for seg in segments:
            expected = CRUISE_BY_CLASS[seg.road_class]
            seen_classes.add(seg.road_class)
            if seg.axis == "NS":
                x, y = seg.center + 0.5, 80.5
                south, north = (0, 1), (0, -1)
            else:
                x, y = 80.5, seg.center + 0.5
                south, north = (1, 0), (-1, 0)
            self.assertAlmostEqual(cruise_speed_for(cm, x, y, south), expected,
                                   msg=f"{seg.axis} {seg.road_class} at {seg.center}")
            self.assertAlmostEqual(cruise_speed_for(cm, x, y, north), expected)
        # The seeded town must exercise every class for this contract
        self.assertEqual(seen_classes, {"ARTERIAL", "COLLECTOR", "LOCAL"})
        self.assertAlmostEqual(ARTERIAL_CRUISE, 13.0)
        self.assertAlmostEqual(COLLECTOR_CRUISE, 9.0)
        self.assertAlmostEqual(ALLEY_CRUISE, 5.0)

    def test_cruise_lookup_prefers_containing_band_160x160(self):
        """A coordinate inside a segment band uses that segment's class even
        when another centre-line is marginally nearer (city-scale 160 map)."""
        cm = CityMap(width=160, height=160, seed=0)
        arterial = next(s for s in cm.road_segments if s.road_class == "ARTERIAL")
        lo = arterial.center - arterial.width // 2
        x = lo + 0.5                                     # inner edge of band
        speed = cruise_speed_for(cm, x, 80.5, (0, 1))
        self.assertEqual(speed, CRUISE_BY_CLASS["ARTERIAL"])

    def test_cruise_lookup_prefers_containing_band(self):
        """A coordinate inside a segment band uses that segment's class even
        when another centre-line is marginally nearer."""
        cm = CityMap(width=42, height=42, seed=5)
        arterial = next(s for s in cm.road_segments if s.road_class == "ARTERIAL")
        lo = arterial.center - arterial.width // 2
        x = lo + 0.5                                     # inner edge of band
        speed = cruise_speed_for(cm, x, 20.5, (0, 1))
        self.assertEqual(speed, CRUISE_BY_CLASS["ARTERIAL"])

    def test_controller_top_speeds_are_ms(self):
        ctrl = VehicleController()
        cam = Camera()
        for vtype, top in ((VehicleType.POLICE, 16.0), (VehicleType.CYBER_SEDAN, 14.0),
                           (VehicleType.TAXI, 12.0), (VehicleType.BUS, 9.0)):
            v = Vehicle(12.5, 12.5, vtype, (0, 1))
            ctrl.enter_vehicle(v, cam)
            self.assertAlmostEqual(ctrl.max_forward_speed, top)
            ctrl.exit_vehicle(cam)
            self.assertAlmostEqual(ctrl.speed, 0.0)
            self.assertAlmostEqual(cam.eye_m, Camera.EYE_HEIGHT_M)

    def test_cockpit_gauge_reads_km_h(self):
        ctrl = VehicleController()
        cam = Camera()
        vehicle = Vehicle(12.5, 12.5, VehicleType.TAXI, (0, 1))
        ctrl.enter_vehicle(vehicle, cam)
        ctrl.speed = 13.0                                  # arterial cruise
        buf = ScreenBuffer(80, 32)
        CockpitHUD().render(ctrl, buf)
        dash = "".join(p.char for row in buf.pixels for p in row)
        self.assertIn("KM/H", dash)
        self.assertIn(str(int(13.0 * 3.6)), dash)          # 46 km/h readout


if __name__ == "__main__":
    unittest.main()
