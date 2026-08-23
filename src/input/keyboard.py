"""
Non-blocking Keyboard input poller and ANSI escape sequence parser for Astra 3D.
"""

import sys
import select
import time
from typing import Optional, Set, List


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
    TOGGLE_MAP = "TOGGLE_MAP"
    TOGGLE_TIME = "TOGGLE_TIME"
    TOGGLE_WEATHER = "TOGGLE_WEATHER"
    REGENERATE_CITY = "REGENERATE_CITY"
    CYCLE_LANDMARKS = "CYCLE_LANDMARKS"
    INTERACT = "INTERACT"
    HONK_HORN = "HONK_HORN"
    TOGGLE_FLASHLIGHT = "TOGGLE_FLASHLIGHT"
    QUIT = "QUIT"
    PAUSE = "PAUSE"


class KeyboardController:
    def __init__(self):
        self.active_actions: Set[str] = set()
        self.pressed_events: List[str] = []
        self._pending: List[str] = []
        self._pending_time: float = 0.0
        self.last_input_time: float = 0.0
        self.DECAY_SECONDS = 0.25

    def poll_input(self):
        """Non-blocking read of all available stdin bytes and updates action states."""
        now = time.monotonic()
        chars = []
        while True:
            r, _, _ = select.select([sys.stdin], [], [], 0.0)
            if not r:
                break
            try:
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
                    if i + 2 < n:
                        code = chars[i + 2]
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
                    # Split escape sequence across polls: stash tail for next batch
                    self._pending = chars[i:]
                    self._pending_time = now
                    break
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
                self.active_actions.add(KeyAction.TURN_RIGHT)
            elif lower == 'i':
                self.active_actions.add(KeyAction.LOOK_UP)
            elif lower == 'k':
                self.active_actions.add(KeyAction.LOOK_DOWN)
            elif ch == ' ':
                self.pressed_events.append(KeyAction.JUMP)
            elif lower == 'm':
                self.pressed_events.append(KeyAction.TOGGLE_MAP)
            elif lower == 't':
                self.pressed_events.append(KeyAction.TOGGLE_TIME)
            elif lower == 'r':
                self.pressed_events.append(KeyAction.TOGGLE_WEATHER)
            elif lower in ('g', 'n'):
                self.pressed_events.append(KeyAction.REGENERATE_CITY)
            elif lower == 'l':
                self.pressed_events.append(KeyAction.CYCLE_LANDMARKS)
            elif lower == 'f':
                self.pressed_events.append(KeyAction.INTERACT)
            elif lower == 'b':
                self.pressed_events.append(KeyAction.TOGGLE_FLASHLIGHT)
            elif lower == 'h':
                self.pressed_events.append(KeyAction.HONK_HORN)
            elif lower == 'p':
                self.pressed_events.append(KeyAction.PAUSE)
            elif lower in ('x', '\x03'):  # 'x' or Ctrl+C
                self.pressed_events.append(KeyAction.QUIT)

            # Check if uppercase for sprint (Shift key pressed)
            if ch in ('W', 'A', 'S', 'D'):
                self.active_actions.add(KeyAction.SPRINT)

            i += 1

    def is_action_active(self, action: str) -> bool:
        return action in self.active_actions

    def has_event(self, action: str) -> bool:
        return action in self.pressed_events
