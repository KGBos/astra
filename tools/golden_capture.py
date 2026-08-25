#!/usr/bin/env python3
"""
Golden-frame regression harness for Astra 3D.

Renders a fixed scenario matrix (viewport x render-mode x time-of-day x
weather x headlights) through the real Raycaster headless and reduces each
frame to a deterministic SHA-256 digest over its displayed cells
(glyph + fg + bg per pixel). Digests live in tests/golden/manifest.json;
canonical fixed-width frame dumps live in tests/golden/frames/ so that
tests/test_golden_frames.py can print exact expected-vs-actual cell
differences whenever any visual output changes.

Determinism contract (pinned harness-side, engine untouched):
  - the global `random` module is seeded per scenario BEFORE any object is
    constructed (covers WeatherSystem particle/wind/lightning randomness);
  - DayNightCycle and WeatherSystem are never updated after construction;
    wetness and fog_density are pinned to explicit values;
  - camera pose, sprite placement and city seed are fixed constants;
  - digests use hashlib.sha256 (never the salted built-in hash()).

Coverage notes: interior/driving render paths need the full Game loop and
are intentionally absent until T-11 ships fixtures (see manifest _notes).
Falling-weather streaks are drawn by the Game overlay, not the Raycaster,
so rain/storm scenes pin wetness/fog/lightning shading instead.

Usage:
    python3 tools/golden_capture.py            # verify against the manifest,
                                               # exit code 1 on drift
    python3 tools/golden_capture.py --write    # regenerate manifest + frame
                                               # dumps after intentional
                                               # visual changes (ONE command)
"""

import argparse
import hashlib
import json
import math
import os
import random
import sys
import time
from typing import List, NamedTuple, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.engine.camera import Camera
from src.engine.raycaster import Raycaster
from src.renderer.screen_buffer import Pixel, ScreenBuffer
from src.entities.sprite import make_neon_signpost_sprite, make_streetlamp_sprite
from src.world.city_map import CityMap
from src.world.day_night import DayNightCycle
from src.world.weather import WeatherSystem, WeatherType

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN_DIR = os.path.join(REPO_ROOT, "tests", "golden")
MANIFEST_PATH = os.path.join(GOLDEN_DIR, "manifest.json")
FRAMES_DIR = os.path.join(GOLDEN_DIR, "frames")
REGEN_COMMAND = "python3 tools/golden_capture.py --write"

DIGEST_FORMAT = "astra-golden-v1"
FRAME_FORMAT = "ASTRA-GOLDEN-FRAME-v1"
CITY_SEED = 5
CITY_SIZE = 96
FOV_DEG = 70.0
CAMERA_HEADING_RAD = math.pi / 2.0  # facing South (+Y), matches render_snapshots.py
RAIN_WETNESS = 0.9
STORM_WETNESS = 0.95

Cell = Tuple[str, Optional[Tuple[int, int, int]], Optional[Tuple[int, int, int]]]


class Scenario(NamedTuple):
    """One matrix cell of the golden-frame regression suite."""
    name: str
    width: int
    height: int
    hour: float                 # DayNightCycle start hour [0, 24)
    weather: str                # key into WEATHERS ("clear" => no system)
    headlights: bool            # player headlight beam cone on/off
    mode: str                   # "default" | "mono" (use_color=False) | "nofill" (use_background=False)
    rng_seed: int               # global random.seed() applied pre-construction


WEATHERS = {
    "clear": None,
    "rain": WeatherType.RAIN,
    "fog": WeatherType.FOGGY,
    "storm": WeatherType.STORM,
}

SCENARIOS: Tuple[Scenario, ...] = (
    # --- 80x32, default color+fill --------------------------------------
    Scenario("noon-clear-80x32",         80, 32, 12.0, "clear", False, "default", 101),
    Scenario("sunset-clear-80x32",       80, 32, 18.5, "clear", False, "default", 102),
    Scenario("dusk-fog-80x32",           80, 32, 19.5, "fog",   False, "default", 103),
    Scenario("night-lamps-80x32",        80, 32, 23.0, "clear", False, "default", 104),
    Scenario("night-beams-80x32",        80, 32, 23.0, "clear", True,  "default", 105),
    Scenario("rain-night-80x32",         80, 32, 23.2, "rain",  False, "default", 106),
    Scenario("storm-night-80x32",        80, 32, 23.4, "storm", False, "default", 107),
    # --- 80x32, alternate render modes ----------------------------------
    Scenario("noon-mono-80x32",          80, 32, 12.0, "clear", False, "mono",   108),
    Scenario("rain-night-mono-80x32",    80, 32, 23.2, "rain",  False, "mono",   109),
    Scenario("sunset-nofill-80x32",      80, 32, 18.5, "clear", False, "nofill", 110),
    Scenario("night-beams-nofill-80x32", 80, 32, 23.0, "clear", True,  "nofill", 111),
    # --- 160x50 wide viewport (kept at two scenes for suite speed) ------
    Scenario("noon-clear-160x50",       160, 50, 12.0, "clear", False, "default", 112),
    Scenario("rain-night-160x50",       160, 50, 23.2, "rain",  False, "default", 115),
)

MANIFEST_NOTES = (
    "Regenerate with: %s" % REGEN_COMMAND,
    "Expected-vs-actual cell diffs on drift read the canonical frame dumps in"
    " tests/golden/frames/ (fixed-width cells: 6-hex glyph ordinal, F/N flag +"
    " 6-hex RGB for fg and bg).",
    "Determinism is pinned harness-side: global random is seeded per scenario"
    " before WeatherSystem construction, weather.update() is never called, and"
    " wetness/fog_density are assigned explicit constants.",
    "Interior/driving render modes require the full Game loop and arrive later"
    " via T-11 fixtures; this manifest intentionally excludes them.",
    "Falling-weather streaks are painted by the Game overlay, not the"
    " Raycaster, so rain/storm scenarios exercise wetness reflections, fog"
    " blending and lightning-state shading instead of streak glyphs.",
)


# ---------------------------------------------------------------------------
# Frame serialization / comparison
# ---------------------------------------------------------------------------

def effective_cell(pixel: Pixel, use_color: bool, use_background: bool) -> Cell:
    """Returns the cell state as the terminal would display it for this mode."""
    return (
        pixel.char,
        pixel.fg if use_color else None,
        pixel.bg if use_background else None,
    )


def _color_token(color: Optional[Tuple[int, int, int]]) -> str:
    """Canonical cell-color token; 'N' distinguishes None from black."""
    if color is None:
        return "N"
    r, g, b = color
    for channel in (r, g, b):
        if not isinstance(channel, int) or not 0 <= channel <= 255:
            raise ValueError("color channel out of byte range: %r" % (color,))
    return "C%02X%02X%02X" % (r, g, b)


def serialize_frame(buffer: ScreenBuffer) -> bytes:
    """Serializes the displayed framebuffer into a canonical byte stream."""
    parts = ["%s %dx%d color=%d bg=%d\n" % (
        DIGEST_FORMAT, buffer.width, buffer.height,
        int(buffer.use_color), int(buffer.use_background),
    )]
    for row in buffer.pixels:
        for pixel in row:
            char, fg, bg = effective_cell(pixel, buffer.use_color, buffer.use_background)
            parts.append(char)
            parts.append("\x00")
            parts.append(_color_token(fg))
            parts.append("\x00")
            parts.append(_color_token(bg))
            parts.append("\x01")
    return "".join(parts).encode("utf-8")


def frame_digest(buffer: ScreenBuffer) -> str:
    """SHA-256 hex digest of the canonically serialized displayed frame."""
    return hashlib.sha256(serialize_frame(buffer)).hexdigest()


def _rgb_hex(color: Optional[Tuple[int, int, int]]) -> str:
    if color is None:
        return "000000"
    return "%02X%02X%02X" % color


def _parse_rgb(text: str) -> Tuple[int, int, int]:
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def _encode_cell(cell: Cell) -> str:
    """Fixed-width (20-char) cell encoding so columns stay addressable."""
    char, fg, bg = cell
    if len(char) != 1:
        raise ValueError("glyphs must be single codepoints, got %r" % (char,))
    return "%06X%s%s%s%s" % (
        ord(char),
        "F" if fg is not None else "N", _rgb_hex(fg),
        "F" if bg is not None else "N", _rgb_hex(bg),
    )


def _decode_cell(text: str) -> Cell:
    if len(text) != CELL_WIDTH:
        raise ValueError("corrupt cell encoding: %r" % (text,))
    char = chr(int(text[0:6], 16))
    fg = _parse_rgb(text[7:13]) if text[6] == "F" else None
    bg = _parse_rgb(text[14:20]) if text[13] == "F" else None
    return char, fg, bg


CELL_WIDTH = 20


def frame_to_text(buffer: ScreenBuffer) -> str:
    """Canonical human-inspectable dump: header line + one fixed-width row per line."""
    header = "%s %dx%d color=%d bg=%d\n" % (
        FRAME_FORMAT, buffer.width, buffer.height,
        int(buffer.use_color), int(buffer.use_background),
    )
    lines = [header]
    for row in buffer.pixels:
        lines.append("".join(
            _encode_cell(effective_cell(p, buffer.use_color, buffer.use_background))
            for p in row
        ))
        lines.append("\n")
    return "".join(lines)


def text_to_cells(text: str) -> Tuple[int, int, List[List[Cell]]]:
    """Parses a frame dump back into (width, height, rows of cells)."""
    lines = text.splitlines()
    header = lines[0].split()
    width, height = (int(v) for v in header[1].split("x"))
    rows = []
    for line in lines[1:1 + height]:
        if len(line) != width * CELL_WIDTH:
            raise ValueError(
                "corrupt frame dump: row length %d != %d (header says %dx%d)"
                % (len(line), width * CELL_WIDTH, width, height))
        rows.append([_decode_cell(line[x:x + CELL_WIDTH])
                     for x in range(0, len(line), CELL_WIDTH)])
    return width, height, rows


def diff_frames(expected_buf: ScreenBuffer, actual_buf: ScreenBuffer) -> List[Tuple[int, int, Cell, Cell]]:
    """Cell-level comparison; returns [(x, y, expected_cell, actual_cell), ...]."""
    diffs = []
    for y in range(min(expected_buf.height, actual_buf.height)):
        exp_row, act_row = expected_buf.pixels[y], actual_buf.pixels[y]
        for x in range(min(expected_buf.width, actual_buf.width)):
            exp_cell = effective_cell(exp_row[x], expected_buf.use_color, expected_buf.use_background)
            act_cell = effective_cell(act_row[x], actual_buf.use_color, actual_buf.use_background)
            if exp_cell != act_cell:
                diffs.append((x, y, exp_cell, act_cell))
    return diffs


def diff_stored_vs_actual(stored_text: str, actual_buf: ScreenBuffer) -> List[Tuple[int, int, Cell, Cell]]:
    """Compares a stored frame dump against a freshly rendered buffer."""
    _, _, exp_rows = text_to_cells(stored_text)
    act_text = frame_to_text(actual_buf)
    _, _, act_rows = text_to_cells(act_text)
    diffs = []
    for y in range(min(len(exp_rows), len(act_rows))):
        for x in range(min(len(exp_rows[y]), len(act_rows[y]))):
            if exp_rows[y][x] != act_rows[y][x]:
                diffs.append((x, y, exp_rows[y][x], act_rows[y][x]))
    return diffs


def format_diffs(diffs: List[Tuple[int, int, Cell, Cell]], limit: int = 10) -> str:
    """Human-readable first-N differences: (x, y): expected (...) got (...)."""
    lines = []
    for x, y, exp_cell, act_cell in diffs[:limit]:
        lines.append("    (%d, %d): expected %s got %s" % (x, y, exp_cell, act_cell))
    if len(diffs) > limit:
        lines.append("    ... and %d more differing cells" % (len(diffs) - limit))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Scenario rendering
# ---------------------------------------------------------------------------

def render_scenario(scenario: Scenario) -> ScreenBuffer:
    """Drives the real Raycaster headless for one matrix cell, fully pinned."""
    random.seed(scenario.rng_seed)

    city_map = CityMap(width=CITY_SIZE, height=CITY_SIZE, seed=CITY_SEED)
    sx, sy = city_map.spawn_pos
    camera = Camera(x=sx, y=sy, fov_deg=FOV_DEG)
    camera.set_direction(CAMERA_HEADING_RAD)
    camera.headlights_on = scenario.headlights

    day_night = DayNightCycle(start_hour=scenario.hour)

    weather_type = WEATHERS[scenario.weather]
    weather = WeatherSystem(weather=weather_type) if weather_type else None
    if weather is not None:
        # Pin transitioned-in values without ever calling update().
        weather.fog_density = weather.fog_target_density
        if weather_type is WeatherType.RAIN:
            weather.wetness = RAIN_WETNESS
        elif weather_type is WeatherType.STORM:
            weather.wetness = STORM_WETNESS

    # Emissive sprites ahead of spawn guarantee light pools in night scenes.
    sprites = [
        make_streetlamp_sprite(sx + 1.5, sy + 7.0),
        make_neon_signpost_sprite(sx - 1.0, sy + 10.0),
    ]

    buffer = ScreenBuffer(
        scenario.width, scenario.height,
        use_color=(scenario.mode != "mono"),
        use_background=(scenario.mode != "nofill"),
    )
    raycaster = Raycaster(scenario.width, scenario.height)
    raycaster.render(
        camera=camera, city_map=city_map, sprites=sprites,
        day_night=day_night, buffer=buffer,
        weather=weather, flashlight_on=False,
    )
    return buffer


def capture_all() -> Tuple[dict, float]:
    """Renders every scenario; returns ({name: buffer}, wall_seconds)."""
    buffers = {}
    started = time.perf_counter()
    for scenario in SCENARIOS:
        buffers[scenario.name] = render_scenario(scenario)
    return buffers, time.perf_counter() - started


# ---------------------------------------------------------------------------
# Manifest I/O
# ---------------------------------------------------------------------------

def build_manifest(buffers: dict) -> dict:
    """Full manifest document: per-scenario digest + self-describing metadata."""
    scenarios = {}
    for scenario in SCENARIOS:
        scenarios[scenario.name] = {
            "digest": frame_digest(buffers[scenario.name]),
            "frame_file": "frames/%s.cells" % scenario.name,
            "viewport": [scenario.width, scenario.height],
            "hour": scenario.hour,
            "weather": scenario.weather,
            "headlights": scenario.headlights,
            "mode": scenario.mode,
        }
    return {
        "_format": DIGEST_FORMAT,
        "_regen_command": REGEN_COMMAND,
        "_notes": list(MANIFEST_NOTES),
        "scenarios": scenarios,
    }


def write_goldens(path: str = MANIFEST_PATH) -> Tuple[dict, float]:
    """Captures all scenarios and rewrites manifest.json + frames/*.cells."""
    buffers, elapsed = capture_all()
    document = build_manifest(buffers)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    os.makedirs(FRAMES_DIR, exist_ok=True)

    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(document, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp_path, path)

    for scenario in SCENARIOS:
        frame_path = os.path.join(FRAMES_DIR, "%s.cells" % scenario.name)
        tmp_frame = frame_path + ".tmp"
        with open(tmp_frame, "w", encoding="utf-8") as fh:
            fh.write(frame_to_text(buffers[scenario.name]))
        os.replace(tmp_frame, frame_path)

    return document, elapsed


def load_manifest(path: str = MANIFEST_PATH) -> dict:
    """Loads the golden manifest; raises FileNotFoundError when absent."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_frame_text(name: str, frames_dir: str = FRAMES_DIR) -> str:
    """Loads the stored canonical frame dump for a scenario."""
    with open(os.path.join(frames_dir, "%s.cells" % name), "r", encoding="utf-8") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def verify_against_manifest(path: str = MANIFEST_PATH, verbose: bool = True) -> int:
    """Re-renders the matrix and compares digests. Returns process exit code."""
    try:
        manifest = load_manifest(path)
    except FileNotFoundError:
        print("golden manifest missing: %s" % os.path.relpath(path, REPO_ROOT))
        print("regenerate it with: %s" % REGEN_COMMAND)
        return 1

    stored_scenarios = manifest.get("scenarios", {})
    buffers, elapsed = capture_all()
    drifted = 0
    for scenario in SCENARIOS:
        entry = stored_scenarios.get(scenario.name, {})
        buffer = buffers[scenario.name]
        actual_digest = frame_digest(buffer)
        if entry.get("digest") == actual_digest:
            if verbose:
                print("[ ok ] %s" % scenario.name)
            continue
        drifted += 1
        print("[DRIFT] %s" % scenario.name)
        print("    expected digest %s" % entry.get("digest"))
        print("    actual   digest %s" % actual_digest)
        try:
            stored_text = load_frame_text(scenario.name)
            diffs = diff_stored_vs_actual(stored_text, buffer)
            print("    %d cells differ:" % len(diffs))
            print(format_diffs(diffs))
        except FileNotFoundError:
            print("    stored frame dump missing: frames/%s.cells" % scenario.name)

    if drifted:
        print("%d/%d scenarios drifted in %.2fs" % (drifted, len(SCENARIOS), elapsed))
        print("intentional visual change? regenerate with: %s" % REGEN_COMMAND)
        return 1
    print("all %d golden frames match (%.2fs)" % (len(SCENARIOS), elapsed))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Golden-frame capture/verify harness.")
    parser.add_argument("--write", action="store_true",
                        help="regenerate tests/golden/manifest.json + frames/")
    parser.add_argument("--manifest", default=MANIFEST_PATH,
                        help="manifest path (default: %(default)s)")
    args = parser.parse_args()

    if args.write:
        document, elapsed = write_goldens(args.manifest)
        count = len(document["scenarios"])
        print("wrote %s + frames/ (%d scenarios, %.2fs)" % (
            os.path.relpath(args.manifest, REPO_ROOT), count, elapsed))
        return 0
    return verify_against_manifest(args.manifest)


if __name__ == "__main__":
    sys.exit(main())
