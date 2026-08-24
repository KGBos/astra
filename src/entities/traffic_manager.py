"""
Traffic Manager, NPC Pedestrians, and 3D World Entity Coordinator for Astra 3D.
"""

import math
import random
from typing import List, Tuple, Optional
from src.entities.sprite import Sprite, make_streetlamp_sprite, make_tree_sprite, make_fire_hydrant_sprite
from src.entities.car import Vehicle, VehicleType, CRUISE_BY_CLASS, COLLECTOR_CRUISE
from src.entities.npc import NPC, build_default_npcs
from src.world.city_map import FloorType

DRIVABLE_FLOORS = (FloorType.ROAD_NS, FloorType.ROAD_EW,
                   FloorType.INTERSECTION, FloorType.BRIDGE)
SPAWN_RETRY_LIMIT = 10

# Fleet sizing: one vehicle per METRES_PER_VEHICLE of total lane length,
# clamped so small towns keep life and mega-maps stay cheap.
METRES_PER_VEHICLE = 120.0
VEHICLE_COUNT_MIN = 24
VEHICLE_COUNT_MAX = 80


def compute_vehicle_budget(city_map) -> int:
    """Lane-derived fleet size: round(total lane-length / 120 m) clamped [24, 80].

    Total lane length counts every travel lane separately (segment span times
    its right-hand lane offsets), so arterials carry proportionally more
    vehicles than local lanes.
    """
    total_lane_m = 0.0
    for lane in city_map.road_lanes():
        lo, hi = lane["span"]
        total_lane_m += (hi - lo + 1) * len(lane["lane_offsets_m"])
    return max(VEHICLE_COUNT_MIN, min(VEHICLE_COUNT_MAX,
                                      round(total_lane_m / METRES_PER_VEHICLE)))


class TrafficManager:
    def __init__(self, city_map, vehicle_count: Optional[int] = None):
        self.city_map = city_map
        self.vehicles: List[Vehicle] = []
        self.static_props: List[Sprite] = []
        self.npcs: List[NPC] = build_default_npcs()

        self._spawn_static_props()
        if vehicle_count is None:
            vehicle_count = compute_vehicle_budget(city_map)
        self.vehicle_count = vehicle_count
        self._spawn_vehicles(vehicle_count)

    def _spawn_static_props(self):
        # Use procedural props if available from CityMap
        if hasattr(self.city_map, 'props') and self.city_map.props:
            self.static_props = list(self.city_map.props)
            return

        # Fallback to manual prop placement
        for col in self.city_map.ns_road_cols:
            for row in self.city_map.ew_road_rows:
                # 4 corners around each intersection
                self.static_props.append(make_streetlamp_sprite(col - 1.5, row - 1.5))
                self.static_props.append(make_streetlamp_sprite(col + 2.5, row - 1.5))
                self.static_props.append(make_streetlamp_sprite(col - 1.5, row + 2.5))
                self.static_props.append(make_streetlamp_sprite(col + 2.5, row + 2.5))

        # 2. Place Trees in Central Plaza (14..19, 14..19)
        for tx in [15.5, 18.5]:
            for ty in [15.5, 18.5]:
                self.static_props.append(make_tree_sprite(tx, ty))

        # 3. Place Fire Hydrants along sidewalks
        for col in self.city_map.ns_road_cols:
            for row in [8.5, 16.5, 24.5, 32.5]:
                self.static_props.append(make_fire_hydrant_sprite(col - 1.2, row))

    def _on_drivable_road(self, x: float, y: float) -> bool:
        """True when the cell under (x, y) is an actual drivable road floor
        (never harbor water, piers, or sidewalks)."""
        return self.city_map.get_floor_type(int(x), int(y)) in DRIVABLE_FLOORS

    def _road_candidate(self, make_candidate):
        """Samples a spawn candidate, re-rolling up to SPAWN_RETRY_LIMIT times
        until it lands on a drivable road cell; None if all attempts fail."""
        for _ in range(SPAWN_RETRY_LIMIT):
            cand = make_candidate()
            if self._on_drivable_road(cand[0], cand[1]):
                return cand
        return None

    def _spawn_vehicles(self, count: int):
        """Spawns vehicles in measured lanes from city_map.road_lanes().

        Each lane offset fixes the cross-axis coordinate and, under right-hand
        traffic, the travel heading: a lane west of an NS centre-line runs
        southbound, east of it northbound; south of an EW centre-line eastbound,
        north of it westbound. Zero-offset local lanes take either direction.
        The drivable-floor guard re-rolls along-lane positions so no vehicle
        ever starts on water, piers, or sidewalks.
        """
        vtypes = [VehicleType.TAXI, VehicleType.CYBER_SEDAN, VehicleType.POLICE, VehicleType.BUS]

        candidates = []

        def lane_slot(axis: str, cross_m: float, heading, road_class: str,
                     center_m: float, offset_m: float, span: Tuple[int, int]):
            lo, hi = span

            def mk():
                if axis == "NS":
                    return (cross_m, random.uniform(lo, hi),
                            random.choice(vtypes), heading)
                return (random.uniform(lo, hi), cross_m,
                        random.choice(vtypes), heading)
            cand = self._road_candidate(mk)
            if cand is not None:
                return cand + (axis, road_class, center_m, offset_m)
            return None

        for lane in self.city_map.road_lanes():
            axis = lane["axis"]
            road_class = lane["road_class"]
            center_m = lane["center_m"]
            for offset_m in lane["lane_offsets_m"]:
                cross_m = center_m + offset_m
                if axis == "NS":
                    if offset_m < 0:
                        heading = (0, 1)
                    elif offset_m > 0:
                        heading = (0, -1)
                    else:
                        heading = (0, random.choice((1, -1)))
                else:
                    if offset_m > 0:
                        heading = (1, 0)
                    elif offset_m < 0:
                        heading = (-1, 0)
                    else:
                        heading = (random.choice((1, -1)), 0)
                candidates.append(lane_slot(axis, cross_m, heading, road_class,
                                            center_m, offset_m, lane["span"]))

        candidates = [c for c in candidates if c is not None]
        random.shuffle(candidates)
        # Fleet is capped by available lane slots; the lane-length budget
        # simply requests up to `count` placements across them.
        for x, y, vtype, heading, axis, road_class, center_m, offset_m \
                in candidates[:max(0, count)]:
            vehicle = Vehicle(x, y, vtype, heading)
            vehicle.road_class = road_class
            vehicle.lane_axis = axis
            vehicle.lane_center_m = center_m
            vehicle.lane_offset_m = offset_m
            cruise = CRUISE_BY_CLASS.get(road_class, COLLECTOR_CRUISE)
            vehicle.speed = cruise
            vehicle.target_speed = cruise
            vehicle.current_speed = cruise * 0.5
            self.vehicles.append(vehicle)

    def update(self, dt: float):
        for vehicle in self.vehicles:
            vehicle.update(dt, self.city_map, self.vehicles)
        for npc in self.npcs:
            npc.update(dt, self.city_map)

    def get_all_sprites_for_camera(self, cam_x: float, cam_y: float) -> List[Sprite]:
        """Collects static props, pedestrians, and dynamically oriented vehicle sprites."""
        all_sprites: List[Sprite] = list(self.static_props)
        for npc in self.npcs:
            all_sprites.append(npc.get_sprite())
        for v in self.vehicles:
            all_sprites.append(v.get_sprite_for_camera(cam_x, cam_y))
        return all_sprites

    def get_nearby_vehicle(self, cam_x: float, cam_y: float, max_dist: float = 2.4) -> Optional[Vehicle]:
        for v in self.vehicles:
            if math.hypot(v.x - cam_x, v.y - cam_y) <= max_dist:
                return v
        return None

    def get_nearby_npc(self, cam_x: float, cam_y: float, max_dist: float = 2.2) -> Optional[NPC]:
        for npc in self.npcs:
            if math.hypot(npc.x - cam_x, npc.y - cam_y) <= max_dist:
                return npc
        return None
