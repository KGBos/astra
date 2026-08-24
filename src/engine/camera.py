"""
First-person camera controller with physics, collision, and pitch for Astra 3D.

All units are honest metres: eye height, speeds, radii, and jump clearance.
"""

import math
from src.engine.math3d import Vector2, clamp


class Camera:
    EYE_HEIGHT_M = 1.7      # standing human eye elevation
    SEATED_EYE_M = 1.0      # driver cockpit eye elevation
    WALK_SPEED = 3.6        # m/s
    SPRINT_MULT = 2.0       # sprint => 7.2 m/s
    BACKWARD_MULT = 0.7
    STRAFE_MULT = 0.8
    ROT_SPEED = 2.8         # radians per second
    COLLISION_RADIUS = 0.35 # shoulder radius in metres
    JUMP_VELOCITY = 4.4     # m/s => ~1.0 m clearance (v = sqrt(2 * g * h))
    GRAVITY = 9.8           # m/s^2
    BOB_AMPLITUDE = 0.02    # fraction of viewport height per bob cycle

    def __init__(self, x: float = 12.5, y: float = 12.5, fov_deg: float = 66.0):
        # Position in world coordinates (1 unit = 1 metre)
        self.pos = Vector2(x, y)

        # Direction vector (initial facing East (+X))
        self.dir = Vector2(1.0, 0.0)

        # Camera plane vector (perpendicular to dir, length determines FOV)
        # FOV = 2 * atan(plane_len / dir_len) => plane_len = tan(FOV / 2)
        fov_rad = math.radians(fov_deg)
        plane_len = math.tan(fov_rad / 2.0)
        self.plane = Vector2(0.0, plane_len)

        # Eye elevation above the ground in metres
        self.eye_m = self.EYE_HEIGHT_M
        self.pitch = 0.0         # vertical look offset in pixels/characters [-15, 15]
        self.z_velocity = 0.0
        self.is_jumping = False

        # Movement attributes (metres per second)
        self.move_speed = self.WALK_SPEED
        self.sprint_mult = self.SPRINT_MULT
        self.rot_speed = self.ROT_SPEED
        self.collision_radius = self.COLLISION_RADIUS

        # Head bobbing
        self.bob_timer = 0.0
        self.bob_amount = 0.0

        # Vehicle headlights (beam cone boost in the raycaster).
        # OFF by default; the vehicle controller turns them on while driving
        self.headlights_on = False

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
        if not self.is_jumping and self.eye_m <= self.EYE_HEIGHT_M + 0.01:
            self.is_jumping = True
            self.z_velocity = self.JUMP_VELOCITY

    def update_physics(self, dt: float):
        """Updates jumping and gravity physics."""
        if self.is_jumping:
            self.eye_m += self.z_velocity * dt
            self.z_velocity -= self.GRAVITY * dt
            if self.eye_m <= self.EYE_HEIGHT_M:
                self.eye_m = self.EYE_HEIGHT_M
                self.z_velocity = 0.0
                self.is_jumping = False

    def move_forward(self, dt: float, is_sprinting: bool, world_map) -> bool:
        speed = self.move_speed * (self.sprint_mult if is_sprinting else 1.0) * dt
        dx = self.dir.x * speed
        dy = self.dir.y * speed
        return self._apply_movement(dx, dy, world_map, is_moving=True, dt=dt)

    def move_backward(self, dt: float, is_sprinting: bool, world_map) -> bool:
        speed = self.move_speed * (self.sprint_mult if is_sprinting else 1.0) * dt * self.BACKWARD_MULT
        dx = -self.dir.x * speed
        dy = -self.dir.y * speed
        return self._apply_movement(dx, dy, world_map, is_moving=True, dt=dt)

    def strafe_left(self, dt: float, world_map) -> bool:
        speed = self.move_speed * self.STRAFE_MULT * dt
        # Strafe left is perpendicular to dir: (-dir.y, dir.x)
        dx = self.dir.y * speed
        dy = -self.dir.x * speed
        return self._apply_movement(dx, dy, world_map, is_moving=True, dt=dt)

    def strafe_right(self, dt: float, world_map) -> bool:
        speed = self.move_speed * self.STRAFE_MULT * dt
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
            self.bob_amount = math.sin(self.bob_timer) * self.BOB_AMPLITUDE
        else:
            self.bob_amount = 0.0

        return moved
