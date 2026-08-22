"""
Sound Effects, Radio Stations, and Equalizer Visualizer for Astra 3D.
Runs purely with terminal acoustic pulses, audio status cues, and procedural radio channels.
"""

import sys
import time
import math
import random
from typing import List, Optional


class RadioStation:
    def __init__(self, freq: str, name: str, genre: str, tracklist: List[str]):
        self.freq = freq
        self.name = name
        self.genre = genre
        self.tracklist = tracklist
        self.current_track_idx = 0
        self.track_timer = 0.0
        self.track_duration = 25.0

    def update(self, dt: float):
        self.track_timer += dt
        if self.track_timer >= self.track_duration:
            self.track_timer = 0.0
            self.current_track_idx = (self.current_track_idx + 1) % len(self.tracklist)

    def get_now_playing(self) -> str:
        return self.tracklist[self.current_track_idx]


class SoundSystem:
    def __init__(self):
        self.sound_enabled = True
        self.radio_enabled = True
        self.current_station_idx = 0
        self.eq_anim_timer = 0.0

        self.stations: List[RadioStation] = [
            RadioStation(
                "98.4 FM",
                "ASTRA RETROWAVE",
                "Synthwave / Cyberpunk",
                [
                    "Midnight Overdrive — Neon Highway",
                    "Laser Grid Horizon — CyberVance",
                    "Metropolis Dreams — 80s Skyline",
                    "Tokyo Drift 2099 — Synth Core"
                ]
            ),
            RadioStation(
                "104.2 FM",
                "CYBERPUNK BEATS",
                "Dark Electro / Industrial",
                [
                    "Neural Uplink — Glitch Mob",
                    "Subway Bass Pulse — District 4",
                    "Neon Shadow — Hacker Groove",
                    "Matrix Collision — Overclocked"
                ]
            ),
            RadioStation(
                "88.9 FM",
                "METRO JAZZ NOCTURNE",
                "Lofi / Smooth City Jazz",
                [
                    "Raindrops on Asphalt — Blue Note",
                    "Late Night Diner — Coffee & Sax",
                    "Streetlamp Solitude — Midnight Trio",
                    "Brownstone Balcony — Acoustic Vibes"
                ]
            ),
            RadioStation(
                "92.5 FM",
                "METROPOLIS NEWS & POLICE RADAR",
                "Live Radio Broadcast",
                [
                    "Traffic Alert: 2nd Avenue Clear",
                    "Weather Report: Night Rain Expected",
                    "City Mayor: Central Plaza Renovation",
                    "Scanner: Patrol Active in Downtown"
                ]
            )
        ]

    def play_beep(self):
        """Emits a short acoustic terminal bell pulse."""
        if self.sound_enabled:
            try:
                sys.stdout.write('\a')
                sys.stdout.flush()
            except Exception:
                pass

    def next_station(self) -> RadioStation:
        self.current_station_idx = (self.current_station_idx + 1) % len(self.stations)
        return self.stations[self.current_station_idx]

    def get_current_station(self) -> RadioStation:
        return self.stations[self.current_station_idx]

    def update(self, dt: float):
        self.eq_anim_timer += dt * 6.0
        for s in self.stations:
            s.update(dt)

    def get_eq_visualizer(self, bars: int = 6) -> str:
        """Returns animated ASCII audio equalizer bars e.g. ' ▃▅█▅▃'."""
        eq_chars = [' ', '▂', '▃', '▄', '▅', '▆', '▇', '█']
        out = []
        for i in range(bars):
            val = (math.sin(self.eq_anim_timer + i * 1.3) + 1.0) / 2.0
            idx = int(val * (len(eq_chars) - 1))
            out.append(eq_chars[idx])
        return "".join(out)
