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

## World Interaction & HUD Shortcuts
| Action | Key | Description |
| :--- | :--- | :--- |
| **Toggle GPS Radar** | `M` | Show/hide the top-right mini-map radar |
| **Skip Time of Day** | `T` | Advance clock by 4 hours (Day/Sunset/Night) |
| **Toggle Weather** | `R` | Cycle weather between Clear, Rain, and Fog |
| **Honk Horn** | `H` | Sound vehicle horn and broadcast alert |
| **Exit Game** | `Esc` or `X` | Cleanly restore terminal state and exit |

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

# Launch in monochrome mode (no ANSI colors)
python3 main.py --no-color
```
