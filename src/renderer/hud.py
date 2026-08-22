"""
Interactive HUD, Mini-Map GPS Radar, Vehicle Dashboard, Radio Equalizer, and NPC Dialogue for Astra 3D.
"""

import math
from typing import List, Tuple, Optional
from src.engine.camera import Camera
from src.engine.math3d import rad_to_deg, get_compass_bearing
from src.world.city_map import CityMap
from src.world.day_night import DayNightCycle
from src.world.weather import WeatherSystem
from src.entities.sprite import Sprite
from src.renderer.screen_buffer import ScreenBuffer


class HUD:
    def __init__(self, show_minimap: bool = True):
        self.show_minimap = show_minimap
        self.notification_msg = "WELCOME TO ASTRA 3D // CITY EXPLORER"
        self.notification_timer = 5.0

    def set_notification(self, msg: str, duration: float = 3.0):
        self.notification_msg = msg
        self.notification_timer = duration

    def update(self, dt: float):
        if self.notification_timer > 0.0:
            self.notification_timer -= dt

    def render(
        self,
        camera: Camera,
        city_map,
        sprites: List[Sprite],
        day_night: DayNightCycle,
        weather: WeatherSystem,
        sound_system,
        fps: float,
        prompt_text: Optional[str],
        active_dialogue: Optional[dict],
        buffer: ScreenBuffer
    ):
        w = buffer.width
        h = buffer.height

        # 1. Crosshair at screen center (only when not driving)
        cx = w // 2
        cy = h // 2
        if not camera.is_driving and not active_dialogue:
            buffer.set_pixel(cx, cy, '+', (255, 255, 255), None)
            buffer.set_pixel(cx - 1, cy, '·', (180, 180, 180), None)
            buffer.set_pixel(cx + 1, cy, '·', (180, 180, 180), None)

        # 2. Top Header Telemetry Bar & Radio Station
        district = city_map.get_district_at(camera.pos.x, camera.pos.y) if hasattr(city_map, 'get_district_at') else city_map.name
        street = city_map.get_nearest_street_name(camera.pos.x, camera.pos.y) if hasattr(city_map, 'get_nearest_street_name') else "Interior Zone"
        bearing = get_compass_bearing(camera.dir.x, camera.dir.y)
        cam_deg = int(rad_to_deg(math.atan2(camera.dir.y, camera.dir.x)))
        time_str = day_night.get_time_string()
        weather_str = weather.current_weather.value

        # Radio track & EQ
        curr_station = sound_system.get_current_station()
        eq_bars = sound_system.get_eq_visualizer(4)
        radio_str = f"📻 {curr_station.freq} {eq_bars} {curr_station.name}"

        top_left = f" ASTRA 3D │ {district} │ {street}"
        top_right = f"{radio_str} │ DIR: {bearing} [{cam_deg:03d}°] │ {time_str} │ {fps:4.1f} FPS "

        # Draw Top Bar background
        for x in range(w):
            buffer.set_pixel(x, 0, ' ', None, (20, 25, 35))
        buffer.draw_string(0, 0, top_left[:w - len(top_right) - 1], (0, 240, 255), (20, 25, 35))
        buffer.draw_string(max(0, w - len(top_right)), 0, top_right, (255, 220, 50), (20, 25, 35))

        # 3. Notification banner if active
        if self.notification_timer > 0.0:
            notif = f" ⚡ {self.notification_msg} "
            nx = max(0, (w - len(notif)) // 2)
            buffer.draw_string(nx, 2, notif, (255, 255, 255), (180, 30, 80))

        # 4. Contextual Interaction Prompt (e.g. [E] Enter Store / [F] Drive Car)
        if prompt_text and not active_dialogue:
            px = max(0, (w - len(prompt_text) - 4) // 2)
            py = h - 4
            buffer.draw_string(px, py, f" ▶ {prompt_text} ◀ ", (255, 255, 100), (40, 30, 10))

        # 5. Speed Lines Effect when Driving Fast
        if camera.is_driving and abs(camera.car_velocity) > 6.0:
            speed_ratio = abs(camera.car_velocity) / camera.car_max_speed
            char_line = ">>>" if camera.car_velocity > 0 else "<<<"
            col = (255, 100, 220) if camera.nitro_active else (100, 220, 255)
            for sy in [h // 3, h // 2, 2 * h // 3]:
                buffer.draw_string(2, sy, char_line, col, None)
                buffer.draw_string(w - 5, sy, char_line, col, None)

        # 6. Mini-Map GPS Radar (Top Right below top bar)
        if self.show_minimap and hasattr(city_map, 'width') and w >= 60 and h >= 20 and not active_dialogue:
            self._render_minimap(camera, city_map, sprites, buffer)

        # 7. Bottom Navigation / Vehicle Dashboard Bar
        if camera.is_driving:
            mph = int(abs(camera.car_velocity) * 12.0)
            nitro_bars = "█" * int(camera.nitro_meter / 10.0)
            bot_left = f" 🏎️ [{camera.vehicle_type_name}] {mph:3d} MPH │ NITRO: [{nitro_bars:<10}] │ LIGHTS: {'ON' if camera.headlights_on else 'OFF'}"
            bot_right = "[W] Accel │ [S] Brake │ [A/D] Steer │ [Shift] Nitro │ [L] Lights │ [H] Horn │ [G] Radio │ [F] Exit "
        else:
            speed_gauge = "█" * int(min(10, (camera.move_speed * (camera.sprint_mult if camera.is_jumping or camera.bob_amount > 0 else 1.0))))
            bot_left = f" POS: X:{camera.pos.x:4.1f} Y:{camera.pos.y:4.1f} │ SPEED: [{speed_gauge:<10}] │ EYE: {camera.eye_height:.1f}"
            bot_right = "[WASD] Move │ [←→/QE] Turn │ [Shift] Sprint │ [Space] Jump │ [G] Radio │ [L] Lights │ [M] Map │ [Esc] Quit "

        # Draw Bottom Bar background
        for x in range(w):
            buffer.set_pixel(x, h - 1, ' ', None, (15, 20, 30))
        buffer.draw_string(0, h - 1, bot_left[:w - len(bot_right) - 1], (180, 220, 255), (15, 20, 30))
        buffer.draw_string(max(0, w - len(bot_right)), h - 1, bot_right, (150, 180, 210), (15, 20, 30))

        # 8. Interactive NPC Dialogue Box Overlay
        if active_dialogue:
            self._render_dialogue_box(active_dialogue, buffer)

        # 9. Weather Overlay (Rain particles)
        if weather.current_weather == weather.current_weather.RAIN:
            for p in weather.particles:
                px = int(p.x)
                py = int(p.y)
                if 1 <= py < h - 1 and 0 <= px < w:
                    buffer.set_pixel(px, py, p.char, (160, 200, 255), None)

    def _render_dialogue_box(self, dialogue: dict, buffer: ScreenBuffer):
        w = buffer.width
        h = buffer.height
        box_w = min(70, w - 8)
        box_h = 10
        bx = (w - box_w) // 2
        by = h - box_h - 2

        npc_name = dialogue.get("name", "NPC")
        npc_title = dialogue.get("title", "")
        response_text = dialogue.get("response", "")
        options = dialogue.get("options", [])

        buffer.draw_box(bx, by, box_w, box_h, (255, 60, 180), (15, 10, 25), f" {npc_name.upper()} — {npc_title} ")
        
        # Dialogue message
        buffer.draw_string(bx + 2, by + 2, f'"{response_text}"'[:box_w - 4], (255, 240, 180), (15, 10, 25))

        # Dialogue choices
        for idx, opt in enumerate(options[:3]):
            choice_str = f"[{idx + 1}] {opt.text}"
            buffer.draw_string(bx + 2, by + 4 + idx, choice_str[:box_w - 4], (100, 220, 255), (15, 10, 25))

        buffer.draw_string(bx + 2, by + box_h - 2, "[1/2/3] Choose Question │ [Space] Exit Conversation", (180, 180, 200), (15, 10, 25))

    def _render_minimap(
        self,
        camera: Camera,
        city_map: CityMap,
        sprites: List[Sprite],
        buffer: ScreenBuffer
    ):
        map_w = 17
        map_h = 9
        map_x = buffer.width - map_w - 2
        map_y = 2

        buffer.draw_box(map_x, map_y, map_w, map_h, (0, 200, 255), (10, 15, 25), "GPS RADAR")

        radar_radius_x = (map_w - 2) // 2
        radar_radius_y = (map_h - 2) // 2
        center_screen_x = map_x + 1 + radar_radius_x
        center_screen_y = map_y + 1 + radar_radius_y

        cam_ix = int(camera.pos.x)
        cam_iy = int(camera.pos.y)

        for dy in range(-radar_radius_y, radar_radius_y + 1):
            for dx in range(-radar_radius_x, radar_radius_x + 1):
                wx = cam_ix + dx
                wy = cam_iy + dy
                sx = center_screen_x + dx
                sy = center_screen_y + dy

                if 0 <= wx < city_map.width and 0 <= wy < city_map.height:
                    if city_map.is_solid(wx, wy):
                        buffer.set_pixel(sx, sy, '#', (90, 100, 130), (20, 25, 40))
                    elif hasattr(city_map, 'portals') and (wx, wy) in city_map.portals:
                        buffer.set_pixel(sx, sy, 'D', (255, 220, 0), (30, 20, 10))
                    elif hasattr(city_map, 'traffic_lights') and (wx, wy) in city_map.traffic_lights:
                        tl = city_map.traffic_lights[(wx, wy)]
                        tl_col = (50, 255, 50) if tl.is_green_for_ns() else (255, 50, 50)
                        buffer.set_pixel(sx, sy, 'o', tl_col, (10, 15, 25))
                    else:
                        buffer.set_pixel(sx, sy, '·', (60, 70, 85), (10, 15, 25))

        # Draw vehicle / sprite blips on radar
        for spr in sprites:
            sdx = int(spr.x - camera.pos.x)
            sdy = int(spr.y - camera.pos.y)
            if -radar_radius_x <= sdx <= radar_radius_x and -radar_radius_y <= sdy <= radar_radius_y:
                blip_x = center_screen_x + sdx
                blip_y = center_screen_y + sdy
                if "CAR" in spr.name:
                    buffer.set_pixel(blip_x, blip_y, 'o', (255, 220, 0), (10, 15, 25))
                elif "NPC" in spr.name:
                    buffer.set_pixel(blip_x, blip_y, 'p', (255, 80, 200), (10, 15, 25))
                elif "STREETLAMP" in spr.name:
                    buffer.set_pixel(blip_x, blip_y, '*', (255, 255, 120), (10, 15, 25))

        # Player Arrow Indicator
        heading_arrow = self._get_player_arrow(camera.dir.x, camera.dir.y)
        buffer.set_pixel(center_screen_x, center_screen_y, heading_arrow, (255, 60, 60), (10, 15, 25))

    def _get_player_arrow(self, dir_x: float, dir_y: float) -> str:
        angle = math.atan2(dir_y, dir_x)
        deg = rad_to_deg(angle)
        arrows = ["►", "↘", "▼", "↙", "◄", "↖", "▲", "↗"]
        idx = int((deg + 22.5) / 45.0) % 8
        return arrows[idx]
