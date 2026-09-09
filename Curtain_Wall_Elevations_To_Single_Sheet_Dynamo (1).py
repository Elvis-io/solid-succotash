
# Dynamo Python (CPython3) - Revit 2022-2026
# Creates one orthographic curtain-wall view per wall and places all views
# on one sheet.
#
# IN[0] Title Block Type (Family Types node; None = first available)
# IN[1] Sheet Number                     default "CW-001"
# IN[2] Sheet Name                       default "CURTAIN WALL ELEVATIONS"
# IN[3] Starting Scale                   default 50
# IN[4] Crop Margin, mm                  default 300
# IN[5] Viewport Gap, mm                 default 10
# IN[6] Sheet Edge Margin, mm            default 15
# IN[7] Bottom Reserved Area, mm         default 35
# IN[8] Auto-fit by increasing scale     default True
# IN[9] Run                              default True

import clr
import traceback

clr.AddReference("RevitAPI")
clr.AddReference("RevitServices")
clr.AddReference("RevitNodes")

from Autodesk.Revit.DB import *
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

import Revit
clr.ImportExtensions(Revit.Elements)

doc = DocumentManager.Instance.CurrentDBDocument


def IN_or(index, default):
    try:
        return default if IN[index] is None else IN[index]
    except:
        return default


def unwrap(value):
    try:
        return UnwrapElement(value)
    except:
        return value


def mm(value):
    return UnitUtils.ConvertToInternalUnits(float(value), UnitTypeId.Millimeters)


def id_number(element):
    try:
        return int(element.Id.Value)
    except:
        return int(element.Id.IntegerValue)


def clean_name(value):
    text = str(value)
    for character in ['\\', ':', '{', '}', '[', ']', '|', ';', '<', '>', '?', '`', '~']:
        text = text.replace(character, "-")
    return " ".join(text.split()).strip()


def unique_sheet_number(base):
    used = {
        s.SheetNumber.lower()
        for s in FilteredElementCollector(doc).OfClass(ViewSheet)
    }
    base = clean_name(base) or "CW-001"
    number = base
    i = 1
    while number.lower() in used:
        number = "{}.{:02d}".format(base, i)
        i += 1
    return number


def unique_view_name(base, used):
    name = base
    i = 1
    while name.lower() in used:
        i += 1
        name = "{} ({})".format(base, i)
    used.add(name.lower())
    return name


def model_bbox_corners(box):
    points = []
    for x in (box.Min.X, box.Max.X):
        for y in (box.Min.Y, box.Max.Y):
            for z in (box.Min.Z, box.Max.Z):
                points.append(box.Transform.OfPoint(XYZ(x, y, z)))
    return points


def curtain_wall_section_box(wall, crop_margin, depth_margin):
    box = wall.get_BoundingBox(None)
    if box is None:
        raise Exception("No model bounding box.")

    points = model_bbox_corners(box)

    # Wall.Orientation points toward the exterior. Use the opposite direction
    # so the view looks from the exterior back toward the wall.
    normal = wall.Orientation
    normal = XYZ(normal.X, normal.Y, 0.0)

    if normal.GetLength() < 1e-9:
        raise Exception("Could not determine a horizontal wall orientation.")

    view_direction = normal.Normalize().Negate()
    up = XYZ.BasisZ
    right = up.CrossProduct(view_direction).Normalize()

    origin = XYZ(
        sum(p.X for p in points) / 8.0,
        sum(p.Y for p in points) / 8.0,
        sum(p.Z for p in points) / 8.0
    )

    transform = Transform.Identity
    transform.Origin = origin
    transform.BasisX = right
    transform.BasisY = up
    transform.BasisZ = view_direction

    inverse = transform.Inverse
    local = [inverse.OfPoint(p) for p in points]

    section_box = BoundingBoxXYZ()
    section_box.Transform = transform
    section_box.Min = XYZ(
        min(p.X for p in local) - crop_margin,
        min(p.Y for p in local) - crop_margin,
        min(p.Z for p in local) - depth_margin
    )
    section_box.Max = XYZ(
        max(p.X for p in local) + crop_margin,
        max(p.Y for p in local) + crop_margin,
        max(p.Z for p in local) + depth_margin
    )
    return section_box


def viewport_sizes(viewports):
    result = []
    for viewport in viewports:
        outline = viewport.GetBoxOutline()
        p0 = outline.MinimumPoint
        p1 = outline.MaximumPoint
        result.append((p1.X - p0.X, p1.Y - p0.Y))
    return result


def pack(sizes, left, right, bottom, top, gap):
    """Row-pack largest views first. Returns None when they do not fit."""
    order = sorted(
        range(len(sizes)),
        key=lambda i: (-sizes[i][1], -sizes[i][0])
    )
    positions = [None] * len(sizes)
    x = left
    y = top
    row_height = 0.0

    for i in order:
        width, height = sizes[i]

        if width > right - left or height > top - bottom:
            return None

        if x > left and x + width > right:
            x = left
            y -= row_height + gap
            row_height = 0.0

        if y - height < bottom:
            return None

        positions[i] = XYZ(x + width / 2.0, y - height / 2.0, 0.0)
        x += width + gap
        row_height = max(row_height, height)

    return positions


def scale_list(start, auto_fit):
    start = max(1, int(start))
    if not auto_fit:
        return [start]

    standards = [
        20, 25, 50, 75, 100, 125, 150, 200, 250, 300, 400, 500,
        750, 1000, 1500, 2000, 2500, 5000, 10000, 15000, 24000
    ]
    return [start] + [s for s in standards if s > start]


def wrap(element):
    try:
        return element.ToDSType(False)
    except:
        return element


def main():
    if not bool(IN_or(9, True)):
        return {"Status": "Run is False; no changes made."}

    if doc.IsFamilyDocument:
        return {"Status": "Run this graph in a Revit project, not a family."}

    walls = [
        w for w in
        FilteredElementCollector(doc)
        .OfClass(Wall)
        .WhereElementIsNotElementType()
        if w.WallType.Kind == WallKind.Curtain
    ]
    walls.sort(key=id_number)

    if not walls:
        return {"Status": "No curtain-wall Wall instances found."}

    title_block = unwrap(IN_or(0, None))
    if isinstance(title_block, (list, tuple)):
        title_block = title_block[0] if title_block else None

    if title_block is None:
        title_block = (
            FilteredElementCollector(doc)
            .OfCategory(BuiltInCategory.OST_TitleBlocks)
            .WhereElementIsElementType()
            .FirstElement()
        )

    section_type = next(
        (
            t for t in
            FilteredElementCollector(doc).OfClass(ViewFamilyType)
            if t.ViewFamily == ViewFamily.Section
        ),
        None
    )

    if title_block is None:
        return {"Status": "No title-block type is loaded."}
    if section_type is None:
        return {"Status": "No Section view type is available."}

    sheet_number = IN_or(1, "CW-001")
    sheet_name = clean_name(IN_or(2, "CURTAIN WALL ELEVATIONS")) or "CURTAIN WALL ELEVATIONS"
    start_scale = max(1, int(IN_or(3, 50)))
    crop_margin = mm(IN_or(4, 300))
    gap = mm(IN_or(5, 10))
    sheet_margin = mm(IN_or(6, 15))
    bottom_reserve = mm(IN_or(7, 35))
    auto_fit = bool(IN_or(8, True))
    depth_margin = max(crop_margin, mm(500))

    used_view_names = {
        v.Name.lower()
        for v in FilteredElementCollector(doc).OfClass(View)
        if not v.IsTemplate
    }

    created_views = []
    created_viewports = []
    failures = []
    final_scale = start_scale
    fitted = False

    TransactionManager.Instance.ForceCloseTransaction()
    transaction = Transaction(doc, "Create curtain wall elevation sheet")
    transaction.Start()

    try:
        if isinstance(title_block, FamilySymbol) and not title_block.IsActive:
            title_block.Activate()
            doc.Regenerate()

        sheet = ViewSheet.Create(doc, title_block.Id)
        sheet.SheetNumber = unique_sheet_number(sheet_number)
        sheet.Name = sheet_name
        doc.Regenerate()

        outline = sheet.Outline
        temporary_point = XYZ(
            (outline.Min.U + outline.Max.U) / 2.0,
            (outline.Min.V + outline.Max.V) / 2.0,
            0.0
        )

        for wall in walls:
            sub = SubTransaction(doc)
            sub.Start()
            try:
                view = ViewSection.CreateSection(
                    doc,
                    section_type.Id,
                    curtain_wall_section_box(
                        wall,
                        crop_margin,
                        depth_margin
                    )
                )

                view.Name = unique_view_name(
                    "CW ELEVATION - ID {}".format(id_number(wall)),
                    used_view_names
                )
                view.Scale = start_scale
                view.CropBoxActive = True
                view.CropBoxVisible = False
                try:
                    view.DetailLevel = ViewDetailLevel.Fine
                except:
                    pass

                viewport = Viewport.Create(
                    doc,
                    sheet.Id,
                    view.Id,
                    temporary_point
                )

                sub.Commit()
                created_views.append(view)
                created_viewports.append(viewport)

            except Exception as ex:
                sub.RollBack()
                failures.append({
                    "WallId": id_number(wall),
                    "Type": wall.WallType.Name,
                    "Error": str(ex)
                })

        if not created_viewports:
            raise Exception("No curtain-wall views could be created.")

        outline = sheet.Outline
        left = outline.Min.U + sheet_margin
        right = outline.Max.U - sheet_margin
        bottom = outline.Min.V + bottom_reserve
        top = outline.Max.V - sheet_margin

        positions = None

        for candidate in scale_list(start_scale, auto_fit):
            for view in created_views:
                view.Scale = candidate

            doc.Regenerate()
            positions = pack(
                viewport_sizes(created_viewports),
                left, right, bottom, top, gap
            )

            final_scale = candidate
            if positions is not None:
                fitted = True
                break

        if positions is None:
            # Best-effort placement; all views remain associated with this sheet.
            positions = []
            x = left
            y = top
            row_height = 0.0
            for width, height in viewport_sizes(created_viewports):
                if x > left and x + width > right:
                    x = left
                    y -= row_height + gap
                    row_height = 0.0
                positions.append(XYZ(x + width / 2.0, y - height / 2.0, 0))
                x += width + gap
                row_height = max(row_height, height)

        for viewport, point in zip(created_viewports, positions):
            viewport.SetBoxCenter(point)

        doc.Regenerate()
        transaction.Commit()

        return {
            "Status": "Completed",
            "Sheet": wrap(sheet),
            "SheetNumber": sheet.SheetNumber,
            "CurtainWallsFound": len(walls),
            "ViewsCreated": [wrap(v) for v in created_views],
            "FinalScale": "1:{}".format(final_scale),
            "FitInsideSheetBoundary": fitted,
            "Failures": failures
        }

    except Exception as ex:
        try:
            transaction.RollBack()
        except:
            pass
        return {
            "Status": "Failed; transaction rolled back.",
            "Error": str(ex),
            "Traceback": traceback.format_exc()
        }


OUT = main()
