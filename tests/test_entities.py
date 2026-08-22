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
        v = self.traffic.vehicles[0]
        initial_pos = (v.x, v.y)
        
        # Update simulation for 1 second
        self.traffic.update(1.0)
        new_pos = (v.x, v.y)
        self.assertNotEqual(initial_pos, new_pos)

    def test_directional_sprites(self):
        v = Vehicle(x=10.0, y=10.0, vtype=VehicleType.TAXI, heading_dir=(0, 1))  # moving South (+Y)
        
        # Camera behind vehicle at (10, 5) -> looking at rear
        spr_rear = v.get_sprite_for_camera(cam_x=10.0, cam_y=5.0)
        self.assertEqual(spr_rear.name, "CAR_REAR")

        # Camera in front of vehicle at (10, 15) -> looking at front
        spr_front = v.get_sprite_for_camera(cam_x=10.0, cam_y=15.0)
        self.assertEqual(spr_front.name, "CAR_FRONT")

        # Camera to side of vehicle at (15, 10) -> looking at side
        spr_side = v.get_sprite_for_camera(cam_x=15.0, cam_y=10.0)
        self.assertEqual(spr_side.name, "CAR_SIDE")

    def test_static_props_created(self):
        self.assertGreater(len(self.traffic.static_props), 15)
        tree = make_tree_sprite(15.0, 15.0)
        self.assertEqual(tree.name, "TREE")
        self.assertGreater(tree.width, 0)
        self.assertGreater(tree.height, 0)


if __name__ == "__main__":
    unittest.main()
