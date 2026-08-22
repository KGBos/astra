"""
Core 3D Raycasting Engine, Z-Buffer, Floor/Sky Renderer, and 3D Sprite Projector for Astra 3D.
"""

import math
from typing import List, Tuple, Optional
from src.engine.camera import Camera
from src.engine.math3d import clamp, RayHit
from src.world.city_map import CityMap, FloorType
from src.world.textures import get_texture
from src.world.day_night import DayNightCycle
from src.entities.sprite import Sprite
from src.renderer.screen_buffer import ScreenBuffer


class Raycaster:
    def __init__(self, screen_w: int = 80, screen_h: int = 32):
        self.width = screen_w
        self.height = screen_h
        self.z_buffer: List[float] = [float('inf') for _ in range(screen_w)]

    def resize(self, width: int, height: int):
        self.width = width
        self.height = height
        self.z_buffer = [float('inf') for _ in range(width)]

    def render(
        self,
        camera: Camera,
        city_map: CityMap,
        sprites: List[Sprite],
        day_night: DayNightCycle,
        buffer: ScreenBuffer
    ):
        ambient = day_night.get_ambient_light()
        zenith_col, horizon_col = day_night.get_sky_gradient()

        # Camera horizon with pitch and eye height offset
        horizon_y = int(self.height / 2.0 + camera.pitch + (camera.eye_height - 0.5) * 8.0 + camera.bob_amount * self.height)

        # 1. Render Sky (Ceiling) & Floor Background Slices
        self._render_sky_and_floor(camera, city_map, day_night, horizon_y, buffer)

        # 2. Raycast Walls & Record Z-Buffer
        for x in range(self.width):
            hit = self._cast_ray(x, camera, city_map)
            if hit.hit:
                self.z_buffer[x] = hit.perp_wall_dist
                self._draw_wall_slice(x, hit, camera, horizon_y, ambient, buffer)
            else:
                self.z_buffer[x] = 100.0

        # 3. Project & Draw 3D Billboarding Sprites (Vehicles, Streetlamps, Trees)
        self._render_sprites(camera, sprites, horizon_y, ambient, buffer)

    def _cast_ray(self, screen_x: int, camera: Camera, city_map: CityMap) -> RayHit:
        camera_x = 2.0 * screen_x / float(self.width) - 1.0
        ray_dir_x = camera.dir.x + camera.plane.x * camera_x
        ray_dir_y = camera.dir.y + camera.plane.y * camera_x

        map_x = int(camera.pos.x)
        map_y = int(camera.pos.y)

        delta_dist_x = abs(1.0 / ray_dir_x) if ray_dir_x != 0 else 1e30
        delta_dist_y = abs(1.0 / ray_dir_y) if ray_dir_y != 0 else 1e30

        if ray_dir_x < 0:
            step_x = -1
            side_dist_x = (camera.pos.x - map_x) * delta_dist_x
        else:
            step_x = 1
            side_dist_x = (map_x + 1.0 - camera.pos.x) * delta_dist_x

        if ray_dir_y < 0:
            step_y = -1
            side_dist_y = (camera.pos.y - map_y) * delta_dist_y
        else:
            step_y = 1
            side_dist_y = (map_y + 1.0 - camera.pos.y) * delta_dist_y

        hit = False
        side = 0
        max_steps = 45

        for _ in range(max_steps):
            if side_dist_x < side_dist_y:
                side_dist_x += delta_dist_x
                map_x += step_x
                side = 0
            else:
                side_dist_y += delta_dist_y
                map_y += step_y
                side = 1

            if city_map.is_solid(map_x, map_y):
                hit = True
                break

        if not hit:
            return RayHit(False, map_x, map_y, 0, 100.0, 0.0, 0, 1.0, ray_dir_x, ray_dir_y)

        if side == 0:
            perp_wall_dist = (map_x - camera.pos.x + (1 - step_x) / 2.0) / ray_dir_x
            wall_x = camera.pos.y + perp_wall_dist * ray_dir_y
        else:
            perp_wall_dist = (map_y - camera.pos.y + (1 - step_y) / 2.0) / ray_dir_y
            wall_x = camera.pos.x + perp_wall_dist * ray_dir_x

        wall_x -= math.floor(wall_x)
        wall_type = city_map.get_wall_type(map_x, map_y)
        wall_h = city_map.get_wall_height(wall_type)
        perp_wall_dist = max(0.08, perp_wall_dist)

        return RayHit(True, map_x, map_y, side, perp_wall_dist, wall_x, wall_type, wall_h, ray_dir_x, ray_dir_y)

    def _draw_wall_slice(
        self,
        screen_x: int,
        hit: RayHit,
        camera: Camera,
        horizon_y: int,
        ambient: float,
        buffer: ScreenBuffer
    ):
        texture = get_texture(hit.wall_type)
        line_height = int((self.height / hit.perp_wall_dist) * hit.wall_height)
        
        draw_start = int(horizon_y - line_height / 2.0)
        draw_end = int(horizon_y + line_height / 2.0)

        # Distance attenuation and side shading (North/South side gets directional shadow)
        side_mult = 0.82 if hit.side == 1 else 1.0
        distance_shade = (1.0 / (1.0 + 0.08 * hit.perp_wall_dist + 0.005 * hit.perp_wall_dist * hit.perp_wall_dist))
        shade = clamp(distance_shade * ambient * side_mult, 0.1, 1.0)

        y0 = max(0, draw_start)
        y1 = min(self.height - 1, draw_end)

        for y in range(y0, y1 + 1):
            # Normalized vertical texture coordinate
            v = (y - draw_start) / float(line_height) if line_height > 0 else 0.0
            char, fg_raw, bg_raw = texture.sample(hit.wall_x, v)

            # Apply lighting
            fg = (int(fg_raw[0] * shade), int(fg_raw[1] * shade), int(fg_raw[2] * shade))
            bg = (int(bg_raw[0] * shade), int(bg_raw[1] * shade), int(bg_raw[2] * shade))

            buffer.set_pixel(screen_x, y, char, fg, bg)

    def _render_sky_and_floor(
        self,
        camera: Camera,
        city_map: CityMap,
        day_night: DayNightCycle,
        horizon_y: int,
        buffer: ScreenBuffer
    ):
        zenith_col, horizon_col = day_night.get_sky_gradient()
        ambient = day_night.get_ambient_light()
        is_night = day_night.time_of_day > 20.0 or day_night.time_of_day < 5.0

        # Sky rows (above horizon)
        for y in range(0, max(0, min(self.height, horizon_y))):
            t = y / float(max(1, horizon_y))  # 0 at top, 1 at horizon
            r = int(zenith_col[0] + (horizon_col[0] - zenith_col[0]) * t)
            g = int(zenith_col[1] + (horizon_col[1] - zenith_col[1]) * t)
            b = int(zenith_col[2] + (horizon_col[2] - zenith_col[2]) * t)
            sky_col = (r, g, b)

            for x in range(self.width):
                char = ' '
                if is_night and ((x * 17 + y * 31) % 67 == 0):
                    char = '.' if (x + y) % 2 == 0 else '*'
                    buffer.set_pixel(x, y, char, (240, 240, 255), sky_col)
                else:
                    buffer.set_pixel(x, y, char, (100, 100, 120), sky_col)

        # Floor rows (below horizon)
        for y in range(max(0, horizon_y), self.height):
            dy = float(y - horizon_y)
            if dy <= 0.0:
                continue

            # Row distance
            row_dist = (0.5 * self.height) / dy
            floor_shade = clamp((1.0 / (1.0 + 0.1 * row_dist + 0.008 * row_dist * row_dist)) * ambient, 0.1, 1.0)

            # Left and right ray step
            ray_dir_x0 = camera.dir.x - camera.plane.x
            ray_dir_y0 = camera.dir.y - camera.plane.y
            ray_dir_x1 = camera.dir.x + camera.plane.x
            ray_dir_y1 = camera.dir.y + camera.plane.y

            step_x = row_dist * (ray_dir_x1 - ray_dir_x0) / float(self.width)
            step_y = row_dist * (ray_dir_y1 - ray_dir_y0) / float(self.width)

            floor_x = camera.pos.x + row_dist * ray_dir_x0
            floor_y = camera.pos.y + row_dist * ray_dir_y0

            for x in range(self.width):
                cell_x = int(floor_x)
                cell_y = int(floor_y)
                ftype = city_map.get_floor_type(cell_x, cell_y)

                # Road & sidewalk texture characters
                fx_frac = floor_x - cell_x
                fy_frac = floor_y - cell_y

                if ftype in (FloorType.ROAD_NS, FloorType.ROAD_EW, FloorType.INTERSECTION):
                    # Asphalt road
                    is_center_line = (ftype == FloorType.ROAD_NS and abs(fx_frac - 0.5) < 0.08) or \
                                     (ftype == FloorType.ROAD_EW and abs(fy_frac - 0.5) < 0.08)
                    if is_center_line:
                        char = '=' if ftype == FloorType.ROAD_EW else '|'
                        fg = (int(255 * floor_shade), int(220 * floor_shade), int(0 * floor_shade))
                        bg = (int(40 * floor_shade), int(40 * floor_shade), int(45 * floor_shade))
                    else:
                        char = '.' if (int(floor_x * 4) + int(floor_y * 4)) % 3 == 0 else ' '
                        fg = (int(80 * floor_shade), int(80 * floor_shade), int(90 * floor_shade))
                        bg = (int(25 * floor_shade), int(26 * floor_shade), int(30 * floor_shade))
                elif ftype == FloorType.PARK_GRASS:
                    char = '"' if (int(floor_x * 3) + int(floor_y * 3)) % 2 == 0 else ','
                    fg = (int(40 * floor_shade), int(160 * floor_shade), int(60 * floor_shade))
                    bg = (int(15 * floor_shade), int(45 * floor_shade), int(20 * floor_shade))
                elif ftype == FloorType.PLAZA_TILES:
                    char = '+' if (int(floor_x * 2) + int(floor_y * 2)) % 2 == 0 else ' '
                    fg = (int(160 * floor_shade), int(150 * floor_shade), int(140 * floor_shade))
                    bg = (int(50 * floor_shade), int(48 * floor_shade), int(45 * floor_shade))
                else:
                    # Sidewalk concrete tiles
                    char = '.' if (int(floor_x * 4) + int(floor_y * 4)) % 2 == 0 else '_'
                    fg = (int(140 * floor_shade), int(140 * floor_shade), int(150 * floor_shade))
                    bg = (int(45 * floor_shade), int(45 * floor_shade), int(50 * floor_shade))

                buffer.set_pixel(x, y, char, fg, bg)
                floor_x += step_x
                floor_y += step_y

    def _render_sprites(
        self,
        camera: Camera,
        sprites: List[Sprite],
        horizon_y: int,
        ambient: float,
        buffer: ScreenBuffer
    ):
        # Calculate distance squared and filter out sprites behind or too far
        active_sprites: List[Tuple[float, Sprite]] = []
        for spr in sprites:
            dx = spr.x - camera.pos.x
            dy = spr.y - camera.pos.y
            dist_sq = dx * dx + dy * dy
            if dist_sq < 900.0:  # within 30 units
                active_sprites.append((dist_sq, spr))

        # Sort far-to-near for Painter's algorithm
        active_sprites.sort(key=lambda item: item[0], reverse=True)

        inv_det = 1.0 / (camera.plane.x * camera.dir.y - camera.dir.x * camera.plane.y)

        for dist_sq, spr in active_sprites:
            spr_x = spr.x - camera.pos.x
            spr_y = spr.y - camera.pos.y

            # Transform sprite with inverted camera matrix
            trans_x = inv_det * (camera.dir.y * spr_x - camera.dir.x * spr_y)
            trans_y = inv_det * (-camera.plane.y * spr_x + camera.plane.x * spr_y)  # depth

            if trans_y <= 0.2:
                continue

            spr_screen_x = int((self.width / 2.0) * (1.0 + trans_x / trans_y))
            spr_h = abs(int((self.height / trans_y) * spr.scale_y))
            spr_w = abs(int((self.height / trans_y) * spr.scale_x))

            if spr_h == 0 or spr_w == 0:
                continue

            vert_offset = int((spr.vertical_offset * self.height) / trans_y)
            draw_y0 = int(horizon_y - spr_h / 2.0 - vert_offset)
            draw_y1 = int(horizon_y + spr_h / 2.0 - vert_offset)

            draw_x0 = int(spr_screen_x - spr_w / 2.0)
            draw_x1 = int(spr_screen_x + spr_w / 2.0)

            # Shade calculation
            dist = math.sqrt(dist_sq)
            distance_shade = 1.0 / (1.0 + 0.09 * dist + 0.005 * dist_sq)
            shade = 1.0 if spr.is_luminous else clamp(distance_shade * ambient, 0.15, 1.0)

            x_start = max(0, draw_x0)
            x_end = min(self.width - 1, draw_x1)

            for stripe in range(x_start, x_end + 1):
                # Depth test against wall Z-buffer
                if trans_y < self.z_buffer[stripe]:
                    u = (stripe - draw_x0) / float(spr_w) if spr_w > 0 else 0.0
                    tex_x = int(u * spr.width)
                    tex_x = max(0, min(tex_x, spr.width - 1))

                    y_start = max(0, draw_y0)
                    y_end = min(self.height - 1, draw_y1)

                    for y in range(y_start, y_end + 1):
                        v = (y - draw_y0) / float(spr_h) if spr_h > 0 else 0.0
                        tex_y = int(v * spr.height)
                        tex_y = max(0, min(tex_y, spr.height - 1))

                        char = spr.chars[tex_y][tex_x]
                        if char != ' ':  # transparency key
                            fg_raw = spr.fg_colors[tex_y][tex_x]
                            fg = (int(fg_raw[0] * shade), int(fg_raw[1] * shade), int(fg_raw[2] * shade))
                            buffer.set_pixel(stripe, y, char, fg, None)
