"""
Terminal Raw Mode lifecycle manager, screen dimensions, and ANSI output for Astra 3D.
"""

import os
import sys
import tty
import atexit
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
        self._active = False
        self._atexit_registered = False
        self._prev_handlers = {}

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
            self._active = True

            # Save screen, switch to alternate buffer, hide cursor, clear screen,
            # enable button-event mouse tracking with SGR extended coordinates
            sys.stdout.write("\033[?1049h\033[?25l\033[2J\033[H\033[?1002h\033[?1006h")
            sys.stdout.flush()

            # Install WINCH signal handler for dynamic terminal resizing,
            # fatal-signal safety nets, and a last-resort atexit restore
            self._install_safety_nets()
        except Exception:
            pass

    def _install_safety_nets(self):
        try:
            self._prev_handlers[signal.SIGWINCH] = signal.getsignal(signal.SIGWINCH)
            signal.signal(signal.SIGWINCH, self._on_resize)
        except Exception:
            pass
        for sig_name in ("SIGTERM", "SIGHUP"):
            sig = getattr(signal, sig_name, None)
            if sig is None:
                continue
            try:
                self._prev_handlers[sig] = signal.getsignal(sig)
                signal.signal(sig, self._on_fatal_signal)
            except Exception:
                self._prev_handlers.pop(sig, None)
        if not self._atexit_registered:
            atexit.register(self.restore_terminal)
            self._atexit_registered = True

    def _on_fatal_signal(self, signum, frame):
        # Restore the terminal even on kill signals, then re-raise the default
        # disposition so process exit status stays conventional (128+signum).
        self.restore_terminal()
        try:
            signal.signal(signum, signal.SIG_DFL)
            os.kill(os.getpid(), signum)
        except Exception:
            os._exit(128 + signum)

    def restore_terminal(self):
        if not self._active:
            return
        self._active = False
        try:
            # Disable mouse tracking, show cursor, exit alternate buffer, reset colors
            sys.stdout.write("\033[?1006l\033[?1002l\033[0m\033[?25h\033[?1049l")
            sys.stdout.flush()
        except Exception:
            pass
        try:
            if self.is_raw and self.old_settings:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
        except Exception:
            pass
        self.is_raw = False
        for sig, prev in self._prev_handlers.items():
            try:
                signal.signal(sig, prev)
            except Exception:
                pass
        self._prev_handlers.clear()

    def _on_resize(self, signum, frame):
        self.resized = True

    def flush_frame(self, frame_str: str):
        if not frame_str:
            return  # dirty-region delta: nothing changed, skip the syscall
        try:
            sys.stdout.write(frame_str)
            sys.stdout.flush()
        except (OSError, ValueError):
            pass
