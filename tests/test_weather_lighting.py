"""
Unit tests for Advanced Weather Simulation, Atmospheric FX, Lightning Flash & Dynamic Lighting.
Author: Valerie Sterling ⚡ (3D Raycaster & Rasterization Specialist)
"""

import math
import unittest
from src.engine.camera import Camera
from src.engine.raycaster import Raycaster
from src.world.city_map import CityMap
from src.world.day_night import DayNightCycle
from src.world.weather import WeatherSystem, WeatherType, WeatherParticle, LightningState
from src.renderer.screen_buffer import ScreenBuffer
from src.renderer.hud import HUD


class TestWeatherAndLighting(unittest.TestCase):
    def setUp(self):
        self.city_map = CityMap(width=42, height=42)
        self.camera = Camera(x=12.5, y=6.5)
        self.camera.set_direction(math.pi / 2.0)
        self.day_night = DayNightCycle(start_hour=23.0)
        self.weather = WeatherSystem(weather=WeatherType.CLEAR)
        self.raycaster = Raycaster(screen_w=80, screen_h=32)
        self.buffer = ScreenBuffer(80, 32)
        self.hud = HUD(show_minimap=True)

    def test_weather_particle_physics_and_wrapping(self):
        particle = WeatherParticle(80, 32, WeatherType.RAIN)
        initial_y = particle.y
        particle.update(dt=0.1, screen_w=80, screen_h=32, wind_x=5.0)
        self.assertGreater(particle.y, initial_y)

        # Force particle beyond screen bottom to test wrap
        particle.y = 35.0
        particle.update(dt=0.01, screen_w=80, screen_h=32, wind_x=0.0)
        self.assertLessEqual(particle.y, 1.0)

    def test_weather_cycle_transitions(self):
        w = WeatherSystem(weather=WeatherType.CLEAR)
        self.assertEqual(w.current_weather, WeatherType.CLEAR)
        self.assertEqual(len(w.particles), 0)

        w.cycle_weather(80, 32)
        self.assertEqual(w.current_weather, WeatherType.RAIN)
        self.assertGreater(len(w.particles), 0)

        w.cycle_weather(80, 32)
        self.assertEqual(w.current_weather, WeatherType.STORM)

        w.cycle_weather(80, 32)
        self.assertEqual(w.current_weather, WeatherType.FOGGY)

        w.cycle_weather(80, 32)
        self.assertEqual(w.current_weather, WeatherType.SNOW)

        w.cycle_weather(80, 32)
        self.assertEqual(w.current_weather, WeatherType.ACID_RAIN)

        w.cycle_weather(80, 32)
        self.assertEqual(w.current_weather, WeatherType.CLEAR)

    def test_lightning_simulation(self):
        lightning = LightningState()
        self.assertFalse(lightning.active)
        self.assertEqual(lightning.intensity, 0.0)

        lightning.trigger()
        self.assertTrue(lightning.active)
        self.assertGreater(lightning.intensity, 0.5)

        # Update through flash decay
        lightning.update(0.1)
        self.assertTrue(lightning.active)
        
        lightning.update(0.4)
        self.assertFalse(lightning.active)
        self.assertEqual(lightning.intensity, 0.0)

    def test_wetness_accumulation_and_drying(self):
        w = WeatherSystem(weather=WeatherType.RAIN)
        self.assertEqual(w.wetness, 0.0)

        # Simulate 2 seconds of rain
        w.update(dt=2.0, screen_w=80, screen_h=32)
        self.assertGreater(w.wetness, 0.2)

        # Switch to clear and simulate drying
        wet_before = w.wetness
        w.set_weather(WeatherType.CLEAR)
        w.update(dt=2.0, screen_w=80, screen_h=32)
        self.assertLess(w.wetness, wet_before)

    def test_rendering_with_weather_and_fog(self):
        self.weather.set_weather(WeatherType.FOGGY)
        self.weather.fog_density = 0.15

        self.raycaster.render(
            camera=self.camera,
            city_map=self.city_map,
            sprites=[],
            day_night=self.day_night,
            buffer=self.buffer,
            weather=self.weather,
            flashlight_on=False
        )

        # Ensure buffer rendered correctly without exceptions
        non_empty = sum(1 for row in self.buffer.pixels for p in row if p.char != ' ')
        self.assertGreater(non_empty, 100)

    def test_rendering_with_storm_lightning(self):
        self.weather.set_weather(WeatherType.STORM)
        self.weather.trigger_lightning()
        self.assertTrue(self.weather.is_lightning_active())

        self.raycaster.render(
            camera=self.camera,
            city_map=self.city_map,
            sprites=[],
            day_night=self.day_night,
            buffer=self.buffer,
            weather=self.weather,
            flashlight_on=False
        )
        self.assertGreater(self.weather.get_lightning_intensity(), 0.0)

    def test_rendering_with_tactical_flashlight(self):
        self.raycaster.render(
            camera=self.camera,
            city_map=self.city_map,
            sprites=[],
            day_night=self.day_night,
            buffer=self.buffer,
            weather=self.weather,
            flashlight_on=True
        )
        # Should render smoothly with tactical spotlight beam
        self.assertEqual(len(self.raycaster.z_buffer), 80)

    def test_hud_flashlight_and_weather_rendering(self):
        self.hud.toggle_flashlight()
        self.assertTrue(self.hud.flashlight_on)
        self.hud.update(0.1, self.weather)

        self.hud.render(
            camera=self.camera,
            city_map=self.city_map,
            sprites=[],
            day_night=self.day_night,
            weather=self.weather,
            fps=30.0,
            buffer=self.buffer
        )
        # Check that top bar & bottom bar strings were drawn
        self.assertTrue(any("ASTRA 3D" in "".join(p.char for p in row) for row in self.buffer.pixels))


if __name__ == "__main__":
    unittest.main()
