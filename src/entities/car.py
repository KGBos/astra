"""
Dynamic Vehicle physics, traffic AI, and directional 3D ASCII sprites for Astra 3D.
"""

import math
import random
from enum import Enum
from typing import List, Tuple
from src.entities.sprite import Sprite
from src.world.city_map import FloorType


class VehicleType(Enum):
    TAXI = "TAXI"
    CYBER_SEDAN = "CYBER_SEDAN"
    POLICE = "POLICE"
    BUS = "BUS"


class Vehicle:
    def __init__(self, x: float, y: float, vtype: VehicleType, heading_dir: Tuple[int, int]):
        self.x = float(x)
        self.y = float(y)
        self.vtype = vtype
        self.dx, self.dy = heading_dir  # (1, 0), (-1, 0), (0, 1), (0, -1)
        self.speed = random.uniform(2.5, 4.0)
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

        # 1. Look ahead for traffic light or another vehicle
        ahead_dist = 1.6
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
            if dist_to_other < 2.0:
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

    def get_sprite_for_camera(self, cam_x: float, cam_y: float) -> Sprite:
        """Returns directional ASCII sprite based on angle between vehicle heading and camera view."""
        # Angle of vehicle motion
        v_angle = math.atan2(self.dy, self.dx)
        # Vector from vehicle to camera
        rel_x = cam_x - self.x
        rel_y = cam_y - self.y
        rel_angle = math.atan2(rel_y, rel_x)
        
        # Difference angle
        diff = (rel_angle - v_angle + math.pi * 3) % (math.pi * 2) - math.pi

        # Determine aspect: Front, Back, or Side
        # |diff| < pi/4 => camera is in front (seeing front of car)
        # |diff| > 3pi/4 => camera is behind (seeing rear of car)
        # otherwise side view
        is_front = abs(diff) < math.pi * 0.3
        is_rear = abs(diff) > math.pi * 0.7

        if is_front:
            # Front view of car
            chars = [
                "  [TAXI]  " if self.vtype == VehicleType.TAXI else "  ======  ",
                " /######\\ ",
                "[o======o]",
                " |O|  |O| "
            ]
            fg = [
                [(255, 255, 100) for _ in range(10)],
                [(180, 220, 255) for _ in range(10)],  # windshield
                [(255, 255, 200) if c == 'o' else self.primary_color for c in "[o======o]"],  # glowing headlights
                [(50, 50, 60) for _ in range(10)]      # tires
            ]
            if self.vtype == VehicleType.POLICE:
                siren_color = (255, 30, 30) if int(self.siren_tick) % 2 == 0 else (30, 100, 255)
                fg[0] = [siren_color for _ in range(10)]

            return Sprite(self.x, self.y, "CAR_FRONT", chars, fg, scale_x=0.7, scale_y=0.5, is_luminous=True)

        elif is_rear:
            # Rear view of car (red taillights)
            chars = [
                "  ======  ",
                " /######\\ ",
                "[*======*]",
                " |O|  |O| "
            ]
            fg = [
                [self.primary_color for _ in range(10)],
                [(100, 120, 140) for _ in range(10)],
                [(255, 20, 20) if c == '*' else self.primary_color for c in "[*======*]"],  # red taillights
                [(50, 50, 60) for _ in range(10)]
            ]
            return Sprite(self.x, self.y, "CAR_REAR", chars, fg, scale_x=0.7, scale_y=0.5, is_luminous=True)

        else:
            # Side profile of car
            chars = [
                "   .-----.   ",
                " _/ # # # \\_ ",
                "[o=========*]",
                "  (O)   (O)  "
            ]
            fg = [
                [self.primary_color for _ in range(13)],
                [(180, 220, 255) if c == '#' else self.primary_color for c in " _/ # # # \\_ "],
                [(255, 255, 180) if c == 'o' else ((255, 30, 30) if c == '*' else self.primary_color) for c in "[o=========*]"],
                [(50, 50, 60) for _ in range(13)]
            ]
            return Sprite(self.x, self.y, "CAR_SIDE", chars, fg, scale_x=0.85, scale_y=0.5, is_luminous=True)
