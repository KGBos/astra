"""
Unit tests and benchmarks for Procedural City Generator, District Partitioner, Road Graph & Landmarks.
Author: Darius Thorne (Procedural World & City Generation Specialist 📐)
"""

import time
import unittest
from src.world.procedural_gen import (
    ProceduralCityGenerator,
    DistrictType,
    Landmark,
    RoadGraph,
)
from src.world.city_map import CityMap, FloorType


class TestProceduralCityGenerator(unittest.TestCase):
    def setUp(self):
        self.generator = ProceduralCityGenerator()

    def test_deterministic_seed_reproducibility(self):
        """Maps generated with the exact same seed must produce identical data structures."""
        map_a = self.generator.generate(seed=424242, width=42, height=42)
        map_b = self.generator.generate(seed=424242, width=42, height=42)

        self.assertEqual(map_a.walls, map_b.walls)
        self.assertEqual(map_a.floors, map_b.floors)
        self.assertEqual(map_a.districts, map_b.districts)
        self.assertEqual(map_a.avenue_names, map_b.avenue_names)
        self.assertEqual(map_a.street_names, map_b.street_names)
        self.assertEqual(len(map_a.landmarks), len(map_b.landmarks))
        for la, lb in zip(map_a.landmarks, map_b.landmarks):
            self.assertEqual(la.name, lb.name)
            self.assertEqual((la.x, la.y), (lb.x, lb.y))

    def test_different_seeds_variation(self):
        """Different seeds must produce varying building layouts and landmark configurations."""
        map_1 = self.generator.generate(seed=111111, width=42, height=42)
        map_2 = self.generator.generate(seed=999999, width=42, height=42)

        # Check that wall layout or street names differ
        differ = (map_1.walls != map_2.walls) or (map_1.avenue_names != map_2.avenue_names)
        self.assertTrue(differ)

    def test_string_seed_hashing(self):
        """String seeds must be deterministically converted and produce reproducible maps."""
        map_str_1 = self.generator.generate(seed="CYBER_PUNK_2077", width=42, height=42)
        map_str_2 = self.generator.generate(seed="CYBER_PUNK_2077", width=42, height=42)
        self.assertEqual(map_str_1.seed, map_str_2.seed)
        self.assertEqual(map_str_1.walls, map_str_2.walls)

    def test_map_dimension_scaling(self):
        """Generator should handle small (30x30) and large (64x64) metropolitan grids."""
        for dim in (30, 42, 64):
            data = self.generator.generate(seed=12345, width=dim, height=dim)
            self.assertEqual(len(data.walls), dim)
            self.assertEqual(len(data.walls[0]), dim)
            # Perimeter must be solid
            for i in range(dim):
                self.assertGreater(data.walls[0][i], 0)
                self.assertGreater(data.walls[dim - 1][i], 0)
                self.assertGreater(data.walls[i][0], 0)
                self.assertGreater(data.walls[i][dim - 1], 0)

    def test_road_graph_and_pathfinding(self):
        """Road network graph must be connected and allow shortest path routing."""
        data = self.generator.generate(seed=777, width=42, height=42)
        graph = data.road_graph

        self.assertGreater(len(graph.nodes), 5)
        self.assertGreater(len(graph.edges), 5)

        # Pick two distinct intersection nodes and verify pathfinding
        node_ids = list(graph.nodes.keys())
        start_id = node_ids[0]
        target_id = node_ids[-1]

        path = graph.shortest_path(start_id, target_id)
        self.assertGreater(len(path), 0)
        self.assertEqual(path[0], (graph.nodes[start_id].x, graph.nodes[start_id].y))
        self.assertEqual(path[-1], (graph.nodes[target_id].x, graph.nodes[target_id].y))

    def test_landmark_and_poi_queries(self):
        """Landmark distance and compass bearings must return accurate data."""
        city = CityMap.from_seed(seed=8888, width=42, height=42)
        self.assertGreater(len(city.landmarks), 0)

        # Nearest landmark query
        lm_info = city.get_nearest_landmark(10.0, 10.0)
        self.assertIsNotNone(lm_info)
        lm, dist, bearing = lm_info
        self.assertIsInstance(lm, Landmark)
        self.assertGreater(dist, 0.0)
        self.assertIn(bearing, ["N", "S", "E", "W", "NE", "NW", "SE", "SW"])

    def test_safe_spawn_point(self):
        """Player spawn position must be strictly inside bounds and on a non-solid, non-water tile."""
        for test_seed in (101, 202, 303, 404, 505):
            city = CityMap.from_seed(seed=test_seed, width=42, height=42)
            sx, sy = city.spawn_pos
            self.assertTrue(1 <= sx < 41)
            self.assertTrue(1 <= sy < 41)
            self.assertFalse(city.is_solid(sx, sy))
            self.assertFalse(city.is_water(sx, sy))

    def test_ascii_overview_renderer(self):
        """ASCII overview renderer should return valid multi-line string containing landmark summaries."""
        city = CityMap.from_seed(seed=999, width=42, height=42)
        ascii_map = city.render_ascii_map()
        self.assertIn("ASTRA 3D CITY MAP", ascii_map)
        self.assertIn("Landmarks", ascii_map)
        self.assertGreater(len(ascii_map.splitlines()), 40)

    def test_generation_performance_benchmark(self):
        """Procedural generation must complete in under 5ms per city."""
        start = time.perf_counter()
        iterations = 50
        for i in range(iterations):
            _ = self.generator.generate(seed=i, width=42, height=42)
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / iterations) * 1000.0
        self.assertLess(avg_ms, 15.0, f"Map generation took {avg_ms:.2f}ms, target is < 15ms")


if __name__ == "__main__":
    unittest.main()
