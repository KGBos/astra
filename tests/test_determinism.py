"""Regression tests for seed-reproducible entity spawning and behavior."""

import random
import unittest

from src.entities.pedestrian_manager import PedestrianManager
from src.entities.traffic_manager import TrafficManager
from src.world.city_map import CityMap


def _snapshot(seed, *, vehicle_count=12, pedestrian_count=12, steps=0):
    city = CityMap(width=42, height=42, seed=seed)
    traffic = TrafficManager(city, vehicle_count=vehicle_count)
    pedestrians = PedestrianManager(city, pedestrian_count=pedestrian_count)

    for _ in range(steps):
        traffic.update(0.2)
        pedestrians.update(0.2)
    pedestrians.alert_nearby(10.0, 10.0, radius=100.0)

    vehicles = tuple(
        (
            round(vehicle.x, 8),
            round(vehicle.y, 8),
            vehicle.vtype.value,
            vehicle.dx,
            vehicle.dy,
        )
        for vehicle in traffic.vehicles
    )
    peds = tuple(
        (
            round(ped.x, 8),
            round(ped.y, 8),
            ped.archetype.value,
            ped.dx,
            ped.dy,
            round(ped.walk_speed, 8),
            round(ped.walk_tick, 8),
            round(ped.state_timer, 8),
            ped.speech_bubble,
        )
        for ped in pedestrians.pedestrians
    )
    npcs = tuple(
        (
            npc.name,
            round(npc.x, 8),
            round(npc.y, 8),
            round(npc.walk_timer, 8),
            npc.walk_dir,
        )
        for npc in traffic.npcs
    )
    return city.seed, vehicles, peds, npcs


class TestSeedReproducibility(unittest.TestCase):
    def test_same_seed_reproduces_spawn_and_runtime_entity_state(self):
        first = _snapshot(424242, steps=12)
        second = _snapshot(424242, steps=12)

        self.assertEqual(first, second)

    def test_different_seeds_change_entity_placements(self):
        first = _snapshot(111111)
        second = _snapshot(999999)

        self.assertNotEqual(first[1:3], second[1:3])

    def test_entity_managers_do_not_advance_global_random_state(self):
        random.seed(8675309)
        expected_next = random.random()

        random.seed(8675309)
        _snapshot(123456, steps=3)
        actual_next = random.random()

        self.assertEqual(actual_next, expected_next)

    def test_random_city_seed_is_recorded_and_replayable(self):
        city = CityMap(width=42, height=42, seed=None)
        replay = CityMap(width=42, height=42, seed=city.seed)

        self.assertIsInstance(city.seed, int)
        self.assertEqual(city.walls, replay.walls)
        self.assertEqual(city.floors, replay.floors)
        self.assertEqual(city.spawn_pos, replay.spawn_pos)

    def test_story_npcs_stay_inside_the_320m_city_bounds(self):
        city = CityMap(width=320, height=320, seed=7)
        traffic = TrafficManager(city, vehicle_count=0)

        self.assertGreater(len(traffic.npcs), 0)
        for npc in traffic.npcs:
            self.assertGreaterEqual(npc.x, 0.0)
            self.assertLess(npc.x, city.width)
            self.assertGreaterEqual(npc.y, 0.0)
            self.assertLess(npc.y, city.height)


if __name__ == "__main__":
    unittest.main()
