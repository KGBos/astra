"""
Building Interiors, Doorway Detection, and Live-Window Portal support.

An InteriorSpace overlays the exact world-coordinate footprint of its building,
so the player camera crosses the threshold without any remapping. The
InteriorView wrapper implements the same query surface as CityMap (is_solid,
get_wall_type, ...) and is fed ONLY to player-facing systems (raycaster +
camera physics); traffic and pedestrians keep querying the raw world.

Themed storefront content (Ramen Bar / Arcade / Hotel Lobby names, wall
textures, and furniture props) was ported from the M2 engine branch onto this
architecture: rooms are still real footprints entered through detected
doorways, not teleport chambers.

Author: Nora Voss ⚙️ (OpenCode Platform)
"""

import random
from typing import Dict, List, Optional, Tuple

from src.entities.sprite import Sprite
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

# Minimum footprint for furniture placement (smaller masses stay bare)
FURNITURE_MIN_SIZE = 6

# Tower lobby contract (M5 Cycle C): wall masses containing a facade at least
# this tall become double-height lobby interiors instead of storefront rooms.
TOWER_LOBBY_MIN_HEIGHT_M = 25.0
LOBBY_WALL_TEXTURE = 104      # build_tower_lobby_interior(): 8 m ceiling volume
MAX_TOWER_LOBBIES = 8         # enterable-tower cap per city
STREET_REACH_CELLS = 64       # bounded BFS budget for door reachability


class Doorway:
    __slots__ = ('bld_id', 'ext', 'inner', 'side')

    def __init__(self, bld_id: int, ext: Tuple[int, int], inner: Tuple[int, int], side: int):
        self.bld_id = bld_id
        self.ext = ext        # exterior wall cell containing the door
        self.inner = inner    # matching walkable cell on the interior ring
        self.side = side      # 0=E,1=S,2=W,3=N (direction from door toward road)


class InteriorTheme:
    """Storefront identity applied to enterable buildings (ported M2 content)."""

    __slots__ = ('room_id', 'name', 'icon', 'wall_texture', '_furniture_builder')

    def __init__(self, room_id: str, name: str, icon: str, wall_texture: int,
                 furniture_builder=None):
        self.room_id = room_id
        self.name = name
        self.icon = icon
        self.wall_texture = wall_texture
        self._furniture_builder = furniture_builder

    def build_furniture(self, cx: float, cy: float) -> List[Sprite]:
        if self._furniture_builder is None:
            return []
        return self._furniture_builder(cx, cy)


def _ramen_counter_sprite(x: float, y: float) -> List[Sprite]:
    chars = [
        " [STEAMING NOODLES] ",
        "   (~)   (~)   (~)  ",
        "====================",
        "  |  |  |  |  |  |  "
    ]
    fg = [
        [(255, 240, 180) for _ in range(20)],
        [(255, 200, 50) for _ in range(20)],
        [(180, 100, 50) for _ in range(20)],
        [(100, 60, 30) for _ in range(20)]
    ]
    return [Sprite(x, y, "RAMEN_BAR", chars, fg,
                   scale_x=0.12, scale_y=0.3, is_luminous=True)]


def _arcade_cabinet_sprite(x: float, y: float) -> List[Sprite]:
    chars = [
        " [TOP 1: 999,990] ",
        "  <ASTRA RUNNER>  ",
        "  [CRT]     [CRT] ",
        "   (^)       (^)  "
    ]
    fg = [
        [(255, 255, 100) for _ in range(18)],
        [(0, 240, 255) for _ in range(18)],
        [(255, 50, 180) for _ in range(18)],
        [(50, 255, 150) for _ in range(18)]
    ]
    return [Sprite(x, y, "ARCADE_CABINET", chars, fg,
                   scale_x=0.09, scale_y=0.45, is_luminous=True)]


def _hotel_desk_sprite(x: float, y: float) -> List[Sprite]:
    chars = [
        "  * CHANDELIER *  ",
        " [CONCIERGE DESK] ",
        "  | [GOLD BELL] | ",
        "=================="
    ]
    fg = [
        [(255, 240, 150) for _ in range(18)],
        [(220, 180, 100) for _ in range(18)],
        [(255, 220, 50) for _ in range(18)],
        [(150, 120, 70) for _ in range(18)]
    ]
    return [Sprite(x, y, "HOTEL_DESK", chars, fg,
                   scale_x=0.14, scale_y=0.5, is_luminous=True)]


# Storefront catalog ported from the M2 branch's build_interiors_catalog()
BUILDING_THEMES = (
    InteriorTheme("RAMEN_SHOP", "KAITO'S 24H CYBER RAMEN", "~", 101, _ramen_counter_sprite),
    InteriorTheme("ARCADE", "NEON MATRIX CYBER ARCADE", "&", 102, _arcade_cabinet_sprite),
    InteriorTheme("HOTEL_LOBBY", "THE GRAND ASTRA HOTEL LOBBY", "^", 103, _hotel_desk_sprite),
)


def _reception_desk_sprite(x: float, y: float) -> List[Sprite]:
    chars = [
        "  * * SKY LOBBY * *  ",
        " [TOWER DIRECTORY] ",
        "  |==[DESK]==|  (^) ",
        "===================="
    ]
    fg = [
        [(160, 230, 255) for _ in range(20)],
        [(120, 255, 200) for _ in range(20)],
        [(220, 180, 100) for _ in range(20)],
        [(150, 150, 160) for _ in range(20)]
    ]
    return [Sprite(x, y, "TOWER_DESK", chars, fg,
                   scale_x=0.14, scale_y=0.6, is_luminous=True)]


LOBBY_THEME = InteriorTheme(
    "TOWER_LOBBY", "TOWER SKY LOBBY // 8 M VOLUME", "^",
    LOBBY_WALL_TEXTURE, _reception_desk_sprite)


def theme_for_building(bld_id: int) -> InteriorTheme:
    """Deterministic theme rotation across enterable buildings."""
    return BUILDING_THEMES[bld_id % len(BUILDING_THEMES)]


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
        self.theme = theme_for_building(bld_id)
        self.is_lobby = False

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


class LobbySpace(InteriorSpace):
    """Double-height ground-floor hall carved from a downtown tower mass.

    Same footprint mechanics as a storefront room; the lobby theme's wall
    texture projects an 8 m ceiling volume, so the space reads as a tall
    atrium from inside while windows stay live portals to the street.
    """

    def __init__(self, bld_id: int, bx0: int, by0: int, bw: int, bh: int,
                 doorway: Optional[Doorway], seed: int):
        super().__init__(bld_id, bx0, by0, bw, bh, doorway, seed)
        self.theme = LOBBY_THEME
        self.is_lobby = True


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

        # Themed furniture, placed toward the back wall of large enough rooms
        self.props: List[Sprite] = []
        if space.w >= FURNITURE_MIN_SIZE and space.h >= FURNITURE_MIN_SIZE:
            fx = space.x0 + space.w / 2.0
            fy = space.y0 + space.h * 0.35
            self.props.extend(space.theme.build_furniture(fx, fy))

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
        if code == CELL_DOOR:
            return WALL_TYPE_DOORWAY
        return self.space.theme.wall_texture

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


def flood_wall_mass(walls, w: int, h: int, sx: int, sy: int,
                    visited) -> List[Tuple[int, int]]:
    """Connected wall cells containing (sx, sy), marking them visited."""
    stack = [(sx, sy)]
    visited[sy][sx] = True
    mass: List[Tuple[int, int]] = []
    while stack:
        cx, cy = stack.pop()
        mass.append((cx, cy))
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx] and walls[ny][nx] != 0:
                visited[ny][nx] = True
                stack.append((nx, ny))
    return mass


def find_street_door(world, mass: List[Tuple[int, int]],
                     bx0: int, by0: int, bx1: int, by1: int):
    """First perimeter cell (scan order => deterministic) with street access.

    Returns ((cx, cy), side) or (None, 0)."""
    walls = world.walls
    w = world.width
    h = world.height
    mass_set = set(mass)

    def walkable(ix, iy):
        return (0 <= ix < w and 0 <= iy < h
                and walls[iy][ix] == 0
                and world.get_floor_type(ix, iy) != FloorType.WATER)

    for cy in range(by0, by1 + 1):
        for cx in range(bx0, bx1 + 1):
            if walls[cy][cx] == 0 or (cx, cy) not in mass_set:
                continue
            for sidx, (ox, oy) in enumerate(((1, 0), (0, 1), (-1, 0), (0, -1))):
                if walkable(cx + ox, cy + oy):
                    return (cx, cy), sidx
    return None, 0


def door_reaches_street(world, door: Tuple[int, int], side: int) -> bool:
    """Bounded BFS from the door's outside neighbor looking for road floor.

    Sealed courtyards and tower podium moats are open ground but never touch
    a road, so doors facing them would be unreachable; those fail this check.
    """
    walls = world.walls
    w = world.width
    h = world.height
    ox, oy = ((1, 0), (0, 1), (-1, 0), (0, -1))[side]
    start = (door[0] + ox, door[1] + oy)
    if not (0 <= start[0] < w and 0 <= start[1] < h):
        return False
    if walls[start[1]][start[0]] != 0:
        return False
    road_floors = (FloorType.ROAD_NS, FloorType.ROAD_EW,
                   FloorType.INTERSECTION, FloorType.BRIDGE)
    seen = {start}
    queue = [start]
    while queue:
        cx, cy = queue.pop()
        if world.get_floor_type(cx, cy) in road_floors:
            return True
        if len(seen) >= STREET_REACH_CELLS:
            break
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if (0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen
                    and walls[ny][nx] == 0
                    and world.get_floor_type(nx, ny) != FloorType.WATER):
                seen.add((nx, ny))
                queue.append((nx, ny))
    return False


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

    for sy in range(1, h - 1):
        if len(doorways) >= max_doors:
            break
        for sx in range(1, w - 1):
            if len(doorways) >= max_doors:
                break
            if visited[sy][sx] or walls[sy][sx] == 0:
                continue

            mass = flood_wall_mass(walls, w, h, sx, sy, visited)

            if not (6 <= len(mass) <= 90):
                continue
            xs = [p[0] for p in mass]
            ys = [p[1] for p in mass]
            bx0, bx1 = min(xs), max(xs)
            by0, by1 = min(ys), max(ys)
            if bx1 - bx0 < 2 or by1 - by0 < 2:
                continue

            door, side = find_street_door(world, mass, bx0, by0, bx1, by1)
            if not door:
                continue

            doorways.append(Doorway(len(doorways), door,
                                    _inner_step(mass, door), side))

    return doorways


def _inner_step(mass: List[Tuple[int, int]], door: Tuple[int, int]) -> Tuple[int, int]:
    """Interior threshold: one step from the door toward the mass centroid."""
    cx_avg = sum(p[0] for p in mass) / len(mass)
    cy_avg = sum(p[1] for p in mass) / len(mass)
    tx = 1 if cx_avg > door[0] else (-1 if cx_avg < door[0] else 0)
    ty = 1 if cy_avg > door[1] else (-1 if cy_avg < door[1] else 0)
    return (door[0] + tx, door[1] + ty)


def detect_tower_doorways(world, exclude_exts=(), next_bld_id: int = 0,
                          max_lobbies: int = MAX_TOWER_LOBBIES) -> List[Doorway]:
    """Adds enterable doorways on downtown towers taller than the lobby floor.

    A wall mass qualifies when it contains a facade at least
    TOWER_LOBBY_MIN_HEIGHT_M tall, is at least a 3x3 room, and its chosen
    perimeter door provably reaches road floor via bounded BFS -- so sealed
    podium moats never claim an unreachable door. Deterministic scan order;
    already-used exterior cells are skipped.
    """
    from src.world.textures import get_texture

    w = world.width
    h = world.height
    walls = world.walls
    visited = [[False] * w for _ in range(h)]
    doorways: List[Doorway] = []
    bld_id = next_bld_id
    excluded = set(exclude_exts)

    for sy in range(1, h - 1):
        if len(doorways) >= max_lobbies:
            break
        for sx in range(1, w - 1):
            if len(doorways) >= max_lobbies:
                break
            if visited[sy][sx] or walls[sy][sx] == 0:
                continue

            mass = flood_wall_mass(walls, w, h, sx, sy, visited)

            if len(mass) < 6:
                continue
            xs = [p[0] for p in mass]
            ys = [p[1] for p in mass]
            bx0, bx1 = min(xs), max(xs)
            by0, by1 = min(ys), max(ys)
            if bx1 - bx0 < 2 or by1 - by0 < 2:
                continue
            if not any(get_texture(walls[cy][cx]).height_mult >= TOWER_LOBBY_MIN_HEIGHT_M
                       for cx, cy in mass):
                continue

            door, side = find_street_door(world, mass, bx0, by0, bx1, by1)
            if not door or door in excluded:
                continue
            if not door_reaches_street(world, door, side):
                continue

            doorways.append(Doorway(bld_id, door, _inner_step(mass, door), side))
            bld_id += 1

    return doorways


def build_interior(world, doorway: Doorway) -> Tuple[InteriorSpace, InteriorView]:
    """Builds (and wraps) the interior for one doorway's building.

    Masses carrying a >=25 m facade become LobbySpace halls; everything else
    keeps the storefront room behavior."""
    walls = world.walls
    w = world.width
    h = world.height
    # Bounding box of the door's connected mass (recomputed cheaply via flood)
    mass = flood_wall_mass(walls, w, h, doorway.ext[0], doorway.ext[1],
                           [[False] * w for _ in range(h)])

    xs = [p[0] for p in mass]
    ys = [p[1] for p in mass]
    bx0, bx1 = min(xs), max(xs)
    by0, by1 = min(ys), max(ys)

    from src.world.textures import get_texture
    is_tower = any(get_texture(walls[cy][cx]).height_mult >= TOWER_LOBBY_MIN_HEIGHT_M
                   for cx, cy in mass)

    space_cls = LobbySpace if is_tower else InteriorSpace
    space = space_cls(
        bld_id=doorway.bld_id,
        bx0=bx0, by0=by0,
        bw=bx1 - bx0 + 1, bh=by1 - by0 + 1,
        doorway=doorway,
        seed=world.seed,
    )
    return space, InteriorView(space, world)
