"""
Regression tests for the M2 integration review fixes:
- R1: mute-default audio with V-key / CLI opt-in
- R2: drive-gated headlights (off by default)
- N3: lazy audio tempdir (no filesystem touch until audible need)
- N5: enter_vehicle clears mid-air jump state
"""

import os
import tempfile
import unittest

from src.game import Game
from src.engine.camera import Camera
from src.entities.car import Vehicle, VehicleType
from src.entities.vehicle_controller import VehicleController
from src.audio.soundscape import SoundscapeManager


class TestMuteDefaultAudio(unittest.TestCase):
    def tearDown(self):
        if getattr(self, "_soundscape", None) is not None:
            self._soundscape.cleanup()

    def test_soundscape_disabled_constructs_without_tempdir(self):
        s = SoundscapeManager(enabled=False)
        self._soundscape = s
        self.assertTrue(s.is_muted)
        self.assertIsNone(s.temp_dir)
        self.assertEqual(s.sound_cache, {})

    def test_game_default_is_muted_and_tempdir_free(self):
        game = Game(width=40, height=20)
        try:
            self.assertTrue(game.soundscape.is_muted)
            self.assertFalse(game.soundscape.enabled)
            self.assertIsNone(game.soundscape.temp_dir)
        finally:
            game.soundscape.cleanup()

    def test_unmute_lazily_synthesizes_bank(self):
        s = SoundscapeManager(enabled=False)
        self._soundscape = s
        self.assertIsNone(s.temp_dir)
        unmuted = s.toggle_mute()
        self.assertTrue(unmuted)
        self.assertFalse(s.is_muted)
        # First audible use builds the WAV bank on a background thread (T-39);
        # wait for it, then the tempdir and cache must be populated
        s.join_synthesis()
        self.assertIsNotNone(s.temp_dir)
        self.assertIn("horn", s.sound_cache)
        # Muting again flips state back without destroying the cache
        on_again = s.toggle_mute()
        self.assertFalse(on_again)
        self.assertTrue(s.is_muted)

    def test_cleanup_after_lazy_creation_removes_tempdir(self):
        s = SoundscapeManager(enabled=False)
        s.toggle_mute()
        s.join_synthesis()
        temp_dir = s.temp_dir
        self.assertIsNotNone(temp_dir)
        s.cleanup()
        self.assertFalse(os.path.exists(temp_dir))
        self.assertIsNone(s.temp_dir)


class TestDriveGatedHeadlights(unittest.TestCase):
    def setUp(self):
        self.camera = Camera(x=12.5, y=6.5)
        self.vehicle = Vehicle(x=12.5, y=7.0, vtype=VehicleType.POLICE, heading_dir=(0, 1))
        self.ctrl = VehicleController()

    def test_headlights_default_off(self):
        self.assertFalse(self.camera.headlights_on)

    def test_enter_turns_on_exit_turns_off(self):
        self.ctrl.enter_vehicle(self.vehicle, self.camera)
        self.assertTrue(self.camera.headlights_on)
        self.ctrl.exit_vehicle(self.camera)
        self.assertFalse(self.camera.headlights_on)

    def test_enter_clears_jump_state(self):
        self.camera.is_jumping = True
        self.camera.z_velocity = 2.8
        self.ctrl.enter_vehicle(self.vehicle, self.camera)
        self.assertFalse(self.camera.is_jumping)
        self.assertEqual(self.camera.z_velocity, 0.0)


if __name__ == "__main__":
    unittest.main()
