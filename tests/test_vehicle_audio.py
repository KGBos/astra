"""
Unit tests for Vehicle Controller, Cockpit Dashboard HUD, and Soundscape Engine.
Author: Valerie Sterling ⚡ (3D Raycaster & Rasterization Specialist)
"""

import math
import unittest
from src.engine.camera import Camera
from src.world.city_map import CityMap
from src.entities.car import Vehicle, VehicleType
from src.entities.vehicle_controller import VehicleController
from src.renderer.cockpit_hud import CockpitHUD
from src.renderer.screen_buffer import ScreenBuffer
from src.audio.soundscape import SoundscapeManager


class TestVehicleAndAudio(unittest.TestCase):
    def setUp(self):
        self.city_map = CityMap(width=42, height=42)
        self.camera = Camera(x=12.5, y=6.5)
        self.vehicle = Vehicle(x=12.5, y=7.0, vtype=VehicleType.POLICE, heading_dir=(0, 1))
        self.vehicle_ctrl = VehicleController()
        self.cockpit_hud = CockpitHUD()
        self.buffer = ScreenBuffer(80, 32)
        self.soundscape = SoundscapeManager(enabled=True)

    def tearDown(self):
        self.soundscape.cleanup()

    def test_vehicle_mount_and_exit(self):
        self.assertFalse(self.vehicle_ctrl.is_driving)
        
        # Mount vehicle
        mounted = self.vehicle_ctrl.try_enter_nearest_vehicle(self.camera, [self.vehicle])
        self.assertIsNotNone(mounted)
        self.assertTrue(self.vehicle_ctrl.is_driving)
        self.assertEqual(self.vehicle_ctrl.current_vehicle, self.vehicle)
        self.assertEqual(self.camera.pos.x, self.vehicle.x)
        self.assertEqual(self.camera.pos.y, self.vehicle.y)
        self.assertAlmostEqual(self.camera.eye_m, Camera.SEATED_EYE_M)

        # Exit vehicle
        self.vehicle_ctrl.exit_vehicle(self.camera)
        self.assertFalse(self.vehicle_ctrl.is_driving)
        self.assertIsNone(self.vehicle_ctrl.current_vehicle)
        self.assertAlmostEqual(self.camera.eye_m, Camera.EYE_HEIGHT_M)

    def test_driving_physics_acceleration_and_steering(self):
        self.vehicle_ctrl.enter_vehicle(self.vehicle, self.camera)
        self.assertEqual(self.vehicle_ctrl.speed, 0.0)

        # Accelerate forward
        self.vehicle_ctrl.update_physics(
            dt=0.2,
            throttle=1.0,
            steer_input=0.5,
            camera=self.camera,
            city_map=self.city_map,
            other_vehicles=[]
        )
        self.assertGreater(self.vehicle_ctrl.speed, 0.0)
        self.assertGreater(self.vehicle_ctrl.rpm, 900.0)
        self.assertGreater(self.vehicle_ctrl.steering_angle, 0.0)
        self.assertEqual(self.vehicle_ctrl.gear, "D")

        # Brake and switch to reverse
        for _ in range(5):
            self.vehicle_ctrl.update_physics(
                dt=0.2,
                throttle=-1.0,
                steer_input=0.0,
                camera=self.camera,
                city_map=self.city_map,
                other_vehicles=[]
            )
        self.assertLessEqual(self.vehicle_ctrl.speed, 0.0)

    def test_driving_wall_collision(self):
        self.vehicle_ctrl.enter_vehicle(self.vehicle, self.camera)
        # Place vehicle directly in front of solid wall building
        self.vehicle.x = 2.5
        self.vehicle.y = 2.5
        self.vehicle_ctrl.heading_angle = math.pi  # facing West into perimeter wall
        self.vehicle_ctrl.speed = 5.0

        collided = self.vehicle_ctrl.update_physics(
            dt=0.1,
            throttle=1.0,
            steer_input=0.0,
            camera=self.camera,
            city_map=self.city_map,
            other_vehicles=[]
        )
        # Should detect wall collision and rebound
        self.assertTrue(collided)
        self.assertLess(self.vehicle_ctrl.speed, 0.0)

    def test_cockpit_hud_rendering(self):
        self.vehicle_ctrl.enter_vehicle(self.vehicle, self.camera)
        self.vehicle_ctrl.speed = 5.0
        self.vehicle_ctrl.steering_angle = -0.5  # turning left

        self.cockpit_hud.update(0.1, is_raining=True)
        self.cockpit_hud.render(self.vehicle_ctrl, self.buffer, is_raining=True)

        # Check that dashboard characters and instruments are rendered on bottom rows
        dash_text = "".join(p.char for p in self.buffer.pixels[self.buffer.height - 3])
        self.assertTrue("SPEED" in dash_text or "LEFT" in dash_text or "POLICE" in dash_text)

    def test_soundscape_synthesizer(self):
        self.assertIn("horn", self.soundscape.sound_cache)
        self.assertIn("thunder", self.soundscape.sound_cache)
        self.assertIn("chime", self.soundscape.sound_cache)
        self.assertIn("rev", self.soundscape.sound_cache)
        self.assertIn("thud", self.soundscape.sound_cache)

        # Test mute toggle
        self.soundscape.is_muted = False
        unmuted = self.soundscape.toggle_mute()
        self.assertFalse(unmuted)
        self.assertTrue(self.soundscape.is_muted)


if __name__ == "__main__":
    unittest.main()
