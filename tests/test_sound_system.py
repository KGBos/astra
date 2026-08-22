"""
Unit tests for SoundSystem, Radio stations, and Equalizer animation.
"""

import unittest
from src.audio.sound_system import SoundSystem, RadioStation


class TestSoundSystem(unittest.TestCase):
    def setUp(self):
        self.sound = SoundSystem()

    def test_stations_and_playlist(self):
        self.assertGreater(len(self.sound.stations), 2)
        curr = self.sound.get_current_station()
        self.assertTrue(len(curr.name) > 0)
        self.assertTrue(len(curr.get_now_playing()) > 0)

        # Next station
        next_s = self.sound.next_station()
        self.assertNotEqual(curr.name, next_s.name)

    def test_eq_visualizer(self):
        eq = self.sound.get_eq_visualizer(6)
        self.assertEqual(len(eq), 6)
        self.sound.update(0.5)
        eq2 = self.sound.get_eq_visualizer(6)
        self.assertEqual(len(eq2), 6)


if __name__ == "__main__":
    unittest.main()
