"""
M5 Cycle C verification: lane-accurate traffic spawning, district-scaled
pedestrian density, tower lobby interiors, and the perf-budget toolchain.

Locks the Cycle C contracts from docs/DESIGN_M5_LIFESIZE.md sections 5-7:
vehicles spawn inside measured lane bands with class-appropriate cruise
speeds, pedestrian populations scale with walkable area per district, downtown
towers expose enterable 8 m lobby volumes, and tools/bench_matrix.py runs
headless as the CI benchmark gate.
"""

import math
import os
import subprocess
import sys
import time
import unittest

from src.world.city_map import CityMap
from src.entities.car import CRUISE_BY_CLASS, COLLECTOR_CRUISE
from src.entities.traffic_manager import (
    TrafficManager,
    compute_vehicle_budget,
    METRES_PER_VEHICLE,
    VEHICLE_COUNT_MIN,
    VEHICLE_COUNT_MAX,
)
from src.entities.pedestrian_manager import (
    PedestrianManager,
    survey_district_walkable,
    compute_pedestrian_budget,
    _apportion,
    SPARSE_DISTRICTS,
)
from src.world.interiors import LobbySpace, door_reaches_street
from src.world.textures import get_texture
from src.game import Game

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVABLE_FLOOR_IDS = (1, 2, 3, 8)          # ROAD_NS / ROAD_EW / INTERSECTION / BRIDGE


class TestLaneAccurateTraffic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.city = CityMap(width=320, height=320, seed=7)
        cls.traffic = TrafficManager(cls.city)

    def test_budget_scales_with_lane_length_and_clamps(self):
        """Fleet budget equals round(total lane metres / 120) clamped [24, 80]."""
        lanes = self.city.road_lanes()
        total_lane_m = sum((ln["span"][1] - ln["span"][0] + 1) * len(ln["lane_offsets_m"])
                           for ln in lanes)
        raw = total_lane_m / METRES_PER_VEHICLE
        expected = max(VEHICLE_COUNT_MIN, min(VEHICLE_COUNT_MAX, round(raw)))
        self.assertEqual(compute_vehicle_budget(self.city), expected)
        self.assertGreaterEqual(raw, VEHICLE_COUNT_MIN)   # 320² metro clears the floor
        # Actual fleet is capped by available lane slots on this geometry
        self.assertGreater(len(self.traffic.vehicles), 0)
        self.assertLessEqual(len(self.traffic.vehicles), expected)

    def test_vehicles_sit_inside_their_lane_band(self):
        """Every spawned vehicle rests on its designed cross-axis coordinate,
        inside the carrier segment's carriageway band."""
        segments = self.city.road_segments
        placed = 0
        for v in self.traffic.vehicles:
            self.assertIsNotNone(v.lane_axis)
            cross = v.x if v.lane_axis == "NS" else v.y
            designed = v.lane_center_m + v.lane_offset_m
            self.assertAlmostEqual(cross, designed, delta=1e-6,
                                   msg="vehicle left its designed lane")
            carrier = [s for s in segments
                       if s.axis == v.lane_axis
                       and abs(s.center + (0.5 if s.width % 2 else 0.0)
                               - v.lane_center_m) < 0.51]
            self.assertTrue(carrier, f"no segment backs lane center {v.lane_center_m}")
            seg = carrier[0]
            half = seg.width / 2.0
            self.assertLessEqual(abs(v.lane_offset_m), half + 0.01,
                                 "lane offset leaves the carriageway band")
            along_lo, along_hi = seg.start, seg.end
            along = v.y if v.lane_axis == "NS" else v.x
            self.assertTrue(along_lo <= along <= along_hi + 1.0,
                            "vehicle spawned outside the segment span")
            placed += 1
        self.assertGreater(placed, 0)

    def test_right_hand_headings_match_lane_side(self):
        """Right-hand traffic: a lane west of an NS centre-line runs southbound
        (and east of it northbound); south of an EW centre-line eastbound."""
        for v in self.traffic.vehicles:
            side = v.lane_offset_m
            if v.lane_axis == "NS":
                expected = (0, 1) if side < 0 else ((0, -1) if side > 0 else None)
            else:
                expected = (1, 0) if side > 0 else ((-1, 0) if side < 0 else None)
            if expected is not None:
                self.assertEqual((v.dx, v.dy), expected,
                                 f"wrong heading for offset {side} on {v.lane_axis}")

    def test_class_appropriate_cruise_speeds(self):
        """Cruise targets come from the carrier road class: arterial 13,
        collector 9, local 5 m/s."""
        counts = {}
        for v in self.traffic.vehicles:
            self.assertIn(v.road_class, CRUISE_BY_CLASS)
            self.assertAlmostEqual(v.target_speed, CRUISE_BY_CLASS[v.road_class])
            counts[v.road_class] = counts.get(v.road_class, 0) + 1
        self.assertIn("ARTERIAL", counts, "no arterial traffic spawned")
        self.assertIn("COLLECTOR", counts, "no collector traffic spawned")

    def test_no_vehicle_spawns_on_water_or_park(self):
        """The drivable-floor guard survives the lane rewrite: no vehicle ever
        starts on water, piers, sidewalks, or park grass."""
        for v in self.traffic.vehicles:
            ft = self.city.get_floor_type(int(v.x), int(v.y))
            self.assertIn(ft, DRIVABLE_FLOOR_IDS,
                          f"vehicle on floor {ft} at ({v.x:.1f}, {v.y:.1f})")

    def test_explicit_count_still_respected(self):
        """Hand-picked fleet sizes bypass the auto budget unchanged."""
        small = CityMap(width=42, height=42, seed=7)
        tm = TrafficManager(small, vehicle_count=9)
        self.assertEqual(len(tm.vehicles), 9)


class TestPedestrianDensity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.city = CityMap(width=320, height=320, seed=11)
        started = time.perf_counter()
        cls.manager = PedestrianManager(cls.city)
        cls.spawn_seconds = time.perf_counter() - started

    def test_population_within_bounds_at_320(self):
        """Auto population lands inside the [40, 140] contract band at 320²."""
        self.assertGreaterEqual(len(self.manager.pedestrians), 40)
        self.assertLessEqual(len(self.manager.pedestrians), 140)

    def test_spawn_scan_under_half_second(self):
        """Walkable survey plus placement stays far below the 0.5 s budget."""
        self.assertLess(self.spawn_seconds, 0.5,
                        f"spawn took {self.spawn_seconds * 1000:.0f} ms")

    def test_budget_matches_density_formula(self):
        """Auto count equals the per-district density integral, clamped."""
        areas, _ = survey_district_walkable(self.city)
        self.assertEqual(len(self.manager.pedestrians),
                         compute_pedestrian_budget(areas))

    def test_district_shares_are_proportional_to_weighted_area(self):
        """Each district's pedestrian share tracks its density-weighted share
        of walkable ground (largest-remainder quotas, tolerance for rounding)."""
        areas, _ = survey_district_walkable(self.city)
        weights = {
            district: area * (1.0 / 2700.0 if district in SPARSE_DISTRICTS
                              else 1.0 / 900.0)
            for district, area in areas.items()
        }
        total = len(self.manager.pedestrians)
        expected = _apportion(total, weights)
        actual = {}
        for ped in self.manager.pedestrians:
            district = self.city.get_district_at(ped.x, ped.y)
            actual[district] = actual.get(district, 0) + 1
        for district, quota in expected.items():
            if quota < 4:
                continue
            self.assertLessEqual(abs(actual.get(district, 0) - quota),
                                 max(2, 0.25 * quota),
                                 f"{district}: {actual.get(district, 0)} vs quota {quota}")

    def test_dense_districts_pack_tighter_than_industrial(self):
        """Downtown-side walkable ground carries more peds per m2 than the
        industrial docklands (target ratio ~3x)."""
        areas, _ = survey_district_walkable(self.city)
        dense_area = sum(a for d, a in areas.items() if d not in SPARSE_DISTRICTS)
        sparse_area = sum(a for d, a in areas.items() if d in SPARSE_DISTRICTS)
        if min(dense_area, sparse_area) < 300:
            self.skipTest("seed lacks comparable dense/sparse walkable area")
        dense_peds = sparse_peds = 0
        for ped in self.manager.pedestrians:
            district = self.city.get_district_at(ped.x, ped.y)
            if district in SPARSE_DISTRICTS:
                sparse_peds += 1
            else:
                dense_peds += 1
        ratio = (dense_peds / dense_area) / max(1e-9, sparse_peds / sparse_area)
        self.assertGreater(ratio, 1.5, "industrial is not sparser than the core")
        self.assertLess(ratio, 6.0, "dense/sparse split drifted off-model")

    def test_small_map_explicit_count_unchanged(self):
        """Legacy explicit-count construction keeps its exact population."""
        town = CityMap(width=42, height=42, seed=12345)
        pm = PedestrianManager(town, pedestrian_count=20)
        self.assertEqual(len(pm.pedestrians), 20)

    def test_apportion_conserves_total(self):
        """Largest-remainder split always sums exactly to the requested total."""
        for total in (0, 1, 7, 40, 137):
            quotas = _apportion(total, {"a": 10.0, "b": 3.0, "c": 1.0})
            self.assertEqual(sum(quotas.values()), total)


def _find_lobby_city(max_seeds=8):
    """Deterministic first seed (ascending) whose map yields a tower lobby."""
    for seed in range(max_seeds):
        city = CityMap(width=320, height=320, seed=seed)
        for doorway in city.doorways:
            space, view = city.get_interior(doorway)
            if isinstance(space, LobbySpace):
                return city, doorway, space, view
    return None


class TestTowerLobbies(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.found = _find_lobby_city()
        cls.city = cls.found[0] if cls.found else None

    def test_downtown_tower_seed_yields_a_lobby(self):
        """Some enterable building within the scan resolves to a lobby hall."""
        self.assertIsNotNone(
            self.found, "no seed in range produced a tower lobby interior")

    def test_lobby_is_an_eight_metre_volume(self):
        """The lobby theme's wall texture projects a ~8 m ceiling volume."""
        _, doorway, space, _view = self.found
        self.assertTrue(space.is_lobby)
        self.assertEqual(space.theme.wall_texture, 104)
        texture = get_texture(space.theme.wall_texture)
        self.assertGreaterEqual(texture.height_mult, 7.5)
        self.assertGreaterEqual(space.w * space.h, 9)

    def test_lobby_door_is_retextured_and_street_reachable(self):
        """Tower thresholds read as doors from the street and provably reach
        road floor, so the entrance is never sealed behind a courtyard."""
        _, doorway, _, _ = self.found
        ex, ey = doorway.ext
        self.assertEqual(self.city.walls[ey][ex], 13)
        self.assertTrue(door_reaches_street(self.city, doorway.ext, doorway.side))

    def test_lobby_enter_exit_flow(self):
        """The standard game transition enters the lobby and returns to the
        street through the same door (Nora's doorway flow, lobby edition)."""
        g = Game(width=64, height=24)
        g.city_map = self.city
        g.interior_view = None
        g.traffic = TrafficManager(self.city)
        g.pedestrians = PedestrianManager(self.city)
        doorway, space = self.found[1], self.found[2]
        ex, ey = doorway.ext
        ox, oy = ((1, 0), (0, 1), (-1, 0), (0, -1))[doorway.side]
        g.camera.pos.x = ex + 0.5 + ox * 0.9
        g.camera.pos.y = ey + 0.5 + oy * 0.9
        g._update_space()
        self.assertIsNotNone(g.interior_view, "did not enter the tower lobby")
        entered = g.interior_view.space
        self.assertTrue(entered.is_lobby)
        self.assertIs(entered, space)
        inside_x = g.camera.pos.x
        inside_y = g.camera.pos.y
        self.assertTrue(space.x0 <= int(inside_x) < space.x0 + space.w
                        and space.y0 <= int(inside_y) < space.y0 + space.h)
        wx, wy = space.inner_door_world
        g.camera.pos.x, g.camera.pos.y = wx, wy
        g._update_space()
        self.assertIsNone(g.interior_view, "did not exit the tower lobby")


class TestPerfBudgetTooling(unittest.TestCase):
    def test_bench_matrix_runs_headless_and_passes(self):
        """tools/bench_matrix.py completes headless with a tiny matrix and
        exits 0 with an FPS table on stdout."""
        proc = subprocess.run(
            [sys.executable, "tools/bench_matrix.py",
             "--frames", "4", "--runs", "1", "--sizes", "48x16"],
            cwd=REPO_ROOT, capture_output=True, timeout=300,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn(b"FPS", proc.stdout)
        self.assertIn(b"PASS", proc.stdout)

    def test_generation_time_under_budget(self):
        """City generation (now including tower-door detection) stays under
        the 100 ms cycle budget at the default 320x320 size."""
        start = time.perf_counter()
        CityMap(width=320, height=320, seed=7)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 0.1,
                        f"generation took {elapsed * 1000:.0f} ms")


if __name__ == "__main__":
    unittest.main()
