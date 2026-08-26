# Memo — T-03 touched `src/renderer/terminal.py`

Theo,

T-03's done-when required adding the pty terminal-restore test to CI. The roadmap claimed the pty matrix was "already passing" — it was not on master. Reproduced with a real pty: sending SIGTERM while a frame write is in flight kills the process with the terminal left in raw mode + alternate buffer.

Root cause: `_on_fatal_signal` → `restore_terminal()` runs inside the signal handler. If it interrupts an in-flight `sys.stdout.write`, Python raises `RuntimeError("reentrant call inside <_io.BufferedWriter name='<stdout>'>")`, which the bare `except Exception: pass` swallows — no restore bytes are ever emitted.

Fix (minimal, in my PR): emit the restore escape payload via signal-safe `os.write(sys.stdout.fileno(), ...)` instead of buffered `sys.stdout.write`. No behaviour change on graceful paths; mocked unit tests were blind to this because they never exercise real reentrancy.

The new `tests/test_pty_terminal_restore.py` locks all three exit paths (x-key quit, SIGINT, SIGTERM). If you'd rather route the terminal.py change through another ticket/owner, say so and I'll split it into its own PR — but note the pty test will stay red until it lands somewhere.

— Honey Beaumont 🍯 (OpenCode)
