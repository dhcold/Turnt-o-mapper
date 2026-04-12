# Turnt-o-Mapper

> A procedural `.map` file generator and Diabotical importer for the game **Turnt**.

<!-- Insert hero screenshot here -->

Turnt-o-Mapper generates ready-to-play for Turnt / ready-to-compile Quake 3 `.map` files.
Design a full map layout in seconds: choose room count, dimensions, corridor width, texture sets, and let the generator handle the geometry.

---

## Features

- **6 layout strategies** — Linear, Zigzag, Snake, Random, Spiral, Multilevel
- **Unified art style** — one cohesive texture set per map with accent outline borders on floors and mint-colored ramp surfaces
- **Interactive 2D preview** — scroll to zoom, drag to pan, double-click to fit
- **Interactive 3D wireframe** — drag to rotate, WASD to pan, scroll to zoom, Iso/Top/Front/Side presets
- **Physics model** — acceleration-based speed simulation per room segment
- **Texture selector** — assign floor / wall / ceiling textures with F/W/C checkboxes; the generator picks one set per map from the enabled pool
- **Diabotical `.rbe` importer** — import existing DBT maps with configurable XYZ scale
- **Auto-update** — checks GitHub Releases on startup and downloads new versions automatically

---

## Download

Pre-built binaries are available on the [Releases](../../releases) page:

| Platform | File |
|---|---|
| Windows | `turnt-o-mapper-windows.exe` |
| macOS | `turnt-o-mapper-macos` |
| Linux | `turnt-o-mapper-linux` |

**Windows:** Double-click the `.exe` — no install needed.

**macOS:** If you see a security warning, right-click → Open, or run:
```bash
xattr -cr turnt-o-mapper-macos && chmod +x turnt-o-mapper-macos && ./turnt-o-mapper-macos
```

**Linux:**
```bash
chmod +x turnt-o-mapper-linux && ./turnt-o-mapper-linux
```

---

## Build from source

**Requirements:** Python 3.10+

```bash
git clone https://github.com/dhcold/Turnt-o-mapper.git
cd Turnt-o-mapper
pip install PyQt6 Pillow
python main.py
```

Optional — texture thumbnails require Pillow (already listed above).

### Build a standalone binary yourself

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name turnt-o-mapper main.py
# Output: dist/turnt-o-mapper[.exe]
```

---

## Usage

### Generate tab
<img width="1887" height="1129" alt="image" src="https://github.com/user-attachments/assets/abc8e11b-a877-4fe6-898f-c72eef3f2347" />
- Set **Number of rooms** (2–100) and choose a **Layout style**
- Adjust **Room size** (min/max width, depth, height)
- Set **Corridor width** (25–100%)
- Optionally enable **Physics model** for acceleration-based level design
- Click **⚡ Generate** — preview updates instantly
   
### DBT Import tab
<img width="1886" height="1179" alt="image" src="https://github.com/user-attachments/assets/cb473cb1-2b10-45b9-9ec1-d3b3005cea75" />
- Select a Diabotical `.rbe` map file
- Configure X/Y/Z scale (Quake units per DBT block)
- Click **Import** to get a `.map`
- **Save** map file
  
### Textures tab
- Assign textures to **Floor**, **Wall**, and **Ceiling** categories using the F/W/C checkboxes
- Set the **Texture folder** path in Settings to see live thumbnails
- The generator picks one unified texture set per map from the enabled pool
- Floor outlines use an accent texture (a different wall texture) for visual detail

### Settings tab
- **Output .map file** — where the generated file is saved
- **Texture folder** — path to your Turnt texture assets (for preview only)
- **Game executable** — path to Turnt binary for the Launch button

### Save & launch
- **Save .map** — writes the current map to the configured output path
- **Open .map** — opens the current map with TB / Radiant / etc
- **Open folder** — opens the output folder in your file manager
- **Launch game** — runs Turnt with `--import=<path>` to preview in-engine

---

## Map pipeline

```
Turnt-o-Mapper  →  .map file  →  Turnt
```

The generated `.map` uses standard Quake 3 brush format and is compatible
with any Q3-based compiler (q3map2, DarkPlaces, etc.).

---

## Project structure

```
main.py                  Entry point (QApplication bootstrap)
turnt_o_mapper/
  app.py                 Main window (PyQt6 UI)
  preview2d.py           2D top-down preview widget
  viewer3d.py            3D wireframe preview widget
  generation.py          Map generation orchestrator + bridge footprint clipping
  layout.py              Room placement, corridor routing, Z collision avoidance
  brushes.py             Quake 3 brush/face geometry (rooms, ramps, outlines)
  entities.py            Spawn, trigger, checkpoint entities + footprint/wall clips
  dbt_import.py          Diabotical .rbe importer
  constants.py           Texture registry, theme colours, geometry params
  models.py              Room & Bridge dataclasses
  config.py              JSON config persistence
  updater.py             GitHub Releases auto-update
  __version__.py         Version string
```

---

## License

MIT
