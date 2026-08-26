"""Unit tests for the T-03 two-level perf gate in tools/bench_matrix.py."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.bench_matrix import FPS_BUDGET, FPS_FLOOR, append_history, classify, parse_size


class TestClassify(unittest.TestCase):
    def test_at_or_above_budget_passes(self):
        self.assertEqual(classify(60.0, 30.0, 60.0), ("OK", False))
        self.assertEqual(classify(120.0, 30.0, 60.0), ("OK", False))

    def test_below_budget_warn_only_does_not_fail(self):
        status, failed = classify(40.0, 30.0, 60.0)
        self.assertIn("warn-only", status)
        self.assertFalse(failed)

    def test_below_budget_enforced_fails(self):
        status, failed = classify(40.0, 30.0, 60.0, enforce_budget=True)
        self.assertFalse(failed is False)
        self.assertTrue(failed)

    def test_below_floor_always_fails_even_warn_only(self):
        for enforce in (False, True):
            status, failed = classify(20.0, 30.0, 60.0, enforce_budget=enforce)
            self.assertEqual(status, "BELOW FLOOR")
            self.assertTrue(failed)

    def test_defaults_match_documented_guardrails(self):
        self.assertEqual(FPS_FLOOR, 30.0)
        self.assertEqual(FPS_BUDGET, 60.0)


class TestParseSize(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_size("80x32"), (80, 32))
        self.assertEqual(parse_size("160X50"), (160, 50))

    def test_too_small_rejected(self):
        with self.assertRaises(Exception):
            parse_size("10x5")


class TestHistory(unittest.TestCase):
    def test_appends_header_then_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "perf_history.tsv")
            results = [(80, 32, 160.5), (160, 50, 44.2)]
            append_history(path, results)
            append_history(path, results)
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().strip().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("timestamp_utc\t80x32\t160x50"))
        self.assertRegex(lines[1].split("\t")[1], r"^\d+\.\d$")
        self.assertEqual(lines[2].split("\t")[2], "44.2")

    def test_creates_missing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "nested", "dir", "perf_history.tsv")
            append_history(path, [(80, 32, 100.0)])
            self.assertTrue(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
