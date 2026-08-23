"""
First-Person Vehicle Driving Controller & Physics Simulation for Astra 3D.
Author: Valerie Sterling ⚡ (3D Raycaster & Rasterization Specialist)
Status: M3 WORK-IN-PROGRESS — module is implemented and unit-tested (tests/test_vehicle_audio.py) but not yet integrated into the main Game loop (src/game.py).
"""

import math
from typing import Optional, List
from src.entities.car import Vehicle, VehicleType
from src.engine.camera import Camera
from src.world.city_map import CityMap


class VehicleController:
    """Manages player vehicle interaction, driving physics, steering and camera attachment."""

    def __init__(self):
        self.is_driving = False
        self.current_vehicle: Optional[Vehicle] = None
        self.gear = "D"  # P, R, N, D
        self.steering_angle = 0.0  # [-1.0, 1.0]
        self.speed = 0.0  # units per sec
        self.rpm = 900.0  # idle RPM
        self.max_forward_speed = 8.5
        self.max_reverse_speed = 3.5
        self.acceleration = 7.0
        self.braking_force = 12.0
        self.drag = 2.5
        self.heading_angle = 0.0  # radians
        self.siren_active = False
        self.horn_active = False

    def try_enter_nearest_vehicle(
        self,
        camera: Camera,
        vehicles: List[Vehicle],
        max_dist: float = 2.4
    ) -> Optional[Vehicle]:
        """Checks if a vehicle is within interaction range and mounts it."""
        if self.is_driving:
            # Already driving -> exit vehicle
            self.exit_vehicle(camera)
            return None

        best_v = None
        best_d = max_dist

        for v in vehicles:
            dist = math.hypot(v.x - camera.pos.x, v.y - camera.pos.y)
            if dist < best_d:
                best_d = dist
                best_v = v

        if best_v is not None:
            self.enter_vehicle(best_v, camera)
            return best_v
        return None

    def enter_vehicle(self, vehicle: Vehicle, camera: Camera):
        self.is_driving = True
        self.current_vehicle = vehicle
        self.speed = 0.0
        self.gear = "D"
        self.heading_angle = math.atan2(vehicle.dy, vehicle.dx)
        self.steering_angle = 0.0
        self.rpm = 900.0
        self.siren_active = (vehicle.vtype == VehicleType.POLICE)

        # Set max speed according to vehicle type
        if vehicle.vtype == VehicleType.POLICE:
            self.max_forward_speed = 11.5
        elif vehicle.vtype == VehicleType.CYBER_SEDAN:
            self.max_forward_speed = 10.0
        elif vehicle.vtype == VehicleType.TAXI:
            self.max_forward_speed = 8.5
        elif vehicle.vtype == VehicleType.BUS:
            self.max_forward_speed = 6.0

        # Snap camera inside vehicle cockpit (eye height slightly lower for car seating)
        camera.pos.x = vehicle.x
        camera.pos.y = vehicle.y
        camera.eye_height = 0.42
        camera.set_direction(self.heading_angle)

    def exit_vehicle(self, camera: Camera):
        if not self.is_driving or self.current_vehicle is None:
            return

        # Restore normal pedestrian eye height
        camera.eye_height = 0.5
        # Place player slightly to the sidewalk side of the car
        perp_angle = self.heading_angle + math.pi / 2.0
        camera.pos.x = self.current_vehicle.x + math.cos(perp_angle) * 0.9
        camera.pos.y = self.current_vehicle.y + math.sin(perp_angle) * 0.9

        self.is_driving = False
        self.current_vehicle = None
        self.speed = 0.0
        self.siren_active = False

    def update_physics(
        self,
        dt: float,
        throttle: float,   # -1.0 (reverse/brake) to +1.0 (gas)
        steer_input: float, # -1.0 (left) to +1.0 (right)
        camera: Camera,
        city_map: CityMap,
        other_vehicles: List[Vehicle]
    ) -> bool:
        """Updates vehicle physics, steering kinematics, collisions, and camera synchronization."""
        if not self.is_driving or self.current_vehicle is None:
            return False

        collision_event = False

        # 1. Steering Dynamics
        steer_speed = 4.0
        if steer_input != 0.0:
            self.steering_angle = max(-1.0, min(1.0, self.steering_angle + steer_input * steer_speed * dt))
        else:
            # Self-centering steering wheel
            self.steering_angle -= self.steering_angle * min(1.0, 6.0 * dt)

        # 2. Acceleration / Braking
        if throttle > 0.0:
            self.speed = min(self.max_forward_speed, self.speed + self.acceleration * throttle * dt)
        elif throttle < 0.0:
            if self.speed > 0.1:
                # Braking
                self.speed = max(0.0, self.speed - self.braking_force * abs(throttle) * dt)
            else:
                # Reverse Gear
                self.gear = "R"
                self.speed = max(-self.max_reverse_speed, self.speed - self.acceleration * 0.6 * abs(throttle) * dt)
        else:
            # Coasting drag
            if abs(self.speed) > 0.01:
                drag_step = self.drag * dt
                if self.speed > 0:
                    self.speed = max(0.0, self.speed - drag_step)
                else:
                    self.speed = min(0.0, self.speed + drag_step)

        if self.speed >= 0.0:
            self.gear = "D"

        # RPM calculation based on speed
        target_rpm = 900.0 + (abs(self.speed) / self.max_forward_speed) * 5800.0
        self.rpm += (target_rpm - self.rpm) * min(1.0, dt * 10.0)

        # 3. Kinematic Turning (Bicycle / Ackermann approximation)
        turn_rate = 1.8 * (self.speed / max(1.0, self.max_forward_speed * 0.7)) * self.steering_angle
        self.heading_angle += turn_rate * dt

        # 4. Integrate Position
        vx = math.cos(self.heading_angle) * self.speed * dt
        vy = math.sin(self.heading_angle) * self.speed * dt

        target_x = self.current_vehicle.x + vx
        target_y = self.current_vehicle.y + vy

        # Check collision with solid buildings (with buffer margin)
        radius = 0.35
        is_blocked_x = abs(vx) > 1e-5 and city_map.is_solid(target_x + math.copysign(radius, vx), self.current_vehicle.y)
        is_blocked_y = abs(vy) > 1e-5 and city_map.is_solid(self.current_vehicle.x, target_y + math.copysign(radius, vy))

        if is_blocked_x:
            self.speed *= -0.3  # Bouncy rebound
            collision_event = True
        else:
            self.current_vehicle.x = target_x

        if is_blocked_y:
            self.speed *= -0.3
            collision_event = True
        else:
            self.current_vehicle.y = target_y

        # Update vehicle heading vectors for external rendering
        self.current_vehicle.dx = int(round(math.cos(self.heading_angle)))
        self.current_vehicle.dy = int(round(math.sin(self.heading_angle)))

        # 5. Lock Camera to Vehicle Driver Cockpit View
        camera.pos.x = self.current_vehicle.x
        camera.pos.y = self.current_vehicle.y
        camera.set_direction(self.heading_angle)

        return collision_event
