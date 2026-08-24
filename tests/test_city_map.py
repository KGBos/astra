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
        # Generator v2: every planned road band must be fully carved (no
        # buildings on roads) along its live span -- the connectivity
        # guarantee that replaced the old uniform 2-lane grid assumption.
        # Spans may be truncated by the harbor quay (EW roads end there).
        for seg in self.map.road_segments:
            lo = seg.center - seg.width // 2
            hi = lo + seg.width
            if seg.axis == "NS":
                for y in range(max(2, seg.start), min(self.map.height - 2, seg.end + 1)):
                    for x in range(lo, hi):
                        self.assertFalse(self.map.is_solid(x, y),
                                         f"solid in NS {seg.road_class}@{seg.center} at {(x, y)}")
            else:
                for x in range(max(2, seg.start), min(self.map.width - 2, seg.end + 1)):
                    for y in range(lo, hi):
                        self.assertFalse(self.map.is_solid(x, y),
                                         f"solid in EW {seg.road_class}@{seg.center} at {(x, y)}")

    def test_traffic_lights_registered(self):
        self.assertGreater(len(self.map.traffic_lights), 10)
        # Verify traffic light update cycle
        tl = list(self.map.traffic_lights.values())[0]
        initial_state = tl.state
        tl.update(12.0)  # should transition
        self.assertNotEqual(tl.state, initial_state)

    def test_districts_and_streets(self):
        # Generator v2 zones center-out: the map centre is downtown ground
        mid = self.map.width // 2
        district = self.map.get_district_at(mid, mid)
        self.assertIn("CYBER-DOWNTOWN", district)
        street = self.map.get_nearest_street_name(4, 4)
        self.assertTrue(len(street) > 0)


if __name__ == "__main__":
    unittest.main()
