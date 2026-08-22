"""
Day/Night lighting cycle and sky simulation for Astra 3D.
"""

import math
from typing import Tuple


class DayNightCycle:
    def __init__(self, start_hour: float = 22.0, time_speed: float = 0.5):
        # 24-hour clock [0.0, 24.0)
        self.time_of_day = start_hour
        self.time_speed = time_speed  # hours per real second
        self.is_paused = False

    def update(self, dt: float):
        if not self.is_paused:
            self.time_of_day = (self.time_of_day + self.time_speed * dt) % 24.0

    def get_time_string(self) -> str:
        h = int(self.time_of_day)
        m = int((self.time_of_day * 60) % 60)
        phase = self.get_phase_name()
        return f"{h:02d}:{m:02d} {phase}"

    def get_phase_name(self) -> str:
        t = self.time_of_day
        if 5.0 <= t < 8.0:
            return "DAWN"
        elif 8.0 <= t < 17.0:
            return "DAY"
        elif 17.0 <= t < 20.0:
            return "SUNSET"
        elif 20.0 <= t < 23.0:
            return "DUSK"
        else:
            return "NIGHT"

    def get_ambient_light(self) -> float:
        """Returns ambient brightness factor [0.25, 1.0]."""
        # Peak daylight at 13:00 (1.0), darkest at 01:00 (0.28)
        # Cosine curve shifted so peak is at 13
        angle = ((self.time_of_day - 13.0) / 24.0) * (2.0 * math.pi)
        norm = (math.cos(angle) + 1.0) / 2.0  # [0, 1]
        return 0.28 + norm * 0.72

    def get_sky_gradient(self) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
        """Returns (zenith_color, horizon_color) for sky rendering."""
        t = self.time_of_day
        if 8.0 <= t < 17.0:
            # Daytime Sky
            return ((20, 60, 140), (120, 180, 240))
        elif 17.0 <= t < 20.0:
            # Sunset Sky (Hot orange / purple)
            return ((40, 10, 60), (255, 100, 40))
        elif 5.0 <= t < 8.0:
            # Dawn Sky
            return ((30, 20, 70), (220, 140, 90))
        else:
            # Night Sky (Cyberpunk Obsidian / Deep Indigo)
            return ((5, 5, 15), (15, 20, 35))
