"""
Regression tests locking in recently fixed engine behaviors: seeded regeneration,
deterministic worldgen, split escape parsing, held-key decay, render/simulation
wiring, frame capping, entity spawning, pedestrian dock exits, and CLI health.
"""

import contextlib
import io
import os
import subprocess
import sys
import time
import unittest
from types import SimpleNamespace
from unittest import mock

from src.game import Game
from src.world.city_map import CityMap
from src.input.keyboard import KeyboardController, KeyAction
from src.entities.traffic_manager import TrafficManager
from src.entities.pedestrian import Pedestrian, PedestrianState


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestFixesRegression(unittest.TestCase):
    def test_regenerate_city_with_string_seed(self):
        """Guards the fix where Game.regenerate_city("seed1") crashed instead of rebuilding with an int seed and safe spawn."""
        g = Game(width=64, height=24)
        g.regenerate_city("seed1")
        self.assertIsInstance(g.city_map.seed, int)
        self.assertFalse(g.city_map.is_solid(g.camera.pos.x, g.camera.pos.y))

    def test_city_map_determinism_for_same_seed(self):
        """Guards deterministic procedural generation: identical seeds must yield identical wall grids."""
        m1 = CityMap(width=42, height=42, seed="dup")
        m2 = CityMap(width=42, height=42, seed="dup")
        self.assertEqual(m1.walls, m2.walls)

    def test_flashlight_key_binding_b(self):
        """Guards the fix binding KeyAction.TOGGLE_FLASHLIGHT to the 'b' key press event."""
        kc = KeyboardController()
        kc._consume(["b"])
        self.assertTrue(kc.has_event(KeyAction.TOGGLE_FLASHLIGHT))

    def test_split_escape_sequence_across_polls(self):
        """Guards the fix stashing a lone ESC byte so split arrow-key sequences never emit QUIT."""
        kc2 = KeyboardController()
        kc2._consume(["\033"])
        self.assertEqual(kc2.pressed_events, [])
        self.assertFalse(kc2.has_event(KeyAction.QUIT))
        kc2._consume(["[", "A"])
        self.assertTrue(kc2.has_event(KeyAction.MOVE_FORWARD))
        self.assertFalse(kc2.has_event(KeyAction.QUIT))

    def test_held_key_decay_in_poll_input(self):
        """Guards the fix moving held-key decay into poll_input using last_input_time and DECAY_SECONDS."""
        kc3 = KeyboardController()
        kc3.active_actions.add(KeyAction.MOVE_FORWARD)
        kc3.last_input_time = time.monotonic()
        with mock.patch("src.input.keyboard.select.select", return_value=([], [], [])):
            kc3.poll_input()
        self.assertTrue(kc3.is_action_active(KeyAction.MOVE_FORWARD))
        kc3.active_actions.add(KeyAction.MOVE_FORWARD)
        kc3.last_input_time = time.monotonic() - 1.0
        with mock.patch("src.input.keyboard.select.select", return_value=([], [], [])):
            kc3.poll_input()
        self.assertFalse(kc3.is_action_active(KeyAction.MOVE_FORWARD))

    def test_render_and_simulation_wiring(self):
        """Guards the fix passing weather and flashlight_on into raycaster.render and weather into hud.update."""
        g = Game(width=64, height=24)
        captured = {}
        g.raycaster.render = lambda **kw: captured.update(kw)
        g._render_frame()
        self.assertIs(captured.get("weather"), g.weather)
        self.assertEqual(captured.get("flashlight_on"), g.hud.flashlight_on)

        g2 = Game(width=64, height=24)
        seen = {}
        g2.hud.update = lambda *a, **k: seen.update(k)
        g2._update_simulation(0.016)
        self.assertIn("weather", seen)
        self.assertIs(seen["weather"], g2.weather)

    def test_run_respects_max_frames_headless(self):
        """Guards the frame-cap fix: run(max_frames=N) returns headlessly with total_frames >= N."""
        game = Game(width=40, height=12, target_fps=240, demo_mode=True)
        with contextlib.redirect_stdout(io.StringIO()):
            game.run(max_frames=5)
        self.assertGreaterEqual(game.total_frames, 5)

    def test_traffic_manager_respects_vehicle_count(self):
        """Guards the fix where TrafficManager spawned more vehicles than vehicle_count requested."""
        tm = TrafficManager(CityMap(width=42, height=42, seed=7), vehicle_count=9)
        self.assertEqual(len(tm.vehicles), 9)

    def test_pedestrian_exits_crossing_on_dock_floor(self):
        """Guards the fix where pedestrians stuck in CROSSING_STREET because WOOD_DECK floors did not end crossing."""
        ped = Pedestrian(10.5, 10.5, heading_dir=(1, 0))
        stub = SimpleNamespace(
            get_floor_type=lambda x, y: 10,
            is_solid=lambda x, y: False,
        )
        ped.state = PedestrianState.CROSSING_STREET
        ped._update_street_crossing(0.016, stub)
        self.assertEqual(ped.state, PedestrianState.WALKING)

    def test_cli_benchmark_runs_clean(self):
        """Guards the CLI fix: --seed --benchmark subprocess exits 0 without NameError output."""
        proc = subprocess.run(
            [sys.executable, "main.py", "--seed", "99", "--benchmark"],
            cwd=REPO_ROOT,
            capture_output=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0)
        combined = proc.stdout + proc.stderr
        self.assertNotIn(b"NameError", combined)

    def test_standalone_escape_quits_after_decay(self):
        """Guards the fix where a lone trailing '\033' stashed in _pending never resolved to QUIT after decay."""
        kc4 = KeyboardController()
        kc4._consume(["\033"], now=100.0)
        self.assertFalse(kc4.has_event(KeyAction.QUIT))
        kc4._consume([], now=100.1)
        self.assertFalse(kc4.has_event(KeyAction.QUIT))
        kc4._consume([], now=100.5)
        self.assertTrue(kc4.has_event(KeyAction.QUIT))
        kc4._consume([], now=101.0)
        self.assertFalse(kc4.has_event(KeyAction.QUIT))

    def test_split_arrow_still_works_within_window(self):
        """Guards that a split arrow sequence completed within DECAY_SECONDS still parses without a spurious QUIT."""
        kc5 = KeyboardController()
        kc5._consume(["\033"], now=200.0)
        kc5._consume(["[", "A"], now=200.1)
        self.assertTrue(kc5.has_event(KeyAction.MOVE_FORWARD))
        self.assertFalse(kc5.has_event(KeyAction.QUIT))

    def test_regenerate_preserves_vehicle_count(self):
        """Guards the Cycle C fleet contract: regeneration with the identical
        seed keeps the lane-derived vehicle count stable (auto budget mode)."""
        g = Game(width=64, height=24)
        before = len(g.traffic.vehicles)
        g.regenerate_city(g.city_map.seed)
        self.assertEqual(len(g.traffic.vehicles), before)
        self.assertGreaterEqual(before, 24)


if __name__ == "__main__":
    unittest.main()
