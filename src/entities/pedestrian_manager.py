"""
Pedestrian Crowd Manager and Autonomous Sidewalk Coordinator for Astra 3D.
Author: Darius Thorne (Procedural World & City Generation Specialist 📐)
"""

import math
import random
from typing import List, Optional, Tuple

from src.entities.pedestrian import Pedestrian, PedestrianArchetype, PedestrianState
from src.entities.sprite import Sprite
from src.world.city_map import CityMap, FloorType


class PedestrianManager:
    """
    Manages autonomous sidewalk pedestrian populations across all city districts,
    handling spatial density, traffic crosswalks, interaction queries, and sprite rendering.
    """

    def __init__(self, city_map: CityMap, pedestrian_count: int = 24):
        self.city_map = city_map
        self.pedestrians: List[Pedestrian] = []
        self._spawn_pedestrians(pedestrian_count)

    def _spawn_pedestrians(self, count: int):
        # District archetype weight mapping
        archetype_map = {
            "CYBER-DOWNTOWN": [PedestrianArchetype.CYBERPUNK, PedestrianArchetype.CORP_SUIT, PedestrianArchetype.CYBER_ANDROID],
            "FINANCIAL CORE": [PedestrianArchetype.CORP_SUIT, PedestrianArchetype.POLICE_OFFICER, PedestrianArchetype.CYBER_ANDROID],
            "NEON ENTERTAINMENT": [PedestrianArchetype.CYBERPUNK, PedestrianArchetype.STREET_VENDOR, PedestrianArchetype.CASUAL_CITIZEN],
            "HISTORIC BROWNSTONES": [PedestrianArchetype.CASUAL_CITIZEN, PedestrianArchetype.STREET_VENDOR],
            "INDUSTRIAL DOCKLANDS": [PedestrianArchetype.CYBER_ANDROID, PedestrianArchetype.POLICE_OFFICER],
            "CENTRAL ASTRA PLAZA": [PedestrianArchetype.CASUAL_CITIZEN, PedestrianArchetype.CYBERPUNK, PedestrianArchetype.STREET_VENDOR]
        }

        # Find valid walkable sidewalk tiles (not road, not wall, not water)
        walkable_tiles = []
        for y in range(2, self.city_map.height - 2):
            for x in range(2, self.city_map.width - 2):
                ftype = self.city_map.get_floor_type(x, y)
                if not self.city_map.is_solid(x, y) and not self.city_map.is_water(x, y):
                    if ftype in (FloorType.SIDEWALK, FloorType.PLAZA_TILES, FloorType.PARK_GRASS, FloorType.COBBLESTONE, FloorType.WOOD_DECK):
                        walkable_tiles.append((x, y))

        if not walkable_tiles:
            walkable_tiles = [(5, 5), (6, 5), (5, 6)]

        random.shuffle(walkable_tiles)

        for i in range(min(count, len(walkable_tiles))):
            gx, gy = walkable_tiles[i]
            district = self.city_map.get_district_at(gx, gy)
            candidates = archetype_map.get(district, list(PedestrianArchetype))
            archetype = random.choice(candidates)

            # Spawn slightly offset within grid cell
            px = gx + random.uniform(0.2, 0.8)
            py = gy + random.uniform(0.2, 0.8)

            ped = Pedestrian(px, py, archetype=archetype)
            self.pedestrians.append(ped)

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
            # Check render range (within 35 units)
            dist_sq = (ped.x - cam_x) ** 2 + (ped.y - cam_y) ** 2
            if dist_sq < 1225.0:
                sprites.append(ped.get_sprite_for_camera(cam_x, cam_y))
        return sprites
