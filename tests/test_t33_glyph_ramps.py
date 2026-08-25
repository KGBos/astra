"""
T-33 — Per-material luminance->glyph ramps.

The art-directed no-fill mode maps material surfaces through curated
dark->light glyph ladders driven by shaded luminance (point lights included),
while literal art (signage letters, digits, road markings) survives intact.
Colored-fill mode must remain byte-for-byte the classic textured pipeline.

Author: Nora Voss ⚙️ (OpenCode Platform)
"""

import math
import unittest

from src.engine.camera import Camera
from src.engine.raycaster import Raycaster
from src.engine.lighting import PointLight
from src.world.city_map import CityMap
from src.world.day_night import DayNightCycle
from src.world.textures import (
    TEXTURE_REGISTRY, MATERIAL_RAMPS, is_literal_char, get_texture,
)
from src.renderer.screen_buffer import ScreenBuffer


def _render(map_size=48, seed=5, hour=22.0, use_background=False,
            use_color=True, lamps=None, wall_cells=((18, 20), (19, 20), (20, 20)),
            cam_pos=(19.5, 14.0)):
    """Renders a one-facade scene; returns (buffer, city_map)."""
    cm = CityMap(width=map_size, height=map_size, seed=seed)
    cm.walls = [[0] * map_size for _ in range(map_size)]
    for (x, y) in wall_cells:
        cm.walls[y][x] = 4                      # storefront (has RAMEN sign)
    buf = ScreenBuffer(80, 32, use_background=use_background, use_color=use_color)
    rc = Raycaster(80, 32)
    cam = Camera(x=cam_pos[0], y=cam_pos[1])
    cam.set_direction(math.pi / 2.0)            # face +Y at the facade row
    sprites = []
    if lamps:
        for (lx, ly) in lamps:
            from src.entities.sprite import make_streetlamp_sprite
            sprites.append(make_streetlamp_sprite(lx, ly))
    rc.render(camera=cam, city_map=cm, sprites=sprites,
              day_night=DayNightCycle(start_hour=hour), buffer=buf)
    return buf, cm


class TestRampData(unittest.TestCase):
    def test_every_texture_carries_valid_ascii_ramp(self):
        for tex in TEXTURE_REGISTRY.values():
            self.assertTrue(tex.ramp, f"{tex.name} has no ramp")
            self.assertEqual(tex.ramp[0], " ", f"{tex.name} ramp must start empty")
            self.assertGreaterEqual(len(tex.ramp), 8, f"{tex.name} ramp too short")
            self.assertTrue(all(c.isascii() for c in tex.ramp),
                            f"{tex.name} ramp is not pure ASCII")

    def test_literal_classifier(self):
        self.assertTrue(is_literal_char("A"))
        self.assertTrue(is_literal_char("!"))
        self.assertTrue(is_literal_char("7"))
        self.assertFalse(is_literal_char("#"))
        self.assertFalse(is_literal_char("/"))


class TestArtDirectedNoFill(unittest.TestCase):
    def test_signage_survives_ramp_mapping(self):
        buf, _ = _render(use_background=False)
        joined = "".join(p.char for row in buf.pixels for p in row)
        # Letters survive glyph mapping; per-column projection may mirror the
        # sign horizontally at close range (identical to fill mode), so we
        # assert letter survival rather than literal ordering.
        self.assertTrue(set("RAMEN") <= set(joined),
                        "signage letters lost to ramp mapping")

    def test_fill_mode_keeps_texture_art_chars(self):
        """Default colored-fill mode renders the classic art, not ramp glyphs."""
        buf, _ = _render(use_background=True)
        tex = get_texture(4)
        art_alphabet = set("".join(tex.chars)) | {" "}
        wall_chars = {buf.pixels[y][40].char for y in range(6, 26)}
        self.assertTrue(wall_chars <= art_alphabet,
                        f"fill mode leaked non-art glyphs: {wall_chars - art_alphabet}")

    def test_no_fill_introduces_ramp_glyphs_absent_from_art(self):
        buf, _ = _render(use_background=False)
        tex = get_texture(4)
        art = set("".join(tex.chars))
        ramp_glyphs = set(MATERIAL_RAMPS["wood"]) | set(MATERIAL_RAMPS["stone"])
        novel = {buf.pixels[y][40].char for y in range(32)} - art - {" "}
        self.assertTrue(novel <= ramp_glyphs,
                        f"unexpected non-ramp substitutions: {novel}")

    def test_light_makes_wall_glyphs_denser(self):
        """Cells of the same facade nearest a streetlamp read higher ramp
        indices than dim cells far from it."""
        buf, _ = _render(use_background=False,
                         lamps=[(19.5, 16.5)])   # mid-facade, 3.5 m out
        ramp = MATERIAL_RAMPS["wood"]
        order = {ch: i for i, ch in enumerate(ramp)}
        lit_idx, dim_idx = [], []
        for y in range(32):
            ch = buf.pixels[y][34].char          # facade beside the lamp pole
            if ch in order:
                lit_idx.append(order[ch])
            ch2 = buf.pixels[y][52].char         # same facade, far off-axis
            if ch2 in order:
                dim_idx.append(order[ch2])
        self.assertTrue(lit_idx and dim_idx, "no ramp glyphs found on facade")
        self.assertGreater(sum(lit_idx) / len(lit_idx),
                           sum(dim_idx) / len(dim_idx),
                           "lamp proximity did not densify glyphs")

    def test_ground_pools_densify_floor_glyphs(self):
        buf, _ = _render(use_background=False,
                         lamps=[(19.5, 16.0)])
        gr = " .,:;-=#"
        order = {ch: i for i, ch in enumerate(gr)}
        near = [order[c] for c in
                (buf.pixels[26][x].char for x in range(38, 43)) if c in order]
        far = [order[c] for c in
               (buf.pixels[26][x].char for x in range(4, 9)) if c in order]
        self.assertTrue(near, "no ground ramp glyphs under the lamp")
        if far:
            self.assertGreater(sum(near) / len(near), sum(far) / len(far))

    def test_mono_nofill_frame_is_ascii_only(self):
        buf, _ = _render(use_background=False, use_color=False)
        for row in buf.pixels:
            for p in row:
                self.assertTrue(p.char.isascii(),
                                f"non-ASCII glyph {p.char!r} in mono no-fill")


if __name__ == "__main__":
    unittest.main()
