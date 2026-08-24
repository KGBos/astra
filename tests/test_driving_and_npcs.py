"""
Unit tests for vehicle driving mode (VehicleController incl. nitro), NPC
pedestrians, and dialogue trees.

Adapted to the M2-integration architecture: driving physics live on the
single VehicleController module, not on Camera.
"""

import unittest
from src.engine.camera import Camera
from src.world.city_map import CityMap
from src.entities.car import Vehicle, VehicleType
from src.entities.npc import NPC, build_default_npcs, DialogueOption
from src.entities.vehicle_controller import VehicleController


class TestDrivingAndNPCs(unittest.TestCase):
    def setUp(self):
        # Deterministic seed: the mount-and-drive scenario needs a clear
        # runway from the fixed camera start, which random layouts break.
        self.map = CityMap(width=42, height=42, seed=20260823)
        self.camera = Camera(x=12.5, y=6.5)
        self.ctrl = VehicleController()
        self.vehicle = Vehicle(x=12.5, y=7.0, vtype=VehicleType.CYBER_SEDAN, heading_dir=(0, 1))

    def test_vehicle_mounting_and_driving(self):
        self.assertFalse(self.ctrl.is_driving)
        self.assertIsNone(self.ctrl.try_enter_nearest_vehicle(self.camera, []))
        mounted = self.ctrl.try_enter_nearest_vehicle(self.camera, [self.vehicle])
        self.assertIsNotNone(mounted)
        self.assertTrue(self.ctrl.is_driving)

        # Accelerate
        self.ctrl.update_physics(
            dt=0.5, throttle=1.0, steer_input=0.0,
            camera=self.camera, city_map=self.map, other_vehicles=[])
        self.assertGreater(self.ctrl.speed, 0.0)

        # Nitro boost engages and drains the meter while throttling
        meter_before = self.ctrl.nitro_meter
        speed_before = self.ctrl.speed
        self.ctrl.update_physics(
            dt=0.2, throttle=1.0, steer_input=0.0,
            camera=self.camera, city_map=self.map, other_vehicles=[],
            nitro=True)
        self.assertTrue(self.ctrl.nitro_active)
        self.assertLess(self.ctrl.nitro_meter, meter_before)
        self.assertGreater(self.ctrl.speed, speed_before)

        # Nitro disengages when the request stops; camera follows the car
        self.ctrl.update_physics(
            dt=0.05, throttle=0.0, steer_input=0.0,
            camera=self.camera, city_map=self.map, other_vehicles=[],
            nitro=False)
        self.assertFalse(self.ctrl.nitro_active)
        self.assertAlmostEqual(self.camera.pos.x, self.vehicle.x)
        self.assertAlmostEqual(self.camera.pos.y, self.vehicle.y)

        # Exit vehicle
        self.ctrl.exit_vehicle(self.camera)
        self.assertFalse(self.ctrl.is_driving)
        self.assertEqual(self.ctrl.speed, 0.0)
        self.assertAlmostEqual(self.camera.eye_m, Camera.EYE_HEIGHT_M)

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
