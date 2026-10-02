@echo off
setlocal
title emzakit - Roadmap board

rem This repo has no copy of the tools: it runs the plugin's templates directly, with its own config (Windows).
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on PATH.
  goto failed
)

echo Opening the roadmap board in your browser...
python -X utf8 "%~dp0..\skills\principles\templates\tools\roadmap_board.py" --config "%~dp0record-config.json" %*
if errorlevel 1 goto failed
exit /b 0

:failed
echo.
pause
exit /b 1
