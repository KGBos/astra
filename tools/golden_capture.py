#!/usr/bin/env python3
"""
Golden-frame regression harness for Astra 3D (TASKBOARD ticket T-02).

Renders a fixed matrix of scenarios -- seed, camera pose, time of day, weather,
viewport, render mode -- through the real Raycaster into deterministic
framebuffer digests. The digests (plus zlib-compressed cell data for readable
diffing) live in `tests/golden/manifest.json` and are locked by
`tests/test_golden_frames.py`, so any refactor that changes a single pixel of
any locked scenario fails the suite loudly.

Determinism contract
--------------------
* The city grid comes from the already-seeded procedural generator.
* Every scenario seeds the global `random` module for its ENTIRE build -- city,
  weather particles, traffic/pedestrian managers, fixed-dt simulation steps and
  the render itself -- then restores the caller's RNG state. This matters
  because entity modules draw from the module-level RNG (T-08 will fix that)
  and no engine code seeds it.
* Time of day is frozen: `DayNightCycle` is constructed at a fixed hour and
  never advanced with wall-clock deltas.
* Simulation stepping (rain fall, traffic, pedestrians, driving physics) uses
  fixed-dt updates only -- no `time.monotonic()` anywhere in the capture path.

Usage
-----
    python3 tools/golden_capture.py                 # verify against goldens
    python3 tools/golden_capture.py --regenerate    # recapture after an
                                                    # INTENTIONAL visual change
    python3 tools/golden_capture.py --scenario rain-night-blocks-160x50
    python3 tools/golden_capture.py --list

Scenario matrix (10 cells)
--------------------------
day/night x clear/rain/fog x interior/driving/street-life x
blocks / ascii-color / ascii-mono x 80x32 / 160x50.
"""

import argparse
import base64
import hashlib
import json
import math
import os
import random
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.engine.camera import Camera
from src.engine.raycaster import Raycaster
from src.renderer.cockpit_hud import CockpitHUD
from src.renderer.screen_buffer import ScreenBuffer
from src.entities.pedestrian_manager import PedestrianManager
from src.entities.sprite import make_neon_signpost_sprite, make_streetlamp_sprite
from src.entities.traffic_manager import TrafficManager
from src.entities.vehicle_controller import VehicleController
from src.world.city_map import CityMap
from src.world.day_night import DayNightCycle
from src.world.weather import WeatherSystem, WeatherType

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN_MANIFEST = os.path.join(REPO_ROOT, "tests", "golden", "manifest.json")

# One seed for everything stochastic outside the city generator. Bump this and
# the whole matrix changes; do it only when entity placement must move.
SCENARIO_SEED = 20260824
CITY_SEED = 5          # same city as tools/render_snapshots.py
CITY_SIZE = 96         # metres; small enough to keep captures fast

# Render modes (ScreenBuffer flags). `blocks` = today's filled-cell look,
# `ascii-color` = coloured glyphs on the terminal background (--no-fill),
# `ascii-mono` = no colour at all (--no-color).
MODES = {
    "blocks": (True, True),
    "ascii-color": (True, False),
    "ascii-mono": (False, False),
}

FIXED_DT = 1.0 / 30.0   # simulation step for weather / driving
SIM_DT = 1.0 / 15.0     # simulation step for street-life entities


# --------------------------------------------------------------------------
# Cell serialization
# --------------------------------------------------------------------------

def _color_str(color):
    """Formats an RGB tuple canonically ('-' when absent)."""
    if color is None:
        return "-"
    return "%d,%d,%d" % (color[0], color[1], color[2])


def canonical_frame(buffer):
    """Serializes the framebuffer into one canonical string.

    Row-major, every cell contributes glyph \\x1f fg \\x1f bg \\x1e. Stable
    across runs and Python versions (no hashing of Python objects involved).

    Channels the buffer's render mode disables are masked to '-' so locked
    digests only track values the terminal actually paints: ascii-mono
    (use_color=False) masks foreground, and any mode without background fills
    (use_background=False) masks background.
    """
    show_fg = bool(getattr(buffer, "use_color", True))
    show_bg = bool(getattr(buffer, "use_background", True))
    parts = []
    for row in buffer.pixels:
        for px in row:
            parts.append(px.char)
            parts.append("\x1f")
            parts.append(_color_str(px.fg) if show_fg else "-")
            parts.append("\x1f")
            parts.append(_color_str(px.bg) if show_bg else "-")
            parts.append("\x1e")
    return "".join(parts)


def digest_frame(buffer):
    """sha256 hex digest of the canonical frame string."""
    return hashlib.sha256(canonical_frame(buffer).encode("utf-8")).hexdigest()


def pack_frame(canonical):
    """zlib + base64 payload for the manifest (enables readable diffs)."""
    blob = zlib.compress(canonical.encode("utf-8"), 9)
    return base64.b64encode(blob).decode("ascii")


def unpack_frame(frame_b64):
    """Inverse of pack_frame -> canonical frame string."""
    return zlib.decompress(base64.b64decode(frame_b64)).decode("utf-8")


def parse_canonical(canonical, width, height):
    """Canonical string -> {(x, y): (glyph, fg, bg)} with parsed colours."""
    cells = {}
    idx = 0
    fields = canonical.split("\x1e")
    for y in range(height):
        for x in range(width):
            glyph, fg_s, bg_s = fields[idx].split("\x1f")
            idx += 1
            fg = tuple(int(v) for v in fg_s.split(",")) if fg_s != "-" else None
            bg = tuple(int(v) for v in bg_s.split(",")) if bg_s != "-" else None
            cells[(x, y)] = (glyph, fg, bg)
    return cells


def diff_canonical(old_canonical, new_canonical, width, height, max_lines=20):
    """Human-readable diff between two canonical frames.

    Returns (changed_count, total_cells, [lines]) where lines pinpoint the
    first changed cells plus the rows most affected.
    """
    old_cells = parse_canonical(old_canonical, width, height)
    new_cells = parse_canonical(new_canonical, width, height)
    changed = []
    for key in sorted(old_cells.keys()):
        if old_cells[key] != new_cells[key]:
            changed.append(key)
    total = width * height

    lines = []
    for x, y in changed[:max_lines]:
        og, ofg, obg = old_cells[(x, y)]
        ng, nfg, nbg = new_cells[(x, y)]
        lines.append("  (%3d,%2d): %r fg=%s bg=%s  ->  %r fg=%s bg=%s" % (
            x, y, og, _color_str(ofg), _color_str(obg),
            ng, _color_str(nfg), _color_str(nbg)))
    if len(changed) > max_lines:
        lines.append("  ... and %d more changed cells" % (len(changed) - max_lines))

    if changed:
        rows = {}
        for _, y in changed:
            rows[y] = rows.get(y, 0) + 1
        worst = sorted(rows.items(), key=lambda kv: -kv[1])[:3]
        lines.append("  rows most affected: " + ", ".join(
            "y=%d (%d cells)" % (y, n) for y, n in worst))
    return len(changed), total, lines


# --------------------------------------------------------------------------
# Deterministic scene builders
# --------------------------------------------------------------------------

class _RngGuard(object):
    """Seeds the global RNG for a scenario and restores the caller's state."""

    def __enter__(self):
        self._state = random.getstate()
        random.seed(SCENARIO_SEED)
        return self

    def __exit__(self, *exc):
        random.setstate(self._state)
        return False


def _base_city():
    """Seeded city + camera posed at the spawn, facing east."""
    city_map = CityMap(width=CITY_SIZE, height=CITY_SIZE, seed=CITY_SEED)
    sx, sy = city_map.spawn_pos
    camera = Camera(x=sx, y=sy, fov_deg=70.0)
    camera.set_direction(math.pi / 2.0)
    return city_map, camera, sx, sy


def _emissive_street_props(sx, sy):
    """Guaranteed point lights ahead of the spawn (lamp pool + neon wash)."""
    return [
        make_streetlamp_sprite(sx + 1.5, sy + 7.0),
        make_neon_signpost_sprite(sx - 1.0, sy + 10.0),
    ]


def _weather(weather_type, width, height, steps, wetness=None):
    """Seeded weather settled at the viewport with fixed-dt steps."""
    weather = WeatherSystem()
    weather.set_weather(weather_type, width, height)
    if wetness is not None:
        weather.wetness = wetness
    for _ in range(steps):
        weather.update(FIXED_DT, width, height)
    return weather


def _render(width, height, mode, camera, scene_map, sprites,
            day_night, weather=None, flashlight_on=False, cockpit=None,
            vehicle_ctrl=None, is_raining=False):
    """One full deterministic frame through the real pipeline."""
    with _RngGuard():
        use_color, use_background = MODES[mode]
        buffer = ScreenBuffer(width, height, use_color=use_color,
                              use_background=use_background)
        raycaster = Raycaster(width, height)
        raycaster.render(camera=camera, city_map=scene_map, sprites=sprites,
                         day_night=day_night, buffer=buffer, weather=weather,
                         flashlight_on=flashlight_on)
        if cockpit is not None:
            cockpit.render(vehicle_ctrl, buffer, is_raining=is_raining)
        return buffer


# --- street scenarios ------------------------------------------------------

def _capture_street(name, width, height, mode, hour, weather_spec=None,
                    headlights=False):
    city_map, camera, sx, sy = _base_city()
    # Headlight state must be set BEFORE rendering: the raycaster reads it
    # mid-frame (ground light pools), so a post-render assignment is dead code.
    camera.headlights_on = headlights
    weather = None
    if weather_spec is not None:
        weather_type, settle_steps, wetness = weather_spec
        weather = _weather(weather_type, width, height, settle_steps, wetness)
    sprites = _emissive_street_props(sx, sy)
    buffer = _render(width, height, mode, camera, city_map, sprites,
                     DayNightCycle(start_hour=hour), weather=weather,
                     flashlight_on=False)
    return name, buffer


def _capture_interior(name, width, height, mode, hour):
    city_map, camera, sx, sy = _base_city()
    if not city_map.doorways:
        raise RuntimeError("city has no doorways; cannot capture interior")
    door = min(city_map.doorways,
               key=lambda d: math.hypot(d.ext[0] + 0.5 - sx, d.ext[1] + 0.5 - sy))
    _, view = city_map.get_interior(door)

    # Mirror the game's enter transition: place the eye just inside the door,
    # then step one cell deeper so the doorway frame is behind us.
    camera.pos.x, camera.pos.y = view.space.inner_door_world
    cx = view.space.x0 + view.space.w / 2.0
    cy = view.space.y0 + view.space.h / 2.0
    ndx, ndy = camera.pos.x - cx, camera.pos.y - cy
    nl = max(0.001, math.hypot(ndx, ndy))
    step = 1.1 / nl
    tx, ty = camera.pos.x + ndx * step, camera.pos.y + ndy * step
    if not view.is_solid(tx, ty):
        camera.pos.x, camera.pos.y = tx, ty
    camera.set_direction(math.atan2(cy - camera.pos.y, cx - camera.pos.x))

    buffer = _render(width, height, mode, camera, view, list(view.props),
                     DayNightCycle(start_hour=hour))
    return name, buffer


def _capture_driving(name, width, height, mode, hour):
    city_map, camera, sx, sy = _base_city()
    traffic = TrafficManager(city_map)
    if not traffic.vehicles:
        raise RuntimeError("traffic manager produced no vehicles")

    # Board whichever vehicle spawned closest to the player spawn.
    vehicle = min(traffic.vehicles,
                  key=lambda v: math.hypot(v.x - sx, v.y - sy))
    ctrl = VehicleController()
    ctrl.enter_vehicle(vehicle, camera)

    # Fixed-dt straight-line drive so the dashboard shows real motion.
    cockpit = CockpitHUD()
    for _ in range(60):
        traffic.update(FIXED_DT)
        ctrl.update_physics(FIXED_DT, throttle=0.8, steer_input=0.0,
                            camera=camera, city_map=city_map,
                            other_vehicles=traffic.vehicles)
    cockpit.update(FIXED_DT, is_raining=False)

    sprites = traffic.get_all_sprites_for_camera(camera.pos.x, camera.pos.y)
    buffer = _render(width, height, mode, camera, city_map, sprites,
                     DayNightCycle(start_hour=hour), cockpit=cockpit,
                     vehicle_ctrl=ctrl, is_raining=False)
    return name, buffer


def _capture_street_life(name, width, height, mode, hour):
    city_map, camera, sx, sy = _base_city()
    traffic = TrafficManager(city_map)
    pedestrians = PedestrianManager(city_map)

    # Let the city breathe for four simulated seconds under the seeded RNG.
    for _ in range(60):
        traffic.update(SIM_DT)
        pedestrians.update(SIM_DT)

    sprites = (_emissive_street_props(sx, sy)
               + traffic.get_all_sprites_for_camera(sx, sy)
               + pedestrians.get_all_sprites_for_camera(sx, sy))
    buffer = _render(width, height, mode, camera, city_map, sprites,
                     DayNightCycle(start_hour=hour))
    return name, buffer


# --------------------------------------------------------------------------
# Scenario matrix
# --------------------------------------------------------------------------
# Each entry: (name, width, height, mode, builder). The matrix must keep
# covering: day/night, clear/rain/fog, interior, driving, street life, all
# three render modes, and both standard viewports.

def _scenarios():
    return [
        # Day / clear / blocks / small viewport
        ("noon-clear-blocks-80x32", 80, 32, "blocks",
         lambda n, w, h, m: _capture_street(n, w, h, m, hour=12.0)),
        # Golden-hour clouds / blocks / small
        ("sunset-clouds-blocks-80x32", 80, 32, "blocks",
         lambda n, w, h, m: _capture_street(n, w, h, m, hour=18.5)),
        # Dusk fog over the skyline / blocks / large
        ("dusk-fog-blocks-160x50", 160, 50, "blocks",
         lambda n, w, h, m: _capture_street(
             n, w, h, m, hour=19.5,
             weather_spec=(WeatherType.FOGGY, 90, None))),
        # Night with lamp pools + neon wash / blocks / large
        ("night-lamps-blocks-160x50", 160, 50, "blocks",
         lambda n, w, h, m: _capture_street(n, w, h, m, hour=23.0)),
        # Rain at night, settled wetness / blocks / large
        ("rain-night-blocks-160x50", 160, 50, "blocks",
         lambda n, w, h, m: _capture_street(
             n, w, h, m, hour=23.2,
             weather_spec=(WeatherType.RAIN, 45, 0.9))),
        # ascii-color: glyphs carry the image, zero background fills
        ("noon-clear-ascii-color-160x50", 160, 50, "ascii-color",
         lambda n, w, h, m: _capture_street(n, w, h, m, hour=12.0)),
        # ascii-mono: form carried entirely by glyph density
        ("night-lamps-ascii-mono-80x32", 80, 32, "ascii-mono",
         lambda n, w, h, m: _capture_street(n, w, h, m, hour=23.0)),
        # Interior storefront room, themed furniture props
        ("interior-day-blocks-80x32", 80, 32, "blocks",
         lambda n, w, h, m: _capture_interior(n, w, h, m, hour=12.0)),
        # Driving: cockpit HUD over a moving-traffic street
        ("driving-day-blocks-160x50", 160, 50, "blocks",
         lambda n, w, h, m: _capture_driving(n, w, h, m, hour=12.0)),
        # Street life: simulated traffic + pedestrians at dusk
        ("street-life-dusk-blocks-80x32", 80, 32, "blocks",
         lambda n, w, h, m: _capture_street_life(n, w, h, m, hour=19.5)),
    ]


SCENARIO_NAMES = [s[0] for s in _scenarios()]


def render_scenario(name):
    """Renders one scenario by name -> (canonical_frame, digest).

    The seed guard spans the entire build -- city, managers, simulation steps
    AND render -- because manager constructors and fixed-dt updates draw from
    the module-level RNG long before _render() runs.
    """
    for sc_name, width, height, mode, builder in _scenarios():
        if sc_name == name:
            with _RngGuard():
                _, buffer = builder(sc_name, width, height, mode)
            canonical = canonical_frame(buffer)
            return canonical, digest_frame(buffer)
    raise KeyError("unknown scenario: %s" % name)


# --------------------------------------------------------------------------
# Manifest IO + CLI
# --------------------------------------------------------------------------

def load_manifest():
    """Loads tests/golden/manifest.json (raises FileNotFoundError if absent)."""
    with open(GOLDEN_MANIFEST, "r") as fh:
        return json.load(fh)


def build_manifest_entry(name, width, height, mode, canonical, digest):
    return {
        "width": width,
        "height": height,
        "mode": mode,
        "cell_count": width * height,
        "digest": digest,
        "frame_b64": pack_frame(canonical),
    }


def regenerate(scenario_filter=None):
    """Recaptures goldens into tests/golden/manifest.json.

    Returns a process exit code (0 ok, 2 unusable invocation). A filtered
    regeneration only rewrites the selected scenario and therefore requires
    a complete existing manifest for the others -- it never silently
    recaptures or drops cells it was not asked to touch.
    """
    entries = {}
    existing = {}
    if os.path.exists(GOLDEN_MANIFEST):
        try:
            existing = load_manifest().get("scenarios", {})
        except (ValueError, KeyError):
            existing = {}

    if scenario_filter and not set(SCENARIO_NAMES).issubset(existing):
        print("Partial regeneration requires a complete existing manifest "
              "(missing %d of %d scenarios)." % (
                  len([n for n in SCENARIO_NAMES if n not in existing]),
                  len(SCENARIO_NAMES)))
        print("Run: python3 tools/golden_capture.py --regenerate")
        return 2

    for name, width, height, mode, builder in _scenarios():
        if scenario_filter and name != scenario_filter:
            entries[name] = existing[name]  # leave untouched cells alone
            continue
        with _RngGuard():
            _, buffer = builder(name, width, height, mode)
        canonical = canonical_frame(buffer)
        entries[name] = build_manifest_entry(name, width, height, mode,
                                             canonical, digest_frame(buffer))
        print("captured %-34s %s" % (name, entries[name]["digest"][:12]))

    manifest = {
        "version": 1,
        "generator": "tools/golden_capture.py",
        "seed_note": ("city seed %d, scenario seed %d; regenerate with "
                      "`python3 tools/golden_capture.py --regenerate`"
                      % (CITY_SEED, SCENARIO_SEED)),
        "scenarios": entries,
    }
    os.makedirs(os.path.dirname(GOLDEN_MANIFEST), exist_ok=True)
    with open(GOLDEN_MANIFEST, "w") as fh:
        json.dump(manifest, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print("wrote %s (%d scenarios)" % (
        os.path.relpath(GOLDEN_MANIFEST, REPO_ROOT), len(entries)))


def check(scenario_filter=None):
    """Verifies current frames against the manifest. Returns exit code."""
    try:
        manifest = load_manifest()
    except FileNotFoundError:
        print("GOLDEN MANIFEST MISSING: %s" %
              os.path.relpath(GOLDEN_MANIFEST, REPO_ROOT))
        print("Capture it once with: python3 tools/golden_capture.py --regenerate")
        return 2

    failures = 0
    checked = 0
    for name, width, height, mode, builder in _scenarios():
        if scenario_filter and name != scenario_filter:
            continue
        checked += 1
        entry = manifest.get("scenarios", {}).get(name)
        if entry is None:
            print("FAIL %-34s no golden captured" % name)
            failures += 1
            continue

        with _RngGuard():
            _, buffer = builder(name, width, height, mode)
        canonical = canonical_frame(buffer)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if digest == entry.get("digest"):
            print("ok   %-34s %s" % (name, digest[:12]))
            continue

        failures += 1
        print("FAIL %-34s" % name)
        print("     expected digest %s" % entry.get("digest"))
        print("     actual   digest %s" % digest)
        try:
            old_canonical = unpack_frame(entry["frame_b64"])
            changed, total, lines = diff_canonical(old_canonical, canonical,
                                                   width, height)
            pct = 100.0 * changed / total
            print("     %d / %d cells changed (%.2f%%)" % (changed, total, pct))
            for line in lines:
                print(line)
        except Exception as exc:  # corrupted/unparseable golden blob
            print("     (stored frame unreadable: %s)" % exc)

    missing = [n for n in SCENARIO_NAMES
               if n not in manifest.get("scenarios", {})]
    for name in missing:
        if not scenario_filter or name == scenario_filter:
            print("FAIL %-34s no golden captured" % name)
            failures += 1

    if failures:
        print("\n%d/%d golden scenarios changed." % (failures, checked))
        print("If the visual change is INTENTIONAL, recapture with:")
        print("  python3 tools/golden_capture.py --regenerate")
        return 1
    print("\nAll %d golden scenarios match." % checked)
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Golden-frame capture & verification (T-02)")
    parser.add_argument("--regenerate", action="store_true",
                        help="recapture goldens after an intentional visual "
                             "change (writes tests/golden/manifest.json)")
    parser.add_argument("--scenario", default=None,
                        help="operate on a single scenario by name")
    parser.add_argument("--list", action="store_true",
                        help="list scenario names and exit")
    args = parser.parse_args()

    if args.list:
        for name, width, height, mode, _ in _scenarios():
            print("%-34s %dx%d %s" % (name, width, height, mode))
        return 0
    if args.scenario and args.scenario not in SCENARIO_NAMES:
        parser.error("unknown scenario %r (see --list)" % args.scenario)

    if args.regenerate:
        return regenerate(args.scenario)
    return check(args.scenario)


if __name__ == "__main__":
    sys.exit(main())
