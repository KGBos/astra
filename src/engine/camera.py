"""
First-person camera controller with physics, collision, and pitch for Astra 3D.
"""

import math
from src.engine.math3d import Vector2, clamp


class Camera:
    def __init__(self, x: float = 12.5, y: float = 12.5, fov_deg: float = 66.0):
        # Position in world coordinates
        self.pos = Vector2(x, y)
        
        # Direction vector (initial facing East (+X))
        self.dir = Vector2(1.0, 0.0)
        
        # Camera plane vector (perpendicular to dir, length determines FOV)
        # FOV = 2 * atan(plane_len / dir_len) => plane_len = tan(FOV / 2)
        fov_rad = math.radians(fov_deg)
        plane_len = math.tan(fov_rad / 2.0)
        self.plane = Vector2(0.0, plane_len)

        # Eye height and pitch
        self.eye_height = 0.5    # 0.5 = middle height in unit cube
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

    def set_direction(self, angle_rad: float):
        """Sets absolute looking angle in radians (0 = East, pi/2 = South, pi = West, 3pi/2 = North)."""
        plane_len = self.plane.length()
        self.dir = Vector2(math.cos(angle_rad), math.sin(angle_rad))
        # Perpendicular vector to the right of direction
        self.plane = Vector2(-self.dir.y * plane_len, self.dir.x * plane_len)

    def rotate(self, angle_rad: float):
        """Rotates camera direction and plane by relative angle in radians."""
        self.dir = self.dir.rotated(angle_rad).normalized()
        plane_len = self.plane.length()
        self.plane = Vector2(-self.dir.y * plane_len, self.dir.x * plane_len)

    def pitch_look(self, delta_pitch: float, max_pitch: float = 18.0):
        """Pitches camera view up/down."""
        self.pitch = clamp(self.pitch + delta_pitch, -max_pitch, max_pitch)

    def jump(self):
        """Initiates a jump if on ground."""
        if not self.is_jumping and self.eye_height <= 0.51:
            self.is_jumping = True
            self.z_velocity = 2.8

    def update_physics(self, dt: float):
        """Updates jumping and gravity physics."""
        if self.is_jumping:
            self.eye_height += self.z_velocity * dt
            self.z_velocity -= 9.8 * dt  # Gravity
            if self.eye_height <= 0.5:
                self.eye_height = 0.5
                self.z_velocity = 0.0
                self.is_jumping = False

    def move_forward(self, dt: float, is_sprinting: bool, world_map) -> bool:
        speed = self.move_speed * (self.sprint_mult if is_sprinting else 1.0) * dt
        dx = self.dir.x * speed
        dy = self.dir.y * speed
        return self._apply_movement(dx, dy, world_map, is_moving=True, dt=dt)

    def move_backward(self, dt: float, is_sprinting: bool, world_map) -> bool:
        speed = self.move_speed * (self.sprint_mult if is_sprinting else 1.0) * dt * 0.7
        dx = -self.dir.x * speed
        dy = -self.dir.y * speed
        return self._apply_movement(dx, dy, world_map, is_moving=True, dt=dt)

    def strafe_left(self, dt: float, world_map) -> bool:
        speed = self.move_speed * 0.8 * dt
        # Strafe left is perpendicular to dir: (-dir.y, dir.x)
        dx = self.dir.y * speed
        dy = -self.dir.x * speed
        return self._apply_movement(dx, dy, world_map, is_moving=True, dt=dt)

    def strafe_right(self, dt: float, world_map) -> bool:
        speed = self.move_speed * 0.8 * dt
        dx = -self.dir.y * speed
        dy = self.dir.x * speed
        return self._apply_movement(dx, dy, world_map, is_moving=True, dt=dt)

    def _apply_movement(self, dx: float, dy: float, world_map, is_moving: bool, dt: float) -> bool:
        """Applies movement with axis-independent wall sliding and collision detection."""
        moved = False
        r = self.collision_radius

        # Check X movement
        new_x = self.pos.x + dx
        check_x = new_x + (r if dx > 0 else -r)
        if not world_map.is_solid(check_x, self.pos.y - r) and \
           not world_map.is_solid(check_x, self.pos.y + r):
            self.pos.x = new_x
            moved = True

        # Check Y movement
        new_y = self.pos.y + dy
        check_y = new_y + (r if dy > 0 else -r)
        if not world_map.is_solid(self.pos.x - r, check_y) and \
           not world_map.is_solid(self.pos.x + r, check_y):
            self.pos.y = new_y
            moved = True

        # Head bobbing
        if is_moving and moved:
            self.bob_timer += dt * 10.0
            self.bob_amount = math.sin(self.bob_timer) * 0.04
        else:
            self.bob_amount = 0.0

        return moved
