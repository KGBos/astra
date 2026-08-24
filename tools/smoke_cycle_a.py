#!/usr/bin/env python3
"""
Cycle A smoke check: render downtown frames at noon and night and assert that
close-by tower slices overflow the top of the screen (tall buildings feel tall
under the honest-metre projection). Run from the repo root:

    python3 tools/smoke_cycle_a.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.engine.camera import Camera
from src.engine.raycaster import Raycaster, pixels_per_meter_at_1m
from src.world.city_map import CityMap
from src.world.day_night import DayNightCycle
from src.renderer.screen_buffer import ScreenBuffer


def _tower_scene(hour: float):
    city = CityMap(width=320, height=320, seed=4242)
    wall_values = {city.walls[y][x]
                   for y in range(city.height) for x in range(city.width)}
    towers = [t for t in wall_values if t > 0 and city.get_wall_height(t) >= 40.0]
    assert towers, "no >=40 m tower textures present in generated city"

    placed = False
    for y in range(8, 313):
        for x in range(2, 318):
            if city.walls[y][x] in towers and all(
                    not city.is_solid(x, yy) and not city.is_water(x, yy)
                    for yy in range(y - 6, y)):
                cam = Camera(x=x + 0.5, y=y - 6.5)
                cam.set_direction(__import__("math").pi / 2.0)
                rc = Raycaster(80, 32)
                buf = ScreenBuffer(80, 32)
                rc.render(camera=cam, city_map=city, sprites=[],
                          day_night=DayNightCycle(start_hour=hour), buffer=buf)
                col = [buf.pixels[yy][40] for yy in range(32)]
                sky = {' ', '.', '*'}
                top = next((yy for yy in range(32) if col[yy].char not in sky), None)
                yield x, y, city.get_wall_height(city.walls[y][x]), top, col
                placed = True
                break
        if placed:
            break


def main():
    ppm = pixels_per_meter_at_1m(80, 32, __import__("math").tan(__import__("math").radians(70.0) / 2.0))
    print(f"projection: {ppm:.2f} rows per metre at 1 m (fov 70, 80x32)")
    failures = 0
    for hour in (12.0, 23.0):
        label = "noon" if hour == 12.0 else "night"
        for tx, ty, height_m, top_row, _col in _tower_scene(hour):
            dist = 6.5
            exp_overflow = height_m > dist + 0  # roofline above eye level always true here
            clipped = top_row == 0
            print(f"[{label}] tower type={height_m:.0f} m at ({tx},{ty}) viewed from "
                  f"{dist:.1f} m -> first painted row = {top_row} "
                  f"({'CLIPS TOP' if clipped else 'does not clip'})")
            if exp_overflow and not clipped:
                failures += 1
    if failures:
        print(f"SMOKE FAILED: {failures} frame(s) failed the overflow assertion")
        sys.exit(1)
    print("SMOKE PASSED: towers overflow the frame top at noon and night")


if __name__ == "__main__":
    main()
