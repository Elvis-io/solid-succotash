def linked_element(element_id, fallback):
    try:
        return output.linkify(element_id)
    except Exception:
        return str(fallback)


def show_result(result):
    output.set_title("Curtain Wall Front Elevation Sheets")
    output.print_md("# Curtain Wall Front Elevation Sheets Created")

    sheet_rows = []
    for index, sheet in enumerate(result["sheets"]):
        utilization = 0.0
        if index < len(result.get("page_utilizations", [])):
            utilization = result["page_utilizations"][index]
        sheet_rows.append(
            [
                linked_element(sheet.Id, id_number(sheet)),
                sheet.SheetNumber,
                sheet.Name,
                result["views_per_sheet"][index],
                "{0:.1f}%".format(utilization),
            ]
        )
    output.print_table(
        table_data=sheet_rows,
        columns=["Sheet", "Number", "Name", "Views", "Viewport area used"],
        title="Created Sheets",
    )

    dimensions = result["dimension_totals"]
    summary_rows = [
        ["Curtain walls found", result["walls_found"]],
        ["Front elevations created", len(result["views_created"])],
        ["View direction", "One front elevation per curtain-wall instance"],
        ["View isolation enabled", result["isolation_enabled"]],
        ["Views permanently isolated", result["isolated_view_count"]],
        ["Non-target elements hidden", result["isolated_element_count"]],
        ["Isolation view template", result["view_template_name"]],
        [
            "View template status",
            (
                "Disabled"
                if not result["isolation_enabled"]
                else (
                    "Created"
                    if result["view_template_created"]
                    else (
                        "Reused"
                        if result["view_template"] is not None
                        else "Not available"
                    )
                )
            ),
        ],
        ["Sheets created", len(result["sheets"])],
        ["Selected sheet size", sheet_size_description(result["sheet_size_info"])],
        ["Placement method", result["layout_method"]],
        [
            "Usable layout area",
            "{0:.0f} x {1:.0f} mm".format(
                result["usable_width_mm"],
                result["usable_height_mm"],
            ),
        ],
        ["Selected drawing scale", "1:{0}".format(result["requested_scale"])],
        ["Final view scale", "1:{0}".format(result["final_scale"])],
        ["All viewports fit calculated sheet areas", result["fitted"]],
        ["Curtain-grid dimensions created", dimensions["grid_dimensions"]],
        ["Overall dimensions created", dimensions["overall_dimensions"]],
        ["Fallback value notes created", dimensions["fallback_notes"]],
        ["Walls skipped", len(result["failures"])],
    ]
    output.print_table(
        table_data=summary_rows,
        columns=["Result", "Value"],
        title="Run Summary",
    )

    if result["isolation_warnings"]:
        isolation_rows = []
        for warning in result["isolation_warnings"]:
            isolation_rows.append(
                [
                    linked_element(
                        warning["element_id"],
                        warning["wall_id"],
                    ),
                    warning["wall_type"],
                    warning["warning"],
                ]
            )
        output.print_table(
            table_data=isolation_rows,
            columns=["Curtain Wall", "Wall Type", "Isolation Note"],
            title="View Isolation Review",
        )

    if result["dimension_warnings"]:
        warning_rows = []
        for warning in result["dimension_warnings"]:
            warning_rows.append(
                [
                    linked_element(
                        warning["element_id"],
                        warning["wall_id"],
                    ),
                    warning["wall_type"],
                    warning["warning"],
                ]
            )
        output.print_table(
            table_data=warning_rows,
            columns=["Curtain Wall", "Wall Type", "Dimension Note"],
            title="Dimensioning Review",
        )

    if result["failures"]:
        failure_rows = []
        for failure in result["failures"]:
            failure_rows.append(
                [
                    linked_element(
                        failure["element_id"],
                        failure["wall_id"],
                    ),
                    failure["wall_type"],
                    failure["error"],
                ]
            )
        output.print_table(
            table_data=failure_rows,
            columns=["Curtain Wall", "Wall Type", "Reason Skipped"],
            title="Skipped Curtain Walls",
        )

    if result["fitted"]:
        fit_message = (
            "All viewports fit within the calculated sheet areas."
        )
    else:
        fit_message = (
            "One or more viewports remained larger than the calculated sheet "
            "area after the available scale attempts. Review the generated "
            "sheets, use a larger title block, or increase the scale denominator."
        )

    message = (
        "Created {0} front curtain-wall elevation{1} on {2} sheet{3} at 1:{4}.\n\n"
        "Sheet: {5}.\nPlacement: {6}.\n\n{7}"
        .format(
            len(result["views_created"]),
            "" if len(result["views_created"]) == 1 else "s",
            len(result["sheets"]),
            "" if len(result["sheets"]) == 1 else "s",
            result["final_scale"],
            sheet_size_description(result["sheet_size_info"]),
            result["layout_method"],
            fit_message,
        )
    )

    if result["final_scale"] != result["requested_scale"]:
        message += (
            "\n\nSelected scale 1:{0} was automatically adjusted to 1:{1} "
            "because at least one viewport was too large for the sheet."
            .format(result["requested_scale"], result["final_scale"])
        )

    if result["isolation_enabled"]:
        if result["view_template"] is not None:
            message += (
                "\n\nApplied the '{0}' view template and permanently "
                "isolated {1} generated view{2}."
                .format(
                    result["view_template_name"],
                    result["isolated_view_count"],
                    "" if result["isolated_view_count"] == 1 else "s",
                )
            )
        else:
            message += (
                "\n\nIsolation was requested, but no compatible view "
                "template was available. Review the pyRevit output."
            )

    if result["isolation_warnings"]:
        message += (
            "\n\n{0} curtain-wall view{1} require isolation review; "
            "see the pyRevit output."
            .format(
                len(result["isolation_warnings"]),
                "" if len(result["isolation_warnings"]) == 1 else "s",
            )
        )

    if result["dimension_warnings"]:
        message += (
            "\n\n{0} curtain-wall view{1} require dimension review; "
            "see the pyRevit output."
            .format(
                len(result["dimension_warnings"]),
                "" if len(result["dimension_warnings"]) == 1 else "s",
            )
        )

    if result["failures"]:
        message += "\n\n{0} wall{1} were skipped.".format(
            len(result["failures"]),
            "" if len(result["failures"]) == 1 else "s",
        )

    forms.alert(
        message,
        title="Curtain Wall Sheets",
        warn_icon=(
            not result["fitted"]
            or bool(result["failures"])
            or bool(result["dimension_warnings"])
            or bool(result["isolation_warnings"])
        ),
    )


def main():
    if doc is None:
        forms.alert(
            "Open a Revit project before running this command.",
            title="Curtain Wall Sheets",
            warn_icon=True,
        )
        return

    if doc.IsFamilyDocument:
        forms.alert(
            "Run this command in a Revit project, not in the Family Editor.",
            title="Curtain Wall Sheets",
            warn_icon=True,
        )
        return

    walls = collect_curtain_walls()
    if not walls:
        forms.alert(
            "No curtain-wall Wall instances were found in the active project.\n\n"
            "The command does not process linked models or mass-based "
            "CurtainSystem elements.",
            title="Curtain Wall Sheets",
            warn_icon=True,
        )
        return

    title_blocks = collect_title_blocks()
    if not title_blocks:
        forms.alert(
            "No title-block type is loaded in this project.",
            title="Curtain Wall Sheets",
            warn_icon=True,
        )
        return

    try:
        title_block_sizes = inspect_title_block_sizes(title_blocks)
    except Exception as size_error:
        logger.warning(
            "Could not inspect title-block sheet sizes: %s",
            size_error,
        )
        title_block_sizes = {}

    section_types = collect_section_types()
    if not section_types:
        forms.alert(
            "No Section ViewFamilyType is available in this project.",
            title="Curtain Wall Sheets",
            warn_icon=True,
        )
        return

    dialog = CurtainWallSettingsWindow(
        title_blocks,
        title_block_sizes,
        section_types,
        len(walls),
    )
    dialog.show_dialog()
    settings = dialog.result
    if not settings:
        return

    save_settings(settings)

    try:
        result = create_curtain_wall_sheets(walls, settings)
        if settings["open_sheet"] and result["sheets"]:
            try:
                uidoc.ActiveView = result["sheets"][0]
            except Exception:
                try:
                    uidoc.RequestViewChange(result["sheets"][0])
                except Exception:
                    pass
        show_result(result)
    except Exception as error:
        error_traceback = traceback.format_exc()
        logger.error(error_traceback)
        output.set_title("Curtain Wall Front Elevation Sheets - Error")
        output.print_md("# Curtain Wall Sheets Failed")
        output.print_md("**Error:** {0}".format(str(error)))
        output.print_md("```text\n{0}\n```".format(error_traceback))
        forms.alert(
            "The operation failed and the Revit transaction was rolled back.\n\n"
            "{0}\n\nSee the pyRevit output for the full traceback."
            .format(str(error)),
            title="Curtain Wall Sheets",
            warn_icon=True,
        )


main()
