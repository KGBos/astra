"""
Unit tests and behavioral simulation verification for Autonomous Pedestrian & Crowd AI.
Author: Darius Thorne (Procedural World & City Generation Specialist 📐)
"""

import unittest
from src.world.city_map import CityMap
from src.entities.pedestrian import (
    Pedestrian,
    PedestrianArchetype,
    PedestrianState,
    ARCHETYPE_DIALOGS
)
from src.entities.pedestrian_manager import PedestrianManager


class TestPedestrians(unittest.TestCase):
    def setUp(self):
        self.city_map = CityMap(width=42, height=42, seed=12345)
        self.ped_manager = PedestrianManager(self.city_map, pedestrian_count=20)

    def test_pedestrian_spawning_and_count(self):
        """PedestrianManager must spawn non-zero pedestrians with valid archetypes."""
        self.assertEqual(len(self.ped_manager.pedestrians), 20)
        for ped in self.ped_manager.pedestrians:
            self.assertIn(ped.archetype, list(PedestrianArchetype))
            self.assertGreater(ped.x, 0.0)
            self.assertGreater(ped.y, 0.0)

    def test_archetype_dialogs_and_quotes(self):
        """All archetypes must have non-empty dialog pools and return valid quotes."""
        for archetype in PedestrianArchetype:
            self.assertIn(archetype, ARCHETYPE_DIALOGS)
            self.assertGreater(len(ARCHETYPE_DIALOGS[archetype]), 0)
            ped = Pedestrian(10.0, 10.0, archetype=archetype)
            quote = ped.get_ambient_quote()
            self.assertTrue(len(quote) > 0)

    def test_directional_sprites(self):
        """Pedestrian sprite generation must dynamically calculate viewing aspect."""
        # Pedestrian walking South (+Y)
        ped = Pedestrian(10.0, 10.0, archetype=PedestrianArchetype.CYBERPUNK, heading_dir=(0, 1))

        # Camera in front of pedestrian (South at 10, 15) -> seeing front
        spr_front = ped.get_sprite_for_camera(cam_x=10.0, cam_y=15.0)
        self.assertIn("FRONT", spr_front.name)
        self.assertGreater(spr_front.width, 0)
        self.assertGreater(spr_front.height, 0)

        # Camera behind pedestrian (North at 10, 5) -> seeing rear
        spr_rear = ped.get_sprite_for_camera(cam_x=10.0, cam_y=5.0)
        self.assertIn("REAR", spr_rear.name)

        # Camera to the side of pedestrian (East at 15, 10) -> seeing side profile
        spr_side = ped.get_sprite_for_camera(cam_x=15.0, cam_y=10.0)
        self.assertIn("SIDE", spr_side.name)

    def test_sitting_state_and_sprite(self):
        """Sitting pedestrians must produce sitting sprites."""
        ped = Pedestrian(15.0, 15.0, archetype=PedestrianArchetype.CASUAL_CITIZEN)
        ped.state = PedestrianState.SITTING
        spr_sit = ped.get_sprite_for_camera(cam_x=15.0, cam_y=18.0)
        self.assertIn("SIT", spr_sit.name)

    def test_walking_movement_and_update(self):
        """Walking update must advance position and stride cycle."""
        ped = self.ped_manager.pedestrians[0]
        init_pos = (ped.x, ped.y)
        init_tick = ped.walk_tick

        for _ in range(5):
            ped.update(0.2, self.city_map, [])
        self.assertNotEqual(init_pos, (ped.x, ped.y))
        self.assertGreater(ped.walk_tick, init_tick)

    def test_proximity_focus_and_interaction(self):
        """Player looking directly at nearby pedestrian must trigger focused interaction."""
        ped = self.ped_manager.pedestrians[0]
        # Place camera 1.5 units behind pedestrian looking straight at them
        cam_x = ped.x - 1.5
        cam_y = ped.y
        dir_x = 1.0  # looking East towards pedestrian
        dir_y = 0.0

        focused = self.ped_manager.get_focused_pedestrian(cam_x, cam_y, dir_x, dir_y, max_dist=3.0)
        self.assertEqual(focused, ped)

        talk_res = self.ped_manager.interact_with_focused(cam_x, cam_y, dir_x, dir_y)
        self.assertIsNotNone(talk_res)
        archetype, quote = talk_res
        self.assertEqual(archetype, ped.archetype.value)
        self.assertTrue(len(quote) > 0)
        self.assertIsNotNone(ped.speech_bubble)

    def test_acoustic_horn_alert(self):
        """Honking horn within radius must cause speech reaction on nearby pedestrians."""
        ped = self.ped_manager.pedestrians[0]
        self.assertIsNone(ped.speech_bubble)

        # Honk right next to pedestrian
        self.ped_manager.alert_nearby(ped.x, ped.y, radius=5.0)
        self.assertIsNotNone(ped.speech_bubble)

    def test_all_sprites_collection(self):
        """Manager must collect all active pedestrian sprites for camera rendering."""
        sprites = self.ped_manager.get_all_sprites_for_camera(cam_x=12.0, cam_y=6.0)
        self.assertGreater(len(sprites), 0)
        for s in sprites:
            self.assertTrue("PED_" in s.name)


if __name__ == "__main__":
    unittest.main()
