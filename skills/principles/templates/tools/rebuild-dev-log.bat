@echo off
setlocal
title Rebuild dev-log

rem Rebuilds the dev-log page, then the record pages, so the links between them and the theme stay in place (Windows).
rem It finds the tools next to itself. The window stays open so the result can be read; --no-pause skips that.
set "RESULT=1"

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on PATH.
  goto finished
)

python -X utf8 "%~dp0build_dev_log.py"
if errorlevel 1 goto failed
python -X utf8 "%~dp0build_record.py"
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
