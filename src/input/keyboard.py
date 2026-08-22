"""
Non-blocking Keyboard input poller and ANSI escape sequence parser for Astra 3D.
"""

import sys
import select
from typing import Set, List


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
    HONK_HORN = "HONK_HORN"
    NUM_1 = "NUM_1"
    NUM_2 = "NUM_2"
    NUM_3 = "NUM_3"
    QUIT = "QUIT"
    PAUSE = "PAUSE"


class KeyboardController:
    def __init__(self):
        self.active_actions: Set[str] = set()
        self.pressed_events: List[str] = []

    def poll_input(self):
        """Non-blocking read of all available stdin bytes and updates action states."""
        self.pressed_events.clear()
        
        # Drain all available input without blocking
        chars = []
        while True:
            # Check if stdin has data ready
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

        if not chars:
            # Decay momentary movement keys when no input arrives
            self.active_actions.clear()
            return

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

    def is_action_active(self, action: str) -> bool:
        return action in self.active_actions

    def has_event(self, action: str) -> bool:
        return action in self.pressed_events
