def _architectural_order(footprints, indices, mode):
    def area(index):
        return footprints[index]["width"] * footprints[index]["height"]

    if mode == "height":
        key_function = lambda index: (
            footprints[index]["height"],
            footprints[index]["width"],
            area(index),
        )
    elif mode == "width":
        key_function = lambda index: (
            footprints[index]["width"],
            footprints[index]["height"],
            area(index),
        )
    elif mode == "max_side":
        key_function = lambda index: (
            max(
                footprints[index]["width"],
                footprints[index]["height"],
            ),
            area(index),
        )
    elif mode == "perimeter":
        key_function = lambda index: (
            footprints[index]["width"] + footprints[index]["height"],
            area(index),
        )
    else:
        key_function = lambda index: (
            area(index),
            footprints[index]["height"],
            footprints[index]["width"],
        )

    return sorted(indices, key=key_function, reverse=True)


def _pack_architectural_page(
    footprints,
    ordered_indices,
    left,
    right,
    bottom,
    top,
    gap,
):
    """Pack as many viewports as possible on one measured sheet area."""
    page_width = right - left
    page_height = top - bottom
    if page_width <= 0.0 or page_height <= 0.0:
        return None

    # Expand the free rectangle by one gap at its right and bottom edges. Each
    # occupied cell includes a right/bottom gap, while the actual viewport stays
    # completely inside the requested sheet boundaries.
    free_rectangles = [
        {
            "x": left,
            "y": bottom - gap,
            "width": page_width + gap,
            "height": page_height + gap,
        }
    ]
    positions = {}
    placed_indices = []

    for index in ordered_indices:
        footprint = footprints[index]
        width = footprint["width"]
        height = footprint["height"]
        cell_width = width + gap
        cell_height = height + gap
        best_candidate = None

        for free_index, free_rectangle in enumerate(free_rectangles):
            if cell_width > free_rectangle["width"] + 0.000000001:
                continue
            if cell_height > free_rectangle["height"] + 0.000000001:
                continue

            x_position = free_rectangle["x"]
            y_position = _rect_top(free_rectangle) - cell_height
            remaining_width = free_rectangle["width"] - cell_width
            remaining_height = free_rectangle["height"] - cell_height
            remaining_area = (
                free_rectangle["width"] * free_rectangle["height"]
                - cell_width * cell_height
            )
            candidate_score = (
                remaining_area,
                min(remaining_width, remaining_height),
                max(remaining_width, remaining_height),
                -1.0 * (y_position + cell_height),
                x_position,
                free_index,
            )

            if (
                best_candidate is None
                or candidate_score < best_candidate["score"]
            ):
                best_candidate = {
                    "score": candidate_score,
                    "x": x_position,
                    "y": y_position,
                    "width": cell_width,
                    "height": cell_height,
                }

        if best_candidate is None:
            continue

        used_rectangle = {
            "x": best_candidate["x"],
            "y": best_candidate["y"],
            "width": best_candidate["width"],
            "height": best_candidate["height"],
        }
        free_rectangles = _split_free_rectangles(
            free_rectangles,
            used_rectangle,
        )

        positions[index] = DB.XYZ(
            used_rectangle["x"] + width / 2.0,
            _rect_top(used_rectangle) - height / 2.0,
            0.0,
        )
        placed_indices.append(index)

    return {
        "indices": placed_indices,
        "positions": positions,
    }


def _pack_architectural_pages_for_order(
    footprints,
    ordered_indices,
    left,
    right,
    bottom,
    top,
    gap,
):
    remaining = list(ordered_indices)
    pages = []

    while remaining:
        page = _pack_architectural_page(
            footprints,
            remaining,
            left,
            right,
            bottom,
            top,
            gap,
        )
        if page is None or not page["indices"]:
            return None

        pages.append(page)
        placed = set(page["indices"])
        remaining = [index for index in remaining if index not in placed]

    return pages


def _packing_quality(pages, footprints, usable_area):
    if not pages:
        return (999999, 0.0, 0.0)

    utilizations = []
    for page in pages:
        occupied = sum(
            footprints[index]["width"] * footprints[index]["height"]
            for index in page["indices"]
        )
        utilization = occupied / usable_area if usable_area > 0.0 else 0.0
        utilizations.append(utilization)

    # Fewer sheets is the primary objective. For equal page counts, prefer a
    # fuller first set of sheets rather than distributing empty space evenly.
    concentration = sum(value * value for value in utilizations)
    first_page_fill = utilizations[0] if utilizations else 0.0
    return (len(pages), -concentration, -first_page_fill)


def pack_footprints_for_architectural_sheet(
    footprints,
    left,
    right,
    bottom,
    top,
    gap,
    allow_multiple,
):
    """Optimize unrotated viewport placement for a measured A-series sheet."""
    page_width = right - left
    page_height = top - bottom
    usable_area = page_width * page_height
    if page_width <= 0.0 or page_height <= 0.0:
        return None

    all_indices = list(range(len(footprints)))
    for index in all_indices:
        if footprints[index]["width"] > page_width + 0.000000001:
            return None
        if footprints[index]["height"] > page_height + 0.000000001:
            return None

    candidates = []
    modes = ["area", "height", "width", "max_side", "perimeter"]
    for mode in modes:
        ordered_indices = _architectural_order(
            footprints,
            all_indices,
            mode,
        )
        pages = _pack_architectural_pages_for_order(
            footprints,
            ordered_indices,
            left,
            right,
            bottom,
            top,
            gap,
        )
        if pages is None:
            continue
        if not allow_multiple and len(pages) != 1:
            continue
        candidates.append(
            {
                "pages": pages,
                "score": _packing_quality(
                    pages,
                    footprints,
                    usable_area,
                ),
                "mode": mode,
            }
        )

    if not candidates:
        return None

    candidates.sort(key=lambda candidate: candidate["score"])
    return candidates[0]["pages"]


def page_layout_utilizations(page_layouts, footprints, usable_area):
    values = []
    for page in page_layouts or []:
        occupied_area = sum(
            footprints[index]["width"] * footprints[index]["height"]
            for index in page["indices"]
        )
        if usable_area > 0.0:
            values.append(100.0 * occupied_area / usable_area)
        else:
            values.append(0.0)
    return values


def scale_candidates(start_scale, auto_fit):
    start_scale = max(1, int(start_scale))
    if not auto_fit:
        return [start_scale]

    result = [start_scale]
    for scale in STANDARD_DRAWING_SCALES:
        if scale > start_scale and scale not in result:
            result.append(scale)
    return result


def overflow_positions(footprints, left, right, top, gap):
    """Best-effort row placement when the views still do not fit."""
    positions = []
    x_position = left
    y_position = top
    row_height = 0.0

    for footprint in footprints:
        width = footprint["width"]
        height = footprint["height"]
        if x_position > left and x_position + width > right:
            x_position = left
            y_position -= row_height + gap
            row_height = 0.0
        positions.append(
            DB.XYZ(
                x_position + width / 2.0,
                y_position - height / 2.0,
                0.0,
            )
        )
        x_position += width + gap
        row_height = max(row_height, height)
    return positions


def oversized_pages(footprints, left, right, bottom, top):
    """Place each oversized viewport on its own centred page as a fallback."""
    centre = DB.XYZ(
        (left + right) / 2.0,
        (bottom + top) / 2.0,
        0.0,
    )
    pages = []
    for index in range(len(footprints)):
        pages.append(
            {
                "indices": [index],
                "positions": {index: centre},
            }
        )
    return pages


def target_box_centre(footprint, union_centre):
    return DB.XYZ(
        union_centre.X - footprint["offset_x"],
        union_centre.Y - footprint["offset_y"],
        0.0,
    )


# -----------------------------------------------------------------------------
# Revit creation routine
# -----------------------------------------------------------------------------

def activate_title_block(title_block):
    try:
        if isinstance(title_block, DB.FamilySymbol) and not title_block.IsActive:
            title_block.Activate()
            doc.Regenerate()
    except Exception:
        pass


def create_sheet(title_block, desired_number, sheet_name, used_numbers):
    sheet = DB.ViewSheet.Create(doc, title_block.Id)
    sheet.SheetNumber = reserve_unique_sheet_number(
        desired_number,
        used_numbers,
    )
    sheet.Name = sheet_name
    return sheet


def create_view_name(wall, naming_data, settings, used_names):
    if settings["name_by_type"]:
        data = naming_data[id_number(wall)]
        base_name = "CW ELEVATION - {0}".format(data["type_name"])
        if data["total"] > 1:
            base_name += " - {0:02d}".format(data["sequence"])
    else:
        base_name = "CW ELEVATION - ID {0}".format(id_number(wall))
    return unique_view_name(base_name, used_names)


