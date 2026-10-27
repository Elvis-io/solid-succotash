def save_settings(settings):
    try:
        config.title_block_label = settings["title_block_label"]
        config.title_block_id = str(settings["title_block_id"])
        config.section_type_label = settings["section_type_label"]
        config.view_side = "Front"
        config.sheet_number = settings["sheet_number"]
        config.sheet_name = settings["sheet_name"]
        config.drawing_scale = str(settings["start_scale"])
        # Retain the legacy key so settings survive upgrades from v2.
        config.start_scale = str(settings["start_scale"])
        config.crop_margin_mm = str(settings["crop_margin_mm"])
        config.viewport_gap_mm = str(settings["viewport_gap_mm"])
        config.sheet_margin_mm = str(settings["sheet_margin_mm"])
        config.bottom_reserve_mm = str(settings["bottom_reserve_mm"])
        config.dimension_spacing_mm = str(settings["dimension_spacing_mm"])
        config.name_by_type = bool(settings["name_by_type"])
        config.isolate_view = bool(settings["isolate_view"])
        config.view_template_name = settings["view_template_name"]
        config.dimension_grids = bool(settings["dimension_grids"])
        config.dimension_overall = bool(settings["dimension_overall"])
        config.optimize_sheet = bool(settings["optimize_sheet"])
        config.multiple_sheets = bool(settings["multiple_sheets"])
        config.auto_fit = bool(settings["auto_fit"])
        config.open_sheet = bool(settings["open_sheet"])
        script.save_config()
    except Exception as error:
        logger.warning("Could not save command settings: %s", error)


# -----------------------------------------------------------------------------
# Curtain-wall view geometry
# -----------------------------------------------------------------------------

def model_bbox_corners(box):
    points = []
    for x_value in (box.Min.X, box.Max.X):
        for y_value in (box.Min.Y, box.Max.Y):
            for z_value in (box.Min.Z, box.Max.Z):
                points.append(
                    box.Transform.OfPoint(DB.XYZ(x_value, y_value, z_value))
                )
    return points


def curtain_wall_model_points(wall):
    """Return model-space bounding-box corners for the host, panels and mullions."""
    points = []
    for element in curtain_reference_elements(wall):
        try:
            box = element.get_BoundingBox(None)
        except Exception:
            box = None
        if box is not None:
            points.extend(model_bbox_corners(box))

    if not points:
        box = wall.get_BoundingBox(None)
        if box is None:
            raise RuntimeError("The wall has no model bounding box.")
        points = model_bbox_corners(box)

    return points


def curtain_wall_section_frame(
    wall,
    crop_margin,
    front_clearance,
    rear_clearance,
):
    """Build one shallow exterior/front view volume for a curtain wall.

    The previous tool centred a deep section box on the wall and added a large
    depth margin, which allowed unrelated model geometry to appear behind the
    target. This frame places the cut plane just outside the front-most curtain
    wall geometry and clips immediately behind the wall, panels and mullions.
    """
    points = curtain_wall_model_points(wall)

    # Wall.Orientation is the outward-facing exterior normal. Curtain-wall
    # orientation does not update when the wall is flipped, so Wall.Flipped is
    # applied explicitly to keep the generated view on the modelled front side.
    normal = wall.Orientation
    normal = DB.XYZ(normal.X, normal.Y, 0.0)
    if normal.GetLength() < 0.000000001:
        raise RuntimeError("A horizontal wall orientation could not be determined.")
    normal = normal.Normalize()
    try:
        if wall.Flipped:
            normal = normal.Negate()
    except Exception:
        pass

    # A front elevation is viewed from outside toward the curtain wall.
    view_direction = normal.Negate()
    up_direction = DB.XYZ.BasisZ
    right_direction = up_direction.CrossProduct(view_direction).Normalize()

    point_count = float(len(points))
    centre = DB.XYZ(
        sum(point.X for point in points) / point_count,
        sum(point.Y for point in points) / point_count,
        sum(point.Z for point in points) / point_count,
    )

    # First project all target geometry into a wall-aligned coordinate system
    # to locate its true front-most depth, including mullion projections.
    preliminary = DB.Transform.Identity
    preliminary.Origin = centre
    preliminary.BasisX = right_direction
    preliminary.BasisY = up_direction
    preliminary.BasisZ = view_direction
    preliminary_inverse = preliminary.Inverse
    preliminary_points = [
        preliminary_inverse.OfPoint(point) for point in points
    ]
    front_z = min(point.Z for point in preliminary_points)

    # Put the section cut plane just outside the front-most geometry. With the
    # new origin at that plane, all target geometry lies at positive local Z.
    cut_plane_origin = preliminary.OfPoint(
        DB.XYZ(0.0, 0.0, front_z - front_clearance)
    )

    transform = DB.Transform.Identity
    transform.Origin = cut_plane_origin
    transform.BasisX = right_direction
    transform.BasisY = up_direction
    transform.BasisZ = view_direction

    inverse = transform.Inverse
    local_points = [inverse.OfPoint(point) for point in points]

    model_min_x = min(point.X for point in local_points)
    model_max_x = max(point.X for point in local_points)
    model_min_y = min(point.Y for point in local_points)
    model_max_y = max(point.Y for point in local_points)
    model_min_z = min(point.Z for point in local_points)
    model_max_z = max(point.Z for point in local_points)

    # Revit requires a non-zero near/far distance. The depth remains tight to
    # the complete curtain-wall assembly so background rooms, walls and façades
    # are excluded from the generated elevation wherever geometry permits.
    minimum_depth = mm(50.0)
    far_depth = max(model_max_z + rear_clearance, minimum_depth)

    section_box = DB.BoundingBoxXYZ()
    section_box.Transform = transform
    section_box.Min = DB.XYZ(
        model_min_x - crop_margin,
        model_min_y - crop_margin,
        0.0,
    )
    section_box.Max = DB.XYZ(
        model_max_x + crop_margin,
        model_max_y + crop_margin,
        far_depth,
    )

    return {
        "box": section_box,
        "transform": transform,
        "origin": cut_plane_origin,
        "right": right_direction,
        "up": up_direction,
        "view_direction": view_direction,
        "model_min_x": model_min_x,
        "model_max_x": model_max_x,
        "model_min_y": model_min_y,
        "model_max_y": model_max_y,
        "model_min_z": model_min_z,
        "model_max_z": model_max_z,
        "front_clearance": front_clearance,
        "far_depth": far_depth,
    }


def frame_point(frame, x_value, y_value, z_value=0.0):
    return frame["transform"].OfPoint(
        DB.XYZ(float(x_value), float(y_value), float(z_value))
    )


def wall_is_straight(wall):
    try:
        return isinstance(wall.Location.Curve, DB.Line)
    except Exception:
        return False


# -----------------------------------------------------------------------------
# Dimension reference extraction
# -----------------------------------------------------------------------------

def geometry_options(view):
    options = DB.Options()
    options.ComputeReferences = True
    options.IncludeNonVisibleObjects = True
    try:
        options.View = view
    except Exception:
        try:
            options.DetailLevel = DB.ViewDetailLevel.Fine
        except Exception:
            pass
    return options


def iter_planar_faces(geometry_element, current_transform):
    if geometry_element is None:
        return

    for geometry_object in geometry_element:
        if isinstance(geometry_object, DB.Solid):
            try:
                if geometry_object.Faces.Size == 0:
                    continue
            except Exception:
                continue
            for face in geometry_object.Faces:
                if isinstance(face, DB.PlanarFace):
                    yield face, current_transform

        elif isinstance(geometry_object, DB.GeometryInstance):
            nested_transform = current_transform
            try:
                nested_transform = current_transform.Multiply(
                    geometry_object.Transform
                )
            except Exception:
                pass

            nested_geometry = None
            try:
                nested_geometry = geometry_object.GetSymbolGeometry()
            except Exception:
                try:
                    nested_geometry = geometry_object.GetInstanceGeometry()
                    nested_transform = current_transform
                except Exception:
                    nested_geometry = None

            if nested_geometry is not None:
                for item in iter_planar_faces(
                    nested_geometry,
                    nested_transform,
                ):
                    yield item


def curtain_reference_elements(wall):
    elements = [wall]
    seen = set([id_number(wall)])

    try:
        curtain_grid = wall.CurtainGrid
        child_ids = []
        child_ids.extend(list(curtain_grid.GetPanelIds()))
        child_ids.extend(list(curtain_grid.GetMullionIds()))
        for element_id in child_ids:
            number = id_number(element_id)
            if number in seen:
                continue
            element = doc.GetElement(element_id)
            if element is not None:
                elements.append(element)
                seen.add(number)
    except Exception:
        pass

    return elements


def net_element_id_list(element_ids):
    result = List[DB.ElementId]()
    for element_id in element_ids:
        result.Add(element_id)
    return result


def add_unique_element_id(collection, seen, element_id):
    if element_id is None:
        return False
    try:
        number = id_number(element_id)
    except Exception:
        return False
    try:
        if number == id_number(DB.ElementId.InvalidElementId):
            return False
    except Exception:
        pass
    if number in seen:
        return False
    element = doc.GetElement(element_id)
    if element is None:
        return False
    seen.add(number)
    collection.append(element_id)
    return True


def curtain_wall_isolation_element_ids(wall):
    """Return the complete model-element set retained in one front view."""
    element_ids = []
    seen = set()
    add_unique_element_id(element_ids, seen, wall.Id)

    try:
        curtain_grid = wall.CurtainGrid
        for getter_name in (
            "GetPanelIds",
            "GetMullionIds",
            "GetUGridLineIds",
            "GetVGridLineIds",
        ):
            try:
                getter = getattr(curtain_grid, getter_name)
                for element_id in getter():
                    add_unique_element_id(element_ids, seen, element_id)
            except Exception:
                continue
    except Exception:
        pass

    # Curtain-wall doors, embedded walls and similar hosted inserts can be
    # exposed separately from the panel collection.
    try:
        for element_id in wall.FindInserts(True, True, True, True):
            add_unique_element_id(element_ids, seen, element_id)
    except Exception:
        pass

    # Preserve shared or nested components used within panel families.
    queue = list(element_ids)
    queue_index = 0
    while queue_index < len(queue):
        element_id = queue[queue_index]
        queue_index += 1
        element = doc.GetElement(element_id)
        if element is None:
            continue
        try:
            subcomponent_ids = element.GetSubComponentIds()
        except Exception:
            subcomponent_ids = []
        for subcomponent_id in subcomponent_ids:
            if add_unique_element_id(
                element_ids,
                seen,
                subcomponent_id,
            ):
                queue.append(subcomponent_id)

    return element_ids


def hide_elements_safely(view, element_ids):
    """Hide all possible elements, falling back to one-at-a-time hiding."""
    if not element_ids:
        return 0, []

    try:
        view.HideElements(net_element_id_list(element_ids))
        return len(element_ids), []
    except Exception:
        pass

    hidden = 0
    failures = []
    for element_id in element_ids:
        try:
            view.HideElements(net_element_id_list([element_id]))
            hidden += 1
        except Exception as error:
            failures.append(
                "{0}: {1}".format(id_number(element_id), error)
            )
    return hidden, failures


def permanently_isolate_curtain_wall(view, wall):
    """Permanently hide every visible model element outside this assembly."""
    target_ids = curtain_wall_isolation_element_ids(wall)
    target_numbers = set(id_number(item) for item in target_ids)

    doc.Regenerate()
    hide_ids = []
    collector = (
        DB.FilteredElementCollector(doc, view.Id)
        .WhereElementIsNotElementType()
    )
    for element in collector:
        try:
            if id_number(element) in target_numbers:
                continue
            if element.ViewSpecific:
                continue
            if element.CanBeHidden(view):
                hide_ids.append(element.Id)
        except Exception:
            continue

    hidden_count, failures = hide_elements_safely(view, hide_ids)
    return {
        "target_count": len(target_ids),
        "candidate_hide_count": len(hide_ids),
        "hidden_count": hidden_count,
        "failures": failures,
        "method": "Permanent per-element hide",
    }


def enum_integer(enum_value):
    try:
        return int(enum_value)
    except Exception:
        try:
            return int(enum_value.value__)
        except Exception:
            return None


def managed_template_controlled_parameter_values():
    values = set()
    for parameter_name in TEMPLATE_CONTROLLED_BUILTIN_PARAMETERS:
        try:
            value = enum_integer(
                getattr(DB.BuiltInParameter, parameter_name)
            )
            if value is not None:
                values.add(value)
        except Exception:
            continue
    return values


def configure_template_parameter_control(template):
    """Keep only stable graphics parameters controlled by the template."""
    controlled_values = managed_template_controlled_parameter_values()
    noncontrolled = List[DB.ElementId]()

    for parameter_id in template.GetTemplateParameterIds():
        try:
            value = id_number(parameter_id)
        except Exception:
            noncontrolled.Add(parameter_id)
            continue
        if value not in controlled_values:
            noncontrolled.Add(parameter_id)

    template.SetNonControlledTemplateParameterIds(noncontrolled)


def configure_isolation_view_template(template):
    try:
        template.DetailLevel = DB.ViewDetailLevel.Fine
    except Exception:
        pass
    try:
        template.DisplayStyle = DB.DisplayStyle.HiddenLine
    except Exception:
        pass
    try:
        template.Discipline = DB.ViewDiscipline.Architectural
    except Exception:
        pass
    configure_template_parameter_control(template)


