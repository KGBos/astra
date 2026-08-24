"""
Dynamic Vehicle physics, traffic AI, and directional 3D ASCII sprites for Astra 3D.
"""

import math
from enum import Enum
from typing import List, Tuple
from src.entities.sprite import Sprite, VolumetricSprite
from src.world.city_map import FloorType


class VehicleType(Enum):
    TAXI = "TAXI"
    CYBER_SEDAN = "CYBER_SEDAN"
    POLICE = "POLICE"
    BUS = "BUS"


ARTERIAL_CRUISE = 13.0
COLLECTOR_CRUISE = 9.0
ALLEY_CRUISE = 5.0


def cruise_speed_for(city_map, x: float, y: float, heading_dir: Tuple[int, int]) -> float:
    """Cruise speed in m/s for the road a vehicle occupies.

    Interim index heuristic over ns_road_cols/ew_road_rows (every fourth line
    arterial 13 m/s, every second of the rest collector 9 m/s, else alley
    5 m/s). Generator v2 now exposes the real classes via city_map.road_lanes();
    consuming them lands with the Cycle C traffic retune.
    """
    dx, dy = heading_dir
    if dy != 0:
        coords = getattr(city_map, 'ns_road_cols', [])
        coord = int(x)
    else:
        coords = getattr(city_map, 'ew_road_rows', [])
        coord = int(y)
    if not coords:
        return COLLECTOR_CRUISE
    idx = 0
    for i, c in enumerate(coords):
        if c <= coord:
            idx = i
        else:
            break
    if idx % 4 == 0:
        return ARTERIAL_CRUISE
    if idx % 2 == 0:
        return COLLECTOR_CRUISE
    return ALLEY_CRUISE


class Vehicle:
    def __init__(self, x: float, y: float, vtype: VehicleType, heading_dir: Tuple[int, int]):
        self.x = float(x)
        self.y = float(y)
        self.vtype = vtype
        self.dx, self.dy = heading_dir  # (1, 0), (-1, 0), (0, 1), (0, -1)
        self.speed = COLLECTOR_CRUISE
        self.target_speed = self.speed
        self.current_speed = self.speed
        self.stopped = False
        self.siren_tick = 0.0

        # Colors based on vehicle type
        self.primary_color = (255, 200, 0) if vtype == VehicleType.TAXI else (
            (0, 220, 255) if vtype == VehicleType.CYBER_SEDAN else (
                (240, 240, 255) if vtype == VehicleType.POLICE else (80, 160, 240)
            )
        )

    def update(self, dt: float, city_map, other_vehicles: List['Vehicle']):
        self.siren_tick += dt * 8.0

        # 1. Look ahead for traffic light or another vehicle (sight distance
        # scales with speed so higher m/s cruise speeds can still stop in time)
        ahead_dist = max(2.0, self.current_speed * 1.2)
        follow_dist = max(2.0, self.current_speed * 0.6 + 1.0)
        look_x = self.x + self.dx * ahead_dist
        look_y = self.y + self.dy * ahead_dist
        look_grid = (int(look_x), int(look_y))

        # Check traffic light at intersection
        should_stop = False
        if look_grid in city_map.traffic_lights:
            tl = city_map.traffic_lights[look_grid]
            if self.dx != 0 and not tl.is_green_for_ew():
                should_stop = True
            elif self.dy != 0 and not tl.is_green_for_ns():
                should_stop = True

        # Check collision with other cars in front
        for other in other_vehicles:
            if other is self:
                continue
            dist_to_other = math.hypot(other.x - self.x, other.y - self.y)
            if dist_to_other < follow_dist:
                # Check if other is ahead in our travel direction
                rel_x = other.x - self.x
                rel_y = other.y - self.y
                dot = rel_x * self.dx + rel_y * self.dy
                if dot > 0.3:  # in front
                    should_stop = True
                    break

        if should_stop:
            self.current_speed = max(0.0, self.current_speed - 8.0 * dt)
        else:
            self.current_speed = min(self.target_speed, self.current_speed + 5.0 * dt)

        # Move
        new_x = self.x + self.dx * self.current_speed * dt
        new_y = self.y + self.dy * self.current_speed * dt

        # Wrap around world bounds or turn at intersections
        if new_x < 2 or new_x >= city_map.width - 2 or new_y < 2 or new_y >= city_map.height - 2:
            # Respawn at opposite side
            if self.dx > 0: self.x = 2.0
            elif self.dx < 0: self.x = city_map.width - 3.0
            if self.dy > 0: self.y = 2.0
            elif self.dy < 0: self.y = city_map.height - 3.0
        else:
            self.x = new_x
            self.y = new_y

    def get_sprite_for_camera(self, cam_x: float, cam_y: float) -> VolumetricSprite:
        """
        Pseudo-volumetric vehicle box: distinct FRONT (headlights), BACK
        (taillights) and SIDE (profile) faces projected with an angle-dependent
        split, so the car reads as a solid body from any orbit angle.
        """
        # Vehicle motion direction is its front-facing normal
        facing_angle = math.atan2(self.dy, self.dx)

        siren_color = None
        if self.vtype == VehicleType.POLICE:
            siren_color = (255, 30, 30) if int(self.siren_tick) % 2 == 0 else (30, 100, 255)

        # ---- FRONT face: windshield + glowing headlights ----
        front_chars = [
            "  [TAXI]  " if self.vtype == VehicleType.TAXI else "  ======  ",
            " /######\\ ",
            "[o======o]",
            " |O|  |O| "
        ]
        front_fg = [
            [(255, 255, 100) for _ in range(10)],
            [(180, 220, 255) for _ in range(10)],  # windshield
            [(255, 255, 200) if c == 'o' else self.primary_color for c in "[o======o]"],  # headlights
            [(50, 50, 60) for _ in range(10)]      # tires
        ]
        if siren_color:
            front_fg[0] = [siren_color for _ in range(10)]

        # ---- BACK face: red taillights ----
        back_chars = [
            "  ======  ",
            " /######\\ ",
            "[*======*]",
            " |O|  |O| "
        ]
        back_fg = [
            [self.primary_color for _ in range(10)],
            [(100, 120, 140) for _ in range(10)],
            [(255, 20, 20) if c == '*' else self.primary_color for c in "[*======*]"],  # taillights
            [(50, 50, 60) for _ in range(10)]
        ]
        if siren_color:
            back_fg[0] = [siren_color for _ in range(10)]

        # ---- SIDE face: full profile with wheels ----
        side_chars = [
            "   .-----.   ",
            " _/ # # # \\_ ",
            "[o=========*]",
            "  (O)   (O)  "
        ]
        side_fg = [
            [self.primary_color for _ in range(13)],
            [(180, 220, 255) if c == '#' else self.primary_color for c in " _/ # # # \\_ "],
            [(255, 255, 180) if c == 'o' else ((255, 30, 30) if c == '*' else self.primary_color) for c in "[o=========*]"],
            [(50, 50, 60) for _ in range(13)]
        ]

        return VolumetricSprite(
            self.x, self.y, "CAR",
            front_chars, front_fg,
            side_chars, side_fg,
            facing_angle=facing_angle,
            scale_x=2.2,
            scale_y=0.375,
            is_luminous=True,
            back_chars=back_chars, back_fg=back_fg,
            corner_smooth=True
        )
