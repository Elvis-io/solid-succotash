# Curtain Wall Tools for pyRevit

A pyRevit extension that creates **one isolated front elevation for every Revit curtain-wall instance**, dimensions the wall where valid references are available, and arranges the finished views across one or more architectural sheets.

## v6: custom view template and isolation

For each curtain wall, the command now:

1. Creates one exterior/front Section view.
2. Creates or reuses a custom Section view template named `CW - FRONT ELEVATION - ISOLATED` by default.
3. Applies Architectural discipline, Fine detail, and Hidden Line display.
4. Permanently hides non-target model elements in that generated view.
5. Retains the host wall, panels, mullions, U/V curtain-grid lines, hosted inserts, and nested panel components.
6. Adds dimensions and notes after isolation so annotations remain visible.
7. Places the view on the selected architectural sheet and creates continuation sheets as needed.

A single Revit view template cannot store a different target element ID for every wall. The template therefore standardizes graphics, while wall-specific isolation is stored directly in each generated view.

## Included features

- One front elevation per unique curtain-wall `Wall` instance
- View naming by curtain-wall type
- Custom reusable isolation view template
- Permanent per-view curtain-wall isolation
- Curtain-grid chain dimensions
- Overall width and height dimensions
- Standard and custom drawing-scale selection
- A0–A4 sheet recognition from actual sheet dimensions
- Viewport packing based on the selected sheet size and orientation
- Automatic continuation sheets
- Optional scale adjustment for oversized viewports
- Dimension and isolation review reports

## Requirements

- Autodesk Revit 2022–2026
- pyRevit compatible with the installed Revit version
- A Revit project document
- A loaded title-block type
- A Section `ViewFamilyType`

The command is written for pyRevit's default IronPython engine and WPF forms.

## Install

Run:

```text
Install_CurtainWallTools.bat
```

or copy `CurtainWallTools.extension` to:

```text
%APPDATA%\pyRevit\Extensions\
```

Reload pyRevit or restart Revit. The command appears at:

```text
Curtain Wall Tools > Documentation > Curtain Wall Sheets
```

## Use

1. Open and save a backup of the Revit project.
2. Run **Curtain Wall Sheets**.
3. Select the title block and Section view type.
4. Keep **Apply a custom view template and permanently isolate each curtain wall** enabled.
5. Accept the default template name or enter a project-specific name.
6. Select scale, dimension, sheet-optimization, and continuation-sheet options.
7. Click **Create Front Views + Sheets**.

The pyRevit report shows whether the template was created or reused, isolated views, hidden non-target elements, sheet utilization, dimensions, and any items requiring review.

## Isolation behavior

The tool controls only stable template graphics parameters: discipline, detail level, and display style. Scale, crop, clipping, phase, design option, and per-element visibility remain view-specific so the sheet-fitting and isolation routines can operate.

The permanent isolation routine gathers the curtain-wall host, panels, mullions, curtain-grid lines, inserts, and nested subcomponents. It then hides other hideable model elements visible in the generated view. If batch hiding fails, it retries elements individually and reports failures.

## Scope

- Active-project curtain-wall `Wall` instances only
- Linked-model curtain walls are excluded
- Mass-based `CurtainSystem` elements are excluded
- Curved walls receive one orthographic projection, not an unrolled elevation
- Every run creates new views and sheets
- Model-specific Revit testing is required before issued documentation

## Development

Validate the extension:

```bash
python tools/validate_extension.py
```

Build the distributable ZIP:

```bash
python tools/build_release.py
```

Static validation checks source syntax, XAML, command controls, required files, and isolation/template implementation. It does not execute Revit transactions.
