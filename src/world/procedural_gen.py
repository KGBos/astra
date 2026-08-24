"""
Procedural Metropolis Generator v2 -- hierarchical roads, irregular blocks,
and life-sized districts for Astra 3D (M5 "Life-Sized World", Cycle B).

Layout model (1 tile = 1 m, default 320x320):
  1. Arterials (14 m wide: 2x5 travel lanes flanking a 2 m painted median,
     rendered by the floor-caster's centre dashes) every 40-56 m on both axes.
  2. Collectors (9 m wide: 2 lanes + parking rows) fill selected corridors
     between arterials so consecutive road centre-lines stay 16-24 m apart;
     corridors left open keep full super-block faces of up to ~42 m.
  3. Local lanes (5 m) cut through any open block face wider than 34 m.
  4. The resulting lattice yields irregular blocks (super-block faces land in
     the spec's 18-48 m band) that receive district-aware massing: tower
     podiums with setback cores, perimeter courtyards with service alleys,
     fine-grained parcel streetwalls, warehouse yards.
  5. Center-out zoning: downtown towers within ~90 m of centre, midrise ring
     out to ~180 m, industrial sprawl in far quadrant(s), a central park
     (>80x80 m), and a harbor front with quay walls, piers, and mooring
     bollards along one edge.

Everything is driven by a single seeded RNG: identical seeds produce
byte-identical walls/floors/districts grids.

Author: Darius Thorne (Procedural World & City Generation Specialist 📐)
"""

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union

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
    make_vending_machine_sprite,
)


class DistrictType(str, Enum):
    CYBER_DOWNTOWN = "CYBER-DOWNTOWN"
    FINANCIAL_CORE = "FINANCIAL CORE"
    NEON_ENTERTAINMENT = "NEON ENTERTAINMENT"
    HISTORIC_QUARTER = "HISTORIC BROWNSTONES"
    INDUSTRIAL_DOCKLANDS = "INDUSTRIAL DOCKLANDS"
    CENTRAL_PLAZA_PARK = "CENTRAL ASTRA PLAZA"
    WATERFRONT_MARINA = "WATERFRONT MARINA"


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

# Wall type ids (textures.py registry); comments give metered facade heights.
WALL_PERIMETER = 5          # 9 m concrete boundary
WALL_GLASS_TOWER = 1        # 40 m
WALL_NEON_TOWER = 2         # 60 m
WALL_BROWNSTONE = 3         # 11 m
WALL_STOREFRONT = 4         # 4 m podium / shopfront
WALL_WAREHOUSE = 5          # 9 m
WALL_HOTEL = 6              # 18 m
WALL_ARCOLOGY = 7           # 50 m
WALL_MEGASTRUCTURE = 8      # 45 m
WALL_MARINA_DOCK = 10       # 5 m quay

CLASS_ARTERIAL = "ARTERIAL"
CLASS_COLLECTOR = "COLLECTOR"
CLASS_LOCAL = "LOCAL"

# Facade palettes per district as (wall_type, weight). Height bands emerge
# from the metered textures: downtown 40-60 m, midrise ring 4-18 m, industry 9 m.
DISTRICT_PALETTES: Dict[str, List[Tuple[int, int]]] = {
    DistrictType.CYBER_DOWNTOWN.value: [(WALL_GLASS_TOWER, 3), (WALL_NEON_TOWER, 4),
                                        (WALL_ARCOLOGY, 2), (WALL_MEGASTRUCTURE, 2)],
    DistrictType.FINANCIAL_CORE.value: [(WALL_HOTEL, 3), (WALL_BROWNSTONE, 2),
                                        (WALL_MEGASTRUCTURE, 1)],
    DistrictType.NEON_ENTERTAINMENT.value: [(WALL_HOTEL, 3), (WALL_STOREFRONT, 2),
                                            (WALL_BROWNSTONE, 2)],
    DistrictType.HISTORIC_QUARTER.value: [(WALL_BROWNSTONE, 5), (WALL_STOREFRONT, 1)],
    DistrictType.INDUSTRIAL_DOCKLANDS.value: [(WALL_WAREHOUSE, 5)],
}

TOWER_TYPES = [WALL_GLASS_TOWER, WALL_NEON_TOWER, WALL_ARCOLOGY, WALL_MEGASTRUCTURE]


@dataclass
class Landmark:
    name: str
    x: float
    y: float
    district: str
    landmark_type: str  # "SKYSCRAPER", "MONUMENT", "PARK", "MARINA", "COMMERCIAL", "INDUSTRIAL"
    description: str
    icon: str = "★"
    foot_w: int = 0     # true footprint extent in metres (generator v2)
    foot_h: int = 0

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
class RoadSegment:
    """Measured road geometry for one road line (traffic/pedestrian contracts)."""
    axis: str            # "NS" or "EW"
    road_class: str      # CLASS_ARTERIAL | CLASS_COLLECTOR | CLASS_LOCAL
    center: int          # centre-line cell on the cross axis
    width: int           # full road width in metres (14 / 9 / 5 at city scale)
    start: int           # inclusive extent start along the road axis
    end: int             # inclusive extent end along the road axis
    name: str = ""


def build_road_lanes(segments: List[RoadSegment]) -> List[dict]:
    """Converts road segments into spawn-ready lane descriptors.

    Each entry carries the road class, metre width, continuous centre-line
    coordinate (metres), right-hand travel-lane offsets from that centre-line,
    and the inclusive along-axis span. Cruise classes map to 13/9/5 m/s for
    arterial/collector/local (consumed by the traffic retune in Cycle C).
    """
    lane_table = {
        CLASS_ARTERIAL: (-3.5, 3.5),     # 2x5 m lanes flanking a 2 m median
        CLASS_COLLECTOR: (-1.25, 1.25),  # 2x2.5 m lanes inside parking rows
        CLASS_LOCAL: (0.0,),
    }
    lanes = []
    for seg in segments:
        half_even = 0.0 if seg.width % 2 == 0 else 0.5
        lanes.append({
            "axis": seg.axis,
            "road_class": seg.road_class,
            "width_m": float(seg.width),
            "center_m": seg.center + half_even,
            "lane_offsets_m": lane_table.get(seg.road_class, (0.0,)),
            "span": (seg.start, seg.end),
            "name": seg.name,
        })
    return lanes


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
    road_segments: List[RoadSegment] = field(default_factory=list)


@dataclass
class _RoadLine:
    """Internal planning record for one road line on an axis."""
    center: int
    road_class: str
    width: int

    @property
    def lo(self) -> int:
        return self.center - self.width // 2

    @property
    def hi(self) -> int:
        return self.lo + self.width - 1


class ProceduralCityGenerator:
    """
    Life-sized metropolis synthesizer: hierarchical road network, irregular
    subdivided blocks, center-out district zoning with metered facades,
    landmarks with plazas, and measured road-lane geometry -- all deterministic
    under a single seeded RNG.
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
        ("Neo-Ramen Night Market", "COMMERCIAL", "A vibrant alleyway market lined with amber neon ramen stalls and cyber-cafes."),
        ("Old Brownstone Brewery", "COMMERCIAL", "Historic brick landmark preserved amidst the rising neon megastructures."),
        ("Hyperion Power Substation", "INDUSTRIAL", "Heavy industrial transformers and high-voltage cooling silos."),
        ("Dock 42 Cargo Terminal", "INDUSTRIAL", "Automated container cranes and heavy concrete freight warehouses."),
        ("Zenith Glass Conservatory", "PARK", "Lush botanical greenhouse oasis surrounded by verdant flora."),
        ("Solaria Deepwater Marina", "MARINA", "The bustling coastal docklands with illuminated mooring piers."),
    ]

    def __init__(self):
        pass

    @staticmethod
    def normalize_seed(seed: Optional[Union[int, str]]) -> int:
        if seed is None:
            return random.randint(100000, 999999)
        if isinstance(seed, str):
            # Deterministic hash
            h = 0
            for char in seed:
                h = (h * 31 + ord(char)) & 0xFFFFFFFF
            return h
        return int(seed)

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def generate(
        self,
        seed: Optional[Union[int, str]] = None,
        width: int = 320,
        height: int = 320,
        preset: str = "DEFAULT"
    ) -> CityMapData:
        """Generates a complete deterministic life-sized city layout."""
        int_seed = self.normalize_seed(seed)
        rng = random.Random(int_seed)
        sx, sy = width / 320.0, height / 320.0

        walls = [[0 for _ in range(width)] for _ in range(height)]
        floors = [[FLOOR_SIDEWALK for _ in range(width)] for _ in range(height)]
        districts: List[List[str]] = [["" for _ in range(width)] for _ in range(height)]

        for x in range(width):
            walls[0][x] = WALL_PERIMETER
            walls[height - 1][x] = WALL_PERIMETER
        for y in range(height):
            walls[y][0] = WALL_PERIMETER
            walls[y][width - 1] = WALL_PERIMETER

        # 1. Road hierarchy planning (arterial / collector / local lines).
        # With a harbor, the easternmost NS arterial is anchored so its band
        # crosses the water: the advertised bridges always materialize.
        has_marina = width >= 40 and height >= 40
        water_x0 = width - 1 - max(3, round(16 * sx))
        ns_lines = self._plan_axis(
            width, sx, rng,
            anchor=self._harbor_bridge_anchor(width, sx, water_x0, has_marina, rng))
        ew_lines = self._plan_axis(height, sy, rng, reserve_local=True)

        # 2. Feature zones: central park rectangle + harbor front band.
        # Hierarchy floors are satisfied BEFORE the park so the green's
        # candidate selection knows exactly what pruning may take away.
        self._ensure_hierarchy_floors(width, height, sx, ns_lines, ew_lines, rng)

        park_rect = self._plan_park_rect(width, height, sx, sy, rng,
                                         ns_lines, ew_lines)

        ns_lines.sort(key=lambda ln: ln.center)
        ew_lines.sort(key=lambda ln: ln.center)
        avenue_names, street_names = self._assign_road_names(ns_lines, ew_lines, rng)

        # 3. Center-out district zoning
        self._assign_districts(
            width, height, districts, rng, park_rect, water_x0, has_marina
        )

        # 4. Carve the road grid (arterials, collectors, locals, intersections)
        self._carve_roads(width, height, ns_lines, ew_lines, walls, floors)

        # 5. Harbor front: water basin, quay walls, bridge spans, piers
        props: List[Sprite] = []
        landmarks: List[Landmark] = []
        pier_ys, quay_x = self._carve_harbor(
            width, height, ns_lines, ew_lines, walls, floors, districts,
            water_x0, sx, sy, rng
        )
        if has_marina:
            self._add_mooring_props(quay_x, pier_ys, walls, floors, props)

        # 6. Irregular blocks from the lattice, each receiving district massing
        self._mass_city(
            width, height, ns_lines, ew_lines, walls, floors, districts,
            props, park_rect, water_x0, has_marina, sx, rng
        )

        # 7. Landmarks with plazas (true footprints, spaced apart)
        self._place_landmarks(
            width, height, ns_lines, ew_lines, walls, floors, districts,
            props, landmarks, water_x0, has_marina, pier_ys, sx, rng
        )

        # 8. Street furniture scaled to metres
        self._populate_street_props(ns_lines, ew_lines, width, height, walls, props, rng)

        # 9. Road graph + traffic lights at signalized crossings
        traffic_light_coords, road_graph = self._build_graph_and_lights(
            ns_lines, ew_lines, districts, avenue_names, street_names,
            water_x0, has_marina
        )

        segments = (
            [RoadSegment("NS", ln.road_class, ln.center, ln.width, 1, height - 2,
                         avenue_names.get(ln.center, ""))
             for ln in ns_lines]
            + [RoadSegment("EW", ln.road_class, ln.center, ln.width, 1, width - 2,
                           street_names.get(ln.center, ""))
               for ln in ew_lines]
        )
        if has_marina:
            for seg in segments:
                if seg.axis == "EW":
                    seg.end = min(seg.end, water_x0 - 2)

        spawn_pos = self._find_safe_spawn_pos(width, height, floors, walls,
                                              [ln.center for ln in ns_lines])

        return CityMapData(
            width=width,
            height=height,
            seed=int_seed,
            walls=walls,
            floors=floors,
            districts=districts,
            ns_road_cols=[ln.center for ln in ns_lines],
            ew_road_rows=[ln.center for ln in ew_lines],
            traffic_light_coords=traffic_light_coords,
            avenue_names=avenue_names,
            street_names=street_names,
            landmarks=landmarks,
            road_graph=road_graph,
            props=props,
            spawn_pos=spawn_pos,
            road_segments=segments,
        )

    # ------------------------------------------------------------------
    # Road hierarchy planning
    # ------------------------------------------------------------------

    def _harbor_bridge_anchor(self, width: int, sx: float, water_x0: int,
                              has_marina: bool, rng: random.Random) -> Optional[int]:
        """Centre-line for a guaranteed harbour-bridge arterial: an NS arterial
        whose whole 14 m band lies inside the flooded band, so `_carve_harbor`
        always converts it into FLOOR_BRIDGE. None when no harbor fits."""
        if not has_marina:
            return None
        art_w = max(2, round(14 * sx))
        lo_off = art_w // 2
        hi_off = art_w - 1 - lo_off
        band_lo = water_x0 - 1                      # first flooded column
        # Straddle the quay: the majority of the band reaches into the water
        # while >= 2 columns stay on land, keeping the bridge arterial tied
        # into the mainland grid (no orphaned island segment).
        c_min = band_lo - hi_off + max(2, art_w // 2)
        c_max = min(band_lo + lo_off - 2, width - 2 - hi_off)
        if c_min > c_max:
            c_min = band_lo - hi_off                # degenerate widths: touch water
            c_max = width - 2 - hi_off
            if c_min > c_max:
                return None
        return max(c_min, min(c_max, (c_min + c_max) // 2 + rng.randint(-2, 2)))

    def _plan_axis(self, dim: int, scale: float, rng: random.Random,
                   anchor: Optional[int] = None,
                   reserve_local: bool = False) -> List[_RoadLine]:
        """Plans one axis' road centre-lines: arterials every 40-56 m (scaled),
        collectors keeping the 16-24 m centre-line rhythm in selected corridors,
        and local lanes through open corridors wider than 34 m.

        With an `anchor`, arterials are planned east-to-west starting from the
        anchored harbour-bridge arterial so every consecutive centre-line gap
        keeps the 40-56 m rhythm by construction and the bridge arterial's
        collector relationships stay intact. With `reserve_local`, the first
        wide corridor is forced onto the local branch -- that corridor stays
        collector-free and anchors the axis' local-lane contract."""
        art_w = max(2, round(14 * scale))
        col_w = max(1, round(9 * scale))
        loc_w = max(1, round(5 * scale))

        step_lo = max(8, round(40 * scale))
        step_hi = max(step_lo + 1, round(56 * scale))
        if anchor is not None:
            arterial_centers = [anchor]
            pos = anchor
            edge = max(8, round(dim * 0.07))
            while True:
                pos -= rng.randint(step_lo, step_hi)
                if pos <= edge:
                    break
                arterial_centers.append(pos)
        else:
            pos = round(dim * (0.07 + 0.05 * rng.random()))
            arterial_centers: List[int] = []
            limit = dim - max(3, round(0.05 * dim))
            while pos < limit:
                arterial_centers.append(pos)
                pos += rng.randint(step_lo, step_hi)
            if not arterial_centers:
                arterial_centers = [dim // 2]

        lines = [_RoadLine(c, CLASS_ARTERIAL, art_w) for c in arterial_centers]

        # Interior corridors between consecutive arterials only; the two edge
        # margins stay as open low-rise fringe beside the perimeter wall.
        ordered = sorted(arterial_centers)
        margin_g = max(4, round(6 * scale))
        wide_gate = max(12, round(34 * scale))
        forced_local_done = not reserve_local
        for i in range(len(ordered) - 1):
            a, b = ordered[i], ordered[i + 1]
            corridor_lo = a - art_w // 2 + art_w      # first free cell past band a
            corridor_hi = b - art_w // 2 - 1          # last free cell before band b
            free = corridor_hi - corridor_lo + 1
            if free < col_w + 2 * margin_g:
                continue
            if not forced_local_done and free > wide_gate:
                # Reserved local-lane corridor: never carries collectors, so
                # the open-corridor contract has a guaranteed holder.
                self._maybe_add_local(corridor_lo, corridor_hi, loc_w, scale,
                                      rng, lines)
                forced_local_done = True
                continue
            if rng.random() < 0.62:
                self._add_collectors(a, b, col_w, scale, rng, lines)
            else:
                self._maybe_add_local(corridor_lo, corridor_hi, loc_w, scale,
                                      rng, lines)

        lines.sort(key=lambda ln: ln.center)
        return lines

    @staticmethod
    def _reserved_local_corridor(lines: List[_RoadLine], scale: float):
        """The (a, b) arterial centres of the axis' reserved local-lane
        corridor -- the first wide corridor in ascending order, matching the
        forcing rule in _plan_axis. None when the axis has none."""
        art_w = max(2, round(14 * scale))
        wide_gate = max(12, round(34 * scale))
        margin_g = max(4, round(6 * scale))
        col_w = max(1, round(9 * scale))
        arts = sorted(ln.center for ln in lines if ln.road_class == CLASS_ARTERIAL)
        for a, b in zip(arts, arts[1:]):
            corridor_lo = a - art_w // 2 + art_w
            corridor_hi = b - art_w // 2 - 1
            free = corridor_hi - corridor_lo + 1
            if free < col_w + 2 * margin_g:
                continue
            if free > wide_gate:
                return (a, b)
        return None

    def _add_collectors(self, a: int, b: int, col_w: int, scale: float,
                        rng: random.Random, lines: List[_RoadLine]):
        """Places 1-2 collector centre-lines between arterial centres a < b so
        every consecutive centre-line gap stays within [16, 24] m (scaled)."""
        g = b - a
        gap_min = max(6, round(16 * scale))
        gap_max = round(24 * scale)
        k = 1 if g <= 2 * gap_max else 2
        jmax = max(1, round(3 * scale))
        base = g / (k + 1)

        prev = 0
        for i in range(1, k + 1):
            remaining = k - i + 1
            lo_o = max(prev + gap_min, g - remaining * gap_max)
            hi_o = min(prev + gap_max, g - remaining * gap_min)
            if lo_o > hi_o:
                break
            offset = round(base * i) + rng.randint(-jmax, jmax)
            offset = max(lo_o, min(hi_o, offset))
            lines.append(_RoadLine(a + offset, CLASS_COLLECTOR, col_w))
            prev = offset

    def _maybe_add_local(self, lo: int, hi: int, loc_w: int, scale: float,
                         rng: random.Random, lines: List[_RoadLine]):
        """Cuts a 5 m local lane through any open block face wider than 34 m."""
        free = hi - lo + 1
        wide_gate = max(12, round(34 * scale))
        if free <= wide_gate:
            return
        jitter = rng.randint(-max(1, free // 10), max(1, free // 10))
        center = lo + free // 2 + jitter
        center = max(lo + loc_w, min(hi - loc_w, center))
        lines.append(_RoadLine(center, CLASS_LOCAL, loc_w))

    def _ensure_hierarchy_floors(self, width, height, scale,
                                 ns_lines, ew_lines, rng):
        """City-wide hierarchy minimums, applied BEFORE the park is planned:
        enough collectors to survive park pruning (>= 6 remain) plus a local
        lane on a wide open corridor. Park selection later refuses candidates
        whose pruning would break these."""
        collector_target = 9   # 6 contract + slack for park-prune losses
        art_w = max(2, round(14 * scale))
        col_w = max(1, round(9 * scale))
        loc_w = max(1, round(5 * scale))
        margin = max(4, round(6 * scale))
        gap_min = max(6, round(16 * scale))
        gap_max = round(24 * scale)
        wide_gate = max(12, round(34 * scale))

        def corridors(lines):
            arts = sorted(ln.center for ln in lines if ln.road_class == CLASS_ARTERIAL)
            out = []
            for a, b in zip(arts, arts[1:]):
                c_lo = a - art_w // 2 + art_w
                c_hi = b - art_w // 2 - 1
                inner = [ln for ln in lines if a < ln.center < b]
                out.append((a, b, c_lo, c_hi, inner))
            return out

        def insert_collector(lines, a, b, c_lo, c_hi, axis):
            """Places one rhythm-valid collector between arterials a < b,
            clear of local bands and the central landmark cross."""
            half = col_w // 2
            blocked = [(ln.lo - 1 - half, ln.hi + 1 + half) for ln in lines
                       if a < ln.center < b]
            centre = (width if axis == 0 else height) // 2
            blocked.append((centre - max(24, round(40 * scale)),
                            centre + max(24, round(40 * scale))))
            lo_c = max(a + gap_min, c_lo + col_w // 2)
            hi_c = min(b - gap_min, c_hi - col_w // 2)
            if lo_c > hi_c:
                return False
            mid = (lo_c + hi_c) // 2
            offsets = [mid]
            offsets += [c for d in range(1, hi_c - lo_c + 1)
                        for c in (mid + d, mid - d)]
            for off in offsets:
                if off < lo_c or off > hi_c:
                    continue
                # Rhythm contract needs one side inside [gap_min, gap_max].
                if not (a + gap_min <= off <= a + gap_max
                        or b - gap_max <= off <= b - gap_min):
                    continue
                if any(zlo <= off <= zhi for zlo, zhi in blocked):
                    continue
                lines.append(_RoadLine(off, CLASS_COLLECTOR, col_w))
                return True
            return False

        def collector_count():
            return sum(1 for ls in (ns_lines, ew_lines)
                       for ln in ls if ln.road_class == CLASS_COLLECTOR)

        while collector_count() < collector_target:
            progressed = False
            for ax in (0, 1):
                if collector_count() >= collector_target:
                    break
                lines = ns_lines if ax == 0 else ew_lines
                for a, b, c_lo, c_hi, inner in corridors(lines):
                    if inner:
                        continue  # corridor already carries a line
                    before = len(lines)
                    if insert_collector(lines, a, b, c_lo, c_hi, axis=ax):
                        progressed = True
                        break
            if not progressed:
                break  # every open corridor resists a rhythm-valid collector

        # Local-lane floor: exactly one 5 m lane in some wide collector-free
        # corridor. Forced during planning via reserve_local; repaired here
        # only when that corridor went missing (tiny maps).
        def has_qualifying_local(lines):
            arts = sorted(ln.center for ln in lines
                          if ln.road_class == CLASS_ARTERIAL)
            for ln in lines:
                if ln.road_class != CLASS_LOCAL:
                    continue
                prev_a = [a for a in arts if a < ln.center]
                next_a = [b for b in arts if b > ln.center]
                if not prev_a or not next_a:
                    continue
                a, b = prev_a[-1], next_a[0]
                if any(a < s.center < b and s.road_class == CLASS_COLLECTOR
                       for s in lines):
                    continue
                if b - a > wide_gate + art_w:
                    return True
            return False

        if not any(has_qualifying_local(ls) for ls in (ns_lines, ew_lines)):
            best = None
            for ax, lines in ((0, ns_lines), (1, ew_lines)):
                for a, b, c_lo, c_hi, inner in corridors(lines):
                    if inner or b - a - art_w <= wide_gate:
                        continue
                    if best is None or b - a > best[0]:
                        best = (b - a, ax, lines, c_lo, c_hi)
            if best is not None:
                _, _, lines, c_lo, c_hi = best
                self._maybe_add_local(c_lo, c_hi, loc_w, scale, rng, lines)

    def _assign_road_names(self, ns_lines, ew_lines, rng) -> Tuple[Dict[int, str], Dict[int, str]]:
        avenues = list(self.AVENUE_POOLS)
        streets = list(self.STREET_POOLS)
        rng.shuffle(avenues)
        rng.shuffle(streets)
        avenue_names: Dict[int, str] = {}
        for i, ln in enumerate(ns_lines):
            pool = avenues if ln.road_class == CLASS_ARTERIAL else streets
            avenue_names[ln.center] = pool[i % len(pool)]
        street_names: Dict[int, str] = {}
        for i, ln in enumerate(ew_lines):
            pool = avenues if ln.road_class == CLASS_ARTERIAL else streets
            street_names[ln.center] = pool[(i + 3) % len(pool)]
        return avenue_names, street_names

    # ------------------------------------------------------------------
    # Zones and districts
    # ------------------------------------------------------------------

    def _plan_park_rect(self, width, height, sx, sy, rng,
                        ns_lines, ew_lines):
        """Central park (>80x80 m at city scale) spanning whole arterial
        corridors east of centre. Collectors and locals inside the rect are
        removed -- crossing arterials stay as park transverses -- so the lawn
        is contiguous instead of shredded into traffic slivers."""
        ns_arts = [ln for ln in ns_lines if ln.road_class == CLASS_ARTERIAL]
        ew_arts = [ln for ln in ew_lines if ln.road_class == CLASS_ARTERIAL]
        water_cap = width - 2 - max(3, round(16 * sx)) - 6

        def corridor_span(arts, i, j, target, cap):
            """Extends j until [arts[i].hi, arts[j].lo] clears the target."""
            while j < len(arts):
                x0 = arts[i].hi + 1
                x1 = min(arts[j].lo - 1, cap)
                if x1 - x0 + 1 >= target:
                    return x0, x1
                j += 1
            return None

        tx = max(12, round(82 * sx))
        ty = max(12, round(82 * sy))
        if len(ns_arts) >= 2 and len(ew_arts) >= 2:
            art_w = max(2, round(14 * sx))

            def keeps_reserved(rx0, rx1, ry0, ry1):
                """The reserved local-lane corridor must survive the park
                unflagged: a corridor within one arterial band of the green
                reads as a park transverse, breaking the hierarchy contract."""
                pad = art_w
                res = self._reserved_local_corridor(ew_lines, sy)
                if res is None:
                    return True
                ac, bc = res
                return not (ac <= ry1 + pad and bc >= ry0 - pad)

            def keeps_collector_floor(rx0, rx1, ry0, ry1):
                """Pruning must leave >= 6 collectors city-wide."""
                kept = sum(1 for ln in ns_lines
                           if ln.road_class == CLASS_COLLECTOR
                           and not (rx0 <= ln.center <= rx1))
                kept += sum(1 for ln in ew_lines
                            if ln.road_class == CLASS_COLLECTOR
                            and not (ry0 <= ln.center <= ry1))
                return kept >= 6

            # Prefer corridors nearest the ideal axes, but accept any
            # arterial-bounded pair that clears the size targets so the park
            # never silently degrades to the small-map fallback on dense or
            # east-anchored arterial layouts.
            xi_order = sorted(range(len(ns_arts)),
                              key=lambda k: abs(ns_arts[k].center - (width / 2 - 24)))
            yi_order = sorted(range(len(ew_arts)),
                              key=lambda k: abs(ew_arts[k].center - height / 2))
            best = None
            for xi in xi_order:
                xr = corridor_span(ns_arts, xi, xi + 1, tx, water_cap)
                if xr is None:
                    continue
                for yi in yi_order:
                    yr = corridor_span(ew_arts, yi, yi + 1, ty, height)
                    if yr is None:
                        continue
                    # Cap over-wide spans: every extra corridor becomes lawn
                    # that the hierarchy floors have to survive around.
                    max_span_x = tx + 18
                    x0 = xr[0]
                    x1 = min(xr[1], x0 + max_span_x - 1)
                    max_span_y = ty + 18
                    y0 = yr[0]
                    y1 = min(yr[1], y0 + max_span_y - 1)
                    centre_hit = (x0 <= width // 2 <= x1
                                  and y0 <= height // 2 <= y1)
                    if width < 100 and centre_hit:
                        continue  # tiny maps: the centre stays downtown ground
                    if not keeps_reserved(x0, x1, y0, y1):
                        continue
                    if not keeps_collector_floor(x0, x1, y0, y1):
                        continue
                    key = ((x1 - x0 + 1) * (y1 - y0 + 1),
                           -int(centre_hit), -xi, -yi)
                    if best is None or key > best[0]:
                        best = (key, (x0, y0, x1, y1))
            if best is not None:
                x0, y0, x1, y1 = best[1]

                def through(lo, hi, center):
                    return lo <= center <= hi

                ns_lines[:] = [ln for ln in ns_lines
                               if ln.road_class == CLASS_ARTERIAL
                               or not through(x0, x1, ln.center)]
                ew_lines[:] = [ln for ln in ew_lines
                               if ln.road_class == CLASS_ARTERIAL
                               or not through(y0, y1, ln.center)]
                return (x0, y0, x1, y1)

        # Small-map fallback: modest seeded green beside the core.
        pw = max(12, round(rng.uniform(84, 94) * sx))
        ph = max(12, round(rng.uniform(84, 94) * sy))
        cx, cy = width // 2, height // 2
        x0 = cx + max(6, round(8 * sx))
        y0 = cy - ph // 2 + rng.randint(-4, 4)
        x1 = min(x0 + pw - 1, width - 3 - max(3, round(16 * sx)))
        y0, y1 = max(2, y0), min(height - 3, y0 + ph - 1)
        if x1 - x0 + 1 < pw // 2 or y1 - y0 + 1 < ph // 2:
            return None
        return (x0, y0, x1, y1)

    def _assign_districts(self, width, height, districts, rng, park_rect,
                          water_x0, has_marina):
        cx, cy = width / 2.0, height / 2.0
        s_avg = (width + height) / 640.0
        r_downtown = round(90 * s_avg)
        r_midrise = round(180 * s_avg)

        quads = [(False, False), (True, False), (False, True), (True, True)]
        rng.shuffle(quads)
        n_industrial = 2 if rng.random() < 0.5 else 1
        industrial_quads = set(quads[:n_industrial])
        far_fill = {
            (True, False): DistrictType.FINANCIAL_CORE.value,
            (False, False): DistrictType.NEON_ENTERTAINMENT.value,
            (True, True): DistrictType.HISTORIC_QUARTER.value,
            (False, True): DistrictType.FINANCIAL_CORE.value,
        }
        midring = dict(far_fill)
        midring[(False, True)] = rng.choice([
            DistrictType.FINANCIAL_CORE.value,
            DistrictType.NEON_ENTERTAINMENT.value,
            DistrictType.HISTORIC_QUARTER.value,
        ])

        for y in range(height):
            dy = y - cy
            row_d = districts[y]
            for x in range(width):
                if has_marina and x >= water_x0 - 1:
                    row_d[x] = DistrictType.WATERFRONT_MARINA.value
                    continue
                if park_rect and park_rect[0] <= x <= park_rect[2] \
                        and park_rect[1] <= y <= park_rect[3]:
                    row_d[x] = DistrictType.CENTRAL_PLAZA_PARK.value
                    continue
                r = math.hypot(x - cx, dy)
                quad = (x >= cx, y >= cy)
                if r <= r_downtown:
                    row_d[x] = DistrictType.CYBER_DOWNTOWN.value
                elif r <= r_midrise:
                    row_d[x] = midring[quad]
                elif quad in industrial_quads:
                    row_d[x] = DistrictType.INDUSTRIAL_DOCKLANDS.value
                else:
                    row_d[x] = far_fill[quad]

    # ------------------------------------------------------------------
    # Road carving
    # ------------------------------------------------------------------

    def _carve_roads(self, width, height, ns_lines, ew_lines, walls, floors):
        for ln in ns_lines:
            lo, hi = max(1, ln.lo), min(width - 2, ln.hi)
            for y in range(1, height - 1):
                row_f = floors[y]
                row_w = walls[y]
                for x in range(lo, hi + 1):
                    row_f[x] = FLOOR_ROAD_NS
                    row_w[x] = 0
        for ln in ew_lines:
            for y in range(max(1, ln.lo), min(height - 2, ln.hi) + 1):
                row_f = floors[y]
                row_w = walls[y]
                for x in range(1, width - 1):
                    if row_f[x] == FLOOR_ROAD_NS:
                        row_f[x] = FLOOR_INTERSECTION
                    else:
                        row_f[x] = FLOOR_ROAD_EW
                    row_w[x] = 0

    # ------------------------------------------------------------------
    # Harbor front
    # ------------------------------------------------------------------

    def _carve_harbor(self, width, height, ns_lines, ew_lines, walls, floors, districts,
                      water_x0, sx, sy, rng) -> Tuple[List[int], int]:
        """Floods the eastern band with water, raises quay walls, converts NS
        roads crossing the band into bridges, and cuts wooden mooring piers.
        Returns the pier centre-row coordinates and the quay column (shifted
        west of any bridge band so the promenade stays continuous)."""
        if not has_marina_guard(width, height):
            return [], water_x0 - 1
        ns_band_cols = set()
        for ln in ns_lines:
            ns_band_cols.update(range(max(1, ln.lo), min(width - 2, ln.hi) + 1))

        water_y0, water_y1 = 2, height - 3
        for y in range(water_y0, water_y1 + 1):
            row_f = floors[y]
            row_w = walls[y]
            row_d = districts[y]
            for x in range(max(1, water_x0 - 1), width - 1):
                row_d[x] = DistrictType.WATERFRONT_MARINA.value
                if x in ns_band_cols:
                    row_f[x] = FLOOR_BRIDGE
                else:
                    row_f[x] = FLOOR_WATER
                row_w[x] = 0

        # The bridge arterial straddles the shoreline, so the quay promenade
        # steps one block west of it and runs along the waterfront -- keeping
        # every EW street opening clear so the grid stays connected.
        quay_x = water_x0 - 1
        while quay_x > 1 and quay_x in ns_band_cols:
            quay_x -= 1
        ew_band_rows = set()
        for ln in ew_lines:
            ew_band_rows.update(range(max(1, ln.lo), min(height - 2, ln.hi) + 1))
        for y in range(water_y0, water_y1 + 1):
            if y in ew_band_rows:
                continue  # open street mouth to the quay
            walls[y][quay_x] = WALL_MARINA_DOCK
            floors[y][quay_x] = FLOOR_WOOD_DECK
            districts[y][quay_x] = DistrictType.WATERFRONT_MARINA.value

        pier_len = max(4, round(9 * sy))
        candidates = [y for y in range(water_y0 + 8, water_y1 - 8, 24)
                      if all(abs(y - ln.center) > 10 for ln in ew_lines)]
        rng.shuffle(candidates)
        pier_ys = sorted(candidates[:2])
        for py in pier_ys:
            for y in range(py - 2, py + 3):
                if not (water_y0 <= y <= water_y1):
                    continue
                for x in range(quay_x, min(width - 2, quay_x + pier_len) + 1):
                    floors[y][x] = FLOOR_WOOD_DECK
                    walls[y][x] = 0
        return pier_ys, quay_x

    def _add_mooring_props(self, quay_x, pier_ys, walls, floors, props):
        """Mooring bollards along the quay promenade and pier heads."""
        for py in pier_ys:
            tip_x = quay_x
            run = 0
            for x in range(quay_x, len(floors[0]) - 1):
                if floors[py][x] != FLOOR_WOOD_DECK:
                    break
                tip_x = x
                run += 1
            if run > 2:
                props.append(make_bollard_sprite(tip_x - 0.5, py - 1.5))
                props.append(make_bollard_sprite(tip_x - 0.5, py + 1.5))
        step = max(9, len(floors) // 26)
        for y in range(6, len(floors) - 6, step):
            if walls[y][quay_x] == WALL_MARINA_DOCK and quay_x - 1 >= 1 \
                    and floors[y][quay_x] == FLOOR_WOOD_DECK:
                props.append(make_bollard_sprite(quay_x - 0.5, y + 0.5))

    # ------------------------------------------------------------------
    # Block massing
    # ------------------------------------------------------------------

    def _block_spans(self, lines: List[_RoadLine], dim: int) -> List[Tuple[int, int]]:
        """Block extents in the free space between consecutive road bands."""
        bands = sorted((max(1, ln.lo), min(dim - 2, ln.hi)) for ln in lines)
        spans = []
        cur = 1
        for blo, bhi in bands:
            if blo - 1 >= cur:
                spans.append((cur, blo - 1))
            cur = max(cur, bhi + 1)
        if cur <= dim - 2:
            spans.append((cur, dim - 2))
        return spans

    def _mass_city(self, width, height, ns_lines, ew_lines, walls, floors, districts,
                   props, park_rect, water_x0, has_marina, sx, rng):
        x_spans = self._block_spans(ns_lines, width)
        y_spans = self._block_spans(ew_lines, height)
        inset = max(1, round(2 * sx))

        for y0, y1 in y_spans:
            for x0, x1 in x_spans:
                if x1 - x0 + 1 < 3 or y1 - y0 + 1 < 3:
                    continue
                bx0, by0 = x0 + inset, y0 + inset
                bx1, by1 = x1 - inset, y1 - inset
                if bx1 - bx0 + 1 < 3 or by1 - by0 + 1 < 3:
                    continue
                cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
                district = districts[cy][cx]
                if has_marina and cx >= water_x0 - 1:
                    continue  # open water / quay handled by the harbor carve
                if district == DistrictType.CENTRAL_PLAZA_PARK.value:
                    self._mass_park_block(bx0, by0, bx1, by1, walls, floors, props, rng)
                    continue
                if district == DistrictType.WATERFRONT_MARINA.value:
                    continue
                self._mass_urban_block(bx0, by0, bx1, by1, district, walls, floors, props, rng)

    def _mass_park_block(self, x0, y0, x1, y1, walls, floors, props, rng):
        """Park lawn with crossed promenade paths, metered trees, and benches."""
        mid_x = (x0 + x1) / 2.0
        mid_y = (y0 + y1) / 2.0
        for y in range(y0, y1 + 1):
            row_f = floors[y]
            row_w = walls[y]
            for x in range(x0, x1 + 1):
                row_w[x] = 0
                on_path = abs(x - mid_x) < 1.5 or abs(y - mid_y) < 1.5
                row_f[x] = FLOOR_PLAZA_TILES if on_path else FLOOR_PARK_GRASS
        area = (x1 - x0 + 1) * (y1 - y0 + 1)
        for _ in range(max(1, area // 110)):
            tx = rng.uniform(x0 + 0.5, x1 + 0.5)
            ty = rng.uniform(y0 + 0.5, y1 + 0.5)
            if floors[int(ty)][int(tx)] == FLOOR_PARK_GRASS:
                props.append(make_tree_sprite(tx, ty))
        if (x1 - x0) >= 8 and (y1 - y0) >= 8:
            props.append(make_park_bench_sprite(mid_x - 2.0, mid_y + 2.5))
            props.append(make_park_bench_sprite(mid_x + 2.0, mid_y - 2.5))

    def _pick_facade(self, district: str, rng: random.Random) -> int:
        palette = DISTRICT_PALETTES.get(district, DISTRICT_PALETTES[DistrictType.CYBER_DOWNTOWN.value])
        types = [t for t, _ in palette]
        weights = [w for _, w in palette]
        return rng.choices(types, weights=weights)[0]

    def _mass_urban_block(self, x0, y0, x1, y1, district, walls, floors, props, rng):
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        roll = rng.random()
        if district == DistrictType.CYBER_DOWNTOWN.value:
            if roll < 0.5 and bw >= 10 and bh >= 10:
                self._mass_tower(x0, y0, x1, y1, walls, props, rng)
            elif roll < 0.78 and bw >= 12 and bh >= 12:
                self._mass_courtyard(x0, y0, x1, y1, district, walls, floors, props, rng)
            else:
                self._mass_parcels(x0, y0, x1, y1, district, walls, floors, props, rng)
        elif district == DistrictType.INDUSTRIAL_DOCKLANDS.value:
            self._mass_warehouse(x0, y0, x1, y1, walls, floors, props, rng)
        else:
            if roll < 0.52:
                self._mass_parcels(x0, y0, x1, y1, district, walls, floors, props, rng)
            elif roll < 0.82 and bw >= 12 and bh >= 12:
                self._mass_courtyard(x0, y0, x1, y1, district, walls, floors, props, rng)
            else:
                self._mass_slab(x0, y0, x1, y1, district, walls, rng)

    def _fill_ring(self, x0, y0, x1, y1, thickness, wall_type, walls):
        for y in range(y0, y1 + 1):
            row = walls[y]
            for x in range(x0, x1 + 1):
                if (x < x0 + thickness or x > x1 - thickness
                        or y < y0 + thickness or y > y1 - thickness):
                    row[x] = wall_type

    def _mass_tower(self, x0, y0, x1, y1, walls, props, rng):
        """Podium ring (4-18 m storefront/hotel) with an inset tall core;
        stacked wall types approximate the upper-floor setback."""
        podium = WALL_STOREFRONT if rng.random() < 0.6 else WALL_HOTEL
        core_type = rng.choices(TOWER_TYPES, weights=[3, 4, 2, 2])[0]
        self._fill_ring(x0, y0, x1, y1, 1, podium, walls)
        # Inset 2 keeps the tall core flush behind the podium ring so the
        # setback reads as stacked massing at street level.
        cx0, cy0 = x0 + 2, y0 + 2
        cx1, cy1 = x1 - 2, y1 - 2
        if cx1 - cx0 + 1 >= 5 and cy1 - cy0 + 1 >= 5:
            cap_w = min(cx1 - cx0 + 1, 23)
            cap_h = min(cy1 - cy0 + 1, 23)
            tx0 = cx0 + rng.randint(0, (cx1 - cx0 + 1) - cap_w)
            ty0 = cy0 + rng.randint(0, (cy1 - cy0 + 1) - cap_h)
            tx1, ty1 = tx0 + cap_w - 1, ty0 + cap_h - 1
            for y in range(ty0, ty1 + 1):
                row = walls[y]
                for x in range(tx0, tx1 + 1):
                    row[x] = core_type
            # Hollow the core into a lobby ring (doorway-detectable mass)
            for y in range(ty0 + 1, ty1):
                row = walls[y]
                for x in range(tx0 + 1, tx1):
                    row[x] = 0
            if rng.random() < 0.4:
                props.append(make_vending_machine_sprite(
                    tx0 - 1.5, ty1 + 1.5, facing_angle=math.pi))
        else:
            for y in range(y0 + 1, y1):
                row = walls[y]
                for x in range(x0 + 1, x1):
                    row[x] = podium

    def _mass_courtyard(self, x0, y0, x1, y1, district, walls, floors, props, rng):
        """Perimeter courtyard block with cobbled yard and optional alley cross."""
        facade = self._pick_facade(district, rng)
        thickness = 2 if min(x1 - x0, y1 - y0) >= 16 and rng.random() < 0.5 else 1
        self._fill_ring(x0, y0, x1, y1, thickness, facade, walls)
        ix0, iy0, ix1, iy1 = x0 + thickness, y0 + thickness, x1 - thickness, y1 - thickness
        for y in range(iy0, iy1 + 1):
            row_f = floors[y]
            for x in range(ix0, ix1 + 1):
                row_f[x] = FLOOR_COBBLESTONE
        if (x1 - x0) >= 22 and (y1 - y0) >= 22:
            mx, my = (ix0 + ix1) // 2, (iy0 + iy1) // 2
            for y in range(iy0, iy1 + 1):
                walls[y][mx] = 0
                floors[y][mx] = FLOOR_COBBLESTONE
            for x in range(ix0, ix1 + 1):
                walls[my][x] = 0
                floors[my][x] = FLOOR_COBBLESTONE
            props.append(make_dumpster_sprite(mx + 0.5, iy0 + 1.5))
        elif rng.random() < 0.45:
            props.append(make_fountain_sprite((ix0 + ix1) / 2.0 + 0.5,
                                              (iy0 + iy1) / 2.0 + 0.5))

    def _parcel_grid(self, x0, y0, x1, y1, pmin, pmax, rng):
        """Splits [x0..x1]x[y0..y1] into parcel rects separated by 1 m gaps."""
        def split_axis(lo, hi):
            out = []
            cur = lo
            while cur <= hi:
                end = min(hi, cur + rng.randint(pmin, pmax) - 1)
                if hi - end < pmin:
                    end = hi
                out.append((cur, end))
                cur = end + 2  # the 1 m gap becomes sidewalk
            return out
        rects = []
        for (by0, by1) in split_axis(y0, y1):
            for (bx0, bx1) in split_axis(x0, x1):
                if bx1 - bx0 >= 2 and by1 - by0 >= 2:
                    rects.append((bx0, by0, bx1, by1))
        return rects

    def _mass_parcels(self, x0, y0, x1, y1, district, walls, floors, props, rng):
        """Fine-grained streetwall: 5-9 m parcels with sidewalk gaps -- dozens
        of doorway-sized enterable masses per block."""
        for (ax0, ay0, ax1, ay1) in self._parcel_grid(x0, y0, x1, y1, 5, 9, rng):
            facade = self._pick_facade(district, rng)
            if (ax1 - ax0) >= 6 and (ay1 - ay0) >= 6 and rng.random() < 0.35:
                self._fill_ring(ax0, ay0, ax1, ay1, 1, facade, walls)
                floors[ay0 + 1][ax0 + 1] = FLOOR_COBBLESTONE
            else:
                for y in range(ay0, ay1 + 1):
                    row = walls[y]
                    for x in range(ax0, ax1 + 1):
                        row[x] = facade
            if rng.random() < 0.08:
                props.append(make_neon_signpost_sprite(ax0 + 0.5, ay1 + 0.5, "RAMEN"))

    def _mass_slab(self, x0, y0, x1, y1, district, walls, rng):
        facade = self._pick_facade(district, rng)
        for y in range(y0, y1 + 1):
            row = walls[y]
            for x in range(x0, x1 + 1):
                row[x] = facade

    def _mass_warehouse(self, x0, y0, x1, y1, walls, floors, props, rng):
        """Big-footprint low-sprawl warehouse with an open service yard."""
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        wx = max(4, round(bw * rng.uniform(0.6, 0.8)))
        wh = max(4, round(bh * rng.uniform(0.6, 0.8)))
        wx0 = x0 if rng.random() < 0.5 else x1 - wx + 1
        wy0 = y0 if rng.random() < 0.5 else y1 - wh + 1
        wx1, wy1 = wx0 + wx - 1, wy0 + wh - 1
        for y in range(wy0, wy1 + 1):
            row = walls[y]
            for x in range(wx0, wx1 + 1):
                row[x] = WALL_WAREHOUSE
        for y in range(y0, y1 + 1):
            row_f = floors[y]
            for x in range(x0, x1 + 1):
                if walls[y][x] == 0:
                    row_f[x] = FLOOR_SIDEWALK
        if wx1 + 2 <= x1:
            props.append(make_crate_stack_sprite(wx1 + 1.5, wy0 + 1.5))
        if rng.random() < 0.5 and wx0 - 2 >= x0:
            props.append(make_dumpster_sprite(wx0 - 1.5, wy1 - 0.5))

    # ------------------------------------------------------------------
    # Landmarks
    # ------------------------------------------------------------------

    def _place_landmarks(self, width, height, ns_lines, ew_lines, walls, floors, districts,
                         props, landmarks, water_x0, has_marina, pier_ys, sx, rng):
        """Eight landmark pads on a corner + edge-midpoint lattice (~154 m minimum
        spacing at city scale), seed-jittered then repaired to the 150 m floor.
        Each pad gets a carved approach plaza; names follow the pad's district."""
        s_avg = (width + height) / 640.0
        min_sep = max(10.0, 150.0 * s_avg)
        x_max = (water_x0 - 8.0) if has_marina else float(width - 5)

        # Corner + edge-midpoint lattice. With a harbor, the east column pins
        # against the quay, so its corner pads stagger toward the quarters, its
        # edge-mid pad is dropped, and the centre joins instead -- every
        # pairwise distance stays inside the 150-400 m band by construction.
        used: List[Tuple[float, float]] = []
        for fyv in (0.02, 0.5, 0.98):
            for fxv in (0.02, 0.5, 0.98):
                if fxv == 0.5 and fyv == 0.5:
                    if has_marina:
                        used.append((width / 2.0, height / 2.0))
                    continue  # otherwise centre stays downtown streetscape
                if has_marina and fxv == 0.98 and fyv == 0.5:
                    continue
                lx, ly = fxv * width, fyv * height
                if has_marina and fxv == 0.98:
                    lx = x_max
                    ly = height * (0.26 if fyv == 0.02 else 0.74)
                used.append((lx, ly))
        # Plaza aprons must never pave over carved roads: nudge each pad out
        # of every road band (+ its 8x6 plaza footprint), let spacing repair
        # settle the layout, then re-snap -- repair knows nothing of roads.
        x_cap = (water_x0 - 7.0) if has_marina else float(width - 6)
        y_cap = float(height - 6)

        def snap_all(pads):
            return [
                (self._snap_off_road_bands(px, ns_lines, 4, 4, 5.0, x_cap),
                 self._snap_off_road_bands(py, ew_lines, 3, 3, 5.0, y_cap))
                for px, py in pads
            ]

        used = snap_all(used)
        self._repair_spacing(used, min_sep, width, height, x_max=x_max)

        # Re-snap any pad that repair pushed onto a road band. Each axis may
        # slide to either side of its band; a combination is accepted only
        # when every pairwise distance still clears the floor, so spacing
        # stays intact by induction. The plaza carve itself also skips
        # road/water cells as the final guard for the grid contracts.
        for _ in range(2):
            moved = False
            for idx in range(len(used)):
                px, py = used[idx]
                if (self._snap_off_road_bands(px, ns_lines, 4, 4, 5.0, x_cap) == px
                        and self._snap_off_road_bands(py, ew_lines, 3, 3, 5.0,
                                                      float(height - 6)) == py):
                    continue
                xs = self._snap_options(px, ns_lines, 4, 4, 5.0, x_cap)
                ys = self._snap_options(py, ew_lines, 3, 3, 5.0,
                                        float(height - 6))
                accepted = None
                for cx_, cy_ in ((a, b) for a in xs for b in ys):
                    cand = (cx_, cy_)
                    if all(math.hypot(cand[0] - q[0], cand[1] - q[1]) >= min_sep
                           for k, q in enumerate(used) if k != idx):
                        accepted = cand
                        break
                if accepted is not None and accepted != used[idx]:
                    used[idx] = accepted
                    moved = True
            if not moved:
                break

        buckets: Dict[str, List[Tuple[str, str, str]]] = {}
        for t in self.LANDMARK_TEMPLATES:
            buckets.setdefault(t[1], []).append(t)
        cycle: Dict[str, int] = {"SKYSCRAPER": 0, "MONUMENT": 0, "COMMERCIAL": 0,
                                 "INDUSTRIAL": 0}
        claimed = {"Solaria Deepwater Marina"}

        for idx, (lx, ly) in enumerate(used):
            district = districts[int(ly)][int(lx)] or DistrictType.CYBER_DOWNTOWN.value
            if district == DistrictType.CYBER_DOWNTOWN.value:
                cat = "SKYSCRAPER"
            elif district == DistrictType.INDUSTRIAL_DOCKLANDS.value:
                cat = "INDUSTRIAL"
            else:
                cat = "COMMERCIAL" if idx % 2 == 0 else "MONUMENT"
            pool = buckets.get(cat) or buckets["COMMERCIAL"]
            name, lm_type, desc = pool[cycle[cat] % len(pool)]
            cycle[cat] += 1
            if name in claimed:  # keep landmark names unique for HUD cycling
                remaining = [t for t in self.LANDMARK_TEMPLATES if t[0] not in claimed]
                if remaining:
                    name, lm_type, desc = remaining[0]
            claimed.add(name)

            self._carve_plaza(lx, ly, walls, floors, props, rng)
            fw, fh = self._containing_block_dims(ns_lines, ew_lines,
                                                 int(lx), int(ly), width, height)
            landmarks.append(Landmark(
                name=name, x=lx, y=ly, district=district, landmark_type=lm_type,
                description=desc, foot_w=fw, foot_h=fh,
            ))

        if has_marina and pier_ys:
            py = pier_ys[len(pier_ys) // 2]
            landmarks.append(Landmark(
                name="Solaria Deepwater Marina",
                x=float(water_x0 + 2), y=float(py) + 0.5,
                district=DistrictType.WATERFRONT_MARINA.value,
                landmark_type="MARINA",
                description="The bustling coastal docklands with illuminated mooring piers.",
            ))

    def _containing_block_dims(self, ns_lines, ew_lines, ix, iy, width, height):
        """True footprint (buildable extents) of the block nearest to (ix, iy)."""
        def nearest_span(spans, coord):
            best, best_d = None, None
            for a, b in spans:
                d = 0 if a <= coord <= b else min(abs(coord - a), abs(coord - b))
                if best_d is None or d < best_d:
                    best, best_d = (a, b), d
            return best
        x_span = nearest_span(self._block_spans(ns_lines, width), ix)
        y_span = nearest_span(self._block_spans(ew_lines, height), iy)
        fw = (x_span[1] - x_span[0] + 1) if x_span else 0
        fh = (y_span[1] - y_span[0] + 1) if y_span else 0
        return fw, fh

    @staticmethod
    def _snap_options(value, lines, margin_lo, margin_hi, clamp_lo, clamp_hi):
        """All safe values (nearest first) after sliding `value` out of every
        road band inflated by the plaza footprint margins."""
        zones = sorted((ln.lo - margin_lo, ln.hi + margin_hi) for ln in lines)
        merged = []
        for zlo, zhi in zones:
            if merged and zlo <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], zhi)
            else:
                merged.append([zlo, zhi])
        options = [value]
        for zlo, zhi in merged:
            if zlo <= value <= zhi:
                lo_opt = max(clamp_lo, min(clamp_hi, zlo - 0.5))
                hi_opt = max(clamp_lo, min(clamp_hi, zhi + 0.5))
                options = ([lo_opt] if abs(value - zlo) <= abs(zhi - value)
                           else [hi_opt]) + \
                          ([hi_opt] if abs(value - zlo) <= abs(zhi - value)
                           else [lo_opt])
                break
        seen, out = set(), []
        for v in options:
            if v not in seen:
                seen.add(v)
                out.append(v)
        return out

    @staticmethod
    def _snap_off_road_bands(value, lines, margin_lo, margin_hi,
                             clamp_lo, clamp_hi):
        """Nearest safe value after sliding out of every inflated road band."""
        return ProceduralCityGenerator._snap_options(
            value, lines, margin_lo, margin_hi, clamp_lo, clamp_hi)[0]

    @staticmethod
    def _repair_spacing(used, min_sep, width, height, max_rounds: int = 60,
                        x_max=None):
        """Deterministic pairwise repair: separates violating sites by pushing
        both ends apart within the map/harbor bounds until the spacing floor
        holds (or the bounded relaxation converges)."""
        lo_x, hi_x = 4.0, float(width - 5) if x_max is None else x_max
        lo_y, hi_y = 4.0, float(height - 5)
        for _ in range(max_rounds):
            worst = None
            for i in range(len(used)):
                for j in range(i + 1, len(used)):
                    d = math.hypot(used[i][0] - used[j][0], used[i][1] - used[j][1])
                    if d < min_sep and (worst is None or d < worst[0]):
                        worst = (d, i, j)
            if worst is None:
                return
            _, i, j = worst
            (ax, ay), (bx, by) = used[i], used[j]
            d = max(1e-6, math.hypot(bx - ax, by - ay))
            push = ((min_sep - d) / 2.0) + 0.25
            ux, uy = (bx - ax) / d, (by - ay) / d
            used[i] = (max(lo_x, min(hi_x, ax - ux * push)),
                       max(lo_y, min(hi_y, ay - uy * push)))
            used[j] = (max(lo_x, min(hi_x, bx + ux * push)),
                       max(lo_y, min(hi_y, by + uy * push)))

    def _carve_plaza(self, lx, ly, walls, floors, props, rng):
        """Approach vista: a paved plaza cut into the landmark's frontage.
        Road, water and bridge floors are never overwritten -- the street
        grid survives every plaza."""
        px0, py0 = int(lx) - 3, int(ly) - 2
        h, w = len(floors), len(floors[0])
        for y in range(max(1, py0), min(h - 1, py0 + 5)):
            for x in range(max(1, px0), min(w - 1, px0 + 7)):
                if floors[y][x] in (FLOOR_ROAD_NS, FLOOR_ROAD_EW,
                                    FLOOR_INTERSECTION, FLOOR_WATER,
                                    FLOOR_BRIDGE):
                    continue
                walls[y][x] = 0
                floors[y][x] = FLOOR_PLAZA_TILES
        if rng.random() < 0.5:
            props.append(make_monument_obelisk_sprite(lx, ly))
        else:
            props.append(make_fountain_sprite(lx, ly))

    # ------------------------------------------------------------------
    # Street props
    # ------------------------------------------------------------------

    def _populate_street_props(self, ns_lines, ew_lines, width, height, walls, props, rng):
        """Streetlamps, trees, hydrants, and vending machines on sidewalks,
        spaced in metres along the arterial corridors."""
        for ln in ns_lines:
            if ln.road_class != CLASS_ARTERIAL:
                continue
            step = max(6, round(14 * (width / 320.0)))
            left, right = ln.lo - 1.5, ln.hi + 1.5
            il, ir = int(left), int(right)
            y = 3.0
            while y < height - 3:
                iy = int(y)
                near_crossing = any(abs(iy - e.center) <= e.width for e in ew_lines)
                if not near_crossing and 1 <= il and ir < width - 1:
                    if walls[iy][il] == 0:
                        props.append(make_streetlamp_sprite(left, y))
                    if walls[iy][ir] == 0:
                        props.append(make_streetlamp_sprite(right, y))
                    if rng.random() < 0.35 and walls[iy][ir] == 0:
                        props.append(make_tree_sprite(right, y + 2.0))
                    if rng.random() < 0.18 and walls[iy][il] == 0:
                        props.append(make_fire_hydrant_sprite(left, y + 3.0))
                    if rng.random() < 0.10 and walls[iy][ir] == 0:
                        props.append(make_vending_machine_sprite(
                            right - 0.3, y + 1.0, facing_angle=math.pi))
                y += step
        for ln in ew_lines:
            if ln.road_class != CLASS_ARTERIAL:
                continue
            step = max(6, round(14 * (height / 320.0)))
            top, bot = ln.lo - 1.5, ln.hi + 1.5
            it, ib = int(top), int(bot)
            x = 3.0
            while x < width - 3:
                ix = int(x)
                near_crossing = any(abs(ix - n.center) <= n.width for n in ns_lines)
                if not near_crossing and 1 <= ix < width - 1 \
                        and 1 <= it and ib < height - 1:
                    if walls[it][ix] == 0:
                        props.append(make_streetlamp_sprite(x, top))
                    if walls[ib][ix] == 0:
                        props.append(make_streetlamp_sprite(x, bot))
                x += step

    # ------------------------------------------------------------------
    # Graph, lights, spawn
    # ------------------------------------------------------------------

    def _build_graph_and_lights(self, ns_lines, ew_lines, districts,
                                avenue_names, street_names,
                                water_x0=None, has_marina=False):
        road_graph = RoadGraph()
        traffic_light_coords: List[Tuple[int, int]] = []

        for ns in ns_lines:
            for ew in ew_lines:
                d_name = districts[ew.center][ns.center] or DistrictType.CYBER_DOWNTOWN.value
                road_graph.add_node(ns.center, ew.center, is_intersection=True, district=d_name)
                # No signals on the harbor bridge: EW traffic never crosses
                # the water, so those nodes carry NS through-traffic only.
                if ns.road_class != CLASS_LOCAL and ew.road_class != CLASS_LOCAL \
                        and not (has_marina and water_x0 is not None
                                 and ns.center >= water_x0 - 1):
                    traffic_light_coords.append((ns.center, ew.center))

        def wire(lines, axis):
            for ln in lines:
                nodes = sorted(
                    (nid for nid, n in road_graph.nodes.items()
                     if (n.x == ln.center if axis == "NS" else n.y == ln.center)),
                    key=lambda nid: road_graph.nodes[nid].y if axis == "NS"
                    else road_graph.nodes[nid].x,
                )
                for i in range(len(nodes) - 1):
                    if axis == "NS":
                        road_graph.add_edge(nodes[i], nodes[i + 1], FLOOR_ROAD_NS,
                                            avenue_names.get(ln.center, "Avenue"))
                    else:
                        road_graph.add_edge(nodes[i], nodes[i + 1], FLOOR_ROAD_EW,
                                            street_names.get(ln.center, "Street"))

        wire(ns_lines, "NS")
        wire(ew_lines, "EW")
        return traffic_light_coords, road_graph

    MAX_SPAWN_SCAN_RADIUS = 24

    def _find_safe_spawn_pos(
        self,
        width: int,
        height: int,
        floors: List[List[int]],
        walls: List[List[int]],
        ns_road_cols: List[int]
    ) -> Tuple[float, float]:
        """Finds a safe non-solid coordinate near the center, capped-radius
        spiral first, then an avenue-column fallback (keeps 320x320 scans O(1)
        instead of pathological full-grid spirals)."""
        mid_x = width // 2
        mid_y = height // 2

        for radius in range(self.MAX_SPAWN_SCAN_RADIUS + 1):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    x = mid_x + dx
                    y = mid_y + dy
                    if 1 <= x < width - 1 and 1 <= y < height - 1:
                        if walls[y][x] == 0 and floors[y][x] != 7:  # Not wall, not water
                            return (float(x) + 0.5, float(y) + 0.5)

        for col in ns_road_cols:
            probe_y = min(height - 2, max(1, mid_y))
            if walls[probe_y][col] == 0 and floors[probe_y][col] != 7:
                return (float(col) + 0.5, float(probe_y) + 0.5)

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


def has_marina_guard(width: int, height: int) -> bool:
    """Harbor front requires room for a water band plus developable land."""
    return width >= 40 and height >= 40
