"""
Procedural City Map, District Grid, Road Topology, and Traffic Light Controller for Astra 3D.
Integrated with Darius Thorne's Next-Gen Procedural World Engine.
"""

from enum import IntEnum
from typing import Dict, List, Optional, Tuple
from src.world.textures import get_texture
from src.world.procedural_gen import (
    ProceduralCityGenerator,
    CityMapData,
    Landmark,
    RoadGraph,
    DistrictType,
)


class FloorType(IntEnum):
    VOID = 0
    ROAD_NS = 1
    ROAD_EW = 2
    INTERSECTION = 3
    SIDEWALK = 4
    PARK_GRASS = 5
    PLAZA_TILES = 6
    WATER = 7
    BRIDGE = 8
    COBBLESTONE = 9
    WOOD_DECK = 10


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
    """
    Procedural City World Container for Astra 3D.
    Supports deterministic multi-district generation, dynamic traffic light grids,
    road graphs, named landmarks, and query APIs.
    """

    def __init__(
        self,
        width: int = 42,
        height: int = 42,
        seed: Optional[int | str] = None,
        preset: str = "DEFAULT"
    ):
        self.width = width
        self.height = height
        self.generator = ProceduralCityGenerator()
        
        # Generate city data deterministically
        self._map_data: CityMapData = self.generator.generate(
            seed=seed,
            width=width,
            height=height,
            preset=preset
        )

        self.seed: int = self._map_data.seed
        self.walls: List[List[int]] = self._map_data.walls
        self.floors: List[List[int]] = self._map_data.floors
        self.districts: List[List[str]] = self._map_data.districts
        self.ns_road_cols: List[int] = self._map_data.ns_road_cols
        self.ew_road_rows: List[int] = self._map_data.ew_road_rows
        self.avenue_names: Dict[int, str] = self._map_data.avenue_names
        self.street_names: Dict[int, str] = self._map_data.street_names
        self.landmarks: List[Landmark] = self._map_data.landmarks
        self.road_graph: RoadGraph = self._map_data.road_graph
        self.props = self._map_data.props
        self.spawn_pos: Tuple[float, float] = self._map_data.spawn_pos

        # Traffic lights keyed by (grid_x, grid_y)
        self.traffic_lights: Dict[Tuple[int, int], TrafficLight] = {}
        for coord in self._map_data.traffic_light_coords:
            self.traffic_lights[coord] = TrafficLight(coord[0], coord[1])

        # Enterable buildings: doorways + lazily-built interiors.
        # Imported lazily to avoid a circular module dependency
        from src.world.interiors import WALL_TYPE_DOORWAY, detect_doorways

        self.doorways: List[Doorway] = detect_doorways(self)
        self._doorway_by_ext: Dict[Tuple[int, int], Doorway] = {
            d.ext: d for d in self.doorways
        }
        for d in self.doorways:
            # Retexture the threshold so the door reads as an entry from outside
            ex, ey = d.ext
            self.walls[ey][ex] = WALL_TYPE_DOORWAY
        self._interior_cache: Dict = {}

    def doorway_at(self, ix: int, iy: int):
        return self._doorway_by_ext.get((ix, iy))

    def get_interior(self, doorway):
        """Lazily builds and caches (space, view) for a doorway's building."""
        from src.world.interiors import build_interior
        if doorway.bld_id not in self._interior_cache:
            self._interior_cache[doorway.bld_id] = build_interior(self, doorway)
        return self._interior_cache[doorway.bld_id]

    @classmethod
    def from_seed(
        cls,
        seed: int | str,
        width: int = 42,
        height: int = 42,
        preset: str = "DEFAULT"
    ) -> 'CityMap':
        return cls(width=width, height=height, seed=seed, preset=preset)

    def is_solid(self, x: float, y: float) -> bool:
        """Returns True if world position (x, y) contains a solid wall or is out of bounds."""
        ix = int(x)
        iy = int(y)
        if ix < 0 or ix >= self.width or iy < 0 or iy >= self.height:
            return True
        return self.walls[iy][ix] > 0

    def is_water(self, x: float, y: float) -> bool:
        """Returns True if world position (x, y) is water."""
        ix = int(x)
        iy = int(y)
        if 0 <= ix < self.width and 0 <= iy < self.height:
            return self.floors[iy][ix] == FloorType.WATER
        return False

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
        if not self.ns_road_cols or not self.ew_road_rows:
            return "Astra Way"
        closest_ns = min(self.ns_road_cols, key=lambda c: abs(c - ix))
        closest_ew = min(self.ew_road_rows, key=lambda r: abs(r - iy))

        if abs(closest_ns - ix) <= abs(closest_ew - iy):
            return self.avenue_names.get(closest_ns, "Astra Way")
        else:
            return self.street_names.get(closest_ew, "Neon Street")

    def get_nearest_landmark(self, x: float, y: float) -> Optional[Tuple[Landmark, float, str]]:
        """Returns (landmark, distance, compass_bearing) to the closest landmark."""
        if not self.landmarks:
            return None
        nearest = min(self.landmarks, key=lambda lm: lm.distance_to(x, y))
        dist = nearest.distance_to(x, y)
        bearing = nearest.bearing_from(x, y)
        return (nearest, dist, bearing)

    def get_landmarks(self) -> List[Landmark]:
        return list(self.landmarks)

    def render_ascii_map(self) -> str:
        return self.generator.render_ascii_overview(self._map_data)

    def update(self, dt: float):
        for tl in self.traffic_lights.values():
            tl.update(dt)
