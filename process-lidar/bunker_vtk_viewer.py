#!/usr/bin/env python3
import argparse
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import vtk  # type: ignore
except Exception as e:  # pragma: no cover
    raise SystemExit(
        "This viewer requires the 'vtk' package. Install with: pip install vtk\n"
        f"Import error: {e}"
    )


def find_vtk_files(input_dir: Path) -> List[Path]:
    files = [p for p in sorted(input_dir.glob("*.vtk")) if p.is_file()]
    return files


def parse_timestamp_from_name(name: str) -> Optional[datetime]:
    # Expect formats like: 20250822075825_xxx.vtk or 20250822075825.vtk
    ts_part = name.split("_")[0].split(".")[0]
    if len(ts_part) >= 14 and ts_part[:14].isdigit():
        try:
            return datetime.strptime(ts_part[:14], "%Y%m%d%H%M%S")
        except ValueError:
            return None
    return None


def dataset_to_polydata(dataset: "vtk.vtkDataSet") -> "vtk.vtkPolyData":
    # If already polydata with cells, return as-is
    if isinstance(dataset, vtk.vtkPolyData):
        return dataset

    # Otherwise, convert to polydata with vertices for each point
    poly = vtk.vtkPolyData()
    poly.SetPoints(dataset.GetPoints())

    # Create a vertex for each point so points are renderable
    glyph = vtk.vtkVertexGlyphFilter()
    glyph.SetInputData(poly)
    glyph.Update()
    return glyph.GetOutput()


def read_legacy_vtk(path: Path) -> "vtk.vtkPolyData":
    # Use vtkDataSetReader to handle any legacy dataset type
    reader = vtk.vtkDataSetReader()
    reader.SetFileName(str(path))
    reader.Update()
    data_object = reader.GetOutput()
    if data_object is None or data_object.GetNumberOfPoints() == 0:
        # Fallback to generic reader (rarely needed)
        generic = vtk.vtkGenericDataObjectReader()
        generic.SetFileName(str(path))
        generic.Update()
        data_object = generic.GetOutput()
        if data_object is None:
            raise RuntimeError(f"Failed to read VTK dataset: {path}")

    return dataset_to_polydata(data_object)


class LRUCache:
    def __init__(self, capacity: int) -> None:
        self.capacity = max(1, capacity)
        self._data: "OrderedDict[int, vtk.vtkPolyData]" = OrderedDict()

    def get(self, key: int) -> Optional["vtk.vtkPolyData"]:
        if key in self._data:
            self._data.move_to_end(key)
            return self._data[key]
        return None

    def put(self, key: int, value: "vtk.vtkPolyData") -> None:
        self._data[key] = value
        self._data.move_to_end(key)
        if len(self._data) > self.capacity:
            self._data.popitem(last=False)


class TimelineViewer:
    def __init__(
        self,
        files: List[Path],
        point_size: float,
        cache_size: int,
        start_index: int,
        bg_color: Tuple[float, float, float],
        autoplay_fps: Optional[float],
    ) -> None:
        if not files:
            raise SystemExit("No .vtk files found. Run extractor first or check --input-dir.")

        self.files = files
        self.num_frames = len(files)
        self.index = max(0, min(start_index, self.num_frames - 1))
        self.point_size = point_size
        self.cache = LRUCache(cache_size)
        self.bg_color = bg_color
        self.autoplay_fps = autoplay_fps
        self._timer_id: Optional[int] = None

        # VTK setup
        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(*bg_color)
        self.renwin = vtk.vtkRenderWindow()
        self.renwin.AddRenderer(self.renderer)
        self.iren = vtk.vtkRenderWindowInteractor()
        self.iren.SetRenderWindow(self.renwin)

        # Mapper/actor for frames
        self.mapper = vtk.vtkPolyDataMapper()
        self.actor = vtk.vtkActor()
        self.actor.SetMapper(self.mapper)
        self.actor.GetProperty().SetPointSize(self.point_size)
        self.actor.GetProperty().SetRepresentationToPoints()
        self.actor.GetProperty().RenderPointsAsSpheresOn()
        self.renderer.AddActor(self.actor)

        # Overlays
        self.text_actor = vtk.vtkTextActor()
        self.text_actor.GetTextProperty().SetFontSize(18)
        self.text_actor.GetTextProperty().SetColor(1, 1, 1)
        self.text_actor.SetDisplayPosition(10, 10)
        self.renderer.AddViewProp(self.text_actor)

        self.help_actor = vtk.vtkTextActor()
        self.help_actor.GetTextProperty().SetFontSize(14)
        self.help_actor.GetTextProperty().SetColor(0.8, 0.8, 0.8)
        self.help_actor.SetDisplayPosition(10, 35)
        self.help_actor.SetInput("Left/Right: Prev/Next | A: Autoplay | Q/Esc: Quit")
        self.renderer.AddViewProp(self.help_actor)

        # Slider UI
        self.slider_rep = vtk.vtkSliderRepresentation2D()
        self.slider_rep.SetMinimumValue(0)
        self.slider_rep.SetMaximumValue(self.num_frames - 1)
        self.slider_rep.SetValue(float(self.index))
        self.slider_rep.SetTitleText("Frame")
        self.slider_rep.GetSliderProperty().SetColor(0.9, 0.9, 0.9)
        self.slider_rep.GetTitleProperty().SetColor(0.9, 0.9, 0.9)
        self.slider_rep.GetLabelProperty().SetColor(0.9, 0.9, 0.9)
        self.slider_rep.GetSelectedProperty().SetColor(1.0, 0.3, 0.3)
        self.slider_rep.SetSliderLength(0.02)
        self.slider_rep.SetSliderWidth(0.03)
        self.slider_rep.SetEndCapLength(0.01)
        self.slider_rep.SetEndCapWidth(0.03)
        self.slider_rep.SetTubeWidth(0.005)
        # Positioning in NDC (viewport) coordinates
        self.slider_rep.GetPoint1Coordinate().SetCoordinateSystemToNormalizedDisplay()
        self.slider_rep.GetPoint1Coordinate().SetValue(0.1, 0.1)
        self.slider_rep.GetPoint2Coordinate().SetCoordinateSystemToNormalizedDisplay()
        self.slider_rep.GetPoint2Coordinate().SetValue(0.9, 0.1)

        self.slider_widget = vtk.vtkSliderWidget()
        self.slider_widget.SetInteractor(self.iren)
        self.slider_widget.SetRepresentation(self.slider_rep)
        self.slider_widget.SetAnimationModeToAnimate()
        self.slider_widget.EnabledOn()
        self.slider_widget.AddObserver("EndInteractionEvent", self._on_slider_changed)

        # Key bindings
        self.iren.AddObserver("KeyPressEvent", self._on_key_press)
        self.iren.AddObserver("TimerEvent", self._on_timer)

        # Initial load
        self._update_frame(self.index, reset_camera=True)

    def _format_overlay(self, idx: int) -> str:
        p = self.files[idx]
        ts = parse_timestamp_from_name(p.name)
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if ts else p.name
        return f"Frame {idx + 1}/{self.num_frames} | {ts_str}"

    def _load_frame(self, idx: int) -> "vtk.vtkPolyData":
        cached = self.cache.get(idx)
        if cached is not None:
            return cached
        poly = read_legacy_vtk(self.files[idx])
        # Ensure a stable copy inside cache
        copier = vtk.vtkPolyData()
        copier.DeepCopy(poly)
        self.cache.put(idx, copier)
        return copier

    def _update_frame(self, idx: int, reset_camera: bool = False) -> None:
        idx = max(0, min(idx, self.num_frames - 1))
        poly = self._load_frame(idx)
        self.mapper.SetInputData(poly)
        self.mapper.Update()
        if reset_camera:
            self.renderer.ResetCamera()
        self.text_actor.SetInput(self._format_overlay(idx))
        self.index = idx
        self.slider_rep.SetValue(float(idx))
        self.renwin.Render()

    def _on_slider_changed(self, obj, evt):  # noqa: ANN001, ANN201
        # Snap to nearest integer frame index
        try:
            value = int(round(self.slider_rep.GetValue()))
        except Exception:
            return
        self._update_frame(value, reset_camera=False)

    def _on_key_press(self, obj, evt):  # noqa: ANN001, ANN201
        key = self.iren.GetKeySym()
        if key in ("q", "Escape"):
            self._stop_timer()
            self.iren.TerminateApp()
            return
        if key in ("Right", "KP_Right", "space"):
            self._stop_timer()
            self._update_frame(self.index + 1)
            return
        if key in ("Left", "KP_Left"):
            self._stop_timer()
            self._update_frame(self.index - 1)
            return
        if key in ("a", "A"):
            if self._timer_id is None:
                self._start_timer()
            else:
                self._stop_timer()

    def _start_timer(self) -> None:
        if not self.autoplay_fps or self.autoplay_fps <= 0:
            return
        interval_ms = int(1000.0 / self.autoplay_fps)
        self._timer_id = self.iren.CreateRepeatingTimer(interval_ms)

    def _stop_timer(self) -> None:
        if self._timer_id is not None:
            try:
                self.iren.DestroyTimer(self._timer_id)
            except Exception:
                pass
            self._timer_id = None

    def _on_timer(self, obj, evt):  # noqa: ANN001, ANN201
        next_idx = (self.index + 1) % self.num_frames
        self._update_frame(next_idx)

    def start(self) -> None:
        self.iren.Initialize()
        if self.autoplay_fps and self.autoplay_fps > 0:
            self._start_timer()
        self.renwin.SetWindowName("VTK Timeline Viewer")
        self.renwin.Render()
        self.iren.Start()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Visualize a timeline of legacy .vtk files with a slider and keyboard controls.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path(__file__).parent / "lidar",
        help="Directory containing .vtk frames (default: ./lidar)",
    )
    parser.add_argument(
        "--point-size",
        type=float,
        default=2.0,
        help="Point size for rendering point clouds (default: 2.0)",
    )
    parser.add_argument(
        "--cache-size",
        type=int,
        default=6,
        help="Number of frames to keep in memory (default: 6)",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Start frame index (default: 0)",
    )
    parser.add_argument(
        "--bg",
        type=str,
        default="#000000",
        help="Background color as hex (e.g., #000000) (default: black)",
    )
    parser.add_argument(
        "--autoplay-fps",
        type=float,
        default=0.0,
        help="If >0, start autoplay at this FPS (default: 0 disabled)",
    )
    return parser.parse_args()


def hex_to_rgb_floats(hex_color: str) -> Tuple[float, float, float]:
    c = hex_color.lstrip("#")
    if len(c) == 6:
        r = int(c[0:2], 16) / 255.0
        g = int(c[2:4], 16) / 255.0
        b = int(c[4:6], 16) / 255.0
        return (r, g, b)
    return (0.0, 0.0, 0.0)


def main() -> None:
    args = parse_args()
    input_dir = args.input_dir.resolve()
    files = find_vtk_files(input_dir)
    bg = hex_to_rgb_floats(args.bg)

    viewer = TimelineViewer(
        files=files,
        point_size=args.point_size,
        cache_size=args.cache_size,
        start_index=args.start,
        bg_color=bg,
        autoplay_fps=args.autoplay_fps if args.autoplay_fps and args.autoplay_fps > 0 else None,
    )
    viewer.start()


if __name__ == "__main__":
    main()


