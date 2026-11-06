@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
pushd "%~dp0"
if errorlevel 1 exit /b 1
if exist "runtime\python\python.exe" goto portable
if exist ".venv\Scripts\python.exe" goto install
py -3 -m venv .venv
if errorlevel 1 goto failed
:install
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto failed
echo Python setup complete. Read docs/setup.md to supply external resources.
popd
exit /b 0
:portable
"runtime\python\python.exe" -B -X utf8 -m a7m4 doctor
set "result=%errorlevel%"
popd
exit /b %result%
:failed
echo Setup failed. Python 3.11 or later is required.
popd
exit /b 1
