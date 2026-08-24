"""
Unit tests for vehicle AI, traffic simulation, and 3D sprites.
"""

import unittest
from src.world.city_map import CityMap
from src.entities.car import Vehicle, VehicleType
from src.entities.traffic_manager import TrafficManager
from src.entities.sprite import make_streetlamp_sprite, make_tree_sprite


class TestEntities(unittest.TestCase):
    def setUp(self):
        self.map = CityMap(width=42, height=42)
        self.traffic = TrafficManager(self.map)

    def test_vehicle_spawn_and_movement(self):
        self.assertGreater(len(self.traffic.vehicles), 0)

        # Test movement on isolated vehicle
        v = Vehicle(x=10.0, y=10.0, vtype=VehicleType.TAXI, heading_dir=(0, 1))
        initial_pos = (v.x, v.y)
        v.update(1.0, self.map, [])
        self.assertNotEqual(initial_pos, (v.x, v.y))

        # Test full traffic manager update step
        self.traffic.update(0.1)

        # At least one vehicle advances over a full second of simulation
        initial_positions = [(veh.x, veh.y) for veh in self.traffic.vehicles]
        self.traffic.update(1.0)
        new_positions = [(veh.x, veh.y) for veh in self.traffic.vehicles]
        moved = any(init != new for init, new in zip(initial_positions, new_positions))
        self.assertTrue(moved)

    def test_directional_sprites(self):
        from src.entities.sprite import VolumetricSprite

        v = Vehicle(x=10.0, y=10.0, vtype=VehicleType.TAXI, heading_dir=(0, 1))  # moving South (+Y)

        # Cars are pseudo-volumetric boxes: one sprite, orientation-driven faces
        spr = v.get_sprite_for_camera(cam_x=10.0, cam_y=5.0)
        self.assertIsInstance(spr, VolumetricSprite)

        # Camera behind vehicle at (10, 5) -> rear hemisphere, red taillights
        _, _, see_front = spr.visible_faces(10.0 - v.x, 5.0 - v.y)
        self.assertFalse(see_front)
        self.assertIn((255, 20, 20), spr.back_fg[2])

        # Camera in front of vehicle at (10, 15) -> front face, headlight glow
        _, _, see_front_ahead = v.get_sprite_for_camera(
            cam_x=10.0, cam_y=15.0).visible_faces(10.0 - v.x, 15.0 - v.y)
        self.assertTrue(see_front_ahead)

        # Camera abeam-but-forward at (15, 12) -> blended corner view
        share, _, _ = v.get_sprite_for_camera(
            cam_x=15.0, cam_y=12.0).visible_faces(15.0 - v.x, 12.0 - v.y)
        self.assertGreater(share, 0.2)
        self.assertLess(share, 0.8)

    def test_police_siren_alternates_on_both_faces(self):
        v = Vehicle(x=10.0, y=10.0, vtype=VehicleType.POLICE, heading_dir=(0, 1))
        v.siren_tick = 0.0
        spr = v.get_sprite_for_camera(cam_x=10.0, cam_y=20.0)
        self.assertEqual(spr.front_fg[0][3], (255, 30, 30))
        self.assertEqual(spr.back_fg[0][3], (255, 30, 30))
        v.siren_tick = 1.0  # odd tick flips the siren phase
        spr2 = v.get_sprite_for_camera(cam_x=10.0, cam_y=20.0)
        self.assertEqual(spr2.front_fg[0][3], (30, 100, 255))

    def test_static_props_created(self):
        self.assertGreater(len(self.traffic.static_props), 15)
        tree = make_tree_sprite(15.0, 15.0)
        self.assertEqual(tree.name, "TREE")
        self.assertGreater(tree.width, 0)
        self.assertGreater(tree.height, 0)


if __name__ == "__main__":
    unittest.main()
