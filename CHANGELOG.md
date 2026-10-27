# Changelog

## v6.0.0 — Custom view template and permanent isolation

- Added a custom Section view template, enabled by default.
- Added an editable template name; default is `CW - FRONT ELEVATION - ISOLATED`.
- Added compatible-template reuse and automatic template creation.
- Limited template control to discipline, detail level, and display style so crop, clipping, scale, phase, and element visibility remain editable.
- Added permanent isolation of the host wall, panels, mullions, curtain-grid lines, hosted inserts, and nested panel components.
- Added batch-hide fallback and isolation warning reporting.
- Kept dimensions and notes visible by creating them after isolation.
- Reorganized the repository as directly installable source.
- Added validation, release packaging, and GitHub Actions CI.
- Removed obsolete versioned archives and the superseded Dynamo prototype.

## v5.0.0 — Front elevation only

- Reduced output to one front elevation per curtain-wall instance.
- Removed rear, interior, and side view options.
- Added shallow front and far clipping.

## v4.0.0 — Architectural sheet optimizer

- Added measured A0–A4 title-block recognition and optimized viewport packing.

## v3.0.0 — Drawing-scale selection

- Added standard and custom drawing-scale selection.

## v2.0.0 — Dimensions and continuation sheets

- Added type-based view naming, curtain-grid dimensions, overall dimensions, and overflow sheets.
