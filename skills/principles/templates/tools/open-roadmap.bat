@echo off
setlocal
title Roadmap board

rem Opens the roadmap board (Windows). It finds the tools next to itself, so the project can live anywhere.
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on PATH.
  goto failed
)

echo Opening the roadmap board in your browser...
python -X utf8 "%~dp0roadmap_board.py" %*
if errorlevel 1 goto failed
exit /b 0

:failed
echo.
pause
exit /b 1
