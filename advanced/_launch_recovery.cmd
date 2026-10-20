@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
pushd "%~dp0.."
if errorlevel 1 exit /b 2
if "%A7M4_DEMO%"=="1" goto no_demo
if defined A7M4_PYTHON if exist "%A7M4_PYTHON%" goto custom_python
if exist "%CD%\.venv\Scripts\python.exe" goto source
echo Python 3.11+ missing. Run setup.bat or set A7M4_PYTHON.
set "result=2"
goto finished
:no_demo
echo Recovery does not use A7M4_DEMO. Run the offline tests instead.
set "result=2"
goto finished
:custom_python
"%A7M4_PYTHON%" -B -X utf8 -m a7m4.recover_sd %*
set "result=%errorlevel%"
goto finished
:source
"%CD%\.venv\Scripts\python.exe" -B -X utf8 -m a7m4.recover_sd %*
set "result=%errorlevel%"
:finished
echo.
echo Exit code: %result%
if not "%A7M4_NO_PAUSE%"=="1" pause
popd
exit /b %result%
