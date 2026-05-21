### Prerequisites

- Python 3.9+
- Install dependencies:

```bash
pip install vtk
```


### 3D Timeline Viewer (VTK)

Script: `bunker_vtk_viewer.py`

The viewer plays a sequence of legacy VTK files (one frame per file). It renders point clouds and provides scrubbing and autoplay.

Run (from the project root):

```bash
python bunker_vtk_viewer.py \
  --input-dir ./lidar_vtk \
  --point-size 2.0 \
  --cache-size 8 \
  --autoplay-fps 5
```

Arguments:
- `--input-dir`: Directory containing `.vtk` frames (default: `./lidar`).
- `--point-size`: Point size for rendering point clouds (default: `2.0`).
- `--cache-size`: Number of frames cached in memory (default: `6`).
- `--start`: Start frame index (default: `0`).
- `--bg`: Background color hex (e.g., `#000000`).
- `--autoplay-fps`: If `> 0`, starts autoplay at this FPS; `0` disables.

Controls:
- Left/Right arrow: previous/next frame
- `A`: toggle autoplay
- `Q` or `Esc`: quit
- Slider: scrub to any frame


### LiDAR File Format

- VTK frames are legacy `.vtk` files with dataset type `UNSTRUCTURED_GRID` and binary point data. Many frames represent point clouds (no cells). The viewer converts datasets to renderable points when needed.

