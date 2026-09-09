It creates one view for every curtain-wall instance, names each view using the wall element ID, and places all views on a newly created sheet. If the requested sheet number already exists, the script adds a suffix such as CW-001.01.

The layout routine measures the actual viewport sizes and arranges the largest views first. When the views do not fit at the starting scale, it tries progressively smaller drawing sizes, such as 1:75, 1:100, 1:150, and so forth. Check the FinalScale and FitInsideSheetBoundary values returned by the Python node.

The generated views are Section views named as curtain-wall elevations. This avoids creating elevation markers throughout the floor plans and allows each crop volume to be aligned precisely with its wall.

Important limitations

The script processes curtain-wall Wall elements in the active Revit document. It does not process curtain walls inside linked Revit models or mass-based CurtainSystem elements.

Curved curtain walls are shown as orthographic projections based on their Revit wall orientation; they are not unrolled or developed elevations.

If the elevation is looking at the wrong side of every wall, locate this line:

view_direction = normal.Normalize().Negate()

Replace it with:

view_direction = normal.Normalize()

Run the graph in Manual mode and test it on a copy of the project first, because each execution creates a new set of views and a new sheet.

Curtain_Wall_Elevations_To_Single_Sheet_Dynamo.py
Code
