#!/usr/bin/env python3
"""
Rendered-frame snapshot capture for Astra 3D (visual QA for the Rendering-2.0
pipeline). Drives the real Raycaster headless across scenario matrix cells
(time of day x weather x headlights) and writes raw ANSI files that can be
`cat`-ed inside a terminal to eyeball gamma shading, light pools, wet-road
reflections, clouds/moon, vignette and bloom without launching the game.

Usage:
    python3 tools/render_snapshots.py               # writes ./snapshots/*.ans
    python3 tools/render_snapshots.py --dir /tmp/s  # custom output dir
    cat snapshots/night-lamps.ans                   # view
"""

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.engine.camera import Camera
from src.engine.raycaster import Raycaster
from src.world.city_map import CityMap
from src.world.day_night import DayNightCycle
from src.world.weather import WeatherSystem, WeatherType
from src.renderer.screen_buffer import ScreenBuffer
from src.entities.sprite import make_streetlamp_sprite, make_neon_signpost_sprite

W, H = 120, 40

SCENARIOS = (
    ("noon-clear", 12.0, None, False),
    ("sunset-clouds", 18.5, None, False),
    ("dusk-fog", 19.5, WeatherType.FOGGY, False),
    ("night-lamps", 23.0, None, False),
    ("night-beams", 23.0, None, True),
    ("rain-night", 23.2, WeatherType.RAIN, False),
)


def capture(name: str, hour: float, weather_type, headlights: bool, out_dir: str):
    """Renders one scenario cell and writes its ANSI frame to out_dir."""
    city_map = CityMap(width=96, height=96, seed=5)
    sx, sy = city_map.spawn_pos
    camera = Camera(x=sx, y=sy, fov_deg=70.0)
    camera.set_direction(math.pi / 2.0)
    camera.headlights_on = headlights

    day_night = DayNightCycle(start_hour=hour)
    weather = WeatherSystem(weather=weather_type) if weather_type else None
    if weather_type is WeatherType.RAIN and weather is not None:
        weather.wetness = 0.9

    # A lamp and a neon sign placed ahead of the spawn so night scenes have
    # guaranteed emissive sources in frame.
    sprites = [
        make_streetlamp_sprite(sx + 1.5, sy + 7.0),
        make_neon_signpost_sprite(sx - 1.0, sy + 10.0),
    ]

    buffer = ScreenBuffer(W, H)
    raycaster = Raycaster(W, H)
    raycaster.render(camera=camera, city_map=city_map, sprites=sprites,
                     day_night=day_night, buffer=buffer,
                     weather=weather, flashlight_on=False)

    frame = buffer.render_to_ansi()
    path = os.path.join(out_dir, f"{name}.ans")
    with open(path, "w") as fh:
        fh.write(frame + "\n")
    print(f"wrote {path}")


def main():
    """Captures the full scenario matrix into the output directory."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="snapshots")
    args = parser.parse_args()

    os.makedirs(args.dir, exist_ok=True)
    for name, hour, weather, beams in SCENARIOS:
        capture(name, hour, weather, beams, args.dir)


if __name__ == "__main__":
    main()
