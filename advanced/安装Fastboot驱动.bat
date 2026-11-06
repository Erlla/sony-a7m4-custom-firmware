@echo off
call "%~dp0_launch.cmd" install-driver
exit /b %errorlevel%
