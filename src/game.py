"""
Main Game Engine loop, state management, vehicle driving, NPC conversations,
and autonomous demo mode for Astra 3D.
"""

import math
import random
import time
from typing import Optional

from src.engine.camera import Camera
from src.engine.raycaster import Raycaster
from src.world.city_map import CityMap
from src.world import interiors as interiors_mod
from src.world.day_night import DayNightCycle
from src.world.weather import WeatherSystem, WeatherType
from src.entities.traffic_manager import TrafficManager
from src.entities.pedestrian_manager import PedestrianManager
from src.entities.vehicle_controller import VehicleController
from src.audio.soundscape import SoundscapeManager
from src.renderer.screen_buffer import ScreenBuffer
from src.renderer.hud import HUD
from src.renderer.cockpit_hud import CockpitHUD
from src.renderer.terminal import TerminalManager
from src.input.keyboard import KeyboardController, KeyAction


# Demo/benchmark city. `CityMap()` with seed=None draws randint(100000, 999999)
# every Game() construction, so the CI 160x50 floor was a lottery: same T-08
# tree measured 29.6 / 30.5 / 40.1 FPS across Actions runs with no engine
# change. Same-seed T-08 vs master keeps fleet size (e.g. seed 5 → 43
# vehicles, 40 peds) and frame time within ~2 FPS; the swing is the random
# city. Seed 5 is T-02's city seed and sat at median complexity in a 6-seed
# local sample — not the cheapest layout.
DEMO_CITY_SEED = 5


class Game:
    def __init__(
        self,
        width: int = 80,
        height: int = 32,
        target_fps: int = 30,
        use_color: bool = True,
        use_background: bool = True,
        demo_mode: bool = False,
        use_audio: bool = False,
        seed: Optional[int] = None,
    ):
        self.target_fps = target_fps
        self.frame_time = 1.0 / target_fps
        # Hybrid limiter spin window: proportional to the frame budget so the
        # busy-wait slice absorbs macOS timer-coalescing oversleep (wakeups
        # quantize to ~2.5ms scheduler ticks, so the window must clear one
        # tick plus slack) without burning a growing CPU share at high targets
        self._spin_window = min(0.005, max(0.0008, self.frame_time * 0.15))
        self.running = False
        self.demo_mode = demo_mode
        self.demo_timer = 0.0

        # Subsystems
        self.terminal = TerminalManager()
        self.keyboard = KeyboardController()
        # Mute-default per roadmap NEXT.4: opt in with --audio or the V key
        self.soundscape = SoundscapeManager(enabled=use_audio)

        # World & Camera (CityMap default is a 320x320 m metropolis).
        # Demo/benchmark pins DEMO_CITY_SEED so the 30 FPS floor measures a
        # known world; interactive play still draws a random recorded seed.
        if seed is None and demo_mode:
            seed = DEMO_CITY_SEED
        self.city_map = CityMap(seed=seed)
        # Spawn player in Cyber-Downtown near avenue
        self.camera = Camera(x=12.5, y=6.5, fov_deg=70.0)
        self.camera.set_direction(math.pi / 2.0)  # Face South (+Y) down avenue
        self.camera.pos.x, self.camera.pos.y = self.city_map.spawn_pos

        # Cycle C density retune: None lets each manager derive population
        # from measured lane length / district walkable area
        self.vehicle_count = None
        self.pedestrian_count = None
        self.traffic = TrafficManager(self.city_map, vehicle_count=self.vehicle_count)
        self.pedestrians = PedestrianManager(self.city_map,
                                             pedestrian_count=self.pedestrian_count)
        self.day_night = DayNightCycle(start_hour=22.5, time_speed=0.4)
        self.weather = WeatherSystem(weather=WeatherType.CLEAR)

        # Driving mode (single controller module for the whole game)
        self.vehicle_ctrl = VehicleController()
        self.cockpit_hud = CockpitHUD()
        self._throttle = 0.0
        self._steer_input = 0.0
        self._nitro_request = False

        # Rendering
        self.screen_w = width
        self.screen_h = height
        self.buffer = ScreenBuffer(width, height, use_color=use_color, use_background=use_background)
        self.raycaster = Raycaster(width, height)
        self.hud = HUD(show_minimap=True)

        # Player space: None = street, else InteriorView while inside a building
        self.interior_view = None

        # Interaction & dialogue state (NPC conversations)
        self.current_prompt: Optional[str] = None
        self.active_dialogue: Optional[dict] = None

        # Performance metrics
        self.fps = float(target_fps)
        self.frame_count = 0
        self.total_frames = 0
        self.last_fps_calc = time.monotonic()

    def regenerate_city(self, seed=None) -> None:
        """Rebuilds the procedural city, traffic, and pedestrians for a given seed (random if None)."""
        if seed is None:
            seed = random.randint(100000, 999999)
        self.interior_view = None
        self.active_dialogue = None
        if self.vehicle_ctrl.is_driving:
            self.vehicle_ctrl.exit_vehicle(self.camera)
        self.city_map = CityMap(width=self.city_map.width, height=self.city_map.height, seed=seed)
        self.traffic = TrafficManager(self.city_map, vehicle_count=self.vehicle_count)
        self.pedestrians = PedestrianManager(self.city_map,
                                             pedestrian_count=self.pedestrian_count)
        self.camera.pos.x, self.camera.pos.y = self.city_map.spawn_pos

    def _active_map(self):
        """World queried by player-facing systems (camera physics + raycaster)."""
        return self.interior_view if self.interior_view is not None else self.city_map

    def _update_space(self):
        """Walk-through doorways: street <-> building interior transitions."""
        cam = self.camera
        if self.interior_view is None:
            nearest, dist = self._nearest_doorway()
            if nearest and dist <= interiors_mod.ENTER_RADIUS:
                _, view = self.city_map.get_interior(nearest)
                self.interior_view = view
                cam.pos.x, cam.pos.y = view.space.inner_door_world
                # Step one cell deeper so we don't re-trigger the exit instantly
                cx = view.space.x0 + view.space.w / 2.0
                cy = view.space.y0 + view.space.h / 2.0
                ndx, ndy = cam.pos.x - cx, cam.pos.y - cy
                nl = max(0.001, math.hypot(ndx, ndy))
                step = 1.1 / nl
                tx, ty = cam.pos.x + ndx * step, cam.pos.y + ndy * step
                if not view.is_solid(tx, ty):
                    cam.pos.x, cam.pos.y = tx, ty
                theme = view.space.theme
                self.hud.set_notification(f"ENTERED {theme.icon} {theme.name} // WINDOWS ARE LIVE")
                self.soundscape.play("chime")
        else:
            space = self.interior_view.space
            wx, wy = space.inner_door_world
            if math.hypot(cam.pos.x - wx, cam.pos.y - wy) <= interiors_mod.EXIT_RADIUS:
                doorway = space.doorway
                ox, oy = ((1, 0), (0, 1), (-1, 0), (0, -1))[doorway.side]
                self.interior_view = None
                cam.pos.x = doorway.ext[0] + 0.5 + ox * 0.9
                cam.pos.y = doorway.ext[1] + 0.5 + oy * 0.9
                self.hud.set_notification("BACK ON THE STREET")
                self.soundscape.play("chime")

    def _nearest_doorway(self):
        """(doorway, center_distance) of the closest entrance, or (None, inf)."""
        best, best_d = None, float('inf')
        for d in self.city_map.doorways:
            dist = math.hypot(self.camera.pos.x - (d.ext[0] + 0.5),
                              self.camera.pos.y - (d.ext[1] + 0.5))
            if dist < best_d:
                best, best_d = d, dist
        return best, best_d

    def run(self, max_frames: Optional[int] = None):
        """Starts the main game loop."""
        self.running = True

        with self.terminal:
            tw, th = self.terminal.get_size()
            self._resize_viewport(tw, th)

            last_time = time.monotonic()

            while self.running:
                loop_start = time.monotonic()
                dt = min(0.1, loop_start - last_time)
                last_time = loop_start

                # 1. Handle Terminal Resize Event
                if self.terminal.resized:
                    self.terminal.resized = False
                    tw, th = self.terminal.get_size()
                    self._resize_viewport(tw, th)

                # 1.5 Walk-through doorway transitions (street <-> interiors)
                self._update_space()

                # 2. Input Processing
                self._process_input(dt)

                # 3. Update Simulation
                self._update_simulation(dt)

                # 4. Render Frame
                self._render_frame()

                # 5. Flush to Terminal (dirty-region delta; '' = nothing changed)
                frame_str = self.buffer.render_frame_delta()
                self.terminal.flush_frame(frame_str)

                # 6. FPS Calculation
                self.frame_count += 1
                self.total_frames += 1
                now = time.monotonic()
                if now - self.last_fps_calc >= 0.5:
                    self.fps = self.frame_count / (now - self.last_fps_calc)
                    self.frame_count = 0
                    self.last_fps_calc = now

                # 7. Frame Limiter: coarse sleep, then short spin for a
                # locked framerate immune to OS scheduler oversleep jitter
                deadline = loop_start + self.frame_time
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    if remaining > self._spin_window:
                        time.sleep(remaining - self._spin_window)
                    while time.monotonic() < deadline:
                        pass

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
            self.keyboard.poll_input()
            if self.keyboard.has_event(KeyAction.QUIT):
                self.running = False
            return

        self.keyboard.poll_input()

        # Exit (Escape backs out of a conversation first)
        if self.keyboard.has_event(KeyAction.QUIT):
            if self.active_dialogue:
                self.active_dialogue = None
            else:
                self.running = False
            return

        # NPC Dialogue interaction mode: number keys pick questions
        if self.active_dialogue:
            # Drain buffered drag deltas so they don't jerk the camera
            # the moment the conversation closes
            self.keyboard.pop_mouse_delta()
            if self.keyboard.has_event(KeyAction.JUMP):
                self.active_dialogue = None
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
                self.soundscape.play_beep()
            return

        # Vehicle enter / exit
        if self.keyboard.has_event(KeyAction.ENTER_EXIT_VEHICLE):
            if self.vehicle_ctrl.is_driving:
                self.vehicle_ctrl.exit_vehicle(self.camera)
                self.hud.set_notification("EXITED VEHICLE // WALKING MODE", 2.0)
                self.soundscape.play("chime")
            else:
                mounted = self.vehicle_ctrl.try_enter_nearest_vehicle(
                    self.camera, self.traffic.vehicles)
                if mounted:
                    self.hud.set_notification(
                        f"DRIVING [{mounted.vtype.value}] // [W] ACCEL [A/D] STEER [SHIFT] NITRO", 3.0)
                    self.soundscape.play("rev")

        # Radio tuning
        if self.keyboard.has_event(KeyAction.TOGGLE_RADIO):
            station = self.soundscape.next_station()
            self.hud.set_notification(f"TUNED RADIO // {station.freq} {station.name}", 2.5)
            self.soundscape.play_beep()

        # Master audio mute toggle (V for Volume)
        if self.keyboard.has_event(KeyAction.TOGGLE_AUDIO):
            audio_on = self.soundscape.toggle_mute()
            self.hud.set_notification(f"AUDIO // {'ON' if audio_on else 'OFF'}", 2.0)

        # Headlight toggle (driving ambience; beam cone follows the camera)
        if self.keyboard.has_event(KeyAction.TOGGLE_LIGHTS):
            self.camera.headlights_on = not self.camera.headlights_on
            self.hud.set_notification(f"LIGHTS: {'HIGH BEAMS ON' if self.camera.headlights_on else 'OFF'}", 2.0)

        # Interaction: NPC conversation, else ambient pedestrian quote
        if self.keyboard.has_event(KeyAction.INTERACT) and not self.vehicle_ctrl.is_driving:
            nearby_npc = self.traffic.get_nearby_npc(self.camera.pos.x, self.camera.pos.y)
            if nearby_npc:
                self.active_dialogue = {
                    "name": nearby_npc.name,
                    "title": nearby_npc.title,
                    "response": nearby_npc.dialogue[0].response if nearby_npc.dialogue else "Hello traveler!",
                    "options": nearby_npc.dialogue
                }
                self.soundscape.play_beep()
            else:
                talk_res = self.pedestrians.interact_with_focused(self.camera.pos.x, self.camera.pos.y, self.camera.dir.x, self.camera.dir.y)
                if talk_res:
                    archetype, quote = talk_res
                    arch_name = archetype.replace('_', ' ').title()
                    self.hud.set_notification(f"[{arch_name}]: \"{quote}\"", duration=4.5)

        # Movement (walking only; driving input is collected below)
        self._throttle = 0.0
        self._steer_input = 0.0
        self._nitro_request = False
        if self.vehicle_ctrl.is_driving:
            if self.keyboard.is_action_active(KeyAction.MOVE_FORWARD):
                self._throttle = 1.0
                self._nitro_request = self.keyboard.is_action_active(KeyAction.SPRINT)
            elif self.keyboard.is_action_active(KeyAction.MOVE_BACKWARD):
                self._throttle = -1.0
            if self.keyboard.is_action_active(KeyAction.STRAFE_LEFT):
                self._steer_input = -1.0
            elif self.keyboard.is_action_active(KeyAction.STRAFE_RIGHT):
                self._steer_input = 1.0
        else:
            is_sprint = self.keyboard.is_action_active(KeyAction.SPRINT)
            if self.keyboard.is_action_active(KeyAction.MOVE_FORWARD):
                self.camera.move_forward(dt, is_sprint, self._active_map())
            elif self.keyboard.is_action_active(KeyAction.MOVE_BACKWARD):
                self.camera.move_backward(dt, is_sprint, self._active_map())

            if self.keyboard.is_action_active(KeyAction.STRAFE_LEFT):
                self.camera.strafe_left(dt, self._active_map())
            elif self.keyboard.is_action_active(KeyAction.STRAFE_RIGHT):
                self.camera.strafe_right(dt, self._active_map())

            # Turning
            if self.keyboard.is_action_active(KeyAction.TURN_LEFT):
                self.camera.rotate(-self.camera.rot_speed * dt)
            elif self.keyboard.is_action_active(KeyAction.TURN_RIGHT):
                self.camera.rotate(self.camera.rot_speed * dt)

        # Mouse look: drag deltas rotate instantly, wheel nudges pitch
        mdx, mdy = self.keyboard.pop_mouse_delta()
        if mdx != 0:
            self.camera.rotate(mdx * 0.045)
        if mdy != 0:
            self.camera.pitch_look(-mdy * 1.2)
        if self.keyboard.has_event(KeyAction.WHEEL_UP):
            self.camera.pitch_look(2.0)
        elif self.keyboard.has_event(KeyAction.WHEEL_DOWN):
            self.camera.pitch_look(-2.0)

        # Pitch
        if not self.vehicle_ctrl.is_driving:
            if self.keyboard.is_action_active(KeyAction.LOOK_UP):
                self.camera.pitch_look(12.0 * dt)
            elif self.keyboard.is_action_active(KeyAction.LOOK_DOWN):
                self.camera.pitch_look(-12.0 * dt)

            if self.keyboard.has_event(KeyAction.JUMP):
                self.camera.jump()

        # Actions & System Toggles
        if self.keyboard.has_event(KeyAction.TOGGLE_MAP):
            self.hud.cycle_minimap()
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
        if self.keyboard.has_event(KeyAction.HONK_HORN):
            self.pedestrians.alert_nearby(self.camera.pos.x, self.camera.pos.y)
            self.soundscape.play("horn")
            self.hud.set_notification("HONK! CITIZENS & CARS ALERTED", duration=2.0)

    def _update_demo_camera(self, dt: float):
        """Smooth autonomous city tour for demo mode."""
        self.demo_timer += dt
        # Move forward automatically along road grid
        self.camera.move_forward(dt, is_sprinting=False, world_map=self._active_map())

        # Slowly sweep camera yaw and turn at intersections
        ix = int(self.camera.pos.x)
        iy = int(self.camera.pos.y)
        if (ix, iy) in self.city_map.traffic_lights:
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
        self.soundscape.update_radio(dt)

        # Driving physics stay on the single vehicle controller module
        if self.vehicle_ctrl.is_driving:
            collided = self.vehicle_ctrl.update_physics(
                dt=dt,
                throttle=self._throttle,
                steer_input=self._steer_input,
                camera=self.camera,
                city_map=self.city_map,
                other_vehicles=self.traffic.vehicles,
                nitro=self._nitro_request
            )
            if collided:
                self.soundscape.play("thud")

        is_raining = self.weather.current_weather in (WeatherType.RAIN, WeatherType.STORM, WeatherType.ACID_RAIN)
        self.cockpit_hud.update(dt, is_raining=is_raining)

        # Check focused pedestrian for interaction prompt
        focused_ped = self.pedestrians.get_focused_pedestrian(self.camera.pos.x, self.camera.pos.y, self.camera.dir.x, self.camera.dir.y)
        if focused_ped and not self.vehicle_ctrl.is_driving:
            self.hud.interaction_prompt = f"[E] Talk with {focused_ped.archetype.value.replace('_', ' ').title()}"
        else:
            self.hud.interaction_prompt = None

        # Contextual center prompt (drive / talk)
        self.current_prompt = None
        if not self.vehicle_ctrl.is_driving and not self.active_dialogue and self.interior_view is None:
            nearby_v = self.traffic.get_nearby_vehicle(self.camera.pos.x, self.camera.pos.y)
            if nearby_v:
                self.current_prompt = f"[F] DRIVE VEHICLE ({nearby_v.vtype.value})"
            else:
                nearby_npc = self.traffic.get_nearby_npc(self.camera.pos.x, self.camera.pos.y)
                if nearby_npc:
                    self.current_prompt = f"[E] TALK TO {nearby_npc.name} ({nearby_npc.title})"

        self.hud.update(dt, weather=self.weather)

    def _render_frame(self):
        self.buffer.clear()

        # Collect dynamic sprites (traffic vehicles, static props, pedestrians,
        # and themed furniture while inside a building)
        sprites = self.traffic.get_all_sprites_for_camera(self.camera.pos.x, self.camera.pos.y) + \
                  self.pedestrians.get_all_sprites_for_camera(self.camera.pos.x, self.camera.pos.y)
        if self.interior_view is not None:
            sprites = list(self.interior_view.props) + sprites

        # 3D Raycasting & projection
        self.raycaster.render(
            camera=self.camera,
            city_map=self._active_map(),
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
            soundscape=self.soundscape,
            fps=self.fps,
            prompt_text=self.current_prompt,
            active_dialogue=self.active_dialogue,
            buffer=self.buffer
        )

        # First-person cockpit dashboard takes over while driving
        is_raining = self.weather.current_weather in (WeatherType.RAIN, WeatherType.STORM, WeatherType.ACID_RAIN)
        self.cockpit_hud.render(self.vehicle_ctrl, self.buffer, is_raining=is_raining)
