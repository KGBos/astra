"""
First-person camera controller with vehicle driving physics, collision, and headlights for Astra 3D.
"""

import math
from typing import Optional
from src.engine.math3d import Vector2, clamp


class Camera:
    def __init__(self, x: float = 12.5, y: float = 12.5, fov_deg: float = 66.0):
        # Position in world coordinates
        self.pos = Vector2(x, y)
        
        # Direction vector (initial facing East (+X))
        self.dir = Vector2(1.0, 0.0)
        
        # Camera plane vector (perpendicular to dir, length determines FOV)
        fov_rad = math.radians(fov_deg)
        self.base_plane_len = math.tan(fov_rad / 2.0)
        self.plane = Vector2(0.0, self.base_plane_len)

        # Eye height and pitch
        self.eye_height = 0.5    # 0.5 = pedestrian height, 0.35 = car driving height
        self.pitch = 0.0         # vertical look offset in pixels/characters [-15, 15]
        self.z_velocity = 0.0
        self.is_jumping = False

        # Movement attributes
        self.move_speed = 4.5    # units per second
        self.sprint_mult = 1.8
        self.rot_speed = 2.8     # radians per second
        self.collision_radius = 0.25

        # Head bobbing
        self.bob_timer = 0.0
        self.bob_amount = 0.0

        # Headlight & Flashlight
        self.headlights_on = True

        # Vehicle Driving Mode
        self.is_driving = False
        self.vehicle_type_name = ""
        self.car_velocity = 0.0
        self.car_max_speed = 10.0
        self.nitro_active = False
        self.nitro_meter = 100.0

    def enter_vehicle(self, vtype_name: str, vx: float, vy: float, vdx: float, vdy: float):
        self.is_driving = True
        self.vehicle_type_name = vtype_name
        self.pos = Vector2(vx, vy)
        self.eye_height = 0.38
        self.car_velocity = 2.0
        if vdx != 0 or vdy != 0:
            self.set_direction(math.atan2(vdy, vdx))

    def exit_vehicle(self):
        self.is_driving = False
        self.vehicle_type_name = ""
        self.eye_height = 0.5
        self.car_velocity = 0.0
        self.nitro_active = False

    def set_direction(self, angle_rad: float):
        """Sets absolute looking angle in radians."""
        plane_len = self.plane.length() if self.plane.length() > 0 else self.base_plane_len
        self.dir = Vector2(math.cos(angle_rad), math.sin(angle_rad))
        self.plane = Vector2(-self.dir.y * plane_len, self.dir.x * plane_len)

    def rotate(self, angle_rad: float):
        """Rotates camera direction and plane by relative angle in radians."""
        self.dir = self.dir.rotated(angle_rad).normalized()
        plane_len = self.plane.length() if self.plane.length() > 0 else self.base_plane_len
        self.plane = Vector2(-self.dir.y * plane_len, self.dir.x * plane_len)

    def pitch_look(self, delta_pitch: float, max_pitch: float = 18.0):
        self.pitch = clamp(self.pitch + delta_pitch, -max_pitch, max_pitch)

    def jump(self):
        if not self.is_driving and not self.is_jumping and self.eye_height <= 0.51:
            self.is_jumping = True
            self.z_velocity = 2.8

    def update_physics(self, dt: float, world_map):
        """Updates jumping or vehicle momentum & nitro recharge."""
        if self.is_driving:
            # Nitro recharge
            if not self.nitro_active and self.nitro_meter < 100.0:
                self.nitro_meter = min(100.0, self.nitro_meter + 15.0 * dt)
            elif self.nitro_active:
                self.nitro_meter = max(0.0, self.nitro_meter - 40.0 * dt)
                if self.nitro_meter <= 0.0:
                    self.nitro_active = False

            # Natural drag deceleration
            if abs(self.car_velocity) > 0.1:
                drag = 3.5 * dt
                if self.car_velocity > 0:
                    self.car_velocity = max(0.0, self.car_velocity - drag)
                else:
                    self.car_velocity = min(0.0, self.car_velocity + drag)

                # Move vehicle forward/back
                dx = self.dir.x * self.car_velocity * dt
                dy = self.dir.y * self.car_velocity * dt
                self._apply_movement(dx, dy, world_map, is_moving=True, dt=dt)
        else:
            if self.is_jumping:
                self.eye_height += self.z_velocity * dt
                self.z_velocity -= 9.8 * dt  # Gravity
                if self.eye_height <= 0.5:
                    self.eye_height = 0.5
                    self.z_velocity = 0.0
                    self.is_jumping = False

    # Vehicle driving controls
    def car_accelerate(self, dt: float, nitro: bool = False):
        self.nitro_active = (nitro and self.nitro_meter > 5.0)
        accel = 12.0 * (1.8 if self.nitro_active else 1.0)
        max_v = self.car_max_speed * (1.6 if self.nitro_active else 1.0)
        self.car_velocity = min(max_v, self.car_velocity + accel * dt)

    def car_brake(self, dt: float):
        if self.car_velocity > 0:
            self.car_velocity = max(-3.0, self.car_velocity - 18.0 * dt)
        else:
            self.car_velocity = max(-3.5, self.car_velocity - 8.0 * dt)

    def car_steer(self, steer_dir: float, dt: float):
        # Steer sensitivity scales with forward speed
        steer_rate = 2.2 * (0.4 + 0.6 * min(1.0, abs(self.car_velocity) / 4.0))
        self.rotate(steer_dir * steer_rate * dt)

    # Pedestrian movement controls
    def move_forward(self, dt: float, is_sprinting: bool, world_map) -> bool:
        if self.is_driving:
            self.car_accelerate(dt, nitro=is_sprinting)
            return True
        speed = self.move_speed * (self.sprint_mult if is_sprinting else 1.0) * dt
        dx = self.dir.x * speed
        dy = self.dir.y * speed
        return self._apply_movement(dx, dy, world_map, is_moving=True, dt=dt)

    def move_backward(self, dt: float, is_sprinting: bool, world_map) -> bool:
        if self.is_driving:
            self.car_brake(dt)
            return True
        speed = self.move_speed * (self.sprint_mult if is_sprinting else 1.0) * dt * 0.7
        dx = -self.dir.x * speed
        dy = -self.dir.y * speed
        return self._apply_movement(dx, dy, world_map, is_moving=True, dt=dt)

    def strafe_left(self, dt: float, world_map) -> bool:
        if self.is_driving:
            self.car_steer(-1.0, dt)
            return True
        speed = self.move_speed * 0.8 * dt
        dx = self.dir.y * speed
        dy = -self.dir.x * speed
        return self._apply_movement(dx, dy, world_map, is_moving=True, dt=dt)

    def strafe_right(self, dt: float, world_map) -> bool:
        if self.is_driving:
            self.car_steer(1.0, dt)
            return True
        speed = self.move_speed * 0.8 * dt
        dx = -self.dir.y * speed
        dy = self.dir.x * speed
        return self._apply_movement(dx, dy, world_map, is_moving=True, dt=dt)

    def _apply_movement(self, dx: float, dy: float, world_map, is_moving: bool, dt: float) -> bool:
        moved = False
        r = self.collision_radius if not self.is_driving else 0.4

        # Check X movement
        new_x = self.pos.x + dx
        check_x = new_x + (r if dx > 0 else -r)
        if not world_map.is_solid(check_x, self.pos.y - r) and \
           not world_map.is_solid(check_x, self.pos.y + r):
            self.pos.x = new_x
            moved = True
        else:
            if self.is_driving:
                self.car_velocity *= 0.3  # Slow down on wall bumper collision

        # Check Y movement
        new_y = self.pos.y + dy
        check_y = new_y + (r if dy > 0 else -r)
        if not world_map.is_solid(self.pos.x - r, check_y) and \
           not world_map.is_solid(self.pos.x + r, check_y):
            self.pos.y = new_y
            moved = True
        else:
            if self.is_driving:
                self.car_velocity *= 0.3

        # Head bobbing (only while walking)
        if not self.is_driving and is_moving and moved:
            self.bob_timer += dt * 10.0
            self.bob_amount = math.sin(self.bob_timer) * 0.04
        else:
            self.bob_amount = 0.0

        return moved
