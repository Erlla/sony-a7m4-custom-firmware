@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
pushd "%~dp0.."
if errorlevel 1 exit /b 1
set "demo_flag="
if "%A7M4_DEMO%"=="1" set "demo_flag=--demo"
if exist "%CD%\a7m4.exe" goto packaged
if defined A7M4_PYTHON if exist "%A7M4_PYTHON%" goto custom_python
if exist "%CD%\.venv\Scripts\python.exe" goto source
echo Runtime missing. Extract the full offline bundle or install source dependencies.
set "result=1"
goto finished
:packaged
"%CD%\a7m4.exe" %demo_flag% %*
set "result=%errorlevel%"
goto finished
:custom_python
"%A7M4_PYTHON%" -m a7m4 %demo_flag% %*
set "result=%errorlevel%"
goto finished
:source
"%CD%\.venv\Scripts\python.exe" -m a7m4 %demo_flag% %*
set "result=%errorlevel%"
:finished
echo.
echo Exit code: %result%
if not "%A7M4_NO_PAUSE%"=="1" pause
popd
exit /b %result%
