"""
Terminal Raw Mode lifecycle manager, screen dimensions, and ANSI output for Astra 3D.
"""

import os
import sys
import tty
import termios
import signal
from typing import Tuple, Optional


class TerminalManager:
    def __init__(self):
        self.old_settings = None
        self.is_raw = False
        self.width = 80
        self.height = 32
        self.resized = False

    def __enter__(self):
        self.enter_raw_mode()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.restore_terminal()

    def get_size(self) -> Tuple[int, int]:
        try:
            size = os.get_terminal_size()
            self.width = max(40, size.columns)
            self.height = max(20, size.lines)
        except Exception:
            self.width = 80
            self.height = 32
        return (self.width, self.height)

    def enter_raw_mode(self):
        if not sys.stdin.isatty():
            return

        try:
            self.old_settings = termios.tcgetattr(sys.stdin)
            tty.setraw(sys.stdin.fileno())
            self.is_raw = True

            # Save screen, switch to alternate buffer, hide cursor, clear screen
            sys.stdout.write("\033[?1049h\033[?25l\033[2J\033[H")
            sys.stdout.flush()

            # Install WINCH signal handler for dynamic terminal resizing
            signal.signal(signal.SIGWINCH, self._on_resize)
        except Exception:
            pass

    def restore_terminal(self):
        try:
            # Show cursor, exit alternate buffer, reset colors
            sys.stdout.write("\033[0m\033[?25h\033[?1049l")
            sys.stdout.flush()

            if self.is_raw and self.old_settings:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
                self.is_raw = False
        except Exception:
            pass

    def _on_resize(self, signum, frame):
        self.resized = True

    def flush_frame(self, frame_str: str):
        try:
            sys.stdout.write(frame_str)
            sys.stdout.flush()
        except IOError:
            pass
