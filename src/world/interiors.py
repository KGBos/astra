"""
Building Interiors, Doorway Detection, and Live-Window Portal support.

An InteriorSpace overlays the exact world-coordinate footprint of its building,
so the player camera crosses the threshold without any remapping. The
InteriorView wrapper implements the same query surface as CityMap (is_solid,
get_wall_type, ...) and is fed ONLY to player-facing systems (raycaster +
camera physics); traffic and pedestrians keep querying the raw world.

Author: Nora Voss ⚙️ (OpenCode Platform)
"""

import random
from typing import Dict, List, Optional, Tuple

from src.world.city_map import FloorType


# Interior grid cell codes
CELL_FLOOR = 0
CELL_WALL = 1
CELL_WINDOW = 2
CELL_DOOR = 3

WALL_TYPE_INTERIOR = 12
WALL_TYPE_DOORWAY = 13

ENTER_RADIUS = 0.95   # distance from exterior door center that triggers entry
EXIT_RADIUS = 0.60    # distance from interior door center that triggers exit


class Doorway:
    __slots__ = ('bld_id', 'ext', 'inner', 'side')

    def __init__(self, bld_id: int, ext: Tuple[int, int], inner: Tuple[int, int], side: int):
        self.bld_id = bld_id
        self.ext = ext        # exterior wall cell containing the door
        self.inner = inner    # matching walkable cell on the interior ring
        self.side = side      # 0=E,1=S,2=W,3=N (direction from door toward road)


class InteriorSpace:
    """Walkable room filling a building footprint; ring walls carry windows."""

    def __init__(self, bld_id: int, bx0: int, by0: int, bw: int, bh: int,
                 doorway: Optional[Doorway], seed: int):
        self.bld_id = bld_id
        self.x0 = bx0
        self.y0 = by0
        self.w = bw
        self.h = bh
        self.doorway = doorway

        rng = random.Random(seed * 7919 + bld_id)
        grid = [[CELL_WALL for _ in range(bw)] for _ in range(bh)]

        # Carve walkable core (everything inside the outer ring)
        for y in range(1, bh - 1):
            for x in range(1, bw - 1):
                grid[y][x] = CELL_FLOOR

        # Door gap on the ring, aligned with the exterior door
        dx = bw // 2
        dy = bh - 1
        if doorway is not None:
            dx = max(1, min(bw - 2, doorway.ext[0] - bx0))
            dy = max(1, min(bh - 2, doorway.ext[1] - by0))
        grid[dy][dx] = CELL_DOOR

        # Windows every other remaining ring cell (never beside the door)
        for y in range(bh):
            for x in range(bw):
                if grid[y][x] != CELL_WALL:
                    continue
                on_ring = (x in (0, bw - 1)) or (y in (0, bh - 1))
                if not on_ring:
                    continue
                near_door = abs(x - dx) + abs(y - dy) <= 2
                if not near_door and rng.random() < 0.62:
                    grid[y][x] = CELL_WINDOW

        self.grid = grid
        # World-space center of the inner door threshold (walkable)
        self.inner_door_world = (bx0 + dx + 0.5, by0 + dy + 0.5)

    def code_at(self, ix: int, iy: int) -> Optional[int]:
        lx = ix - self.x0
        ly = iy - self.y0
        if 0 <= lx < self.w and 0 <= ly < self.h:
            return self.grid[ly][lx]
        return None


class InteriorView:
    """
    Duck-typed CityMap substitute for player-facing queries while indoors.
    Falls through to the real world for anything outside the footprint, which
    is what makes live-window portals work: rays leaving the room see the city.
    """

    def __init__(self, space: InteriorSpace, world):
        self.space = space
        self.world = world
        self.in_interior = True

    # ---- geometry queries used by Camera + Raycaster ----
    def is_solid(self, fx: float, fy: float) -> bool:
        code = self.space.code_at(int(fx), int(fy))
        if code is None:
            return self.world.is_solid(fx, fy)
        return code in (CELL_WALL, CELL_WINDOW)

    def get_wall_type(self, x: int, y: int) -> int:
        code = self.space.code_at(x, y)
        if code is None:
            return self.world.get_wall_type(x, y)
        if code == CELL_WINDOW:
            return WALL_TYPE_INTERIOR
        if code == CELL_DOOR:
            return WALL_TYPE_DOORWAY
        return WALL_TYPE_INTERIOR

    def get_wall_height(self, wall_type: int) -> float:
        return self.world.get_wall_height(wall_type)

    def get_floor_type(self, x: int, y: int) -> int:
        code = self.space.code_at(int(x), int(y))
        if code is None:
            return self.world.get_floor_type(x, y)
        return FloorType.WOOD_DECK

    def is_water(self, x: float, y: float) -> bool:
        return False

    # ---- portal helpers ----
    def is_window_cell(self, ix: int, iy: int) -> bool:
        return self.space.code_at(ix, iy) == CELL_WINDOW


def detect_doorways(world, max_doors: int = 8) -> List[Doorway]:
    """
    Deterministically picks enterable buildings: connected wall masses with a
    perimeter cell adjacent to walkable ground. Returns one Doorway each.
    """
    w = world.width
    h = world.height
    walls = world.walls
    visited = [[False] * w for _ in range(h)]
    doorways: List[Doorway] = []

    def walkable(ix, iy):
        return (0 <= ix < w and 0 <= iy < h
                and walls[iy][ix] == 0
                and world.get_floor_type(ix, iy) != FloorType.WATER)

    for sy in range(1, h - 1):
        if len(doorways) >= max_doors:
            break
        for sx in range(1, w - 1):
            if len(doorways) >= max_doors:
                break
            if visited[sy][sx] or walls[sy][sx] == 0:
                continue

            # Flood-fill this wall mass
            stack = [(sx, sy)]
            mass: List[Tuple[int, int]] = []
            visited[sy][sx] = True
            while stack:
                cx, cy = stack.pop()
                mass.append((cx, cy))
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx] and walls[ny][nx] != 0:
                        visited[ny][nx] = True
                        stack.append((nx, ny))

            if not (6 <= len(mass) <= 90):
                continue
            xs = [p[0] for p in mass]
            ys = [p[1] for p in mass]
            bx0, bx1 = min(xs), max(xs)
            by0, by1 = min(ys), max(ys)
            if bx1 - bx0 < 2 or by1 - by0 < 2:
                continue

            # First perimeter cell (scan order => deterministic) with street access
            door = None
            side = 0
            for cy in range(by0, by1 + 1):
                for cx in range(bx0, bx1 + 1):
                    if walls[cy][cx] == 0 or (cx, cy) not in set(mass):
                        continue
                    for sidx, (ox, oy) in enumerate(((1, 0), (0, 1), (-1, 0), (0, -1))):
                        if walkable(cx + ox, cy + oy):
                            door = (cx, cy)
                            side = sidx
                            break
                    if door:
                        break
                if door:
                    break

            if not door:
                continue

            # Interior threshold: step from door toward the mass centroid
            cx_avg = sum(p[0] for p in mass) / len(mass)
            cy_avg = sum(p[1] for p in mass) / len(mass)
            tx = 1 if cx_avg > door[0] else (-1 if cx_avg < door[0] else 0)
            ty = 1 if cy_avg > door[1] else (-1 if cy_avg < door[1] else 0)
            inner = (door[0] + tx, door[1] + ty)

            doorways.append(Doorway(len(doorways), door, inner, side))

    return doorways


def build_interior(world, doorway: Doorway) -> Tuple[InteriorSpace, InteriorView]:
    """Builds (and wraps) the interior for one doorway's building."""
    walls = world.walls
    w = world.width
    h = world.height
    # Bounding box of the door's connected mass (recomputed cheaply via flood)
    sx, sy = doorway.ext
    stack = [(sx, sy)]
    seen = {(sx, sy)}
    mass = []
    while stack:
        cx, cy = stack.pop()
        mass.append((cx, cy))
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and walls[ny][nx] != 0:
                seen.add((nx, ny))
                stack.append((nx, ny))

    xs = [p[0] for p in mass]
    ys = [p[1] for p in mass]
    bx0, bx1 = min(xs), max(xs)
    by0, by1 = min(ys), max(ys)

    space = InteriorSpace(
        bld_id=doorway.bld_id,
        bx0=bx0, by0=by0,
        bw=bx1 - bx0 + 1, bh=by1 - by0 + 1,
        doorway=doorway,
        seed=world.seed,
    )
    return space, InteriorView(space, world)
