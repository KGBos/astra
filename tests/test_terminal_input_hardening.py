"""
Regression tests for terminal lifecycle hardening, batched input draining,
and ANSI escape caching introduced by the OpenCode platform performance pass.
"""

import io
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

from src.game import Game
from src.input.keyboard import KeyboardController, KeyAction
from src.renderer.screen_buffer import ScreenBuffer
from src.renderer.terminal import TerminalManager


class TestTerminalLifecycle(unittest.TestCase):
    def test_restore_is_noop_when_never_activated(self):
        """Headless sessions must not leak escape bytes into redirected stdout."""
        out = io.StringIO()
        with redirect_stdout(out):
            TerminalManager().restore_terminal()
        self.assertEqual(out.getvalue(), "")

    def test_enter_skips_escape_setup_for_non_tty(self):
        """Piped stdin must never receive alternate-buffer or mouse-mode codes."""
        out = io.StringIO()
        tm = TerminalManager()
        with mock.patch.object(sys.stdin, "isatty", return_value=False):
            with redirect_stdout(out):
                with tm:
                    pass
        self.assertEqual(out.getvalue(), "")
        self.assertFalse(tm.is_raw)

    def test_restore_reinstalls_previous_signal_handlers(self):
        """SIGWINCH/SIGTERM/SIGHUP handlers present before entry must survive exit."""
        sentinel = lambda sig, frm: None
        recorded = []

        def fake_signal(sig, handler):
            recorded.append((sig, handler))

        tm = TerminalManager()
        with mock.patch.object(sys.stdin, "isatty", return_value=True), \
             mock.patch("termios.tcgetattr", return_value=[0, 0, 0, 0]), \
             mock.patch("tty.setraw"), \
             mock.patch("src.renderer.terminal.signal.getsignal", return_value=sentinel), \
             mock.patch("src.renderer.terminal.signal.signal", side_effect=fake_signal), \
             mock.patch("src.renderer.terminal.atexit.register"):
            with redirect_stdout(io.StringIO()):
                tm.enter_raw_mode()
                self.assertTrue(tm.is_raw)
                with redirect_stdout(io.StringIO()):
                    tm.restore_terminal()

        installed = {sig for sig, _ in recorded}
        restored = [handler for sig, handler in recorded if handler is sentinel]
        self.assertTrue(installed)
        self.assertTrue(restored)
        self.assertFalse(tm.is_raw)

    def test_fatal_signal_handler_restores_then_reraises_default(self):
        """The SIGTERM safety net must restore the terminal before re-raising default."""
        tm = TerminalManager()
        calls = []

        def fake_signal(sig, handler):
            calls.append(handler)

        with mock.patch.object(sys.stdin, "isatty", return_value=True), \
             mock.patch("termios.tcgetattr", return_value=[0, 0, 0, 0]), \
             mock.patch("tty.setraw"), \
             mock.patch("src.renderer.terminal.signal.getsignal", return_value=None), \
             mock.patch("src.renderer.terminal.signal.signal", side_effect=fake_signal), \
             mock.patch("src.renderer.terminal.atexit.register"), \
             mock.patch("os.kill"), \
             redirect_stdout(io.StringIO()):
            tm.enter_raw_mode()
            fatal = calls[-1]
            fatal(15, None)

        self.assertFalse(tm.is_raw)

    def test_restore_is_idempotent(self):
        """Double restore must not raise or re-emit sequences."""
        out = io.StringIO()
        with mock.patch.object(sys.stdin, "isatty", return_value=True), \
             mock.patch("termios.tcgetattr", return_value=[0, 0, 0, 0]), \
             mock.patch("tty.setraw"), \
             mock.patch("src.renderer.terminal.atexit.register"):
            with redirect_stdout(out):
                tm = TerminalManager()
                tm.enter_raw_mode()
                tm.restore_terminal()
                tm.restore_terminal()
        self.assertEqual(out.getvalue().count("\033[?1049l"), 1)

    def test_flush_frame_survives_closed_stdout(self):
        """A closed stdout raises ValueError; flush must swallow it."""
        class ClosedOut:
            def write(self, s):
                raise ValueError("I/O operation on closed file")

            def flush(self):
                pass

        with redirect_stdout(ClosedOut()):
            TerminalManager().flush_frame("\033[Hframe")


class _FakeStdin:
    def __init__(self):
        self.fd = 5

    def fileno(self):
        return self.fd

    def read(self, n):
        return ""


class TestBatchedInputDrain(unittest.TestCase):
    def test_single_os_read_parses_full_mouse_burst(self):
        """A burst of SGR reports drained in one syscall parses completely."""
        fake = _FakeStdin()
        kc = KeyboardController()
        burst = b"\033[<0;5;5M\033[<32;9;7M\033[<0;9;7m"
        with mock.patch("src.input.keyboard.sys.stdin", fake), \
             mock.patch("src.input.keyboard.select.select",
                        side_effect=[([fake], [], []), ([], [], [])]), \
             mock.patch("src.input.keyboard.os.read", return_value=burst):
            kc.poll_input()

        self.assertFalse(kc.has_event(KeyAction.INTERACT))  # drag exceeded click threshold
        self.assertFalse(kc._dragging)
        self.assertEqual(kc.mouse_x, 9)
        self.assertEqual(kc.mouse_y, 7)

    def test_quiet_fd_poll_still_decays_keys(self):
        """When select reports nothing, held keys decay per DECAY_SECONDS."""
        import time as _time
        fake = _FakeStdin()
        kc = KeyboardController()
        kc.active_actions.add(KeyAction.MOVE_FORWARD)
        kc.last_input_time = _time.monotonic() - 1.0
        with mock.patch("src.input.keyboard.sys.stdin", fake), \
             mock.patch("src.input.keyboard.select.select", return_value=([], [], [])):
            kc.poll_input()
        self.assertFalse(kc.is_action_active(KeyAction.MOVE_FORWARD))

    def test_nonfd_stdin_falls_back_to_char_reads(self):
        """stdin without a usable fileno keeps the legacy single-char path."""
        class NoFdStdin:
            def fileno(self):
                raise OSError("not a real file")

            def read(self, n):
                return "a"

        fake = NoFdStdin()
        kc = KeyboardController()
        with mock.patch("src.input.keyboard.sys.stdin", fake), \
             mock.patch("src.input.keyboard.select.select",
                        side_effect=[([fake], [], []), ([], [], [])]):
            kc.poll_input()
        self.assertTrue(kc.is_action_active(KeyAction.STRAFE_LEFT))

    def test_select_failure_is_swallowed(self):
        """A closed/invalid stdin must not crash the poll loop."""
        class DeadStdin:
            def fileno(self):
                return 6

            def read(self, n):
                return ""

        fake = DeadStdin()
        kc = KeyboardController()
        with mock.patch("src.input.keyboard.sys.stdin", fake), \
             mock.patch("src.input.keyboard.select.select",
                        side_effect=ValueError("closed file")):
            kc.poll_input()
        self.assertEqual(kc.pressed_events, [])


class TestAnsiEscapeCache(unittest.TestCase):
    def _paint(self, buf):
        red = (255, 0, 0)
        blue = (0, 0, 255)
        buf.draw_string(0, 0, "AB", fg=red, bg=(10, 10, 10))
        buf.draw_string(2, 0, "CD", fg=blue, bg=None)

    def test_cached_render_is_deterministic(self):
        """Consecutive renders (cache-cold vs cache-warm) produce byte-identical frames."""
        buf1 = ScreenBuffer(width=8, height=2)
        buf2 = ScreenBuffer(width=8, height=2)
        self._paint(buf1)
        self._paint(buf2)
        cold = buf1.render_to_ansi()
        warm = buf2.render_to_ansi()
        warm_again = buf2.render_to_ansi()
        self.assertEqual(cold, warm)
        self.assertEqual(warm, warm_again)
        self.assertIn((255, 0, 0), buf2._fg_cache)
        self.assertIn((10, 10, 10), buf2._bg_cache)

    def test_cache_respects_size_cap(self):
        """Cache growth stops at _CACHE_LIMIT without corrupting output."""
        buf = ScreenBuffer(width=4, height=1)
        for i in range(ScreenBuffer._CACHE_LIMIT + 50):
            buf.set_pixel(0, 0, "x", fg=(i % 256, i % 200, i % 100))
        frame = buf.render_to_ansi()
        self.assertLessEqual(len(buf._fg_cache), ScreenBuffer._CACHE_LIMIT)
        self.assertIn("38;2;", frame)

    def test_full_game_frame_uses_cache_without_behavior_change(self):
        """End-to-end: cached pipeline still emits home/cursor/reset framing."""
        g = Game(width=64, height=24)
        g._update_simulation(0.05)
        g._render_frame()
        frame = g.buffer.render_to_ansi()
        self.assertTrue(frame.startswith("\033[H"))
        self.assertTrue(frame.endswith("\033[0m"))


if __name__ == "__main__":
    unittest.main()
