"""
Regression tests for pseudo-volumetric street props: angle-dependent visible
faces, box-corner projection split, side-plane shading, and occlusion.

Author: Nora Voss ⚙️ (OpenCode Platform)
"""

import math
import unittest

from src.engine.camera import Camera
from src.engine.raycaster import Raycaster
from src.engine.tone import get_shade_lut
from src.entities.sprite import VolumetricSprite, make_vending_machine_sprite
from src.world.city_map import CityMap
from src.world.day_night import DayNightCycle
from src.renderer.screen_buffer import ScreenBuffer


GLOW = (90, 220, 255)     # vending machine front window (luminous -> exact)
VENT = (60, 65, 80)       # vending machine side vents (raw art value)
# Rendered side plane: SIDE_SHADE attenuation through the gamma-correct tone
# pipeline (linear-space multiply, sRGB re-encode) -- the honest contract.
_SIDE_LUT = get_shade_lut(VolumetricSprite.SIDE_SHADE)
VENT_DIM = tuple(_SIDE_LUT[c] for c in VENT)


def _render_with_machine(cam_dx, cam_dy):
    """Renders one vending machine viewed from (dx, dy) offset; returns buffer."""
    rc = Raycaster(screen_w=80, screen_h=32)
    city_map = CityMap(width=42, height=42, seed=3)
    city_map.walls = [[0 for _ in range(42)] for _ in range(42)]

    px, py = 21.0, 21.0
    cam = Camera(x=px + cam_dx, y=py + cam_dy)
    cam.set_direction(math.atan2(-cam_dy, -cam_dx))  # look at the machine

    machine = make_vending_machine_sprite(px, py, facing_angle=math.pi / 2.0)
    buf = ScreenBuffer(80, 32)
    rc.render(camera=cam, city_map=city_map, sprites=[machine],
              day_night=DayNightCycle(start_hour=12.0), buffer=buf)
    return buf


def _pixels_matching(buf, rgb, tol=12):
    """Cells whose fg matches `rgb` within `tol`, restricted to 3-runs.

    Sprite faces are solid blocks of palette color; requiring horizontal or
    vertical adjacency filters isolated scenery cells that gamma/vignette
    shading may coincidentally land inside the tolerance window.
    """
    pts = [
        (x, y)
        for y in range(buf.height)
        for x in range(buf.width)
        if buf.pixels[y][x].char != ' ' and p_match(buf.pixels[y][x].fg, rgb, tol)
    ]
    m = set(pts)
    return [(x, y) for (x, y) in pts
            if ((x - 1, y) in m and (x + 1, y) in m)
            or ((x, y - 1) in m and (x, y + 1) in m)]


def p_match(fg, rgb, tol):
    return fg is not None and all(abs(a - b) <= tol for a, b in zip(fg, rgb))


class TestVolumetricFaces(unittest.TestCase):
    def test_front_view_shows_only_front_palette(self):
        """Camera dead-ahead of the facing normal: pure front art, full width."""
        buf = _render_with_machine(0.0, 5.0)
        self.assertTrue(_pixels_matching(buf, GLOW), "front glow missing head-on")
        # No side-plane pixels anywhere when viewed dead-front
        self.assertFalse(_pixels_matching(buf, VENT_DIM, tol=4))

    def test_side_view_shows_only_side_palette(self):
        """Camera at 90 degrees: only the shaded side plane is visible."""
        buf = _render_with_machine(5.0, 0.0)
        self.assertTrue(_pixels_matching(buf, VENT_DIM, tol=4), "side vents missing")
        self.assertFalse(_pixels_matching(buf, GLOW, tol=8))

    def test_corner_view_blends_both_faces(self):
        """45-degree orbit shows both planes simultaneously (close enough to resolve)."""
        buf = _render_with_machine(2.2, 2.2)
        front_px = _pixels_matching(buf, GLOW)
        side_px = _pixels_matching(buf, VENT_DIM, tol=4)
        self.assertTrue(front_px, "front panel missing in corner view")
        self.assertTrue(side_px, "side plane missing in corner view")

    def test_corner_ordering_side_left_of_front(self):
        """With bearing sin < 0 the side plane renders LEFT of the front panel."""
        buf = _render_with_machine(2.2, 2.2)
        side_xs = [x for x, _ in _pixels_matching(buf, VENT_DIM, tol=4)]
        front_xs = [x for x, _ in _pixels_matching(buf, GLOW)]
        self.assertTrue(side_xs and front_xs)
        self.assertLess(max(side_xs), min(front_xs))

    def test_side_plane_is_darker(self):
        """The side face carries SIDE_SHADE attenuation versus the lit front."""
        buf = _render_with_machine(2.2, 2.2)
        self.assertTrue(_pixels_matching(buf, VENT_DIM, tol=4))


class TestVolumetricWorld(unittest.TestCase):
    def test_occlusion_by_wall_in_front(self):
        """A nearer wall hides the machine completely via z-buffer stripes."""
        rc = Raycaster(screen_w=80, screen_h=32)
        city_map = CityMap(width=42, height=42, seed=3)
        city_map.walls = [[0 for _ in range(42)] for _ in range(42)]
        for x in (20, 21, 22):
            city_map.walls[18][x] = 5  # wall between camera (y=16) and machine (y=21)

        cam = Camera(x=21.0, y=16.0)
        cam.set_direction(math.pi / 2.0)
        machine = make_vending_machine_sprite(21.0, 21.0, facing_angle=math.pi / 2.0)
        buf = ScreenBuffer(80, 32)
        rc.render(camera=cam, city_map=city_map, sprites=[machine],
                  day_night=DayNightCycle(start_hour=12.0), buffer=buf)
        self.assertEqual(_pixels_matching(buf, GLOW), [])
        self.assertEqual(_pixels_matching(buf, VENT_DIM, tol=4), [])

    def test_generator_spawns_machines(self):
        """Procedural worlds include vending machines among their props."""
        found = False
        for seed in range(24):
            cm = CityMap(width=42, height=42, seed=seed)
            if any(isinstance(p, VolumetricSprite) and p.name == "VENDING_MACHINE"
                   for p in cm.props):
                found = True
                break
        self.assertTrue(found, "no seed produced a vending machine")


if __name__ == "__main__":
    unittest.main()
