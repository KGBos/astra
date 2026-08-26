"""
Pty-based terminal-restore test matrix (T-03 / v1.0 exit criterion #6).

Spawns the real game inside a pseudo-terminal and proves the terminal is
restored on every exit path: graceful quit, KeyboardInterrupt, and fatal
signals. Restore is verified against the actual escape-byte stream on the
pty master, not mocks.
"""

import os
import pty
import select
import signal
import subprocess
import sys
import time
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ENTER_ALT = b"\x1b[?1049h"
RESTORE = b"\x1b[?1049l"

STARTUP_TIMEOUT = 30.0
EXIT_TIMEOUT = 15.0


def _run_in_pty(argv, finish):
    """Runs `argv` in a fresh pty until `finish(proc, send)` returns.

    Returns (collected_output_bytes, exit_status_or_None)."""
    master, slave = pty.openpty()
    proc = subprocess.Popen(
        argv,
        stdin=slave,
        stdout=slave,
        stderr=slave,
        cwd=REPO_ROOT,
        close_fds=True,
    )
    os.close(slave)

    collected = bytearray()

    def drain(duration=0.2):
        # Poll until `duration` elapses; an idle window just means the game
        # has not written anything this instant.
        end = time.monotonic() + duration
        while time.monotonic() < end:
            try:
                ready, _, _ = select.select([master], [], [], 0.1)
            except InterruptedError:
                continue
            if not ready:
                continue
            try:
                chunk = os.read(master, 65536)
            except OSError:
                return False
            if not chunk:
                return False
            collected.extend(chunk)
        return True

    def send(data):
        os.write(master, data)

    drain(STARTUP_TIMEOUT)
    finish(proc, send)
    status = None
    exit_deadline = time.monotonic() + EXIT_TIMEOUT
    while status is None and time.monotonic() < exit_deadline:
        drain()
        try:
            status = proc.wait(timeout=0.2)
        except subprocess.TimeoutExpired:
            pass
    if status is None:
        proc.kill()
        proc.wait()
        status = "TIMEOUT"
    # Keep draining briefly so any restore bytes flushed right before exit
    # are actually read off the master side of the pty.
    drain(1.0)
    try:
        os.close(master)
    except OSError:
        pass
    return bytes(collected), status


@unittest.skipUnless(os.name == "posix" and hasattr(pty, "openpty"),
                     "requires a POSIX pty")
class TestTerminalRestoreOnExitPaths(unittest.TestCase):

    def _assert_restored(self, output, status, expected_status=None):
        self.assertIn(ENTER_ALT, output,
                      "game never entered raw/alternate-buffer mode")
        if RESTORE not in output:
            tail = output[-400:].decode("utf-8", "replace")
            self.fail(f"terminal was never restored (missing ?1049l); "
                      f"exit status={status!r}; output tail={tail!r}")
        if expected_status is not None:
            self.assertEqual(status, expected_status)

    def test_graceful_quit_via_x_key(self):
        def finish(proc, send):
            send(b"x")
            return None

        out, status = _run_in_pty(
            [sys.executable, "main.py", "--demo", "--width", "48",
             "--height", "20"],
            finish)
        self._assert_restored(out, status, expected_status=0)

    def test_keyboard_interrupt_restores_terminal(self):
        def finish(proc, send):
            proc.send_signal(signal.SIGINT)
            return None

        out, status = _run_in_pty(
            [sys.executable, "main.py", "--demo", "--width", "48",
             "--height", "20"],
            finish)
        self._assert_restored(out, status, expected_status=0)

    def test_sigterm_restores_terminal_then_exits_128_plus_signal(self):
        def finish(proc, send):
            proc.send_signal(signal.SIGTERM)
            return None

        out, status = _run_in_pty(
            [sys.executable, "main.py", "--demo", "--width", "48",
             "--height", "20"],
            finish)
        # The fatal handler restores, re-raises the default disposition, so
        # the process dies by SIGTERM (wait: -15; conventional 128+15 in a
        # shell). Both forms prove nothing swallowed the signal.
        self.assertIn(status, (-signal.SIGTERM, 128 + signal.SIGTERM))
        self._assert_restored(out, status)


if __name__ == "__main__":
    unittest.main()
