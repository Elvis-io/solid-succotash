#!/usr/bin/env python3
"""Build a distributable ZIP from the clean source tree."""
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
ARCHIVE = DIST / "CurtainWallTools_pyRevit_v6_Isolated_View_Template.zip"
INCLUDE = ["CurtainWallTools.extension", "Install_CurtainWallTools.bat", "Uninstall_CurtainWallTools.bat", "README.md", "CHANGELOG.md"]

subprocess.run(["python", str(ROOT / "tools" / "validate_extension.py")], check=True, cwd=str(ROOT))
DIST.mkdir(exist_ok=True)
if ARCHIVE.exists():
    ARCHIVE.unlink()
with tempfile.TemporaryDirectory() as temp:
    stage = Path(temp) / "CurtainWallTools_pyRevit_v6"
    stage.mkdir()
    for relative in INCLUDE:
        source = ROOT / relative
        destination = stage / relative
        if source.is_dir():
            shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(source, destination)
    with zipfile.ZipFile(ARCHIVE, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(stage.parent))
print(ARCHIVE)
