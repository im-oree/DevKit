@echo off
REM DevKit launcher - double-click to open GUI
cd /d "%~dp0"
python devkit.py
if errorlevel 1 pause
