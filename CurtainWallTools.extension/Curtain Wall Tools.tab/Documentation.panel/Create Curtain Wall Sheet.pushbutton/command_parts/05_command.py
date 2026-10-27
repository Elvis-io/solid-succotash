def annotate_curtain_wall(
    wall,
    view,
    frame,
    settings,
    text_type_id,
):
    result = {
        "overall_dimensions": 0,
        "grid_dimensions": 0,
        "fallback_notes": 0,
        "warnings": [],
    }

    if not settings["dimension_overall"] and not settings["dimension_grids"]:
        return result

    spacing = mm(settings["dimension_spacing_mm"])
    min_x = frame["model_min_x"]
    max_x = frame["model_max_x"]
    min_y = frame["model_min_y"]
    max_y = frame["model_max_y"]

    width = max_x - min_x
    height = max_y - min_y
    fallback_lines = []

    if not wall_is_straight(wall):
        if settings["dimension_overall"]:
            fallback_lines.append(
                "PROJECTED OVERALL WIDTH: {0}".format(format_length(width))
            )
            fallback_lines.append(
                "PROJECTED OVERALL HEIGHT: {0}".format(format_length(height))
            )
        if settings["dimension_grids"]:
            fallback_lines.append(
                "CURVED WALL: GRID CHAIN DIMENSIONS REQUIRE MANUAL REVIEW"
            )
        result["warnings"].append(
            "Curved curtain wall: projected values were used; graphical grid dimensions were skipped."
        )
    else:
        width_boundaries = []
        endpoint_entries = wall_endpoint_entries(wall, frame)
        if len(endpoint_entries) >= 2:
            width_boundaries.append(endpoint_entries)

        face_data = planar_face_reference_data(wall, view)
        face_width_entries = extreme_face_entries(
            face_data,
            frame,
            frame["right"],
        )
        if len(face_width_entries) >= 2:
            width_boundaries.append(face_width_entries)

        height_boundaries = []
        face_height_entries = extreme_face_entries(
            face_data,
            frame,
            frame["up"],
        )
        if len(face_height_entries) >= 2:
            height_boundaries.append(face_height_entries)

        vertical_grids, horizontal_grids = collect_grid_line_data(
            wall,
            frame,
        )

        if settings["dimension_grids"] and vertical_grids:
            width_grid_line = DB.Line.CreateBound(
                frame_point(frame, min_x, min_y - spacing),
                frame_point(frame, max_x, min_y - spacing),
            )
            variants = build_grid_entry_variants(
                vertical_grids,
                width_boundaries,
            )
            dimension, error = first_successful_dimension(
                view,
                width_grid_line,
                variants,
            )
            if dimension is not None:
                result["grid_dimensions"] += 1
            else:
                coordinates = [min_x]
                coordinates.extend(
                    item["coordinate"] for item in vertical_grids
                )
                coordinates.append(max_x)
                sequence = interval_text(coordinates)
                if sequence:
                    fallback_lines.append(
                        "WIDTH GRID: {0}".format(sequence)
                    )
                result["warnings"].append(
                    "Horizontal grid-chain dimension could not bind: {0}".format(error)
                )

        if settings["dimension_grids"] and horizontal_grids:
            height_grid_line = DB.Line.CreateBound(
                frame_point(frame, min_x - spacing, min_y),
                frame_point(frame, min_x - spacing, max_y),
            )
            variants = build_grid_entry_variants(
                horizontal_grids,
                height_boundaries,
            )
            dimension, error = first_successful_dimension(
                view,
                height_grid_line,
                variants,
            )
            if dimension is not None:
                result["grid_dimensions"] += 1
            else:
                coordinates = [min_y]
                coordinates.extend(
                    item["coordinate"] for item in horizontal_grids
                )
                coordinates.append(max_y)
                sequence = interval_text(coordinates)
                if sequence:
                    fallback_lines.append(
                        "HEIGHT GRID: {0}".format(sequence)
                    )
                result["warnings"].append(
                    "Vertical grid-chain dimension could not bind: {0}".format(error)
                )

        if settings["dimension_overall"]:
            width_dimension_line = DB.Line.CreateBound(
                frame_point(frame, min_x, min_y - (2.0 * spacing)),
                frame_point(frame, max_x, min_y - (2.0 * spacing)),
            )
            dimension, error = first_successful_dimension(
                view,
                width_dimension_line,
                width_boundaries,
            )
            if dimension is not None:
                result["overall_dimensions"] += 1
            else:
                fallback_lines.append(
                    "OVERALL WIDTH: {0}".format(format_length(width))
                )
                result["warnings"].append(
                    "Overall width dimension could not bind: {0}".format(error)
                )

            height_dimension_line = DB.Line.CreateBound(
                frame_point(frame, min_x - (2.0 * spacing), min_y),
                frame_point(frame, min_x - (2.0 * spacing), max_y),
            )
            dimension, error = first_successful_dimension(
                view,
                height_dimension_line,
                height_boundaries,
            )
            if dimension is not None:
                result["overall_dimensions"] += 1
            else:
                fallback_lines.append(
                    "OVERALL HEIGHT: {0}".format(format_length(height))
                )
                result["warnings"].append(
                    "Overall height dimension could not bind: {0}".format(error)
                )

    if fallback_lines:
        note_point = frame_point(
            frame,
            min_x,
            max_y + (0.65 * spacing),
        )
        note, error = try_create_text_note(
            view,
            note_point,
            "\n".join(fallback_lines),
            text_type_id,
        )
        if note is not None:
            result["fallback_notes"] += 1
        else:
            result["warnings"].append(
                "Fallback annotation note could not be created: {0}".format(error)
            )

    return result


# -----------------------------------------------------------------------------
# Sheet layout
# -----------------------------------------------------------------------------

def viewport_footprints(viewports):
    """Measure each viewport, including its title label when available."""
    footprints = []
    for viewport in viewports:
        box_outline = viewport.GetBoxOutline()
        minimum_x = box_outline.MinimumPoint.X
        minimum_y = box_outline.MinimumPoint.Y
        maximum_x = box_outline.MaximumPoint.X
        maximum_y = box_outline.MaximumPoint.Y

        try:
            label_outline = viewport.GetLabelOutline()
            minimum_x = min(minimum_x, label_outline.MinimumPoint.X)
            minimum_y = min(minimum_y, label_outline.MinimumPoint.Y)
            maximum_x = max(maximum_x, label_outline.MaximumPoint.X)
            maximum_y = max(maximum_y, label_outline.MaximumPoint.Y)
        except Exception:
            pass

        box_center = viewport.GetBoxCenter()
        union_center_x = (minimum_x + maximum_x) / 2.0
        union_center_y = (minimum_y + maximum_y) / 2.0

        footprints.append(
            {
                "width": maximum_x - minimum_x,
                "height": maximum_y - minimum_y,
                "offset_x": union_center_x - box_center.X,
                "offset_y": union_center_y - box_center.Y,
            }
        )
    return footprints


def pack_footprints(footprints, left, right, bottom, top, gap):
    """Pack all viewport footprints into one page, largest first."""
    order = sorted(
        range(len(footprints)),
        key=lambda index: (
            -footprints[index]["height"],
            -footprints[index]["width"],
        ),
    )

    positions = [None] * len(footprints)
    x_position = left
    y_position = top
    row_height = 0.0

    for index in order:
        width = footprints[index]["width"]
        height = footprints[index]["height"]

        if width > (right - left) or height > (top - bottom):
            return None

        if x_position > left and x_position + width > right:
            x_position = left
            y_position -= row_height + gap
            row_height = 0.0

        if y_position - height < bottom:
            return None

        positions[index] = DB.XYZ(
            x_position + width / 2.0,
            y_position - height / 2.0,
            0.0,
        )
        x_position += width + gap
        row_height = max(row_height, height)

    return positions


def pack_footprints_across_pages(
    footprints,
    left,
    right,
    bottom,
    top,
    gap,
):
    """Pack footprints into as many row-based pages as required."""
    order = sorted(
        range(len(footprints)),
        key=lambda index: (
            -footprints[index]["height"],
            -footprints[index]["width"],
        ),
    )

    page_width = right - left
    page_height = top - bottom
    for index in order:
        if (
            footprints[index]["width"] > page_width
            or footprints[index]["height"] > page_height
        ):
            return None

    pages = []
    current = None

    for index in order:
        width = footprints[index]["width"]
        height = footprints[index]["height"]

        if current is None:
            current = {
                "indices": [],
                "positions": {},
                "x": left,
                "y": top,
                "row_height": 0.0,
            }
            pages.append(current)

        x_position = current["x"]
        y_position = current["y"]
        row_height = current["row_height"]

        if x_position > left and x_position + width > right:
            x_position = left
            y_position -= row_height + gap
            row_height = 0.0

        if y_position - height < bottom:
            current = {
                "indices": [],
                "positions": {},
                "x": left,
                "y": top,
                "row_height": 0.0,
            }
            pages.append(current)
            x_position = left
            y_position = top
            row_height = 0.0

        current["indices"].append(index)
        current["positions"][index] = DB.XYZ(
            x_position + width / 2.0,
            y_position - height / 2.0,
            0.0,
        )
        current["x"] = x_position + width + gap
        current["y"] = y_position
        current["row_height"] = max(row_height, height)

    for page in pages:
        page.pop("x", None)
        page.pop("y", None)
        page.pop("row_height", None)

    return pages


def _rect_right(rectangle):
    return rectangle["x"] + rectangle["width"]


def _rect_top(rectangle):
    return rectangle["y"] + rectangle["height"]


def _rectangles_intersect(first, second, tolerance=0.000000001):
    return not (
        _rect_right(first) <= second["x"] + tolerance
        or _rect_right(second) <= first["x"] + tolerance
        or _rect_top(first) <= second["y"] + tolerance
        or _rect_top(second) <= first["y"] + tolerance
    )


def _rectangle_contains(outer, inner, tolerance=0.000000001):
    return (
        inner["x"] >= outer["x"] - tolerance
        and inner["y"] >= outer["y"] - tolerance
        and _rect_right(inner) <= _rect_right(outer) + tolerance
        and _rect_top(inner) <= _rect_top(outer) + tolerance
    )


def _prune_free_rectangles(rectangles):
    cleaned = []
    for rectangle in rectangles:
        if rectangle["width"] <= 0.000000001:
            continue
        if rectangle["height"] <= 0.000000001:
            continue
        cleaned.append(rectangle)

    result = []
    for index, rectangle in enumerate(cleaned):
        contained = False
        for other_index, other in enumerate(cleaned):
            if index == other_index:
                continue
            if _rectangle_contains(other, rectangle):
                contained = True
                break
        if not contained:
            result.append(rectangle)
    return result


def _split_free_rectangles(free_rectangles, used_rectangle):
    """Split MaxRects free areas around one newly occupied rectangle."""
    result = []
    used_right = _rect_right(used_rectangle)
    used_top = _rect_top(used_rectangle)

    for free_rectangle in free_rectangles:
        if not _rectangles_intersect(free_rectangle, used_rectangle):
            result.append(free_rectangle)
            continue

        free_right = _rect_right(free_rectangle)
        free_top = _rect_top(free_rectangle)

        if used_rectangle["x"] > free_rectangle["x"]:
            result.append(
                {
                    "x": free_rectangle["x"],
                    "y": free_rectangle["y"],
                    "width": used_rectangle["x"] - free_rectangle["x"],
                    "height": free_rectangle["height"],
                }
            )

        if used_right < free_right:
            result.append(
                {
                    "x": used_right,
                    "y": free_rectangle["y"],
                    "width": free_right - used_right,
                    "height": free_rectangle["height"],
                }
            )

        if used_rectangle["y"] > free_rectangle["y"]:
            result.append(
                {
                    "x": free_rectangle["x"],
                    "y": free_rectangle["y"],
                    "width": free_rectangle["width"],
                    "height": used_rectangle["y"] - free_rectangle["y"],
                }
            )

        if used_top < free_top:
            result.append(
                {
                    "x": free_rectangle["x"],
                    "y": used_top,
                    "width": free_rectangle["width"],
                    "height": free_top - used_top,
                }
            )

    return _prune_free_rectangles(result)


