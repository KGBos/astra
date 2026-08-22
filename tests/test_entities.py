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
        self.traffic = TrafficManager(self.map, vehicle_count=10)

    def test_vehicle_spawn_and_movement(self):
        self.assertEqual(len(self.traffic.vehicles), 10)
        v = self.traffic.vehicles[0]
        initial_pos = (v.x, v.y)
        
        # Update simulation for 1 second
        self.traffic.update(1.0)
        new_pos = (v.x, v.y)
        self.assertNotEqual(initial_pos, new_pos)

    def test_directional_sprites(self):
        v = Vehicle(x=10.0, y=10.0, vtype=VehicleType.TAXI, heading_dir=(0, 1))  # moving South (+Y)
        
        # Camera behind vehicle (at 10, 5) -> looking South at car's back -> seeing rear
        spr_rear = v.get_sprite_for_camera(cam_x=10.0, cam_y=5.0)
        self.assertEqual(spr_rear.name, "CAR_REAR")

        # Camera ahead of vehicle (at 10, 15) -> looking North at car's front -> seeing front
        spr_front = v.get_sprite_for_camera(cam_x=10.0, cam_y=15.0)
        self.assertEqual(spr_front.name, "CAR_FRONT")

    def test_static_props_created(self):
        self.assertGreater(len(self.traffic.static_props), 15)
        tree = make_tree_sprite(15.0, 15.0)
        self.assertEqual(tree.name, "TREE")
        self.assertGreater(tree.width, 0)
        self.assertGreater(tree.height, 0)


if __name__ == "__main__":
    unittest.main()
