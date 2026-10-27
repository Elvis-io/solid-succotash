@echo off
setlocal EnableExtensions

set "DEST=%APPDATA%\pyRevit\Extensions\CurtainWallTools.extension"

echo.
echo Curtain Wall Tools v6 - Isolated Front Views Uninstaller
echo ====================================================
echo.

if not exist "%DEST%\" (
    echo The extension is not installed at:
    echo "%DEST%"
    echo.
    pause
    exit /b 0
)

rmdir /S /Q "%DEST%"
if exist "%DEST%\" (
    echo ERROR: The extension folder could not be removed.
    echo Close Revit and try again.
    echo.
    pause
    exit /b 1
)

echo Uninstallation completed successfully.
echo In Revit, use pyRevit ^> Reload, or restart Revit.
echo.
pause
exit /b 0
