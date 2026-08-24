"""
Traffic Manager, NPC Pedestrians, and 3D World Entity Coordinator for Astra 3D.
"""

import math
import random
from typing import List, Tuple, Optional
from src.entities.sprite import Sprite, make_streetlamp_sprite, make_tree_sprite, make_fire_hydrant_sprite
from src.entities.car import Vehicle, VehicleType, cruise_speed_for
from src.entities.npc import NPC, build_default_npcs
from src.world.city_map import FloorType

DRIVABLE_FLOORS = (FloorType.ROAD_NS, FloorType.ROAD_EW,
                   FloorType.INTERSECTION, FloorType.BRIDGE)
SPAWN_RETRY_LIMIT = 10


class TrafficManager:
    def __init__(self, city_map, vehicle_count: int = 16):
        self.city_map = city_map
        self.vehicles: List[Vehicle] = []
        self.static_props: List[Sprite] = []
        self.npcs: List[NPC] = build_default_npcs()

        self._spawn_static_props()
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
        vtypes = [VehicleType.TAXI, VehicleType.CYBER_SEDAN, VehicleType.POLICE, VehicleType.BUS]

        candidates = []

        def ns_slot(col: float, dy):
            def mk():
                return (col, random.uniform(3, self.city_map.height - 4),
                        random.choice(vtypes), dy)
            return self._road_candidate(mk)

        def ew_slot(row: float, dx):
            def mk():
                return (random.uniform(3, self.city_map.width - 4), row,
                        random.choice(vtypes), dx)
            return self._road_candidate(mk)

        for col in self.city_map.ns_road_cols:
            candidates.append(ns_slot(col + 0.5, (0, 1)))
            candidates.append(ns_slot(col + 1.5, (0, -1)))
        for row in self.city_map.ew_road_rows:
            candidates.append(ew_slot(row + 0.5, (1, 0)))
            candidates.append(ew_slot(row + 1.5, (-1, 0)))
        candidates = [c for c in candidates if c is not None]
        random.shuffle(candidates)
        for x, y, vtype, heading in candidates[:max(0, count)]:
            vehicle = Vehicle(x, y, vtype, heading)
            cruise = cruise_speed_for(self.city_map, x, y, heading)
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
