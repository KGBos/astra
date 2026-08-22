"""
Unit tests for vehicle driving mode, nitro acceleration, NPC pedestrians, and dialogue trees.
"""

import unittest
from src.engine.camera import Camera
from src.world.city_map import CityMap
from src.entities.car import Vehicle, VehicleType
from src.entities.npc import NPC, build_default_npcs, DialogueOption


class TestDrivingAndNPCs(unittest.TestCase):
    def setUp(self):
        self.map = CityMap(width=42, height=42)
        self.camera = Camera(x=12.5, y=6.5)

    def test_vehicle_mounting_and_driving(self):
        self.assertFalse(self.camera.is_driving)
        self.camera.enter_vehicle("CYBER_SEDAN", 12.5, 6.5, 0.0, 1.0)
        self.assertTrue(self.camera.is_driving)
        self.assertEqual(self.camera.vehicle_type_name, "CYBER_SEDAN")

        # Accelerate
        initial_v = self.camera.car_velocity
        self.camera.car_accelerate(0.5, nitro=False)
        self.assertGreater(self.camera.car_velocity, initial_v)

        # Nitro boost
        self.camera.car_accelerate(0.5, nitro=True)
        self.assertTrue(self.camera.nitro_active)

        # Update physics
        self.camera.update_physics(0.1, self.map)
        self.assertLess(self.camera.nitro_meter, 100.0)

        # Exit vehicle
        self.camera.exit_vehicle()
        self.assertFalse(self.camera.is_driving)
        self.assertEqual(self.camera.car_velocity, 0.0)

    def test_npc_pedestrians_and_dialogue(self):
        npcs = build_default_npcs()
        self.assertGreater(len(npcs), 0)
        kaito = npcs[0]
        self.assertEqual(kaito.name, "Kaito")
        self.assertGreater(len(kaito.dialogue), 0)

        # Test dialogue structure
        opt = kaito.dialogue[0]
        self.assertTrue(len(opt.text) > 0)
        self.assertTrue(len(opt.response) > 0)

        # Test NPC walking update
        init_x, init_y = kaito.x, kaito.y
        kaito.update(1.0, self.map)
        spr = kaito.get_sprite()
        self.assertIn("NPC_Kaito", spr.name)


if __name__ == "__main__":
    unittest.main()
