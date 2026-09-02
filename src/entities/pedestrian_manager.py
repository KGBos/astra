"""
Pedestrian Crowd Manager and Autonomous Sidewalk Coordinator for Astra 3D.
Author: Darius Thorne (Procedural World & City Generation Specialist 📐)
"""

import math
import random
import time
from typing import Dict, List, Optional, Tuple

from src.entities.pedestrian import Pedestrian, PedestrianArchetype, PedestrianState
from src.entities.sprite import Sprite
from src.world.city_map import CityMap, FloorType

# Crowd density contract (M5 Cycle C): dense districts carry roughly one
# pedestrian per 900 m2 of walkable ground, industrial sprawl one per 2700 m2.
DENSE_PED_PER_SQM = 1.0 / 900.0
SPARSE_PED_PER_SQM = 1.0 / 2700.0
SPARSE_DISTRICTS = ("INDUSTRIAL DOCKLANDS", "WATERFRONT MARINA")
PED_COUNT_MIN = 40
PED_COUNT_MAX = 140

WALKABLE_FLOORS = (FloorType.SIDEWALK, FloorType.PLAZA_TILES,
                   FloorType.PARK_GRASS, FloorType.COBBLESTONE,
                   FloorType.WOOD_DECK)

DISTRICT_ARCHETYPES = {
    "CYBER-DOWNTOWN": [PedestrianArchetype.CYBERPUNK, PedestrianArchetype.CORP_SUIT, PedestrianArchetype.CYBER_ANDROID],
    "FINANCIAL CORE": [PedestrianArchetype.CORP_SUIT, PedestrianArchetype.POLICE_OFFICER, PedestrianArchetype.CYBER_ANDROID],
    "NEON ENTERTAINMENT": [PedestrianArchetype.CYBERPUNK, PedestrianArchetype.STREET_VENDOR, PedestrianArchetype.CASUAL_CITIZEN],
    "HISTORIC BROWNSTONES": [PedestrianArchetype.CASUAL_CITIZEN, PedestrianArchetype.STREET_VENDOR],
    "INDUSTRIAL DOCKLANDS": [PedestrianArchetype.CYBER_ANDROID, PedestrianArchetype.POLICE_OFFICER],
    "CENTRAL ASTRA PLAZA": [PedestrianArchetype.CASUAL_CITIZEN, PedestrianArchetype.CYBERPUNK, PedestrianArchetype.STREET_VENDOR]
}


def survey_district_walkable(city_map) -> Tuple[Dict[str, int], Dict[str, List[Tuple[int, int]]]]:
    """Single O(cells) pass over the grid returning walkable area in m2 and the
    tile list per district. Walkable mirrors the sidewalk predicate used by the
    crowd sim (open, dry land: sidewalks, plazas, lawns, cobbles, piers)."""
    areas: Dict[str, int] = {}
    tiles: Dict[str, List[Tuple[int, int]]] = {}
    walls = city_map.walls
    floors = city_map.floors
    districts = city_map.districts
    width = city_map.width
    height = city_map.height
    for y in range(2, height - 2):
        wall_row = walls[y]
        floor_row = floors[y]
        district_row = districts[y]
        for x in range(2, width - 2):
            if wall_row[x] != 0:
                continue
            ftype = floor_row[x]
            if ftype not in WALKABLE_FLOORS:
                continue
            district = district_row[x] or "ASTRA METROPOLIS"
            areas[district] = areas.get(district, 0) + 1
            tiles.setdefault(district, []).append((x, y))
    return areas, tiles


def compute_pedestrian_budget(areas: Dict[str, int]) -> int:
    """Auto population from measured walkable areas, clamped [40, 140]."""
    weighted = 0.0
    for district, area_sqm in areas.items():
        rate = SPARSE_PED_PER_SQM if district in SPARSE_DISTRICTS else DENSE_PED_PER_SQM
        weighted += area_sqm * rate
    return max(PED_COUNT_MIN, min(PED_COUNT_MAX, round(weighted)))


def _apportion(total: int, weights: Dict[str, float]) -> Dict[str, int]:
    """Largest-remainder split of `total` proportional to weights (sums exactly)."""
    weight_sum = sum(weights.values())
    if weight_sum <= 0 or total <= 0:
        return {district: 0 for district in weights}
    quotas = {}
    assigned = 0
    remainders = []
    for district, weight in weights.items():
        exact = total * weight / weight_sum
        base = int(exact)
        quotas[district] = base
        remainders.append((exact - base, district))
        assigned += base
    remainders.sort(reverse=True)
    for _, district in remainders[:total - assigned]:
        quotas[district] += 1
    return quotas


class PedestrianManager:
    """
    Manages autonomous sidewalk pedestrian populations across all city districts,
    handling spatial density, traffic crosswalks, interaction queries, and sprite rendering.

    Population scales with measured walkable area per district (dense ~1 ped /
    900 m2, industrial sparse) and each district's share of pedestrians is
    proportional to its density-weighted share of walkable ground.
    """

    def __init__(self, city_map: CityMap, pedestrian_count: Optional[int] = None,
                 spawn_clock: bool = False):
        self.city_map = city_map
        self.rng = random.Random(f"astra:pedestrians:{city_map.seed}")
        self.pedestrians: List[Pedestrian] = []
        self.last_spawn_seconds: Optional[float] = None
        started = time.perf_counter() if spawn_clock else None
        self._spawn_pedestrians(pedestrian_count)
        if spawn_clock:
            self.last_spawn_seconds = time.perf_counter() - started

    def _spawn_pedestrians(self, count: Optional[int]):
        areas, tiles = survey_district_walkable(self.city_map)
        if not tiles:
            tiles = {"ASTRA METROPOLIS": [(5, 5), (6, 5), (5, 6)]}
            areas = {"ASTRA METROPOLIS": 3}

        if count is None:
            count = compute_pedestrian_budget(areas)
        weights: Dict[str, float] = {}
        for district, area_sqm in areas.items():
            rate = SPARSE_PED_PER_SQM if district in SPARSE_DISTRICTS else DENSE_PED_PER_SQM
            weights[district] = area_sqm * rate
        quotas = _apportion(count, weights)

        for district, quota in quotas.items():
            district_tiles = tiles.get(district)
            if not district_tiles or quota <= 0:
                continue
            candidates = DISTRICT_ARCHETYPES.get(district, list(PedestrianArchetype))
            picked = self.rng.sample(district_tiles, min(quota, len(district_tiles)))
            for gx, gy in picked:
                archetype = self.rng.choice(candidates)
                px = gx + self.rng.uniform(0.2, 0.8)
                py = gy + self.rng.uniform(0.2, 0.8)
                self.pedestrians.append(
                    Pedestrian(px, py, archetype=archetype, rng=self.rng)
                )

    def update(self, dt: float):
        for ped in self.pedestrians:
            ped.update(dt, self.city_map, self.pedestrians)

    def get_focused_pedestrian(
        self,
        cam_x: float,
        cam_y: float,
        dir_x: float,
        dir_y: float,
        max_dist: float = 2.8
    ) -> Optional[Pedestrian]:
        """Returns the closest pedestrian directly in the player's line of sight."""
        closest_ped = None
        closest_dist = max_dist

        for ped in self.pedestrians:
            dx = ped.x - cam_x
            dy = ped.y - cam_y
            dist = math.hypot(dx, dy)
            if dist < closest_dist and dist > 0.1:
                # Normalise to vector
                ndx = dx / dist
                ndy = dy / dist
                dot = ndx * dir_x + ndy * dir_y
                if dot > 0.65:  # within ~45-degree frontal cone
                    closest_dist = dist
                    closest_ped = ped

        return closest_ped

    def interact_with_focused(
        self,
        cam_x: float,
        cam_y: float,
        dir_x: float,
        dir_y: float
    ) -> Optional[Tuple[str, str]]:
        """Interacts with the pedestrian in front of the player, returning (Archetype, Quote)."""
        ped = self.get_focused_pedestrian(cam_x, cam_y, dir_x, dir_y)
        if ped:
            quote = ped.get_ambient_quote()
            ped.trigger_speech(quote, duration=4.0)
            return (ped.archetype.value, quote)
        return None

    def alert_nearby(self, center_x: float, center_y: float, radius: float = 6.0):
        """Triggers reaction on all pedestrians within acoustic radius."""
        for ped in self.pedestrians:
            dist = math.hypot(ped.x - center_x, ped.y - center_y)
            if dist <= radius:
                ped.react_to_horn()

    def get_all_sprites_for_camera(self, cam_x: float, cam_y: float) -> List[Sprite]:
        """Collects dynamic directional sprites for all active pedestrians."""
        sprites = []
        for ped in self.pedestrians:
            # Check render range (within 55 units — matches the long-range
            # draw distance; sub-cell sprites are cheap and add depth)
            dist_sq = (ped.x - cam_x) ** 2 + (ped.y - cam_y) ** 2
            if dist_sq < 3025.0:
                sprites.append(ped.get_sprite_for_camera(cam_x, cam_y))
        return sprites
