"""
Regression tests for SGR mouse controls and pure-ASCII monochrome rendering.
"""

import unittest

from src.input.keyboard import KeyboardController, KeyAction
from src.game import Game


def sgr(b, x, y, final):
    return list(f"\033[<{b};{x};{y}{final}")


class TestMouseControl(unittest.TestCase):
    def test_left_click_without_drag_interacts(self):
        """Clean press+release under the click threshold emits INTERACT."""
        kc = KeyboardController()
        kc._consume(sgr(0, 5, 5, "M") + sgr(0, 5, 5, "m"))
        self.assertTrue(kc.has_event(KeyAction.INTERACT))
        self.assertFalse(kc._dragging)

    def test_right_click_toggles_flashlight(self):
        """Clean right-click press+release emits TOGGLE_FLASHLIGHT."""
        kc = KeyboardController()
        kc._consume(sgr(2, 5, 5, "M") + sgr(2, 6, 6, "m"))
        self.assertTrue(kc.has_event(KeyAction.TOGGLE_FLASHLIGHT))

    def test_middle_click_jumps(self):
        """Clean middle-click press+release emits JUMP."""
        kc = KeyboardController()
        kc._consume(sgr(1, 5, 5, "M") + sgr(1, 5, 5, "m"))
        self.assertTrue(kc.has_event(KeyAction.JUMP))

    def test_drag_accumulates_deltas_and_suppresses_click(self):
        """Button-held motion accumulates cell deltas in drag direction and release emits no click."""
        kc = KeyboardController()
        kc._consume(sgr(0, 10, 10, "M"))
        self.assertTrue(kc._dragging)
        kc._consume(sgr(32, 14, 12, "M"))
        dx, dy = kc.pop_mouse_delta()
        self.assertEqual((dx, dy), (4, 2))
        self.assertEqual(kc.pop_mouse_delta(), (0, 0))
        kc._consume(sgr(0, 18, 9, "m"))
        self.assertFalse(kc.has_event(KeyAction.INTERACT))

    def test_motion_without_button_held_is_ignored(self):
        """Hover motion with no button down must not rotate the camera."""
        kc = KeyboardController()
        kc._consume(sgr(35, 3, 3, "M"))
        self.assertEqual(kc.pop_mouse_delta(), (0, 0))

    def test_split_mouse_sequence_across_polls(self):
        """An SGR report split across two consume calls parses once complete."""
        kc = KeyboardController()
        kc._consume(["\033", "[", "<", "0"], now=1.0)
        self.assertEqual(kc.pressed_events, [])
        kc._consume([";", "8", ";", "8", "M"], now=1.01)
        self.assertTrue(kc._dragging)

    def test_wheel_reports(self):
        """Wheel events map to WHEEL_UP / WHEEL_DOWN pressed events."""
        kc = KeyboardController()
        kc._consume(sgr(64, 5, 5, "M") + sgr(65, 5, 5, "M"))
        self.assertTrue(kc.has_event(KeyAction.WHEEL_UP))
        self.assertTrue(kc.has_event(KeyAction.WHEEL_DOWN))

    def test_malformed_sgr_report_is_ignored(self):
        """Garbled SGR payloads must not crash the parser."""
        kc = KeyboardController()
        kc._consume(list("\033[<abc;zzM\033[<0;5M"))
        self.assertEqual(kc.pressed_events, [])

    def test_game_applies_mouse_delta_to_camera(self):
        """Game loop converts drag deltas into yaw rotation via pop_mouse_delta."""
        g = Game(width=64, height=24)
        start_dir = (g.camera.dir.x, g.camera.dir.y)
        g.keyboard.mouse_dx = 10
        g.keyboard.mouse_dy = 0
        g.keyboard.poll_input = lambda: None
        g._process_input(0.016)
        self.assertNotEqual(start_dir, (g.camera.dir.x, g.camera.dir.y))
        self.assertEqual(g.keyboard.pop_mouse_delta(), (0, 0))


if __name__ == "__main__":
    unittest.main()
