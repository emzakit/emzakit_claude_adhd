@echo off
setlocal
title {{PROJECT_NAME}} - Roadmap board

rem An absolute path lets this work when the notebook is a symlink or sits in an Obsidian vault.
set "BOARD_SCRIPT={{BOARD_PATH}}"

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on PATH.
  goto failed
)

if not exist "%BOARD_SCRIPT%" (
  echo The roadmap board was not found at "%BOARD_SCRIPT%".
  echo Update BOARD_SCRIPT in this script if the project has moved.
  goto failed
)

echo Opening the {{PROJECT_NAME}} roadmap board in your browser...
python -X utf8 "%BOARD_SCRIPT%"
if errorlevel 1 goto failed
exit /b 0

:failed
echo.
pause
exit /b 1
