"""
Weather simulation and atmospheric particle effects for Astra 3D.
"""

import random
from enum import Enum
from typing import List


class WeatherType(Enum):
    CLEAR = "CLEAR"
    RAIN = "RAIN"
    FOGGY = "FOGGY"


class RainParticle:
    __slots__ = ('x', 'y', 'speed', 'char')

    def __init__(self, screen_w: int, screen_h: int):
        self.x = random.randint(0, screen_w - 1)
        self.y = random.uniform(0, screen_h - 1)
        self.speed = random.uniform(18.0, 35.0)
        self.char = random.choice(['|', '/', ':', '.'])

    def update(self, dt: float, screen_w: int, screen_h: int):
        self.y += self.speed * dt
        self.x = (self.x + int(dt * 5)) % screen_w
        if self.y >= screen_h:
            self.y = 0.0
            self.x = random.randint(0, screen_w - 1)


class WeatherSystem:
    def __init__(self, weather: WeatherType = WeatherType.CLEAR, particle_count: int = 40):
        self.current_weather = weather
        self.particles: List[RainParticle] = []
        self.particle_count = particle_count

    def set_weather(self, weather: WeatherType, screen_w: int = 80, screen_h: int = 30):
        self.current_weather = weather
        if weather == WeatherType.RAIN:
            self.particles = [RainParticle(screen_w, screen_h) for _ in range(self.particle_count)]
        else:
            self.particles.clear()

    def toggle_weather(self, screen_w: int = 80, screen_h: int = 30):
        if self.current_weather == WeatherType.CLEAR:
            self.set_weather(WeatherType.RAIN, screen_w, screen_h)
        elif self.current_weather == WeatherType.RAIN:
            self.set_weather(WeatherType.FOGGY, screen_w, screen_h)
        else:
            self.set_weather(WeatherType.CLEAR, screen_w, screen_h)

    def update(self, dt: float, screen_w: int, screen_h: int):
        if self.current_weather == WeatherType.RAIN:
            for p in self.particles:
                p.update(dt, screen_w, screen_h)
