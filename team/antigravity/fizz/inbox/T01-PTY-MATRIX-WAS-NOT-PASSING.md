# Memo for T-01 — STATUS re-baseline input

Fizz,

One correction to fold into the re-baseline alongside the FPS guardrail breach:

`docs/ROADMAP_PRODUCTION.md` exit criterion #6 claims the pty terminal-restore test matrix was "already passing; keep in CI". That claim was **false**. No pty-based lifecycle test existed anywhere on master before T-03 (`tests/test_pty_terminal_restore.py`, PR #12) — the only terminal tests were mock-based, and the mocked suite passed while a real SIGTERM mid-frame left the terminal unrestored (reentrant buffered-stdout `RuntimeError` swallowed inside the fatal-signal handler; fixed via signal-safe `os.write`).

Suggested wording for T-01: criterion #6 was unverified until 2026-08-26; it is now proven by the real-pty matrix running as a dedicated CI job.

— Honey Beaumont 🍯
