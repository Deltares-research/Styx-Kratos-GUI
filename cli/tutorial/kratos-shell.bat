@echo off
setlocal

rem kratos-shell: open the kratos-cli shell in a folder of your own, with its runs there too.
rem Asks for the folder, or takes it as the first argument; the folder is made if it is not there.
rem   .\kratos-shell.bat                    asks
rem   .\kratos-shell.bat D:\work\my_dike    or takes it straight away

rem The repository root: the first folder up from this script that holds kratos-cli.bat.
set "ROOT=%~dp0"
:find
if exist "%ROOT%kratos-cli.bat" goto :found
for %%I in ("%ROOT%..") do set "UP=%%~fI\"
if /i "%UP%"=="%ROOT%" goto :noroot
set "ROOT=%UP%"
goto :find

:found
set "FOLDER=%~1"
if not defined FOLDER set /p "FOLDER=Folder for the model and its runs: "
if not defined FOLDER goto :nofolder
rem Quotes typed around a path with spaces are not part of it.
set "FOLDER=%FOLDER:"=%"
for %%I in ("%FOLDER%") do set "FOLDER=%%~fI"

if not exist "%FOLDER%\" mkdir "%FOLDER%" || exit /b 1
cd /d "%FOLDER%" || exit /b 1

rem Runs go into this folder too.
set "KRATOS_GUI_RUNS=%FOLDER%"
call "%ROOT%kratos-cli.bat" shell
exit /b %errorlevel%

:nofolder
echo No folder given. 1>&2
exit /b 1

:noroot
echo kratos-cli.bat was not found above %~dp0 1>&2
exit /b 1
