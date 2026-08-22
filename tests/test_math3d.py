"""
Unit tests for mathematical primitives and 3D projection math in Astra 3D.
"""

import math
import unittest
from src.engine.math3d import Vector2, clamp, lerp, rad_to_deg, get_compass_bearing


class TestMath3D(unittest.TestCase):
    def test_vector_operations(self):
        v1 = Vector2(3.0, 4.0)
        self.assertAlmostEqual(v1.length(), 5.0)
        self.assertAlmostEqual(v1.length_sq(), 25.0)

        v_norm = v1.normalized()
        self.assertAlmostEqual(v_norm.length(), 1.0)
        self.assertAlmostEqual(v_norm.x, 0.6)
        self.assertAlmostEqual(v_norm.y, 0.8)

        v2 = Vector2(1.0, 2.0)
        v_add = v1 + v2
        self.assertEqual((v_add.x, v_add.y), (4.0, 6.0))

        v_sub = v1 - v2
        self.assertEqual((v_sub.x, v_sub.y), (2.0, 2.0))

        v_mul = v1 * 2.0
        self.assertEqual((v_mul.x, v_mul.y), (6.0, 8.0))

        v_div = v1 / 2.0
        self.assertEqual((v_div.x, v_div.y), (1.5, 2.0))

    def test_vector_rotation_and_dot(self):
        v = Vector2(1.0, 0.0)
        rotated = v.rotated(math.pi / 2.0)
        self.assertAlmostEqual(rotated.x, 0.0, places=5)
        self.assertAlmostEqual(rotated.y, 1.0, places=5)

        dot = v.dot(Vector2(0.0, 1.0))
        self.assertAlmostEqual(dot, 0.0)

        dot_parallel = v.dot(Vector2(2.0, 0.0))
        self.assertAlmostEqual(dot_parallel, 2.0)

    def test_clamp_and_lerp(self):
        self.assertEqual(clamp(15.0, 0.0, 10.0), 10.0)
        self.assertEqual(clamp(-5.0, 0.0, 10.0), 0.0)
        self.assertEqual(clamp(5.0, 0.0, 10.0), 5.0)

        self.assertAlmostEqual(lerp(10.0, 20.0, 0.5), 15.0)
        self.assertAlmostEqual(lerp(0.0, 100.0, 0.25), 25.0)

    def test_compass_bearing(self):
        self.assertEqual(get_compass_bearing(1.0, 0.0), "E")
        self.assertEqual(get_compass_bearing(0.0, 1.0), "S")
        self.assertEqual(get_compass_bearing(-1.0, 0.0), "W")
        self.assertEqual(get_compass_bearing(0.0, -1.0), "N")


if __name__ == "__main__":
    unittest.main()
