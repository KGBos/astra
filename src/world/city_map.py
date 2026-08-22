"""
Procedural City Map, District Grid, Road Topology, and Traffic Light Controller for Astra 3D.
"""

from enum import IntEnum
from typing import List, Tuple, Optional, Dict
from src.world.textures import get_texture


class FloorType(IntEnum):
    VOID = 0
    ROAD_NS = 1
    ROAD_EW = 2
    INTERSECTION = 3
    SIDEWALK = 4
    PARK_GRASS = 5
    PLAZA_TILES = 6
    WATER = 7


class TrafficLightState(IntEnum):
    NS_GREEN = 1
    NS_YELLOW = 2
    EW_GREEN = 3
    EW_YELLOW = 4


class TrafficLight:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y
        self.state = TrafficLightState.NS_GREEN
        self.timer = 0.0
        self.green_duration = 10.0
        self.yellow_duration = 2.5

    def update(self, dt: float):
        self.timer += dt
        if self.state in (TrafficLightState.NS_GREEN, TrafficLightState.EW_GREEN):
            if self.timer >= self.green_duration:
                self.timer = 0.0
                self.state = TrafficLightState.NS_YELLOW if self.state == TrafficLightState.NS_GREEN else TrafficLightState.EW_YELLOW
        elif self.state in (TrafficLightState.NS_YELLOW, TrafficLightState.EW_YELLOW):
            if self.timer >= self.yellow_duration:
                self.timer = 0.0
                self.state = TrafficLightState.EW_GREEN if self.state == TrafficLightState.NS_YELLOW else TrafficLightState.NS_GREEN

    def is_green_for_ns(self) -> bool:
        return self.state == TrafficLightState.NS_GREEN

    def is_green_for_ew(self) -> bool:
        return self.state == TrafficLightState.EW_GREEN


class CityMap:
    def __init__(self, width: int = 42, height: int = 42):
        self.width = width
        self.height = height
        
        # Grid arrays
        self.walls: List[List[int]] = [[0 for _ in range(width)] for _ in range(height)]
        self.floors: List[List[int]] = [[FloorType.SIDEWALK for _ in range(width)] for _ in range(height)]
        self.districts: List[List[str]] = [["" for _ in range(width)] for _ in range(height)]
        
        # Road coordinates
        self.ns_road_cols = [4, 12, 20, 28, 36]
        self.ew_road_rows = [4, 12, 20, 28, 36]
        
        # Traffic lights keyed by (grid_x, grid_y)
        self.traffic_lights: Dict[Tuple[int, int], TrafficLight] = {}

        # Street Names
        self.avenue_names = {
            4: "Astra Avenue",
            12: "Cyber Boulevard",
            20: "Silicon Way",
            28: "Neon Parkway",
            36: "Terminal Express"
        }
        self.street_names = {
            4: "1st Uptown Street",
            12: "Matrix Boulevard",
            20: "Central Grand Way",
            28: "South Dock Road",
            36: "Industrial Avenue"
        }

        self._generate_city()

    def _generate_city(self):
        # 1. Build Perimeter Boundary Walls (Industrial / Security Wall)
        for x in range(self.width):
            self.walls[0][x] = 5
            self.walls[self.height - 1][x] = 5
        for y in range(self.height):
            self.walls[y][0] = 5
            self.walls[y][self.width - 1] = 5

        # 2. Carve Road Grid
        for col in self.ns_road_cols:
            for y in range(1, self.height - 1):
                # 2-lane road
                self.floors[y][col] = FloorType.ROAD_NS
                self.floors[y][col + 1] = FloorType.ROAD_NS
                self.walls[y][col] = 0
                self.walls[y][col + 1] = 0

        for row in self.ew_road_rows:
            for x in range(1, self.width - 1):
                # 2-lane road
                if self.floors[row][x] == FloorType.ROAD_NS or self.floors[row + 1][x] == FloorType.ROAD_NS:
                    self.floors[row][x] = FloorType.INTERSECTION
                    self.floors[row + 1][x] = FloorType.INTERSECTION
                else:
                    self.floors[row][x] = FloorType.ROAD_EW
                    self.floors[row + 1][x] = FloorType.ROAD_EW
                self.walls[row][x] = 0
                self.walls[row + 1][x] = 0

        # Register Traffic Lights at Intersections
        for col in self.ns_road_cols:
            for row in self.ew_road_rows:
                tl = TrafficLight(col, row)
                self.traffic_lights[(col, row)] = tl

        # 3. Populate City Blocks with District-Specific Architecture
        block_x_starts = [1, 6, 14, 22, 30, 38]
        block_x_ends =   [3, 11, 19, 27, 35, 40]
        block_y_starts = [1, 6, 14, 22, 30, 38]
        block_y_ends =   [3, 11, 19, 27, 35, 40]

        for by_idx, (by0, by1) in enumerate(zip(block_y_starts, block_y_ends)):
            for bx_idx, (bx0, bx1) in enumerate(zip(block_x_starts, block_x_ends)):
                self._fill_block(bx0, bx1, by0, by1, bx_idx, by_idx)

    def _fill_block(self, x0: int, x1: int, y0: int, y1: int, bx: int, by: int):
        mid_x = self.width // 2
        mid_y = self.height // 2
        
        # Determine district
        if x0 < mid_x and y0 < mid_y:
            district = "CYBER-DOWNTOWN"
            default_wall = 2 if (bx + by) % 2 == 0 else 1  # Neon & Glass Skyscraper
        elif x0 >= mid_x and y0 < mid_y:
            district = "MIDTOWN COMMERCIAL"
            default_wall = 4 if (bx * 3 + by) % 2 == 0 else 6  # Ramen shops & Neon Hotels
        elif x0 < mid_x and y0 >= mid_y:
            district = "HISTORIC BROWNSTONES"
            default_wall = 3  # Brick Brownstone
        else:
            district = "INDUSTRIAL DOCKLANDS"
            default_wall = 5  # Concrete Warehouse

        # Central Park / Plaza special block at (14..19, 14..19)
        if 14 <= x0 <= 19 and 14 <= y0 <= 19:
            district = "CENTRAL ASTRA PLAZA"
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    self.districts[y][x] = district
                    self.walls[y][x] = 0
                    self.floors[y][x] = FloorType.PARK_GRASS if (x + y) % 2 == 0 else FloorType.PLAZA_TILES
            return

        # Regular block: Building footprint with surrounding sidewalk
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.districts[y][x] = district
                
                # Check if edge of block (sidewalk alley / plaza)
                is_outer = (x == x0 or x == x1 or y == y0 or y == y1)
                
                # Keep small walkways between buildings
                if is_outer and (x0 + 1 <= x <= x1 - 1) and (x % 3 == 0 or y % 3 == 0):
                    self.walls[y][x] = 0
                    self.floors[y][x] = FloorType.SIDEWALK
                else:
                    self.walls[y][x] = default_wall

    def is_solid(self, x: float, y: float) -> bool:
        """Returns True if world position (x, y) contains a solid wall or is out of bounds."""
        ix = int(x)
        iy = int(y)
        if ix < 0 or ix >= self.width or iy < 0 or iy >= self.height:
            return True
        return self.walls[iy][ix] > 0

    def get_wall_type(self, x: int, y: int) -> int:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.walls[y][x]
        return 5

    def get_wall_height(self, wall_type: int) -> float:
        tex = get_texture(wall_type)
        return tex.height_mult if tex else 1.0

    def get_floor_type(self, x: int, y: int) -> int:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.floors[y][x]
        return FloorType.SIDEWALK

    def get_district_at(self, x: float, y: float) -> str:
        ix = int(x)
        iy = int(y)
        if 0 <= ix < self.width and 0 <= iy < self.height:
            d = self.districts[iy][ix]
            if d:
                return d
        return "ASTRA METROPOLIS"

    def get_nearest_street_name(self, x: float, y: float) -> str:
        ix = int(x)
        iy = int(y)
        # Check closest avenue (NS)
        closest_ns = min(self.ns_road_cols, key=lambda c: abs(c - ix))
        closest_ew = min(self.ew_road_rows, key=lambda r: abs(r - iy))
        
        if abs(closest_ns - ix) <= abs(closest_ew - iy):
            return self.avenue_names.get(closest_ns, "Astra Way")
        else:
            return self.street_names.get(closest_ew, "Neon Street")

    def update(self, dt: float):
        for tl in self.traffic_lights.values():
            tl.update(dt)
