"""
Golden-frame regression lock (TASKBOARD ticket T-02).

Renders every scenario from tools/golden_capture.py through the real pipeline
and fails loudly -- with a readable per-cell diff -- if anything changed a
pixel of a locked frame. Goldens live in tests/golden/manifest.json.

Intentional visual change? Recapture in one command:

    python3 tools/golden_capture.py --regenerate

Accidental changes are impossible to miss; intentional ones are cheap to accept.
"""

import hashlib
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

import golden_capture  # noqa: E402  (path set up above)


MANIFEST_ABSENT = (
    "tests/golden/manifest.json is missing. Capture it once with:\n"
    "    python3 tools/golden_capture.py --regenerate"
)


def _load_manifest_or_fail(test):
    try:
        return golden_capture.load_manifest()
    except FileNotFoundError:
        test.fail(MANIFEST_ABSENT)


class GoldenFrameCoverage(unittest.TestCase):
    """The manifest must cover the full promised scenario matrix."""

    def test_manifest_exists_and_matches_harness(self):
        manifest = _load_manifest_or_fail(self)
        entries = manifest.get("scenarios", {})
        names = golden_capture.SCENARIO_NAMES

        self.assertGreaterEqual(
            len(names), 8,
            "scenario matrix shrank below the T-02 minimum of 8 cells")

        for name in names:
            self.assertIn(name, entries,
                          "scenario %r has no golden; regenerate" % name)

        specs = {s[0]: s for s in golden_capture._scenarios()}
        for name, entry in entries.items():
            spec = specs[name]
            self.assertEqual(entry["width"], spec[1], name)
            self.assertEqual(entry["height"], spec[2], name)
            self.assertEqual(entry["mode"], spec[3], name)

    def test_matrix_spans_required_axes(self):
        """Day/night, clear/rain/fog, interior, driving, 3 modes, 2 viewports."""
        names = golden_capture.SCENARIO_NAMES
        joined = " ".join(names)
        self.assertIn("noon", joined)          # day
        self.assertIn("night", joined)         # night
        self.assertIn("rain", joined)          # rain
        self.assertIn("fog", joined)           # fog
        self.assertIn("interior", joined)      # interior
        self.assertIn("driving", joined)       # driving
        for mode in ("blocks", "ascii-color", "ascii-mono"):
            self.assertTrue(any(mode in n for n in names),
                            "no scenario covers mode %r" % mode)
        self.assertTrue(any("80x32" in n for n in names), "no 80x32 scenario")
        self.assertTrue(any("160x50" in n for n in names), "no 160x50 scenario")


class GoldenFramesMatch(unittest.TestCase):
    """The actual pixel lock: any drift fails with a readable diff."""

    def test_every_scenario_digest_matches_manifest(self):
        manifest = _load_manifest_or_fail(self)
        entries = manifest.get("scenarios", {})

        for name in golden_capture.SCENARIO_NAMES:
            with self.subTest(scenario=name):
                entry = entries.get(name)
                if entry is None:
                    self.fail(
                        "no golden captured for %r; regenerate with:\n"
                        "    python3 tools/golden_capture.py --regenerate" % name)

                canonical, digest = golden_capture.render_scenario(name)

                if digest == entry["digest"]:
                    continue

                old_canonical = golden_capture.unpack_frame(entry["frame_b64"])
                changed, total, lines = golden_capture.diff_canonical(
                    old_canonical,
                    canonical,
                    entry["width"], entry["height"],
                    max_lines=12)
                pct = 100.0 * changed / total
                self.fail(
                    "%r drifted from its golden frame\n"
                    "  expected digest %s\n"
                    "  actual   digest %s\n"
                    "  %d / %d cells changed (%.2f%%)\n%s\n"
                    "If this visual change is INTENTIONAL, recapture with:\n"
                    "    python3 tools/golden_capture.py --regenerate"
                    % (name, entry["digest"], digest, changed, total, pct,
                       "\n".join(lines)))


class GoldenManifestIntegrity(unittest.TestCase):
    """Stored payloads must hash to their own digests (no hand-edited frames)."""

    def test_frame_blobs_hash_to_their_digest(self):
        manifest = _load_manifest_or_fail(self)
        for name, entry in manifest.get("scenarios", {}).items():
            with self.subTest(scenario=name):
                canonical = golden_capture.unpack_frame(entry["frame_b64"])
                digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                self.assertEqual(digest, entry["digest"], name)


class HarnessDeterminism(unittest.TestCase):
    """The capture path itself must be reproducible inside one process."""

    def test_repeat_render_is_byte_identical(self):
        canonical_a, digest_a = golden_capture.render_scenario(
            "street-life-dusk-blocks-80x32")
        canonical_b, digest_b = golden_capture.render_scenario(
            "street-life-dusk-blocks-80x32")
        self.assertEqual(digest_a, digest_b)
        self.assertEqual(canonical_a, canonical_b)

    def test_render_is_insensitive_to_prior_rng_consumption(self):
        """Global-RNG churn before a capture must not alter the frame."""
        import random
        state = random.getstate()
        try:
            _, pristine = golden_capture.render_scenario(
                "noon-clear-blocks-80x32")
            random.uniform(0.0, 1.0)  # burn entropy like a sloppy prior test
            random.seed(12345)        # hostile reseed
            _, after_churn = golden_capture.render_scenario(
                "noon-clear-blocks-80x32")
        finally:
            random.setstate(state)
        self.assertEqual(pristine, after_churn)


if __name__ == "__main__":
    unittest.main()
