# Astra 3D Controls & Navigation Guide

## Movement & Camera Controls
| Action | Key | Description |
| :--- | :--- | :--- |
| **Move Forward** | `W` or `↑` | Walk forward in looking direction |
| **Move Backward** | `S` or `↓` | Walk backward |
| **Strafe Left** | `A` | Step sideways to the left |
| **Strafe Right** | `D` | Step sideways to the right |
| **Turn Left** | `Q` or `←` | Rotate camera view left |
| **Turn Right** | `E` or `→` | Rotate camera view right |
| **Look Up** | `I` | Pitch camera view upward |
| **Look Down** | `K` | Pitch camera view downward |
| **Sprint** | `Shift + W` / `W (caps)` | Sprint at $1.8\times$ movement velocity |
| **Jump** | `Space` | Jump with gravity simulation |

---

## Mouse Controls
| Action | Input | Description |
| :--- | :--- | :--- |
| **Look Around** | `Left-drag` | Drag mouse to turn yaw and pitch the camera |
| **Talk** | `Left-click` | Interact with focused pedestrian |
| **Tactical Beam** | `Right-click` | Toggle flashlight beam |
| **Jump** | `Middle-click` | Jump with gravity simulation |
| **Look Up / Down** | `Scroll Wheel` | Nudge camera pitch |

---

## World Interaction & HUD Shortcuts
| Action | Key | Description |
| :--- | :--- | :--- |
| **Enter Buildings** | `Walk into a door` | Glowing `EXIT`-bar thresholds are live portals — walk up to one to step inside |
| **Exit Buildings** | `Walk to inner door` | Inside, return to the glowing threshold to step back onto the street |
| **Live Windows** | Automatic | Interior windows render the real city outside, from your inside perspective |
| **Toggle GPS Radar** | `M` | Show/hide the top-right mini-map radar |
| **Skip Time of Day** | `T` | Advance clock by 4 hours (Day/Sunset/Night) |
| **Toggle Weather** | `R` | Cycle weather between Clear, Rain, and Fog |
| **Honk Horn** | `H` | Sound vehicle horn and broadcast alert |
| **Exit Game** | `Esc` or `X` | Cleanly restore terminal state and exit |

---

## Engine Rendering Features
- **Two-tier draw distance**: a detailed raycaster covers the near field, while a coarse "far renderer" simplifies distant masses into a hazy skyline silhouette.
- **Depth-layer overlap**: rays see past shorter buildings and keep drawing taller towers rising behind them (up to 3 layers per column).
- **Pseudo-volumetric props**: vending machines and similar street objects project distinct front/side faces with an angle-dependent corner split — not flat billboards.
- **Live-window portals**: building windows act as transparent portals; the engine renders a secondary exterior view clipped inside each glass opening.

---

## Command-Line Options
```bash
# Launch interactive exploration (auto-adapts to terminal size)
python3 main.py

# Launch autonomous city tour demo
python3 main.py --demo

# Run performance benchmark (measures raw FPS)
python3 main.py --benchmark

# Launch with custom locked framerate or viewport size
python3 main.py --fps 60 --width 100 --height 40

# Launch in pure-ASCII monochrome mode (no ANSI colors, ASCII-only glyphs)
python3 main.py --no-color

# Launch with colored glyphs on your terminal's own background (no block fills)
python3 main.py --no-fill
```
