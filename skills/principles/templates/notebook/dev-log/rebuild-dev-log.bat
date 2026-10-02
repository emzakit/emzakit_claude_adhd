@echo off
setlocal
title {{PROJECT_NAME}} - Rebuild dev log

rem An absolute path lets this work when the dev-log folder is a symlink or sits in an Obsidian vault.
set "DEV_LOG_BUILDER={{BUILDER_PATH}}"
set "DEV_LOG_RESULT=1"

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on PATH.
  goto finished
)

if not exist "%DEV_LOG_BUILDER%" (
  echo The dev-log builder was not found at "%DEV_LOG_BUILDER%".
  echo Update DEV_LOG_BUILDER in this script if the project has moved.
  goto finished
)

echo Rebuilding the {{PROJECT_NAME}} dev log...
python -X utf8 "%DEV_LOG_BUILDER%"
set "DEV_LOG_RESULT=%ERRORLEVEL%"
echo.
if "%DEV_LOG_RESULT%"=="0" (
  echo Done. Refresh dev-log.html to read the diary.
) else (
  echo The rebuild failed. See the message above before trying again.
)

:finished
echo.
if /I not "%~1"=="--no-pause" pause
exit /b %DEV_LOG_RESULT%
