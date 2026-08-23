"""
Core 3D Raycasting Engine, Z-Buffer, Floor/Sky Renderer, Volumetric Fog, Wet Surface Reflections, Multi-district floors & 3D Sprite Projector.
Author: Valerie Sterling ⚡ & Darius Thorne 📐
"""

import math
from typing import List, Tuple, Optional
from src.engine.camera import Camera
from src.engine.math3d import clamp, RayHit
from src.world.city_map import CityMap, FloorType
from src.world.textures import get_texture
from src.world.day_night import DayNightCycle
from src.world.weather import WeatherSystem
from src.entities.sprite import Sprite
from src.renderer.screen_buffer import ScreenBuffer


def _blend_color(c1: Tuple[int, int, int], c2: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    f = clamp(factor, 0.0, 1.0)
    return (
        int(c1[0] + (c2[0] - c1[0]) * f),
        int(c1[1] + (c2[1] - c1[1]) * f),
        int(c1[2] + (c2[2] - c1[2]) * f)
    )


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
        buffer: ScreenBuffer,
        weather: Optional[WeatherSystem] = None,
        flashlight_on: bool = False
    ):
        base_ambient = day_night.get_ambient_light()
        zenith_col, horizon_col = day_night.get_sky_gradient()

        # Check for lightning surge in storm mode
        lightning_intensity = weather.get_lightning_intensity() if weather else 0.0
        lightning_col = weather.get_lightning_color() if weather else (255, 255, 255)
        
        # Modulate ambient with lightning flash
        ambient = clamp(base_ambient * (1.0 + lightning_intensity * 2.8), 0.1, 2.0)

        # Camera horizon with pitch and eye height offset
        horizon_y = int(self.height / 2.0 + camera.pitch + (camera.eye_height - 0.5) * 8.0 + camera.bob_amount * self.height)

        # 1. Render Sky (Ceiling) & Floor Background Slices
        self._render_sky_and_floor(
            camera=camera,
            city_map=city_map,
            day_night=day_night,
            weather=weather,
            horizon_y=horizon_y,
            lightning_intensity=lightning_intensity,
            lightning_col=lightning_col,
            buffer=buffer
        )

        # 2. Raycast Walls & Record Z-Buffer
        for x in range(self.width):
            hit = self._cast_ray(x, camera, city_map)
            if hit.hit:
                self.z_buffer[x] = hit.perp_wall_dist
                self._draw_wall_slice(
                    screen_x=x,
                    hit=hit,
                    camera=camera,
                    horizon_y=horizon_y,
                    ambient=ambient,
                    weather=weather,
                    flashlight_on=flashlight_on,
                    buffer=buffer
                )
            else:
                self.z_buffer[x] = 100.0

        # 3. Project & Draw 3D Billboarding Sprites (Vehicles, Streetlamps, Trees, Pedestrians)
        self._render_sprites(
            camera=camera,
            sprites=sprites,
            horizon_y=horizon_y,
            ambient=ambient,
            weather=weather,
            buffer=buffer
        )

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
        weather: Optional[WeatherSystem],
        flashlight_on: bool,
        buffer: ScreenBuffer
    ):
        texture = get_texture(hit.wall_type)
        line_height = int((self.height / hit.perp_wall_dist) * hit.wall_height)
        
        draw_start = int(horizon_y - line_height / 2.0)
        draw_end = int(horizon_y + line_height / 2.0)

        # Distance attenuation and side shading
        side_mult = 0.82 if hit.side == 1 else 1.0
        distance_shade = (1.0 / (1.0 + 0.08 * hit.perp_wall_dist + 0.005 * hit.perp_wall_dist * hit.perp_wall_dist))
        shade = clamp(distance_shade * ambient * side_mult, 0.1, 1.0)

        # Tactical Flashlight conical boost in front of camera
        if flashlight_on:
            cam_dot_ray = (camera.dir.x * hit.ray_dir_x + camera.dir.y * hit.ray_dir_y)
            if cam_dot_ray > 0.85:  # Narrow tactical beam
                beam_focus = (cam_dot_ray - 0.85) / 0.15
                beam_boost = (1.8 / (1.0 + 0.12 * hit.perp_wall_dist)) * beam_focus
                shade = clamp(shade + beam_boost, 0.1, 1.8)

        # Volumetric Fog blending factor
        fog_factor = 0.0
        if weather and weather.fog_density > 0:
            fog_factor = clamp(1.0 - math.exp(-hit.perp_wall_dist * weather.fog_density), 0.0, 0.95)

        y0 = max(0, draw_start)
        y1 = min(self.height - 1, draw_end)

        for y in range(y0, y1 + 1):
            tex_v = (y - draw_start) / float(max(1, draw_end - draw_start))
            tex_u = hit.wall_x
            
            char, fg_raw, bg_raw = texture.sample(tex_u, tex_v)

            fg = (int(fg_raw[0] * shade), int(fg_raw[1] * shade), int(fg_raw[2] * shade))
            bg = (int(bg_raw[0] * shade), int(bg_raw[1] * shade), int(bg_raw[2] * shade))

            # Apply Volumetric Fog Color Blending
            if fog_factor > 0.0 and weather:
                fg = _blend_color(fg, weather.fog_color, fog_factor)
                bg = _blend_color(bg, weather.fog_color, fog_factor)

            buffer.set_pixel(screen_x, y, char, fg, bg)

    def _render_sky_and_floor(
        self,
        camera: Camera,
        city_map: CityMap,
        day_night: DayNightCycle,
        weather: Optional[WeatherSystem],
        horizon_y: int,
        lightning_intensity: float,
        lightning_col: Tuple[int, int, int],
        buffer: ScreenBuffer
    ):
        zenith_col, horizon_col = day_night.get_sky_gradient()
        ambient = day_night.get_ambient_light()
        is_night = day_night.time_of_day > 20.0 or day_night.time_of_day < 5.0
        wetness = weather.wetness if weather else 0.0

        # Sky rows (above horizon)
        for y in range(0, max(0, min(self.height, horizon_y))):
            t = y / float(max(1, horizon_y))
            r = int(zenith_col[0] + (horizon_col[0] - zenith_col[0]) * t)
            g = int(zenith_col[1] + (horizon_col[1] - zenith_col[1]) * t)
            b = int(zenith_col[2] + (horizon_col[2] - zenith_col[2]) * t)
            sky_col = (r, g, b)

            if lightning_intensity > 0.0:
                sky_col = _blend_color(sky_col, lightning_col, lightning_intensity * 0.9)

            if weather and weather.fog_density > 0.04:
                sky_col = _blend_color(sky_col, weather.fog_color, min(0.85, weather.fog_density * 6.0))

            for x in range(self.width):
                char = ' '
                if is_night and lightning_intensity < 0.1 and ((x * 17 + y * 31) % 67 == 0):
                    char = '.' if (x + y) % 2 == 0 else '*'
                    buffer.set_pixel(x, y, char, (240, 240, 255), sky_col)
                else:
                    buffer.set_pixel(x, y, char, (100, 100, 120), sky_col)

        # Floor rows (below horizon)
        for y in range(max(0, horizon_y), self.height):
            dy = float(y - horizon_y)
            if dy <= 0.0:
                continue

            row_dist = (0.5 * self.height) / dy
            floor_shade = clamp((1.0 / (1.0 + 0.1 * row_dist + 0.008 * row_dist * row_dist)) * ambient, 0.1, 1.0)

            ray_dir_x0 = camera.dir.x - camera.plane.x
            ray_dir_y0 = camera.dir.y - camera.plane.y
            ray_dir_x1 = camera.dir.x + camera.plane.x
            ray_dir_y1 = camera.dir.y + camera.plane.y

            step_x = row_dist * (ray_dir_x1 - ray_dir_x0) / float(self.width)
            step_y = row_dist * (ray_dir_y1 - ray_dir_y0) / float(self.width)

            floor_x = camera.pos.x + row_dist * ray_dir_x0
            floor_y = camera.pos.y + row_dist * ray_dir_y0

            floor_fog = 0.0
            if weather and weather.fog_density > 0:
                floor_fog = clamp(1.0 - math.exp(-row_dist * weather.fog_density), 0.0, 0.95)

            for x in range(self.width):
                cell_x = int(floor_x)
                cell_y = int(floor_y)
                ftype = city_map.get_floor_type(cell_x, cell_y)

                fx_frac = floor_x - cell_x
                fy_frac = floor_y - cell_y

                if ftype in (FloorType.ROAD_NS, FloorType.ROAD_EW, FloorType.INTERSECTION):
                    is_center_line = (ftype == FloorType.ROAD_NS and abs(fx_frac - 0.5) < 0.08) or \
                                     (ftype == FloorType.ROAD_EW and abs(fy_frac - 0.5) < 0.08)
                    if is_center_line:
                        char = '=' if ftype == FloorType.ROAD_EW else '|'
                        fg = (int(255 * floor_shade), int(220 * floor_shade), int(0 * floor_shade))
                        bg = (int(40 * floor_shade), int(40 * floor_shade), int(45 * floor_shade))
                    else:
                        is_puddle = wetness > 0.1 and (((int(floor_x * 7) ^ int(floor_y * 11)) % 100) < int(wetness * 60))
                        if is_puddle:
                            char = '≈' if (int(floor_x * 6) + int(floor_y * 6)) % 2 == 0 else '~'
                            fg = (min(255, int(180 * floor_shade + horizon_col[0] * 0.4)),
                                  min(255, int(200 * floor_shade + horizon_col[1] * 0.4)),
                                  min(255, int(240 * floor_shade + horizon_col[2] * 0.5)))
                            bg = (min(255, int(50 * floor_shade + horizon_col[0] * 0.2)),
                                  min(255, int(55 * floor_shade + horizon_col[1] * 0.2)),
                                  min(255, int(70 * floor_shade + horizon_col[2] * 0.25)))
                        else:
                            char = '.' if (int(floor_x * 4) + int(floor_y * 4)) % 3 == 0 else ' '
                            fg = (int(80 * floor_shade), int(80 * floor_shade), int(90 * floor_shade))
                            bg = (int(25 * floor_shade), int(26 * floor_shade), int(30 * floor_shade))
                elif ftype == FloorType.PARK_GRASS:
                    char = '"' if (int(floor_x * 3) + int(floor_y * 3)) % 2 == 0 else ','
                    fg = (int(40 * floor_shade), int(160 * floor_shade), int(60 * floor_shade))
                    bg = (int(15 * floor_shade), int(45 * floor_shade), int(20 * floor_shade))
                elif ftype == FloorType.PLAZA_TILES:
                    is_wet_plaza = wetness > 0.2 and (((int(floor_x * 5) + int(floor_y * 5)) % 4) == 0)
                    char = '·' if is_wet_plaza else ('+' if (int(floor_x * 2) + int(floor_y * 2)) % 2 == 0 else ' ')
                    fg = (int(160 * floor_shade), int(150 * floor_shade), int(140 * floor_shade))
                    bg = (int(50 * floor_shade), int(48 * floor_shade), int(45 * floor_shade))
                elif ftype == FloorType.WATER:
                    char = '~' if (int(floor_x * 4) + int(floor_y * 4)) % 2 == 0 else '≈'
                    fg = (int(100 * floor_shade), int(210 * floor_shade), int(255 * floor_shade))
                    bg = (int(10 * floor_shade), int(30 * floor_shade), int(65 * floor_shade))
                elif ftype == FloorType.BRIDGE:
                    char = '=' if (int(floor_x * 3) + int(floor_y * 3)) % 2 == 0 else '-'
                    fg = (int(190 * floor_shade), int(160 * floor_shade), int(120 * floor_shade))
                    bg = (int(40 * floor_shade), int(35 * floor_shade), int(30 * floor_shade))
                elif ftype == FloorType.COBBLESTONE:
                    char = 'o' if (int(floor_x * 3) + int(floor_y * 3)) % 2 == 0 else '·'
                    fg = (int(170 * floor_shade), int(140 * floor_shade), int(120 * floor_shade))
                    bg = (int(45 * floor_shade), int(35 * floor_shade), int(30 * floor_shade))
                elif ftype == FloorType.WOOD_DECK:
                    char = '|' if (int(floor_x * 4)) % 2 == 0 else ' '
                    fg = (int(160 * floor_shade), int(115 * floor_shade), int(75 * floor_shade))
                    bg = (int(40 * floor_shade), int(28 * floor_shade), int(18 * floor_shade))
                else:
                    is_puddle = wetness > 0.2 and (((int(floor_x * 8) + int(floor_y * 8)) % 7) == 0)
                    if is_puddle:
                        char = '~'
                        fg = (min(255, int(160 * floor_shade)), min(255, int(180 * floor_shade)), min(255, int(210 * floor_shade)))
                        bg = (min(255, int(60 * floor_shade)), min(255, int(65 * floor_shade)), min(255, int(75 * floor_shade)))
                    else:
                        char = '.' if (int(floor_x * 4) + int(floor_y * 4)) % 2 == 0 else '_'
                        fg = (int(140 * floor_shade), int(140 * floor_shade), int(150 * floor_shade))
                        bg = (int(45 * floor_shade), int(45 * floor_shade), int(50 * floor_shade))

                if floor_fog > 0.0 and weather:
                    fg = _blend_color(fg, weather.fog_color, floor_fog)
                    bg = _blend_color(bg, weather.fog_color, floor_fog)

                buffer.set_pixel(x, y, char, fg, bg)
                floor_x += step_x
                floor_y += step_y

    def _render_sprites(
        self,
        camera: Camera,
        sprites: List[Sprite],
        horizon_y: int,
        ambient: float,
        weather: Optional[WeatherSystem],
        buffer: ScreenBuffer
    ):
        active_sprites: List[Tuple[float, Sprite]] = []
        for spr in sprites:
            dx = spr.x - camera.pos.x
            dy = spr.y - camera.pos.y
            dist_sq = dx * dx + dy * dy
            if dist_sq < 900.0:
                active_sprites.append((dist_sq, spr))

        active_sprites.sort(key=lambda item: item[0], reverse=True)
        inv_det = 1.0 / (camera.plane.x * camera.dir.y - camera.dir.x * camera.plane.y)

        for dist_sq, spr in active_sprites:
            dist = math.sqrt(dist_sq)
            spr_x = spr.x - camera.pos.x
            spr_y = spr.y - camera.pos.y

            transform_x = inv_det * (camera.dir.y * spr_x - camera.dir.x * spr_y)
            transform_y = inv_det * (-camera.plane.y * spr_x + camera.plane.x * spr_y)

            if transform_y <= 0.2:
                continue

            spr_screen_x = int((self.width / 2.0) * (1.0 + transform_x / transform_y))

            spr_h = abs(int(self.height / transform_y * spr.scale_y))
            spr_w = abs(int(self.height / transform_y * spr.scale_x))

            vert_offset = int((spr.vertical_offset * self.height) / transform_y)
            draw_y0 = int(horizon_y - spr_h / 2.0 - vert_offset)
            draw_y1 = int(horizon_y + spr_h / 2.0 - vert_offset)

            draw_x0 = int(spr_screen_x - spr_w / 2.0)
            draw_x1 = int(spr_screen_x + spr_w / 2.0)

            distance_shade = 1.0 / (1.0 + 0.09 * dist + 0.005 * dist_sq)
            shade = 1.0 if spr.is_luminous else clamp(distance_shade * ambient, 0.15, 1.0)

            fog_blend = 0.0
            if weather and weather.fog_density > 0 and not spr.is_luminous:
                fog_blend = clamp(1.0 - math.exp(-dist * weather.fog_density), 0.0, 0.9)

            x_start = max(0, draw_x0)
            x_end = min(self.width - 1, draw_x1)

            for stripe in range(x_start, x_end + 1):
                if transform_y < self.z_buffer[stripe]:
                    tex_x = int((stripe - draw_x0) * spr.width / max(1, spr_w))
                    tex_x = max(0, min(tex_x, spr.width - 1))

                    y_start = max(0, draw_y0)
                    y_end = min(self.height - 1, draw_y1)

                    for y in range(y_start, y_end + 1):
                        tex_y = int((y - draw_y0) * spr.height / max(1, spr_h))
                        tex_y = max(0, min(tex_y, spr.height - 1))

                        char = spr.chars[tex_y][tex_x]
                        if char != ' ':
                            fg_raw = spr.fg_colors[tex_y][tex_x]
                            fg = (min(255, int(fg_raw[0] * shade)), min(255, int(fg_raw[1] * shade)), min(255, int(fg_raw[2] * shade)))
                            
                            if fog_blend > 0.0 and weather:
                                fg = _blend_color(fg, weather.fog_color, fog_blend)

                            buffer.set_pixel(stripe, y, char, fg, None)
