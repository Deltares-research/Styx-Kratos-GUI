@echo off
setlocal

rem The Python launcher keeps Windows dependencies separate from Linux dependencies.

cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 goto :python
py -3 -m backend.launcher --open-browser %*
exit /b %errorlevel%

:python
where python >nul 2>nul
if errorlevel 1 goto :nopython
python -m backend.launcher --open-browser %*
exit /b %errorlevel%

:nopython
echo.
echo Python 3.10+ was not found on PATH. Install it from https://python.org
exit /b 1
