"""
Unit tests for the Radio Tuner hosted on the single production audio engine
(SoundscapeManager). Stations/tracklists/EQ were ported from the M2 branch.
"""

import unittest
from src.audio.soundscape import SoundscapeManager, RadioTuner


class TestRadioTuner(unittest.TestCase):
    def setUp(self):
        self.radio = RadioTuner()

    def test_stations_and_playlist(self):
        self.assertGreater(len(self.radio.stations), 2)
        curr = self.radio.get_current_station()
        self.assertTrue(len(curr.name) > 0)
        self.assertTrue(len(curr.get_now_playing()) > 0)

        # Next station
        next_s = self.radio.next_station()
        self.assertNotEqual(curr.name, next_s.name)

    def test_eq_visualizer(self):
        eq = self.radio.get_eq_visualizer(6)
        self.assertEqual(len(eq), 6)
        self.radio.update(0.5)
        eq2 = self.radio.get_eq_visualizer(6)
        self.assertEqual(len(eq2), 6)

    def test_soundscape_hosts_tuner(self):
        soundscape = SoundscapeManager(enabled=False)
        try:
            station = soundscape.next_station()
            self.assertEqual(station.name, soundscape.get_current_station().name)
            self.assertEqual(len(soundscape.get_eq_visualizer(4)), 4)
            # Station tracklist rotates over time
            before = station.get_now_playing()
            for _ in range(30):
                soundscape.update_radio(station.track_duration + 0.1)
            self.assertNotEqual(before, station.get_now_playing())
        finally:
            soundscape.cleanup()


if __name__ == "__main__":
    unittest.main()
