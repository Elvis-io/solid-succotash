@echo off
setlocal EnableExtensions

set "SOURCE=%~dp0CurtainWallTools.extension"
set "EXTROOT=%APPDATA%\pyRevit\Extensions"
set "DEST=%EXTROOT%\CurtainWallTools.extension"

echo.
echo Curtain Wall Tools v6 - Isolated Front Views Installer
echo ==================================================
echo.

if not exist "%SOURCE%\" (
    echo ERROR: The extension folder was not found beside this installer.
    echo Expected: "%SOURCE%"
    echo.
    pause
    exit /b 1
)

if not exist "%EXTROOT%\" (
    mkdir "%EXTROOT%" 2>nul
    if errorlevel 1 (
        echo ERROR: Could not create the pyRevit Extensions folder:
        echo "%EXTROOT%"
        echo.
        pause
        exit /b 1
    )
)

echo Installing to:
echo "%DEST%"
echo.

robocopy "%SOURCE%" "%DEST%" /E /PURGE /R:2 /W:1 /NFL /NDL /NJH /NJS /NP >nul
set "RC=%ERRORLEVEL%"

if %RC% GEQ 8 (
    echo ERROR: Installation failed. Robocopy exit code: %RC%
    echo.
    pause
    exit /b %RC%
)

echo Installation completed successfully.
echo.
echo In Revit, use pyRevit ^> Reload, or restart Revit.
echo Ribbon location: Curtain Wall Tools ^> Documentation ^> Curtain Wall Sheets
echo.
pause
exit /b 0
