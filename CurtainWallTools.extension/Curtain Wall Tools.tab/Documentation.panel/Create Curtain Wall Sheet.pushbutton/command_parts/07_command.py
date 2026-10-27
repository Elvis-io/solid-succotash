def create_curtain_wall_sheets(walls, settings):
    title_block = settings["title_block"]
    section_type = settings["section_type"]
    start_scale = settings["start_scale"]
    requested_crop_margin = mm(settings["crop_margin_mm"])
    dimension_spacing = mm(settings["dimension_spacing_mm"])
    viewport_gap = mm(settings["viewport_gap_mm"])
    sheet_margin = mm(settings["sheet_margin_mm"])
    bottom_reserve = mm(settings["bottom_reserve_mm"])

    dimensions_requested = (
        settings["dimension_grids"] or settings["dimension_overall"]
    )
    effective_crop_margin = requested_crop_margin
    if dimensions_requested:
        effective_crop_margin = max(
            requested_crop_margin,
            dimension_spacing * 3.0,
        )

    # Shallow front-only depth: enough tolerance to avoid clipping projected
    # mullions, while preventing unrelated background geometry from entering.
    front_clearance = mm(25)
    rear_clearance = mm(25)
    text_type_id = collect_text_note_type_id()

    used_view_names = all_used_view_names()
    used_sheet_numbers = all_sheet_numbers()
    naming_data = view_name_data(walls)
    records = []
    failures = []
    dimension_warnings = []
    isolation_warnings = []
    isolated_view_count = 0
    isolated_element_count = 0
    isolation_template = None
    isolation_template_created = False
    template_resolution_attempted = False
    dimension_totals = {
        "overall_dimensions": 0,
        "grid_dimensions": 0,
        "fallback_notes": 0,
    }
    final_scale = start_scale
    fitted = False
    page_layouts = None
    footprints = None
    sheets = []
    created_viewports = []
    sheet_size_info = None
    usable_width = 0.0
    usable_height = 0.0
    page_utilizations = []
    layout_method = (
        "Architectural A-series sheet optimizer"
        if settings["optimize_sheet"]
        else "Standard row layout"
    )

    transaction = DB.Transaction(doc, "Create curtain wall front elevation sheets")
    transaction.Start()

    try:
        activate_title_block(title_block)

        first_sheet = create_sheet(
            title_block,
            settings["sheet_number"],
            settings["sheet_name"],
            used_sheet_numbers,
        )
        sheets.append(first_sheet)
        doc.Regenerate()

        sheet_outline = first_sheet.Outline
        sheet_size_info = sheet_outline_info(sheet_outline)
        if settings["optimize_sheet"] and not sheet_size_info.get(
            "is_architectural"
        ):
            raise RuntimeError(
                "The selected title block measures {0}. The architectural "
                "optimizer supports A0, A1, A2, A3, and A4 sheets only."
                .format(sheet_size_description(sheet_size_info))
            )

        temporary_point = DB.XYZ(
            (sheet_outline.Min.U + sheet_outline.Max.U) / 2.0,
            (sheet_outline.Min.V + sheet_outline.Max.V) / 2.0,
            0.0,
        )

        for wall in walls:
            wall_subtransaction = DB.SubTransaction(doc)
            wall_subtransaction.Start()
            try:
                frame = curtain_wall_section_frame(
                    wall,
                    effective_crop_margin,
                    front_clearance,
                    rear_clearance,
                )
                view = DB.ViewSection.CreateSection(
                    doc,
                    section_type.Id,
                    frame["box"],
                )
                view.Name = create_view_name(
                    wall,
                    naming_data,
                    settings,
                    used_view_names,
                )
                view.Scale = start_scale
                view.CropBoxActive = True
                view.CropBoxVisible = False
                try:
                    view.DetailLevel = DB.ViewDetailLevel.Fine
                except Exception:
                    pass
                try:
                    view.Discipline = DB.ViewDiscipline.Architectural
                except Exception:
                    pass

                viewport = DB.Viewport.Create(
                    doc,
                    first_sheet.Id,
                    view.Id,
                    temporary_point,
                )
                wall_subtransaction.Commit()

                record = {
                    "wall": wall,
                    "view": view,
                    "frame": frame,
                    "temporary_viewport": viewport,
                }
                records.append(record)

                if settings["isolate_view"]:
                    if (
                        isolation_template is None
                        and not template_resolution_attempted
                    ):
                        template_resolution_attempted = True
                        template_subtransaction = DB.SubTransaction(doc)
                        template_subtransaction.Start()
                        try:
                            (
                                isolation_template,
                                isolation_template_created,
                            ) = resolve_isolation_view_template(
                                view,
                                settings["view_template_name"],
                            )
                            template_subtransaction.Commit()
                        except Exception as template_error:
                            try:
                                template_subtransaction.RollBack()
                            except Exception:
                                pass
                            isolation_template = None
                            isolation_template_created = False
                            isolation_warnings.append(
                                {
                                    "element_id": wall.Id,
                                    "wall_id": id_number(wall),
                                    "wall_type": element_type_name(
                                        wall.WallType
                                    ),
                                    "warning": (
                                        "The custom view template could not "
                                        "be created or reused: {0}. Permanent "
                                        "element isolation was still attempted."
                                        .format(template_error)
                                    ),
                                }
                            )

                    isolation_subtransaction = DB.SubTransaction(doc)
                    isolation_subtransaction.Start()
                    try:
                        if isolation_template is not None:
                            if not view.IsValidViewTemplate(
                                isolation_template.Id
                            ):
                                raise RuntimeError(
                                    "The managed template is not compatible "
                                    "with the generated view."
                                )
                            view.ViewTemplateId = isolation_template.Id
                            doc.Regenerate()

                        isolation_result = permanently_isolate_curtain_wall(
                            view,
                            wall,
                        )
                        isolated_view_count += 1
                        isolated_element_count += isolation_result[
                            "hidden_count"
                        ]
                        if isolation_result["failures"]:
                            isolation_warnings.append(
                                {
                                    "element_id": wall.Id,
                                    "wall_id": id_number(wall),
                                    "wall_type": element_type_name(
                                        wall.WallType
                                    ),
                                    "warning": (
                                        "{0} of {1} non-target elements could "
                                        "not be hidden. First failures: {2}"
                                        .format(
                                            len(isolation_result["failures"]),
                                            isolation_result[
                                                "candidate_hide_count"
                                            ],
                                            " | ".join(
                                                isolation_result["failures"][:5]
                                            ),
                                        )
                                    ),
                                }
                            )
                        isolation_subtransaction.Commit()
                    except Exception as isolation_error:
                        try:
                            isolation_subtransaction.RollBack()
                        except Exception:
                            pass
                        isolation_warnings.append(
                            {
                                "element_id": wall.Id,
                                "wall_id": id_number(wall),
                                "wall_type": element_type_name(
                                    wall.WallType
                                ),
                                "warning": (
                                    "The view was retained but isolation "
                                    "failed: {0}".format(isolation_error)
                                ),
                            }
                        )

                try:
                    annotation_result = annotate_curtain_wall(
                        wall,
                        view,
                        frame,
                        settings,
                        text_type_id,
                    )
                    dimension_totals["overall_dimensions"] += (
                        annotation_result["overall_dimensions"]
                    )
                    dimension_totals["grid_dimensions"] += (
                        annotation_result["grid_dimensions"]
                    )
                    dimension_totals["fallback_notes"] += (
                        annotation_result["fallback_notes"]
                    )
                    if annotation_result["warnings"]:
                        dimension_warnings.append(
                            {
                                "element_id": wall.Id,
                                "wall_id": id_number(wall),
                                "wall_type": element_type_name(wall.WallType),
                                "warning": " | ".join(
                                    annotation_result["warnings"]
                                ),
                            }
                        )
                except Exception as annotation_error:
                    dimension_warnings.append(
                        {
                            "element_id": wall.Id,
                            "wall_id": id_number(wall),
                            "wall_type": element_type_name(wall.WallType),
                            "warning": (
                                "Dimensioning failed, but the view was retained: {0}"
                                .format(annotation_error)
                            ),
                        }
                    )

            except Exception as error:
                try:
                    wall_subtransaction.RollBack()
                except Exception:
                    pass
                failures.append(
                    {
                        "element_id": wall.Id,
                        "wall_id": id_number(wall),
                        "wall_type": element_type_name(wall.WallType),
                        "error": str(error),
                    }
                )

        if not records:
            raise RuntimeError("No curtain-wall views could be created.")

        doc.Regenerate()

        sheet_outline = first_sheet.Outline
        left = sheet_outline.Min.U + sheet_margin
        right = sheet_outline.Max.U - sheet_margin
        bottom = sheet_outline.Min.V + bottom_reserve
        top = sheet_outline.Max.V - sheet_margin

        if right <= left or top <= bottom:
            raise RuntimeError(
                "The selected sheet is too small for the entered sheet margins."
            )

        usable_width = right - left
        usable_height = top - bottom
        usable_area = usable_width * usable_height

        temporary_viewports = [
            record["temporary_viewport"] for record in records
        ]

        for candidate_scale in scale_candidates(
            start_scale,
            settings["auto_fit"],
        ):
            for record in records:
                record["view"].Scale = candidate_scale
            doc.Regenerate()

            footprints = viewport_footprints(temporary_viewports)
            final_scale = candidate_scale

            if settings["optimize_sheet"]:
                page_layouts = pack_footprints_for_architectural_sheet(
                    footprints,
                    left,
                    right,
                    bottom,
                    top,
                    viewport_gap,
                    settings["multiple_sheets"],
                )
                if page_layouts is not None:
                    fitted = True
                    break
            elif settings["multiple_sheets"]:
                page_layouts = pack_footprints_across_pages(
                    footprints,
                    left,
                    right,
                    bottom,
                    top,
                    viewport_gap,
                )
                if page_layouts is not None:
                    fitted = True
                    break
            else:
                positions = pack_footprints(
                    footprints,
                    left,
                    right,
                    bottom,
                    top,
                    viewport_gap,
                )
                if positions is not None:
                    page_layouts = [
                        {
                            "indices": list(range(len(records))),
                            "positions": dict(
                                (index, positions[index])
                                for index in range(len(records))
                            ),
                        }
                    ]
                    fitted = True
                    break

        if footprints is None:
            footprints = viewport_footprints(temporary_viewports)

        if page_layouts is None:
            if settings["multiple_sheets"]:
                page_layouts = oversized_pages(
                    footprints,
                    left,
                    right,
                    bottom,
                    top,
                )
            else:
                positions = overflow_positions(
                    footprints,
                    left,
                    right,
                    top,
                    viewport_gap,
                )
                page_layouts = [
                    {
                        "indices": list(range(len(records))),
                        "positions": dict(
                            (index, positions[index])
                            for index in range(len(records))
                        ),
                    }
                ]

        page_utilizations = page_layout_utilizations(
            page_layouts,
            footprints,
            usable_area,
        )

        for viewport in temporary_viewports:
            doc.Delete(viewport.Id)
        doc.Regenerate()

        total_pages = len(page_layouts)
        for page_index in range(1, total_pages):
            desired_number = sheet_series_candidate(
                settings["sheet_number"],
                page_index,
            )
            sheet = create_sheet(
                title_block,
                desired_number,
                settings["sheet_name"],
                used_sheet_numbers,
            )
            sheets.append(sheet)

        if total_pages > 1:
            for page_index, sheet in enumerate(sheets):
                sheet.Name = "{0} - {1} OF {2}".format(
                    settings["sheet_name"],
                    page_index + 1,
                    total_pages,
                )
        else:
            first_sheet.Name = settings["sheet_name"]

        views_per_sheet = []
        for page_index, page in enumerate(page_layouts):
            sheet = sheets[page_index]
            page_viewports = []

            for record_index in page["indices"]:
                record = records[record_index]
                union_centre = page["positions"][record_index]
                box_centre = target_box_centre(
                    footprints[record_index],
                    union_centre,
                )
                viewport = DB.Viewport.Create(
                    doc,
                    sheet.Id,
                    record["view"].Id,
                    box_centre,
                )
                page_viewports.append(viewport)
                created_viewports.append(viewport)
                record["sheet"] = sheet
                record["viewport"] = viewport

            views_per_sheet.append(len(page_viewports))

        doc.Regenerate()
        transaction.Commit()

        return {
            "sheets": sheets,
            "sheet_numbers": [sheet.SheetNumber for sheet in sheets],
            "sheet_names": [sheet.Name for sheet in sheets],
            "views_per_sheet": views_per_sheet,
            "walls_found": len(walls),
            "views_created": [record["view"] for record in records],
            "viewports_created": created_viewports,
            "requested_scale": start_scale,
            "final_scale": final_scale,
            "fitted": fitted,
            "failures": failures,
            "dimension_warnings": dimension_warnings,
            "dimension_totals": dimension_totals,
            "isolation_enabled": settings["isolate_view"],
            "isolated_view_count": isolated_view_count,
            "isolated_element_count": isolated_element_count,
            "isolation_warnings": isolation_warnings,
            "view_template": isolation_template,
            "view_template_name": (
                isolation_template.Name
                if isolation_template is not None
                else (
                    settings["view_template_name"]
                    if settings["isolate_view"]
                    else "Not applied"
                )
            ),
            "view_template_created": isolation_template_created,
            "multiple_sheets_enabled": settings["multiple_sheets"],
            "sheet_size_info": sheet_size_info,
            "layout_method": layout_method,
            "optimizer_enabled": settings["optimize_sheet"],
            "usable_width_mm": from_internal_mm(usable_width),
            "usable_height_mm": from_internal_mm(usable_height),
            "page_utilizations": page_utilizations,
        }

    except Exception:
        try:
            transaction.RollBack()
        except Exception:
            pass
        raise


# -----------------------------------------------------------------------------
# Results and command entry point
# -----------------------------------------------------------------------------

