#!/usr/bin/env python3
from pathlib import Path

try:
	import vtk  # type: ignore
except Exception as e:  # pragma: no cover
	raise SystemExit(
		"This script requires the 'vtk' package. Install with: pip install vtk\n"
		f"Import error: {e}"
	)

# Set your target .vtk file here.
FILE_PATH = Path("<Path-to-vtk-file>")


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
	reader = vtk.vtkDataSetReader()
	reader.SetFileName(str(path))
	reader.Update()
	data_object = reader.GetOutput()

	if data_object is None or data_object.GetNumberOfPoints() == 0:
		generic = vtk.vtkGenericDataObjectReader()
		generic.SetFileName(str(path))
		generic.Update()
		data_object = generic.GetOutput()

	if data_object is None:
		raise RuntimeError(f"Failed to read VTK dataset: {path}")

	return dataset_to_polydata(data_object)


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
