@echo off
call "%~dp0_launch.cmd" maintain --action backup
exit /b %errorlevel%
