"""
Virtual Screen Buffer and optimized TrueColor ANSI escape generator for Astra 3D.
"""

from typing import List, Tuple, Optional


ASCII_TRANSLATION = {
    '°': '*', '·': '.', '—': '-', '•': '*',
    '↖': '\\', '↗': '/', '↘': '\\', '↙': '/',
    '≈': '~', '─': '-', '│': '|',
    '┌': '+', '┐': '+', '└': '+', '┘': '+',
    '═': '=', '║': '|', '╔': '+', '╗': '+',
    '█': '#', '▲': '^', '►': '>', '▼': 'v', '◄': '<',
    '★': '*', '♣': '&', '⚓': 'o', '⚡': '*', '💬': '"', '📐': '#',
}


class Pixel:
    __slots__ = ('char', 'fg', 'bg')

    def __init__(self, char: str = ' ', fg: Optional[Tuple[int, int, int]] = None, bg: Optional[Tuple[int, int, int]] = None):
        self.char = char
        self.fg = fg
        self.bg = bg


class ScreenBuffer:
    _CACHE_LIMIT = 4096

    def __init__(self, width: int = 80, height: int = 32, use_color: bool = True, use_background: bool = True):
        self.width = width
        self.height = height
        self.use_color = use_color
        self.use_background = use_background
        self.pixels: List[List[Pixel]] = [
            [Pixel(' ', None, None) for _ in range(width)] for _ in range(height)
        ]
        # Memoized ANSI escape strings keyed by RGB tuple; escapes are immutable
        # per color so the cache never needs invalidation (size-capped only)
        self._fg_cache = {}
        self._bg_cache = {}

    def resize(self, width: int, height: int):
        self.width = width
        self.height = height
        self.pixels = [
            [Pixel(' ', None, None) for _ in range(width)] for _ in range(height)
        ]

    def clear(self, bg: Optional[Tuple[int, int, int]] = None):
        for row in self.pixels:
            for p in row:
                p.char = ' '
                p.fg = None
                p.bg = bg

    def _glyph(self, ch: str) -> str:
        """Transliterates non-ASCII glyphs when running in monochrome ASCII mode."""
        if self.use_color or ch.isascii():
            return ch
        return ASCII_TRANSLATION.get(ch, '?')

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
            p.char = self._glyph(char)
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
                p.char = self._glyph(ch)
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
        paint_bg = self.use_background
        fg_cache = self._fg_cache
        bg_cache = self._bg_cache
        cache_limit = self._CACHE_LIMIT
        append = out.append

        for y, row in enumerate(self.pixels):
            for p in row:
                fg = p.fg
                # Update foreground color if changed
                if fg != last_fg:
                    if fg is None:
                        append("\033[39m")
                    else:
                        esc = fg_cache.get(fg)
                        if esc is None:
                            esc = f"\033[38;2;{fg[0]};{fg[1]};{fg[2]}m"
                            if len(fg_cache) < cache_limit:
                                fg_cache[fg] = esc
                        append(esc)
                    last_fg = fg

                # Update background color if changed (skipped entirely in no-fill mode)
                if paint_bg:
                    bg = p.bg
                    if bg != last_bg:
                        if bg is None:
                            append("\033[49m")
                        else:
                            esc = bg_cache.get(bg)
                            if esc is None:
                                esc = f"\033[48;2;{bg[0]};{bg[1]};{bg[2]}m"
                                if len(bg_cache) < cache_limit:
                                    bg_cache[bg] = esc
                            append(esc)
                        last_bg = bg

                append(p.char)

            # Reset style at line end
            if y < self.height - 1:
                append("\r\n")

        append("\033[0m")
        return "".join(out)
