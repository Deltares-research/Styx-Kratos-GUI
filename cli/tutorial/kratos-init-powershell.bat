@echo off
setlocal

rem kratos-init-powershell: a PowerShell ready for 1_How_to_create_project.md.
rem Checks that Kratos is set up, builds the Python environment the first time, then opens
rem PowerShell in the model's folder with $repo, $model, $cli and $py already set, and the
rem runs kept in that folder too (KRATOS_GUI_RUNS).
rem   .\kratos-init-powershell.bat                     asks for the project folder, where the .py is
rem   .\kratos-init-powershell.bat D:\work\my_model    or takes it straight away
rem Double-click it, or run it from PowerShell; `exit` leaves the PowerShell it opened.

rem The repository root: the first folder up from this script that holds kratos-cli.bat.
set "ROOT=%~dp0"
:find
if exist "%ROOT%kratos-cli.bat" goto :found
for %%I in ("%ROOT%..") do set "UP=%%~fI\"
if /i "%UP%"=="%ROOT%" goto :noroot
set "ROOT=%UP%"
goto :find

:found
set "MODEL=%~1"
if not defined MODEL set /p "MODEL=Project folder (where the .py file is): "
if not defined MODEL goto :nofolder
rem Quotes typed around a path with spaces are not part of it.
set "MODEL=%MODEL:"=%"
for %%I in ("%MODEL%") do set "MODEL=%%~fI"
for %%I in ("%ROOT%.") do set "REPO=%%~fI"
if not exist "%MODEL%\" goto :nomodel
if not exist "%MODEL%\*.py" goto :nopy

rem Kratos: kratos.local.json in the root, or KRATOS_GUI_PYTHON.
if exist "%REPO%\kratos.local.json" goto :kratos
if defined KRATOS_GUI_PYTHON goto :kratos
echo Kratos is not set up on this machine yet: kratos.local.json is not in %REPO%.
echo Follow steps 1 and 2 of %REPO%\docs\KRATOS_SETUP.md, then run this again.
goto :fail

:kratos
rem The Python environment: kratos-cli.bat makes it the first time.
if not exist "%REPO%\.venv-windows\Scripts\python.exe" echo Building the Python environment, once; this can take a few minutes...
call "%REPO%\kratos-cli.bat" --help >nul || goto :fail

powershell -NoExit -NoLogo -Command ^
  "$repo = '%REPO%'; $model = '%MODEL%';" ^
  "$cli = \"$repo\kratos-cli.bat\"; $py = \"$repo\.venv-windows\Scripts\python.exe\";" ^
  "Set-Location $model; $env:KRATOS_GUI_RUNS = $model;" ^
  "Write-Host 'Ready. In this PowerShell:' -ForegroundColor Green;" ^
  "Write-Host \"  `$repo  = $repo\"; Write-Host \"  `$model = $model\";" ^
  "Write-Host \"  `$cli   = $cli\"; Write-Host \"  `$py    = $py\";" ^
  "Write-Host \"  runs go into $env:KRATOS_GUI_RUNS\";" ^
  "Write-Host '`exit` closes it.'"
exit /b 0

:nofolder
echo No folder given.
goto :fail

:nomodel
echo The folder %MODEL% is not there.
goto :fail

:nopy
echo There is no .py file in %MODEL%: give the folder that holds the model's script.
goto :fail

:noroot
echo kratos-cli.bat was not found above %~dp0

:fail
rem Keep the message on screen when it was double-clicked.
pause
exit /b 1
