def populate_drawing_scale_combo(combo, saved_scale):
    combo.Items.Clear()
    combo.SelectedItem = None
    for scale in STANDARD_DRAWING_SCALES:
        # Strings are used here instead of ComboBoxItem objects so the editable
        # text value is always the visible ratio and can be parsed reliably.
        combo.Items.Add(drawing_scale_label(scale))

    try:
        saved_value = parse_drawing_scale(saved_scale)
    except Exception:
        saved_value = 50

    saved_label = drawing_scale_label(saved_value)
    for index in range(combo.Items.Count):
        try:
            if str(combo.Items[index]) == saved_label:
                combo.SelectedIndex = index
                combo.Text = saved_label
                return
        except Exception:
            pass

    # Retain a previously entered custom denominator that is not in the list.
    combo.SelectedItem = None
    combo.Text = saved_label


def parse_drawing_scale(value):
    """Return a positive whole-number scale denominator from common formats."""
    text = str(value or "").strip().lower()
    text = text.replace("scale", "").replace(" ", "")
    if not text:
        raise ValueError("Select or enter a drawing scale.")

    if ":" in text:
        text = text.rsplit(":", 1)[-1]
    elif "/" in text:
        parts = text.rsplit("/", 1)
        text = parts[-1]

    text = text.replace(",", ".")
    try:
        number = float(text)
    except Exception:
        raise ValueError(
            "Drawing scale must be entered as a denominator such as 50 or 1:50."
        )

    rounded = int(round(number))
    if rounded < 1:
        raise ValueError("Drawing scale must be at least 1:1.")
    if abs(number - rounded) > 0.000001:
        raise ValueError("Drawing scale denominator must be a whole number.")
    return rounded


class CurtainWallSettingsWindow(forms.WPFWindow):
    def __init__(
        self,
        title_blocks,
        title_block_sizes,
        section_types,
        wall_count,
    ):
        forms.WPFWindow.__init__(self, XAML_PATH)
        self.result = None
        self.title_block_sizes = title_block_sizes

        self.wall_count_text.Text = (
            "{0} curtain-wall instance{1} found in the active project."
            .format(wall_count, "" if wall_count == 1 else "s")
        )

        saved_title_block = config_value("title_block_label", "")
        saved_title_block_id = config_value("title_block_id", "")
        profile_order = {"A0": 0, "A1": 1, "A2": 2, "A3": 3, "A4": 4}

        def title_block_order(symbol):
            size_info = title_block_sizes.get(id_number(symbol)) or {}
            profile = size_info.get("profile")
            if profile:
                return (
                    0,
                    profile_order.get(profile.get("name"), 99),
                    0 if profile.get("orientation") == "Landscape" else 1,
                    title_block_label(symbol).lower(),
                )
            return (1, 99, 0, title_block_label(symbol).lower())

        for symbol in sorted(title_blocks, key=title_block_order):
            size_info = title_block_sizes.get(id_number(symbol))
            add_combo_item(
                self.title_block_combo,
                title_block_option_label(symbol, size_info),
                symbol,
            )
        selected_saved_title_block = select_combo_element_id(
            self.title_block_combo,
            saved_title_block_id,
        )
        if not selected_saved_title_block:
            # Preserve selection from older versions that saved only the plain
            # family/type label rather than the element id.
            for item in self.title_block_combo.Items:
                try:
                    if title_block_label(item.Tag) == str(saved_title_block):
                        self.title_block_combo.SelectedItem = item
                        selected_saved_title_block = True
                        break
                except Exception:
                    pass
        if not selected_saved_title_block:
            self.title_block_combo.SelectedIndex = 0

        saved_section_type = config_value("section_type_label", "")
        for section_type in section_types:
            add_combo_item(
                self.section_type_combo,
                element_type_name(section_type),
                section_type,
            )
        if not select_combo_label(self.section_type_combo, saved_section_type):
            self.section_type_combo.SelectedIndex = 0

        self.front_only_text.Text = (
            "Front-only mode is active: one front elevation is created for "
            "each curtain-wall instance. Rear, interior, side and duplicate "
            "directions are not generated."
        )

        self.sheet_number_text.Text = str(
            config_value("sheet_number", "CW-001")
        )
        self.sheet_name_text.Text = str(
            config_value("sheet_name", "CURTAIN WALL ELEVATIONS")
        )
        saved_scale = config_value(
            "drawing_scale",
            config_value("start_scale", "50"),
        )
        populate_drawing_scale_combo(self.scale_combo, saved_scale)
        self.crop_margin_text.Text = str(
            config_value("crop_margin_mm", "300")
        )
        self.viewport_gap_text.Text = str(
            config_value("viewport_gap_mm", "10")
        )
        self.sheet_margin_text.Text = str(
            config_value("sheet_margin_mm", "15")
        )
        self.bottom_reserve_text.Text = str(
            config_value("bottom_reserve_mm", "35")
        )
        self.dimension_spacing_text.Text = str(
            config_value("dimension_spacing_mm", "300")
        )

        self.name_by_type_check.IsChecked = to_bool(
            config_value("name_by_type", True), True
        )
        self.isolate_view_check.IsChecked = to_bool(
            config_value("isolate_view", True), True
        )
        self.view_template_name_text.Text = str(
            config_value(
                "view_template_name",
                DEFAULT_ISOLATION_TEMPLATE_NAME,
            )
        )
        self.dimension_grids_check.IsChecked = to_bool(
            config_value("dimension_grids", True), True
        )
        self.dimension_overall_check.IsChecked = to_bool(
            config_value("dimension_overall", True), True
        )
        self.optimize_sheet_check.IsChecked = to_bool(
            config_value("optimize_sheet", True), True
        )
        self.multiple_sheets_check.IsChecked = to_bool(
            config_value("multiple_sheets", True), True
        )
        self.auto_fit_check.IsChecked = to_bool(
            config_value("auto_fit", True), True
        )
        self.open_sheet_check.IsChecked = to_bool(
            config_value("open_sheet", True), True
        )

        self.create_button.Content = "Create {0} Front View{1} + Sheet{2}".format(
            wall_count,
            "" if wall_count == 1 else "s",
            "" if wall_count == 1 else "s",
        )
        self.title_block_changed(None, None)

    def _selected_title_block_size(self):
        selected_item = self.title_block_combo.SelectedItem
        if selected_item is None:
            return None
        try:
            return self.title_block_sizes.get(id_number(selected_item.Tag))
        except Exception:
            return None

    def title_block_changed(self, sender, args):
        size_info = self._selected_title_block_size()
        if size_info and size_info.get("is_architectural"):
            self.sheet_size_text.Text = (
                "Detected {0}. The optimizer will use the actual sheet outline "
                "and orientation when calculating viewport positions."
                .format(sheet_size_description(size_info))
            )
        elif size_info and size_info.get("width_mm", 0.0) > 0.0:
            self.sheet_size_text.Text = (
                "Detected {0}. This is not a supported architectural A-series "
                "size; disable the architectural optimizer or choose A0-A4."
                .format(sheet_size_description(size_info))
            )
        else:
            self.sheet_size_text.Text = (
                "The selected title block could not be measured. Disable the "
                "architectural optimizer or choose another title block."
            )

    def _set_error(self, message):
        self.status_text.Text = message

    def _parse_number(self, control, field_name, minimum, integer=False):
        raw_value = str(control.Text or "").strip().replace(",", ".")
        try:
            value = float(raw_value)
        except Exception:
            raise ValueError("{0} must be a number.".format(field_name))

        if value < minimum:
            raise ValueError(
                "{0} must be at least {1}.".format(field_name, minimum)
            )

        if integer:
            rounded = int(round(value))
            if abs(value - rounded) > 0.000001:
                raise ValueError("{0} must be a whole number.".format(field_name))
            return rounded
        return value

    def _selected_drawing_scale(self):
        text = str(self.scale_combo.Text or "").strip()
        if not text and self.scale_combo.SelectedItem is not None:
            text = str(self.scale_combo.SelectedItem)
        return parse_drawing_scale(text)

    def create_click(self, sender, args):
        try:
            sheet_number = clean_name(self.sheet_number_text.Text)
            sheet_name = clean_name(self.sheet_name_text.Text)
            if not sheet_number:
                raise ValueError("Enter a sheet number.")
            if not sheet_name:
                raise ValueError("Enter a sheet name.")
            if self.title_block_combo.SelectedItem is None:
                raise ValueError("Select a title-block type.")
            if self.section_type_combo.SelectedItem is None:
                raise ValueError("Select a section view type.")
            selected_title_block = self.title_block_combo.SelectedItem.Tag
            selected_size_info = self._selected_title_block_size()
            optimize_sheet = to_bool(
                self.optimize_sheet_check.IsChecked,
                True,
            )
            if optimize_sheet and not (
                selected_size_info
                and selected_size_info.get("is_architectural")
            ):
                raise ValueError(
                    "The architectural sheet optimizer supports measured "
                    "A0, A1, A2, A3, and A4 title blocks only. Choose a "
                    "supported title block or disable the optimizer."
                )

            isolate_view = to_bool(
                self.isolate_view_check.IsChecked,
                True,
            )
            view_template_name = clean_name(
                self.view_template_name_text.Text
            )
            if isolate_view and not view_template_name:
                raise ValueError(
                    "Enter a name for the isolation view template."
                )

            self.result = {
                "title_block": selected_title_block,
                "title_block_id": id_number(selected_title_block),
                "title_block_label": title_block_label(selected_title_block),
                "title_block_size": selected_size_info,
                "section_type": self.section_type_combo.SelectedItem.Tag,
                "section_type_label": str(
                    self.section_type_combo.SelectedItem.Content
                ),
                "view_side": "Front",
                "sheet_number": sheet_number,
                "sheet_name": sheet_name,
                "start_scale": self._selected_drawing_scale(),
                "crop_margin_mm": self._parse_number(
                    self.crop_margin_text, "Crop margin", 0
                ),
                "viewport_gap_mm": self._parse_number(
                    self.viewport_gap_text, "Viewport gap", 0
                ),
                "sheet_margin_mm": self._parse_number(
                    self.sheet_margin_text, "Sheet edge margin", 0
                ),
                "bottom_reserve_mm": self._parse_number(
                    self.bottom_reserve_text, "Bottom reserved area", 0
                ),
                "dimension_spacing_mm": self._parse_number(
                    self.dimension_spacing_text, "Dimension line spacing", 1
                ),
                "name_by_type": to_bool(
                    self.name_by_type_check.IsChecked, True
                ),
                "isolate_view": isolate_view,
                "view_template_name": (
                    view_template_name or DEFAULT_ISOLATION_TEMPLATE_NAME
                ),
                "dimension_grids": to_bool(
                    self.dimension_grids_check.IsChecked, True
                ),
                "dimension_overall": to_bool(
                    self.dimension_overall_check.IsChecked, True
                ),
                "optimize_sheet": optimize_sheet,
                "multiple_sheets": to_bool(
                    self.multiple_sheets_check.IsChecked, True
                ),
                "auto_fit": to_bool(self.auto_fit_check.IsChecked, True),
                "open_sheet": to_bool(self.open_sheet_check.IsChecked, True),
            }
            self.Close()
        except ValueError as error:
            self._set_error(str(error))
        except Exception as error:
            self._set_error("Invalid settings: {0}".format(error))

    def reset_click(self, sender, args):
        self.sheet_number_text.Text = "CW-001"
        self.sheet_name_text.Text = "CURTAIN WALL ELEVATIONS"
        populate_drawing_scale_combo(self.scale_combo, 50)
        self.crop_margin_text.Text = "300"
        self.viewport_gap_text.Text = "10"
        self.sheet_margin_text.Text = "15"
        self.bottom_reserve_text.Text = "35"
        self.dimension_spacing_text.Text = "300"
        self.name_by_type_check.IsChecked = True
        self.isolate_view_check.IsChecked = True
        self.view_template_name_text.Text = (
            DEFAULT_ISOLATION_TEMPLATE_NAME
        )
        self.dimension_grids_check.IsChecked = True
        self.dimension_overall_check.IsChecked = True
        self.optimize_sheet_check.IsChecked = True
        self.multiple_sheets_check.IsChecked = True
        self.auto_fit_check.IsChecked = True
        self.open_sheet_check.IsChecked = True
        self.status_text.Text = "Defaults restored."

    def cancel_click(self, sender, args):
        self.result = None
        self.Close()


