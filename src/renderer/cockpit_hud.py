"""
First-Person Vehicle Cockpit Dashboard, Dynamic Steering Wheel & Instruments for Astra 3D.
Author: Valerie Sterling ⚡ (3D Raycaster & Rasterization Specialist)
"""

import math
from typing import List, Optional
from src.entities.vehicle_controller import VehicleController
from src.entities.car import VehicleType, Vehicle
from src.renderer.screen_buffer import ScreenBuffer


class CockpitHUD:
    """Renders retro-cyberpunk first-person vehicle dashboard and controls overlay."""

    def __init__(self):
        self.wiper_phase = 0.0
        self.siren_tick = 0.0

    def update(self, dt: float, is_raining: bool):
        if is_raining:
            self.wiper_phase = (self.wiper_phase + dt * 3.5) % (math.pi * 2.0)
        self.siren_tick += dt * 8.0

    def render(
        self,
        vehicle_ctrl: VehicleController,
        buffer: ScreenBuffer,
        is_raining: bool = False
    ):
        if not vehicle_ctrl.is_driving or vehicle_ctrl.current_vehicle is None:
            return

        w = buffer.width
        h = buffer.height
        v = vehicle_ctrl.current_vehicle

        # 1. Windshield Wipers during rain/storm
        if is_raining:
            wiper_angle = math.sin(self.wiper_phase)  # [-1.0, 1.0]
            wiper_x = int(w * 0.5 + wiper_angle * (w * 0.25))
            for y in range(max(2, h - 14), h - 6):
                buffer.set_pixel(wiper_x, y, '/', (180, 200, 220), None)

        # 2. Lower Dashboard Bar (bottom 5 rows)
        dash_h = 5
        dash_y0 = max(0, h - dash_h)

        # Primary dash theme colors based on vehicle type
        if v.vtype == VehicleType.POLICE:
            dash_border_col = (40, 60, 140)
            dash_bg_col = (10, 15, 30)
            if vehicle_ctrl.siren_active:
                # Emergency light flash reflection on dashboard
                is_red = int(self.siren_tick) % 2 == 0
                strobe_tint = (50, 10, 15) if is_red else (10, 20, 60)
                dash_bg_col = strobe_tint
        elif v.vtype == VehicleType.TAXI:
            dash_border_col = (200, 180, 40)
            dash_bg_col = (25, 22, 15)
        elif v.vtype == VehicleType.CYBER_SEDAN:
            dash_border_col = (0, 220, 255)
            dash_bg_col = (12, 20, 30)
        else:
            dash_border_col = (100, 130, 160)
            dash_bg_col = (18, 22, 28)

        # Fill Dashboard Background
        for y in range(dash_y0, h):
            for x in range(w):
                char = '═' if y == dash_y0 else ' '
                fg = dash_border_col if y == dash_y0 else None
                buffer.set_pixel(x, y, char, fg, dash_bg_col)

        # 3. Dynamic Rotating Steering Wheel (Centered)
        steer = vehicle_ctrl.steering_angle
        if steer < -0.35:
            wheel_str = r" ╔══\\====//══╗ "
            wheel_center = r" ║  ◄ LEFT   ║ "
        elif steer > 0.35:
            wheel_str = r" ╔══//====\\══╗ "
            wheel_center = r" ║   RIGHT ► ║ "
        else:
            wheel_str = r" ╔════════════╗ "
            wheel_center = r" ║  ▲ CENTER  ║ "

        cx = max(0, (w - 16) // 2)
        if dash_y0 + 1 < h:
            buffer.draw_string(cx, dash_y0 + 1, wheel_str, (240, 240, 255), dash_bg_col)
        if dash_y0 + 2 < h:
            buffer.draw_string(cx, dash_y0 + 2, wheel_center, (0, 240, 255), dash_bg_col)

        # 4. Left Instrument Cluster (Speedometer & Gear)
        speed_mph = int(abs(vehicle_ctrl.speed) * 9.5)
        gear = vehicle_ctrl.gear
        gear_display = f"[P] [{'R*' if gear == 'R' else 'R'}] [N] [{'D*' if gear == 'D' else 'D'}]"
        speed_bars = "█" * int(min(12, speed_mph // 5))

        if dash_y0 + 1 < h:
            buffer.draw_string(2, dash_y0 + 1, f"SPEED: {speed_mph:02d} MPH [{speed_bars:<12}]", (0, 255, 200), dash_bg_col)
        if dash_y0 + 2 < h:
            buffer.draw_string(2, dash_y0 + 2, f"GEAR : {gear_display}  VEHICLE: {v.vtype.value}", (255, 220, 80), dash_bg_col)

        # 5. Right Instrument Cluster (Tachometer RPM & Sirens)
        rpm_val = int(vehicle_ctrl.rpm)
        rpm_bars = "█" * int(min(10, rpm_val // 700))
        siren_status = "SIREN: [ON]" if vehicle_ctrl.siren_active else "SIREN: [OFF]"

        right_x = max(0, w - 34)
        if dash_y0 + 1 < h:
            buffer.draw_string(right_x, dash_y0 + 1, f"RPM : [{rpm_bars:<10}] {rpm_val:4d}", (255, 120, 50), dash_bg_col)
        if dash_y0 + 2 < h:
            siren_col = (255, 60, 60) if vehicle_ctrl.siren_active else (150, 160, 180)
            buffer.draw_string(right_x, dash_y0 + 2, f"{siren_status} │ [E] Exit Car", siren_col, dash_bg_col)
