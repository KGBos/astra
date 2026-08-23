"""
Autonomous Pedestrian Simulation, Archetypes, State Machine & Directional 3D Sprites for Astra 3D.
Author: Darius Thorne (Procedural World & City Generation Specialist 📐)
"""

import math
import random
from enum import Enum
from typing import List, Optional, Tuple

from src.entities.sprite import Sprite
from src.world.city_map import CityMap, FloorType


class PedestrianArchetype(str, Enum):
    CYBERPUNK = "CYBERPUNK"
    CORP_SUIT = "CORP_SUIT"
    STREET_VENDOR = "STREET_VENDOR"
    CYBER_ANDROID = "CYBER_ANDROID"
    CASUAL_CITIZEN = "CASUAL_CITIZEN"
    POLICE_OFFICER = "POLICE_OFFICER"


class PedestrianState(str, Enum):
    WALKING = "WALKING"
    WAITING_AT_CROSSWALK = "WAITING_AT_CROSSWALK"
    CROSSING_STREET = "CROSSING_STREET"
    SITTING = "SITTING"
    BROWSING_SHOP = "BROWSING_SHOP"


# Thematic ambient dialog pools per archetype
ARCHETYPE_DIALOGS = {
    PedestrianArchetype.CYBERPUNK: [
        "The neon reflections look wild tonight, choom.",
        "Check out that skyscraper grid... pure voxel beauty.",
        "Watch out for the police drones near the financial core.",
        "Got any spare cyber-credits for a battery recharge?",
        "I heard the data streams in the Cyber-Downtown are blazing."
    ],
    PedestrianArchetype.CORP_SUIT: [
        "I'm late for a board meeting at the Astra Zenith Spire.",
        "Stock futures in neural synthesis are up 14%.",
        "Step aside, citizen. High-priority transaction in progress.",
        "The corporate tax rates in this district are optimal.",
        "Time is bandwidth, and bandwidth is money."
    ],
    PedestrianArchetype.STREET_VENDOR: [
        "Fresh spicy synth-ramen! Steaming hot 24/7!",
        "Best dumplings in the Neon Quarter right here!",
        "Special discount on cyber-snacks today only!",
        "Take a seat and warm up from the rain, friend.",
        "Imported spices straight from the Solaria Docklands!"
    ],
    PedestrianArchetype.CYBER_ANDROID: [
        "Unit 404 status: Optical sensors functioning at 99.8%.",
        "Navigating metropolitan grid. Priority: Path optimization.",
        "Greetings, human. Atmospheric humidity detected.",
        "Maintaining public utility subroutines.",
        "Power cells at 87%. Recharging schedule: 02:00."
    ],
    PedestrianArchetype.CASUAL_CITIZEN: [
        "Astra Metropolis really never sleeps, does it?",
        "I love walking through the Central Plaza when it rains.",
        "Just heading over to the ramen arcade for lunch.",
        "The architecture in this city is breathtaking.",
        "Did you see the latest broadcast on the megastructure billboard?"
    ],
    PedestrianArchetype.POLICE_OFFICER: [
        "Metropolitan Security Patrol. Move along, citizen.",
        "Report any unauthorized cyber-intrusions immediately.",
        "Keep the sidewalks clear of vehicle obstructions.",
        "All district sectors currently rated Code Green.",
        "Stay vigilant in the Industrial Docklands after dark."
    ]
}


class Pedestrian:
    """
    Autonomous pedestrian entity that navigates sidewalks, crosses streets at intersections,
    sits on benches, and responds to player proximity.
    """

    def __init__(
        self,
        x: float,
        y: float,
        archetype: Optional[PedestrianArchetype] = None,
        heading_dir: Optional[Tuple[float, float]] = None,
        walk_speed: Optional[float] = None
    ):
        self.x = float(x)
        self.y = float(y)
        self.archetype = archetype or random.choice(list(PedestrianArchetype))
        
        # Initial heading along cardinal directions
        if heading_dir:
            self.dx, self.dy = heading_dir
        else:
            dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
            self.dx, self.dy = random.choice(dirs)

        self.walk_speed = walk_speed or random.uniform(1.0, 1.8)
        self.state = PedestrianState.WALKING
        self.walk_tick = random.uniform(0.0, 10.0)
        self.state_timer = random.uniform(2.0, 6.0)
        self.speech_bubble: Optional[str] = None
        self.speech_timer = 0.0

        # Colors based on archetype
        self.palette = self._get_palette()

    def _get_palette(self):
        if self.archetype == PedestrianArchetype.CYBERPUNK:
            return {
                "hair": (0, 255, 220),       # Cyan hair/visor
                "torso": (255, 40, 180),     # Hot magenta jacket
                "legs": (40, 40, 60),        # Dark jeans
                "skin": (255, 200, 160)
            }
        elif self.archetype == PedestrianArchetype.CORP_SUIT:
            return {
                "hair": (70, 70, 80),        # Dark sleek hair
                "torso": (30, 45, 70),       # Navy suit
                "legs": (25, 35, 55),        # Dress slacks
                "skin": (245, 210, 180)
            }
        elif self.archetype == PedestrianArchetype.STREET_VENDOR:
            return {
                "hair": (255, 180, 50),      # Golden bandanna
                "torso": (220, 50, 40),      # Red apron
                "legs": (180, 160, 140),     # Khaki pants
                "skin": (250, 195, 150)
            }
        elif self.archetype == PedestrianArchetype.CYBER_ANDROID:
            return {
                "hair": (0, 255, 100),       # Neon green sensor strip
                "torso": (190, 200, 210),    # Chrome chassis
                "legs": (120, 130, 145),     # Titanium limbs
                "skin": (220, 230, 240)
            }
        elif self.archetype == PedestrianArchetype.POLICE_OFFICER:
            return {
                "hair": (30, 50, 100),       # Police cap
                "torso": (20, 70, 160),      # Deep blue armor
                "legs": (15, 25, 45),        # Combat trousers
                "skin": (240, 200, 170)
            }
        else:  # CASUAL_CITIZEN
            return {
                "hair": (140, 80, 40),       # Brown hair
                "torso": (50, 180, 120),     # Emerald hoodie
                "legs": (60, 70, 90),        # Denim
                "skin": (250, 205, 165)
            }

    def get_ambient_quote(self) -> str:
        quotes = ARCHETYPE_DIALOGS.get(self.archetype, ["Hello citizen!"])
        return random.choice(quotes)

    def trigger_speech(self, text: Optional[str] = None, duration: float = 3.5):
        self.speech_bubble = text or self.get_ambient_quote()
        self.speech_timer = duration

    def react_to_horn(self):
        """Reaction when vehicle or player honks horn nearby."""
        reactions = [
            "Hey! Watch it!",
            "I'm walking here!",
            "Jammed audio sensors!",
            "Whoa! Keep it on the road!",
            "Out of the way!"
        ]
        self.trigger_speech(random.choice(reactions), duration=2.5)

    def update(self, dt: float, city_map: CityMap, other_pedestrians: List['Pedestrian']):
        self.walk_tick += dt * 5.0
        if self.speech_timer > 0.0:
            self.speech_timer -= dt
            if self.speech_timer <= 0.0:
                self.speech_bubble = None

        self.state_timer -= dt

        # State Machine
        if self.state == PedestrianState.WALKING:
            self._update_walking(dt, city_map, other_pedestrians)
        elif self.state == PedestrianState.WAITING_AT_CROSSWALK:
            self._update_crosswalk_waiting(dt, city_map)
        elif self.state == PedestrianState.CROSSING_STREET:
            self._update_street_crossing(dt, city_map)
        elif self.state in (PedestrianState.SITTING, PedestrianState.BROWSING_SHOP):
            if self.state_timer <= 0.0:
                # Resume walking
                self.state = PedestrianState.WALKING
                dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
                self.dx, self.dy = random.choice(dirs)
                self.state_timer = random.uniform(4.0, 8.0)

    def _update_walking(self, dt: float, city_map: CityMap, other_pedestrians: List['Pedestrian']):
        look_dist = 1.0
        next_x = self.x + self.dx * self.walk_speed * dt
        next_y = self.y + self.dy * self.walk_speed * dt

        look_ahead_x = self.x + self.dx * look_dist
        look_ahead_y = self.y + self.dy * look_dist
        look_ix = int(look_ahead_x)
        look_iy = int(look_ahead_y)

        # Check if approaching a road / intersection
        ftype_ahead = city_map.get_floor_type(look_ix, look_iy)
        is_road_ahead = ftype_ahead in (FloorType.ROAD_NS, FloorType.ROAD_EW, FloorType.INTERSECTION)

        if is_road_ahead:
            # Check traffic light for pedestrian crossing
            tl_coord = (look_ix, look_iy)
            # Find nearest traffic light
            can_cross = False
            for (tx, ty), tl in city_map.traffic_lights.items():
                if abs(tx - look_ix) <= 2 and abs(ty - look_iy) <= 2:
                    # Pedestrian crosses NS road when EW is green, or crosses EW road when NS is green
                    if self.dx != 0 and tl.is_green_for_ew():
                        can_cross = True
                    elif self.dy != 0 and tl.is_green_for_ns():
                        can_cross = True
                    break

            if can_cross:
                self.state = PedestrianState.CROSSING_STREET
                self.state_timer = 3.0
            else:
                self.state = PedestrianState.WAITING_AT_CROSSWALK
                self.state_timer = random.uniform(1.5, 3.5)
                return

        # Check collision with solid wall or water
        if city_map.is_solid(look_ahead_x, look_ahead_y) or city_map.is_water(look_ahead_x, look_ahead_y):
            # Turn at corner or reverse
            self._pick_alternative_walk_direction(city_map)
            return

        # Move
        self.x = next_x
        self.y = next_y

        # Chance to sit or browse when near plazas
        if self.state_timer <= 0.0:
            if ftype_ahead == FloorType.PARK_GRASS and random.random() < 0.25:
                self.state = PedestrianState.SITTING
                self.state_timer = random.uniform(4.0, 10.0)
            elif ftype_ahead == FloorType.PLAZA_TILES and random.random() < 0.2:
                self.state = PedestrianState.BROWSING_SHOP
                self.state_timer = random.uniform(3.0, 7.0)
            else:
                # 30% chance to turn at intersection/corner
                if random.random() < 0.3:
                    self._pick_turn_direction(city_map)
                self.state_timer = random.uniform(3.0, 6.0)

    def _update_crosswalk_waiting(self, dt: float, city_map: CityMap):
        if self.state_timer <= 0.0:
            # Check light again
            look_ix = int(self.x + self.dx * 1.2)
            look_iy = int(self.y + self.dy * 1.2)
            can_cross = True
            for (tx, ty), tl in city_map.traffic_lights.items():
                if abs(tx - look_ix) <= 2 and abs(ty - look_iy) <= 2:
                    if self.dx != 0: can_cross = tl.is_green_for_ew()
                    elif self.dy != 0: can_cross = tl.is_green_for_ns()
                    break

            if can_cross:
                self.state = PedestrianState.CROSSING_STREET
                self.state_timer = 2.5
            else:
                # 40% chance to turn around rather than wait
                if random.random() < 0.4:
                    self._pick_alternative_walk_direction(city_map)
                    self.state = PedestrianState.WALKING
                    self.state_timer = random.uniform(3.0, 5.0)
                else:
                    self.state_timer = 1.5

    def _update_street_crossing(self, dt: float, city_map: CityMap):
        # Move briskly across road
        self.x += self.dx * self.walk_speed * 1.4 * dt
        self.y += self.dy * self.walk_speed * 1.4 * dt

        ix, iy = int(self.x), int(self.y)
        ftype = city_map.get_floor_type(ix, iy)
        # If reached sidewalk again, switch back to walking
        if ftype in (FloorType.SIDEWALK, FloorType.PLAZA_TILES, FloorType.PARK_GRASS, FloorType.COBBLESTONE):
            self.state = PedestrianState.WALKING
            self.state_timer = random.uniform(3.0, 6.0)

    def _pick_turn_direction(self, city_map: CityMap):
        """Picks a valid 90-degree turn along walkable sidewalks."""
        if self.dx != 0:
            turns = [(0, 1), (0, -1)]
        else:
            turns = [(1, 0), (-1, 0)]
        random.shuffle(turns)
        for tdx, tdy in turns:
            test_x = self.x + tdx * 1.5
            test_y = self.y + tdy * 1.5
            if not city_map.is_solid(test_x, test_y) and not city_map.is_water(test_x, test_y):
                self.dx, self.dy = tdx, tdy
                return

    def _pick_alternative_walk_direction(self, city_map: CityMap):
        """Picks any open walkable direction when blocked."""
        candidates = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        # Remove current direction
        candidates = [c for c in candidates if c != (self.dx, self.dy)]
        random.shuffle(candidates)
        for cdx, cdy in candidates:
            test_x = self.x + cdx * 1.5
            test_y = self.y + cdy * 1.5
            if not city_map.is_solid(test_x, test_y) and not city_map.is_water(test_x, test_y):
                self.dx, self.dy = cdx, cdy
                return
        # If all blocked, reverse
        self.dx = -self.dx
        self.dy = -self.dy

    def get_sprite_for_camera(self, cam_x: float, cam_y: float) -> Sprite:
        """
        Generates dynamic 3D directional animated ASCII sprite based on angle to camera.
        """
        # Direction of pedestrian motion
        p_angle = math.atan2(self.dy, self.dx)
        rel_x = cam_x - self.x
        rel_y = cam_y - self.y
        rel_angle = math.atan2(rel_y, rel_x)

        diff = (rel_angle - p_angle + math.pi * 3) % (math.pi * 2) - math.pi

        is_front = abs(diff) < math.pi * 0.3
        is_rear = abs(diff) > math.pi * 0.7

        # Stride animation step
        stride = int(self.walk_tick) % 2 == 0 if self.state != PedestrianState.SITTING else False
        p = self.palette

        if self.state == PedestrianState.SITTING:
            chars = [
                " (o) ",
                "/[=] ",
                " |_| "
            ]
            fg = [
                [p["hair"] if i in (1, 2, 3) else p["skin"] for i in range(5)],
                [p["torso"] for _ in range(5)],
                [p["legs"] for _ in range(5)]
            ]
            return Sprite(self.x, self.y, f"PED_SIT_{self.archetype.value}", chars, fg, scale_x=0.45, scale_y=0.6)

        if is_front:
            # Front view (facing camera)
            chars = [
                " (..) ",
                " /||\\ ",
                "  ||  " if stride else " /  \\ "
            ]
            fg = [
                [p["hair"] if i in (1, 4) else p["skin"] for i in range(6)],
                [p["torso"] for _ in range(6)],
                [p["legs"] for _ in range(6)]
            ]
            return Sprite(self.x, self.y, f"PED_FRONT_{self.archetype.value}", chars, fg, scale_x=0.45, scale_y=0.7)

        elif is_rear:
            # Rear view (walking away)
            chars = [
                " (##) ",
                " /||\\ ",
                "  ||  " if stride else " /  \\ "
            ]
            fg = [
                [p["hair"] for _ in range(6)],
                [p["torso"] for _ in range(6)],
                [p["legs"] for _ in range(6)]
            ]
            return Sprite(self.x, self.y, f"PED_REAR_{self.archetype.value}", chars, fg, scale_x=0.45, scale_y=0.7)

        else:
            # Side profile
            chars = [
                " (o) ",
                " /|\\ ",
                " / | " if stride else " | \\ "
            ]
            fg = [
                [p["hair"] if i in (1, 2) else p["skin"] for i in range(5)],
                [p["torso"] for _ in range(5)],
                [p["legs"] for _ in range(5)]
            ]
            return Sprite(self.x, self.y, f"PED_SIDE_{self.archetype.value}", chars, fg, scale_x=0.4, scale_y=0.7)
