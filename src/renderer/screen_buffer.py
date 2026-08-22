"""
Virtual Screen Buffer and optimized TrueColor ANSI escape generator for Astra 3D.
"""

from typing import List, Tuple, Optional


class Pixel:
    __slots__ = ('char', 'fg', 'bg')

    def __init__(self, char: str = ' ', fg: Optional[Tuple[int, int, int]] = None, bg: Optional[Tuple[int, int, int]] = None):
        self.char = char
        self.fg = fg
        self.bg = bg


class ScreenBuffer:
    def __init__(self, width: int = 80, height: int = 32, use_color: bool = True):
        self.width = width
        self.height = height
        self.use_color = use_color
        self.pixels: List[List[Pixel]] = [
            [Pixel(' ', None, None) for _ in range(width)] for _ in range(height)
        ]

    def resize(self, width: int, height: int):
        self.width = width
        self.height = height
        self.pixels = [
            [Pixel(' ', None, None) for _ in range(width)] for _ in range(height)
        ]

    def clear(self, bg: Optional[Tuple[int, int, int]] = None):
        for y in range(self.height):
            for x in range(self.width):
                p = self.pixels[y][x]
                p.char = ' '
                p.fg = None
                p.bg = bg

    def set_pixel(
        self,
        x: int,
        y: int,
        char: str,
        fg: Optional[Tuple[int, int, int]] = None,
        bg: Optional[Tuple[int, int, int]] = None
    ):
        if 0 <= x < self.width and 0 <= y < self.height:
            p = self.pixels[y][x]
            p.char = char
            if fg is not None:
                p.fg = fg
            if bg is not None:
                p.bg = bg

    def draw_string(
        self,
        x: int,
        y: int,
        text: str,
        fg: Optional[Tuple[int, int, int]] = (255, 255, 255),
        bg: Optional[Tuple[int, int, int]] = None
    ):
        for i, ch in enumerate(text):
            px = x + i
            if 0 <= px < self.width and 0 <= y < self.height:
                p = self.pixels[y][px]
                p.char = ch
                if fg is not None:
                    p.fg = fg
                if bg is not None:
                    p.bg = bg

    def draw_box(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        fg: Tuple[int, int, int] = (100, 200, 255),
        bg: Optional[Tuple[int, int, int]] = (10, 15, 25),
        title: Optional[str] = None
    ):
        if w < 2 or h < 2:
            return

        # Top border
        self.set_pixel(x, y, '┌', fg, bg)
        for cx in range(x + 1, x + w - 1):
            self.set_pixel(cx, y, '─', fg, bg)
        self.set_pixel(x + w - 1, y, '┐', fg, bg)

        # Title
        if title:
            t_str = f" {title} "
            self.draw_string(x + 2, y, t_str[:w - 4], (255, 255, 100), bg)

        # Sides and fill
        for cy in range(y + 1, y + h - 1):
            self.set_pixel(x, cy, '│', fg, bg)
            for cx in range(x + 1, x + w - 1):
                self.set_pixel(cx, cy, ' ', fg, bg)
            self.set_pixel(x + w - 1, cy, '│', fg, bg)

        # Bottom border
        self.set_pixel(x, y + h - 1, '└', fg, bg)
        for cx in range(x + 1, x + w - 1):
            self.set_pixel(cx, y + h - 1, '─', fg, bg)
        self.set_pixel(x + w - 1, y + h - 1, '┘', fg, bg)

    def render_to_ansi(self) -> str:
        """
        Builds a single ANSI frame string with stateful color caching to minimize escape codes.
        """
        out = ["\033[H"]  # Move cursor to home (row 1, col 1)

        if not self.use_color:
            for row in self.pixels:
                out.append("".join(p.char for p in row))
                out.append("\r\n")
            return "".join(out)

        last_fg: Optional[Tuple[int, int, int]] = None
        last_bg: Optional[Tuple[int, int, int]] = None

        for y, row in enumerate(self.pixels):
            for p in row:
                # Update foreground color if changed
                if p.fg != last_fg:
                    if p.fg is None:
                        out.append("\033[39m")
                    else:
                        out.append(f"\033[38;2;{p.fg[0]};{p.fg[1]};{p.fg[2]}m")
                    last_fg = p.fg

                # Update background color if changed
                if p.bg != last_bg:
                    if p.bg is None:
                        out.append("\033[49m")
                    else:
                        out.append(f"\033[48;2;{p.bg[0]};{p.bg[1]};{p.bg[2]}m")
                    last_bg = p.bg

                out.append(p.char)

            # Reset style at line end
            if y < self.height - 1:
                out.append("\r\n")

        out.append("\033[0m")
        return "".join(out)
