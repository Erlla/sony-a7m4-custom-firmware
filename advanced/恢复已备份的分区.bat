@echo off
call "%~dp0_launch.cmd" maintain --action restore
exit /b %errorlevel%
