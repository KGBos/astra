"""
Unit tests for procedural city map grid, road topology, and districts.
"""

import unittest
from src.world.city_map import CityMap, FloorType


class TestCityMap(unittest.TestCase):
    def setUp(self):
        self.map = CityMap(width=42, height=42)

    def test_dimensions_and_boundaries(self):
        self.assertEqual(self.map.width, 42)
        self.assertEqual(self.map.height, 42)

        # Boundary perimeter must be solid
        for x in range(42):
            self.assertTrue(self.map.is_solid(x, 0))
            self.assertTrue(self.map.is_solid(x, 41))
        for y in range(42):
            self.assertTrue(self.map.is_solid(0, y))
            self.assertTrue(self.map.is_solid(41, y))

    def test_road_grid_continuity(self):
        # Road columns must not be solid
        for col in self.map.ns_road_cols:
            for y in range(2, 40):
                self.assertFalse(self.map.is_solid(col, y))
                self.assertFalse(self.map.is_solid(col + 1, y))

        # Road rows must not be solid
        for row in self.map.ew_road_rows:
            for x in range(2, 40):
                self.assertFalse(self.map.is_solid(x, row))
                self.assertFalse(self.map.is_solid(x, row + 1))

    def test_traffic_lights_registered(self):
        self.assertGreater(len(self.map.traffic_lights), 10)
        # Verify traffic light update cycle
        tl = list(self.map.traffic_lights.values())[0]
        initial_state = tl.state
        tl.update(12.0)  # should transition
        self.assertNotEqual(tl.state, initial_state)

    def test_districts_and_streets(self):
        district = self.map.get_district_at(8, 8)
        self.assertIn("CYBER-DOWNTOWN", district)
        street = self.map.get_nearest_street_name(4, 4)
        self.assertTrue(len(street) > 0)


if __name__ == "__main__":
    unittest.main()
