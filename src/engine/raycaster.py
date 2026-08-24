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
from src.world.interiors import WALL_TYPE_INTERIOR
from src.world.day_night import DayNightCycle
from src.world.weather import WeatherSystem
from src.entities.sprite import Sprite, VolumetricSprite
from src.renderer.screen_buffer import ScreenBuffer


def _blend_color(c1: Tuple[int, int, int], c2: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    f = clamp(factor, 0.0, 1.0)
    return (
        int(c1[0] + (c2[0] - c1[0]) * f),
        int(c1[1] + (c2[1] - c1[1]) * f),
        int(c1[2] + (c2[2] - c1[2]) * f)
    )


class Raycaster:
    # Two-tier draw distance: detailed DDA in the near field, coarse parametric
    # sampling for the far skyline; plus depth-layer stacking so rays see past
    # shorter buildings to taller towers behind them
    MAX_LAYERS = 3        # max wall layers recorded per column
    NEAR_STEPS = 18       # detailed cell-by-cell DDA budget (near tier)
    FAR_MAX_DIST = 60.0   # world units scanned by the far tier (skyline range)
    FAR_STRIDE = 1.5      # far-tier sampling step along the ray
    WINDOW_OPENING = 0.30 # half-height of the glass opening as slice fraction

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

        # Vertical projection: rows-per-meter at unit distance, corrected for
        # terminal cell aspect (chars ~2x taller than wide). All wall/sprite/
        # floor geometry derives from this single factor.
        from src.world.scale import CELL_ASPECT
        self._v_proj = (self.width / 2.0) / camera.plane.length() / CELL_ASPECT

        # Camera horizon: pitched center line. Eye height is NOT folded in
        # here — it scales the wall/floor projection instead (see slices)
        horizon_y = int(self.height / 2.0 + camera.pitch)

        # 1. Render Sky (Ceiling) & Floor Background Slices
        self._render_sky_and_floor(
            camera=camera,
            city_map=city_map,
            day_night=day_night,
            weather=weather,
            horizon_y=horizon_y,
            zenith_col=zenith_col,
            horizon_col=horizon_col,
            ambient=base_ambient,
            lightning_intensity=lightning_intensity,
            lightning_col=lightning_col,
            buffer=buffer
        )

        # 2. Raycast Walls & Record Z-Buffer (multi-layer, far-to-near paint)
        for x in range(self.width):
            layers = self._cast_ray_layers(x, camera, city_map, horizon_y)
            if layers and layers[0].hit:
                self.z_buffer[x] = layers[0].perp_wall_dist
                wall_layers = [h for h in layers if h.win_dist == 0.0]
                portal_layers = [h for h in layers if h.win_dist > 0.0 and h.hit]

                # Solid geometry first, far to near (classic painter)
                for hit in reversed(wall_layers):
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

                if portal_layers:
                    # Live-window portals: exterior world seen through the
                    # glass opening, painted far-to-near inside the span
                    win_dist = portal_layers[0].win_dist
                    w_half = (self.height / win_dist) * self.WINDOW_OPENING
                    w_top = int(horizon_y - w_half)
                    w_bot = int(horizon_y + w_half)
                    for hit in reversed(portal_layers):
                        self._draw_wall_slice(
                            screen_x=x,
                            hit=hit,
                            camera=camera,
                            horizon_y=horizon_y,
                            ambient=ambient,
                            weather=weather,
                            flashlight_on=flashlight_on,
                            buffer=buffer,
                            clip=(w_top, w_bot)
                        )
                elif layers[-1].win_dist > 0.0 and not layers[-1].hit:
                    # Window crossed with nothing solid beyond: open sky through glass
                    win_dist = layers[-1].win_dist
                    w_half = (self.height / win_dist) * self.WINDOW_OPENING
                    self._draw_sky_span(
                        screen_x=x,
                        y0=int(horizon_y - w_half),
                        y1=int(horizon_y + w_half),
                        zenith_col=zenith_col,
                        horizon_col=horizon_col,
                        lightning_intensity=lightning_intensity,
                        lightning_col=lightning_col,
                        day_night=day_night,
                        weather=weather,
                        buffer=buffer
                    )
            else:
                self.z_buffer[x] = 100.0
                if layers and not layers[0].hit and layers[0].win_dist > 0.0:
                    # Window with nothing solid beyond: open sky through glass
                    win_dist = layers[0].win_dist
                    w_half = (self.height / win_dist) * self.WINDOW_OPENING
                    self._draw_sky_span(
                        screen_x=x,
                        y0=int(horizon_y - w_half),
                        y1=int(horizon_y + w_half),
                        zenith_col=zenith_col,
                        horizon_col=horizon_col,
                        lightning_intensity=lightning_intensity,
                        lightning_col=lightning_col,
                        day_night=day_night,
                        weather=weather,
                        buffer=buffer
                    )

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
        """Nearest wall hit for a column (compatibility accessor over _cast_ray_layers)."""
        layers = self._cast_ray_layers(screen_x, camera, city_map)
        if layers and layers[0].hit:
            return layers[0]
        camera_x = 2.0 * screen_x / float(self.width) - 1.0
        return RayHit(False, 0, 0, 0, 100.0, 0.0, 0, 1.0,
                      camera.dir.x + camera.plane.x * camera_x,
                      camera.dir.y + camera.plane.y * camera_x)

    def _cast_ray_layers(self, screen_x: int, camera: Camera, city_map: CityMap,
                         horizon_y: Optional[int] = None) -> List[RayHit]:
        """
        Casts one column ray and records up to MAX_LAYERS wall hits near-to-far.

        Tier 1 (detailed): cell-by-cell DDA through the near field; a farther
        structure is recorded only when it stands TALLER than every nearer
        layer on this ray (its roofline rises above theirs), which is exactly
        the overlap case that adds visible pixels.

        Tier 2 (far skyline): past the detailed budget, the ray advances in
        coarse world-space strides out to FAR_MAX_DIST; the first solid sample
        becomes a simplified silhouette layer. The stride grows with distance
        and the whole tier is skipped when nearer layers already cover the
        full screen column.

        Indoors (InteriorView): window cells are transparent — the first one
        crossed is remembered as a portal plane and every solid hit beyond it
        is stamped win_dist so it renders clipped inside the glass opening.
        """
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

        layers: List[RayHit] = []
        max_height = -1.0
        side = 0
        indoors = getattr(city_map, 'in_interior', False)
        window_dist = 0.0   # perp distance of the portal plane, once crossed
        frame_count = 0     # synthetic window-frame layers (exempt from MAX_LAYERS)

        # A layer whose projected top reaches above the screen top hides every
        # farther candidate; used to bail out of all remaining scanning
        covered_top = False

        def make_hit(mx, my, sd, perp, wx, wtype):
            return RayHit(True, mx, my, sd, max(0.08, perp), wx,
                          wtype, city_map.get_wall_height(wtype),
                          ray_dir_x, ray_dir_y,
                          is_far=False, win_dist=window_dist)

        # ---- Tier 1: detailed near-field DDA with depth-layer stacking ----
        for _ in range(self.NEAR_STEPS):
            if side_dist_x < side_dist_y:
                side_dist_x += delta_dist_x
                map_x += step_x
                side = 0
                marched = side_dist_x - delta_dist_x
            else:
                side_dist_y += delta_dist_y
                map_y += step_y
                side = 1
                marched = side_dist_y - delta_dist_y

            if indoors and window_dist == 0.0 and getattr(city_map, 'is_window_cell')(map_x, map_y):
                # Live portal plane: the glass cell's own interior face is
                # stamped as a full-column frame layer (win_dist 0.0 so it
                # paints before the clipped through-glass content), then the
                # ray is allowed to fly through
                frame_type = city_map.get_wall_type(map_x, map_y)
                if frame_type == 0:
                    frame_type = WALL_TYPE_INTERIOR
                if side == 0:
                    frame_x = camera.pos.y + marched * ray_dir_y
                else:
                    frame_x = camera.pos.x + marched * ray_dir_x
                frame_x -= math.floor(frame_x)
                layers.append(RayHit(True, map_x, map_y, side, max(0.08, marched),
                                     frame_x, frame_type,
                                     city_map.get_wall_height(frame_type),
                                     ray_dir_x, ray_dir_y,
                                     is_far=False, win_dist=0.0))
                frame_count += 1
                window_dist = marched
                continue

            if not city_map.is_solid(map_x, map_y):
                continue

            wall_type = city_map.get_wall_type(map_x, map_y)
            wall_h = city_map.get_wall_height(wall_type)

            taller_rule = (wall_h > max_height + 1e-6
                           or (indoors and window_dist > 0.0 and not layers)
                           or not layers)
            if taller_rule:
                max_height = max(max_height, wall_h)
                # Distance to the boundary crossed INTO the solid cell (= wall face)
                perp = marched
                if side == 0:
                    wall_x = camera.pos.y + perp * ray_dir_y
                else:
                    wall_x = camera.pos.x + perp * ray_dir_x
                wall_x -= math.floor(wall_x)
                layers.append(make_hit(map_x, map_y, side, perp, wall_x, wall_type))
                if horizon_y is not None and len(layers) == 1 and window_dist == 0.0:
                    unit_px = self._v_proj / perp
                    covered_top = (horizon_y - unit_px * (wall_h - camera.eye_height)) <= 0.0
                if covered_top or len(layers) - frame_count >= self.MAX_LAYERS:
                    return layers

        if window_dist > 0.0:
            # Indoors past the glass: keep marching a little for the exterior
            # view even if tier 1 ran out of steps
            extra = 0
            while extra < 40:
                if side_dist_x < side_dist_y:
                    side_dist_x += delta_dist_x
                    map_x += step_x
                    side = 0
                    marched = side_dist_x - delta_dist_x
                else:
                    side_dist_y += delta_dist_y
                    map_y += step_y
                    side = 1
                    marched = side_dist_y - delta_dist_y
                extra += 1
                if not city_map.is_solid(map_x, map_y):
                    if extra >= 40:
                        break
                    continue
                wall_type = city_map.get_wall_type(map_x, map_y)
                if side == 0:
                    wall_x = camera.pos.y + marched * ray_dir_y
                else:
                    wall_x = camera.pos.x + marched * ray_dir_x
                wall_x -= math.floor(wall_x)
                layers.append(RayHit(True, map_x, map_y, side, max(0.08, marched),
                                     wall_x, wall_type, city_map.get_wall_height(wall_type),
                                     ray_dir_x, ray_dir_y,
                                     is_far=False, win_dist=window_dist))
                break
            if not layers or all(not h.hit for h in layers):
                layers.append(RayHit(False, map_x, map_y, 0, 100.0, 0.0, 0, 1.0,
                                     ray_dir_x, ray_dir_y, win_dist=window_dist))
            return layers

        # ---- Tier 2: coarse far-skyline sampling (stride grows with range) ----
        if covered_top:
            return layers

        forward_now = min(side_dist_x - delta_dist_x, side_dist_y - delta_dist_y)
        dir_dot = ray_dir_x * camera.dir.x + ray_dir_y * camera.dir.y
        if dir_dot <= 1e-6:
            return layers

        t = max(forward_now, 0.0) + self.FAR_STRIDE
        stride = self.FAR_STRIDE
        while t <= self.FAR_MAX_DIST and len(layers) < self.MAX_LAYERS:
            px = camera.pos.x + ray_dir_x * t
            py = camera.pos.y + ray_dir_y * t
            if city_map.is_solid(px, py):
                fx = int(px)
                fy = int(py)
                wall_type = city_map.get_wall_type(fx, fy)
                wall_h = city_map.get_wall_height(wall_type)
                # Shorter/equal far masses add nothing; keep scanning for a
                # taller silhouette rising behind them (distant skyline layering)
                if wall_h > max_height + 1e-6 or not layers:
                    max_height = max(max_height, wall_h)
                    # Face hint from fractional position inside the sampled cell
                    frac_x = px - math.floor(px)
                    frac_y = py - math.floor(py)
                    side = 0 if min(frac_x, 1.0 - frac_x) < min(frac_y, 1.0 - frac_y) else 1
                    wall_x = frac_y if side == 0 else frac_x
                    layers.append(RayHit(True, fx, fy, side,
                                         max(0.08, t * dir_dot), wall_x,
                                         wall_type, wall_h, ray_dir_x, ray_dir_y,
                                         is_far=True))
            t += stride
            stride *= 1.12  # distant silhouette needs less sampling precision

        return layers

    def _draw_wall_slice(
        self,
        screen_x: int,
        hit: RayHit,
        camera: Camera,
        horizon_y: int,
        ambient: float,
        weather: Optional[WeatherSystem],
        flashlight_on: bool,
        buffer: ScreenBuffer,
        clip: Optional[Tuple[int, int]] = None
    ):
        texture = get_texture(hit.wall_type)

        # Perspective-correct vertical extent with eye-height anchoring:
        # the wall BASE always lands exactly on the floor plane at this
        # distance (z=0), and the TOP rises wall_height units above the eye.
        # Centering on the horizon was only correct for 1-high walls — taller
        # buildings projected their lower floors underground ("basements").
        eye = camera.eye_height
        unit = self._v_proj / hit.perp_wall_dist
        draw_start = int(horizon_y - unit * (hit.wall_height - eye))
        draw_end = int(horizon_y + unit * eye)

        # Distance attenuation and side shading, plus headlight beam boost
        side_mult = 0.82 if hit.side == 1 else 1.0
        distance_shade = (1.0 / (1.0 + 0.08 * hit.perp_wall_dist + 0.005 * hit.perp_wall_dist * hit.perp_wall_dist))
        
        headlight_boost = 0.0
        if getattr(camera, 'headlights_on', False):
            cone_factor = max(0.0, 1.0 - abs(screen_x - self.width / 2.0) / (self.width * 0.45))
            if hit.perp_wall_dist < 18.0:
                headlight_boost = cone_factor * (1.0 - hit.perp_wall_dist / 18.0) * 0.75

        shade = clamp((distance_shade * ambient + headlight_boost) * side_mult, 0.1, 1.0)

        if hit.is_far:
            self._draw_far_body(screen_x, hit, draw_start, draw_end,
                                texture, shade, weather, buffer)
            return

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

        # Live-window portal: keep only the rows inside the glass opening
        if clip is not None:
            y0 = max(y0, clip[0])
            y1 = min(y1, clip[1])

        # Story-quantized facade sampling: tall buildings repeat their floor
        # pattern every STORY_HEIGHT_M so window bands stay human-scale and
        # height becomes legible (a 60 m tower shows ~20 stacked floors)
        from src.world.scale import STORY_HEIGHT_M
        repeating = hit.wall_height >= 2.0 * STORY_HEIGHT_M

        for y in range(y0, y1 + 1):
            if repeating:
                z_m = (draw_end - y) / max(1e-6, unit)
                tex_v = (z_m % STORY_HEIGHT_M) / STORY_HEIGHT_M
            else:
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

    def _window_span(self, win_dist: float, camera: Camera, horizon_y: int) -> Tuple[int, int]:
        """Glass opening rows on a window-cell face: sill 0.9 m, header 2.1 m."""
        unit_w = self._v_proj / win_dist
        center_z = 1.5                                   # mid between sill/header
        center_row = horizon_y - unit_w * (center_z - camera.eye_height)
        half_px = unit_w * 0.6                           # (2.1 - 0.9) / 2
        return int(center_row - half_px), int(center_row + half_px)

    def _draw_far_body(
        self,
        screen_x: int,
        hit: RayHit,
        draw_start: int,
        draw_end: int,
        texture,
        shade: float,
        weather: Optional[WeatherSystem],
        buffer: ScreenBuffer
    ):
        """
        Simplified far-skyline slice: blocky two-glyph silhouette tinted from
        the building's base palette, with a minimum fog haze for depth cueing.
        """
        _, _, bg_raw = texture.sample(hit.wall_x, 0.5)
        fg_raw = texture.fg_colors[len(texture.fg_colors) // 2][0]

        fog_factor = 0.0
        if weather and weather.fog_density > 0:
            fog_factor = clamp(1.0 - math.exp(-hit.perp_wall_dist * weather.fog_density), 0.0, 0.95)
        # Distant skyline always carries a baseline atmospheric haze
        fog_factor = max(fog_factor, 0.30)

        fg = (int(fg_raw[0] * shade), int(fg_raw[1] * shade), int(fg_raw[2] * shade))
        bg = (int(bg_raw[0] * shade), int(bg_raw[1] * shade), int(bg_raw[2] * shade))
        if weather:
            fg = _blend_color(fg, weather.fog_color, fog_factor)
            bg = _blend_color(bg, weather.fog_color, fog_factor)

        y0 = max(0, draw_start)
        y1 = min(self.height - 1, draw_end)
        col_hash = int(hit.wall_x * 7.99)
        for y in range(y0, y1 + 1):
            char = '#' if ((col_hash + y) & 3) else '%'
            buffer.set_pixel(screen_x, y, char, fg, bg)

    def _draw_sky_span(
        self,
        screen_x: int,
        y0: int,
        y1: int,
        zenith_col: Tuple[int, int, int],
        horizon_col: Tuple[int, int, int],
        lightning_intensity: float,
        lightning_col: Tuple[int, int, int],
        day_night,
        weather: Optional[WeatherSystem],
        buffer: ScreenBuffer
    ):
        """Sky gradient drawn into a clipped span (seen through window glass)."""
        for y in range(max(0, y0), min(self.height - 1, y1) + 1):
            t = y / float(max(1, self.height // 2))
            r = int(zenith_col[0] + (horizon_col[0] - zenith_col[0]) * t)
            g = int(zenith_col[1] + (horizon_col[1] - zenith_col[1]) * t)
            b = int(zenith_col[2] + (horizon_col[2] - zenith_col[2]) * t)
            sky_col = (r, g, b)
            if lightning_intensity > 0.0:
                sky_col = _blend_color(sky_col, lightning_col, lightning_intensity * 0.9)
            if weather and weather.fog_density > 0.04:
                sky_col = _blend_color(sky_col, weather.fog_color, min(0.85, weather.fog_density * 6.0))
            buffer.set_pixel(screen_x, y, ' ', (100, 100, 120), sky_col)

    def _render_sky_and_floor(
        self,
        camera: Camera,
        city_map: CityMap,
        day_night: DayNightCycle,
        weather: Optional[WeatherSystem],
        horizon_y: int,
        zenith_col: Tuple[int, int, int],
        horizon_col: Tuple[int, int, int],
        ambient: float,
        lightning_intensity: float,
        lightning_col: Tuple[int, int, int],
        buffer: ScreenBuffer
    ):
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

        # Floor rows (below horizon); ground plane recedes per eye height
        eye = camera.eye_height
        for y in range(max(0, horizon_y), self.height):
            dy = float(y - horizon_y)
            if dy <= 0.0:
                continue

            row_dist = (eye * self._v_proj) / dy
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

            if isinstance(spr, VolumetricSprite):
                self._render_volumetric(
                    spr=spr,
                    transform_y=transform_y,
                    spr_screen_x=spr_screen_x,
                    camera=camera,
                    horizon_y=horizon_y,
                    ambient=ambient,
                    weather=weather,
                    buffer=buffer,
                    dist=dist,
                    dist_sq=dist_sq
                )
                continue

            px_per_unit = self._v_proj / transform_y
            spr_h = abs(int(px_per_unit * spr.scale_y))
            spr_w = abs(int(px_per_unit * spr.scale_x))

            # Ground anchoring: sprite BASE sits on the floor plane at this
            # distance (z=0), not centered on the horizon — props no longer hover
            vert_offset = int((spr.vertical_offset * self.height) / transform_y)
            base_row = int(horizon_y + px_per_unit * camera.eye_height)
            draw_y1 = base_row - vert_offset
            draw_y0 = draw_y1 - spr_h + 1

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

    def _render_volumetric(
        self,
        spr: VolumetricSprite,
        transform_y: float,
        spr_screen_x: int,
        camera: Camera,
        horizon_y: int,
        ambient: float,
        weather: Optional[WeatherSystem],
        buffer: ScreenBuffer,
        dist: float,
        dist_sq: float
    ):
        """
        Pseudo-volumetric box projection: front and side faces share the
        projected extent with an angle-dependent split, so the visible corner
        edge slides across the prop as the camera orbits it.
        """
        px_per_unit = self._v_proj / transform_y

        cam_dx = camera.pos.x - spr.x
        cam_dy = camera.pos.y - spr.y
        bearing = math.atan2(cam_dy, cam_dx) - spr.facing_angle
        abs_cos = abs(math.cos(bearing))
        sin_signed = math.sin(bearing)
        front_left = sin_signed >= 0.0
        see_front = math.cos(bearing) >= 0.0 or spr.back_chars is None

        # Rear hemisphere shows the back face art when one exists
        if see_front:
            face_chars, face_fg = spr.front_chars, spr.front_fg
        else:
            face_chars, face_fg = spr.back_chars, spr.back_fg
        face_w = len(face_chars[0])

        side_w = len(spr.side_chars[0])

        # True orthographic box projection: each face's screen width is its
        # real-world size times the |cos|/|sin| of the bearing — NO
        # normalization, so a 4.5 m car stays elongated at every angle
        front_span = px_per_unit * spr.front_units * abs_cos
        side_span = px_per_unit * spr.side_units * abs(sin_signed)
        total_span = front_span + side_span

        spr_h = max(1, abs(int(px_per_unit * spr.height_units)))

        # Ground anchoring (same model as flat sprites)
        vert_offset = int((spr.vertical_offset * self.height) / transform_y)
        base_row = int(horizon_y + px_per_unit * camera.eye_height)
        draw_y0 = base_row - vert_offset - spr_h + 1

        x0 = spr_screen_x - int(total_span / 2.0)
        x1 = x0 + int(total_span)

        distance_shade = 1.0 / (1.0 + 0.09 * dist + 0.005 * dist_sq)
        shade = 1.0 if spr.is_luminous else clamp(distance_shade * ambient, 0.15, 1.0)

        fog_blend = 0.0
        if weather and weather.fog_density > 0 and not spr.is_luminous:
            fog_blend = clamp(1.0 - math.exp(-dist * weather.fog_density), 0.0, 0.9)

        y_start = max(0, draw_y0)
        y_end = min(self.height - 1, draw_y0 + spr_h - 1)

        for stripe in range(max(0, x0), min(self.width - 1, x1) + 1):
            if transform_y >= self.z_buffer[stripe]:
                continue

            in_face = (stripe < x0 + front_span) if front_left else (stripe >= x0 + side_span)
            if in_face:
                art_chars, art_fg, art_w = face_chars, face_fg, face_w
                face_offset = (stripe - x0) if front_left else (stripe - (x0 + side_span))
                plane_shade = shade
            else:
                art_chars, art_fg, art_w = spr.side_chars, spr.side_fg, side_w
                face_offset = (stripe - (x0 + front_span)) if front_left else (stripe - x0)
                plane_shade = shade * VolumetricSprite.SIDE_SHADE

            span = max(1.0, front_span if in_face else side_span)
            tex_x = max(0, min(int(face_offset / span * art_w), art_w - 1))

            for y in range(y_start, y_end + 1):
                tex_y = int((y - draw_y0) * len(art_chars) / max(1, spr_h))
                tex_y = max(0, min(tex_y, len(art_chars) - 1))

                char = art_chars[tex_y][tex_x] if tex_x < len(art_chars[tex_y]) else ' '
                if char == ' ':
                    continue
                fg_raw = art_fg[tex_y][tex_x]
                fg = (
                    min(255, int(fg_raw[0] * plane_shade)),
                    min(255, int(fg_raw[1] * plane_shade)),
                    min(255, int(fg_raw[2] * plane_shade))
                )
                if fog_blend > 0.0 and weather:
                    fg = _blend_color(fg, weather.fog_color, fog_blend)
                buffer.set_pixel(stripe, y, char, fg, None)
