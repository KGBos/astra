"""
Core 3D Raycasting Engine, Z-Buffer, Floor/Sky Renderer, Volumetric Fog, Wet Surface Reflections, Multi-district floors & 3D Sprite Projector.
Author: Valerie Sterling ⚡ & Darius Thorne 📐
"""

import math
from typing import List, Tuple, Optional
from src.engine.camera import Camera
from src.engine.math3d import clamp, RayHit
from src.engine.tone import (get_shade_lut, SHADE_CACHE, BAYER4, BAYER_MID,
                             hash_noise, fbm_noise)
from src.engine.lighting import collect_lights, make_player_headlight, strongest_light_at
from src.world.city_map import CityMap, FloorType
from src.world.textures import get_texture
from src.world.interiors import WALL_TYPE_INTERIOR
from src.world.day_night import DayNightCycle
from src.world.weather import WeatherSystem
from src.entities.sprite import Sprite, VolumetricSprite
from src.renderer.screen_buffer import ScreenBuffer, ASCII_TRANSLATION


def _blend_color(c1: Tuple[int, int, int], c2: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    f = clamp(factor, 0.0, 1.0)
    return (
        int(c1[0] + (c2[0] - c1[0]) * f),
        int(c1[1] + (c2[1] - c1[1]) * f),
        int(c1[2] + (c2[2] - c1[2]) * f)
    )


CELL_ASPECT = 0.5


def pixels_per_meter_at_1m(screen_w: int, screen_h: int, plane_len: float) -> float:
    """Vertical focal length in character rows per world metre at 1 m distance.

    Derives the vertical FOV from the horizontal raycaster plane so the
    projection stays aspect-correct: tan(fov_v / 2) equals plane_len scaled
    by the pixel height/width ratio, and the ~1:2 terminal cell shape folds
    into CELL_ASPECT, giving PPM_1M = (H / 2) / tan(fov_v / 2).
    """
    tan_half_fov_v = plane_len * screen_h / (CELL_ASPECT * float(screen_w))
    return (screen_h / 2.0) / max(1e-6, tan_half_fov_v)


class Raycaster:
    # Two-tier draw distance: detailed DDA in the near field, coarse parametric
    # sampling for the far skyline; plus depth-layer stacking so rays see past
    # shorter buildings to taller towers behind them
    MAX_LAYERS = 3        # max wall layers recorded per column
    NEAR_STEPS = 18       # detailed cell-by-cell DDA budget (near tier)
    FAR_MAX_DIST = 60.0   # world units scanned by the far tier (skyline range)
    FAR_STRIDE = 1.5      # far-tier sampling step along the ray
    WINDOW_HALF_HEIGHT_M = 1.0  # glass opening half-height in metres (2 m band)

    # Rendering-2.0 knobs (research: gamma LUTs, Bayer dither, point lights,
    # wet reflections, post-FX). All pure-stdlib and ASCII-safe.
    DITHER_SHADE_AMP = 0.055   # zero-mean Bayer perturbation of shade factors
    DITHER_FOG_AMP = 0.075     # Bayer perturbation of fog blend (kills banding)
    FLOOR_LIGHT_K = 0.85       # additive light scale on ground bg channels
    WALL_LIGHT_K = 0.60        # additive light scale on wall faces
    VIGNETTE_STRENGTH = 0.34
    BLOOM_THRESHOLD = 214     # only genuinely emissive texels seed the glow
    CLOUD_SCALE = 5.5          # angular frequency of the cloud field

    def __init__(self, screen_w: int = 80, screen_h: int = 32):
        self.width = screen_w
        self.height = screen_h
        self.z_buffer: List[float] = [float('inf') for _ in range(screen_w)]
        self._vignette: Optional[List[float]] = None
        self._vignette_size: Tuple[int, int] = (0, 0)

    def resize(self, width: int, height: int):
        self.width = width
        self.height = height
        self.z_buffer = [float('inf') for _ in range(width)]
        self._vignette = None

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

        ppm = pixels_per_meter_at_1m(self.width, self.height, camera.plane.length())

        # Rendering-2.0: collect emissive world objects into point lights
        lights = collect_lights(sprites, camera.pos.x, camera.pos.y)
        headlight = make_player_headlight(camera)
        if headlight is not None:
            lights.append(headlight)

        # Camera horizon with pitch and head-bob offset; true eye height now
        # enters through the wall/sprite/floor projections instead of a horizon shift
        horizon_y = int(self.height / 2.0 + camera.pitch + camera.bob_amount * self.height)

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
            ppm=ppm,
            buffer=buffer,
            lights=lights
        )

        # 2. Raycast Walls & Record Z-Buffer (multi-layer, far-to-near paint)
        for x in range(self.width):
            layers = self._cast_ray_layers(x, camera, city_map, horizon_y, ppm)
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
                        buffer=buffer,
                        ppm=ppm,
                        lights=lights
                    )

                if portal_layers:
                    # Live-window portals: exterior world seen through the
                    # glass opening, painted far-to-near inside the span
                    win_dist = portal_layers[0].win_dist
                    w_half = (ppm * self.WINDOW_HALF_HEIGHT_M) / win_dist
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
                            clip=(w_top, w_bot),
                            lights=lights
                        )
                elif layers[-1].win_dist > 0.0 and not layers[-1].hit:
                    # Window crossed with nothing solid beyond: open sky through glass
                    win_dist = layers[-1].win_dist
                    w_half = (ppm * self.WINDOW_HALF_HEIGHT_M) / win_dist
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
                    w_half = (ppm * self.WINDOW_HALF_HEIGHT_M) / win_dist
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
            buffer=buffer,
            ppm=ppm,
            lights=lights
        )

        # 4. Wet-road light reflections (screen-space vertical smears)
        if weather is not None and weather.wetness > 0.12 and lights:
            self._render_wet_reflections(
                lights=lights,
                camera=camera,
                horizon_y=horizon_y,
                ppm=ppm,
                weather=weather,
                buffer=buffer,
                phase=day_night.time_of_day * 8.0
            )

        # 5. Post-FX: vignette, bloom-lite, film grain (color mode only)
        if buffer.use_color:
            self._postfx(buffer, day_night.time_of_day)

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
                         horizon_y: Optional[int] = None,
                         ppm: Optional[float] = None) -> List[RayHit]:
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

        if ppm is None:
            ppm = pixels_per_meter_at_1m(self.width, self.height, camera.plane.length())

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

        # Raw-grid solid probes: the real CityMap exposes its wall lists, so
        # the DDA hot loop skips per-cell method dispatch; InteriorView and
        # other duck-typed maps keep the is_solid fallback.
        walls_grid = getattr(city_map, 'walls', None)
        map_w = getattr(city_map, 'width', 0)
        map_h = getattr(city_map, 'height', 0)

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

            if walls_grid is not None:
                if 0 <= map_x < map_w and 0 <= map_y < map_h:
                    solid = walls_grid[map_y][map_x] > 0
                else:
                    solid = True
            else:
                solid = city_map.is_solid(map_x, map_y)
            if not solid:
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
                    roofline_row = horizon_y - (ppm / perp) * (wall_h - camera.eye_m)
                    covered_top = roofline_row <= 0.0
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
                if walls_grid is not None:
                    if 0 <= map_x < map_w and 0 <= map_y < map_h:
                        solid = walls_grid[map_y][map_x] > 0
                    else:
                        solid = True
                else:
                    solid = city_map.is_solid(map_x, map_y)
                if not solid:
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
        while t <= self.FAR_MAX_DIST:
            px = camera.pos.x + ray_dir_x * t
            py = camera.pos.y + ray_dir_y * t
            fx = int(px)
            fy = int(py)
            if walls_grid is not None:
                solid = not (0 <= fx < map_w and 0 <= fy < map_h) or walls_grid[fy][fx] > 0
            else:
                solid = city_map.is_solid(px, py)
            if solid:
                wall_type = city_map.get_wall_type(fx, fy)
                wall_h = city_map.get_wall_height(wall_type)
                if wall_h > max_height + 1e-6 or not layers:
                    # Face hint from fractional position inside the sampled cell
                    frac_x = px - math.floor(px)
                    frac_y = py - math.floor(py)
                    side = 0 if min(frac_x, 1.0 - frac_x) < min(frac_y, 1.0 - frac_y) else 1
                    wall_x = frac_y if side == 0 else frac_x
                    layers.append(RayHit(True, fx, fy, side,
                                         max(0.08, t * dir_dot), wall_x,
                                         wall_type, wall_h, ray_dir_x, ray_dir_y,
                                         is_far=True))
                break
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
        clip: Optional[Tuple[int, int]] = None,
        ppm: Optional[float] = None,
        lights: Optional[List] = None
    ):
        texture = get_texture(hit.wall_type)
        if ppm is None:
            ppm = pixels_per_meter_at_1m(self.width, self.height, camera.plane.length())

        rows_per_m = ppm / hit.perp_wall_dist
        draw_end = int(horizon_y + rows_per_m * camera.eye_m)
        draw_start = int(horizon_y - rows_per_m * (hit.wall_height - camera.eye_m))

        # Distance attenuation and side shading, plus headlight beam boost
        side_mult = 0.82 if hit.side == 1 else 1.0
        distance_shade = (1.0 / (1.0 + 0.08 * hit.perp_wall_dist + 0.005 * hit.perp_wall_dist * hit.perp_wall_dist))

        headlight_boost = 0.0
        if getattr(camera, 'headlights_on', False):
            cone_factor = max(0.0, 1.0 - abs(screen_x - self.width / 2.0) / (self.width * 0.45))
            if hit.perp_wall_dist < 18.0:
                headlight_boost = cone_factor * (1.0 - hit.perp_wall_dist / 18.0) * 0.75

        shade = clamp((distance_shade * ambient + headlight_boost) * side_mult, 0.1, 1.8)

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
                shade = clamp(shade + beam_boost, 0.1, 2.2)

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

        span = float(max(1, draw_end - draw_start))
        set_pixel = buffer.set_pixel
        tex_h = texture.height
        tex_fg = texture.fg_colors
        tex_bg = texture.bg_colors
        tex_chars = texture.chars
        tx = int((hit.wall_x % 1.0) * texture.width)
        tx = max(0, min(tx, texture.width - 1))

        # Per-column point-light wash, sampled once at the wall face
        wash_r = wash_g = wash_b = 0.0
        if lights:
            wpx = camera.pos.x + hit.ray_dir_x * hit.perp_wall_dist
            wpy = camera.pos.y + hit.ray_dir_y * hit.perp_wall_dist
            for L in lights:
                dxw = wpx - L.x
                dyw = wpy - L.y
                d2w = dxw * dxw + dyw * dyw
                if d2w < L.radius2:
                    fw = 1.0 - d2w / L.radius2
                    fw *= fw * L.intensity
                    wash_r += L.r * fw
                    wash_g += L.g * fw
                    wash_b += L.b * fw
            k_wall = self.WALL_LIGHT_K
            wash_r *= k_wall
            wash_g *= k_wall
            wash_b *= k_wall
        has_wash = wash_r > 0.5 or wash_g > 0.5 or wash_b > 0.5

        # Zero-mean Bayer perturbation of shade/fog kills gradient banding
        bayer_col = BAYER4[screen_x & 3]
        d_amp = self.DITHER_SHADE_AMP
        f_amp = self.DITHER_FOG_AMP
        mid = BAYER_MID
        shade_lut = get_shade_lut

        if fog_factor > 0.0 and weather is not None:
            fog_r, fog_g, fog_b = weather.fog_color
            for y in range(y0, y1 + 1):
                ty = int((((y - draw_start) / span) % 1.0) * tex_h)
                ty = max(0, min(ty, tex_h - 1))
                fg_raw = tex_fg[ty][tx]
                bg_raw = tex_bg[ty][tx]

                b = bayer_col[y & 3]
                q = int((shade + (b - mid) * d_amp) * 64.0 + 0.5)
                lut = SHADE_CACHE.get(q)
                if lut is None:
                    lut = get_shade_lut(q / 64.0)
                fd = fog_factor + (b - mid) * f_amp
                if fd < 0.0:
                    fd = 0.0
                elif fd > 0.97:
                    fd = 0.97
                inv_fd = 1.0 - fd

                r = lut[fg_raw[0]]
                g = lut[fg_raw[1]]
                bch = lut[fg_raw[2]]
                r = int(r + (fog_r - r) * fd)
                g = int(g + (fog_g - g) * fd)
                bch = int(bch + (fog_b - bch) * fd)
                br = lut[bg_raw[0]]
                bg_g = lut[bg_raw[1]]
                bb = lut[bg_raw[2]]
                br = int(br + (fog_r - br) * fd)
                bg_g = int(bg_g + (fog_g - bg_g) * fd)
                bb = int(bb + (fog_b - bb) * fd)

                if has_wash:
                    nr = r + wash_r
                    ng = g + wash_g
                    nb = bch + wash_b
                    if nr > 255.0:
                        nr = 255.0
                    if ng > 255.0:
                        ng = 255.0
                    if nb > 255.0:
                        nb = 255.0
                    nbr = br + wash_r
                    nbg = bg_g + wash_g
                    nbb = bb + wash_b
                    if nbr > 255.0:
                        nbr = 255.0
                    if nbg > 255.0:
                        nbg = 255.0
                    if nbb > 255.0:
                        nbb = 255.0
                    set_pixel(screen_x, y, tex_chars[ty][tx],
                              (int(nr), int(ng), int(nb)),
                              (int(nbr), int(nbg), int(nbb)))
                else:
                    set_pixel(screen_x, y, tex_chars[ty][tx], (r, g, bch),
                              (br, bg_g, bb))
            return

        for y in range(y0, y1 + 1):
            ty = int((((y - draw_start) / span) % 1.0) * tex_h)
            ty = max(0, min(ty, tex_h - 1))
            fg_raw = tex_fg[ty][tx]
            bg_raw = tex_bg[ty][tx]

            q = int((shade + (bayer_col[y & 3] - mid) * d_amp) * 64.0 + 0.5)
            lut = SHADE_CACHE.get(q)
            if lut is None:
                lut = get_shade_lut(q / 64.0)
            r = lut[fg_raw[0]]
            g = lut[fg_raw[1]]
            bch = lut[fg_raw[2]]

            if has_wash:
                nr = r + wash_r
                ng = g + wash_g
                nb = bch + wash_b
                if nr > 255.0:
                    nr = 255.0
                if ng > 255.0:
                    ng = 255.0
                if nb > 255.0:
                    nb = 255.0
                nbr = lut[bg_raw[0]] + wash_r
                nbg = lut[bg_raw[1]] + wash_g
                nbb = lut[bg_raw[2]] + wash_b
                if nbr > 255.0:
                    nbr = 255.0
                if nbg > 255.0:
                    nbg = 255.0
                if nbb > 255.0:
                    nbb = 255.0
                set_pixel(screen_x, y, tex_chars[ty][tx],
                          (int(nr), int(ng), int(nb)),
                          (int(nbr), int(nbg), int(nbb)))
            else:
                set_pixel(screen_x, y, tex_chars[ty][tx],
                          (r, g, bch),
                          (lut[bg_raw[0]], lut[bg_raw[1]], lut[bg_raw[2]]))

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

        lut = get_shade_lut(shade)
        fg = (lut[fg_raw[0]], lut[fg_raw[1]], lut[fg_raw[2]])
        bg = (lut[bg_raw[0]], lut[bg_raw[1]], lut[bg_raw[2]])
        if weather:
            fg = _blend_color(fg, weather.fog_color, fog_factor)
            bg = _blend_color(bg, weather.fog_color, fog_factor)

        y0 = max(0, draw_start)
        y1 = min(self.height - 1, draw_end)
        col_hash = int(hit.wall_x * 7.99)
        set_pixel = buffer.set_pixel
        for y in range(y0, y1 + 1):
            char = '#' if ((col_hash + y) & 3) else '%'
            set_pixel(screen_x, y, char, fg, bg)

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
        ppm: float,
        buffer: ScreenBuffer,
        lights: Optional[List] = None
    ):
        """Sky gradient, procedural cloud layer, twinkling stars, moon phase
        disc, and a perspective floor-caster with additive point-light pools.

        Hot-path notes (profile-guided, M5 Cycle C): sky rows are row-constant,
        so stars are solved analytically -- (x*17 + y*31) % 67 == 0 has exactly
        one solution mod 67 (x == 10*y) -- instead of testing every pixel; the
        floor caster reads raw grid lists directly when the active map is the
        real CityMap (InteriorView keeps the duck-typed method fallback), and
        paints through direct pixel writes.

        Rendering-2.0 additions: shading goes through gamma-correct LUTs with
        zero-mean Bayer 4x4 perturbation (kills gradient banding), and ground
        light pools accumulate per-row-culled point lights incrementally.
        """
        is_night = day_night.time_of_day > 20.0 or day_night.time_of_day < 5.0
        wetness = weather.wetness if weather else 0.0
        tod = day_night.time_of_day

        # ---- Procedural cloud layer (value-noise FBM, wind-drifted) ----
        # Sampled every 2nd column with nearest fill; the field is smooth so
        # the 2-cell quantization is invisible while halving noise cost.
        width = self.width
        cloud_dens: List[float] = [0.0] * self.width
        if horizon_y > 0:
            inv_w = 1.0 / float(width)
            wind_u = tod * 0.55
            wind_v = tod * 0.05
            cscale = self.CLOUD_SCALE
            for x in range(0, width, 2):
                cxn = 2.0 * x * inv_w - 1.0
                ang = math.atan2(camera.dir.y + camera.plane.y * cxn,
                                 camera.dir.x + camera.plane.x * cxn)
                n = fbm_noise(ang * cscale + wind_u, wind_v, octaves=2, seed=7)
                d = (n * 0.5 + 0.5) - 0.46
                dv = d / 0.54 if d > 0.0 else 0.0
                cloud_dens[x] = dv
                if x + 1 < width:
                    cloud_dens[x + 1] = dv

            # Cloud tint follows the phase of day
            if is_night:
                cloud_col = (15, 17, 27)
            elif 17.0 <= tod < 20.0:
                cloud_col = ((horizon_col[0] + 170) // 2,
                             (horizon_col[1] + 150) // 2,
                             (horizon_col[2] + 165) // 2)
            elif 5.0 <= tod < 8.0:
                cloud_col = ((horizon_col[0] + 185) // 2,
                             (horizon_col[1] + 175) // 2,
                             (horizon_col[2] + 195) // 2)
            else:
                cloud_col = (208, 214, 226)

        # Star columns repeat every 67 pixels: x*17 == -31*y (mod 67) and
        # 17 * 4 == 68 == 1 (mod 67), so x == 10*y (mod 67).
        STAR_STEP = 67
        draw_stars = is_night and lightning_intensity < 0.1
        plain_fg = (100, 100, 120)

        # Sky rows (above horizon); gradient is row-constant, so it is
        # computed once per row rather than once per cell
        pixels = buffer.pixels
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

            # Clouds thicken toward the zenith (higher rows)
            alt_band = 0.35 + 0.65 * t

            row = pixels[y]
            star_x = (10 * y) % STAR_STEP if draw_stars else -1
            for x in range(width):
                p = row[x]

                cd_base = cloud_dens[x]
                if cd_base > 0.02:
                    cd = cd_base * alt_band
                    if cd > 0.04:
                        cb = cd * 0.9
                        if cb > 0.85:
                            cb = 0.85
                        sc = sky_col
                        p.bg = (int(sc[0] + (cloud_col[0] - sc[0]) * cb),
                                int(sc[1] + (cloud_col[1] - sc[1]) * cb),
                                int(sc[2] + (cloud_col[2] - sc[2]) * cb))
                    else:
                        p.bg = sky_col
                else:
                    cd = 0.0
                    p.bg = sky_col

                if x == star_x:
                    if cd > 0.38:
                        p.char = ' '
                        p.fg = plain_fg
                        star_x += STAR_STEP
                        continue
                    # Twinkle: deterministic per-star phase, game-clock driven
                    tw = math.sin(tod * 9.4 + hash_noise(x, y) * 6.2832)
                    if tw > 0.55:
                        p.char = '+'
                        p.fg = (255, 255, 240)
                    elif tw > -0.25:
                        p.char = '*'
                        p.fg = (225, 225, 250)
                    else:
                        p.char = '.'
                        p.fg = (150, 150, 185)
                    star_x += STAR_STEP
                else:
                    p.char = ' '
                    p.fg = plain_fg

        # Moon: hour-driven azimuth/elevation, phase-shaded ASCII disc
        if is_night and lightning_intensity < 0.1 and horizon_y > 0:
            self._draw_moon(camera, day_night, horizon_y, buffer, cloud_dens)

        # Floor rows (below horizon)
        floors_grid = getattr(city_map, 'floors', None)
        map_w = getattr(city_map, 'width', 0)
        map_h = getattr(city_map, 'height', 0)
        get_floor_type = city_map.get_floor_type

        ascii_translate = None if buffer.use_color else ASCII_TRANSLATION.get
        eye_m = camera.eye_m

        ray_dir_x0 = camera.dir.x - camera.plane.x
        ray_dir_y0 = camera.dir.y - camera.plane.y
        ray_dir_x1 = camera.dir.x + camera.plane.x
        ray_dir_y1 = camera.dir.y + camera.plane.y
        span_step_x = (ray_dir_x1 - ray_dir_x0) / float(self.width)
        span_step_y = (ray_dir_y1 - ray_dir_y0) / float(self.width)

        fog_color = weather.fog_color if weather else (0, 0, 0)
        fog_density = weather.fog_density if weather else 0.0

        # Ground light pools: flattened tuples for fast row-culled sampling.
        # Wet pavement boosts and elongates contributions (handled in the
        # dedicated reflection pass; here we just brighten).
        fl_lights: List[Tuple[float, float, float, float, float, float]] = []
        if lights:
            wet_boost = 1.0 + wetness * 0.6
            for L in lights:
                k = L.intensity * wet_boost
                fl_lights.append((L.x, L.y, L.radius2,
                                  L.r * k, L.g * k, L.b * k))

        shade_lut = get_shade_lut
        mid = BAYER_MID
        f_amp = self.DITHER_FOG_AMP
        s_amp = self.DITHER_SHADE_AMP
        fl_k_bg = self.FLOOR_LIGHT_K
        width = self.width

        # Wet-puddle sky tint terms (frame-constant, from the horizon color)
        hrz_r = horizon_col[0] * 0.4
        hrz_g = horizon_col[1] * 0.4
        hrz_b = horizon_col[2] * 0.5
        hrz_r2 = horizon_col[0] * 0.2
        hrz_g2 = horizon_col[1] * 0.2
        hrz_b2 = horizon_col[2] * 0.25

        for y in range(max(0, horizon_y), self.height):
            dy = float(y - horizon_y)
            if dy <= 0.0:
                continue

            row_dist = (ppm * eye_m) / dy
            floor_shade = clamp((1.0 / (1.0 + 0.1 * row_dist + 0.008 * row_dist * row_dist)) * ambient, 0.1, 1.0)

            floor_fog = 0.0
            if fog_density > 0:
                floor_fog = clamp(1.0 - math.exp(-row_dist * fog_density), 0.0, 0.95)
            has_floor_fog = floor_fog > 0.0 and weather is not None

            floor_x = camera.pos.x + row_dist * ray_dir_x0
            floor_y = camera.pos.y + row_dist * ray_dir_y0
            step_x = row_dist * span_step_x
            step_y = row_dist * span_step_y

            # Row culling: keep only lights whose ground-line distance is
            # inside their radius; restrict each to its projected screen span
            # so per-pixel work scales with pool area, not scanline width
            pools: List[List[float]] = []
            if fl_lights:
                slen2 = step_x * step_x + step_y * step_y
                if slen2 > 1e-12:
                    inv_slen = 1.0 / (slen2 ** 0.5)
                    for (lx, ly, lr2, lcr, lcg, lcb) in fl_lights:
                        dxl = lx - floor_x
                        dyl = ly - floor_y
                        cross = dxl * step_y - dyl * step_x
                        dist_line2 = cross * cross * inv_slen * inv_slen
                        if dist_line2 >= lr2:
                            continue
                        proj = (dxl * step_x + dyl * step_y) / slen2
                        half = ((lr2 - dist_line2) ** 0.5) * inv_slen
                        lo = int(proj - half)
                        hi = int(proj + half)
                        if hi < 0 or lo >= width:
                            continue
                        pools.append([lo if lo > 0 else 0,
                                      hi if hi < width - 1 else width - 1,
                                      lx, ly, lr2, lcr, lcg, lcb])
            n_pools = len(pools)
            pools.sort(key=lambda e: e[0])
            active_pools: List[List[float]] = []
            ev = 0

            bayer_row = BAYER4[y & 3]
            row = pixels[y]

            for x in range(width):
                while ev < n_pools and pools[ev][0] == x:
                    p_ = pools[ev]
                    active_pools.append([p_[2] - floor_x, p_[3] - floor_y,
                                         p_[4], p_[5], p_[6], p_[7], p_[1]])
                    ev += 1

                cell_x = int(floor_x)
                cell_y = int(floor_y)
                if floors_grid is not None:
                    if 0 <= cell_x < map_w and 0 <= cell_y < map_h:
                        ftype = floors_grid[cell_y][cell_x]
                    else:
                        ftype = FloorType.SIDEWALK
                else:
                    ftype = get_floor_type(cell_x, cell_y)

                fx_frac = floor_x - cell_x
                fy_frac = floor_y - cell_y

                # Ground light pool accumulation over the active sweep set
                lr_sum = lg_sum = lb_sum = 0.0
                if active_pools:
                    idx_a = 0
                    while idx_a < len(active_pools):
                        e = active_pools[idx_a]
                        # dx = light - floor_pos and floor advances by step,
                        # so the delta evolves with MINUS the step vector
                        e[0] -= step_x
                        e[1] -= step_y
                        ddx = e[0]
                        ddy = e[1]
                        d2 = ddx * ddx + ddy * ddy
                        if d2 < e[2]:
                            fall = 1.0 - d2 / e[2]
                            fall *= fall
                            lr_sum += e[3] * fall
                            lg_sum += e[4] * fall
                            lb_sum += e[5] * fall
                            idx_a += 1
                        elif x > e[6]:
                            active_pools[idx_a] = active_pools[-1]
                            active_pools.pop()
                        else:
                            idx_a += 1

                q = int((floor_shade + (bayer_row[x & 3] - mid) * s_amp) * 64.0 + 0.5)
                lut = SHADE_CACHE.get(q)
                if lut is None:
                    lut = get_shade_lut(q / 64.0)

                if ftype in (FloorType.ROAD_NS, FloorType.ROAD_EW, FloorType.INTERSECTION):
                    is_center_line = (ftype == FloorType.ROAD_NS and abs(fx_frac - 0.5) < 0.08) or \
                                     (ftype == FloorType.ROAD_EW and abs(fy_frac - 0.5) < 0.08)
                    if is_center_line:
                        char = '=' if ftype == FloorType.ROAD_EW else '|'
                        fg = (lut[255], lut[220], lut[0])
                        bg = (lut[40], lut[40], lut[45])
                    else:
                        is_puddle = wetness > 0.1 and (((int(floor_x * 7) ^ int(floor_y * 11)) % 100) < int(wetness * 60))
                        if is_puddle:
                            char = '≈' if (int(floor_x * 6) + int(floor_y * 6)) % 2 == 0 else '~'
                            fg = (min(255, lut[180] + int(hrz_r)),
                                  min(255, lut[200] + int(hrz_g)),
                                  min(255, lut[240] + int(hrz_b)))
                            bg = (min(255, lut[50] + int(hrz_r2)),
                                  min(255, lut[55] + int(hrz_g2)),
                                  min(255, lut[70] + int(hrz_b2)))
                        else:
                            char = '.' if (int(floor_x * 4) + int(floor_y * 4)) % 3 == 0 else ' '
                            fg = (lut[80], lut[80], lut[90])
                            bg = (lut[25], lut[26], lut[30])
                elif ftype == FloorType.PARK_GRASS:
                    char = '"' if (int(floor_x * 3) + int(floor_y * 3)) % 2 == 0 else ','
                    fg = (lut[40], lut[160], lut[60])
                    bg = (lut[15], lut[45], lut[20])
                elif ftype == FloorType.PLAZA_TILES:
                    is_wet_plaza = wetness > 0.2 and (((int(floor_x * 5) + int(floor_y * 5)) % 4) == 0)
                    char = '·' if is_wet_plaza else ('+' if (int(floor_x * 2) + int(floor_y * 2)) % 2 == 0 else ' ')
                    fg = (lut[160], lut[150], lut[140])
                    bg = (lut[50], lut[48], lut[45])
                elif ftype == FloorType.WATER:
                    char = '~' if (int(floor_x * 4) + int(floor_y * 4)) % 2 == 0 else '≈'
                    fg = (lut[100], lut[210], lut[255])
                    bg = (lut[10], lut[30], lut[65])
                elif ftype == FloorType.BRIDGE:
                    char = '=' if (int(floor_x * 3) + int(floor_y * 3)) % 2 == 0 else '-'
                    fg = (lut[190], lut[160], lut[120])
                    bg = (lut[40], lut[35], lut[30])
                elif ftype == FloorType.COBBLESTONE:
                    char = 'o' if (int(floor_x * 3) + int(floor_y * 3)) % 2 == 0 else '·'
                    fg = (lut[170], lut[140], lut[120])
                    bg = (lut[45], lut[35], lut[30])
                elif ftype == FloorType.WOOD_DECK:
                    char = '|' if (int(floor_x * 4)) % 2 == 0 else ' '
                    fg = (lut[160], lut[115], lut[75])
                    bg = (lut[40], lut[28], lut[18])
                else:
                    is_puddle = wetness > 0.2 and (((int(floor_x * 8) + int(floor_y * 8)) % 7) == 0)
                    if is_puddle:
                        char = '~'
                        fg = (min(255, lut[160]), min(255, lut[180]), min(255, lut[210]))
                        bg = (min(255, lut[60]), min(255, lut[65]), min(255, lut[75]))
                    else:
                        char = '.' if (int(floor_x * 4) + int(floor_y * 4)) % 2 == 0 else '_'
                        fg = (lut[140], lut[140], lut[150])
                        bg = (lut[45], lut[45], lut[50])

                if lr_sum > 0.0 or lg_sum > 0.0 or lb_sum > 0.0:
                    nr = fg[0] + lr_sum * 0.45
                    ng = fg[1] + lg_sum * 0.45
                    nb = fg[2] + lb_sum * 0.45
                    if nr > 255.0:
                        nr = 255.0
                    if ng > 255.0:
                        ng = 255.0
                    if nb > 255.0:
                        nb = 255.0
                    nbr = bg[0] + lr_sum * fl_k_bg
                    nbg = bg[1] + lg_sum * fl_k_bg
                    nbb = bg[2] + lb_sum * fl_k_bg
                    if nbr > 255.0:
                        nbr = 255.0
                    if nbg > 255.0:
                        nbg = 255.0
                    if nbb > 255.0:
                        nbb = 255.0
                    fg = (int(nr), int(ng), int(nb))
                    bg = (int(nbr), int(nbg), int(nbb))

                if has_floor_fog:
                    fd = floor_fog + (bayer_row[x & 3] - mid) * f_amp
                    if fd < 0.0:
                        fd = 0.0
                    elif fd > 0.97:
                        fd = 0.97
                    fr, fg_g, fb_b = fog_color
                    fg = (int(fg[0] + (fr - fg[0]) * fd),
                          int(fg[1] + (fg_g - fg[1]) * fd),
                          int(fg[2] + (fb_b - fg[2]) * fd))
                    bg = (int(bg[0] + (fr - bg[0]) * fd),
                          int(bg[1] + (fg_g - bg[1]) * fd),
                          int(bg[2] + (fb_b - bg[2]) * fd))

                if ascii_translate is not None and not char.isascii():
                    char = ascii_translate(char, '?')

                p = row[x]
                p.char = char
                p.fg = fg
                p.bg = bg
                floor_x += step_x
                floor_y += step_y

    def _render_sprites(
        self,
        camera: Camera,
        sprites: List[Sprite],
        horizon_y: int,
        ambient: float,
        weather: Optional[WeatherSystem],
        buffer: ScreenBuffer,
        ppm: Optional[float] = None,
        lights: Optional[List] = None
    ):
        if ppm is None:
            ppm = pixels_per_meter_at_1m(self.width, self.height, camera.plane.length())

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
                    dist_sq=dist_sq,
                    ppm=ppm
                )
                continue

            rows_per_m = ppm / transform_y
            cols_per_m = rows_per_m / CELL_ASPECT
            spr_h = abs(int(rows_per_m * spr.scale_y * spr.height))
            spr_w = abs(int(cols_per_m * spr.scale_x * spr.width))

            ground_row = horizon_y + rows_per_m * camera.eye_m - rows_per_m * spr.vertical_offset
            draw_y0 = int(ground_row - spr_h)
            draw_y1 = int(ground_row)

            draw_x0 = int(spr_screen_x - spr_w / 2.0)
            draw_x1 = int(spr_screen_x + spr_w / 2.0)

            distance_shade = 1.0 / (1.0 + 0.09 * dist + 0.005 * dist_sq)
            shade = 1.0 if spr.is_luminous else clamp(distance_shade * ambient, 0.15, 1.0)

            fog_blend = 0.0
            if weather and weather.fog_density > 0 and not spr.is_luminous:
                fog_blend = clamp(1.0 - math.exp(-dist * weather.fog_density), 0.0, 0.9)

            # One point-light sample per sprite: nearby lamps/neon tint the art
            wash_r = wash_g = wash_b = 0.0
            if lights and not spr.is_luminous and dist < 16.0:
                for L in lights:
                    dxw = spr.x - L.x
                    dyw = spr.y - L.y
                    d2w = dxw * dxw + dyw * dyw
                    if d2w < L.radius2:
                        fw = 1.0 - d2w / L.radius2
                        fw *= fw * L.intensity * self.WALL_LIGHT_K * 0.75
                        wash_r += L.r * fw
                        wash_g += L.g * fw
                        wash_b += L.b * fw
            has_wash = wash_r > 0.5 or wash_g > 0.5 or wash_b > 0.5

            x_start = max(0, draw_x0)
            x_end = min(self.width - 1, draw_x1)

            spr_lut = get_shade_lut(shade)

            for stripe in range(x_start, x_end + 1):
                if transform_y < self.z_buffer[stripe]:
                    tex_x = int((stripe - draw_x0) * spr.width / max(1, spr_w))
                    tex_x = max(0, min(tex_x, spr.width - 1))

                    y_start = max(0, draw_y0)
                    y_end = min(self.height - 1, draw_y1)

                    for y in range(y_start, y_end + 1):
                        tex_y = int((y - draw_y0) * spr.height / max(1, spr_h))
                        tex_y = max(0, min(tex_y, spr.height - 1))

                        row = spr.chars[tex_y]
                        # Sprite grids may be ragged: clamp per-row so a
                        # malformed frame can never tear the render.
                        sx = max(0, min(tex_x, len(row) - 1))
                        char = row[sx]
                        if char != ' ':
                            fg_row = spr.fg_colors[tex_y]
                            fx = sx if sx < len(fg_row) else len(fg_row) - 1
                            fg_raw = fg_row[fx]
                            r = spr_lut[fg_raw[0]]
                            g = spr_lut[fg_raw[1]]
                            b = spr_lut[fg_raw[2]]

                            if has_wash:
                                nr = r + wash_r
                                ng = g + wash_g
                                nb = b + wash_b
                                if nr > 255.0:
                                    nr = 255.0
                                if ng > 255.0:
                                    ng = 255.0
                                if nb > 255.0:
                                    nb = 255.0
                                fg = (int(nr), int(ng), int(nb))
                            else:
                                fg = (r, g, b)

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
        dist_sq: float,
        ppm: Optional[float] = None
    ):
        """
        Pseudo-volumetric box projection: front and side faces share the
        projected extent with an angle-dependent split, so the visible corner
        edge slides across the prop as the camera orbits it.
        """
        if ppm is None:
            ppm = pixels_per_meter_at_1m(self.width, self.height, camera.plane.length())
        rows_per_m = ppm / transform_y

        cam_dx = camera.pos.x - spr.x
        cam_dy = camera.pos.y - spr.y
        front_share, front_left, see_front = spr.visible_faces(cam_dx, cam_dy)

        # Rear hemisphere shows the back face art when one exists
        if see_front:
            face_chars, face_fg = spr.front_chars, spr.front_fg
        else:
            face_chars, face_fg = spr.back_chars, spr.back_fg
        face_w = len(face_chars[0])

        side_w = len(spr.side_chars[0])
        front_w = len(spr.front_chars[0])  # legacy footprint anchor
        rows = max(len(face_chars), len(spr.side_chars))

        # Full-face view must match the legacy flat billboard footprint
        cols_per_m = rows_per_m / CELL_ASPECT
        cell_px = (cols_per_m * spr.scale_x) / float(front_w)
        face_span = cell_px * face_w * front_share
        side_span = cell_px * side_w * (1.0 - front_share)
        total_span = face_span + side_span

        spr_h = abs(int(rows_per_m * spr.scale_y * rows))
        ground_row = horizon_y + rows_per_m * camera.eye_m - rows_per_m * spr.vertical_offset
        draw_y0 = int(ground_row - spr_h)

        x0 = spr_screen_x - int(total_span / 2.0)
        x1 = x0 + int(total_span)

        distance_shade = 1.0 / (1.0 + 0.09 * dist + 0.005 * dist_sq)
        shade = 1.0 if spr.is_luminous else clamp(distance_shade * ambient, 0.15, 1.0)

        fog_blend = 0.0
        if weather and weather.fog_density > 0 and not spr.is_luminous:
            fog_blend = clamp(1.0 - math.exp(-dist * weather.fog_density), 0.0, 0.9)

        y_start = max(0, draw_y0)
        y_end = min(self.height - 1, draw_y0 + spr_h)

        lut_front = get_shade_lut(shade)
        lut_side = get_shade_lut(shade * VolumetricSprite.SIDE_SHADE)

        for stripe in range(max(0, x0), min(self.width - 1, x1) + 1):
            if transform_y >= self.z_buffer[stripe]:
                continue

            in_face = (stripe < x0 + face_span) if front_left else (stripe >= x0 + side_span)
            if in_face:
                art_chars, art_fg, art_w = face_chars, face_fg, face_w
                face_offset = (stripe - x0) if front_left else (stripe - (x0 + side_span))
                plane_shade = shade
            else:
                art_chars, art_fg, art_w = spr.side_chars, spr.side_fg, side_w
                face_offset = (stripe - (x0 + face_span)) if front_left else (stripe - x0)
                plane_shade = shade * VolumetricSprite.SIDE_SHADE

            span = max(1.0, face_span if in_face else side_span)
            tex_x = max(0, min(int(face_offset / span * art_w), art_w - 1))

            for y in range(y_start, y_end + 1):
                tex_y = int((y - draw_y0) * len(art_chars) / max(1, spr_h))
                tex_y = max(0, min(tex_y, len(art_chars) - 1))

                char = art_chars[tex_y][tex_x] if tex_x < len(art_chars[tex_y]) else ' '
                if char == ' ':
                    continue
                fg_raw = art_fg[tex_y][tex_x]
                lut = lut_front if in_face else lut_side
                fg = (lut[fg_raw[0]], lut[fg_raw[1]], lut[fg_raw[2]])
                if fog_blend > 0.0 and weather:
                    fg = _blend_color(fg, weather.fog_color, fog_blend)
                buffer.set_pixel(stripe, y, char, fg, None)

    def _draw_moon(
        self,
        camera: Camera,
        day_night: DayNightCycle,
        horizon_y: int,
        buffer: ScreenBuffer,
        cloud_dens: List[float]
    ):
        """Phase-shaded ASCII moon disc, hour-driven azimuth and elevation."""
        tod = day_night.time_of_day
        # Night arc 19:00 -> 05:00 (10 h): elevation follows a sine bow
        frac = ((tod - 19.0) % 24.0) / 10.0
        if frac > 1.0:
            return
        elev = math.sin(frac * math.pi)
        if elev <= 0.03:
            return

        az = (tod / 24.0) * 6.283185307 + 3.141592654
        yaw = math.atan2(camera.dir.y, camera.dir.x)
        rb = (az - yaw + math.pi) % 6.283185307 - math.pi
        half_fov = camera.plane.length()
        if abs(rb) > half_fov * 1.35:
            return

        mx = int(self.width * (0.5 + math.tan(rb) / (2.0 * max(1e-4, half_fov))))
        my = int(horizon_y - elev * (horizon_y - 2.0))

        # Terminator drifts across the disc over the night (phase cycle)
        cut = int((tod % 3.0) / 3.0 * 7.0) - 3

        bright = (238, 234, 212)
        rim = (206, 202, 184)
        dark = (104, 102, 118)
        pixels = buffer.pixels
        w, h = self.width, self.height
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                d2 = dx * dx + dy * dy * 2.4
                if d2 > 5.4:
                    continue
                x = mx + dx
                y = my + dy
                if x < 0 or x >= w or y < 0 or y >= horizon_y:
                    continue
                if cloud_dens and cloud_dens[x] > 0.55:
                    continue
                if dx < cut:
                    char, col = ':', dark
                elif d2 < 2.0:
                    char, col = 'O', bright
                else:
                    char = '(' if dx < 0 else ('0' if abs(dx) < 1 else ')')
                    col = rim
                p = pixels[y][x]
                p.char = char
                p.fg = col

    def _render_wet_reflections(
        self,
        lights: List,
        camera: Camera,
        horizon_y: int,
        ppm: float,
        weather: WeatherSystem,
        buffer: ScreenBuffer,
        phase: float = 0.0
    ):
        """Screen-space wet-ground reflections: vertical light smears below the
        horizon with hash-noise ripple jitter (research: SSR-lite smear trick).
        Occlusion respects the wall z-buffer per column. `phase` drives the
        ripple animation off the game clock so frames stay deterministic."""
        w, h = self.width, self.height
        wetness = weather.wetness
        inv_det = 1.0 / (camera.plane.x * camera.dir.y - camera.dir.x * camera.plane.y)
        tick = int(phase) & 0xFFFF
        pixels = buffer.pixels

        for L in lights:
            sx_ = L.x - camera.pos.x
            sy_ = L.y - camera.pos.y
            t_x = inv_det * (camera.dir.y * sx_ - camera.dir.x * sy_)
            t_y = inv_det * (-camera.plane.y * sx_ + camera.plane.x * sy_)
            if t_y <= 0.4:
                continue
            col = int((w / 2.0) * (1.0 + t_x / t_y))
            if col < 0 or col >= w:
                continue
            if t_y >= self.z_buffer[col]:
                continue  # light is behind a wall in this column

            gy = int(horizon_y + ppm * camera.eye_m / t_y)
            if gy >= h:
                continue
            if gy < horizon_y:
                gy = horizon_y

            base_int = L.intensity * wetness
            smear = int(ppm * (L.radius * 0.6) / t_y)
            if smear < 2:
                smear = 2
            elif smear > h - gy:
                smear = h - gy
            if smear <= 0:
                continue

            dist_att = 1.0 / (1.0 + 0.03 * t_y * t_y)
            lr = L.r * base_int * dist_att
            lg = L.g * base_int * dist_att
            lb = L.b * base_int * dist_att

            for i in range(smear):
                y = gy + i
                t = i / float(smear)
                fall = (1.0 - t)
                fall *= fall * (1.0 - t * 0.4)
                # Ripple jitter: deterministic, time-animated horizontal wobble
                jx = int(hash_noise(col, y, tick) * 5.0) - 2
                xx = col + jx
                if xx < 0 or xx >= w:
                    continue
                k = fall * 46.0
                kr = lr * k
                kg = lg * k
                kb = lb * k

                row = pixels[y]
                p = row[xx]
                nr = p.fg[0] + kr if p.fg else kr
                ng = p.fg[1] + kg if p.fg else kg
                nb = p.fg[2] + kb if p.fg else kb
                if nr > 255.0:
                    nr = 255.0
                if ng > 255.0:
                    ng = 255.0
                if nb > 255.0:
                    nb = 255.0
                br = (p.bg[0] + kr * 0.8) if p.bg else kr * 0.8
                bg_ = (p.bg[1] + kg * 0.8) if p.bg else kg * 0.8
                bb = (p.bg[2] + kb * 0.8) if p.bg else kb * 0.8
                if br > 255.0:
                    br = 255.0
                if bg_ > 255.0:
                    bg_ = 255.0
                if bb > 255.0:
                    bb = 255.0
                p.fg = (int(nr), int(ng), int(nb))
                p.bg = (int(br), int(bg_), int(bb))
                if fall > 0.72 and p.char == ' ' and hash_noise(xx, y, tick + 91) > 0.86:
                    p.char = '~'

    def _postfx(self, buffer: ScreenBuffer, phase: float = 0.0):
        """Single-pass post chain: bloom-lite (thresholded low-res dilation),
        then vignette multiply via gamma LUT buckets plus subtle film grain.
        Color mode only; skipped entirely in mono/ASCII mode. `phase` (game
        clock) drives grain animation while keeping frames deterministic."""
        bw, bh = buffer.width, buffer.height
        if bw <= 0 or bh <= 0:
            return
        pixels = buffer.pixels
        seed = int(phase * 24.0) & 0xFFFF
        threshold = self.BLOOM_THRESHOLD

        # ---- Bloom-lite: sample every 2nd cell, dilate on a /4 grid ----
        # Energy is a running MAX (bounded [0,255]) and the write-back add is
        # bounded, so glow lifts its neighbourhood without ever blowing out.
        gw = (bw + 3) // 4
        gh = (bh + 3) // 4
        acc = [[0.0, 0.0, 0.0] for _ in range(gw * gh)]
        any_bloom = False
        for y in range(0, bh, 2):
            row = pixels[y]
            gy = (y >> 2) * gw
            for x in range(0, bw, 2):
                p = row[x]
                fg = p.fg
                bg = p.bg
                fm = max(fg) if fg else 0
                bm = max(bg) if bg else 0
                m = fm if fm > bm else bm
                if m > threshold:
                    src = fg if fm > bm else bg
                    scale = m / 255.0
                    cell = acc[gy + (x >> 2)]
                    sr = src[0] * scale
                    sg = src[1] * scale
                    sb = src[2] * scale
                    if sr > cell[0]:
                        cell[0] = sr
                    if sg > cell[1]:
                        cell[1] = sg
                    if sb > cell[2]:
                        cell[2] = sb
                    any_bloom = True

        if any_bloom:
            for gy in range(gh):
                base = gy * gw
                for gx in range(gw):
                    cell = acc[base + gx]
                    er, eg, eb = cell
                    if er + eg + eb <= 60.0:
                        continue
                    for ox in (-1, 0, 1):
                        for oy in (-1, 0, 1):
                            nx = gx + ox
                            ny = gy + oy
                            if nx < 0 or nx >= gw or ny < 0 or ny >= gh:
                                continue
                            k = 0.42 if (ox == 0 and oy == 0) else 0.22
                            cx = nx * 4 + 2
                            cy = ny * 4 + 2
                            if cx >= bw or cy >= bh:
                                continue
                            p = pixels[cy][cx]
                            if p.fg is not None:
                                nr = p.fg[0] + er * k
                                ng = p.fg[1] + eg * k
                                nb = p.fg[2] + eb * k
                                p.fg = (255 if nr > 255.0 else int(nr),
                                        255 if ng > 255.0 else int(ng),
                                        255 if nb > 255.0 else int(nb))

        # ---- Vignette (cached multiplier grid) + film grain ----
        vig = self._vignette
        if vig is None or self._vignette_size != (bw, bh):
            strength = self.VIGNETTE_STRENGTH
            inv_w = 2.0 / max(1, bw - 1)
            inv_h = 2.0 / max(1, bh - 1)
            vig = []
            for y in range(bh):
                ny = y * inv_h - 1.0
                ny2 = ny * ny
                for x in range(bw):
                    nx = x * inv_w - 1.0
                    d2 = nx * nx + ny2
                    if d2 > 1.0:
                        d2 = 1.0
                    v = 1.0 - strength * (d2 * d2 * (3.0 - 2.0 * d2))
                    vig.append(v)
            self._vignette = vig
            self._vignette_size = (bw, bh)

        # Grain: one noise value per column per frame; rows reuse the row with
        # a rotating offset so cells decorrelate without per-pixel hashing.
        grain_row = [(hash_noise(x, 917, seed) - 0.5) for x in range(bw)]
        # Vignette bucket LUTs: quantized to the same 1/64 shade grid, filled
        # lazily so the inner loop only does one dict.get per pixel.
        vig_luts = {}
        idx = 0
        for y in range(bh):
            row = pixels[y]
            grow = (y * 7) % bw
            for x in range(bw):
                v = vig[idx]
                idx += 1
                q = int(v * 64.0 + 0.5)
                lut = vig_luts.get(q)
                if lut is None:
                    lut = get_shade_lut(q / 64.0)
                    vig_luts[q] = lut

                p = row[x]
                fg = p.fg
                if fg is not None:
                    r = lut[fg[0]]
                    gg = lut[fg[1]]
                    b = lut[fg[2]]
                    g = grain_row[(x + grow) % bw]
                    fm0 = fg[0] if fg[0] > fg[1] else fg[1]
                    bm = b if b > fm0 else fm0
                    if bm < 84:
                        g *= 9.0
                    elif bm < 150:
                        g *= 4.0
                    else:
                        g = 0.0
                    if g != 0.0:
                        r += g
                        gg += g
                        b += g
                    p.fg = (0 if r < 0 else (255 if r > 255 else int(r)),
                            0 if gg < 0 else (255 if gg > 255 else int(gg)),
                            0 if b < 0 else (255 if b > 255 else int(b)))
                bg = p.bg
                if bg is not None:
                    p.bg = (lut[bg[0]], lut[bg[1]], lut[bg[2]])
