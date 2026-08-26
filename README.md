# 🏙️ Astra 3D: ASCII First-Person City Explorer

[![Engine](https://img.shields.io/badge/Engine-3D%20Raycasting-cyan.svg)](docs/ARCHITECTURE.md)
[![Framerate](https://img.shields.io/badge/FPS-40.2%20%40%20160x50-yellow.svg)](tools/bench_matrix.py)
[![Dependencies](https://img.shields.io/badge/Dependencies-Zero%20(Pure%20Python)-orange.svg)](main.py)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](AGENTS.md)

**Astra 3D** is a pure ASCII 3D open-world city exploration game and rendering engine built to run natively inside any terminal window on macOS and Linux.

Featuring real-time 3D perspective raycasting, depth-buffered billboarding sprites, dynamic traffic AI with autonomous vehicles, day/night lighting cycles, weather particle effects, and an interactive mini-map GPS radar.

---

## ✨ Features

- **🎮 True 3D First-Person Perspective**:
  - DDA (Digital Differential Analysis) raycasting with variable height walls and $Z$-buffering.
  - Multi-textured facades: Glass Skyscrapers, Cyberpunk Neon Billboards, Historic Brick Brownstones, Ramen Noodle Storefronts, and Industrial Warehouses.
  - Perspective floor and ceiling rendering: asphalt road lanes, crosswalks, sidewalk tiles, park grass, and twilight skies with night starfields.

- **🚗 Dynamic City Life & Traffic Simulation**:
  - Autonomous moving vehicles (Yellow Taxis 🚖, Cyber Sports Sedans 🏎️, Police Cruisers 🚓, City Buses 🚌).
  - Multi-angle directional ASCII sprites (Front, Rear, and Side profiles) with glowing headlights and taillights.
  - Road network with traffic light state machines that cars obey at 4-way intersections.
  - 3D street props: glowing streetlamps, fire hydrants, and park trees.

- **🌗 Dynamic World Simulation**:
  - 24-hour Day/Sunset/Night lighting cycle affecting ambient brightness and color tones.
  - Dynamic weather simulation with animated falling rain streaks and atmospheric fog.

- **🗺️ Heads-Up Display (HUD) & GPS Radar**:
  - Real-time mini-map GPS radar with player heading arrow, building footprints, and vehicle blips.
  - District locator, street name indicator, 8-point compass, speed gauge, and FPS counter.

- **⚡ Zero External Dependencies**:
  - Pure Python 3 standard library (`math`, `time`, `os`, `sys`, `select`, `termios`, `tty`).
  - Optimized virtual screen buffer with stateful TrueColor ANSI escape caching.

---

## 🚀 Quick Start

### 1. Launch Game
```bash
python3 main.py
```

### 2. Autonomous City Tour (Demo Mode)
```bash
python3 main.py --demo
```

### 3. Run Benchmark
```bash
python3 main.py --benchmark
```

### 4. Run Unit Test Suite
```bash
python3 -m unittest discover -s tests
```

### Measured performance

Reference-hardware measurements recorded in `team/cursor/theo-lindqvist/LOGBOOK.md`
on 2026-08-24:

| Viewport | Median FPS |
| :--- | ---: |
| 80×32 | 160.8 |
| 120×40 | 83.6 |
| 160×50 | 40.2 |

The 160×50 result is below the 60 FPS production budget and is a known Phase 1
performance regression. Re-run the matrix with `python3 tools/bench_matrix.py`.

---

## 🕹️ Controls

| Key | Action |
| :--- | :--- |
| `W` / `A` / `S` / `D` | Move Forward / Strafe Left / Move Back / Strafe Right |
| `Q` / `←` / `→` | Turn Left / Turn Right |
| `I` / `K` | Pitch View Up / Down |
| `Shift + W` | Sprint (2× speed, 7.2 m/s) |
| `Space` | Jump (~1 m clearance) |
| `E` or left-click | Talk to a nearby pedestrian or NPC |
| `F` | Enter / exit the nearest vehicle |
| `G` | Cycle radio stations |
| `V` | Toggle audio mute (starts muted; audio is experimental) |
| `L` | Toggle vehicle headlights |
| `M` | Cycle Mini-Map GPS Radar (OFF → NEAR 31 m → FAR 95 m) |
| `T` | Skip Time of Day (Day / Sunset / Night) |
| `R` | Toggle Weather (Clear / Rain / Fog) |
| `N` | Re-synthesize a new procedural city |
| `U` | Cycle city landmarks / points of interest |
| `B` | Toggle the tactical beam |
| `H` | Honk Horn |
| Mouse drag / click / wheel | Look, interact, jump, beam, or adjust pitch |
| `Esc` / `X` | Exit |

---

## 🌆 Life-Sized World (M5)

The city is now a **320×320 m metropolis measured in honest metres**: your eye is
1.7 m above the sidewalk, walking pace is 3.6 m/s, brownstones stand ~11 m tall and
downtown glass towers reach 40–60 m over true 2 m traffic lanes.

> [!NOTE]
> **Seed breaking change (M5 Cycle A):** existing seeds no longer reproduce their
> pre-M5 layouts. The seed format is unchanged — the same number simply synthesizes
> a different (much bigger) city than it did before M5.

---

## 📂 Project Structure

```
astra/
├── AGENTS.md                  # Project guidelines and team contract
├── STATUS.md                  # Milestone 1 status & roadmap
├── README.md                  # Overview & quickstart
├── main.py                    # CLI executable entrypoint
├── docs/
│   ├── ARCHITECTURE.md        # 3D Raycasting math & rendering pipeline
│   └── CONTROLS.md            # Controls & keybindings manual
├── team/
│   ├── DIRECTORY.md           # Team directory & roster
│   ├── BULLETIN.md            # Live workstream radar & broadcasts
│   └── ...                     # Platform dossiers and inboxes
├── src/
│   ├── audio/
│   │   └── soundscape.py      # Experimental procedural SFX and radio
│   ├── game.py                # Main game loop & state machine
│   ├── engine/
│   │   ├── camera.py          # First-person camera & physics
│   │   ├── lighting.py         # Light pools and illumination
│   │   ├── math3d.py          # Vector math & projection utilities
│   │   ├── raycaster.py        # DDA raycaster, floor/sky & sprite projector
│   │   └── tone.py             # Color and tone helpers
│   ├── input/
│   │   └── keyboard.py        # Non-blocking keyboard and mouse poller
│   ├── world/
│   │   ├── city_map.py        # Procedural metropolis & road topology
│   │   ├── interiors.py        # Enterable storefront and lobby spaces
│   │   ├── procedural_gen.py   # Seeded city and landmark generation
│   │   ├── textures.py        # ASCII textures & RGB palettes
│   │   ├── day_night.py       # 24h lighting cycle & sky gradients
│   │   └── weather.py         # Rain particle system & weather modes
│   ├── entities/
│   │   ├── sprite.py          # 3D Billboarding sprites & street props
│   │   ├── car.py             # Vehicle AI & directional ASCII sprites
│   │   ├── npc.py              # Named NPCs and dialogue
│   │   ├── pedestrian.py       # Pedestrian state and behavior
│   │   ├── pedestrian_manager.py # Crowd coordinator and spawner
│   │   ├── traffic_manager.py # Fleet coordinator & prop spawner
│   │   └── vehicle_controller.py # Driving and cockpit state
│   ├── renderer/
│   │   ├── cockpit_hud.py      # Driving dashboard overlay
│   │   ├── screen_buffer.py   # Virtual pixel grid & ANSI generator
│   │   ├── terminal.py        # Raw mode lifecycle manager
│   │   └── hud.py             # Mini-map radar & telemetry overlay
└── tests/
    └── ...                     # 230 unittest cases covering the engine
```
