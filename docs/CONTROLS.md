# Astra 3D Controls & Navigation Guide

## 🏙️ Generator v2 — Life-Sized City (M5 Cycle B)
The metropolis is no longer a uniform grid. **Arterials** (14 m, 40–56 m apart,
center dashes marking the median) carry the skyline; **collectors** (9 m) fill
corridors on a 16–24 m rhythm; **local lanes** (5 m) cut through blocks wider
than 34 m. Downtown towers cluster within ~90 m of the map centre (podium
storefronts with setback glass/neon cores), a midrise ring of brownstones,
hotels and neon arcades reaches ~180 m, far quadrants go industrial with
warehouse yards, and an **80+ m central park** sits east of the core with tree
lawns and transverse avenues. The east edge is a **harbor front**: quay wall,
wooden piers, mooring bollards and a marina landmark; NS roads bridge over the
water. Eight landmarks with carved plazas are spaced 150–400 m apart for the `U`
compass cycle.

> [!WARNING]
> **Breaking change:** Generator v2 changes the layout for every seed again
> (seed format unchanged). Pre-Cycle-B seed bookmarks will not reproduce their
> original cities.

## 📏 Honest Units (M5 Cycle A)
The world is measured in true metres: **1 tile = 1 m**. Eye height is 1.7 m on foot
(≈1.0 m seated in a vehicle), walking is 3.6 m/s, sprinting is 7.2 m/s, and a jump
clears ~1 m under 9.8 m/s² gravity. Facade heights are real too: storefronts ~4 m,
brownstones ~11 m, hotels ~18 m, towers 40–60 m. HUD distances and the radar range
are true metres.

> [!WARNING]
> **Breaking change:** with the switch to the 320×320 m mega-map and metre-based
> heights, **pre-M5 seeds generate a different city than they used to** (the seed
> format itself is unchanged). Old saved seed bookmarks will not reproduce their
> original layouts.

## 🚶 Pedestrian & Camera Controls
| Action | Key | Description |
| :--- | :--- | :--- |
| **Move Forward** | `W` or `↑` | Walk forward at 3.6 m/s |
| **Move Backward** | `S` or `↓` | Walk backward (0.7×) |
| **Strafe Left** | `A` | Step sideways to the left (0.8×) |
| **Strafe Right** | `D` | Step sideways to the right (0.8×) |
| **Turn Left** | `Q` or `←` | Rotate camera view left |
| **Turn Right** | `→` | Rotate camera view right |
| **Look Up / Down** | `I` / `K` | Pitch camera view upward / downward |
| **Sprint** | `Shift + W` | Sprint at $2.0\times$ movement velocity (7.2 m/s) |
| **Jump** | `Space` | Jump ~1 m high with gravity simulation |

---

## Mouse Controls
| Action | Input | Description |
| :--- | :--- | :--- |
| **Look Around** | `Left-drag` | Drag mouse to turn yaw and pitch the camera |
| **Talk** | `Left-click` / `E` | Interact with focused pedestrian or nearby NPC |
| **Tactical Beam** | `Right-click` | Toggle flashlight beam |
| **Jump** | `Middle-click` | Jump with gravity simulation |
| **Look Up / Down** | `Scroll Wheel` | Nudge camera pitch |

---

## 🏎️ Vehicle Driving Controls
| Action | Key | Description |
| :--- | :--- | :--- |
| **Enter / Exit Vehicle** | `F` | Mount or dismount nearby Taxi, Sedan, Police car, or Bus |
| **Accelerate** | `W` / `↑` | Apply engine throttle (gearbox auto-reverses on brake) |
| **Brake / Reverse** | `S` / `↓` | Apply brakes, then reverse gear |
| **Steer Left / Right** | `A` / `D` | Turn front wheels (speed-sensitive, self-centering) |
| **Turbo Nitro Boost** | `Shift + W` | Engage nitrous oxide injection with speed lines |
| **Toggle Headlights** | `L` | Switch the high-beam lighting cone on/off (auto-on while driving, off when walking) |
| **Honk Car Horn** | `H` | Sound vehicle horn and broadcast alert |
| **Cockpit Dashboard** | Automatic | Speedometer (km/h), gear indicator, tachometer, sirens while driving |

---

## 🏬 World Interaction, Interiors & NPCs
| Action | Key | Description |
| :--- | :--- | :--- |
| **Enter Buildings** | `Walk into a door` | Glowing `EXIT`-bar thresholds are live portals — walk up to one to step inside a themed storefront (Ramen Bar, Arcade, Hotel Lobby) |
| **Exit Buildings** | `Walk to inner door` | Inside, return to the glowing threshold to step back onto the street |
| **Live Windows** | Automatic | Interior windows render the real city outside, from your inside perspective |
| **Talk / Dialogue Choices** | `E` then `1`, `2`, `3` | Start branching conversations with named NPC characters |
| **Leave Conversation** | `Space` / `Esc` | Exit the dialogue box |
| **Tune Radio Station** | `G` | Cycle radio channels (Retrowave, Beats, Jazz, News) |
| **Toggle Audio Mute** | `V` | Master mute/unmute (starts muted; launch with `--audio` to start unmuted) |
| **Cycle Landmarks** | `U` | Inspect the next point of interest |
| **Cycle GPS Radar** | `M` | Cycle the mini-map radar OFF → NEAR (31 m range) → FAR (95 m range); each press steps through zoom along with show/hide |
| **Skip Time of Day** | `T` | Advance clock by 4 hours (Day/Sunset/Night) |
| **Toggle Weather** | `R` | Cycle weather between Clear, Rain, Storm, Fog, Snow, Acid Rain |
| **Re-synthesize City** | `N` | Generate a brand-new procedural metropolis |
| **Exit Game** | `Esc` or `X` | Cleanly restore terminal state and exit |

---

## Engine Rendering Features
- **True-metre projection**: wall slices, sprites, and the floor plane are projected through a FOV-derived pixels-per-metre focal length, so a 40 m tower at 20 m looks exactly as tall as the math says; the eye height (1.7 m / seated 1.0 m) anchors every ground line.
- **Two-tier draw distance**: a detailed raycaster covers the near field, while a coarse "far renderer" simplifies distant masses into a hazy skyline silhouette.
- **Depth-layer overlap**: rays see past shorter buildings and keep drawing taller towers rising behind them (up to 3 layers per column).
- **Pseudo-volumetric props**: vending machines and similar street objects project distinct front/side faces with an angle-dependent corner split — not flat billboards.
- **Live-window portals**: building windows act as transparent portals; the engine renders a secondary exterior view clipped inside each glass opening.
- **Headlight beams**: vehicle headlights cast an angle-dependent brightness cone onto near-field walls at night.

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

# Launch with procedural audio SFX & radio unmuted (default is muted; V toggles)
python3 main.py --audio
```
