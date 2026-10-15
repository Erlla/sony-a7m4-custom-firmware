@echo off
call "%~dp0_launch.cmd" maintain --action unlock
exit /b %errorlevel%
