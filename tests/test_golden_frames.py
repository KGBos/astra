"""
Golden-frame regression tests: replays the fixed scenario matrix through the
real Raycaster and fails loudly on any digest drift against
tests/golden/manifest.json - with a cell-level diff (coordinates plus
expected vs actual glyph/fg/bg) read from the canonical frame dumps in
tests/golden/frames/, never a bare "not equal".

Intentional visual change? Regenerate the goldens with ONE command:

    python3 tools/golden_capture.py --write
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.golden_capture import (
    MANIFEST_PATH,
    REGEN_COMMAND,
    SCENARIOS,
    Scenario,
    diff_stored_vs_actual,
    format_diffs,
    frame_digest,
    load_frame_text,
    load_manifest,
    render_scenario,
)

REQUIRED_MODES = ("default", "mono", "nofill")
REQUIRED_WEATHERS = ("clear", "rain", "fog")
MIN_SCENARIO_COUNT = 8


def _load_manifest_or_none():
    try:
        return load_manifest()
    except (FileNotFoundError, UnicodeDecodeError):
        return None


_MANIFEST = _load_manifest_or_none()


def _missing_manifest_message() -> str:
    return (
        "golden manifest missing/unreadable at %s\n"
        "regenerate it with: %s" % (
            os.path.relpath(MANIFEST_PATH, os.getcwd()), REGEN_COMMAND)
    )


def _make_golden_test(scenario: Scenario):
    def test(self: "TestGoldenFrames"):
        if _MANIFEST is None:
            self.fail(_missing_manifest_message())
            return
        entry = _MANIFEST.get("scenarios", {}).get(scenario.name)
        if not entry or not entry.get("digest"):
            self.fail(
                "scenario %r missing from manifest; regenerate with: %s"
                % (scenario.name, REGEN_COMMAND)
            )
            return

        buffer = render_scenario(scenario)
        actual_digest = frame_digest(buffer)
        if actual_digest == entry["digest"]:
            return

        message = [
            "GOLDEN FRAME DRIFT: %s" % scenario.name,
            "  expected digest %s" % entry["digest"],
            "  actual   digest %s" % actual_digest,
        ]
        try:
            stored_text = load_frame_text(scenario.name)
            diffs = diff_stored_vs_actual(stored_text, buffer)
            if diffs:
                message.append(
                    "  %d cells differ; first differences "
                    "(x, y): expected vs got:" % len(diffs)
                )
                message.append(format_diffs(diffs))
            else:
                message.append(
                    "  rendered pixels match the stored frame dump, so only"
                    " the manifest digest is out of date (stale or hand-edited)."
                )
        except (FileNotFoundError, ValueError) as exc:
            message.append(
                "  stored frame dump missing/corrupt"
                " (tests/golden/frames/%s.cells): %s" % (scenario.name, exc)
            )

        control_digest = frame_digest(render_scenario(scenario))
        if control_digest != actual_digest:
            message.append(
                "  WARNING: two fresh renders disagree (%s vs %s); the scene"
                " is non-deterministic - fix harness pinning before"
                " regenerating goldens." % (actual_digest, control_digest)
            )
        message.append("  Intentional visual change? Regenerate goldens with:")
        message.append("      %s" % REGEN_COMMAND)
        self.fail("\n".join(message))

    test.__name__ = "test_golden_%s" % scenario.name
    test.__doc__ = "Golden frame for '%s' must match its stored digest." % scenario.name
    return test


class TestGoldenFrames(unittest.TestCase):
    """One dynamically-generated test per golden scenario (see module tail)."""


if _MANIFEST is not None:
    for _scenario in SCENARIOS:
        setattr(
            TestGoldenFrames,
            "test_golden_%s" % _scenario.name,
            _make_golden_test(_scenario),
        )


class TestGoldenMatrixContract(unittest.TestCase):
    """Guards the ticketed coverage axes of the golden matrix itself."""

    def test_manifest_exists(self):
        if _MANIFEST is None:
            self.fail(_missing_manifest_message())

    def test_matrix_has_minimum_scenarios(self):
        self.assertGreaterEqual(len(SCENARIOS), MIN_SCENARIO_COUNT)

    def test_matrix_spans_time_of_day(self):
        hours = [s.hour for s in SCENARIOS]
        self.assertTrue(any(8.0 <= h < 17.0 for h in hours), "no daytime scenario")
        self.assertTrue(any(17.0 <= h < 20.0 for h in hours), "no sunset scenario")
        self.assertTrue(any(h >= 20.0 or h < 5.0 for h in hours), "no night scenario")

    def test_matrix_spans_weather(self):
        weathers = {s.weather for s in SCENARIOS}
        for required in REQUIRED_WEATHERS:
            self.assertIn(required, weathers)

    def test_matrix_spans_all_render_modes(self):
        modes = {s.mode for s in SCENARIOS}
        for required in REQUIRED_MODES:
            self.assertIn(required, modes)

    def test_matrix_covers_both_viewports(self):
        viewports = {(s.width, s.height) for s in SCENARIOS}
        self.assertIn((80, 32), viewports)
        self.assertIn((160, 50), viewports)

    def test_matrix_covers_headlights_on_and_off(self):
        self.assertEqual({s.headlights for s in SCENARIOS}, {True, False})

    def test_manifest_matches_tool_matrix(self):
        if _MANIFEST is None:
            self.fail(_missing_manifest_message())
            return
        self.assertEqual(
            set(_MANIFEST.get("scenarios", {})),
            {s.name for s in SCENARIOS},
            "manifest scenarios out of sync; regenerate with: %s" % REGEN_COMMAND,
        )

    def test_manifest_documents_notes_and_regen_command(self):
        if _MANIFEST is None:
            self.fail(_missing_manifest_message())
            return
        self.assertTrue(_MANIFEST.get("_notes"), "manifest must carry a _notes list")
        self.assertEqual(_MANIFEST.get("_regen_command"), REGEN_COMMAND)


if __name__ == "__main__":
    unittest.main()
