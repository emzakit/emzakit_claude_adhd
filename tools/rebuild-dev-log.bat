@echo off
setlocal
title emzakit - Rebuild dev-log

rem This repo has no copy of the tools: it runs the plugin's templates directly, with its own configs (Windows).
rem The window stays open so the result can be read; --no-pause skips that.
set "RESULT=1"
set "TOOLS=%~dp0..\skills\principles\templates\tools"

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on PATH.
  goto finished
)

python -X utf8 "%TOOLS%\build_dev_log.py" --config "%~dp0dev-log-config.json"
if errorlevel 1 goto failed
python -X utf8 "%TOOLS%\build_record.py" --config "%~dp0record-config.json"
if errorlevel 1 goto failed
set "RESULT=0"
echo.
echo Done. Refresh dev-log.html to read the dev-log.
goto finished

:failed
echo.
echo The rebuild failed. See the message above before trying again.

:finished
echo.
if /I not "%~1"=="--no-pause" pause
exit /b %RESULT%
