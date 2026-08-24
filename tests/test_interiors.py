"""
Unit tests for themed building interiors, textures, and furniture props.

Adapted to the M2-integration architecture: interior content (themes, wall
textures, furniture) lives on master's doorway/footprint interiors system.
"""

import unittest

from src.world.city_map import CityMap
from src.world.interiors import BUILDING_THEMES, theme_for_building
from src.world.textures import build_interior_textures, TEXTURE_REGISTRY


class TestInteriors(unittest.TestCase):
    def setUp(self):
        self.city = next(
            c for c in (CityMap(width=42, height=42, seed=s) for s in range(24))
            if c.doorways
        )

    def test_themes_catalog_built(self):
        room_ids = [theme.room_id for theme in BUILDING_THEMES]
        self.assertIn("RAMEN_SHOP", room_ids)
        self.assertIn("ARCADE", room_ids)
        self.assertIn("HOTEL_LOBBY", room_ids)

    def test_room_theme_assignment_and_furniture(self):
        d = self.city.doorways[0]
        space, view = self.city.get_interior(d)

        # Deterministic theme rotation per building id
        self.assertEqual(space.theme, theme_for_building(d.bld_id))
        self.assertIn(space.theme.room_id, {"RAMEN_SHOP", "ARCADE", "HOTEL_LOBBY"})

        # Themed walls render with the storefront texture
        self.assertEqual(view.get_wall_type(space.x0, space.y0), space.theme.wall_texture)

        # Large enough rooms carry their themed furniture prop
        if space.w >= 6 and space.h >= 6:
            self.assertGreaterEqual(len(view.props), 1)
            prop = view.props[0]
            self.assertTrue(space.x0 < prop.x < space.x0 + space.w)
            self.assertTrue(space.y0 < prop.y < space.y0 + space.h)

    def test_interior_textures_registered(self):
        textures = build_interior_textures()
        self.assertIn(101, textures)
        self.assertIn(102, textures)
        self.assertIn(103, textures)
        self.assertEqual(textures[101].name, "RAMEN_INTERIOR")
        for texture_id, texture in textures.items():
            self.assertEqual(TEXTURE_REGISTRY[texture_id].name, texture.name)


if __name__ == "__main__":
    unittest.main()
