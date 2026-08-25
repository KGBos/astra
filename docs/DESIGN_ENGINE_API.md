# Design — Astra as a General ASCII 3D Engine

> **Status**: Proposed (Theo Lindqvist 🧭, Shift 1)
> **Goal**: any 3D environment can be handed to the renderer and displayed in the terminal.
> Astra's city becomes *one scene* rather than *the* scene.

---

## 1. Where we already are

The good news is that the renderer is far less entangled with the city than the file
sizes suggest. The complete surface `Raycaster` uses from the world is **four methods**:

```
city_map.is_solid(fx, fy)         -> bool
city_map.get_wall_type(x, y)      -> int
city_map.get_wall_height(wtype)   -> float
city_map.get_floor_type(x, y)     -> int
```

…plus four optional attributes used as a hot-loop fast path (`walls`, `width`, `height`,
`in_interior`, read via `getattr` at `raycaster.py:317-326`). `Camera` needs exactly one
method (`is_solid`). This is already a de-facto scene interface; it has simply never been
written down or enforced.

`InteriorView` (`interiors.py:239`) is the existing proof: it is a completely different
world representation — a room carved out of a building, with live window portals — and it
already substitutes for `CityMap` at the renderer boundary with no renderer changes.
**We have two scene implementations today and did not notice.**

The genuinely city-coupled component is the HUD, which touches twelve members
(`landmarks`, `districts`, `traffic_lights`, street names, water queries). That is correct
— a GPS radar with district names is game content, not engine.

## 2. The split

```
astra/
  engine/     scene-agnostic: raycaster, camera, materials, LOD, tone, screen buffer, terminal
  scenes/     scene implementations: GridScene, HeightfieldScene, CityScene, InteriorScene
  game/       Astra 3D itself: HUD, traffic, pedestrians, dialogue, radio, driving
```

The engine must not import from `scenes/` or `game/`. Today `procedural_gen.py` imports
entity sprite factories (`procedural_gen.py:33-46`), pointing world → entities, which is a
layering inversion to unwind as part of this work.

## 3. The `Scene` protocol

```python
class Scene(Protocol):
    width: int
    height: int

    def is_solid(self, fx: float, fy: float) -> bool: ...
    def material_at(self, x: int, y: int) -> int: ...        # was get_wall_type
    def height_of(self, material: int) -> float: ...         # was get_wall_height
    def floor_material_at(self, x: int, y: int) -> int: ...  # was get_floor_type
    def sprites(self) -> Sequence[Sprite]: ...
    def materials(self) -> MaterialRegistry: ...
```

Declared as a `typing.Protocol` for static checking, with an ABC available for authors who
want inheritance. On Python 3.8 `Protocol` requires `typing_extensions`, which we will not
add — so the protocol is declared under `TYPE_CHECKING` with a plain-ABC fallback,
preserving the zero-dependency guardrail.

The optional `walls` fast path stays exactly as it is: an opt-in performance contract a
scene may expose, not a requirement.

## 4. `MaterialRegistry` — replacing bare integers

Materials are currently module-level integer constants in `procedural_gen.py`, which is how
we ended up with `WALL_PERIMETER = 5` and `WALL_WAREHOUSE = 5` silently aliasing, and with
`get_texture` masking unknown IDs by falling back to skyscraper glass (`textures.py:643`).

A registry fixes the bug class and is a prerequisite for LOD, which needs a place to hang
mip pyramids and decal tables:

```python
@dataclass(frozen=True)
class Material:
    name: str
    height_m: float
    texture: MipTexture
    decals: Optional[DecalTable] = None
    emissive: bool = False
    transparent: bool = False
```

Registration allocates IDs, so collisions become impossible rather than merely unlikely.
Unknown-ID lookups raise instead of silently rendering glass. Scenes register the materials
they need; the city registers its facades, and a user scene registers whatever it likes.

## 5. Bringing in an arbitrary environment

Three ingestion paths, in increasing order of ambition. Only the first is required for v1.0:

**`GridScene`** — the format that makes the engine usable by anyone. A plain-text or JSON
map: a character grid, a legend mapping characters to materials, a spawn point. Ten lines
of input produce a walkable 3D space. This is the deliverable that demonstrates the engine
claim concretely, and it doubles as the fixture format for renderer tests.

**`HeightfieldScene`** — per-cell floor and ceiling heights instead of uniform-height
walls, unlocking terrain, stairs, and multi-storey interiors. The raycaster already stacks
depth layers (`MAX_LAYERS = 3`), so much of the machinery exists.

**Mesh import (post-v1.0)** — voxelise an OBJ into a `GridScene`. Worth stating as
direction so the interfaces above are not designed in a way that forecloses it, but it is
explicitly out of scope for the first production release.

## 6. Why this ordering matters

The engine split is not a parallel track to the LOD work — it is a **prerequisite**. LOD
needs somewhere to put mip pyramids and decal tables, and that place is `Material`. Doing
the registry first (T-09) means the fidelity work has a clean home; doing it afterwards
means touching every LOD call site twice.

Equally, the split is what makes the whole plan safe: once `Scene` is a fixed contract,
renderer changes can be tested against a tiny synthetic `GridScene` fixture instead of a
320×320 procedural city, which makes the golden-frame harness fast and deterministic.

## 7. Compatibility

`CityMap` keeps every current public method as a thin alias, so no call site in the game
layer breaks and the 211-test suite stays green throughout. The rename to `material_at` /
`height_of` happens behind deprecation shims that are removed in a single later cleanup
ticket, not mid-migration.
