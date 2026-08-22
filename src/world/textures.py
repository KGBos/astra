"""
ASCII Texture and Facade definitions for Astra 3D.
Textures provide 2D character patterns and TrueColor RGB color palettes.
"""

from typing import Tuple, List


class AsciiTexture:
    def __init__(
        self,
        name: str,
        width: int,
        height: int,
        chars: List[str],
        fg_colors: List[List[Tuple[int, int, int]]],
        bg_colors: List[List[Tuple[int, int, int]]],
        height_mult: float = 1.0,
        is_transparent: bool = False
    ):
        self.name = name
        self.width = width
        self.height = height
        self.chars = chars
        self.fg_colors = fg_colors
        self.bg_colors = bg_colors
        self.height_mult = height_mult
        self.is_transparent = is_transparent

    def sample(self, u: float, v: float) -> Tuple[str, Tuple[int, int, int], Tuple[int, int, int]]:
        """
        Samples texture at normalized coordinates (u, v) in [0.0, 1.0].
        Returns (char, (r, g, b)_fg, (r, g, b)_bg).
        """
        tx = int((u % 1.0) * self.width)
        ty = int((v % 1.0) * self.height)
        tx = max(0, min(tx, self.width - 1))
        ty = max(0, min(ty, self.height - 1))

        char = self.chars[ty][tx]
        fg = self.fg_colors[ty][tx]
        bg = self.bg_colors[ty][tx]
        return (char, fg, bg)


def _make_uniform_palette(width: int, height: int, fg: Tuple[int, int, int], bg: Tuple[int, int, int]):
    return ([[fg for _ in range(width)] for _ in range(height)],
            [[bg for _ in range(width)] for _ in range(height)])


def build_skyscraper_glass() -> AsciiTexture:
    w, h = 8, 8
    chars = [
        "|##||##|",
        "|##||##|",
        "|--||--|",
        "|##||##|",
        "|##||##|",
        "|--||--|",
        "|##||##|",
        "|======|"
    ]
    fg_base = (120, 210, 255)  # Cyan glass
    bg_base = (15, 30, 50)     # Dark steel
    fg_mullion = (180, 200, 220)
    bg_mullion = (25, 35, 45)

    fg_colors = []
    bg_colors = []
    for y in range(h):
        fg_row = []
        bg_row = []
        for x in range(w):
            c = chars[y][x]
            if c in ('|', '-', '='):
                fg_row.append(fg_mullion)
                bg_row.append(bg_mullion)
            else:
                fg_row.append(fg_base)
                bg_row.append(bg_base)
        fg_colors.append(fg_row)
        bg_colors.append(bg_row)

    return AsciiTexture("SKYSCRAPER_GLASS", w, h, chars, fg_colors, bg_colors, height_mult=2.5)


def build_skyscraper_neon() -> AsciiTexture:
    w, h = 8, 8
    chars = [
        "|**||**|",
        "|ASTRA!|",
        "|--||--|",
        "|##||##|",
        "|CYBER!|",
        "|--||--|",
        "|##||##|",
        "|======|"
    ]
    fg_colors = []
    bg_colors = []
    for y in range(h):
        fg_row = []
        bg_row = []
        for x in range(w):
            c = chars[y][x]
            if y in (1, 4):  # Neon billboard rows
                fg_row.append((255, 60, 180))   # Hot Magenta Neon
                bg_row.append((40, 10, 30))
            elif c in ('|', '-', '='):
                fg_row.append((100, 100, 120))
                bg_row.append((20, 20, 25))
            else:
                fg_row.append((0, 240, 255))     # Electric Cyan
                bg_row.append((10, 30, 40))
        fg_colors.append(fg_row)
        bg_colors.append(bg_row)

    return AsciiTexture("SKYSCRAPER_NEON", w, h, chars, fg_colors, bg_colors, height_mult=3.2)


def build_brick_brownstone() -> AsciiTexture:
    w, h = 8, 8
    chars = [
        "[=][==][",
        "|#| == |",
        "[-][==][",
        " ==|#|==",
        "[=][==][",
        "|#| == |",
        "[-][==][",
        "========"
    ]
    fg_brick = (210, 95, 75)     # Brick red
    bg_brick = (45, 18, 12)
    fg_window = (255, 230, 140)  # Warm lit window
    bg_window = (60, 40, 10)
    fg_fire = (160, 160, 160)    # Fire escape metal

    fg_colors = []
    bg_colors = []
    for y in range(h):
        fg_row = []
        bg_row = []
        for x in range(w):
            c = chars[y][x]
            if c == '#':
                fg_row.append(fg_window)
                bg_row.append(bg_window)
            elif c in ('=', '|', '-'):
                fg_row.append(fg_brick)
                bg_row.append(bg_brick)
            else:
                fg_row.append(fg_fire)
                bg_row.append(bg_brick)
        fg_colors.append(fg_row)
        bg_colors.append(bg_row)

    return AsciiTexture("BRICK_BROWNSTONE", w, h, chars, fg_colors, bg_colors, height_mult=1.3)


def build_storefront_ramen() -> AsciiTexture:
    w, h = 8, 8
    chars = [
        "=========",
        "| RAMEN |",
        "| (24H) |",
        "=========",
        "|o| |#| |",
        "| | |#| |",
        "| | [D] |",
        "========="
    ]
    # Trim to 8 wide
    chars = [row[:8] for row in chars]
    fg_colors = []
    bg_colors = []
    for y in range(h):
        fg_row = []
        bg_row = []
        for x in range(w):
            if y in (1, 2):
                fg_row.append((255, 180, 20))   # Golden Amber Neon Sign
                bg_row.append((50, 25, 0))
            elif chars[y][x] == '#':
                fg_row.append((255, 240, 180))  # Lit display
                bg_row.append((50, 45, 20))
            elif chars[y][x] == 'D':
                fg_row.append((100, 200, 120))  # Glass door
                bg_row.append((15, 30, 20))
            else:
                fg_row.append((180, 120, 90))   # Wood frame
                bg_row.append((30, 20, 15))
        fg_colors.append(fg_row)
        bg_colors.append(bg_row)

    return AsciiTexture("STOREFRONT_RAMEN", w, h, chars, fg_colors, bg_colors, height_mult=1.1)


def build_concrete_warehouse() -> AsciiTexture:
    w, h = 8, 8
    chars = [
        "/\\/\\/\\/\\",
        "|  ::  |",
        "| [VENT] ",
        "|  ::  |",
        "/\\/\\/\\/\\",
        "| ====== |",
        "| |GATE| |",
        "=========="
    ]
    chars = [row[:8] for row in chars]
    fg_colors, bg_colors = _make_uniform_palette(w, h, (160, 165, 170), (35, 38, 40))
    for y in range(h):
        for x in range(w):
            if chars[y][x] in ('/', '\\'):
                fg_colors[y][x] = (255, 200, 0)  # Hazard stripes
                bg_colors[y][x] = (40, 30, 0)
    return AsciiTexture("CONCRETE_WAREHOUSE", w, h, chars, fg_colors, bg_colors, height_mult=1.0)


def build_hotel_neon() -> AsciiTexture:
    w, h = 8, 8
    chars = [
        "|HOTEL!|",
        "|##||##|",
        "|--||--|",
        "|##||##|",
        "|--||--|",
        "|##||##|",
        "| [LOBBY",
        "|======|"
    ]
    chars = [row[:8] for row in chars]
    fg_colors = []
    bg_colors = []
    for y in range(h):
        fg_row = []
        bg_row = []
        for x in range(w):
            if y == 0:
                fg_row.append((255, 50, 100))   # Ruby Neon Sign
                bg_row.append((50, 10, 20))
            elif chars[y][x] == '#':
                fg_row.append((255, 230, 150))
                bg_row.append((45, 35, 15))
            else:
                fg_row.append((140, 140, 160))
                bg_row.append((25, 25, 35))
        fg_colors.append(fg_row)
        bg_colors.append(bg_row)

    return AsciiTexture("HOTEL_NEON", w, h, chars, fg_colors, bg_colors, height_mult=2.0)


# Texture registry
TEXTURE_REGISTRY = {
    1: build_skyscraper_glass(),
    2: build_skyscraper_neon(),
    3: build_brick_brownstone(),
    4: build_storefront_ramen(),
    5: build_concrete_warehouse(),
    6: build_hotel_neon(),
}

# Register interior textures
from src.world.interiors import build_interior_textures
TEXTURE_REGISTRY.update(build_interior_textures())


def get_texture(texture_id: int) -> AsciiTexture:
    return TEXTURE_REGISTRY.get(texture_id, TEXTURE_REGISTRY[1])

