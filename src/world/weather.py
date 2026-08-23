"""
Advanced Weather Simulation, Atmospheric FX, Lightning Flash & Wet Surface System for Astra 3D.
Author: Valerie Sterling ⚡ (3D Raycaster & Rasterization Specialist)
"""

import math
import random
from enum import Enum
from typing import List, Tuple, Optional


class WeatherType(Enum):
    CLEAR = "CLEAR"
    RAIN = "RAIN"
    STORM = "STORM"
    FOGGY = "FOGGY"
    SNOW = "SNOW"
    ACID_RAIN = "ACID_RAIN"


class WeatherParticle:
    __slots__ = ('x', 'y', 'speed_y', 'char', 'fg_color', 'sway_phase', 'sway_speed')

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        weather_type: WeatherType,
        custom_char: Optional[str] = None
    ):
        self.x = float(random.randint(0, max(1, screen_w - 1)))
        self.y = float(random.uniform(0, max(1, screen_h - 1)))
        self.sway_phase = random.uniform(0, math.pi * 2.0)
        self.sway_speed = random.uniform(2.0, 5.0)

        if weather_type in (WeatherType.RAIN, WeatherType.STORM):
            self.speed_y = random.uniform(22.0, 42.0)
            self.char = custom_char or random.choice(['│', '|', '/', ':', '.'])
            self.fg_color = (160, 200, 255) if weather_type == WeatherType.RAIN else (140, 180, 240)
        elif weather_type == WeatherType.ACID_RAIN:
            self.speed_y = random.uniform(20.0, 38.0)
            self.char = custom_char or random.choice(['│', '!', ':', '`'])
            self.fg_color = (120, 255, 140)
        elif weather_type == WeatherType.SNOW:
            self.speed_y = random.uniform(3.5, 9.0)
            self.char = custom_char or random.choice(['*', '·', '•', '°', '+'])
            self.fg_color = (230, 240, 255)
        else:  # FOGGY / CLEAR
            self.speed_y = random.uniform(1.0, 3.0)
            self.char = '·'
            self.fg_color = (140, 150, 160)

    def update(self, dt: float, screen_w: int, screen_h: int, wind_x: float):
        self.y += self.speed_y * dt
        self.sway_phase += self.sway_speed * dt
        sway_offset = math.sin(self.sway_phase) * 1.5
        self.x += (wind_x + sway_offset) * dt

        # Wrap around screen edges
        if self.y >= screen_h:
            self.y = 0.0
            self.x = float(random.randint(0, max(1, screen_w - 1)))
        elif self.y < 0:
            self.y = float(screen_h - 1)

        if self.x >= screen_w:
            self.x = self.x % screen_w
        elif self.x < 0:
            self.x = (self.x % screen_w + screen_w) % screen_w


class LightningState:
    """Multi-phase realistic lightning flash simulation."""
    def __init__(self):
        self.active = False
        self.timer = 0.0
        self.intensity = 0.0
        self.flash_color: Tuple[int, int, int] = (255, 255, 255)
        self.thunder_timer = 0.0
        self.thunder_event = False

    def trigger(self):
        self.active = True
        self.timer = 0.45  # total flash duration
        self.intensity = 1.0
        # Electric cyan-white flash
        self.flash_color = random.choice([
            (255, 255, 255),
            (210, 240, 255),
            (200, 220, 255),
            (230, 255, 245),
        ])
        # Thunder occurs with sound delay based on simulated distance
        self.thunder_timer = random.uniform(0.3, 1.2)
        self.thunder_event = False

    def update(self, dt: float):
        if self.thunder_timer > 0.0:
            self.thunder_timer -= dt
            if self.thunder_timer <= 0.0:
                self.thunder_event = True

        if not self.active:
            self.intensity = 0.0
            return

        self.timer -= dt
        if self.timer <= 0.0:
            self.active = False
            self.intensity = 0.0
        else:
            # Multi-phase strobe curve
            t = self.timer
            if t > 0.35:
                # Initial leader strike spike
                self.intensity = 1.0
            elif t > 0.28:
                # Brief dip
                self.intensity = 0.25
            elif t > 0.15:
                # Secondary return stroke
                self.intensity = 0.85
            else:
                # Exponential decay afterglow
                self.intensity = max(0.0, (t / 0.15) * 0.5)


class WeatherSystem:
    def __init__(
        self,
        weather: WeatherType = WeatherType.CLEAR,
        particle_count: int = 60
    ):
        self.current_weather = weather
        self.particles: List[WeatherParticle] = []
        self.particle_count = particle_count
        
        # Wind simulation (positive = blowing right, negative = blowing left)
        self.wind_x = 4.0
        self.wind_target = 4.0
        self.wind_change_timer = 5.0

        # Wet asphalt and puddles [0.0 = bone dry, 1.0 = soaked mirror puddles]
        self.wetness = 0.0

        # Lightning engine
        self.lightning = LightningState()
        self.lightning_cooldown = random.uniform(4.0, 10.0)

        # Fog parameters
        self.fog_density = 0.0
        self.fog_target_density = 0.0
        self.fog_color = (130, 140, 160)

        self._apply_weather_settings(weather, 80, 32)

    def _apply_weather_settings(self, weather: WeatherType, screen_w: int, screen_h: int):
        self.current_weather = weather
        if weather == WeatherType.CLEAR:
            self.particles.clear()
            self.fog_target_density = 0.01
            self.wind_target = random.uniform(-2.0, 2.0)
        elif weather == WeatherType.RAIN:
            count = self.particle_count
            self.particles = [WeatherParticle(screen_w, screen_h, WeatherType.RAIN) for _ in range(count)]
            self.fog_target_density = 0.04
            self.fog_color = (80, 90, 110)
            self.wind_target = random.uniform(-8.0, 8.0)
        elif weather == WeatherType.STORM:
            count = int(self.particle_count * 1.5)
            self.particles = [WeatherParticle(screen_w, screen_h, WeatherType.STORM) for _ in range(count)]
            self.fog_target_density = 0.07
            self.fog_color = (40, 45, 65)
            self.wind_target = random.choice([-16.0, 16.0])
            self.lightning_cooldown = random.uniform(2.0, 5.0)
        elif weather == WeatherType.FOGGY:
            count = int(self.particle_count * 0.4)
            self.particles = [WeatherParticle(screen_w, screen_h, WeatherType.FOGGY) for _ in range(count)]
            self.fog_target_density = 0.12
            self.fog_color = (160, 170, 190)
            self.wind_target = random.uniform(-1.0, 1.0)
        elif weather == WeatherType.SNOW:
            count = int(self.particle_count * 1.2)
            self.particles = [WeatherParticle(screen_w, screen_h, WeatherType.SNOW) for _ in range(count)]
            self.fog_target_density = 0.05
            self.fog_color = (180, 190, 210)
            self.wind_target = random.uniform(-4.0, 4.0)
        elif weather == WeatherType.ACID_RAIN:
            count = self.particle_count
            self.particles = [WeatherParticle(screen_w, screen_h, WeatherType.ACID_RAIN) for _ in range(count)]
            self.fog_target_density = 0.06
            self.fog_color = (60, 90, 60)
            self.wind_target = random.uniform(-6.0, 6.0)

    def set_weather(self, weather: WeatherType, screen_w: int = 80, screen_h: int = 32):
        self._apply_weather_settings(weather, screen_w, screen_h)

    def cycle_weather(self, screen_w: int = 80, screen_h: int = 32) -> WeatherType:
        order = [
            WeatherType.CLEAR,
            WeatherType.RAIN,
            WeatherType.STORM,
            WeatherType.FOGGY,
            WeatherType.SNOW,
            WeatherType.ACID_RAIN
        ]
        curr_idx = order.index(self.current_weather)
        next_weather = order[(curr_idx + 1) % len(order)]
        self.set_weather(next_weather, screen_w, screen_h)
        return next_weather

    def toggle_weather(self, screen_w: int = 80, screen_h: int = 32):
        """Backward compatible toggle."""
        self.cycle_weather(screen_w, screen_h)

    def trigger_lightning(self):
        """Force a lightning flash."""
        self.lightning.trigger()

    def update(self, dt: float, screen_w: int, screen_h: int):
        # 1. Update Wind Dynamics
        self.wind_change_timer -= dt
        if self.wind_change_timer <= 0.0:
            self.wind_change_timer = random.uniform(4.0, 9.0)
            if self.current_weather == WeatherType.STORM:
                self.wind_target = random.uniform(-18.0, 18.0)
            else:
                self.wind_target = random.uniform(-6.0, 6.0)

        # Smooth wind transition
        self.wind_x += (self.wind_target - self.wind_x) * min(1.0, dt * 1.5)

        # 2. Update Fog Density Transition
        self.fog_density += (self.fog_target_density - self.fog_density) * min(1.0, dt * 1.0)

        # 3. Update Wetness State
        if self.current_weather in (WeatherType.RAIN, WeatherType.STORM, WeatherType.ACID_RAIN):
            rain_rate = 0.25 if self.current_weather == WeatherType.STORM else 0.15
            self.wetness = min(1.0, self.wetness + dt * rain_rate)
        elif self.current_weather == WeatherType.SNOW:
            self.wetness = min(0.6, self.wetness + dt * 0.05)
        else:
            # Drying in clear or foggy weather
            dry_rate = 0.04
            self.wetness = max(0.0, self.wetness - dt * dry_rate)

        # 4. Update Lightning in Storm Mode
        self.lightning.update(dt)
        if self.current_weather == WeatherType.STORM:
            self.lightning_cooldown -= dt
            if self.lightning_cooldown <= 0.0:
                self.lightning.trigger()
                self.lightning_cooldown = random.uniform(3.5, 9.0)

        # 5. Update Particles
        for p in self.particles:
            p.update(dt, screen_w, screen_h, self.wind_x)

    def is_lightning_active(self) -> bool:
        return self.lightning.active

    def get_lightning_intensity(self) -> float:
        return self.lightning.intensity

    def get_lightning_color(self) -> Tuple[int, int, int]:
        return self.lightning.flash_color

    def poll_thunder_event(self) -> bool:
        if self.lightning.thunder_event:
            self.lightning.thunder_event = False
            return True
        return False
