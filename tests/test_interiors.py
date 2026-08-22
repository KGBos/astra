"""
Unit tests for building interiors, textures, and portal transitions.
"""

import unittest
from src.world.interiors import build_interiors_catalog, InteriorRoom, build_interior_textures


class TestInteriors(unittest.TestCase):
    def setUp(self):
        self.interiors = build_interiors_catalog()

    def test_interiors_catalog_built(self):
        self.assertIn("RAMEN_SHOP", self.interiors)
        self.assertIn("ARCADE", self.interiors)
        self.assertIn("HOTEL_LOBBY", self.interiors)

    def test_room_collision_and_doorways(self):
        ramen = self.interiors["RAMEN_SHOP"]
        self.assertEqual(ramen.width, 12)
        self.assertEqual(ramen.height, 12)

        # Boundary perimeter must be solid except doorway
        self.assertTrue(ramen.is_solid(0, 5))
        self.assertTrue(ramen.is_solid(11, 5))
        self.assertTrue(ramen.is_solid(5, 0))

        # Center of room must be open
        self.assertFalse(ramen.is_solid(ramen.spawn_pos[0], ramen.spawn_pos[1]))

    def test_interior_textures(self):
        textures = build_interior_textures()
        self.assertIn(101, textures)
        self.assertIn(102, textures)
        self.assertIn(103, textures)
        self.assertEqual(textures[101].name, "RAMEN_INTERIOR")


if __name__ == "__main__":
    unittest.main()
