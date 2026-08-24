"""
ASCII Texture and Facade definitions for Astra 3D.
Textures provide 2D character patterns and TrueColor RGB color palettes.
"""

from typing import Dict, Tuple, List


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

    return AsciiTexture("SKYSCRAPER_GLASS", w, h, chars, fg_colors, bg_colors, height_mult=5.0)


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

    return AsciiTexture("SKYSCRAPER_NEON", w, h, chars, fg_colors, bg_colors, height_mult=7.0)


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

    return AsciiTexture("HOTEL_NEON", w, h, chars, fg_colors, bg_colors, height_mult=3.5)


def build_arcology_monument() -> AsciiTexture:
    w, h = 8, 8
    chars = [
        " /\\  /\\ ",
        "| |::| |",
        "| |::| |",
        "|<CORE>|",
        "| |::| |",
        "| |::| |",
        "/======\\",
        "========"
    ]
    chars = [row[:8] for row in chars]
    fg_colors = []
    bg_colors = []
    for y in range(h):
        fg_row = []
        bg_row = []
        for x in range(w):
            c = chars[y][x]
            if y == 3:  # Glowing energy core
                fg_row.append((0, 255, 220))    # Neon cyan core
                bg_row.append((10, 40, 50))
            elif c == ':':
                fg_row.append((140, 100, 255))  # Purple plasma conduit
                bg_row.append((25, 15, 45))
            elif c in ('/', '\\'):
                fg_row.append((200, 220, 255))
                bg_row.append((30, 35, 50))
            else:
                fg_row.append((160, 180, 210))  # Titanium alloy
                bg_row.append((20, 25, 35))
        fg_colors.append(fg_row)
        bg_colors.append(bg_row)

    return AsciiTexture("ARCOLOGY_MONUMENT", w, h, chars, fg_colors, bg_colors, height_mult=8.0)


def build_megastructure_matrix() -> AsciiTexture:
    w, h = 8, 8
    chars = [
        "01010101",
        "|==||==|",
        "10101010",
        "|[DATA]|",
        "01010101",
        "|==||==|",
        "10101010",
        "========"
    ]
    fg_colors = []
    bg_colors = []
    for y in range(h):
        fg_row = []
        bg_row = []
        for x in range(w):
            c = chars[y][x]
            if y == 3:
                fg_row.append((0, 255, 120))    # Matrix green
                bg_row.append((10, 35, 20))
            elif c in ('0', '1'):
                fg_row.append((80, 220, 255))   # Cyan binary bits
                bg_row.append((15, 25, 40))
            else:
                fg_row.append((120, 140, 160))
                bg_row.append((20, 25, 30))
        fg_colors.append(fg_row)
        bg_colors.append(bg_row)

    return AsciiTexture("MEGASTRUCTURE_MATRIX", w, h, chars, fg_colors, bg_colors, height_mult=6.0)


def build_industrial_silo() -> AsciiTexture:
    w, h = 8, 8
    chars = [
        "(######)",
        "|!HAZAR|",
        "| (70) |",
        "|======|",
        "|  ::  |",
        "| [VALV|",
        "|======|",
        "========"
    ]
    chars = [row[:8] for row in chars]
    fg_colors = []
    bg_colors = []
    for y in range(h):
        fg_row = []
        bg_row = []
        for x in range(w):
            c = chars[y][x]
            if y == 1:
                fg_row.append((255, 200, 0))   # Hazard warning yellow
                bg_row.append((50, 40, 0))
            elif c == '#':
                fg_row.append((180, 180, 190))
                bg_row.append((40, 42, 45))
            else:
                fg_row.append((150, 155, 160))
                bg_row.append((30, 32, 35))
        fg_colors.append(fg_row)
        bg_colors.append(bg_row)

    return AsciiTexture("INDUSTRIAL_SILO", w, h, chars, fg_colors, bg_colors, height_mult=1.5)


def build_marina_dock() -> AsciiTexture:
    w, h = 8, 8
    chars = [
        "~[PIER]~",
        "|######|",
        "| (⚓)  |",
        "|======|",
        "|  ||  |",
        "| [GATE|",
        "|======|",
        "~~~~~~~~"
    ]
    chars = [row[:8] for row in chars]
    fg_colors = []
    bg_colors = []
    for y in range(h):
        fg_row = []
        bg_row = []
        for x in range(w):
            c = chars[y][x]
            if y in (0, 7) or c == '~':
                fg_row.append((80, 180, 240))   # Water reflection cyan
                bg_row.append((10, 25, 45))
            elif y == 2:
                fg_row.append((255, 220, 100))  # Brass anchor motif
                bg_row.append((35, 25, 15))
            else:
                fg_row.append((160, 120, 80))   # Weathered dock timber
                bg_row.append((35, 25, 15))
        fg_colors.append(fg_row)
        bg_colors.append(bg_row)

    return AsciiTexture("MARINA_DOCK", w, h, chars, fg_colors, bg_colors, height_mult=1.0)


def build_botanical_pavilion() -> AsciiTexture:
    w, h = 8, 8
    chars = [
        "/\\====/\\",
        "|{GRDN}|",
        "|#    #|",
        "|  @@  |",
        "| @@@@ |",
        "|  ||  |",
        "|======|",
        "========"
    ]
    chars = [row[:8] for row in chars]
    fg_colors = []
    bg_colors = []
    for y in range(h):
        fg_row = []
        bg_row = []
        for x in range(w):
            c = chars[y][x]
            if c == '@':
                fg_row.append((70, 220, 90))    # Lush foliage green
                bg_row.append((15, 40, 20))
            elif y == 1:
                fg_row.append((140, 240, 180))  # Mint garden sign
                bg_row.append((20, 45, 30))
            elif c in ('/', '\\', '='):
                fg_row.append((200, 230, 220))  # White greenhouse iron frame
                bg_row.append((25, 35, 30))
            else:
                fg_row.append((120, 200, 220))  # Glass pane
                bg_row.append((15, 30, 35))
        fg_colors.append(fg_row)
        bg_colors.append(bg_row)

    return AsciiTexture("BOTANICAL_PAVILION", w, h, chars, fg_colors, bg_colors, height_mult=1.6)


def build_interior_wall() -> AsciiTexture:
    """Warm plaster interior wall with a wainscot rail."""
    w, h = 8, 8
    chars = [
        "~~~~~~~~",
        "~      ~",
        "~      ~",
        "--------",
        "=      =",
        "=      =",
        "=      =",
        "========"
    ]
    fg_colors = []
    bg_colors = []
    for y in range(h):
        fg_row = []
        bg_row = []
        for x in range(w):
            c = chars[y][x]
            if c == '-':
                fg_row.append((120, 90, 60))    # wainscot rail
                bg_row.append((45, 32, 22))
            elif c == '=':
                fg_row.append((95, 70, 48))     # lower panel trim
                bg_row.append((38, 28, 20))
            elif c == '~':
                fg_row.append((150, 130, 105))  # upper plaster edge
                bg_row.append((52, 42, 34))
            else:
                fg_row.append((185, 165, 135))  # warm plaster
                bg_row.append((58, 47, 38))
        fg_colors.append(fg_row)
        bg_colors.append(bg_row)

    return AsciiTexture("INTERIOR_WALL", w, h, chars, fg_colors, bg_colors, height_mult=1.0)


def build_doorway() -> AsciiTexture:
    """Revolving-door threshold: glass panes with a bright EXIT bar."""
    w, h = 4, 4
    chars = [
        "|==|",
        "|  |",
        "|  |",
        "[!!]"
    ]
    fg_colors = []
    bg_colors = []
    for y in range(h):
        fg_row = []
        bg_row = []
        for x in range(w):
            c = chars[y][x]
            if c == '!':
                fg_row.append((120, 255, 140))  # glowing EXIT bar
                bg_row.append((15, 40, 20))
            elif c in ('|', '[', ']'):
                fg_row.append((200, 210, 220))
                bg_row.append((30, 35, 45))
            elif c == '=':
                fg_row.append((150, 170, 190))
                bg_row.append((25, 30, 40))
            else:
                fg_row.append((160, 230, 255))  # clear glass
                bg_row.append((18, 26, 36))
        fg_colors.append(fg_row)
        bg_colors.append(bg_row)

    return AsciiTexture("DOORWAY", w, h, chars, fg_colors, bg_colors, height_mult=1.0)


def build_ramen_interior() -> AsciiTexture:
    """Ramen counter / kitchen wall (ported from the M2 branch)."""
    chars = [
        "========",
        "| MENU |",
        "|######|",
        "|######|",
        "|------|",
        "|STOOLS|",
        "| |  | |",
        "========"
    ]
    fg, bg = _make_uniform_palette(8, 8, (255, 200, 100), (45, 25, 15))
    return AsciiTexture("RAMEN_INTERIOR", 8, 8, chars, fg, bg, height_mult=1.0)


def build_arcade_interior() -> AsciiTexture:
    """Arcade cabinet wall with glowing CRT banks (ported from the M2 branch)."""
    chars = [
        "[ARCADE]",
        "|#CRT# |",
        "|[JOY] |",
        "|######|",
        "[ARCADE]",
        "|#CRT# |",
        "|[JOY] |",
        "========"
    ]
    fg_colors = []
    bg_colors = []
    for y in range(8):
        fg_row = []
        bg_row = []
        for x in range(8):
            if "CRT" in chars[y]:
                fg_row.append((0, 255, 200))
                bg_row.append((10, 30, 25))
            else:
                fg_row.append((255, 50, 180))
                bg_row.append((30, 10, 30))
        fg_colors.append(fg_row)
        bg_colors.append(bg_row)
    return AsciiTexture("ARCADE_INTERIOR", 8, 8, chars, fg_colors, bg_colors, height_mult=1.0)


def build_hotel_interior() -> AsciiTexture:
    """Hotel marble lobby wall (ported from the M2 branch)."""
    chars = [
        "/======\\",
        "|MARBLE|",
        "|  ::  |",
        "|  ::  |",
        "|------|",
        "| GOLD |",
        "|  ::  |",
        "\\======/"
    ]
    fg, bg = _make_uniform_palette(8, 8, (255, 230, 160), (35, 30, 25))
    return AsciiTexture("HOTEL_INTERIOR", 8, 8, chars, fg, bg, height_mult=1.2)


def build_interior_textures() -> Dict[int, AsciiTexture]:
    """Themed interior wall textures for enterable buildings."""
    return {
        101: build_ramen_interior(),
        102: build_arcade_interior(),
        103: build_hotel_interior(),
    }


# Texture registry
TEXTURE_REGISTRY = {
    1: build_skyscraper_glass(),
    2: build_skyscraper_neon(),
    3: build_brick_brownstone(),
    4: build_storefront_ramen(),
    5: build_concrete_warehouse(),
    6: build_hotel_neon(),
    7: build_arcology_monument(),
    8: build_megastructure_matrix(),
    9: build_industrial_silo(),
    10: build_marina_dock(),
    11: build_botanical_pavilion(),
    12: build_interior_wall(),
    13: build_doorway(),
}

# Register interior textures
TEXTURE_REGISTRY.update(build_interior_textures())


def get_texture(texture_id: int) -> AsciiTexture:
    return TEXTURE_REGISTRY.get(texture_id, TEXTURE_REGISTRY[1])

