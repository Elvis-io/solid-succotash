def compatible_template_by_name(sample_view, template_name):
    wanted = str(template_name or "").strip().lower()
    if not wanted:
        return None

    for candidate in DB.FilteredElementCollector(doc).OfClass(DB.View):
        try:
            if not candidate.IsTemplate:
                continue
            if candidate.Name.strip().lower() != wanted:
                continue
            if sample_view.IsValidViewTemplate(candidate.Id):
                return candidate
        except Exception:
            continue
    return None


def unique_template_name(base_name):
    # Revit view and view-template names share one uniqueness namespace.
    used_names = set()
    for candidate in DB.FilteredElementCollector(doc).OfClass(DB.View):
        try:
            used_names.add(candidate.Name.lower())
        except Exception:
            continue

    cleaned = clean_name(base_name) or DEFAULT_ISOLATION_TEMPLATE_NAME
    cleaned = cleaned[:230].rstrip()
    candidate = cleaned
    suffix = 1
    while candidate.lower() in used_names:
        suffix += 1
        suffix_text = " ({0})".format(suffix)
        candidate = (
            cleaned[:230 - len(suffix_text)].rstrip()
            + suffix_text
        )
    return candidate


def resolve_isolation_view_template(sample_view, requested_name):
    existing = compatible_template_by_name(sample_view, requested_name)
    if existing is not None:
        configure_isolation_view_template(existing)
        return existing, False

    if not sample_view.IsViewValidForTemplateCreation():
        raise RuntimeError(
            "The selected Section view type cannot create a view template."
        )

    template = sample_view.CreateViewTemplate()
    template.Name = unique_template_name(requested_name)
    configure_isolation_view_template(template)
    return template, True


def planar_face_reference_data(wall, view):
    """Parse referenceable planar faces once for both overall dimensions."""
    result = []
    options = geometry_options(view)

    for element in curtain_reference_elements(wall):
        try:
            geometry = element.get_Geometry(options)
        except Exception:
            geometry = None
        if geometry is None:
            continue

        for face, face_transform in iter_planar_faces(
            geometry,
            DB.Transform.Identity,
        ):
            try:
                reference = face.Reference
                if reference is None:
                    continue
                normal = face_transform.OfVector(face.FaceNormal)
                if normal.GetLength() < 0.000000001:
                    continue
                normal = normal.Normalize()
                origin = face_transform.OfPoint(face.Origin)
                result.append((origin, normal, reference))
            except Exception:
                continue

    return result


def extreme_face_entries(face_data, frame, axis):
    candidates = []
    for origin, normal, reference in face_data:
        try:
            if abs(vector_dot(normal, axis)) < 0.965:
                continue
            coordinate = projected_coordinate(
                origin,
                frame["origin"],
                axis,
            )
            candidates.append((coordinate, reference))
        except Exception:
            continue

    if len(candidates) < 2:
        return []

    candidates.sort(key=lambda item: item[0])
    return [candidates[0], candidates[-1]]


def wall_endpoint_entries(wall, frame):
    result = []
    try:
        curve = wall.Location.Curve
        if not isinstance(curve, DB.Line):
            return []
        for index in (0, 1):
            reference = curve.GetEndPointReference(index)
            point = curve.GetEndPoint(index)
            if reference is not None:
                result.append(
                    (
                        projected_coordinate(
                            point,
                            frame["origin"],
                            frame["right"],
                        ),
                        reference,
                    )
                )
    except Exception:
        return []

    result.sort(key=lambda item: item[0])
    return result


def grid_curve_reference(grid_line):
    try:
        curve = grid_line.FullCurve
        reference = curve.Reference
        if reference is not None:
            return reference
    except Exception:
        pass
    return None


def grid_element_reference(grid_line):
    try:
        return DB.Reference(grid_line)
    except Exception:
        return None


def collect_grid_line_data(wall, frame):
    vertical = []
    horizontal = []

    try:
        curtain_grid = wall.CurtainGrid
        grid_ids = []
        grid_ids.extend(list(curtain_grid.GetUGridLineIds()))
        grid_ids.extend(list(curtain_grid.GetVGridLineIds()))
    except Exception:
        return vertical, horizontal

    seen_ids = set()
    for grid_id in grid_ids:
        number = id_number(grid_id)
        if number in seen_ids:
            continue
        seen_ids.add(number)

        grid_line = doc.GetElement(grid_id)
        if grid_line is None:
            continue

        try:
            curve = grid_line.FullCurve
            first = curve.GetEndPoint(0)
            second = curve.GetEndPoint(1)
            direction = second - first
            if direction.GetLength() < 0.000000001:
                continue
            direction = direction.Normalize()
            midpoint = (first + second) * 0.5
        except Exception:
            continue

        primary_reference = grid_curve_reference(grid_line)
        alternate_reference = grid_element_reference(grid_line)
        if primary_reference is None and alternate_reference is None:
            continue

        vertical_score = abs(vector_dot(direction, frame["up"]))
        horizontal_score = abs(vector_dot(direction, frame["right"]))

        item = {
            "element": grid_line,
            "primary": primary_reference,
            "alternate": alternate_reference,
        }

        if vertical_score >= horizontal_score and vertical_score > 0.70:
            item["coordinate"] = projected_coordinate(
                midpoint,
                frame["origin"],
                frame["right"],
            )
            vertical.append(item)
        elif horizontal_score > vertical_score and horizontal_score > 0.70:
            item["coordinate"] = projected_coordinate(
                midpoint,
                frame["origin"],
                frame["up"],
            )
            horizontal.append(item)

    vertical.sort(key=lambda item: item["coordinate"])
    horizontal.sort(key=lambda item: item["coordinate"])
    return vertical, horizontal


def clean_dimension_entries(entries, coordinate_tolerance=0.00001):
    cleaned = []
    reference_keys = set()

    for coordinate, reference in sorted(entries, key=lambda item: item[0]):
        if reference is None:
            continue
        key = reference_key(reference)
        if key in reference_keys:
            continue
        if cleaned and abs(coordinate - cleaned[-1][0]) < coordinate_tolerance:
            continue
        cleaned.append((coordinate, reference))
        reference_keys.add(key)

    return cleaned


def try_create_dimension(view, dimension_line, entries):
    entries = clean_dimension_entries(entries)
    if len(entries) < 2:
        return None, "Fewer than two usable references were found."

    references = DB.ReferenceArray()
    for coordinate, reference in entries:
        references.Append(reference)

    subtransaction = DB.SubTransaction(doc)
    subtransaction.Start()
    try:
        dimension = doc.Create.NewDimension(
            view,
            dimension_line,
            references,
        )
        if dimension is None:
            raise RuntimeError("Revit returned no Dimension element.")
        subtransaction.Commit()
        return dimension, None
    except Exception as error:
        try:
            subtransaction.RollBack()
        except Exception:
            pass
        return None, str(error)


def first_successful_dimension(view, dimension_line, entry_variants):
    errors = []
    attempted_keys = set()

    for entries in entry_variants:
        cleaned = clean_dimension_entries(entries)
        if len(cleaned) < 2:
            continue
        signature = tuple(reference_key(item[1]) for item in cleaned)
        if signature in attempted_keys:
            continue
        attempted_keys.add(signature)

        dimension, error = try_create_dimension(
            view,
            dimension_line,
            cleaned,
        )
        if dimension is not None:
            return dimension, None
        if error:
            errors.append(error)

    if errors:
        return None, errors[-1]
    return None, "No valid reference set was available."


def grid_entries(grid_items, reference_field):
    result = []
    for item in grid_items:
        reference = item.get(reference_field)
        if reference is not None:
            result.append((item["coordinate"], reference))
    return result


def build_grid_entry_variants(grid_items, boundary_variants):
    variants = []
    for reference_field in ("primary", "alternate"):
        grids = grid_entries(grid_items, reference_field)
        if not grids:
            continue
        for boundaries in boundary_variants:
            if boundaries:
                variants.append(boundaries + grids)
        variants.append(grids)
    return variants


def try_create_text_note(view, point, text, text_type_id):
    if text_type_id == DB.ElementId.InvalidElementId:
        return None, "No TextNoteType is available for fallback notes."

    subtransaction = DB.SubTransaction(doc)
    subtransaction.Start()
    try:
        options = DB.TextNoteOptions(text_type_id)
        try:
            options.HorizontalAlignment = DB.HorizontalTextAlignment.Left
        except Exception:
            pass
        note = DB.TextNote.Create(
            doc,
            view.Id,
            point,
            0.0,
            text,
            options,
        )
        subtransaction.Commit()
        return note, None
    except Exception as error:
        try:
            subtransaction.RollBack()
        except Exception:
            pass
        return None, str(error)


def interval_text(coordinates):
    sorted_values = sorted(coordinates)
    cleaned = []
    for value in sorted_values:
        if not cleaned or abs(value - cleaned[-1]) > 0.00001:
            cleaned.append(value)
    if len(cleaned) < 2:
        return ""
    return " + ".join(
        format_length(cleaned[index + 1] - cleaned[index])
        for index in range(len(cleaned) - 1)
    )


