"""Far-tier skyline layering regression.

The 180 m far tier exists so a distant skyline reads with depth: a taller tower
rising behind a nearer low mass must still be recorded as its own layer. An
unconditional `break` on the first solid far cell defeated that entirely -- the
tier could only ever return a single far hit, so `max_height` never updated and
the height comparison guarding the append was dead code.

Salvaged from Nora Voss's `nora-voss/worktree` (commit 3d4a655..111992b range),
which diagnosed the break correctly. Her wider perspective overhaul on that
branch is NOT adopted -- master's `pixels_per_meter_at_1m` projection supersedes
it and uses the reciprocal CELL_ASPECT convention.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.engine.camera import Camera
from src.engine.raycaster import Raycaster
from src.world.city_map import CityMap


class FarTierLayeringTests(unittest.TestCase):
    def setUp(self):
        self.city = CityMap(seed=4242)
        self.raycaster = Raycaster(160, 50)
        self.camera = Camera(x=1.0, y=1.0, fov_deg=70.0)
        self.camera.pos.x, self.camera.pos.y = self.city.spawn_pos

    def _sweep(self):
        """Far-layer counts across a full yaw sweep of the spawn viewpoint."""
        stacked = 0
        deepest = 0
        for angle in range(0, 360, 3):
            self.camera.set_direction(math.radians(angle))
            for screen_x in range(0, 160, 8):
                layers = self.raycaster._cast_ray_layers(screen_x, self.camera, self.city)
                far = [h for h in layers if getattr(h, "is_far", False)]
                deepest = max(deepest, len(far))
                if len(far) > 1:
                    stacked += 1
        return stacked, deepest

    def test_far_tier_stacks_taller_silhouettes(self):
        stacked, deepest = self._sweep()
        self.assertGreater(
            deepest, 1,
            "far tier returned at most one layer per column -- the skyline "
            "cannot read with depth (regression of the unconditional break)")
        self.assertGreater(
            stacked, 0,
            "no column recorded a taller far mass behind a nearer one")

    def test_far_layers_increase_in_height(self):
        """Within a column, each successive far layer must be strictly taller."""
        for angle in range(0, 360, 7):
            self.camera.set_direction(math.radians(angle))
            for screen_x in range(0, 160, 16):
                layers = self.raycaster._cast_ray_layers(screen_x, self.camera, self.city)
                far = [h for h in layers if getattr(h, "is_far", False)]
                heights = [h.wall_height for h in far]
                for prev, nxt in zip(heights, heights[1:]):
                    self.assertGreater(
                        nxt, prev,
                        f"far layers not monotonically taller at angle={angle} "
                        f"x={screen_x}: {heights}")

    def test_far_layers_respect_max_layers(self):
        """Removing the break must not let a column accumulate unbounded layers."""
        for angle in range(0, 360, 5):
            self.camera.set_direction(math.radians(angle))
            for screen_x in range(0, 160, 8):
                layers = self.raycaster._cast_ray_layers(screen_x, self.camera, self.city)
                near = [h for h in layers if h.hit and not getattr(h, "is_far", False)]
                far = [h for h in layers if getattr(h, "is_far", False)]
                self.assertLessEqual(
                    len(far), self.raycaster.MAX_LAYERS,
                    "far tier exceeded MAX_LAYERS")
                self.assertLessEqual(len(near) + len(far), self.raycaster.MAX_LAYERS + 8,
                                     "layer list grew beyond the near+frame budget")

    def test_far_layers_ordered_by_distance(self):
        """Layers must stay depth-sorted so the painter order downstream holds."""
        for angle in range(0, 360, 11):
            self.camera.set_direction(math.radians(angle))
            for screen_x in range(0, 160, 16):
                layers = self.raycaster._cast_ray_layers(screen_x, self.camera, self.city)
                far = [h for h in layers if getattr(h, "is_far", False)]
                dists = [h.perp_wall_dist for h in far]
                self.assertEqual(dists, sorted(dists),
                                 f"far layers out of depth order: {dists}")


if __name__ == "__main__":
    unittest.main()
