"""
Non-blocking Keyboard input poller, ANSI escape sequence parser, and SGR mouse tracker for Astra 3D.
"""

import os
import sys
import select
import time
from typing import Optional, Set, List


MOUSE_CLICK_MOVE_CELLS = 4

# Max bytes drained from the tty per poll; generous enough to swallow a full
# frame of burst mouse reports in a single syscall
_READ_CHUNK = 4096


class KeyAction:
    MOVE_FORWARD = "MOVE_FORWARD"
    MOVE_BACKWARD = "MOVE_BACKWARD"
    STRAFE_LEFT = "STRAFE_LEFT"
    STRAFE_RIGHT = "STRAFE_RIGHT"
    TURN_LEFT = "TURN_LEFT"
    TURN_RIGHT = "TURN_RIGHT"
    LOOK_UP = "LOOK_UP"
    LOOK_DOWN = "LOOK_DOWN"
    SPRINT = "SPRINT"
    JUMP = "JUMP"
    INTERACT = "INTERACT"
    ENTER_EXIT_VEHICLE = "ENTER_EXIT_VEHICLE"
    TOGGLE_RADIO = "TOGGLE_RADIO"
    TOGGLE_LIGHTS = "TOGGLE_LIGHTS"
    TOGGLE_MAP = "TOGGLE_MAP"
    TOGGLE_TIME = "TOGGLE_TIME"
    TOGGLE_WEATHER = "TOGGLE_WEATHER"
    REGENERATE_CITY = "REGENERATE_CITY"
    CYCLE_LANDMARKS = "CYCLE_LANDMARKS"
    HONK_HORN = "HONK_HORN"
    TOGGLE_FLASHLIGHT = "TOGGLE_FLASHLIGHT"
    NUM_1 = "NUM_1"
    NUM_2 = "NUM_2"
    NUM_3 = "NUM_3"
    QUIT = "QUIT"
    PAUSE = "PAUSE"
    WHEEL_UP = "WHEEL_UP"
    WHEEL_DOWN = "WHEEL_DOWN"


class KeyboardController:
    def __init__(self):
        self.active_actions: Set[str] = set()
        self.pressed_events: List[str] = []
        self._pending: List[str] = []
        self._pending_time: float = 0.0
        self.last_input_time: float = 0.0
        self.DECAY_SECONDS = 0.25

        # Mouse tracking state (SGR cells)
        self.mouse_x: int = -1
        self.mouse_y: int = -1
        self.mouse_dx: int = 0
        self.mouse_dy: int = 0
        self._dragging: bool = False
        self._down_moved: int = 0

    def poll_input(self):
        """Non-blocking read of all available stdin bytes and updates action states."""
        now = time.monotonic()
        chars = []
        try:
            fd = sys.stdin.fileno()
        except Exception:
            fd = None

        while True:
            try:
                r, _, _ = select.select([sys.stdin], [], [], 0.0)
            except (OSError, ValueError):
                break
            if not r:
                break
            try:
                if fd is not None:
                    # One syscall drains the whole kernel buffer instead of a
                    # select+read pair per byte (critical during mouse-drag bursts)
                    chunk = os.read(fd, _READ_CHUNK)
                    if not chunk:
                        break
                    chars.extend(chunk.decode('utf-8', 'replace'))
                else:
                    ch = sys.stdin.read(1)
                    if not ch:
                        break
                    chars.append(ch)
            except Exception:
                break

        if chars:
            self.last_input_time = now
        elif now - self.last_input_time > self.DECAY_SECONDS:
            self.active_actions.clear()

        self._consume(chars, now)

    def _consume(self, chars: List[str], now: Optional[float] = None):
        """Parse raw characters into action states, stashing partial escape sequences."""
        if now is None:
            now = time.monotonic()

        self.pressed_events.clear()

        if self._pending == ['\033'] and (now - self._pending_time) > self.DECAY_SECONDS:
            # Stashed lone Escape never got its tail: it was a standalone ESC keypress
            self.pressed_events.append(KeyAction.QUIT)
            self._pending = []

        chars = self._pending + chars
        self._pending = []

        i = 0
        n = len(chars)
        while i < n:
            ch = chars[i]

            if ch == '\033':  # Escape sequence
                if i + 1 < n and chars[i + 1] == '[':
                    if i + 2 >= n:
                        self._pending = chars[i:]
                        self._pending_time = now
                        break
                    code = chars[i + 2]
                    if code == '<':
                        end = -1
                        for j in range(i + 3, n):
                            if chars[j] in ('M', 'm'):
                                end = j
                                break
                        if end < 0:
                            self._pending = chars[i:]
                            self._pending_time = now
                            break
                        self._handle_sgr_mouse(''.join(chars[i + 3:end]), chars[end])
                        i = end + 1
                        continue
                    if code == 'A':  # Up Arrow
                        self.active_actions.add(KeyAction.MOVE_FORWARD)
                        self.pressed_events.append(KeyAction.MOVE_FORWARD)
                    elif code == 'B':  # Down Arrow
                        self.active_actions.add(KeyAction.MOVE_BACKWARD)
                        self.pressed_events.append(KeyAction.MOVE_BACKWARD)
                    elif code == 'C':  # Right Arrow
                        self.active_actions.add(KeyAction.TURN_RIGHT)
                        self.pressed_events.append(KeyAction.TURN_RIGHT)
                    elif code == 'D':  # Left Arrow
                        self.active_actions.add(KeyAction.TURN_LEFT)
                        self.pressed_events.append(KeyAction.TURN_LEFT)
                    i += 3
                    continue
                if i == n - 1:
                    # Trailing Escape byte may be the head of a split sequence
                    self._pending = ['\033']
                    self._pending_time = now
                    break
                # Standalone Escape key
                self.pressed_events.append(KeyAction.QUIT)
                i += 1
                continue

            # Standard ASCII characters
            lower = ch.lower()
            if lower == 'w':
                self.active_actions.add(KeyAction.MOVE_FORWARD)
            elif lower == 's':
                self.active_actions.add(KeyAction.MOVE_BACKWARD)
            elif lower == 'a':
                self.active_actions.add(KeyAction.STRAFE_LEFT)
            elif lower == 'd':
                self.active_actions.add(KeyAction.STRAFE_RIGHT)
            elif lower == 'q':
                self.active_actions.add(KeyAction.TURN_LEFT)
            elif lower == 'e':
                self.pressed_events.append(KeyAction.INTERACT)
            elif lower == 'f':
                self.pressed_events.append(KeyAction.ENTER_EXIT_VEHICLE)
            elif lower == 'g':
                self.pressed_events.append(KeyAction.TOGGLE_RADIO)
            elif lower == 'l':
                self.pressed_events.append(KeyAction.TOGGLE_LIGHTS)
            elif lower == 'i':
                self.active_actions.add(KeyAction.LOOK_UP)
            elif lower == 'k':
                self.active_actions.add(KeyAction.LOOK_DOWN)
            elif ch == ' ':
                self.pressed_events.append(KeyAction.JUMP)
            elif ch == '1':
                self.pressed_events.append(KeyAction.NUM_1)
            elif ch == '2':
                self.pressed_events.append(KeyAction.NUM_2)
            elif ch == '3':
                self.pressed_events.append(KeyAction.NUM_3)
            elif lower == 'm':
                self.pressed_events.append(KeyAction.TOGGLE_MAP)
            elif lower == 't':
                self.pressed_events.append(KeyAction.TOGGLE_TIME)
            elif lower == 'r':
                self.pressed_events.append(KeyAction.TOGGLE_WEATHER)
            elif lower == 'n':
                self.pressed_events.append(KeyAction.REGENERATE_CITY)
            elif lower == 'u':
                self.pressed_events.append(KeyAction.CYCLE_LANDMARKS)
            elif lower == 'b':
                self.pressed_events.append(KeyAction.TOGGLE_FLASHLIGHT)
            elif lower == 'h':
                self.pressed_events.append(KeyAction.HONK_HORN)
            elif lower == 'p':
                self.pressed_events.append(KeyAction.PAUSE)
            elif lower in ('x', '\x03'):  # 'x' or Ctrl+C
                self.pressed_events.append(KeyAction.QUIT)

            # Check if uppercase for sprint / nitro (Shift key pressed)
            if ch in ('W', 'A', 'S', 'D'):
                self.active_actions.add(KeyAction.SPRINT)

            i += 1

    def _handle_sgr_mouse(self, params: str, final: str):
        """Handles an SGR mouse report: params is 'b;x;y', final is 'M' (press/motion) or 'm' (release)."""
        try:
            parts = params.split(';')
            b, x, y = int(parts[0]), int(parts[1]), int(parts[2])
        except (ValueError, IndexError):
            return

        pressed = final == 'M'
        motion = bool(b & 32)
        btn = b & 3
        wheel = b >= 64

        if wheel:
            if pressed:
                self.pressed_events.append(KeyAction.WHEEL_UP if btn == 0 else KeyAction.WHEEL_DOWN)
            self.mouse_x, self.mouse_y = x, y
            return

        if motion:
            if self._dragging:
                if self.mouse_x >= 0:
                    self.mouse_dx += x - self.mouse_x
                    self.mouse_dy += y - self.mouse_y
                    self._down_moved += abs(x - self.mouse_x) + abs(y - self.mouse_y)
        elif pressed:
            self._dragging = True
            self._down_moved = 0
        else:
            if self._dragging and self._down_moved < MOUSE_CLICK_MOVE_CELLS:
                if btn == 0:
                    self.pressed_events.append(KeyAction.INTERACT)
                elif btn == 1:
                    self.pressed_events.append(KeyAction.JUMP)
                elif btn == 2:
                    self.pressed_events.append(KeyAction.TOGGLE_FLASHLIGHT)
            self._dragging = False

        self.mouse_x, self.mouse_y = x, y

    def pop_mouse_delta(self):
        """Returns and clears accumulated drag-look movement in terminal cells."""
        dx, dy = self.mouse_dx, self.mouse_dy
        self.mouse_dx = 0
        self.mouse_dy = 0
        return (dx, dy)

    def is_action_active(self, action: str) -> bool:
        return action in self.active_actions

    def has_event(self, action: str) -> bool:
        return action in self.pressed_events
