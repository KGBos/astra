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
    from src.world.scale import LAMP_HEIGHT_M
    return Sprite(x, y, "STREETLAMP", chars, fg, scale_x=0.6, scale_y=LAMP_HEIGHT_M, is_luminous=True)


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
    from src.world.scale import TREE_HEIGHT_M
    return Sprite(x, y, "TREE", chars, fg, scale_x=0.9, scale_y=TREE_HEIGHT_M)


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
    from src.world.scale import HYDRANT_HEIGHT_M
    return Sprite(x, y, "HYDRANT", chars, fg, scale_x=0.4, scale_y=HYDRANT_HEIGHT_M)


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
    from src.world.scale import BENCH_HEIGHT_M
    return Sprite(x, y, "BENCH", chars, fg, scale_x=0.7, scale_y=BENCH_HEIGHT_M)


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



class VolumetricSprite(Sprite):
    """
    Pseudo-volumetric street prop: a box with distinct FRONT and SIDE faces.

    The renderer projects both faces with an angle-dependent width split
    (front shrinks as the camera moves off-axis while the side face grows),
    producing a convincing corner edge without true mesh geometry.
    """

    SIDE_SHADE = 0.78  # side plane reads darker than the lit front plane

    def __init__(
        self,
        x: float,
        y: float,
        name: str,
        front_chars: List[str],
        front_fg: List[List[Tuple[int, int, int]]],
        side_chars: List[str],
        side_fg: List[List[Tuple[int, int, int]]],
        facing_angle: float = 0.0,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
        vertical_offset: float = 0.0,
        is_luminous: bool = False,
        back_chars: Optional[List[str]] = None,
        back_fg: Optional[List[List[Tuple[int, int, int]]]] = None,
        corner_smooth: bool = False,
        front_units: Optional[float] = None,
        side_units: Optional[float] = None,
        height_units: Optional[float] = None
    ):
        super().__init__(x, y, name, front_chars, front_fg,
                         scale_x=scale_x, scale_y=scale_y,
                         vertical_offset=vertical_offset, is_luminous=is_luminous)
        self.front_chars = front_chars
        self.front_fg = front_fg
        self.side_chars = side_chars
        self.side_fg = side_fg
        self.back_chars = back_chars      # optional rear face (e.g. taillights)
        self.back_fg = back_fg
        self.facing_angle = facing_angle
        self.corner_smooth = corner_smooth
        # Explicit physical footprint in world units (1 tile ~= 1 m); falls
        # back to legacy scale_x/scale_y derivation when omitted
        self.front_units = front_units if front_units is not None else scale_x
        self.side_units = side_units if side_units is not None else scale_x
        self.height_units = height_units if height_units is not None else scale_y

    def visible_faces(self, cam_dx: float, cam_dy: float) -> Tuple[float, bool, bool]:
        """
        Returns (front_share, front_on_left, see_front) for the projected extent.

        front_share: fraction of the box width showing the FRONT face [0..1].
        front_on_left: which side of the screen the front panel occupies.
        see_front: False when the camera is in the rear hemisphere AND a
            distinct back face exists (e.g. taillights instead of headlights).
        """
        bearing = math.atan2(cam_dy, cam_dx) - self.facing_angle
        cos_b = math.cos(bearing)
        sin_b = math.sin(bearing)
        see_front = cos_b >= 0.0 or self.back_chars is None
        abs_cos = abs(cos_b)
        abs_sin = abs(sin_b)
        total = abs_cos + abs_sin
        if total < 1e-6:
            return (1.0, True, see_front)
        if self.corner_smooth:
            # Rounded-body presentation: the face split follows the bearing
            # arc, so edge-on views keep a balanced corner instead of
            # collapsing to a zero-width sliver.
            share = (1.0 + abs_cos) / 2.0
        else:
            share = abs_cos / total
        return (share, sin_b >= 0.0, see_front)


def make_vending_machine_sprite(x: float, y: float, facing_angle: float = 0.0) -> VolumetricSprite:
    """Glowing drink machine: lit product window on the front, vents on the side."""
    front_chars = [
        "[===]",
        "|o.o|",
        "|o.o|",
        "[___]"
    ]
    frame = (150, 160, 175)
    glow = (90, 220, 255)
    cola = (255, 90, 70)
    lime = (120, 255, 120)
    front_fg = [
        [frame, glow, glow, glow, frame],
        [frame, cola, glow, lime, frame],
        [frame, lime, cola, glow, frame],
        [frame, frame, frame, frame, frame]
    ]
    side_chars = [
        "####",
        "#==#",
        "#==#",
        "####"
    ]
    dark = (95, 100, 115)
    vent = (60, 65, 80)
    side_fg = [
        [dark, dark, dark, dark],
        [dark, vent, vent, dark],
        [dark, vent, vent, dark],
        [dark, dark, dark, dark]
    ]
    return VolumetricSprite(
        x, y, "VENDING_MACHINE",
        front_chars, front_fg,
        side_chars, side_fg,
        facing_angle=facing_angle,
        scale_x=0.55, scale_y=0.55,
        is_luminous=True,
        front_units=0.9,
        side_units=0.6,
        height_units=1.5
    )
