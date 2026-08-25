"""
Gamma-correct tone mapping and ordered dithering for the ASCII pipeline.

Research basis (2026 state of the art):
- Multiplying sRGB bytes by a shade factor crushes mid-tones (~2x luminance
  error); correct pipelines linearize, multiply, then re-encode. A 256-entry
  LUT per quantized shade bucket keeps this O(1) per channel in CPython.
- Bayer 4x4 ordered dithering between adjacent shade buckets eliminates
  gradient banding in fog/distance shading while staying temporally stable
  (no per-frame shimmer, unlike white noise).

All tables are pure-stdlib, deterministic, and allocation-free after warmup.
"""

import math
from typing import Dict, List, Tuple


# sRGB byte -> linear-light float (2.2 approximation; <1% error vs exact sRGB)
LINEAR_LUT: List[float] = [(i / 255.0) ** 2.2 for i in range(256)]


def _build_encode_lut() -> List[int]:
    """Linear float [0,1] (256 steps) -> sRGB byte."""
    out = []
    for i in range(256):
        l = i / 255.0
        out.append(max(0, min(255, int((l ** (1.0 / 2.2)) * 255.0 + 0.5))))
    return out


_ENCODE_LUT = _build_encode_lut()

# Quantized shade buckets: 1/64 steps keep the LUT cache small (a few hundred
# entries in practice) while making banding between buckets invisible once
# dithered.
_SHADE_QUANT = 64
_shade_cache: Dict[int, List[int]] = {}

# Public read accessor for hot loops: renderers do `lut = SHADE_CACHE.get(q)`
# inline (zero Python-call overhead) and fall back to get_shade_lut() on a
# miss to fill the cache.
SHADE_CACHE = _shade_cache


def shade_quant(shade: float) -> int:
    """Quantizes a shade factor onto the 1/64 LUT-bucket grid."""
    q = int(shade * _SHADE_QUANT + 0.5)
    return 0 if q < 0 else q


# ---- Blend LUTs -------------------------------------------------------------
# For a fixed target color T, precompute 33 rows (q = fd*32) mapping every
# byte c to int(c + (T - c) * q/32). Turns six per-pixel float blends into
# six list indexes. Targets are near-constant per scene (phase-fixed sky
# bands, weather fog colors), so the cache stays tiny; keys quantized to
# 4-bit channels to bound worst-case growth.

_BLEND_CACHE: Dict[Tuple[int, int, int], Tuple[List[int], List[int], List[int]]] = {}


def get_blend_lut(target):
    """(tbl_r, tbl_g, tbl_b): per-channel tables indexed [q][byte], q in 0..32."""
    key = (target[0] & ~3, target[1] & ~3, target[2] & ~3)
    tbls = _BLEND_CACHE.get(key)
    if tbls is None:
        tr, tg, tb = key
        tbls = (
            [[int(c + (tr - c) * q / 32.0) for c in range(256)] for q in range(33)],
            [[int(c + (tg - c) * q / 32.0) for c in range(256)] for q in range(33)],
            [[int(c + (tb - c) * q / 32.0) for c in range(256)] for q in range(33)],
        )
        if len(_BLEND_CACHE) > 64:
            _BLEND_CACHE.clear()
        _BLEND_CACHE[key] = tbls
    return tbls


def get_shade_lut(shade: float) -> List[int]:
    """256-entry sRGB-correct multiplication table for one shade factor.

    lut[c] gives the shaded byte for input byte c. Shade is quantized to
    1/64 steps; the resulting LUTs are cached process-wide.
    """
    q = int(shade * _SHADE_QUANT + 0.5)
    if q < 0:
        q = 0
    lut = _shade_cache.get(q)
    if lut is None:
        f = q / float(_SHADE_QUANT)
        enc = _ENCODE_LUT
        lin = LINEAR_LUT
        lut = [enc[min(255, int(lin[i] * f * 255.0 + 0.5))] for i in range(256)]
        if len(_shade_cache) > 512:
            _shade_cache.clear()
        _shade_cache[q] = lut
    return lut


def add_light_color(base, lr: float, lg: float, lb: float):
    """Additive light contribution onto an sRGB triple, clamped."""
    r = base[0] + lr
    g = base[1] + lg
    b = base[2] + lb
    if r > 255:
        r = 255
    if g > 255:
        g = 255
    if b > 255:
        b = 255
    return (int(r), int(g), int(b))


# Bayer 4x4 ordered-dither matrix normalized to [0,1). Index with [y&3][x&3].
BAYER4 = (
    (0.03125, 0.53125, 0.15625, 0.65625),
    (0.78125, 0.28125, 0.90625, 0.40625),
    (0.21875, 0.71875, 0.09375, 0.59375),
    (0.96875, 0.46875, 0.84375, 0.34375),
)

# Mid-point of the matrix (for zero-mean perturbation)
BAYER_MID = 0.375

# Deterministic hash noise for grain/twinkle (cheap, no random module state)
_NOISE_SEED_MASK = 0xFFFFFFFF


def hash_noise(x: int, y: int, t: int = 0) -> float:
    """Deterministic pseudo-random float [0,1) from integer coords."""
    n = (x * 374761393 + y * 668265263 + t * 1274126177) & _NOISE_SEED_MASK
    n = (n ^ (n >> 13)) & _NOISE_SEED_MASK
    n = (n * 1103515245 + 12345) & _NOISE_SEED_MASK
    return ((n >> 8) & 0xFFFF) / 65536.0


# ---- Value noise / FBM for procedural clouds -------------------------------

def _vhash(ix: int, iy: int, seed: int) -> float:
    """Integer-lattice hash for value noise, output roughly [-1, 1]."""
    n = (ix * 1619 + iy * 31337 + seed * 6971) & 0x7FFFFFFF
    n = ((n << 13) ^ n) & 0x7FFFFFFF
    return ((n * (n * n * 60493 + 19990303) + 1376312589) & 0x7FFFFFFF) / 1073741824.0 - 1.0


def value_noise(x: float, y: float, seed: int = 0) -> float:
    """Bilinear-smoothed value noise in [-1,1]; valid for negative coords."""
    ix = math.floor(x)
    iy = math.floor(y)
    fx = x - ix
    fy = y - iy
    u = fx * fx * (3.0 - 2.0 * fx)
    v = fy * fy * (3.0 - 2.0 * fy)
    a = _vhash(ix, iy, seed)
    b = _vhash(ix + 1, iy, seed)
    c = _vhash(ix, iy + 1, seed)
    d = _vhash(ix + 1, iy + 1, seed)
    return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v


def fbm_noise(x: float, y: float, octaves: int = 3, seed: int = 0) -> float:
    """Fractal Brownian motion sum of value noise, roughly [-1,1]."""
    total = 0.0
    amp = 1.0
    freq = 1.0
    norm = 0.0
    for i in range(octaves):
        total += value_noise(x * freq, y * freq, seed + i * 131) * amp
        norm += amp
        amp *= 0.5
        freq *= 2.13
    return total / norm if norm > 0 else 0.0
