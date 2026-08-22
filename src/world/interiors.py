"""
Interactive 3D Building Interiors and Storefront Systems for Astra 3D.
Supports seamless outdoor-to-indoor transitions into custom rooms.
"""

from typing import List, Tuple, Optional, Dict
from src.world.textures import AsciiTexture, _make_uniform_palette
from src.entities.sprite import Sprite


class InteriorPortal:
    def __init__(self, outdoor_x: float, outdoor_y: float, target_room_id: str, name: str, icon: str):
        self.outdoor_x = outdoor_x
        self.outdoor_y = outdoor_y
        self.target_room_id = target_room_id
        self.name = name
        self.icon = icon


def build_interior_textures() -> Dict[int, AsciiTexture]:
    textures = {}

    # 101: Ramen Counter / Kitchen Wall
    chars_ramen = [
        "========",
        "| MENU |",
        "|######|",
        "|######|",
        "|------|",
        "|STOOLS|",
        "| |  | |",
        "========"
    ]
    fg_ramen, bg_ramen = _make_uniform_palette(8, 8, (255, 200, 100), (45, 25, 15))
    textures[101] = AsciiTexture("RAMEN_INTERIOR", 8, 8, chars_ramen, fg_ramen, bg_ramen, height_mult=1.0)

    # 102: Arcade Cabinet Wall
    chars_arcade = [
        "[ARCADE]",
        "|#CRT# |",
        "|[JOY] |",
        "|######|",
        "[ARCADE]",
        "|#CRT# |",
        "|[JOY] |",
        "========"
    ]
    fg_arc = []
    bg_arc = []
    for y in range(8):
        fg_row = []
        bg_row = []
        for x in range(8):
            if "CRT" in chars_arcade[y]:
                fg_row.append((0, 255, 200))
                bg_row.append((10, 30, 25))
            else:
                fg_row.append((255, 50, 180))
                bg_row.append((30, 10, 30))
        fg_arc.append(fg_row)
        bg_arc.append(bg_row)
    textures[102] = AsciiTexture("ARCADE_INTERIOR", 8, 8, chars_arcade, fg_arc, bg_arc, height_mult=1.0)

    # 103: Hotel Marble Wall
    chars_hotel = [
        "/======\\",
        "|MARBLE|",
        "|  ::  |",
        "|  ::  |",
        "|------|",
        "| GOLD |",
        "|  ::  |",
        "\\======/"
    ]
    fg_hot, bg_hot = _make_uniform_palette(8, 8, (255, 230, 160), (35, 30, 25))
    textures[103] = AsciiTexture("HOTEL_INTERIOR", 8, 8, chars_hotel, fg_hot, bg_hot, height_mult=1.2)

    return textures


class InteriorRoom:
    def __init__(self, room_id: str, name: str, width: int = 12, height: int = 12, wall_type: int = 101):
        self.room_id = room_id
        self.name = name
        self.width = width
        self.height = height
        self.wall_type = wall_type
        
        self.walls = [[0 for _ in range(width)] for _ in range(height)]
        self.floors = [[6 for _ in range(width)] for _ in range(height)]
        self.props: List[Sprite] = []
        self.spawn_pos = (width / 2.0, height - 2.5)
        self.exit_pos = (width / 2.0, height - 1.5)

        self._build_room()

    def _build_room(self):
        # Build perimeter walls
        for x in range(self.width):
            self.walls[0][x] = self.wall_type
            self.walls[self.height - 1][x] = self.wall_type
        for y in range(self.height):
            self.walls[y][0] = self.wall_type
            self.walls[y][self.width - 1] = self.wall_type

        # Leave doorway at bottom center
        door_x = self.width // 2
        self.walls[self.height - 1][door_x] = 0

    def is_solid(self, x: float, y: float) -> bool:
        ix = int(x)
        iy = int(y)
        if ix < 0 or ix >= self.width or iy < 0 or iy >= self.height:
            return True
        return self.walls[iy][ix] > 0

    def get_wall_type(self, x: int, y: int) -> int:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.walls[y][x]
        return self.wall_type

    def get_wall_height(self, wall_type: int) -> float:
        return 1.0

    def get_floor_type(self, x: int, y: int) -> int:
        return 6  # Plaza / Indoor tiles


def build_interiors_catalog() -> Dict[str, InteriorRoom]:
    catalog = {}

    # 1. Cyber Ramen Bar
    ramen = InteriorRoom("RAMEN_SHOP", "🍜 KAITO'S 24H CYBER RAMEN", width=12, height=12, wall_type=101)
    # Add ramen counter prop in center
    ramen_counter_chars = [
        " [STEAMING NOODLES] ",
        "  (🍜)  (🍜)  (🍜)  ",
        "====================",
        "  |  |  |  |  |  |  "
    ]
    ramen_counter_fg = [
        [(255, 240, 180) for _ in range(20)],
        [(255, 200, 50) for _ in range(20)],
        [(180, 100, 50) for _ in range(20)],
        [(100, 60, 30) for _ in range(20)]
    ]
    ramen.props.append(Sprite(6.0, 5.0, "RAMEN_BAR", ramen_counter_chars, ramen_counter_fg, scale_x=1.2, scale_y=0.7, is_luminous=True))
    catalog["RAMEN_SHOP"] = ramen

    # 2. Cyber Arcade
    arcade = InteriorRoom("ARCADE", "🕹️ NEON MATRIX CYBER ARCADE", width=12, height=12, wall_type=102)
    arcade_chars = [
        " [TOP 1: 999,990] ",
        "  <ASTRA RUNNER>  ",
        "  [CRT]   [CRT]   ",
        "  (🕹️)     (🕹️)   "
    ]
    arcade_fg = [
        [(255, 255, 100) for _ in range(18)],
        [(0, 240, 255) for _ in range(18)],
        [(255, 50, 180) for _ in range(18)],
        [(50, 255, 150) for _ in range(18)]
    ]
    arcade.props.append(Sprite(6.0, 5.0, "ARCADE_CABINET", arcade_chars, arcade_fg, scale_x=1.1, scale_y=0.7, is_luminous=True))
    catalog["ARCADE"] = arcade

    # 3. Grand Hotel Lobby
    hotel = InteriorRoom("HOTEL_LOBBY", "🏨 THE GRAND ASTRA HOTEL LOBBY", width=14, height=14, wall_type=103)
    hotel_chars = [
        "  * CHANDELIER *  ",
        " [CONCIERGE DESK] ",
        "  | [GOLD BELL] | ",
        "=================="
    ]
    hotel_fg = [
        [(255, 240, 150) for _ in range(18)],
        [(220, 180, 100) for _ in range(18)],
        [(255, 220, 50) for _ in range(18)],
        [(150, 120, 70) for _ in range(18)]
    ]
    hotel.props.append(Sprite(7.0, 6.0, "HOTEL_DESK", hotel_chars, hotel_fg, scale_x=1.2, scale_y=0.7, is_luminous=True))
    catalog["HOTEL_LOBBY"] = hotel

    return catalog
