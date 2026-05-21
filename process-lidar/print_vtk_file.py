#!/usr/bin/env python3
from pathlib import Path
import tempfile

try:
	import vtk  # type: ignore
except Exception as e:  # pragma: no cover
	raise SystemExit(
		"This script requires the 'vtk' package. Install with: pip install vtk\n"
		f"Import error: {e}"
	)


FILE_PATH = Path("<path-to-single-file")


def pick_typed_output(reader: object) -> "vtk.vtkDatfaObject | None":
	"""Return the first concrete VTK output with points from a legacy reader."""
	getter_names = (
		"GetPolyDataOutput",
		"GetUnstructuredGridOutput",
		"GetStructuredGridOutput",
		"GetRectilinearGridOutput",
		"GetStructuredPointsOutput",
		"GetImageDataOutput",
		"GetOutput",
	)

	for getter_name in getter_names:
		getter = getattr(reader, getter_name, None)
		if getter is None:
			continue

		candidate = getter()
		if candidate is None:
			continue

		if hasattr(candidate, "GetNumberOfPoints"):
			try:
				if candidate.GetNumberOfPoints() > 0:
					return candidate
			except Exception:
				pass

		if not isinstance(candidate, vtk.vtkDataObject):
			continue

		# Keep a concrete data object fallback even when point count is unavailable.
		if candidate.GetClassName() != "vtkDataObject":
			return candidate

	return None


def maybe_unwrap_multipart_vtk(path: Path) -> tuple[Path, Path | None]:
	"""Extract a VTK payload if the file is a multipart/form-data envelope."""
	data = path.read_bytes()
	if not data.startswith(b"--"):
		return path, None

	if b"Content-Disposition:" not in data[:4096]:
		return path, None

	marker = b"# vtk DataFile Version"
	payload_start = data.find(marker)
	if payload_start < 0:
		return path, None

	line_end = data.find(b"\n")
	if line_end < 0:
		return path, None

	boundary_line = data[:line_end].rstrip(b"\r\n")
	payload = data[payload_start:]

	boundary_marker = b"\n" + boundary_line
	boundary_pos = payload.rfind(boundary_marker)
	if boundary_pos > 0:
		payload = payload[:boundary_pos]

	payload = payload.rstrip(b"\r\n")
	if not payload.startswith(marker):
		return path, None

	with tempfile.NamedTemporaryFile(prefix="vtk_payload_", suffix=".vtk", delete=False) as tmp:
		tmp.write(payload)
		tmp_path = Path(tmp.name)

	return tmp_path, tmp_path

def dataset_to_polydata(data_object: "vtk.vtkDataObject") -> "vtk.vtkPolyData":
	polydata = vtk.vtkPolyData.SafeDownCast(data_object)
	if polydata is not None:
		return polydata

	point_set = vtk.vtkPointSet.SafeDownCast(data_object)
	if point_set is not None and point_set.GetPoints() is not None:
		poly = vtk.vtkPolyData()
		poly.SetPoints(point_set.GetPoints())
		glyph = vtk.vtkVertexGlyphFilter()
		glyph.SetInputData(poly)
		glyph.Update()
		return glyph.GetOutput()

	dataset = vtk.vtkDataSet.SafeDownCast(data_object)
	if dataset is not None:
		geometry = vtk.vtkGeometryFilter()
		geometry.SetInputData(dataset)
		geometry.Update()
		output = geometry.GetOutput()
		if output is not None and output.GetNumberOfPoints() > 0:
			return output

	class_name = data_object.GetClassName() if hasattr(data_object, "GetClassName") else type(data_object).__name__
	raise RuntimeError(f"Unsupported VTK output type for rendering: {class_name}")


def read_vtk(path: Path) -> "vtk.vtkPolyData":
	reader_path, cleanup_path = maybe_unwrap_multipart_vtk(path)
	try:
		reader = vtk.vtkDataSetReader()
		reader.SetFileName(str(reader_path))
		reader.Update()
		data_object = pick_typed_output(reader)

		if data_object is None:
			generic = vtk.vtkGenericDataObjectReader()
			generic.SetFileName(str(reader_path))
			generic.Update()
			data_object = pick_typed_output(generic)

		if data_object is None:
			raise RuntimeError(f"Failed to read VTK dataset: {path}")

		return dataset_to_polydata(data_object)
	finally:
		if cleanup_path is not None:
			cleanup_path.unlink(missing_ok=True)


def plot_vtk(path: Path) -> None:
	if not path.exists():
		raise FileNotFoundError(f"File not found: {path}")

	poly = read_vtk(path)

	mapper = vtk.vtkPolyDataMapper()
	mapper.SetInputData(poly)

	actor = vtk.vtkActor()
	actor.SetMapper(mapper)
	actor.GetProperty().SetRepresentationToPoints()
	actor.GetProperty().SetPointSize(2)
	actor.GetProperty().RenderPointsAsSpheresOn()

	renderer = vtk.vtkRenderer()
	renderer.SetBackground(0.08, 0.08, 0.1)
	renderer.AddActor(actor)

	window = vtk.vtkRenderWindow()
	window.SetWindowName(f"VTK Viewer - {path.name}")
	window.SetSize(1200, 800)
	window.AddRenderer(renderer)

	interactor = vtk.vtkRenderWindowInteractor()
	interactor.SetRenderWindow(window)

	renderer.ResetCamera()
	window.Render()
	interactor.Start()


if __name__ == "__main__":
	plot_vtk(FILE_PATH)
