# 🏙️ Astra 3D: ASCII First-Person City Explorer

[![Engine](https://img.shields.io/badge/Engine-3D%20Raycasting-cyan.svg)](docs/ARCHITECTURE.md)
[![Framerate](https://img.shields.io/badge/FPS-200%2B-brightgreen.svg)](main.py)
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
  - Optimized virtual screen buffer with stateful TrueColor ANSI escape caching delivering **200+ FPS**.

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

---

## 🕹️ Controls

| Key | Action |
| :--- | :--- |
| `W` / `A` / `S` / `D` | Move Forward / Strafe Left / Move Back / Strafe Right |
| `Q` / `E` or `←` / `→` | Turn Left / Turn Right |
| `I` / `K` | Pitch View Up / Down |
| `Shift + W` | Sprint |
| `Space` | Jump |
| `M` | Toggle Mini-Map GPS Radar |
| `T` | Skip Time of Day (Day / Sunset / Night) |
| `R` | Toggle Weather (Clear / Rain / Fog) |
| `H` | Honk Horn |
| `Esc` / `X` | Exit |

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
│   └── antigravity/
│       └── marcus-vance/      # Founding Engine Lead dossier
├── src/
│   ├── game.py                # Main game loop & state machine
│   ├── engine/
│   │   ├── camera.py          # First-person camera & physics
│   │   ├── math3d.py          # Vector math & projection utilities
│   │   └── raycaster.py       # DDA raycaster, floor/sky & sprite projector
│   ├── world/
│   │   ├── city_map.py        # Procedural metropolis & road topology
│   │   ├── textures.py        # ASCII textures & RGB palettes
│   │   ├── day_night.py       # 24h lighting cycle & sky gradients
│   │   └── weather.py         # Rain particle system & weather modes
│   ├── entities/
│   │   ├── sprite.py          # 3D Billboarding sprites & street props
│   │   ├── car.py             # Vehicle AI & directional ASCII sprites
│   │   └── traffic_manager.py # Fleet coordinator & prop spawner
│   ├── renderer/
│   │   ├── screen_buffer.py   # Virtual pixel grid & ANSI generator
│   │   ├── terminal.py        # Raw mode lifecycle manager
│   │   └── hud.py             # Mini-map radar & telemetry overlay
│   └── input/
│       └── keyboard.py        # Non-blocking ANSI escape poller
└── tests/
    ├── test_math3d.py
    ├── test_raycaster.py
    ├── test_city_map.py
    ├── test_entities.py
    └── test_screen_buffer.py
```
