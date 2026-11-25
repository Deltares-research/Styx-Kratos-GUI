@echo off
setlocal

rem Runs Styx with the latest Deltares Kratos release from the internal Nexus.
rem
rem The server itself starts exactly as with run.bat. Kratos runs in a separate
rem interpreter (see core/analysis/calculation.py): a Python 3.13 venv, .venv-kratos,
rem holding the DeltaresRelease* wheels, which are built for CPython 3.13 on Windows only.
rem Every start upgrades that venv to the newest release on the index.
rem
rem The index needs a login. Put it in %USERPROFILE%\.netrc, never in this repository:
rem     machine internal-artifacts.deltares.nl
rem     login <nexus user>
rem     password <nexus token>

cd /d "%~dp0"

set "KRATOS_VENV=%~dp0.venv-kratos"
set "KRATOS_PY=%KRATOS_VENV%\Scripts\python.exe"
set "INTERNAL_INDEX=https://internal-artifacts.deltares.nl/repository/kratos-python-dev/simple/"

py -3.13 -c "pass" >nul 2>nul
if errorlevel 1 (
    echo.
    echo Python 3.13 was not found ^(py -3.13^). The Deltares Kratos wheels need exactly 3.13.
    echo Install it from https://python.org
    exit /b 1
)

if not exist "%KRATOS_PY%" (
    echo Creating .venv-kratos ^(Python 3.13^)...
    py -3.13 -m venv "%KRATOS_VENV%"
    if errorlevel 1 exit /b 1
)

rem numpy is Kratos' only third-party dependency. It comes from PyPI first, so that the
rem internal install below never has to look anything up on a public index: the
rem Deltares packages are resolved from the internal index alone.
"%KRATOS_PY%" -m pip install --disable-pip-version-check --quiet --only-binary :all: numpy
if errorlevel 1 exit /b 1

rem All current Deltares Kratos packages, named explicitly so each is upgraded. Not
set "KRATOS_PACKAGES=DeltaresReleaseKratosMultiphysics DeltaresReleaseGeoMechanicsApplication DeltaresReleaseStructuralMechanicsApplication DeltaresReleaseLinearSolversApplication"

echo Updating to the latest Deltares Kratos release...
"%KRATOS_PY%" -m pip install --disable-pip-version-check --quiet --upgrade ^
    --index-url "%INTERNAL_INDEX%" %KRATOS_PACKAGES%
if errorlevel 1 (
    "%KRATOS_PY%" -c "import KratosMultiphysics.GeoMechanicsApplication" >nul 2>nul
    if errorlevel 1 (
        echo.
        echo Could not install Kratos from %INTERNAL_INDEX%
        echo Check the VPN and the login in %USERPROFILE%\.netrc.
        exit /b 1
    )
    echo WARNING: could not reach the internal index; using the Kratos already installed.
)

for /f "delims=" %%v in ('call "%KRATOS_PY%" -c "from importlib.metadata import version; print(version('DeltaresReleaseGeoMechanicsApplication'))"') do set "KRATOS_VERSION=%%v"
echo Kratos: Deltares release %KRATOS_VERSION%

rem Wins over kratos.local.json. KRATOS_GUI_KRATOS is cleared so a build directory set
rem elsewhere cannot shadow the installed wheels.
set "KRATOS_GUI_PYTHON=%KRATOS_PY%"
set "KRATOS_GUI_KRATOS="

call "%~dp0run.bat" %*
exit /b %errorlevel%
