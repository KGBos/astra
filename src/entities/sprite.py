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
