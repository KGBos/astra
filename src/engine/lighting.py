"""
Dynamic point-light engine for Astra 3D.

Collects emissive world objects (streetlamps, neon signs, vehicle head/
taillights, glowing props) into a small set of per-frame point lights with
quadratic falloff, consumed by the wall slicer (per-column), the floor
caster (per-row culled, incrementally sampled) and the wet-road reflection
pass.

Design notes (research-guided):
- Falloff uses squared distance with NO sqrt: fall = (1 - d2/r2)^2, the
  standard cheap game attenuation (pvigier / lodev style).
- Lights are culled to the nearest MAX_ACTIVE around the camera, then
  further per-row by an infinite-line distance test inside the floor caster,
  so typical per-pixel cost touches only 0-3 lights.
"""

import math
from typing import List, Optional, Tuple


class PointLight:
    __slots__ = ('x', 'y', 'radius', 'radius2', 'r', 'g', 'b', 'intensity')

    def __init__(self, x: float, y: float, color: Tuple[int, int, int],
                 radius: float, intensity: float):
        self.x = x
        self.y = y
        self.radius = radius
        self.radius2 = radius * radius
        self.r = float(color[0])
        self.g = float(color[1])
        self.b = float(color[2])
        self.intensity = intensity

    def falloff(self, dx: float, dy: float) -> float:
        """Quadratic attenuator from squared distance (no sqrt)."""
        d2 = dx * dx + dy * dy
        if d2 >= self.radius2:
            return 0.0
        f = 1.0 - d2 / self.radius2
        return f * f


# name -> (glow color, radius m, intensity). Matched by substring so
# variants ("CAR", "POLICE_CAR", ...) share profiles.
_LIGHT_PROFILES = (
    ("STREETLAMP", (255, 183, 90), 10.0, 1.15),
    ("NEON_SIGN", (255, 60, 180), 6.5, 0.85),
    ("FOUNTAIN", (90, 200, 255), 5.5, 0.65),
    ("OBELISK", (0, 240, 255), 6.5, 0.75),
    ("VENDING_MACHINE", (90, 220, 255), 4.5, 0.70),
    ("CAR", (255, 210, 120), 7.5, 0.90),
)

_GENERIC_PROFILE = ((255, 200, 140), 5.0, 0.60)


def collect_lights(sprites: List, cam_x: float, cam_y: float,
                   max_lights: int = 12, cull_dist: float = 32.0) -> List[PointLight]:
    """Builds the active point-light set from visible luminous sprites."""
    cull2 = cull_dist * cull_dist
    found: List[Tuple[float, PointLight]] = []
    for spr in sprites:
        if not getattr(spr, 'is_luminous', False):
            continue
        dx = spr.x - cam_x
        dy = spr.y - cam_y
        d2 = dx * dx + dy * dy
        if d2 > cull2:
            continue

        profile = None
        for key, color, radius, inten in _LIGHT_PROFILES:
            if key in spr.name:
                profile = (color, radius, inten)
                break
        if profile is None:
            # Data-driven fallback: sample the sprite's brightest top texel
            try:
                row = spr.fg_colors[0]
                col = row[len(row) // 2]
                mx = max(col)
                if mx > 40:
                    scale = 1.0 / max(1, mx)
                    profile = ((int(col[0] * scale * 255),
                                int(col[1] * scale * 255),
                                int(col[2] * scale * 255)), 5.0, min(1.0, mx / 255.0))
                else:
                    profile = _GENERIC_PROFILE
            except Exception:
                profile = _GENERIC_PROFILE

        color, radius, inten = profile
        found.append((d2, PointLight(spr.x, spr.y, color, radius, inten)))

    found.sort(key=lambda item: item[0])
    lights = [light for _, light in found[:max_lights]]
    return lights


def make_player_headlight(camera) -> Optional[PointLight]:
    """Warm forward pool of light when the player toggles high beams."""
    if not getattr(camera, 'headlights_on', False):
        return None
    px = camera.pos.x + camera.dir.x * 5.0
    py = camera.pos.y + camera.dir.y * 5.0
    return PointLight(px, py, (255, 240, 190), 11.0, 1.05)


def strongest_light_at(lights: List[PointLight], wx: float, wy: float) -> Tuple[float, float, float]:
    """Combined RGB contribution [0..255-scale floats] at a world point."""
    lr = lg = lb = 0.0
    for light in lights:
        fall = light.falloff(wx - light.x, wy - light.y)
        if fall > 0.0:
            k = fall * light.intensity
            lr += light.r * k
            lg += light.g * k
            lb += light.b * k
    return (lr, lg, lb)
