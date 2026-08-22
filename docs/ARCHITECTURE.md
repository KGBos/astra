# Astra 3D Engine Architecture & Technical Specification

## 1. Overview
Astra 3D is a software 3D first-person open-world city rendering engine and exploration game running entirely inside standard ANSI terminal windows with zero external binary or library dependencies.

```
                  ┌─────────────────────────────────────┐
                  │              main.py                │
                  └──────────────────┬──────────────────┘
                                     │
                               ┌─────▼─────┐
                               │  Game.py  │
                               └─────┬─────┘
          ┌──────────────────────────┼──────────────────────────┐
          │                          │                          │
   ┌──────▼───────┐          ┌───────▼───────┐          ┌───────▼───────┐
   │    World     │          │    Engine     │          │   Renderer    │
   ├──────────────┤          ├───────────────┤          ├───────────────┤
   │ CityMap      │          │ Raycaster     │          │ ScreenBuffer  │
   │ Textures     │          │ Camera (Phys) │          │ TerminalMgr   │
   │ DayNight     │          │ Math3D / DDA  │          │ HUD & Radar   │
   │ Weather      │          │ Z-Buffer      │          │ TrueColor ANSI│
   └──────────────┘          └───────────────┘          └───────────────┘
```

---

## 2. Rendering Pipeline

### 2.1 Perspective Sky & Floor Slicing
- Floor rows below the dynamic camera horizon are perspective-projected using horizontal ray stepping:
  $$\text{rowDist} = \frac{0.5 \cdot \text{screenHeight}}{y - \text{horizonY}}$$
- The floor is mapped to road types (Asphalt, Center Lane Dashes, Crosswalks, Sidewalks, Grass, Plaza Tiles) with distance-attenuated ambient shading.
- Sky rows above the horizon are smoothly colored via a vertical sky gradient (Zenith to Horizon) with dynamic starfield generation at night.

### 2.2 Digital Differential Analysis (DDA) Raycasting
For each screen column $x \in [0, \text{width}-1]$:
1. Compute ray direction $\vec{d} = \vec{\text{dir}} + \vec{\text{plane}} \cdot (2x / \text{width} - 1.0)$.
2. Step through the 2D grid using DDA until a solid wall is hit.
3. Compute perpendicular wall distance:
   $$\text{perpWallDist} = \frac{\text{mapX} - \text{camX} + (1 - \text{stepX}) / 2}{\text{rayDirX}}$$
4. Record `z_buffer[x] = perpWallDist`.
5. Sample the wall texture $(u, v)$ from custom 8x8 ASCII patterns (e.g. Glass Skyscrapers, Neon Billboards, Brownstones) and apply directional + ambient lighting.

### 2.3 3D Billboarding Sprites Projection & Z-Buffering
1. Collect all static street props (Streetlamps, Trees, Fire Hydrants) and moving vehicles (Taxis, Sedans, Police, Buses).
2. Filter sprites within view distance and sort far-to-near.
3. Transform sprite coordinates into camera space using the inverted 2x2 camera matrix:
   $$\begin{pmatrix} X_{\text{trans}} \\ Y_{\text{trans}} \end{pmatrix} = \mathbf{M}^{-1} \begin{pmatrix} X_{\text{sprite}} - X_{\text{cam}} \\ Y_{\text{sprite}} - Y_{\text{cam}} \end{pmatrix}$$
4. For each vertical column of the sprite, test if $Y_{\text{trans}} < \text{z\_buffer}[\text{col}]$.
5. Project directional ASCII vehicle art (Front, Rear, Side profiles) with luminous headlights/taillights.

---

## 3. Dynamic City Life Simulation

### 3.1 Road Grid & Traffic Light State Machine
- Intersections feature automatic traffic lights cycling through `NS_GREEN` $\to$ `NS_YELLOW` $\to$ `EW_GREEN` $\to$ `EW_YELLOW`.
- Autonomous vehicles navigate the 2-lane road grid, follow road directions, decelerate and stop when approaching red lights or leading cars, and accelerate when green.

### 3.2 Day/Night Cycle & Atmospheric Lighting
- 24-hour clock simulating Dawn, Day, Sunset, Dusk, and Night.
- Ambient light coefficient $A \in [0.28, 1.0]$ attenuates RGB colors and wall visibility.
- Streetlamps and neon building signs illuminate autonomously after dark.
- Real-time weather particle engine overlays rain streaks and fog.

---

## 4. Virtual Screen Buffer & Zero-Flicker ANSI Output
- `ScreenBuffer` maintains a 2D matrix of `Pixel(char, fg_rgb, bg_rgb)`.
- The renderer compiles the frame into a single ANSI escape string with stateful color caching to avoid redundant escape sequences.
- Render speeds exceed 200+ FPS in software.
