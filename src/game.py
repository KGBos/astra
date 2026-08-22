"""
Main Game Engine loop, state management, vehicle driving, interior exploration, and NPC conversations for Astra 3D.
"""

import time
import math
from typing import Optional, Dict

from src.engine.camera import Camera
from src.engine.raycaster import Raycaster
from src.world.city_map import CityMap
from src.world.day_night import DayNightCycle
from src.world.weather import WeatherSystem, WeatherType
from src.world.interiors import build_interiors_catalog, InteriorRoom
from src.entities.traffic_manager import TrafficManager
from src.audio.sound_system import SoundSystem
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
        self.sound_system = SoundSystem()
        
        # World & Camera
        self.city_map = CityMap(width=42, height=42)
        self.interiors: Dict[str, InteriorRoom] = build_interiors_catalog()
        self.current_interior: Optional[InteriorRoom] = None
        self.saved_outdoor_pos = (12.5, 6.5)

        # Spawn player in Cyber-Downtown near avenue
        self.camera = Camera(x=12.5, y=6.5, fov_deg=70.0)
        self.camera.set_direction(math.pi / 2.0)  # Face South (+Y) down avenue

        self.traffic = TrafficManager(self.city_map, vehicle_count=18)
        self.day_night = DayNightCycle(start_hour=22.5, time_speed=0.4)
        self.weather = WeatherSystem(weather=WeatherType.CLEAR)
        
        # Rendering
        self.screen_w = width
        self.screen_h = height
        self.buffer = ScreenBuffer(width, height, use_color=use_color)
        self.raycaster = Raycaster(width, height)
        self.hud = HUD(show_minimap=True)

        # Interaction & Dialogue states
        self.current_prompt: Optional[str] = None
        self.active_dialogue: Optional[dict] = None

        # Performance metrics
        self.fps = float(target_fps)
        self.frame_count = 0
        self.last_fps_calc = time.time()

    def run(self, max_frames: Optional[int] = None):
        """Starts the main game loop."""
        self.running = True
        
        with self.terminal:
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

                if max_frames and self.frame_count >= max_frames:
                    break

    def _resize_viewport(self, w: int, h: int):
        self.screen_w = w
        self.screen_h = h
        self.buffer.resize(w, h)
        self.raycaster.resize(w, h)

    def _process_input(self, dt: float):
        if self.demo_mode:
            self._update_demo_camera(dt)
            self.keyboard.poll_input()
            if self.keyboard.has_event(KeyAction.QUIT):
                self.running = False
            return

        self.keyboard.poll_input()

        # Exit
        if self.keyboard.has_event(KeyAction.QUIT):
            if self.active_dialogue:
                self.active_dialogue = None
            elif self.current_interior:
                self._exit_interior()
            else:
                self.running = False
            return

        active_map = self.current_interior if self.current_interior else self.city_map

        # Handle NPC Dialogue interaction mode
        if self.active_dialogue:
            if self.keyboard.has_event(KeyAction.JUMP):
                self.active_dialogue = None  # Exit conversation on Space
                return
            options = self.active_dialogue.get("options", [])
            choice = None
            if self.keyboard.has_event(KeyAction.NUM_1) and len(options) >= 1:
                choice = options[0]
            elif self.keyboard.has_event(KeyAction.NUM_2) and len(options) >= 2:
                choice = options[1]
            elif self.keyboard.has_event(KeyAction.NUM_3) and len(options) >= 3:
                choice = options[2]

            if choice:
                self.active_dialogue["response"] = choice.response
                self.sound_system.play_beep()
            return

        # Vehicle Enter / Exit
        if self.keyboard.has_event(KeyAction.ENTER_EXIT_VEHICLE):
            if self.camera.is_driving:
                self.camera.exit_vehicle()
                self.hud.set_notification("EXITED VEHICLE // WALKING MODE", 2.0)
                self.sound_system.play_beep()
            else:
                nearby_v = self.traffic.get_nearby_vehicle(self.camera.pos.x, self.camera.pos.y)
                if nearby_v:
                    self.camera.enter_vehicle(
                        nearby_v.vtype.value,
                        nearby_v.x,
                        nearby_v.y,
                        nearby_v.dx,
                        nearby_v.dy
                    )
                    self.hud.set_notification(f"DRIVING [{nearby_v.vtype.value}] // [W] ACCEL [A/D] STEER [SHIFT] NITRO", 3.0)
                    self.sound_system.play_beep()

        # Building Interior Entry / NPC Talk
        if self.keyboard.has_event(KeyAction.INTERACT):
            if self.current_interior:
                # Check if near exit door
                if math.hypot(self.camera.pos.x - self.current_interior.exit_pos[0],
                              self.camera.pos.y - self.current_interior.exit_pos[1]) <= 2.0:
                    self._exit_interior()
            else:
                # Check nearby portal
                portal = self.city_map.get_nearby_portal(self.camera.pos.x, self.camera.pos.y)
                if portal and portal.target_room_id in self.interiors:
                    self._enter_interior(portal.target_room_id)
                else:
                    # Check nearby NPC
                    nearby_npc = self.traffic.get_nearby_npc(self.camera.pos.x, self.camera.pos.y)
                    if nearby_npc:
                        self.active_dialogue = {
                            "name": nearby_npc.name,
                            "title": nearby_npc.title,
                            "response": nearby_npc.dialogue[0].response if nearby_npc.dialogue else "Hello traveler!",
                            "options": nearby_npc.dialogue
                        }
                        self.sound_system.play_beep()

        # Movement
        is_sprint = self.keyboard.is_action_active(KeyAction.SPRINT)
        if self.keyboard.is_action_active(KeyAction.MOVE_FORWARD):
            self.camera.move_forward(dt, is_sprint, active_map)
        elif self.keyboard.is_action_active(KeyAction.MOVE_BACKWARD):
            self.camera.move_backward(dt, is_sprint, active_map)

        if self.keyboard.is_action_active(KeyAction.STRAFE_LEFT):
            self.camera.strafe_left(dt, active_map)
        elif self.keyboard.is_action_active(KeyAction.STRAFE_RIGHT):
            self.camera.strafe_right(dt, active_map)

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

        # Actions & System Toggles
        if self.keyboard.has_event(KeyAction.JUMP):
            self.camera.jump()
        if self.keyboard.has_event(KeyAction.TOGGLE_RADIO):
            st = self.sound_system.next_station()
            self.hud.set_notification(f"TUNED RADIO // {st.freq} {st.name}", 2.5)
            self.sound_system.play_beep()
        if self.keyboard.has_event(KeyAction.TOGGLE_LIGHTS):
            self.camera.headlights_on = not self.camera.headlights_on
            self.hud.set_notification(f"LIGHTS: {'HIGH BEAMS ON' if self.camera.headlights_on else 'OFF'}", 2.0)
        if self.keyboard.has_event(KeyAction.TOGGLE_MAP):
            self.hud.show_minimap = not self.hud.show_minimap
            self.hud.set_notification(f"GPS RADAR: {'ENABLED' if self.hud.show_minimap else 'DISABLED'}")
        if self.keyboard.has_event(KeyAction.TOGGLE_TIME):
            self.day_night.time_of_day = (self.day_night.time_of_day + 4.0) % 24.0
            self.hud.set_notification(f"TIME SKIPPED // {self.day_night.get_time_string()}")
        if self.keyboard.has_event(KeyAction.TOGGLE_WEATHER):
            self.weather.toggle_weather(self.screen_w, self.screen_h)
            self.hud.set_notification(f"WEATHER MODE // {self.weather.current_weather.value}")
        if self.keyboard.has_event(KeyAction.HONK_HORN):
            self.sound_system.play_beep()
            self.hud.set_notification("HONK! 📯 CARS ALERTED", duration=2.0)

    def _enter_interior(self, room_id: str):
        self.saved_outdoor_pos = (self.camera.pos.x, self.camera.pos.y)
        self.current_interior = self.interiors[room_id]
        sx, sy = self.current_interior.spawn_pos
        self.camera.pos.x = sx
        self.camera.pos.y = sy
        self.camera.set_direction(-math.pi / 2.0)  # Face North inside room
        self.hud.set_notification(f"ENTERED {self.current_interior.name} // [E] TO EXIT", 3.0)
        self.sound_system.play_beep()

    def _exit_interior(self):
        if self.current_interior:
            self.current_interior = None
            self.camera.pos.x = self.saved_outdoor_pos[0]
            self.camera.pos.y = self.saved_outdoor_pos[1]
            self.camera.set_direction(math.pi / 2.0)
            self.hud.set_notification("RETURNED TO ASTRA METROPOLIS STREETS", 2.5)
            self.sound_system.play_beep()

    def _update_demo_camera(self, dt: float):
        """Smooth autonomous city tour for demo mode."""
        self.demo_timer += dt
        self.camera.move_forward(dt, is_sprinting=False, world_map=self.city_map)
        ix = int(self.camera.pos.x)
        iy = int(self.camera.pos.y)
        if (ix, iy) in self.city_map.traffic_lights:
            self.camera.rotate(0.3 * dt)
        else:
            self.camera.rotate(math.sin(self.demo_timer * 0.5) * 0.15 * dt)

    def _update_simulation(self, dt: float):
        active_map = self.current_interior if self.current_interior else self.city_map
        self.camera.update_physics(dt, active_map)
        self.city_map.update(dt)
        self.traffic.update(dt)
        self.day_night.update(dt)
        self.weather.update(dt, self.screen_w, self.screen_h)
        self.sound_system.update(dt)
        self.hud.update(dt)

        # Update interaction prompt
        self.current_prompt = None
        if not self.camera.is_driving and not self.active_dialogue:
            if self.current_interior:
                if math.hypot(self.camera.pos.x - self.current_interior.exit_pos[0],
                              self.camera.pos.y - self.current_interior.exit_pos[1]) <= 2.0:
                    self.current_prompt = f"[E] EXIT {self.current_interior.name}"
            else:
                nearby_v = self.traffic.get_nearby_vehicle(self.camera.pos.x, self.camera.pos.y)
                if nearby_v:
                    self.current_prompt = f"[F] DRIVE VEHICLE ({nearby_v.vtype.value})"
                else:
                    portal = self.city_map.get_nearby_portal(self.camera.pos.x, self.camera.pos.y)
                    if portal:
                        self.current_prompt = f"[E] ENTER {portal.name} {portal.icon}"
                    else:
                        nearby_npc = self.traffic.get_nearby_npc(self.camera.pos.x, self.camera.pos.y)
                        if nearby_npc:
                            self.current_prompt = f"[E] TALK TO {nearby_npc.name} ({nearby_npc.title})"

    def _render_frame(self):
        self.buffer.clear()
        
        if self.current_interior:
            active_map = self.current_interior
            sprites = list(self.current_interior.props)
        else:
            active_map = self.city_map
            sprites = self.traffic.get_all_sprites_for_camera(self.camera.pos.x, self.camera.pos.y)

        # 3D Raycasting & projection
        self.raycaster.render(
            camera=self.camera,
            city_map=active_map,
            sprites=sprites,
            day_night=self.day_night,
            buffer=self.buffer
        )

        # HUD & Overlays
        self.hud.render(
            camera=self.camera,
            city_map=active_map,
            sprites=sprites,
            day_night=self.day_night,
            weather=self.weather,
            sound_system=self.sound_system,
            fps=self.fps,
            prompt_text=self.current_prompt,
            active_dialogue=self.active_dialogue,
            buffer=self.buffer
        )
