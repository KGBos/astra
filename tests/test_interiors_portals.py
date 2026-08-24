"""
Regression tests for enterable buildings, interior spaces, walk-through
doorway transitions, and live-window portal rendering.

Author: Nora Voss ⚙️ (OpenCode Platform)
"""

import math
import unittest

from src.engine.camera import Camera
from src.engine.raycaster import Raycaster
from src.world.city_map import CityMap
from src.world.day_night import DayNightCycle
from src.world.interiors import (
    CELL_WINDOW,
    CELL_DOOR,
    ENTER_RADIUS,
    InteriorSpace,
    InteriorView,
    detect_doorways,
)
from src.game import Game
from src.renderer.screen_buffer import ScreenBuffer

TOWER_TYPE = 2


class TestDoorwayDetection(unittest.TestCase):
    def test_some_seed_yields_doorways(self):
        found = None
        for seed in range(24):
            cm = CityMap(width=42, height=42, seed=seed)
            if cm.doorways:
                found = cm
                break
        self.assertIsNotNone(found, "no seed produced enterable buildings")

    def test_door_cell_retextured_and_reachable(self):
        cm = None
        for seed in range(24):
            cm = CityMap(width=42, height=42, seed=seed)
            if cm.doorways:
                break
        d = cm.doorways[0]
        ex, ey = d.ext
        self.assertEqual(cm.walls[ey][ex], 13)          # DOORWAY texture id
        neighbors = [(ex + 1, ey), (ex - 1, ey), (ex, ey + 1), (ex, ey - 1)]
        walkable = any(
            0 <= nx < cm.width and 0 <= ny < cm.height
            and cm.walls[ny][nx] == 0 and cm.floors[ny][nx] != 7  # not water
            for nx, ny in neighbors
        )
        self.assertTrue(walkable, "door has no street access")


class TestInteriorSpace(unittest.TestCase):
    def test_room_layout(self):
        cm = next(c for c in (CityMap(width=42, height=42, seed=s) for s in range(24)) if c.doorways)
        d = cm.doorways[0]
        space, view = cm.get_interior(d)

        # Door gap is walkable on the ring
        lx = d.ext[0] - space.x0
        ly = d.ext[1] - space.y0
        lx = max(1, min(space.w - 2, lx))
        ly = max(1, min(space.h - 2, ly))
        self.assertEqual(space.grid[ly][lx], CELL_DOOR)

        # Windows exist somewhere on the ring
        ring = [space.grid[y][x] for y in range(space.h) for x in range(space.w)]
        self.assertIn(CELL_WINDOW, ring)
        self.assertTrue(view.in_interior)

    def test_wrapper_delegates_outside_footprint(self):
        cm = next(c for c in (CityMap(width=42, height=42, seed=s) for s in range(24)) if c.doorways)
        _, view = cm.get_interior(cm.doorways[0])
        probe_x, probe_y = 1.5, 1.5  # corner cell, far from any building
        self.assertEqual(view.is_solid(probe_x, probe_y), cm.is_solid(probe_x, probe_y))
        self.assertEqual(view.get_floor_type(1, 1), cm.get_floor_type(1, 1))


class TestPortalRendering(unittest.TestCase):
    def _portal_scene(self):
        """Hand-built room overlaying a world with a tower north of it."""
        world = CityMap(width=42, height=42, seed=3)
        world.walls = [[0 for _ in range(42)] for _ in range(42)]

        space = InteriorSpace(bld_id=0, bx0=10, by0=12, bw=5, bh=5,
                              doorway=None, seed=1)
        space.grid[0][2] = CELL_WINDOW          # north ring window at cell x=12

        view = InteriorView(space, world)
        return world, space, view

    def test_ray_through_window_carries_win_dist(self):
        world, space, view = self._portal_scene()
        world.walls[6][12] = TOWER_TYPE         # tower seen through the glass

        rc = Raycaster(screen_w=80, screen_h=32)
        cam = Camera(x=12.5, y=14.5)
        cam.set_direction(-math.pi / 2.0)       # face North (-Y) at the window
        layers = rc._cast_ray_layers(40, cam, view, horizon_y=16)

        portals = [h for h in layers if h.win_dist > 0.0]
        self.assertTrue(portals, "no portal layer recorded through the window")
        self.assertFalse(any(h.win_dist == 0.0 and h.hit and not h.is_frame
                             for h in layers),
                         "unexpected occluder between camera and window")
        # Nearest through-glass content is the tower itself
        through = portals[0]
        self.assertEqual(through.wall_type, TOWER_TYPE)
        self.assertGreater(through.perp_wall_dist, through.win_dist)

    def test_window_view_differs_from_walled_window(self):
        """Differential proof: glass shows exterior; solid wall does not."""
        world, space, view = self._portal_scene()
        world.walls[6][12] = TOWER_TYPE

        rc = Raycaster(screen_w=80, screen_h=32)
        cam = Camera(x=12.5, y=14.5)
        cam.set_direction(-math.pi / 2.0)

        day_night = DayNightCycle(start_hour=12.0)
        buf_glass = ScreenBuffer(80, 32)
        rc.render(camera=cam, city_map=view, sprites=[],
                  day_night=day_night, weather=None, buffer=buf_glass)

        # Same room, but the window bricked up: no portal, plain interior wall
        space_walled = InteriorSpace(bld_id=0, bx0=10, by0=12, bw=5, bh=5,
                                     doorway=None, seed=1)
        view_walled = InteriorView(space_walled, world)
        buf_walled = ScreenBuffer(80, 32)
        rc.render(camera=cam, city_map=view_walled, sprites=[],
                  day_night=day_night, weather=None, buffer=buf_walled)

        win_dist = abs(12.0 - cam.pos.y)                # window plane at y=12
        half = int((32 / win_dist) * rc.WINDOW_OPENING)
        w_top, w_bot = int(16 - half), int(16 + half)

        differing_in_span = [
            y for y in range(max(0, w_top), min(31, w_bot) + 1)
            if (buf_glass.pixels[y][40].char, buf_glass.pixels[y][40].fg)
            != (buf_walled.pixels[y][40].char, buf_walled.pixels[y][40].fg)
        ]
        self.assertTrue(differing_in_span,
                        "glass window shows no exterior content")

    def test_window_frame_surrounds_glass_opening(self):
        """Rows above/below the glass span show interior wall, not sky/floor."""
        world, space, view = self._portal_scene()
        world.walls[6][12] = TOWER_TYPE

        rc = Raycaster(screen_w=80, screen_h=32)
        cam = Camera(x=12.5, y=14.5)
        cam.set_direction(-math.pi / 2.0)

        day_night = DayNightCycle(start_hour=12.0)
        buf_glass = ScreenBuffer(80, 32)
        rc.render(camera=cam, city_map=view, sprites=[],
                  day_night=day_night, weather=None, buffer=buf_glass)

        space_walled = InteriorSpace(bld_id=0, bx0=10, by0=12, bw=5, bh=5,
                                     doorway=None, seed=1)
        view_walled = InteriorView(space_walled, world)
        buf_walled = ScreenBuffer(80, 32)
        rc.render(camera=cam, city_map=view_walled, sprites=[],
                  day_night=day_night, weather=None, buffer=buf_walled)

        win_dist = cam.pos.y - 13.0
        w_top = int(16 - (32 / win_dist) * rc.WINDOW_OPENING)
        w_bot = int(16 + (32 / win_dist) * rc.WINDOW_OPENING)

        for y in (w_top - 1, w_top - 2, w_bot + 1, w_bot + 2):
            self.assertEqual(
                (buf_glass.pixels[y][40].char, buf_glass.pixels[y][40].fg,
                 buf_glass.pixels[y][40].bg),
                (buf_walled.pixels[y][40].char, buf_walled.pixels[y][40].fg,
                 buf_walled.pixels[y][40].bg),
                f"window column row {y} leaks sky/floor instead of wall frame"
            )
        mid = (w_top + w_bot) // 2
        self.assertNotEqual(
            (buf_glass.pixels[mid][40].char, buf_glass.pixels[mid][40].fg),
            (buf_walled.pixels[mid][40].char, buf_walled.pixels[mid][40].fg),
            "glass opening no longer shows exterior through the frame"
        )


class TestSpaceTransitions(unittest.TestCase):
    def test_enter_then_exit_building(self):
        g = Game(width=64, height=24)
        cm = g.city_map
        if not cm.doorways:
            for seed in range(24):
                cm = CityMap(width=42, height=42, seed=seed)
                if cm.doorways:
                    g.city_map = cm
                    break
        d = g.city_map.doorways[0]
        ex, ey = d.ext
        ox, oy = ((1, 0), (0, 1), (-1, 0), (0, -1))[d.side]

        # Stand just outside the entrance
        g.camera.pos.x = ex + 0.5 + ox * 0.9
        g.camera.pos.y = ey + 0.5 + oy * 0.9
        g._update_space()
        self.assertIsNotNone(g.interior_view, "did not enter building")
        space = g.interior_view.space
        self.assertTrue(
            space.x0 <= int(g.camera.pos.x) < space.x0 + space.w
            and space.y0 <= int(g.camera.pos.y) < space.y0 + space.h,
            "camera not placed inside footprint"
        )

        # Walk back onto the inner threshold and leave
        wx, wy = space.inner_door_world
        g.camera.pos.x, g.camera.pos.y = wx, wy
        g._update_space()
        self.assertIsNone(g.interior_view, "did not exit building")

    def test_enter_radius_rejects_far_approach(self):
        g = Game(width=64, height=24)
        cm = g.city_map
        if not cm.doorways:
            for seed in range(24):
                cm = CityMap(width=42, height=42, seed=seed)
                if cm.doorways:
                    g.city_map = cm
                    break
        d = g.city_map.doorways[0]
        ex, ey = d.ext
        g.camera.pos.x = ex + 0.5 + ENTER_RADIUS + 3.0
        g.camera.pos.y = ey + 0.5
        g._update_space()
        self.assertIsNone(g.interior_view)

    def test_headless_run_still_works(self):
        g = Game(width=40, height=12, target_fps=240, demo_mode=True)
        import io, contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            g.run(max_frames=10)
        self.assertGreaterEqual(g.total_frames, 10)


if __name__ == "__main__":
    unittest.main()
