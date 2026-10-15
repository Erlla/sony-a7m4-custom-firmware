@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
pushd "%~dp0"
if errorlevel 1 exit /b 1
if exist ".venv\Scripts\python.exe" goto install
py -3 -m venv .venv
if errorlevel 1 goto failed
:install
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto failed
echo Python setup complete. Read docs/setup.md to supply external resources.
popd
exit /b 0
:failed
echo Setup failed. Python 3.11 or later is required.
popd
exit /b 1
