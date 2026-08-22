"""
Traffic Manager, NPC Pedestrians, and 3D World Entity Coordinator for Astra 3D.
"""

import math
import random
from typing import List, Tuple, Optional
from src.entities.sprite import Sprite, make_streetlamp_sprite, make_tree_sprite, make_fire_hydrant_sprite
from src.entities.car import Vehicle, VehicleType
from src.entities.npc import NPC, build_default_npcs


class TrafficManager:
    def __init__(self, city_map, vehicle_count: int = 16):
        self.city_map = city_map
        self.vehicles: List[Vehicle] = []
        self.static_props: List[Sprite] = []
        self.npcs: List[NPC] = build_default_npcs()

        self._spawn_static_props()
        self._spawn_vehicles(vehicle_count)

    def _spawn_static_props(self):
        # 1. Place Streetlamps at road corners / sidewalks
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

    def _spawn_vehicles(self, count: int):
        vtypes = [VehicleType.TAXI, VehicleType.CYBER_SEDAN, VehicleType.POLICE, VehicleType.BUS]
        
        # Spawn cars along North-South Avenues
        for col in self.city_map.ns_road_cols:
            # Lane 1 (going South: +Y)
            self.vehicles.append(Vehicle(col + 0.5, random.uniform(3, self.city_map.height - 4), random.choice(vtypes), (0, 1)))
            # Lane 2 (going North: -Y)
            self.vehicles.append(Vehicle(col + 1.5, random.uniform(3, self.city_map.height - 4), random.choice(vtypes), (0, -1)))

        # Spawn cars along East-West Streets
        for row in self.city_map.ew_road_rows:
            # Lane 1 (going East: +X)
            self.vehicles.append(Vehicle(random.uniform(3, self.city_map.width - 4), row + 0.5, random.choice(vtypes), (1, 0)))
            # Lane 2 (going West: -X)
            self.vehicles.append(Vehicle(random.uniform(3, self.city_map.width - 4), row + 1.5, random.choice(vtypes), (-1, 0)))

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
