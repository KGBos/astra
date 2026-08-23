"""
Main Game Engine loop, state management, and autonomous demo mode for Astra 3D.
"""

import math
import random
import time
from typing import Optional

from src.engine.camera import Camera
from src.engine.raycaster import Raycaster
from src.world.city_map import CityMap
from src.world.day_night import DayNightCycle
from src.world.weather import WeatherSystem, WeatherType
from src.entities.traffic_manager import TrafficManager
from src.entities.pedestrian_manager import PedestrianManager
from src.renderer.screen_buffer import ScreenBuffer
from src.renderer.hud import HUD
from src.renderer.terminal import TerminalManager
from src.input.keyboard import KeyboardController, KeyAction


class Game:
    def __init__(
        self,
        width: int = 80,
        height: int = 32,
        target_fps: int = 30,
        use_color: bool = True,
        demo_mode: bool = False
    ):
        self.target_fps = target_fps
        self.frame_time = 1.0 / target_fps
        self.running = False
        self.demo_mode = demo_mode
        self.demo_timer = 0.0

        # Subsystems
        self.terminal = TerminalManager()
        self.keyboard = KeyboardController()
        
        # World & Camera
        self.city_map = CityMap(width=42, height=42)
        # Spawn player in Cyber-Downtown near avenue
        self.camera = Camera(x=12.5, y=6.5, fov_deg=70.0)
        self.camera.set_direction(math.pi / 2.0)  # Face South (+Y) down avenue
        self.camera.pos.x, self.camera.pos.y = self.city_map.spawn_pos

        self.vehicle_count = 18
        self.traffic = TrafficManager(self.city_map, vehicle_count=self.vehicle_count)
        self.pedestrians = PedestrianManager(self.city_map, pedestrian_count=28)
        self.day_night = DayNightCycle(start_hour=22.5, time_speed=0.4)
        self.weather = WeatherSystem(weather=WeatherType.CLEAR)
        
        # Rendering
        self.screen_w = width
        self.screen_h = height
        self.buffer = ScreenBuffer(width, height, use_color=use_color)
        self.raycaster = Raycaster(width, height)
        self.hud = HUD(show_minimap=True)

        # Performance metrics
        self.fps = float(target_fps)
        self.frame_count = 0
        self.total_frames = 0
        self.last_fps_calc = time.time()

    def regenerate_city(self, seed=None) -> None:
        """Rebuilds the procedural city, traffic, and pedestrians for a given seed (random if None)."""
        if seed is None:
            seed = random.randint(100000, 999999)
        self.city_map = CityMap(width=self.city_map.width, height=self.city_map.height, seed=seed)
        self.traffic = TrafficManager(self.city_map, vehicle_count=self.vehicle_count)
        self.pedestrians = PedestrianManager(self.city_map, pedestrian_count=28)
        self.camera.pos.x, self.camera.pos.y = self.city_map.spawn_pos

    def run(self, max_frames: Optional[int] = None):
        """Starts the main game loop."""
        self.running = True
        
        with self.terminal:
            # Detect actual terminal size if running interactively
            tw, th = self.terminal.get_size()
            self._resize_viewport(tw, th)

            last_time = time.time()

            while self.running:
                loop_start = time.time()
                dt = min(0.1, loop_start - last_time)
                last_time = loop_start

                # 1. Handle Terminal Resize Event
                if self.terminal.resized:
                    self.terminal.resized = False
                    tw, th = self.terminal.get_size()
                    self._resize_viewport(tw, th)

                # 2. Input Processing
                self._process_input(dt)

                # 3. Update Simulation
                self._update_simulation(dt)

                # 4. Render Frame
                self._render_frame()

                # 5. Flush to Terminal
                frame_str = self.buffer.render_to_ansi()
                self.terminal.flush_frame(frame_str)

                # 6. FPS Calculation
                self.frame_count += 1
                self.total_frames += 1
                now = time.time()
                if now - self.last_fps_calc >= 0.5:
                    self.fps = self.frame_count / (now - self.last_fps_calc)
                    self.frame_count = 0
                    self.last_fps_calc = now

                # 7. Frame Limiter
                elapsed = time.time() - loop_start
                sleep_time = self.frame_time - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

                if max_frames and self.total_frames >= max_frames:
                    break

    def _resize_viewport(self, w: int, h: int):
        self.screen_w = w
        self.screen_h = h
        self.buffer.resize(w, h)
        self.raycaster.resize(w, h)

    def _process_input(self, dt: float):
        if self.demo_mode:
            self._update_demo_camera(dt)
            # Still poll keyboard to check for exit
            self.keyboard.poll_input()
            if self.keyboard.has_event(KeyAction.QUIT):
                self.running = False
            return

        self.keyboard.poll_input()

        # Exit
        if self.keyboard.has_event(KeyAction.QUIT):
            self.running = False
            return

        # Movement
        is_sprint = self.keyboard.is_action_active(KeyAction.SPRINT)
        if self.keyboard.is_action_active(KeyAction.MOVE_FORWARD):
            self.camera.move_forward(dt, is_sprint, self.city_map)
        elif self.keyboard.is_action_active(KeyAction.MOVE_BACKWARD):
            self.camera.move_backward(dt, is_sprint, self.city_map)

        if self.keyboard.is_action_active(KeyAction.STRAFE_LEFT):
            self.camera.strafe_left(dt, self.city_map)
        elif self.keyboard.is_action_active(KeyAction.STRAFE_RIGHT):
            self.camera.strafe_right(dt, self.city_map)

        # Turning
        if self.keyboard.is_action_active(KeyAction.TURN_LEFT):
            self.camera.rotate(-self.camera.rot_speed * dt)
        elif self.keyboard.is_action_active(KeyAction.TURN_RIGHT):
            self.camera.rotate(self.camera.rot_speed * dt)

        # Pitch
        if self.keyboard.is_action_active(KeyAction.LOOK_UP):
            self.camera.pitch_look(12.0 * dt)
        elif self.keyboard.is_action_active(KeyAction.LOOK_DOWN):
            self.camera.pitch_look(-12.0 * dt)

        # Actions
        if self.keyboard.has_event(KeyAction.JUMP):
            self.camera.jump()
        if self.keyboard.has_event(KeyAction.TOGGLE_MAP):
            self.hud.show_minimap = not self.hud.show_minimap
            self.hud.set_notification(f"GPS RADAR: {'ENABLED' if self.hud.show_minimap else 'DISABLED'}")
        if self.keyboard.has_event(KeyAction.TOGGLE_TIME):
            self.day_night.time_of_day = (self.day_night.time_of_day + 4.0) % 24.0
            self.hud.set_notification(f"TIME SKIPPED // {self.day_night.get_time_string()}")
        if self.keyboard.has_event(KeyAction.TOGGLE_WEATHER):
            self.weather.toggle_weather(self.screen_w, self.screen_h)
            self.hud.set_notification(f"WEATHER MODE // {self.weather.current_weather.value}")
        if self.keyboard.has_event(KeyAction.TOGGLE_FLASHLIGHT):
            self.hud.toggle_flashlight()
        if self.keyboard.has_event(KeyAction.REGENERATE_CITY):
            new_seed = random.randint(100000, 999999)
            self.regenerate_city(new_seed)
            self.hud.set_notification(f"METROPOLIS RE-SYNTHESIZED // SEED #{new_seed}", duration=4.0)
        if self.keyboard.has_event(KeyAction.CYCLE_LANDMARKS):
            if not hasattr(self, '_landmark_idx'):
                self._landmark_idx = 0
            else:
                self._landmark_idx = (self._landmark_idx + 1) % max(1, len(self.city_map.landmarks))
            if self.city_map.landmarks:
                lm = self.city_map.landmarks[self._landmark_idx]
                dist = lm.distance_to(self.camera.pos.x, self.camera.pos.y)
                bearing = lm.bearing_from(self.camera.pos.x, self.camera.pos.y)
                desc = lm.description if len(lm.description) <= 35 else lm.description[:32] + "..."
                self.hud.set_notification(f"★ [{lm.district}] {lm.name} ({dist:.0f}m {bearing}) - {desc}", duration=4.0)
        if self.keyboard.has_event(KeyAction.INTERACT):
            talk_res = self.pedestrians.interact_with_focused(self.camera.pos.x, self.camera.pos.y, self.camera.dir.x, self.camera.dir.y)
            if talk_res:
                archetype, quote = talk_res
                arch_name = archetype.replace('_', ' ').title()
                self.hud.set_notification(f"[{arch_name}]: \"{quote}\"", duration=4.5)
        if self.keyboard.has_event(KeyAction.HONK_HORN):
            self.pedestrians.alert_nearby(self.camera.pos.x, self.camera.pos.y)
            self.hud.set_notification("HONK! CITIZENS & CARS ALERTED", duration=2.0)

    def _update_demo_camera(self, dt: float):
        """Smooth autonomous city tour for demo mode."""
        self.demo_timer += dt
        # Move forward automatically along road grid
        self.camera.move_forward(dt, is_sprinting=False, world_map=self.city_map)
        
        # Slowly sweep camera yaw and turn at intersections
        ix = int(self.camera.pos.x)
        iy = int(self.camera.pos.y)
        if (ix, iy) in self.city_map.traffic_lights:
            # Turn slightly
            self.camera.rotate(0.3 * dt)
        else:
            self.camera.rotate(math.sin(self.demo_timer * 0.5) * 0.15 * dt)

    def _update_simulation(self, dt: float):
        self.camera.update_physics(dt)
        self.city_map.update(dt)
        self.traffic.update(dt)
        self.pedestrians.update(dt)
        self.day_night.update(dt)
        self.weather.update(dt, self.screen_w, self.screen_h)

        # Check focused pedestrian for interaction prompt
        focused_ped = self.pedestrians.get_focused_pedestrian(self.camera.pos.x, self.camera.pos.y, self.camera.dir.x, self.camera.dir.y)
        if focused_ped:
            self.hud.interaction_prompt = f"[F] Talk with {focused_ped.archetype.value.replace('_', ' ').title()}"
        else:
            self.hud.interaction_prompt = None

        self.hud.update(dt, weather=self.weather)

    def _render_frame(self):
        self.buffer.clear()
        
        # Collect dynamic sprites (traffic vehicles, static props, and pedestrians)
        sprites = self.traffic.get_all_sprites_for_camera(self.camera.pos.x, self.camera.pos.y) + \
                  self.pedestrians.get_all_sprites_for_camera(self.camera.pos.x, self.camera.pos.y)

        # 3D Raycasting & projection
        self.raycaster.render(
            camera=self.camera,
            city_map=self.city_map,
            sprites=sprites,
            day_night=self.day_night,
            buffer=self.buffer,
            weather=self.weather,
            flashlight_on=self.hud.flashlight_on
        )

        # HUD & Overlays
        self.hud.render(
            camera=self.camera,
            city_map=self.city_map,
            sprites=sprites,
            day_night=self.day_night,
            weather=self.weather,
            fps=self.fps,
            buffer=self.buffer
        )
