# -*- coding: utf-8 -*-
"""Create one tightly cropped, isolated front elevation per curtain wall and arrange the views on sheets.

Designed as a pyRevit push-button command for Revit 2022-2026.
The command uses pyRevit's default IronPython engine because its user interface
is built with pyRevit WPF forms.
"""
from __future__ import print_function

import os
import re
import traceback

from pyrevit import DB
from pyrevit import forms
from pyrevit import revit
from pyrevit import script

from System.Collections.Generic import List

try:
    from System.Windows.Controls import ComboBoxItem
except Exception:
    ComboBoxItem = None


__title__ = "Curtain Wall\nSheets"
__author__ = "OpenAI for Elvis Ekwegbo"
__doc__ = (
    "Creates exactly one tightly cropped and isolated front elevation for each "
    "curtain-wall Wall instance, applies a managed view template, optionally "
    "adds curtain-grid and overall dimensions, and optimizes view placement "
    "for measured A0-A4 architectural sheets."
)


doc = revit.doc
uidoc = revit.uidoc
output = script.get_output()
logger = script.get_logger()
config = script.get_config()
XAML_PATH = os.path.join(os.path.dirname(__file__), "ui.xaml")

# Common metric architectural scales shown in the settings dialog. The scale
# ComboBox remains editable, so any positive whole-number denominator can also
# be entered (for example 1:40 or 1:60).
STANDARD_DRAWING_SCALES = [
    5, 10, 20, 25, 40, 50, 75, 100, 125, 150, 200, 250, 300,
    400, 500, 750, 1000, 1500, 2000, 2500, 5000, 10000, 15000, 24000,
]

# Standard metric architectural drawing sheets supported by the sheet-size
# optimizer. Matching is based on the actual ViewSheet.Outline dimensions, not
# on family or type names, so an A3 title block is recognised even when it has
# a company-specific name.
ARCHITECTURAL_SHEET_PROFILES = [
    {"name": "A0", "short_mm": 841.0, "long_mm": 1189.0},
    {"name": "A1", "short_mm": 594.0, "long_mm": 841.0},
    {"name": "A2", "short_mm": 420.0, "long_mm": 594.0},
    {"name": "A3", "short_mm": 297.0, "long_mm": 420.0},
    {"name": "A4", "short_mm": 210.0, "long_mm": 297.0},
]

DEFAULT_ISOLATION_TEMPLATE_NAME = "CW - FRONT ELEVATION - ISOLATED"

# Only stable graphics parameters are controlled by the managed template.
# Scale, crop, clipping, phase, design option and element visibility remain
# view-specific so the sheet optimizer and permanent isolation can operate.
TEMPLATE_CONTROLLED_BUILTIN_PARAMETERS = [
    "VIEW_DETAIL_LEVEL",
    "MODEL_GRAPHICS_STYLE",
    "VIEW_DISCIPLINE",
]


# -----------------------------------------------------------------------------
# General helpers
# -----------------------------------------------------------------------------

def config_value(name, default):
    try:
        return getattr(config, name)
    except Exception:
        return default


def to_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in ("true", "1", "yes", "on"):
        return True
    if text in ("false", "0", "no", "off"):
        return False
    return default


def mm(value):
    """Convert millimetres to Revit internal units."""
    try:
        return DB.UnitUtils.ConvertToInternalUnits(
            float(value), DB.UnitTypeId.Millimeters
        )
    except AttributeError:
        return DB.UnitUtils.ConvertToInternalUnits(
            float(value), DB.DisplayUnitType.DUT_MILLIMETERS
        )


def from_internal_mm(value):
    try:
        return DB.UnitUtils.ConvertFromInternalUnits(
            float(value), DB.UnitTypeId.Millimeters
        )
    except AttributeError:
        return DB.UnitUtils.ConvertFromInternalUnits(
            float(value), DB.DisplayUnitType.DUT_MILLIMETERS
        )


def format_length(value):
    """Format a model length using project units, with a metric fallback."""
    try:
        return DB.UnitFormatUtils.Format(
            doc.GetUnits(), DB.SpecTypeId.Length, float(value), False
        )
    except Exception:
        value_mm = from_internal_mm(value)
        if abs(value_mm - round(value_mm)) < 0.01:
            return "{0:.0f} mm".format(value_mm)
        return "{0:.1f} mm".format(value_mm)


def id_number(element_or_id):
    element_id = getattr(element_or_id, "Id", element_or_id)
    try:
        return int(element_id.Value)
    except Exception:
        return int(element_id.IntegerValue)


def element_type_name(element):
    """Return a stable display name for a Revit ElementType."""
    try:
        parameter = element.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM)
        if parameter:
            value = parameter.AsString()
            if value:
                return value
    except Exception:
        pass

    try:
        value = element.Name
        if value:
            return value
    except Exception:
        pass

    return "Type {0}".format(id_number(element))


def title_block_label(symbol):
    try:
        family_name = symbol.FamilyName
    except Exception:
        try:
            family_name = symbol.Family.Name
        except Exception:
            family_name = "Title Block"
    return "{0} : {1}".format(family_name, element_type_name(symbol))


def architectural_sheet_profile(width_mm, height_mm):
    """Match actual sheet dimensions to a supported A-series profile."""
    actual_short = min(float(width_mm), float(height_mm))
    actual_long = max(float(width_mm), float(height_mm))
    best_match = None
    best_error = None

    for profile in ARCHITECTURAL_SHEET_PROFILES:
        short_error = abs(actual_short - profile["short_mm"])
        long_error = abs(actual_long - profile["long_mm"])
        error = max(short_error, long_error)
        tolerance = max(6.0, profile["long_mm"] * 0.015)
        if error <= tolerance and (best_error is None or error < best_error):
            best_error = error
            best_match = profile

    if best_match is None:
        return None

    orientation = "Landscape" if width_mm >= height_mm else "Portrait"
    return {
        "name": best_match["name"],
        "orientation": orientation,
        "nominal_short_mm": best_match["short_mm"],
        "nominal_long_mm": best_match["long_mm"],
        "match_error_mm": best_error,
    }


def sheet_outline_info(outline):
    """Return actual and nominal sheet-size information from an outline."""
    width_internal = float(outline.Max.U - outline.Min.U)
    height_internal = float(outline.Max.V - outline.Min.V)
    width_mm = from_internal_mm(width_internal)
    height_mm = from_internal_mm(height_internal)
    profile = architectural_sheet_profile(width_mm, height_mm)
    return {
        "width_internal": width_internal,
        "height_internal": height_internal,
        "width_mm": width_mm,
        "height_mm": height_mm,
        "profile": profile,
        "is_architectural": profile is not None,
    }


def sheet_size_description(size_info):
    if not size_info:
        return "Sheet size unavailable"

    width_mm = size_info.get("width_mm", 0.0)
    height_mm = size_info.get("height_mm", 0.0)
    profile = size_info.get("profile")
    if profile:
        return "{0} {1} ({2:.0f} x {3:.0f} mm)".format(
            profile["name"],
            profile["orientation"],
            width_mm,
            height_mm,
        )
    return "Custom / non-A-series ({0:.0f} x {1:.0f} mm)".format(
        width_mm,
        height_mm,
    )


def title_block_option_label(symbol, size_info):
    return "{0}  —  {1}".format(
        sheet_size_description(size_info),
        title_block_label(symbol),
    )


def inspect_title_block_sizes(symbols):
    """Measure every title-block type using temporary rolled-back sheets."""
    results = {}
    transaction = DB.Transaction(doc, "Inspect title block sheet sizes")
    transaction.Start()
    try:
        for symbol in symbols:
            symbol_id = id_number(symbol)
            temporary_sheet = None
            try:
                if isinstance(symbol, DB.FamilySymbol) and not symbol.IsActive:
                    symbol.Activate()
                    doc.Regenerate()
                temporary_sheet = DB.ViewSheet.Create(doc, symbol.Id)
                doc.Regenerate()
                results[symbol_id] = sheet_outline_info(temporary_sheet.Outline)
                doc.Delete(temporary_sheet.Id)
                doc.Regenerate()
            except Exception as error:
                results[symbol_id] = {
                    "width_internal": 0.0,
                    "height_internal": 0.0,
                    "width_mm": 0.0,
                    "height_mm": 0.0,
                    "profile": None,
                    "is_architectural": False,
                    "error": str(error),
                }
                if temporary_sheet is not None:
                    try:
                        doc.Delete(temporary_sheet.Id)
                    except Exception:
                        pass
        transaction.RollBack()
    except Exception:
        try:
            transaction.RollBack()
        except Exception:
            pass
        raise
    return results


def clean_name(value):
    text = str(value or "")
    invalid_characters = [
        "\\", ":", "{", "}", "[", "]", "|", ";", "<", ">", "?", "`", "~"
    ]
    for character in invalid_characters:
        text = text.replace(character, "-")
    return " ".join(text.split()).strip()


def all_sheet_numbers():
    numbers = set()
    for sheet in DB.FilteredElementCollector(doc).OfClass(DB.ViewSheet):
        try:
            numbers.add(sheet.SheetNumber.lower())
        except Exception:
            pass
    return numbers


def reserve_unique_sheet_number(desired_number, used_numbers):
    base_number = clean_name(desired_number) or "CW-001"
    candidate = base_number
    suffix = 1
    while candidate.lower() in used_numbers:
        candidate = "{0}.{1:02d}".format(base_number, suffix)
        suffix += 1
    used_numbers.add(candidate.lower())
    return candidate


def sheet_series_candidate(base_number, page_index):
    """Return a human-friendly continuation number for a zero-based page."""
    base_number = clean_name(base_number) or "CW-001"
    if page_index <= 0:
        return base_number

    match = re.match(r"^(.*?)(\d+)$", base_number)
    if match:
        prefix = match.group(1)
        digits = match.group(2)
        next_number = str(int(digits) + page_index).zfill(len(digits))
        return "{0}{1}".format(prefix, next_number)
    return "{0}-{1:02d}".format(base_number, page_index + 1)


def unique_view_name(base_name, used_names):
    cleaned_base = clean_name(base_name) or "CURTAIN WALL ELEVATION"
    cleaned_base = cleaned_base[:230].rstrip()
    candidate = cleaned_base
    suffix = 1
    while candidate.lower() in used_names:
        suffix += 1
        suffix_text = " ({0})".format(suffix)
        candidate = cleaned_base[:230 - len(suffix_text)].rstrip() + suffix_text
    used_names.add(candidate.lower())
    return candidate


def vector_dot(first, second):
    return (
        first.X * second.X
        + first.Y * second.Y
        + first.Z * second.Z
    )


def projected_coordinate(point, origin, axis):
    return vector_dot(point - origin, axis)


def reference_key(reference):
    try:
        return reference.ConvertToStableRepresentation(doc)
    except Exception:
        try:
            return "E{0}-T{1}".format(
                id_number(reference.ElementId),
                int(reference.ElementReferenceType),
            )
        except Exception:
            return str(reference)


def collect_curtain_walls():
    """Collect each curtain-wall host instance exactly once."""
    walls = []
    seen_ids = set()
    collector = (
        DB.FilteredElementCollector(doc)
        .OfClass(DB.Wall)
        .WhereElementIsNotElementType()
    )
    for wall in collector:
        try:
            wall_id = id_number(wall)
            if (
                wall.WallType.Kind == DB.WallKind.Curtain
                and wall_id not in seen_ids
            ):
                walls.append(wall)
                seen_ids.add(wall_id)
        except Exception:
            continue
    walls.sort(
        key=lambda item: (
            element_type_name(item.WallType).lower(),
            id_number(item),
        )
    )
    return walls


def collect_title_blocks():
    symbols = list(
        DB.FilteredElementCollector(doc)
        .OfCategory(DB.BuiltInCategory.OST_TitleBlocks)
        .WhereElementIsElementType()
    )
    symbols.sort(key=lambda item: title_block_label(item).lower())
    return symbols


def collect_section_types():
    result = []
    for view_type in DB.FilteredElementCollector(doc).OfClass(DB.ViewFamilyType):
        try:
            if view_type.ViewFamily == DB.ViewFamily.Section:
                result.append(view_type)
        except Exception:
            continue
    result.sort(key=lambda item: element_type_name(item).lower())
    return result


def collect_text_note_type_id():
    try:
        text_type = (
            DB.FilteredElementCollector(doc)
            .OfClass(DB.TextNoteType)
            .FirstElement()
        )
        if text_type:
            return text_type.Id
    except Exception:
        pass
    return DB.ElementId.InvalidElementId


def all_used_view_names():
    used = set()
    for view in DB.FilteredElementCollector(doc).OfClass(DB.View):
        try:
            used.add(view.Name.lower())
        except Exception:
            pass
    return used


def view_name_data(walls):
    totals = {}
    counters = {}
    data = {}

    for wall in walls:
        type_name = clean_name(element_type_name(wall.WallType)) or "Curtain Wall"
        key = type_name.lower()
        totals[key] = totals.get(key, 0) + 1

    for wall in walls:
        type_name = clean_name(element_type_name(wall.WallType)) or "Curtain Wall"
        key = type_name.lower()
        counters[key] = counters.get(key, 0) + 1
        data[id_number(wall)] = {
            "type_name": type_name,
            "sequence": counters[key],
            "total": totals[key],
        }
    return data


# -----------------------------------------------------------------------------
# Settings window
# -----------------------------------------------------------------------------

def add_combo_item(combo, label, value):
    if ComboBoxItem is None:
        raise RuntimeError("WPF ComboBoxItem could not be loaded.")
    item = ComboBoxItem()
    item.Content = label
    item.Tag = value
    combo.Items.Add(item)
    return item


def select_combo_label(combo, label):
    wanted = str(label or "")
    for item in combo.Items:
        try:
            if str(item.Content) == wanted:
                combo.SelectedItem = item
                return True
        except Exception:
            pass
    return False


def select_combo_element_id(combo, element_id):
    try:
        wanted = int(element_id)
    except Exception:
        return False
    for item in combo.Items:
        try:
            if id_number(item.Tag) == wanted:
                combo.SelectedItem = item
                return True
        except Exception:
            pass
    return False


def drawing_scale_label(scale):
    return "1 : {0}".format(int(scale))


