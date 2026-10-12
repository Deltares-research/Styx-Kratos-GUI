@echo off
setlocal

rem kratos-cli: build, mesh, stage, export, run and read a model in the terminal.
rem Runs in your own folder, so the paths you type are yours. Uses the environment
rem run.bat makes (.venv-windows), and makes it first when it is not there yet.

set "ROOT=%~dp0"
set "PYTHON=%ROOT%.venv-windows\Scripts\python.exe"
if exist "%PYTHON%" goto :run

echo Setting up the Python environment first, once... 1>&2
pushd "%ROOT%"
where py >nul 2>nul
if errorlevel 1 goto :python
py -3 -m backend.launcher --check 1>&2
goto :made

:python
where python >nul 2>nul
if errorlevel 1 goto :nopython
python -m backend.launcher --check 1>&2

:made
set "SETUP=%errorlevel%"
popd
if not "%SETUP%"=="0" exit /b %SETUP%

:run
"%PYTHON%" "%ROOT%cli\__main__.py" %*
exit /b %errorlevel%

:nopython
popd
echo Python 3.10+ was not found on PATH. Install it from https://python.org 1>&2
exit /b 1
