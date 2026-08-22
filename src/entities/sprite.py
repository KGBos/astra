"""
3D Billboarding Sprite system for Astra 3D.
"""

import math
from typing import List, Tuple, Optional


class Sprite:
    def __init__(
        self,
        x: float,
        y: float,
        name: str,
        chars: List[str],
        fg_colors: List[List[Tuple[int, int, int]]],
        bg_colors: Optional[List[List[Tuple[int, int, int]]]] = None,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
        vertical_offset: float = 0.0,
        is_luminous: bool = False
    ):
        self.x = float(x)
        self.y = float(y)
        self.name = name
        self.chars = chars
        self.height = len(chars)
        self.width = len(chars[0]) if chars else 0
        self.fg_colors = fg_colors
        self.bg_colors = bg_colors
        self.scale_x = scale_x
        self.scale_y = scale_y
        self.vertical_offset = vertical_offset  # offset from ground [0.0 = on ground]
        self.is_luminous = is_luminous        # glows in dark, ignores night dimming

        # Rendering runtime values
        self.dist_sq: float = 0.0
        self.transform_x: float = 0.0
        self.transform_y: float = 0.0
        self.screen_x: int = 0
        self.draw_w: int = 0
        self.draw_h: int = 0


def make_streetlamp_sprite(x: float, y: float) -> Sprite:
    chars = [
        " (o) ",
        "  |  ",
        "  |  ",
        " === "
    ]
    fg = [
        [(255, 240, 150) for _ in range(5)],  # Glowing golden lamp
        [(150, 150, 160) for _ in range(5)],  # Steel pole
        [(150, 150, 160) for _ in range(5)],
        [(100, 100, 110) for _ in range(5)]
    ]
    return Sprite(x, y, "STREETLAMP", chars, fg, scale_x=0.6, scale_y=0.9, is_luminous=True)


def make_tree_sprite(x: float, y: float) -> Sprite:
    chars = [
        "  @@@  ",
        " @@@@@ ",
        "@@@@@@@",
        "  | |  "
    ]
    fg = [
        [(60, 180, 75) for _ in range(7)],
        [(45, 150, 60) for _ in range(7)],
        [(35, 130, 50) for _ in range(7)],
        [(120, 80, 50) for _ in range(7)]
    ]
    return Sprite(x, y, "TREE", chars, fg, scale_x=0.9, scale_y=0.9)


def make_fire_hydrant_sprite(x: float, y: float) -> Sprite:
    chars = [
        " (o) ",
        "[===]",
        " | | "
    ]
    fg = [
        [(255, 60, 50) for _ in range(5)],
        [(240, 40, 30) for _ in range(5)],
        [(200, 30, 20) for _ in range(5)]
    ]
    return Sprite(x, y, "HYDRANT", chars, fg, scale_x=0.4, scale_y=0.4)


def make_park_bench_sprite(x: float, y: float) -> Sprite:
    chars = [
        "|======|",
        "|======|",
        " |    | "
    ]
    fg = [
        [(170, 110, 60) for _ in range(8)],
        [(140, 90, 50) for _ in range(8)],
        [(80, 80, 90) for _ in range(8)]
    ]
    return Sprite(x, y, "BENCH", chars, fg, scale_x=0.7, scale_y=0.4)


def make_fountain_sprite(x: float, y: float) -> Sprite:
    chars = [
        "  ~*~  ",
        " (~~~)",
        "(~~~~~)",
        " [===] "
    ]
    fg = [
        [(100, 230, 255) for _ in range(7)],
        [(80, 200, 255) for _ in range(7)],
        [(60, 180, 240) for _ in range(7)],
        [(180, 190, 200) for _ in range(7)]
    ]
    return Sprite(x, y, "FOUNTAIN", chars, fg, scale_x=0.8, scale_y=0.7, is_luminous=True)


def make_monument_obelisk_sprite(x: float, y: float) -> Sprite:
    chars = [
        "  /\\  ",
        " |::| ",
        " |**| ",
        " |::| ",
        "[====]"
    ]
    fg = [
        [(0, 240, 255) for _ in range(6)],
        [(180, 180, 210) for _ in range(6)],
        [(255, 220, 50) for _ in range(6)],
        [(180, 180, 210) for _ in range(6)],
        [(100, 110, 130) for _ in range(6)]
    ]
    return Sprite(x, y, "OBELISK", chars, fg, scale_x=0.7, scale_y=1.2, is_luminous=True)


def make_dumpster_sprite(x: float, y: float) -> Sprite:
    chars = [
        " /=====\\ ",
        "| [TRASH]|",
        "|=======|",
        " (O) (O) "
    ]
    fg = [
        [(80, 120, 90) for _ in range(9)],
        [(90, 140, 100) for _ in range(9)],
        [(60, 100, 70) for _ in range(9)],
        [(40, 40, 45) for _ in range(9)]
    ]
    return Sprite(x, y, "DUMPSTER", chars, fg, scale_x=0.8, scale_y=0.6)


def make_neon_signpost_sprite(x: float, y: float, text: str = "NEON") -> Sprite:
    tag = f"<{text[:4]}>"
    chars = [
        f" {tag} ",
        "  ||  ",
        "  ||  ",
        " ==== "
    ]
    fg = [
        [(255, 40, 180) for _ in range(6)],
        [(120, 120, 130) for _ in range(6)],
        [(120, 120, 130) for _ in range(6)],
        [(80, 80, 90) for _ in range(6)]
    ]
    return Sprite(x, y, "NEON_SIGN", chars, fg, scale_x=0.6, scale_y=0.8, is_luminous=True)


def make_crate_stack_sprite(x: float, y: float) -> Sprite:
    chars = [
        " [==] ",
        "[====]",
        "[====]"
    ]
    fg = [
        [(200, 140, 80) for _ in range(6)],
        [(180, 120, 60) for _ in range(6)],
        [(160, 100, 50) for _ in range(6)]
    ]
    return Sprite(x, y, "CRATES", chars, fg, scale_x=0.6, scale_y=0.5)


def make_bollard_sprite(x: float, y: float) -> Sprite:
    chars = [
        "(o)",
        "|#|",
        "|=|"
    ]
    fg = [
        [(255, 200, 0) for _ in range(3)],
        [(160, 160, 170) for _ in range(3)],
        [(90, 90, 100) for _ in range(3)]
    ]
    return Sprite(x, y, "BOLLARD", chars, fg, scale_x=0.3, scale_y=0.4)

