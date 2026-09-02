"""
NPC Dialogue System, Sidewalk Pedestrians, and Interactive Conversations for Astra 3D.
"""

import math
import random
from typing import List, Tuple, Optional, Dict
from src.entities.sprite import Sprite


class DialogueOption:
    def __init__(self, text: str, response: str, next_options: Optional[List['DialogueOption']] = None):
        self.text = text
        self.response = response
        self.next_options = next_options or []


class NPC:
    def __init__(
        self,
        x: float,
        y: float,
        name: str,
        title: str,
        archetype: str,
        dialogue: List[DialogueOption],
        rng=None
    ):
        self.x = float(x)
        self.y = float(y)
        self.name = name
        self.title = title
        self.archetype = archetype
        self.dialogue = dialogue
        self.rng = rng if rng is not None else random
        self.walk_timer = self.rng.uniform(0.0, 5.0)
        self.walk_dir = self.rng.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
        self.speed = 1.0

        # Colors
        self.primary_color = (
            (255, 60, 180) if archetype == "NETRUNNER" else (
                (255, 200, 50) if archetype == "CHEF" else (
                    (100, 220, 255) if archetype == "EXECUTIVE" else (80, 240, 120)
                )
            )
        )

    def update(self, dt: float, city_map):
        self.walk_timer += dt
        if self.walk_timer >= 4.0:
            self.walk_timer = 0.0
            self.walk_dir = self.rng.choice([(1, 0), (-1, 0), (0, 1), (0, -1), (0, 0)])

        dx, dy = self.walk_dir
        new_x = self.x + dx * self.speed * dt
        new_y = self.y + dy * self.speed * dt

        # Only walk if not solid and stay on sidewalks
        if not city_map.is_solid(new_x, new_y):
            self.x = new_x
            self.y = new_y

    def get_sprite(self) -> Sprite:
        is_anim = int(self.walk_timer * 4) % 2 == 0
        legs = " / \\ " if is_anim else " | | "

        if self.archetype == "CHEF":
            chars = [
                " [CHEF] ",
                "  (o_o) ",
                "  <[#]> ",
                legs
            ]
        elif self.archetype == "NETRUNNER":
            chars = [
                " [CYBER]",
                "  (•_•) ",
                "  /|#|\\ ",
                legs
            ]
        elif self.archetype == "EXECUTIVE":
            chars = [
                " [CORP] ",
                "  (⌐_■) ",
                "  <[X]> ",
                legs
            ]
        else:
            chars = [
                " [CITIZEN]",
                "  (^_^) ",
                "  /| |\\ ",
                legs
            ]

        fg = [
            [(255, 255, 150) for _ in range(8)],
            [(255, 220, 180) for _ in range(8)],
            [self.primary_color for _ in range(8)],
            [(100, 120, 160) for _ in range(8)]
        ]

        return Sprite(self.x, self.y, f"NPC_{self.name}", chars, fg, scale_x=0.0625, scale_y=0.4375)


def build_default_npcs(city_map=None, rng=None) -> List[NPC]:
    """Build the fixed story anchors, filtering any anchor outside the map.

    Story NPCs intentionally remain at authored coordinates so dialogue remains
    discoverable across seeds. When a CityMap is supplied, its dimensions are
    the bounds contract; the anchors are only included when fully in bounds.
    """
    if rng is None:
        rng = random
    npcs = []

    def add_npc(npc):
        if city_map is None or (
            0.0 <= npc.x < city_map.width and 0.0 <= npc.y < city_map.height
        ):
            npcs.append(npc)

    # 1. Kaito the Ramen Master (near Midtown Ramen Shop at 22, 6)
    kaito_dialogue = [
        DialogueOption(
            "What's good to eat here?",
            "Try our Legendary Cyber Tonkotsu! Simmered with plasma broth for 48 hours. Best fuel in Midtown!"
        ),
        DialogueOption(
            "Any rumors around the city?",
            "Watch out for the neon sports cars on Astra Avenue. They drive like they own the matrix. Also, the Arcade in District 2 has secret retro cabinets!"
        ),
        DialogueOption(
            "Can I drive that yellow taxi outside?",
            "Sure! Walk up to any vehicle and press [F] to jump in behind the wheel. Watch the traffic lights!"
        )
    ]
    add_npc(NPC(22.5, 7.5, "Kaito", "Master Ramen Chef", "CHEF", kaito_dialogue, rng=rng))

    # 2. Nyx the Netrunner (Downtown Cyber District at 6, 8)
    nyx_dialogue = [
        DialogueOption(
            "Who are you?",
            "Name's Nyx. I tap into the city's sub-grid telemetry. Astra 3D is rendering at pure 60 FPS under the hood."
        ),
        DialogueOption(
            "How do I use high beams at night?",
            "Toggle [L] to fire your headlights. It cuts through the dark and distance fog."
        ),
        DialogueOption(
            "Tell me about Central Plaza.",
            "Take 1st Uptown Street south to (16, 16). Clean air, green trees, and peaceful fountains away from the skyscrapers."
        )
    ]
    add_npc(NPC(6.5, 8.5, "Nyx", "Cyber Netrunner", "NETRUNNER", nyx_dialogue, rng=rng))

    # 3. Mr. Sterling (Historic Brownstones at 8, 24)
    sterling_dialogue = [
        DialogueOption(
            "Good day, sir.",
            "Welcome to the Historic District! Built during the first metropolis expansion. Real brick, genuine fire escapes."
        ),
        DialogueOption(
            "How is the traffic today?",
            "Congested on Silicon Way! The automated traffic lights keep things flowing, though."
        )
    ]
    add_npc(NPC(8.5, 24.5, "Sterling", "Historic Resident", "EXECUTIVE", sterling_dialogue, rng=rng))

    return npcs
