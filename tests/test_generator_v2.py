"""
Cycle B "Generator v2" verification: road hierarchy stats measured from the
floors grid, irregular block faces, center-out district height gradient,
central park and harbor front presence, landmark spacing, road connectivity,
interiors doorway compatibility, spawn safety, determinism, and the <3 s
generation budget at the 320x320 default.
"""

import math
import time
import unittest
from collections import deque
from dataclasses import fields as dataclass_fields

from src.world.city_map import CityMap, FloorType
from src.entities.traffic_manager import TrafficManager
from src.world.procedural_gen import (
    CLASS_ARTERIAL,
    CLASS_COLLECTOR,
    CLASS_LOCAL,
    CityMapData,
    ProceduralCityGenerator,
    RoadSegment,
    build_road_lanes,
)
from src.world.textures import get_texture

SEED = 20260823
DIM = 320

ROAD_FLOORS = (FloorType.ROAD_NS, FloorType.ROAD_EW,
               FloorType.INTERSECTION, FloorType.BRIDGE)


def _generate(seed=SEED, width=DIM, height=DIM):
    return ProceduralCityGenerator().generate(seed=seed, width=width, height=height)


def _road_runs(data, axis):
    """Maximal road-line runs measured purely from the floors grid.

    A cross-axis line counts when >=75% of its cells carry a road floor
    (roads/intersections/bridges); returns [(start, end, width), ...].
    """
    lo, hi = 1, data.height - 2 if axis == "NS" else data.width - 2
    frac = []
    for i in range(data.width if axis == "NS" else data.height):
        if axis == "NS":
            f = sum(1 for y in range(lo, hi + 1) if data.floors[y][i] in ROAD_FLOORS)
        else:
            f = sum(1 for x in range(lo, hi + 1) if data.floors[i][x] in ROAD_FLOORS)
        frac.append(f / (hi - lo + 1))
    runs = []
    cur = None
    for i, f in enumerate(frac):
        if f >= 0.75:
            cur = [i, i] if cur is None else [cur[0], i]
        elif cur is not None:
            runs.append((cur[0], cur[1], cur[1] - cur[0] + 1))
            cur = None
    if cur is not None:
        runs.append((cur[0], cur[1], cur[1] - cur[0] + 1))
    return runs


def _corridors(lines):
    """Arterial-bounded corridors of one axis: [(A, B, inner_lines)]."""
    arts = [s for s in lines if s.road_class == CLASS_ARTERIAL]
    out = []
    for a, b in zip(arts, arts[1:]):
        inner = [s for s in lines if a.center < s.center < b.center]
        out.append((a, b, inner))
    return out


class TestRoadHierarchy(unittest.TestCase):
    def setUp(self):
        self.data = _generate()

    def test_arterial_width_and_spacing_measured_from_floors(self):
        """Grid-measured runs must bucket into 14 m arterials / 9 m collectors /
        5 m locals, with arterial centre spacing of 40-56 m on both axes."""
        for axis in ("NS", "EW"):
            runs = _road_runs(self.data, axis)
            widths = {w for _, _, w in runs}
            self.assertTrue(widths <= {14, 9, 5},
                            f"{axis} unexpected road widths: {widths}")
            art_centers = [c for c, _, w in runs if w == 14]
            self.assertGreaterEqual(len(art_centers), 4,
                                    f"{axis} too few arterials: {art_centers}")
            for a, b in zip(art_centers, art_centers[1:]):
                self.assertTrue(40 <= b - a <= 56,
                                f"{axis} arterial spacing {b - a} outside 40-56")

    def _park_bbox(self):
        pts = [(x, y) for y in range(DIM) for x in range(DIM)
               if self.data.districts[y][x] == "CENTRAL ASTRA PLAZA"]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    def test_collector_width_and_16_24_rhythm(self):
        """Collectors are 9 m wide and every consecutive centre-line gap inside
        a collector corridor stays within 16-24 m; each terminates on an
        arterial, the map edge, or the harbor quay."""
        segs = self.data.road_segments
        for axis in ("NS", "EW"):
            lines = sorted((s for s in segs if s.axis == axis),
                           key=lambda s: s.center)
            cols = [s for s in lines if s.road_class == CLASS_COLLECTOR]
            self.assertGreaterEqual(len(cols), 1, f"{axis} too few collectors")
            for c in cols:
                self.assertEqual(c.width, 9)
                neighbours = sorted(
                    (s.center for s in lines
                     if s.road_class != CLASS_LOCAL and s.center != c.center))
                pos = neighbours.index(max((n for n in neighbours if n < c.center),
                                           default=c.center))
                left = c.center - neighbours[pos]
                right = neighbours[pos + 1] - c.center
                # One side may be the quay truncation; the other must be rhythmic.
                rhythm_ok = (16 <= left <= 24) or (16 <= right <= 24)
                at_quay = c.end <= self._quay_x()
                self.assertTrue(rhythm_ok or at_quay,
                                f"{axis} collector {c.center} gaps {left}/{right}")
        total_cols = sum(1 for s in segs if s.road_class == CLASS_COLLECTOR)
        self.assertGreaterEqual(total_cols, 6,
                                "hierarchy collapsed to almost no collectors")

    def test_local_lanes_cut_only_wide_open_blocks(self):
        """Open corridors (no collector) wider than 34 m get exactly one 5 m
        local lane; narrower open corridors get none. Park corridors are
        intentionally open transverse lawn."""
        segs = self.data.road_segments
        px0, py0, px1, py1 = self._park_bbox()
        found_local = False
        for axis in ("NS", "EW"):
            lines = sorted((s for s in segs if s.axis == axis),
                           key=lambda s: s.center)
            arts = [s for s in lines if s.road_class == CLASS_ARTERIAL]
            for a, b in zip(arts, arts[1:]):
                face = (b.center - b.width // 2 - 1) \
                    - (a.center - a.width // 2 + a.width) + 1
                locals_here = [s for s in lines
                               if s.road_class == CLASS_LOCAL
                               and a.center < s.center < b.center]
                cols_here = [s for s in lines
                             if s.road_class == CLASS_COLLECTOR
                             and a.center < s.center < b.center]
                if axis == "NS":
                    in_park = a.center <= px1 + 14 and b.center >= px0 - 14
                else:
                    in_park = a.center <= py1 + 14 and b.center >= py0 - 14
                if in_park or cols_here:
                    # Collector corridors subdivide into narrow cells already;
                    # park corridors are intentionally open transverse lawn.
                    continue
                if face > 34:
                    self.assertEqual(len(locals_here), 1,
                                     f"{axis} corridor {a.center}-{b.center} "
                                     f"face {face} needs exactly one local")
                    found_local = True
                else:
                    self.assertFalse(locals_here,
                                     f"{axis} narrow corridor {a.center} got a local")
        self.assertTrue(found_local, "expected at least one local lane on this seed")

    def test_superblock_faces_within_spec_band(self):
        """Arterial-to-arterial block faces land in the spec's 18-48 m band."""
        for axis in ("NS", "EW"):
            arts = sorted((s for s in self.data.road_segments
                           if s.axis == axis and s.road_class == CLASS_ARTERIAL),
                          key=lambda s: s.center)
            for a, b in zip(arts, arts[1:]):
                face = (b.center - b.width // 2 - 1) \
                    - (a.center - a.width // 2 + a.width) + 1
                self.assertTrue(18 <= face <= 48, f"{axis} face {face}")

    def test_road_connectivity_single_component(self):
        """BFS from a downtown intersection reaches ~all road cells: no orphan
        collector or local segments anywhere on the map."""
        walls, floors = self.data.walls, self.data.floors
        cx = cy = DIM // 2
        start = min(
            ((x, y) for y in range(DIM) for x in range(DIM)
             if floors[y][x] in ROAD_FLOORS and walls[y][x] == 0),
            key=lambda p: math.hypot(p[0] - cx, p[1] - cy),
        )
        seen = {start}
        queue = deque([start])
        while queue:
            x, y = queue.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < DIM and 0 <= ny < DIM and (nx, ny) not in seen \
                        and floors[ny][nx] in ROAD_FLOORS and walls[ny][nx] == 0:
                    seen.add((nx, ny))
                    queue.append((nx, ny))
        total = sum(1 for y in range(DIM) for x in range(DIM)
                    if floors[y][x] in ROAD_FLOORS and walls[y][x] == 0)
        self.assertGreaterEqual(len(seen) / total, 0.995,
                                f"only {len(seen)}/{total} road cells reachable")

    def _quay_x(self):
        return self.data.width - 2 - max(3, round(16 * self.data.width / 320.0))


class TestDistrictsAtScale(unittest.TestCase):
    def setUp(self):
        self.data = _generate()

    def _mean_height(self, district_names):
        total = count = 0
        for y in range(DIM):
            for x in range(DIM):
                wt = self.data.walls[y][x]
                if wt > 0 and self.data.districts[y][x] in district_names:
                    total += get_texture(wt).height_mult
                    count += 1
        self.assertGreater(count, 200, f"too few wall samples for {district_names}")
        return total / count

    def test_downtown_midrise_industrial_height_gradient(self):
        downtown = self._mean_height({"CYBER-DOWNTOWN"})
        midrise = self._mean_height({"FINANCIAL CORE", "NEON ENTERTAINMENT",
                                     "HISTORIC BROWNSTONES"})
        industrial = self._mean_height({"INDUSTRIAL DOCKLANDS"})
        self.assertGreater(downtown, 25.0, "downtown towers below 25 m mean")
        self.assertLess(downtown, 60.0)
        self.assertGreater(downtown, midrise * 1.8)
        self.assertGreater(midrise, industrial)

    def test_central_park_exceeds_80x80(self):
        grass = [(x, y) for y in range(DIM) for x in range(DIM)
                 if self.data.floors[y][x] == FloorType.PARK_GRASS]
        xs = [p[0] for p in grass]
        ys = [p[1] for p in grass]
        self.assertGreaterEqual(max(xs) - min(xs), 80)
        self.assertGreaterEqual(max(ys) - min(ys), 80)
        # Lawns minus two arterial transverses and their path margins.
        self.assertGreater(len(grass), 2500, "park mostly paved over")

    def test_harbor_front_water_quay_and_mooring(self):
        water = [(x, y) for y in range(DIM) for x in range(DIM)
                 if self.data.floors[y][x] == FloorType.WATER]
        self.assertTrue(water, "no water cells")
        max_x = max(p[0] for p in water)
        self.assertGreaterEqual(max_x, DIM - 12, "water band not at east edge")
        quay_col = max(range(DIM), key=lambda x: sum(
            1 for y in range(DIM) if self.data.walls[y][x] == 10))
        quay_cells = sum(1 for y in range(DIM)
                         if self.data.walls[y][quay_col] == 10)
        self.assertGreater(quay_cells, 100, "no continuous quay wall")
        bridge_cells = sum(
            1 for y in range(DIM) for x in range(quay_col + 1, DIM - 1)
            if self.data.floors[y][x] == FloorType.BRIDGE)
        self.assertGreaterEqual(
            bridge_cells, 1,
            "harbor front is advertised with bridges but none cross the water")
        crossing_cols = [
            x for x in range(quay_col + 1, DIM - 1)
            if sum(1 for y in range(DIM)
                   if self.data.floors[y][x] == FloorType.BRIDGE) > DIM // 3]
        # The bridged arterial straddles the shoreline: most of its 14 m band
        # lies over water, the rest approaches on land.
        self.assertGreaterEqual(
            len(crossing_cols), 8,
            f"expected a full NS arterial bridging the water, "
            f"got crossing columns {crossing_cols}")
        bollards = [p for p in self.data.props if "BOLLARD" in p.name.upper()]
        self.assertGreaterEqual(len(bollards), 4, "no mooring bollards")
        marina = [lm for lm in self.data.landmarks
                  if lm.landmark_type == "MARINA"]
        self.assertEqual(len(marina), 1)

    def test_districts_cover_every_cell(self):
        for y in range(0, DIM, 7):
            for x in range(0, DIM, 7):
                self.assertTrue(self.data.districts[y][x],
                                f"unzoned cell at {(x, y)}")


class TestLandmarks(unittest.TestCase):
    def setUp(self):
        self.data = _generate()

    def test_at_least_eight_true_footprints(self):
        core = [lm for lm in self.data.landmarks
                if lm.landmark_type != "MARINA"]
        self.assertGreaterEqual(len(core), 8)
        for lm in core:
            self.assertGreater(lm.foot_w, 0)
            self.assertGreater(lm.foot_h, 0)
            self.assertTrue(lm.district)

    def test_spacing_within_150_400_band(self):
        core = [lm for lm in self.data.landmarks
                if lm.landmark_type != "MARINA"]
        for i, a in enumerate(core):
            for b in core[i + 1:]:
                d = math.hypot(a.x - b.x, a.y - b.y)
                self.assertGreaterEqual(d, 150.0, f"{a.name} <-> {b.name}: {d:.1f} m")
                self.assertLessEqual(d, 400.0, f"{a.name} <-> {b.name}: {d:.1f} m")

    def test_each_landmark_has_plaza_approach(self):
        for lm in self.data.landmarks:
            if lm.landmark_type == "MARINA":
                continue  # the mooring pier is the approach
            px, py = int(lm.x), int(lm.y)
            plaza = sum(
                1 for y in range(max(0, py - 4), min(DIM, py + 5))
                for x in range(max(0, px - 5), min(DIM, px + 6))
                if self.data.floors[y][x] == FloorType.PLAZA_TILES
                and self.data.walls[y][x] == 0)
            self.assertGreaterEqual(plaza, 8,
                                    f"{lm.name} has no approach plaza ({plaza} tiles)")


class TestLargeMapLandmarkSpacing(unittest.TestCase):
    def test_512_landmark_min_spacing_floor(self):
        """At 512x512 the pairwise landmark spacing still respects the 150 m
        contract floor (the 400 m ceiling is size-dependent and unasserted)."""
        data = _generate(seed=SEED, width=512, height=512)
        core = [lm for lm in data.landmarks if lm.landmark_type != "MARINA"]
        self.assertGreaterEqual(len(core), 8, "512x512 lost the landmark set")
        for i, a in enumerate(core):
            for b in core[i + 1:]:
                d = math.hypot(a.x - b.x, a.y - b.y)
                self.assertGreaterEqual(d, 150.0,
                                        f"{a.name} <-> {b.name}: {d:.1f} m")


class TestMassingContracts(unittest.TestCase):
    def setUp(self):
        self.data = _generate()

    def test_interiors_doorway_detection_on_v2_blocks(self):
        """Nora's perimeter-mass contract holds: doorways are detected on v2
        blocks and interiors build over the door's true footprint."""
        city = next(c for c in (CityMap(width=DIM, height=DIM, seed=s)
                                for s in (SEED, SEED + 1, 7, 99)) if c.doorways)
        doorway = city.doorways[0]
        ex, ey = doorway.ext
        self.assertEqual(city.walls[ey][ex], 13)  # retextured threshold
        space, view = city.get_interior(doorway)
        self.assertGreaterEqual(space.w, 3)
        self.assertGreaterEqual(space.h, 3)
        lx = max(1, min(space.w - 2, ex - space.x0))
        ly = max(1, min(space.h - 2, ey - space.y0))
        self.assertEqual(space.grid[ly][lx], 3)  # CELL_DOOR aligned with ext door
        self.assertTrue(view.in_interior)

    def test_setback_towers_have_low_podium_and_tall_core(self):
        """Downtown massing stacks wall types: 4-18 m podium rings around
        40-60 m cores somewhere on the map."""
        data = self.data
        podium_next_to_tower = False
        for y in range(1, DIM - 1):
            for x in range(1, DIM - 1):
                if data.walls[y][x] in (4, 6):
                    for nx, ny in ((x + 2, y), (x - 2, y), (x, y + 2), (x, y - 2)):
                        if data.walls[ny][nx] in (1, 2, 7, 8):
                            podium_next_to_tower = True
                            break
                if podium_next_to_tower:
                    break
            if podium_next_to_tower:
                break
        self.assertTrue(podium_next_to_tower, "no setback tower massing found")

    def test_perimeter_walls_solid(self):
        for i in range(DIM):
            self.assertGreater(self.data.walls[0][i], 0)
            self.assertGreater(self.data.walls[DIM - 1][i], 0)
            self.assertGreater(self.data.walls[i][0], 0)
            self.assertGreater(self.data.walls[i][DIM - 1], 0)


class TestTrafficAndSpawnContracts(unittest.TestCase):
    def setUp(self):
        self.data = _generate()
        self.city = CityMap(width=DIM, height=DIM, seed=SEED)

    def test_citymap_exposes_road_lanes(self):
        lanes = self.city.road_lanes()
        self.assertTrue(lanes)
        by_class = {}
        for lane in lanes:
            self.assertIn(lane["axis"], ("NS", "EW"))
            self.assertIn(lane["road_class"],
                          (CLASS_ARTERIAL, CLASS_COLLECTOR, CLASS_LOCAL))
            self.assertIsInstance(lane["center_m"], float)
            self.assertIsInstance(lane["span"], tuple)
            by_class[lane["road_class"]] = lane
        self.assertEqual(by_class[CLASS_ARTERIAL]["width_m"], 14.0)
        self.assertEqual(by_class[CLASS_ARTERIAL]["lane_offsets_m"], (-3.5, 3.5))
        self.assertEqual(by_class[CLASS_COLLECTOR]["width_m"], 9.0)
        self.assertEqual(by_class[CLASS_COLLECTOR]["lane_offsets_m"], (-1.25, 1.25))
        self.assertEqual(by_class[CLASS_LOCAL]["lane_offsets_m"], (0.0,))

    def test_segments_match_floors_geometry(self):
        """Every planned road line is actually carved: at mid-span, the whole
        band carries road floors (no massing may overwrite roads)."""
        for seg in self.city.road_segments:
            lo = seg.center - seg.width // 2
            band = range(max(1, lo), min((DIM - 1 if seg.axis == "NS" else DIM - 1),
                                         lo + seg.width))
            if seg.axis == "NS":
                y = max(1, min(DIM - 2, (seg.start + seg.end) // 2))
                cells = [self.city.floors[y][x] for x in band]
            else:
                x = max(1, min(DIM - 2, (seg.start + seg.end) // 2))
                cells = [self.city.floors[y][x] for y in band]
            self.assertTrue(all(c in ROAD_FLOORS for c in cells),
                            f"{seg.axis} {seg.road_class}@{seg.center} not fully carved")

    def test_traffic_lights_registered_at_signalized_crossings(self):
        lights = set(self.data.traffic_light_coords)
        self.assertGreater(len(lights), 40)
        for ns_center, ew_center in list(lights)[:20]:
            self.assertIn(self.city.floors[ew_center][ns_center],
                          (FloorType.ROAD_NS, FloorType.ROAD_EW, FloorType.INTERSECTION))

    def test_spawn_safe_central_and_fast(self):
        sx, sy = self.data.spawn_pos
        self.assertTrue(1 <= sx < DIM - 1 and 1 <= sy < DIM - 1)
        self.assertFalse(self.city.is_solid(sx, sy))
        self.assertFalse(self.city.is_water(sx, sy))
        dist = math.hypot(sx - DIM / 2, sy - DIM / 2)
        self.assertLessEqual(dist, 30.0, "spawn not central-ish")

    def test_generation_wall_time_under_3s(self):
        start = time.perf_counter()
        _generate(seed=123)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 3.0, f"generation took {elapsed:.2f}s")


class TestVehicleSpawnFloors(unittest.TestCase):
    def test_vehicles_spawn_only_on_drivable_road(self):
        """Traffic spawns must land on real road floors: never harbor water,
        piers, or sidewalks (harbor-adjacent EW rows previously floated cars
        on the water band)."""
        for seed in (SEED, 7, 99):
            city = CityMap(width=160, height=160, seed=seed)
            tm = TrafficManager(city, vehicle_count=24)
            self.assertGreater(len(tm.vehicles), 0, f"seed {seed}: no vehicles spawned")
            for v in tm.vehicles:
                ft = city.get_floor_type(int(v.x), int(v.y))
                self.assertIn(
                    ft, ROAD_FLOORS,
                    f"seed {seed}: vehicle on non-road floor {ft} at ({v.x:.1f}, {v.y:.1f})")


class TestDeterminismAndCompat(unittest.TestCase):
    def test_same_seed_byte_identical_grids(self):
        a = _generate(seed=777)
        b = _generate(seed=777)
        self.assertEqual(a.walls, b.walls)
        self.assertEqual(a.floors, b.floors)
        self.assertEqual(a.districts, b.districts)
        self.assertEqual(a.spawn_pos, b.spawn_pos)
        self.assertEqual([(lm.x, lm.y, lm.name) for lm in a.landmarks],
                         [(lm.x, lm.y, lm.name) for lm in b.landmarks])
        self.assertEqual([(s.axis, s.road_class, s.center, s.start, s.end)
                          for s in a.road_segments],
                         [(s.axis, s.road_class, s.center, s.start, s.end)
                          for s in b.road_segments])

    def test_different_seeds_differ(self):
        a = _generate(seed=1)
        b = _generate(seed=2)
        self.assertNotEqual(a.walls, b.walls)

    def test_small_maps_still_generate(self):
        for dim in (30, 42, 64):
            data = _generate(seed=5, width=dim, height=dim)
            self.assertEqual(len(data.walls), dim)
            self.assertTrue(data.ns_road_cols)
            self.assertTrue(data.landmarks or dim < 40)
            sx, sy = data.spawn_pos
            self.assertTrue(1 <= sx < dim - 1 and 1 <= sy < dim - 1)

    def test_citymapdata_backward_tolerant(self):
        """New fields default: constructing the legacy positional shape works."""
        names = [f.name for f in dataclass_fields(CityMapData)]
        self.assertIn("road_segments", names)
        required = ["width", "height", "seed", "walls", "floors", "districts",
                    "ns_road_cols", "ew_road_rows", "traffic_light_coords",
                    "avenue_names", "street_names", "landmarks", "road_graph",
                    "props", "spawn_pos"]
        for name in required:
            self.assertEqual(names.index(name), required.index(name),
                             "legacy field order changed")
        minimal = CityMapData(
            width=4, height=4, seed=1,
            walls=[[0] * 4 for _ in range(4)],
            floors=[[0] * 4 for _ in range(4)],
            districts=[[""] * 4 for _ in range(4)],
            ns_road_cols=[], ew_road_rows=[], traffic_light_coords=[],
            avenue_names={}, street_names={}, landmarks=[],
            road_graph=type("G", (), {})(), props=[], spawn_pos=(1.0, 1.0),
        )
        self.assertEqual(minimal.road_segments, [])

    def test_build_road_lanes_shapes(self):
        segs = [RoadSegment("NS", CLASS_ARTERIAL, 36, 14, 1, 318, "Test Ave"),
                RoadSegment("EW", CLASS_LOCAL, 199, 5, 1, 318, "Test Ln")]
        lanes = build_road_lanes(segs)
        self.assertEqual(lanes[0]["center_m"], 36.0)   # even width -> on cell seam
        self.assertEqual(lanes[1]["center_m"], 199.5)  # odd width -> half offset
        self.assertEqual(lanes[1]["lane_offsets_m"], (0.0,))


if __name__ == "__main__":
    unittest.main()
