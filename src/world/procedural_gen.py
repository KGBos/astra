"""
Next-Generation Procedural City Generator, District Partitioner, Road Graph & Landmark Engine for Astra 3D.
Author: Darius Thorne (Procedural World & City Generation Specialist 📐)
"""

import math
import random
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Dict, List, Optional, Set, Tuple

from src.entities.sprite import (
    Sprite,
    make_bollard_sprite,
    make_crate_stack_sprite,
    make_dumpster_sprite,
    make_fire_hydrant_sprite,
    make_fountain_sprite,
    make_monument_obelisk_sprite,
    make_neon_signpost_sprite,
    make_park_bench_sprite,
    make_streetlamp_sprite,
    make_tree_sprite,
)


class DistrictType(str, Enum):
    CYBER_DOWNTOWN = "CYBER-DOWNTOWN"
    FINANCIAL_CORE = "FINANCIAL CORE"
    NEON_ENTERTAINMENT = "NEON ENTERTAINMENT"
    HISTORIC_QUARTER = "HISTORIC BROWNSTONES"
    INDUSTRIAL_DOCKLANDS = "INDUSTRIAL DOCKLANDS"
    CENTRAL_PLAZA_PARK = "CENTRAL ASTRA PLAZA"
    WATERFRONT_MARINA = "WATERFRONT MARINA"


@dataclass
class Landmark:
    name: str
    x: float
    y: float
    district: str
    landmark_type: str  # "SKYSCRAPER", "MONUMENT", "PARK", "MARINA", "COMMERCIAL", "INDUSTRIAL"
    description: str
    icon: str = "★"

    def distance_to(self, target_x: float, target_y: float) -> float:
        return math.hypot(self.x - target_x, self.y - target_y)

    def bearing_from(self, from_x: float, from_y: float) -> str:
        dx = self.x - from_x
        dy = self.y - from_y
        angle_deg = math.degrees(math.atan2(dy, dx)) % 360
        # Compass 8-points: 0=East (+X), 90=South (+Y), 180=West (-X), 270=North (-Y)
        if 337.5 <= angle_deg or angle_deg < 22.5: return "E"
        elif 22.5 <= angle_deg < 67.5: return "SE"
        elif 67.5 <= angle_deg < 112.5: return "S"
        elif 112.5 <= angle_deg < 157.5: return "SW"
        elif 157.5 <= angle_deg < 202.5: return "W"
        elif 202.5 <= angle_deg < 247.5: return "NW"
        elif 247.5 <= angle_deg < 292.5: return "N"
        else: return "NE"


@dataclass
class RoadNode:
    id: int
    x: int
    y: int
    is_intersection: bool
    district: str


@dataclass
class RoadEdge:
    u: int
    v: int
    road_type: int
    name: str
    length: float


class RoadGraph:
    """Topological road network graph for traffic routing and spatial navigation."""
    def __init__(self):
        self.nodes: Dict[int, RoadNode] = {}
        self.adj: Dict[int, List[int]] = {}
        self.edges: Dict[Tuple[int, int], RoadEdge] = {}
        self.grid_to_node: Dict[Tuple[int, int], int] = {}
        self._next_id = 0

    def add_node(self, x: int, y: int, is_intersection: bool, district: str) -> int:
        if (x, y) in self.grid_to_node:
            return self.grid_to_node[(x, y)]
        node_id = self._next_id
        self._next_id += 1
        node = RoadNode(node_id, x, y, is_intersection, district)
        self.nodes[node_id] = node
        self.adj[node_id] = []
        self.grid_to_node[(x, y)] = node_id
        return node_id

    def add_edge(self, u: int, v: int, road_type: int, name: str):
        if u not in self.nodes or v not in self.nodes:
            return
        node_u = self.nodes[u]
        node_v = self.nodes[v]
        length = math.hypot(node_u.x - node_v.x, node_u.y - node_v.y)
        edge = RoadEdge(u, v, road_type, name, length)
        self.edges[(u, v)] = edge
        self.edges[(v, u)] = edge
        if v not in self.adj[u]: self.adj[u].append(v)
        if u not in self.adj[v]: self.adj[v].append(u)

    def find_nearest_node(self, x: float, y: float) -> Optional[RoadNode]:
        if not self.nodes:
            return None
        return min(self.nodes.values(), key=lambda n: math.hypot(n.x - x, n.y - y))

    def shortest_path(self, start_id: int, target_id: int) -> List[Tuple[int, int]]:
        """Computes shortest path between two road nodes using BFS."""
        if start_id == target_id or start_id not in self.nodes or target_id not in self.nodes:
            return [(self.nodes[start_id].x, self.nodes[start_id].y)] if start_id in self.nodes else []

        queue = [(start_id, [start_id])]
        visited = {start_id}

        while queue:
            curr, path = queue.pop(0)
            if curr == target_id:
                return [(self.nodes[nid].x, self.nodes[nid].y) for nid in path]
            for neighbor in self.adj.get(curr, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        return []


@dataclass
class CityMapData:
    width: int
    height: int
    seed: int
    walls: List[List[int]]
    floors: List[List[int]]
    districts: List[List[str]]
    ns_road_cols: List[int]
    ew_road_rows: List[int]
    traffic_light_coords: List[Tuple[int, int]]
    avenue_names: Dict[int, str]
    street_names: Dict[int, str]
    landmarks: List[Landmark]
    road_graph: RoadGraph
    props: List[Sprite]
    spawn_pos: Tuple[float, float]


class ProceduralCityGenerator:
    """
    High-performance procedural city synthesizer generating multi-district metropolises,
    road graphs, architectural building masses, thematic street names, and props deterministically.
    """

    AVENUE_POOLS = [
        "Astra Avenue", "Cyber Boulevard", "Silicon Way", "Neon Parkway", "Terminal Express",
        "Turing Corridor", "Quantum Promenade", "Hyperion Drive", "Synapse Boulevard", "Nexus Way",
        "Voxel Highway", "Matrix Arterial", "Zenith Parkway", "Cobalt Boulevard", "Vector Expressway"
    ]

    STREET_POOLS = [
        "1st Uptown Street", "Matrix Boulevard", "Central Grand Way", "South Dock Road", "Industrial Avenue",
        "Kowloon Alley", "Neon Arcade Row", "Old Brewery Lane", "Foundry Street", "Cathedral Court",
        "Circuit Walk", "Harbor Gate Road", "Plaza Promenade", "Starlight Alley", "Solaria Crossing"
    ]

    LANDMARK_TEMPLATES = [
        ("Astra Zenith Spire", "SKYSCRAPER", "The towering corporate monolith overlooking the cyber-downtown skyline."),
        ("Nexus Data Matrix Hub", "SKYSCRAPER", "The pulsating neural core of the metropolis with streaming binary data channels."),
        ("Central Obelisk Monument", "MONUMENT", "The historic glowing obelisk commemorating the founding of Astra Metropolis."),
        ("Grand Solaria Fountain", "MONUMENT", "A luminous multi-tier water fountain at the heart of the central plaza."),
        ("Solaria Deepwater Marina", "MARINA", "The bustling coastal docklands with illuminated mooring piers."),
        ("Neo-Ramen Night Market", "COMMERCIAL", "A vibrant alleyway market lined with amber neon ramen stalls and cyber-cafes."),
        ("Old Brownstone Brewery", "COMMERCIAL", "Historic brick landmark preserved amidst the rising neon megastructures."),
        ("Hyperion Power Substation", "INDUSTRIAL", "Heavy industrial transformers and high-voltage cooling silos."),
        ("Zenith Glass Conservatory", "PARK", "Lush botanical greenhouse oasis surrounded by verdant flora."),
        ("Dock 42 Cargo Terminal", "INDUSTRIAL", "Automated container cranes and heavy concrete freight warehouses.")
    ]

    def __init__(self):
        pass

    @staticmethod
    def normalize_seed(seed: Optional[int | str]) -> int:
        if seed is None:
            return random.randint(100000, 999999)
        if isinstance(seed, str):
            # Deterministic hash
            h = 0
            for char in seed:
                h = (h * 31 + ord(char)) & 0xFFFFFFFF
            return h
        return int(seed)

    def generate(
        self,
        seed: Optional[int | str] = None,
        width: int = 42,
        height: int = 42,
        preset: str = "DEFAULT"
    ) -> CityMapData:
        """
        Generates a complete deterministic city layout for given dimensions and seed.
        """
        int_seed = self.normalize_seed(seed)
        rng = random.Random(int_seed)

        # Floor enum constants matching CityMap.FloorType
        FLOOR_VOID = 0
        FLOOR_ROAD_NS = 1
        FLOOR_ROAD_EW = 2
        FLOOR_INTERSECTION = 3
        FLOOR_SIDEWALK = 4
        FLOOR_PARK_GRASS = 5
        FLOOR_PLAZA_TILES = 6
        FLOOR_WATER = 7
        FLOOR_BRIDGE = 8
        FLOOR_COBBLESTONE = 9
        FLOOR_WOOD_DECK = 10

        # Initialize grids
        walls: List[List[int]] = [[0 for _ in range(width)] for _ in range(height)]
        floors: List[List[int]] = [[FLOOR_SIDEWALK for _ in range(width)] for _ in range(height)]
        districts: List[List[str]] = [["" for _ in range(width)] for _ in range(height)]

        # 1. Compute Road Columns and Rows
        ns_road_cols = self._compute_road_coords(width, rng)
        ew_road_rows = self._compute_road_coords(height, rng)

        # 2. Procedural Street and Avenue Names
        avenue_names: Dict[int, str] = {}
        avail_ave = list(self.AVENUE_POOLS)
        rng.shuffle(avail_ave)
        for i, col in enumerate(ns_road_cols):
            avenue_names[col] = avail_ave[i % len(avail_ave)]

        street_names: Dict[int, str] = {}
        avail_str = list(self.STREET_POOLS)
        rng.shuffle(avail_str)
        for i, row in enumerate(ew_road_rows):
            street_names[row] = avail_str[i % len(avail_str)]

        # 3. Build Perimeter Boundary Walls
        for x in range(width):
            walls[0][x] = 5
            walls[height - 1][x] = 5
        for y in range(height):
            walls[y][0] = 5
            walls[y][width - 1] = 5

        # 4. District Zoning Map
        mid_x = width // 2
        mid_y = height // 2
        has_marina = (width >= 40 and height >= 40)

        for y in range(height):
            for x in range(width):
                if has_marina and x >= width - 6 and 4 <= y < height - 4:
                    districts[y][x] = DistrictType.WATERFRONT_MARINA.value
                elif abs(x - mid_x) <= 4 and abs(y - mid_y) <= 4:
                    districts[y][x] = DistrictType.CENTRAL_PLAZA_PARK.value
                elif x < mid_x and y < mid_y:
                    districts[y][x] = DistrictType.CYBER_DOWNTOWN.value
                elif x >= mid_x and y < mid_y:
                    districts[y][x] = DistrictType.NEON_ENTERTAINMENT.value
                elif x < mid_x and y >= mid_y:
                    districts[y][x] = DistrictType.HISTORIC_QUARTER.value
                else:
                    districts[y][x] = DistrictType.INDUSTRIAL_DOCKLANDS.value

        # 5. Carve Road Grid & Bridge Crossings
        traffic_light_coords: List[Tuple[int, int]] = []
        road_graph = RoadGraph()

        for col in ns_road_cols:
            for y in range(1, height - 1):
                is_water = (districts[y][col] == DistrictType.WATERFRONT_MARINA.value and col >= width - 6)
                ftype = FLOOR_BRIDGE if is_water else FLOOR_ROAD_NS
                floors[y][col] = ftype
                floors[y][col + 1] = ftype
                walls[y][col] = 0
                walls[y][col + 1] = 0

        for row in ew_road_rows:
            for x in range(1, width - 1):
                is_water = (districts[row][x] == DistrictType.WATERFRONT_MARINA.value and x >= width - 6)
                if floors[row][x] in (FLOOR_ROAD_NS, FLOOR_BRIDGE) or floors[row + 1][x] in (FLOOR_ROAD_NS, FLOOR_BRIDGE):
                    floors[row][x] = FLOOR_INTERSECTION
                    floors[row + 1][x] = FLOOR_INTERSECTION
                else:
                    floors[row][x] = FLOOR_BRIDGE if is_water else FLOOR_ROAD_EW
                    floors[row + 1][x] = FLOOR_BRIDGE if is_water else FLOOR_ROAD_EW
                walls[row][x] = 0
                walls[row + 1][x] = 0

        # Register Traffic Lights and Road Nodes
        for col in ns_road_cols:
            for row in ew_road_rows:
                traffic_light_coords.append((col, row))
                d_name = districts[row][col] or DistrictType.CYBER_DOWNTOWN.value
                node_id = road_graph.add_node(col, row, is_intersection=True, district=d_name)

        # Build Graph Edges along North-South and East-West corridors
        for col in ns_road_cols:
            sorted_nodes = sorted([nid for nid, n in road_graph.nodes.items() if n.x == col], key=lambda nid: road_graph.nodes[nid].y)
            for i in range(len(sorted_nodes) - 1):
                road_graph.add_edge(sorted_nodes[i], sorted_nodes[i + 1], FLOOR_ROAD_NS, avenue_names.get(col, "Avenue"))

        for row in ew_road_rows:
            sorted_nodes = sorted([nid for nid, n in road_graph.nodes.items() if n.y == row], key=lambda nid: road_graph.nodes[nid].x)
            for i in range(len(sorted_nodes) - 1):
                road_graph.add_edge(sorted_nodes[i], sorted_nodes[i + 1], FLOOR_ROAD_EW, street_names.get(row, "Street"))

        # 6. Carve Water basin in Waterfront Marina if enabled
        if has_marina:
            for y in range(4, height - 4):
                for x in range(width - 5, width - 1):
                    if floors[y][x] not in (FLOOR_ROAD_EW, FLOOR_ROAD_NS, FLOOR_INTERSECTION, FLOOR_BRIDGE):
                        floors[y][x] = FLOOR_WATER
                        walls[y][x] = 0

        # 7. Subdivide Blocks & Generate Building Massing & Architecture
        block_bounds_x = self._compute_block_bounds(width, ns_road_cols)
        block_bounds_y = self._compute_block_bounds(height, ew_road_rows)

        props: List[Sprite] = []
        landmarks: List[Landmark] = []

        for by_idx, (y0, y1) in enumerate(block_bounds_y):
            for bx_idx, (x0, x1) in enumerate(block_bounds_x):
                self._fill_procedural_block(
                    x0, x1, y0, y1, bx_idx, by_idx,
                    walls, floors, districts, props, landmarks, rng
                )

        # 8. Add Streetlamps & Sidewalk Props along Roads
        self._populate_street_props(ns_road_cols, ew_road_rows, width, height, floors, walls, props, rng)

        # 9. Register Thematic Landmarks from Generated Features
        self._finalize_landmarks(landmarks, districts, width, height, rng)

        # 10. Determine safe player spawn position
        spawn_pos = self._find_safe_spawn_pos(width, height, floors, walls, rng)

        return CityMapData(
            width=width,
            height=height,
            seed=int_seed,
            walls=walls,
            floors=floors,
            districts=districts,
            ns_road_cols=ns_road_cols,
            ew_road_rows=ew_road_rows,
            traffic_light_coords=traffic_light_coords,
            avenue_names=avenue_names,
            street_names=street_names,
            landmarks=landmarks,
            road_graph=road_graph,
            props=props,
            spawn_pos=spawn_pos
        )

    def _compute_road_coords(self, dim: int, rng: random.Random) -> List[int]:
        """Computes 2-lane road column/row offsets spaced 7-9 tiles apart."""
        if dim == 42:
            return [4, 12, 20, 28, 36]
        
        # General dynamic spacing
        coords = []
        curr = 4
        while curr <= dim - 6:
            coords.append(curr)
            curr += 8
        if not coords:
            coords = [dim // 2]
        return coords

    def _compute_block_bounds(self, dim: int, road_coords: List[int]) -> List[Tuple[int, int]]:
        """Returns (start, end) inclusive indices for building blocks between roads."""
        bounds = []
        # First block before first road
        if road_coords[0] > 1:
            bounds.append((1, road_coords[0] - 1))

        # Intermediate blocks between roads (roads are 2 tiles wide: col, col+1)
        for i in range(len(road_coords) - 1):
            start = road_coords[i] + 2
            end = road_coords[i + 1] - 1
            if start <= end:
                bounds.append((start, end))

        # Last block after last road
        last_road_end = road_coords[-1] + 2
        if last_road_end <= dim - 2:
            bounds.append((last_road_end, dim - 2))

        return bounds

    def _fill_procedural_block(
        self,
        x0: int, x1: int, y0: int, y1: int,
        bx: int, by: int,
        walls: List[List[int]],
        floors: List[List[int]],
        districts: List[List[str]],
        props: List[Sprite],
        landmarks: List[Landmark],
        rng: random.Random
    ):
        mid_bx = (x0 + x1) // 2
        mid_by = (y0 + y1) // 2
        district = districts[mid_by][mid_bx] or DistrictType.CYBER_DOWNTOWN.value

        FLOOR_SIDEWALK = 4
        FLOOR_PARK_GRASS = 5
        FLOOR_PLAZA_TILES = 6
        FLOOR_WATER = 7
        FLOOR_COBBLESTONE = 9
        FLOOR_WOOD_DECK = 10

        # Special Case A: Central Plaza Park
        if district == DistrictType.CENTRAL_PLAZA_PARK.value:
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    walls[y][x] = 0
                    districts[y][x] = district
                    floors[y][x] = FLOOR_PARK_GRASS if (x + y) % 2 == 0 else FLOOR_PLAZA_TILES

            center_x = (x0 + x1) / 2.0
            center_y = (y0 + y1) / 2.0
            if (bx + by) % 2 == 0:
                props.append(make_monument_obelisk_sprite(center_x, center_y))
                landmarks.append(Landmark("Central Obelisk", center_x, center_y, district, "MONUMENT", "Historic glowing obelisk."))
            else:
                props.append(make_fountain_sprite(center_x, center_y))
                landmarks.append(Landmark("Grand Solaria Fountain", center_x, center_y, district, "MONUMENT", "Luminous multi-tier water fountain."))

            # Add park benches and trees
            props.append(make_tree_sprite(x0 + 0.5, y0 + 0.5))
            props.append(make_tree_sprite(x1 + 0.5, y1 + 0.5))
            props.append(make_park_bench_sprite(x0 + 1.5, center_y))
            props.append(make_park_bench_sprite(x1 - 0.5, center_y))
            return

        # Special Case B: Waterfront Marina
        if district == DistrictType.WATERFRONT_MARINA.value:
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    districts[y][x] = district
                    if x == x0:
                        walls[y][x] = 10  # MARINA_DOCK wall texture
                        floors[y][x] = FLOOR_WOOD_DECK
                    else:
                        walls[y][x] = 0
                        floors[y][x] = FLOOR_WATER
            props.append(make_bollard_sprite(x0 - 0.5, y0 + 1.5))
            props.append(make_bollard_sprite(x0 - 0.5, y1 - 0.5))
            landmarks.append(Landmark("Solaria Marina Pier", x0 + 0.5, (y0 + y1) / 2.0, district, "MARINA", "Coastal dockland pier."))
            return

        # Block Massing according to District
        if district == DistrictType.CYBER_DOWNTOWN.value:
            wall_palette = [1, 2, 8, 7]  # Glass, Neon, Megastructure Matrix, Arcology
            floor_type = FLOOR_SIDEWALK
        elif district == DistrictType.FINANCIAL_CORE.value:
            wall_palette = [1, 8, 7]
            floor_type = FLOOR_PLAZA_TILES
        elif district == DistrictType.NEON_ENTERTAINMENT.value:
            wall_palette = [2, 4, 6]     # Neon Skyscraper, Ramen Storefront, Neon Hotel
            floor_type = FLOOR_SIDEWALK
        elif district == DistrictType.HISTORIC_QUARTER.value:
            wall_palette = [3]           # Brick Brownstones
            floor_type = FLOOR_COBBLESTONE
        else:  # INDUSTRIAL_DOCKLANDS
            wall_palette = [5, 9]        # Concrete Warehouse, Industrial Silo
            floor_type = FLOOR_SIDEWALK

        primary_wall = rng.choice(wall_palette)

        # Procedural Block Layout (Courtyard, Alleys, or Solid Footprint)
        block_w = x1 - x0 + 1
        block_h = y1 - y0 + 1

        has_courtyard = (block_w >= 5 and block_h >= 5 and rng.random() > 0.4)
        has_alley = (block_w >= 4 and block_h >= 4 and not has_courtyard and rng.random() > 0.3)

        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                districts[y][x] = district
                floors[y][x] = floor_type

                # Check if edge / corner
                is_edge = (x == x0 or x == x1 or y == y0 or y == y1)
                is_center = (x0 + 1 <= x <= x1 - 1 and y0 + 1 <= y <= y1 - 1)

                if has_courtyard and is_center and (x == mid_bx or y == mid_by):
                    walls[y][x] = 0
                    floors[y][x] = FLOOR_PLAZA_TILES
                elif has_alley and (x == mid_bx):
                    walls[y][x] = 0
                    floors[y][x] = floor_type
                else:
                    walls[y][x] = primary_wall

        # Place thematic props inside block alleys or courtyards
        if has_courtyard:
            props.append(make_fountain_sprite(mid_bx + 0.5, mid_by + 0.5))
        elif has_alley:
            props.append(make_dumpster_sprite(mid_bx + 0.5, y0 + 0.5))
            if district == DistrictType.NEON_ENTERTAINMENT.value:
                props.append(make_neon_signpost_sprite(mid_bx + 0.5, y1 - 0.5, "RAMEN"))

    def _populate_street_props(
        self,
        ns_cols: List[int],
        ew_rows: List[int],
        width: int,
        height: int,
        floors: List[List[int]],
        walls: List[List[int]],
        props: List[Sprite],
        rng: random.Random
    ):
        """Places streetlamps, hydrants, trees, and trash cans along sidewalk corridors."""
        for col in ns_cols:
            for row in ew_rows:
                # Streetlamps at intersection corners
                corners = [
                    (col - 1.5, row - 1.5),
                    (col + 2.5, row - 1.5),
                    (col - 1.5, row + 2.5),
                    (col + 2.5, row + 2.5)
                ]
                for px, py in corners:
                    ix, iy = int(px), int(py)
                    if 1 <= ix < width - 1 and 1 <= iy < height - 1 and walls[iy][ix] == 0:
                        props.append(make_streetlamp_sprite(px, py))

        # Mid-block sidewalk props
        for col in ns_cols:
            for row in ew_rows:
                mid_y = row + 4.5
                if mid_y < height - 2:
                    props.append(make_fire_hydrant_sprite(col - 1.2, mid_y))
                    if rng.random() > 0.5:
                        props.append(make_tree_sprite(col + 2.2, mid_y))

    def _finalize_landmarks(
        self,
        landmarks: List[Landmark],
        districts: List[List[str]],
        width: int,
        height: int,
        rng: random.Random
    ):
        """Ensures at least 4 named landmarks are mapped across districts."""
        if len(landmarks) >= 4:
            return

        mid_x = width // 2
        mid_y = height // 2

        # Add Core Skycraper Landmark
        landmarks.append(Landmark(
            name="Astra Zenith Spire",
            x=max(2.0, mid_x - 8.0),
            y=max(2.0, mid_y - 8.0),
            district=DistrictType.CYBER_DOWNTOWN.value,
            landmark_type="SKYSCRAPER",
            description="The premier corporate monolith overlooking Astra Metropolis."
        ))

        # Add Neon Arcade Landmark
        landmarks.append(Landmark(
            name="Neo-Ramen Arcade",
            x=min(width - 4.0, mid_x + 8.0),
            y=max(2.0, mid_y - 8.0),
            district=DistrictType.NEON_ENTERTAINMENT.value,
            landmark_type="COMMERCIAL",
            description="Vibrant entertainment boulevard illuminated with neon holograms."
        ))

        # Add Historic Brewery
        landmarks.append(Landmark(
            name="Old Brownstone Brewery",
            x=max(2.0, mid_x - 8.0),
            y=min(height - 4.0, mid_y + 8.0),
            district=DistrictType.HISTORIC_QUARTER.value,
            landmark_type="COMMERCIAL",
            description="19th-century architectural heritage brick structure."
        ))

        # Add Dock Terminal
        landmarks.append(Landmark(
            name="Dock 42 Freight Terminal",
            x=min(width - 4.0, mid_x + 8.0),
            y=min(height - 4.0, mid_y + 8.0),
            district=DistrictType.INDUSTRIAL_DOCKLANDS.value,
            landmark_type="INDUSTRIAL",
            description="Heavy freight and automated logistics depot."
        ))

    def _find_safe_spawn_pos(
        self,
        width: int,
        height: int,
        floors: List[List[int]],
        walls: List[List[int]],
        rng: random.Random
    ) -> Tuple[float, float]:
        """Finds a safe non-solid coordinate near the center for player spawn."""
        mid_x = width // 2
        mid_y = height // 2

        # Check spiral around center
        for radius in range(0, max(width, height)):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    x = mid_x + dx
                    y = mid_y + dy
                    if 1 <= x < width - 1 and 1 <= y < height - 1:
                        if walls[y][x] == 0 and floors[y][x] != 7:  # Not wall, not water
                            return (float(x) + 0.5, float(y) + 0.5)

        return (4.5, 4.5)

    def render_ascii_overview(self, data: CityMapData) -> str:
        """Renders an ASCII overview map of the generated metropolis for debugging/HUD."""
        lines = []
        header = f"=== ASTRA 3D CITY MAP [SEED: {data.seed}] ({data.width}x{data.height}) ==="
        lines.append(header)

        for y in range(data.height):
            row_chars = []
            for x in range(data.width):
                w = data.walls[y][x]
                f = data.floors[y][x]
                if w > 0:
                    row_chars.append("#")
                elif f == 7:  # WATER
                    row_chars.append("~")
                elif f == 5:  # PARK GRASS
                    row_chars.append("♣")
                elif f == 8:  # BRIDGE
                    row_chars.append("=")
                elif f in (1, 2, 3):  # ROADS
                    row_chars.append("·")
                else:
                    row_chars.append(" ")
            lines.append("".join(row_chars))

        lines.append(f"Landmarks ({len(data.landmarks)}):")
        for lm in data.landmarks:
            lines.append(f" - [{lm.icon}] {lm.name} ({lm.district}) at ({lm.x:.1f}, {lm.y:.1f})")
        return "\n".join(lines)
