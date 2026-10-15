@echo off
call "%~dp0_launch.cmd" maintain --action set_version
exit /b %errorlevel%
