@echo off
call "%~dp0_launch_recovery.cmd" --check-connection
exit /b %errorlevel%
