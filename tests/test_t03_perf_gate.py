"""
T-03 CI perf gate: two-level floor/budget gating in tools/bench_matrix.py.

Locks the T-03 contract: the hard playability floor fails the build, the
60 FPS guardrail budget is reported on every run but only gates when
--enforce-budget is passed (warn-only until Phase 1 recovers headroom),
and --history appends comparable TSV trend rows.
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SPEC = importlib.util.spec_from_file_location(
    "bench_matrix",
    os.path.join(REPO_ROOT, "tools", "bench_matrix.py"),
)
bench_matrix = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bench_matrix)


class TestClassify(unittest.TestCase):
    def test_above_budget_is_ok(self):
        status, failed = bench_matrix.classify(75.0, 30.0, 60.0)
        self.assertEqual(status, "OK")
        self.assertFalse(failed)

    def test_between_floor_and_budget_warns_only_by_default(self):
        status, failed = bench_matrix.classify(45.0, 30.0, 60.0)
        self.assertIn("warn-only", status)
        self.assertFalse(failed)

    def test_below_floor_always_fails(self):
        status, failed = bench_matrix.classify(20.0, 30.0, 60.0)
        self.assertEqual(status, "BELOW FLOOR")
        self.assertTrue(failed)

    def test_enforce_budget_fails_below_budget(self):
        status, failed = bench_matrix.classify(45.0, 30.0, 60.0,
                                               enforce_budget=True)
        self.assertIn("BELOW BUDGET", status)
        self.assertTrue(failed)

    def test_enforce_budget_passes_at_or_above_budget(self):
        _, failed = bench_matrix.classify(60.0, 30.0, 60.0,
                                          enforce_budget=True)
        self.assertFalse(failed)


class TestHistory(unittest.TestCase):
    def test_append_history_creates_header_then_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "perf_history.tsv")
            results = [(80, 32, 71.5), (120, 40, 63.2)]
            bench_matrix.append_history(path, results)
            bench_matrix.append_history(path, results)
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().strip().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("timestamp_utc\t80x32\t120x40"))
        self.assertRegex(lines[1], r"^\d{4}-\d{2}-\d{2}T.*\t71\.5\t63\.2$")
        self.assertRegex(lines[2], r"^\d{4}-\d{2}-\d{2}T.*\t71\.5\t63\.2$")


class TestCliGate(unittest.TestCase):
    def test_warn_only_mode_exits_zero_with_shortfall_reported(self):
        proc = subprocess.run(
            [sys.executable, "tools/bench_matrix.py",
             "--frames", "4", "--runs", "1", "--sizes", "48x16",
             "--budget", "100000"],
            cwd=REPO_ROOT, capture_output=True, timeout=300,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn(b"warn-only", proc.stdout)
        self.assertIn(b"budget shortfall", proc.stdout)
        self.assertIn(b"PASS", proc.stdout)

    def test_enforce_budget_exits_nonzero_when_unreachable(self):
        proc = subprocess.run(
            [sys.executable, "tools/bench_matrix.py",
             "--frames", "4", "--runs", "1", "--sizes", "48x16",
             "--budget", "100000", "--enforce-budget"],
            cwd=REPO_ROOT, capture_output=True, timeout=300,
        )
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn(b"BELOW BUDGET", proc.stdout)
        self.assertIn(b"FAIL", proc.stdout)

    def test_history_flag_writes_tsv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "perf_history.tsv")
            proc = subprocess.run(
                [sys.executable, "tools/bench_matrix.py",
                 "--frames", "4", "--runs", "1", "--sizes", "48x16",
                 "--history", path],
                cwd=REPO_ROOT, capture_output=True, timeout=300,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().strip().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("48x16", lines[0])


if __name__ == "__main__":
    unittest.main()
