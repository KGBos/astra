"""
Mathematical primitives and 3D projection utilities for Astra 3D Engine.
"""

import math
from typing import Tuple, NamedTuple


class Vector2:
    __slots__ = ('x', 'y')

    def __init__(self, x: float = 0.0, y: float = 0.0):
        self.x = float(x)
        self.y = float(y)

    def __add__(self, other: 'Vector2') -> 'Vector2':
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: 'Vector2') -> 'Vector2':
        return Vector2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> 'Vector2':
        return Vector2(self.x * scalar, self.y * scalar)

    def __rmul__(self, scalar: float) -> 'Vector2':
        return Vector2(self.x * scalar, self.y * scalar)

    def __truediv__(self, scalar: float) -> 'Vector2':
        if scalar == 0:
            return Vector2(0.0, 0.0)
        return Vector2(self.x / scalar, self.y / scalar)

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def length_sq(self) -> float:
        return self.x * self.x + self.y * self.y

    def normalized(self) -> 'Vector2':
        l = self.length()
        if l == 0.0:
            return Vector2(0.0, 0.0)
        return Vector2(self.x / l, self.y / l)

    def dot(self, other: 'Vector2') -> float:
        return self.x * other.x + self.y * other.y

    def distance_to(self, other: 'Vector2') -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def rotated(self, angle_rad: float) -> 'Vector2':
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        return Vector2(
            self.x * cos_a - self.y * sin_a,
            self.x * sin_a + self.y * cos_a
        )

    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def __repr__(self) -> str:
        return f"Vector2({self.x:.3f}, {self.y:.3f})"


class RayHit(NamedTuple):
    hit: bool
    map_x: int
    map_y: int
    side: int             # 0 for East/West wall (X-side), 1 for North/South wall (Y-side)
    perp_wall_dist: float
    wall_x: float         # exact hit coordinate along wall surface [0.0, 1.0]
    wall_type: int
    wall_height: float
    ray_dir_x: float
    ray_dir_y: float
    is_far: bool = False  # True when resolved by the coarse far-skyline tier


def clamp(val: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(val, max_val))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def rad_to_deg(rad: float) -> float:
    return (math.degrees(rad) + 360.0) % 360.0


def deg_to_rad(deg: float) -> float:
    return math.radians(deg)


def get_compass_bearing(dir_x: float, dir_y: float) -> str:
    """Returns 8-point compass bearing from 2D direction vector."""
    angle = math.atan2(dir_y, dir_x)
    deg = rad_to_deg(angle)
    # 0 = East (+X), 90 = South (+Y), 180 = West (-X), 270 = North (-Y)
    # Standard navigation: North is -Y in 2D top-down grid
    headings = ["E", "SE", "S", "SW", "W", "NW", "N", "NE"]
    idx = int((deg + 22.5) / 45.0) % 8
    return headings[idx]
