#!/usr/bin/env python3
"""Static validation for the Curtain Wall Tools pyRevit extension."""
import ast
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUTTON = ROOT / "CurtainWallTools.extension" / "Curtain Wall Tools.tab" / "Documentation.panel" / "Create Curtain Wall Sheet.pushbutton"
required = [ROOT / "README.md", ROOT / "CHANGELOG.md", ROOT / "Install_CurtainWallTools.bat", ROOT / "Uninstall_CurtainWallTools.bat", BUTTON / "script.py", BUTTON / "ui.xaml", BUTTON / "bundle.yaml", BUTTON / "icon.png", BUTTON / "icon.dark.png"]
checks = []

def check(value, message):
    checks.append((bool(value), message))

for path in required:
    check(path.exists(), "Required file exists: {0}".format(path.relative_to(ROOT)))
loader = (BUTTON / "script.py").read_text(encoding="utf-8")
parts = sorted((BUTTON / "command_parts").glob("*_command.py"))
source = "".join(path.read_text(encoding="utf-8") for path in parts)
xaml = (BUTTON / "ui.xaml").read_text(encoding="utf-8")
try:
    ast.parse(loader)
    for path in parts:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    check(len(parts) == 8, "Eight command source parts parse")
except SyntaxError as error:
    check(False, "Python source parses: {0}".format(error))
try:
    ET.parse(str(BUTTON / "ui.xaml"))
    check(True, "XAML is well formed")
except Exception as error:
    check(False, "XAML is well formed: {0}".format(error))
for handler in re.findall(r'(?:Click|SelectionChanged)="([^"]+)"', xaml):
    check(re.search(r"^\s*def\s+" + re.escape(handler) + r"\s*\(", source, re.M), "XAML handler exists: {0}".format(handler))
for token in ["CreateViewTemplate", "ViewTemplateId", "HideElements", "GetPanelIds", "GetMullionIds", "GetUGridLineIds", "GetVGridLineIds", "GetSubComponentIds", "FindInserts", "SetNonControlledTemplateParameterIds", "DEFAULT_ISOLATION_TEMPLATE_NAME"]:
    check(token in source, "Isolation/template implementation contains {0}".format(token))
check(source.count("DB.ViewSection.CreateSection(") == 1, "Single Section-view creation path")
failed = [message for passed, message in checks if not passed]
for passed, message in checks:
    print("[{0}] {1}".format("PASS" if passed else "FAIL", message))
print("\nAssertions: {0} passed; {1} failed.".format(len(checks) - len(failed), len(failed)))
if failed:
    sys.exit(1)
