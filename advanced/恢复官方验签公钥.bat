@echo off
call "%~dp0_launch.cmd" maintain --action restore_official
exit /b %errorlevel%
